import os
import json
import time
import threading
import queue
import traceback
import importlib.util
from flask import Flask, request, jsonify
import psycopg2, psycopg2.extras
import websocket, requests
from concurrent.futures import ThreadPoolExecutor, TimeoutError

# =========================================================
# ENV
# =========================================================
PORT = int(os.getenv("PORT", 5000))
NEON_DATABASE_URL = os.getenv("NEON_DATABASE_URL")
ENGINE_DEBUG = os.getenv("ENGINE_DEBUG", "0") == "1"

# =========================================================
# FLASK
# =========================================================
app = Flask(__name__)

# =========================================================
# ENGINE CORE STATE
# =========================================================
ENGINE = {
    "token": None,
    "ws": None,
    "connected": False,
    "rooms": set(),
    "rooms_lock": threading.Lock(),
    "plugins": {},
    "games": {},
    "logs": queue.Queue(maxsize=1000)
}

ROOM_LOCKS = {}
USER_LOCKS = {}
LOCKS_LOCK = threading.Lock()
ROOM_STATES = {}  # room_id -> state dict

# =========================================================
# LOGGING
# =========================================================
def log(msg):
    if ENGINE_DEBUG:
        print(msg)
    try:
        ENGINE["logs"].put_nowait(msg)
    except:
        pass

# =========================================================
# LOCK HELPERS
# =========================================================
def room_lock(room):
    with LOCKS_LOCK:
        if room not in ROOM_LOCKS:
            ROOM_LOCKS[room] = threading.Lock()
        return ROOM_LOCKS[room]

def user_lock(user):
    with LOCKS_LOCK:
        if user not in USER_LOCKS:
            USER_LOCKS[user] = threading.Lock()
        return USER_LOCKS[user]

# =========================================================
# DATABASE
# =========================================================
class Database:
    def __init__(self):
        self.lock = threading.Lock()
        self.conn = None
        self._connect()

    def _connect(self):
        try:
            if NEON_DATABASE_URL:
                self.conn = psycopg2.connect(NEON_DATABASE_URL)
                log("DB connected")
            else:
                log("Warning: NEON_DATABASE_URL not set, DB disabled")
                self.conn = None
        except Exception as e:
            log(f"DB connection failed: {e}")
            self.conn = None

    def atomic(self, fn, retries=3, delay=1):
        for attempt in range(retries):
            with self.lock:
                if self.conn is None:
                    self._connect()
                if self.conn is None:
                    return None
                try:
                    with self.conn:
                        with self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                            return fn(cur)
                except psycopg2.OperationalError:
                    log("DB OperationalError, reconnecting...")
                    self._connect()
                    time.sleep(delay)
                except Exception as e:
                    log(f"DB Error: {e}")
                    return None
        return None

DB = Database()

# =========================================================
# AUTO-INIT TABLES
# =========================================================
def init_tables():
    tables = {
        "scores": """
            CREATE TABLE IF NOT EXISTS scores (
                user_id TEXT,
                game TEXT,
                score BIGINT,
                PRIMARY KEY(user_id, game)
            );
        """,
        "wallet": """
            CREATE TABLE IF NOT EXISTS wallet (
                user_id TEXT PRIMARY KEY,
                balance BIGINT
            );
        """,
        # future plugin/game tables can be added here
        # Example:
        # "tictactoe_state": """
        #     CREATE TABLE IF NOT EXISTS tictactoe_state (
        #         room_id TEXT PRIMARY KEY,
        #         board TEXT,
        #         players TEXT[]
        #     );
        # """
    }
    for sql in tables.values():
        DB.atomic(lambda cur: cur.execute(sql))
    log("DB tables checked/created")

# Call at boot
init_tables()

# =========================================================
# SAFE APIs
# =========================================================
class DB_API:
    def add_score(self, user, game, points):
        with user_lock(user):
            def q(cur):
                cur.execute("""
                INSERT INTO scores(user_id, game, score)
                VALUES (%s,%s,%s)
                ON CONFLICT (user_id,game)
                DO UPDATE SET score = scores.score + %s
                """, (user, game, points, points))
            DB.atomic(q)

    def get_score(self, user, game):
        def q(cur):
            cur.execute(
                "SELECT score FROM scores WHERE user_id=%s AND game=%s",
                (user, game)
            )
            r = cur.fetchone()
            return r["score"] if r else 0
        return DB.atomic(q)

    def leaderboard(self, game, limit=10):
        def q(cur):
            cur.execute("""
            SELECT user_id, score FROM scores
            WHERE game=%s ORDER BY score DESC LIMIT %s
            """, (game, limit))
            return cur.fetchall()
        return DB.atomic(q)

class Economy_API:
    def add_currency(self, user, amount):
        with user_lock(user):
            def q(cur):
                cur.execute("""
                INSERT INTO wallet(user_id,balance)
                VALUES (%s,%s)
                ON CONFLICT (user_id)
                DO UPDATE SET balance = wallet.balance + %s
                """, (user, amount, amount))
            DB.atomic(q)

class Media_API:
    def send_image(self, room, url, caption=""):
        send_raw({
            "handler": "chatroommessage",
            "type": "image",
            "roomid": room,
            "url": url,
            "text": caption
        })

    def send_audio(self, room, url):
        send_raw({
            "handler": "chatroommessage",
            "type": "audio",
            "roomid": room,
            "url": url
        })

# =========================================================
# GAME MANAGER
# =========================================================
class GameManager:
    TIMEOUT = 120

    def ensure_room(self, room):
        ROOM_STATES.setdefault(room, {
            "active_game": None,
            "players": set(),
            "started_at": None,
            "state": {}
        })

    def start_game(self, room, game, players):
        self.ensure_room(room)
        with room_lock(room):
            rs = ROOM_STATES[room]
            rs["active_game"] = game
            rs["players"] = set(players)
            rs["started_at"] = time.time()
            rs["state"] = {}

    def end_game_safe(self, room, notify=True):
        lock = room_lock(room)
        with lock:
            rs = ROOM_STATES.pop(room, None)
            if not rs:
                return
            if notify and rs.get("players"):
                game_name = rs.get("active_game", "Unknown Game")
                player_list = ", ".join(rs["players"])
                text = f"Game '{game_name}' ended due to inactivity. Thanks: {player_list}!"
                send_raw({
                    "handler": "chatroommessage",
                    "type": "text",
                    "roomid": room,
                    "text": text
                })

    def player_left(self, room, user):
        lock = room_lock(room)
        with lock:
            rs = ROOM_STATES.get(room)
            if not rs:
                return
            rs["players"].discard(user)
            if len(rs["players"]) == 0:
                self.end_game_safe(room, notify=False)

    def cleanup_loop(self):
        while True:
            now = time.time()
            for room in list(ROOM_STATES.keys()):
                lock = room_lock(room)
                with lock:
                    rs = ROOM_STATES.get(room)
                    if rs and rs.get("started_at") and now - rs["started_at"] > self.TIMEOUT:
                        log(f"Game timeout in {room}")
                        self.end_game_safe(room)
            time.sleep(5)

GAME_MANAGER = GameManager()
threading.Thread(target=GAME_MANAGER.cleanup_loop, daemon=True).start()

# =========================================================
# WEBSOCKET
# =========================================================
def send_raw(payload):
    if ENGINE["connected"] and ENGINE["ws"]:
        try:
            ENGINE["ws"].send(json.dumps(payload))
        except Exception as e:
            log(f"WS send error: {e}")

def on_message(ws, msg):
    try:
        data = json.loads(msg)
        handler = data.get("handler")

        if handler == "joinchatroom":
            with ENGINE["rooms_lock"]:
                ENGINE["rooms"].add(data["roomid"])
        elif handler == "leavechatroom":
            with ENGINE["rooms_lock"]:
                ENGINE["rooms"].discard(data["roomid"])
        elif handler == "chatroommessage":
            room = data["roomid"]
            user = data.get("from")
            text = data.get("text", "")

            # Plugin execution
            for trigger, plugin in ENGINE["plugins"].items():
                if text.startswith(trigger):
                    execute_plugin(plugin, user, room, text)
            
            # Game execution
            for trigger, game_func in ENGINE["games"].items():
                if text.startswith(trigger):
                    execute_plugin(game_func, user, room, text)

    except Exception:
        log(traceback.format_exc())

def on_open(ws):
    ENGINE["connected"] = True
    log("WebSocket connected")

def on_close(ws, close_status_code=None, close_msg=None):
    ENGINE["connected"] = False
    log(f"WebSocket disconnected ({close_status_code} {close_msg})")

def start_ws():
    def run():
        retry_delay = 1
        while True:
            if not ENGINE.get("token"):
                time.sleep(1)
                continue
            try:
                ws = websocket.WebSocketApp(
                    f"wss://app.howdies.app/howdies?token={ENGINE['token']}",
                    on_open=on_open,
                    on_message=on_message,
                    on_close=on_close
                )
                ENGINE["ws"] = ws
                ws.run_forever()
                retry_delay = 1
            except Exception as e:
                log(f"WS loop error: {e}")
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60)
    threading.Thread(target=run, daemon=True).start()

# =========================================================
# PLUGIN EXECUTION
# =========================================================
def execute_plugin(plugin, user, room, msg):
    def run_plugin():
        start = time.time()
        try:
            state = ROOM_STATES.setdefault(room, {})
            plugin(
                user=user,
                msg=msg,
                room_id=room,
                state=state,
                send_text=lambda m: send_raw({
                    "handler": "chatroommessage",
                    "type": "text",
                    "roomid": room,
                    "text": m
                }),
                send_raw=send_raw,
                db_api=DB_API(),
                economy_api=Economy_API(),
                media_api=Media_API(),
                add_log=log
            )
        except Exception:
            log(traceback.format_exc())
        finally:
            if time.time() - start > 3:
                log("Plugin execution slow warning")

    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(run_plugin)
    try:
        future.result(timeout=5)
    except TimeoutError:
        log("Plugin execution timed out")
    finally:
        executor.shutdown(wait=False)

# =========================================================
# PLUGIN LOADER
# =========================================================
def load(folder, target):
    if not os.path.isdir(folder):
        os.makedirs(folder)
    for f in os.listdir(folder):
        if f.endswith(".py"):
            p = os.path.join(folder, f)
            spec = importlib.util.spec_from_file_location(f, p)
            mod = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(mod)
                if mod.TRIGGER in target:
                    log(f"Warning: Duplicate plugin trigger {mod.TRIGGER}")
                target[mod.TRIGGER] = mod.handle
                log(f"Loaded {f}")
            except Exception as e:
                log(f"Failed to load {f}: {e}")

# =========================================================
# FLASK ROUTES
# =========================================================
@app.route("/login", methods=["POST"])
def login():
    data = request.json
    if not data or "botId" not in data or "password" not in data:
         return jsonify({"ok": False, "error": "Missing botId or password"}), 400

    r = requests.post("https://api.howdies.app/api/login", json=data)
    if r.status_code != 200:
        return jsonify({"ok": False, "error": f"API Error: {r.text}"}), 400
        
    resp_data = r.json()
    if "token" not in resp_data:
        return jsonify({"ok": False, "error": "Login failed (No token)"}), 400

    ENGINE["token"] = resp_data["token"]
    start_ws()
    return jsonify({"ok": True})

@app.route("/logout", methods=["POST"])
def logout():
    ENGINE["token"] = None
    ENGINE["connected"] = False
    if ENGINE["ws"]:
        try:
            ENGINE["ws"].close()
        except:
            pass
        ENGINE["ws"] = None
    return jsonify({"ok": True})

@app.route("/status")
def status():
    with ENGINE["rooms_lock"]:
        rooms = list(ENGINE["rooms"])
    return jsonify({
        "connected": ENGINE["connected"],
        "rooms": rooms,
        "plugins": list(ENGINE["plugins"].keys()),
        "games": list(ENGINE["games"].keys())
    })

@app.route("/get_logs")
def get_logs():
    logs_list = []
    while not ENGINE["logs"].empty():
        try:
            logs_list.append(ENGINE["logs"].get_nowait())
        except queue.Empty:
            break
    return jsonify({"logs": logs_list})

@app.route("/")
def health():
    return "OK"

# =========================================================
# BOOT
# =========================================================
load("plugins", ENGINE["plugins"])
load("games", ENGINE["games"])

# =========================================================
# DEPLOYMENT READY
# =========================================================
# Expose `app` for WSGI (Gunicorn, Uvicorn, etc.)
# Example deployment: `gunicorn -w 4 -b 0.0.0.0:$PORT main:app`
