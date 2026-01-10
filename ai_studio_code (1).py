--- START OF FILE app.py ---

import os
import json
import time
import threading
import io
import random
import uuid
import math
import ssl
import sqlite3
import logging
import functools
import collections
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union

import requests
try:
    import psycopg2
except ImportError:
    psycopg2 = None
    
import websocket
from flask import Flask, render_template_string, request, jsonify, send_file, Response, abort
from PIL import Image, ImageDraw, ImageFont

# =============================================================================
# 1. CONFIGURATION & LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("TitanBot")

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", os.urandom(24))
    ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "change_me_in_production") 
    DATABASE_URL = os.environ.get("DATABASE_URL")
    
    # Game Settings
    DB_FILE = "howdies_v17_final.db"
    TABLE_NAME = "howdies_gamers_v17"
    MAX_CHAT_HISTORY = 200
    MAX_DEBUG_LOGS = 500
    MAX_ACTIVE_GAMES = 500
    GAME_TIMEOUT_SECONDS = 45
    
    # Cooldowns (Seconds)
    COOLDOWN_FLIP = 3.0
    COOLDOWN_GAME_MOVE = 0.5
    COOLDOWN_GLOBAL = 1.0
    
    # API & Endpoints
    LOGIN_URL = "https://api.howdies.app/api/login"
    UPLOAD_URL = "https://api.howdies.app/api/upload"
    WS_URL = "wss://app.howdies.app/howdies"
    
    # Assets
    HEADS_URL = "https://www.dropbox.com/scl/fi/sig75nm1i98d8z4jx2yw8/file_0000000026b471fda1f5631420800dd3.png?rlkey=36ov7cpwd90kejav4a7atkhh3&st=tf3jt0np&dl=1"
    TAILS_URL = "https://www.dropbox.com/scl/fi/0s35obflw2dl9r7zulaug/file_0000000085c871fd9a6e9c9b93f39cd9.png?rlkey=g5dx0anpmnjk0h6ysz4d6osqa&st=awly0km3&dl=1"

app = Flask(__name__)
app.secret_key = Config.SECRET_KEY

# =============================================================================
# 2. STATE, THREAD SAFETY & COOLDOWNS
# =============================================================================

class CooldownManager:
    def __init__(self):
        self._cooldowns = {}
        self._lock = threading.Lock()

    def check_and_update(self, user, command_type, duration):
        now = time.time()
        key = f"{user}_{command_type}"
        with self._lock:
            last = self._cooldowns.get(key, 0)
            if now - last < duration:
                return False
            self._cooldowns[key] = now
            return True

    def cleanup(self):
        now = time.time()
        with self._lock:
            # Remove entries older than 60 seconds
            keys_to_del = [k for k, v in self._cooldowns.items() if now - v > 60]
            for k in keys_to_del:
                del self._cooldowns[k]

cooldown_mgr = CooldownManager()
rate_limiter = None # Replaced by class logic below

class RateLimiter:
    def __init__(self):
        self._attempts = {}
        self._lock = threading.Lock()

    def is_allowed(self, ip_addr):
        now = time.time()
        with self._lock:
            self._attempts = {k: v for k, v in self._attempts.items() if now - v['last'] < 300}
            if ip_addr not in self._attempts: self._attempts[ip_addr] = {'count': 0, 'last': now}
            entry = self._attempts[ip_addr]
            if now - entry['last'] > 60:
                entry['count'] = 0
                entry['last'] = now
            if entry['count'] >= 10: return False
            entry['count'] += 1
            entry['last'] = now
            return True

rate_limiter = RateLimiter()

class ThreadSafeList:
    def __init__(self, max_size):
        self._list = collections.deque(maxlen=max_size)
        self._lock = threading.RLock()
    def append(self, item):
        with self._lock: self._list.append(item)
    def get_all(self):
        with self._lock: return list(self._list)
    def clear(self):
        with self._lock: self._list.clear()

DB_LOCK = threading.RLock()
GAME_LOCK = threading.RLock()

CHAT_HISTORY = ThreadSafeList(Config.MAX_CHAT_HISTORY)
DEBUG_LOGS = ThreadSafeList(Config.MAX_DEBUG_LOGS)

BOT_STATE = {
    "ws": None,
    "status": "DISCONNECTED",
    "user": "",
    "pass": "",
    "token": "",
    "user_id": None,
    "target_rooms": [], 
    "active_rooms": {}, 
    "domain": "",
    "should_run": False,
    "avatars": {},
    "last_ping_ts": 0,
    "state_lock": threading.RLock()
}

ACTIVE_GAMES = {}
ASSETS = {}

def sanitize_payload(payload):
    if isinstance(payload, str):
        try: payload = json.loads(payload)
        except: return payload
    if isinstance(payload, dict):
        clean = payload.copy()
        for k in clean:
            if k.lower() in ['password', 'token', 'pass']: clean[k] = "***"
        return clean
    return payload

def log_debug(direction, payload):
    try:
        safe_data = sanitize_payload(payload)
        if isinstance(safe_data, dict): safe_data = json.dumps(safe_data)
        DEBUG_LOGS.append({"time": time.strftime("%H:%M:%S"), "dir": direction, "data": safe_data})
    except: pass

# =============================================================================
# 3. DATABASE MANAGER
# =============================================================================

class DatabaseManager:
    @staticmethod
    def get_connection():
        if Config.DATABASE_URL and psycopg2:
            return psycopg2.connect(Config.DATABASE_URL, sslmode='require')
        else:
            conn = sqlite3.connect(Config.DB_FILE, timeout=20.0) 
            conn.execute("PRAGMA journal_mode=WAL;")
            return conn

    @staticmethod
    def init_db():
        with DB_LOCK:
            conn = None
            try:
                conn = DatabaseManager.get_connection()
                c = conn.cursor()
                c.execute(f'''CREATE TABLE IF NOT EXISTS {Config.TABLE_NAME} 
                           (username VARCHAR(255) PRIMARY KEY, wins INTEGER, score INTEGER, avatar_url TEXT)''')
                c.execute(f"CREATE INDEX IF NOT EXISTS idx_score ON {Config.TABLE_NAME} (score DESC)")
                conn.commit()
            except Exception as e: logger.critical(f"DB Init Failed: {e}")
            finally: 
                if conn: conn.close()

    @staticmethod
    def update_score(username, points, avatar_url=""):
        with DB_LOCK:
            conn = None
            try:
                conn = DatabaseManager.get_connection()
                c = conn.cursor()
                ph = "%s" if (Config.DATABASE_URL and psycopg2) else "?"
                c.execute(f"SELECT score, wins FROM {Config.TABLE_NAME} WHERE username={ph}", (username,))
                data = c.fetchone()

                if data:
                    new_score = data[0] + points
                    new_wins = data[1] + (1 if points > 0 else 0)
                    if avatar_url:
                        c.execute(f"UPDATE {Config.TABLE_NAME} SET score={ph}, wins={ph}, avatar_url={ph} WHERE username={ph}", (new_score, new_wins, avatar_url, username))
                    else:
                        c.execute(f"UPDATE {Config.TABLE_NAME} SET score={ph}, wins={ph} WHERE username={ph}", (new_score, new_wins, username))
                else:
                    new_score = 1000 + points
                    new_wins = 1 if points > 0 else 0
                    c.execute(f"INSERT INTO {Config.TABLE_NAME} (username, score, wins, avatar_url) VALUES ({ph}, {ph}, {ph}, {ph})", (username, new_score, new_wins, avatar_url))
                conn.commit()
                return new_score
            except Exception as e:
                logger.error(f"DB Update Error for {username}: {e}")
                return 0
            finally: 
                if conn: conn.close()

    @staticmethod
    def get_score(username):
        with DB_LOCK:
            conn = None
            try:
                conn = DatabaseManager.get_connection()
                c = conn.cursor()
                ph = "%s" if (Config.DATABASE_URL and psycopg2) else "?"
                c.execute(f"SELECT score FROM {Config.TABLE_NAME} WHERE username={ph}", (username,))
                data = c.fetchone()
                return data[0] if data else 1000
            except: return 1000
            finally: 
                if conn: conn.close()

    @staticmethod
    def get_leaderboard(limit=50):
        conn = None
        try:
            conn = DatabaseManager.get_connection()
            c = conn.cursor()
            c.execute(f"SELECT username, score, wins, avatar_url FROM {Config.TABLE_NAME} ORDER BY score DESC LIMIT {int(limit)}")
            return c.fetchall()
        except: return []
        finally: 
            if conn: conn.close()

DatabaseManager.init_db()

# =============================================================================
# 4. ASSETS
# =============================================================================

def create_number_asset(number):
    """Generates a large, cyan, semi-transparent number tile."""
    img = Image.new('RGBA', (300, 300), (0,0,0,0))
    d = ImageDraw.Draw(img)
    
    # Attempt to load a nice system font, fallback to scaling default
    font = None
    font_paths = [
        "arial.ttf", "Arial.ttf", 
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "C:\\Windows\\Fonts\\arial.ttf"
    ]
    
    for path in font_paths:
        try:
            font = ImageFont.truetype(path, 180) # Large size
            break
        except: continue
        
    if not font:
        # Fallback: Draw small and scale up (Pixelated but functional)
        try:
            temp = Image.new('RGBA', (50, 50), (0,0,0,0))
            dt = ImageDraw.Draw(temp)
            font_def = ImageFont.load_default()
            dt.text((15, 10), str(number), fill=(0, 255, 255, 140), font=font_def)
            img = temp.resize((300, 300), resample=Image.NEAREST)
            return img
        except: pass

    # Center text
    try:
        if font:
            text = str(number)
            bbox = d.textbbox((0,0), text, font=font)
            w, h = bbox[2]-bbox[0], bbox[3]-bbox[1]
            x, y = (300 - w) / 2, (300 - h) / 2 - 20
            d.text((x, y), text, fill=(0, 255, 255, 140), font=font) # Cyan semi-transparent
    except Exception as e:
        logger.error(f"Font Render Error: {e}")
        
    return img

def load_image_from_url(url, fallback_text):
    try:
        response = requests.get(url, stream=True, timeout=10)
        img = Image.open(io.BytesIO(response.content)).convert("RGBA")
        return img.resize((300, 300))
    except:
        img = Image.new('RGBA', (300, 300), (0,0,0,0))
        d = ImageDraw.Draw(img)
        d.ellipse([10, 10, 290, 290], outline="white", width=5)
        d.text((130, 130), fallback_text, fill="white")
        return img

def init_assets():
    if ASSETS.get('loaded'): return
    try:
        board = Image.new('RGB', (900, 900), (10, 12, 20))
        draw = ImageDraw.Draw(board)
        cyan, dark = (0, 255, 255), (0, 80, 80)
        # Draw Grid
        for x in [300, 600]:
            draw.line([(x, 20), (x, 880)], fill=dark, width=25) 
            draw.line([(x, 20), (x, 880)], fill=cyan, width=8)
        for y in [300, 600]:
            draw.line([(20, y), (880, y)], fill=dark, width=25)
            draw.line([(20, y), (880, y)], fill=cyan, width=8)
        draw.rectangle([5, 5, 895, 895], outline=(255,0,255), width=12)
        ASSETS['board'] = board

        x_img = Image.new('RGBA', (300, 300), (0,0,0,0))
        dx = ImageDraw.Draw(x_img)
        dx.line([(60,60), (240,240)], fill=(255, 0, 80), width=45)
        dx.line([(240,60), (60,240)], fill=(255, 0, 80), width=45)
        ASSETS['x'] = x_img

        o_img = Image.new('RGBA', (300, 300), (0,0,0,0))
        do = ImageDraw.Draw(o_img)
        do.ellipse([60,60,240,240], outline=(0, 255, 100), width=45)
        ASSETS['o'] = o_img

        ASSETS['heads'] = load_image_from_url(Config.HEADS_URL, "H")
        ASSETS['tails'] = load_image_from_url(Config.TAILS_URL, "T")
        
        # Generate numbers 1-9
        for i in range(1, 10): ASSETS[str(i)] = create_number_asset(i)
        
        ASSETS['loaded'] = True
        logger.info("Assets initialized.")
    except Exception as e: logger.error(f"Asset Init Failed: {e}")

# =============================================================================
# 5. BOT NETWORK CORE
# =============================================================================

def perform_login(username, password):
    try:
        payload = {"username": username, "password": password}
        response = requests.post(Config.LOGIN_URL, json=payload, timeout=15)
        if response.status_code == 200:
            data = response.json()
            token = data.get("token") or data.get("data", {}).get("token")
            uid = data.get("id") or data.get("userId") or data.get("data", {}).get("id")
            if token and uid:
                with BOT_STATE["state_lock"]: BOT_STATE["user_id"] = uid
                return token
        return None
    except: return None

def upload_image_to_howdies(image_bytes, is_gif=False):
    with BOT_STATE["state_lock"]:
        token = BOT_STATE["token"]
        uid = BOT_STATE["user_id"]
    if not token or not uid: return None

    try:
        filename = f"{uuid.uuid4()}.{'gif' if is_gif else 'png'}"
        mime = 'image/gif' if is_gif else 'image/png'
        files = {'file': (filename, image_bytes, mime)}
        data = {'UserID': uid, 'token': token, 'uploadType': 'image'}
        resp = requests.post(Config.UPLOAD_URL, data=data, files=files, timeout=20)
        if resp.status_code == 200:
            return resp.json().get("url") or resp.json().get("data")
    except: pass
    return None

def send_msg(room_id, text, type="text", url=""):
    with BOT_STATE["state_lock"]: ws = BOT_STATE["ws"]
    if not room_id: return
    
    log_rid = str(room_id)

    if ws and ws.sock and ws.sock.connected:
        pkt = {
            "handler": "chatroommessage", 
            "id": str(time.time()), 
            "type": type, 
            "roomid": room_id, 
            "text": text, 
            "url": url, 
            "length": "0"
        }
        try:
            ws.send(json.dumps(pkt))
            bot_av = "https://cdn-icons-png.flaticon.com/512/4712/4712035.png"
            display = f"[{log_rid[:5]}] [IMG]" if url else f"[{log_rid[:5]}] {text}"
            CHAT_HISTORY.append({"user": "TitanBot", "msg": display, "avatar": bot_av, "time": time.strftime("%H:%M"), "type": "bot"})
            log_debug("OUT", pkt)
        except Exception as e: logger.error(f"Send Error: {e}")

def join_room(ws, room_name):
    pkt = {"handler": "joinchatroom", "id": str(time.time()), "name": room_name, "roomPassword": ""}
    ws.send(json.dumps(pkt))

def leave_room(ws, room_id):
    pkt = {"handler": "leavechatroom", "id": str(time.time()), "roomid": room_id}
    ws.send(json.dumps(pkt))

def on_open(ws):
    with BOT_STATE["state_lock"]:
        BOT_STATE["status"] = "AUTHENTICATING"
        user, pwd = BOT_STATE["user"], BOT_STATE["pass"]
        target_rooms = BOT_STATE["target_rooms"]

    ws.send(json.dumps({"handler": "login", "username": user, "password": pwd}))
    time.sleep(1.0)
    for r_name in target_rooms: join_room(ws, r_name.strip())
    
    with BOT_STATE["state_lock"]: BOT_STATE["status"] = "ONLINE"

def on_message(ws, message):
    try: data = json.loads(message)
    except: return

    handler = data.get("handler")
    
    if handler == "joinchatroom" and data.get("roomid") and data.get("name"):
        r_name = data["name"]
        r_id = data.get("roomid") 
        with BOT_STATE["state_lock"]:
            BOT_STATE["active_rooms"][r_name] = r_id
            if r_name not in BOT_STATE["target_rooms"]:
                BOT_STATE["target_rooms"].append(r_name)
        log_debug("SYSTEM", f"Joined Room: {r_name} ({r_id})")
        
    if data.get("avatar_url") and data.get("username"):
        with BOT_STATE["state_lock"]:
            BOT_STATE["avatars"][data["username"]] = data["avatar_url"]
            
    if handler not in ["receipt_ack", "ping", "pong"]: log_debug("IN", data)
        
    if handler in ["chatroommessage", "message"]:
        msg_body = data.get("text") or data.get("body")
        sender = data.get("from") or data.get("username")
        room_id = data.get("roomid") 
        
        if msg_body and sender and room_id is not None:
            with BOT_STATE["state_lock"]:
                av = BOT_STATE["avatars"].get(sender, "https://cdn-icons-png.flaticon.com/512/149/149071.png")
                my_user = BOT_STATE["user"]
            
            log_rid = str(room_id)
            CHAT_HISTORY.append({"user": f"{sender}", "msg": f"[{log_rid[:5]}] {msg_body}", "avatar": av, "time": time.strftime("%H:%M"), "type": "text"})
            
            if sender != my_user:
                process_command(sender, msg_body, room_id)

def on_error(ws, error): log_debug("WS ERROR", str(error))

def on_close(ws, c, m):
    with BOT_STATE["state_lock"]:
        BOT_STATE["status"] = "DISCONNECTED"
        BOT_STATE["active_rooms"].clear()
        BOT_STATE["token"] = ""
    
    # Cleanup any hanging games so they don't zombie on reconnect
    with GAME_LOCK:
        ACTIVE_GAMES.clear()

def bot_thread_target():
    init_assets()
    while True:
        try:
            with BOT_STATE["state_lock"]:
                if not BOT_STATE["should_run"]: break
                user, pwd = BOT_STATE["user"], BOT_STATE["pass"]
            
            token = perform_login(user, pwd)
            if not token:
                with BOT_STATE["state_lock"]: BOT_STATE["status"] = "AUTH FAILED"
                time.sleep(15) 
                continue
                
            with BOT_STATE["state_lock"]:
                BOT_STATE["token"] = token
                BOT_STATE["status"] = "CONNECTING WS"
                
            ws = websocket.WebSocketApp(
                f"{Config.WS_URL}?token={token}", 
                on_open=on_open, on_message=on_message, 
                on_error=on_error, on_close=on_close
            )
            
            with BOT_STATE["state_lock"]: BOT_STATE["ws"] = ws
            
            # Use cert_none for broader compatibility
            ws.run_forever(ping_interval=20, ping_timeout=10, sslopt={"cert_reqs": ssl.CERT_NONE})
            
            with BOT_STATE["state_lock"]:
                if BOT_STATE["should_run"]: BOT_STATE["status"] = "RETRYING..."
                else: break
            time.sleep(5)
        except Exception as e:
            logger.error(f"Loop Error: {e}")
            with BOT_STATE["state_lock"]: BOT_STATE["status"] = "CRASH_RECOVER"
            time.sleep(5)

# =============================================================================
# 6. GAME LOGIC
# =============================================================================

def cleanup_idle_games():
    while True:
        time.sleep(5)
        try:
            with BOT_STATE["state_lock"]:
                if not BOT_STATE["should_run"]: continue
            
            cooldown_mgr.cleanup() # Clean cooldown memory
            
            now = time.time()
            to_remove = []
            
            with GAME_LOCK:
                # Use keys() copy to avoid iteration size error
                for key, game in list(ACTIVE_GAMES.items()):
                    if now - game['last_active'] > Config.GAME_TIMEOUT_SECONDS:
                        to_remove.append(key)
                
                # Cap active games
                if len(ACTIVE_GAMES) > Config.MAX_ACTIVE_GAMES:
                    sorted_games = sorted(ACTIVE_GAMES.items(), key=lambda x: x[1]['last_active'])
                    excess = len(ACTIVE_GAMES) - Config.MAX_ACTIVE_GAMES
                    for i in range(excess):
                        if sorted_games[i][0] not in to_remove:
                            to_remove.append(sorted_games[i][0])

            for key in to_remove:
                game = None
                with GAME_LOCK:
                    if key in ACTIVE_GAMES: game = ACTIVE_GAMES.pop(key)
                if game and not game.get('ended'):
                    send_msg(game.get('room_id'), f"🛑 **TIMEOUT (45s)!** Game by {game.get('host')} ended.")
        except Exception as e:
            logger.error(f"Cleanup Error: {e}")

threading.Thread(target=cleanup_idle_games, daemon=True).start()

def get_game_key(room_id, user):
    return f"{str(room_id)}_{user}"

def process_command(user, msg, room_id):
    try:
        msg = msg.strip().lower()

        # Simple Global Command Rate Limit
        if not cooldown_mgr.check_and_update(user, "cmd", Config.COOLDOWN_GLOBAL):
            return

        if msg.startswith("!j "):
            target = msg[3:].strip()
            with BOT_STATE["state_lock"]: ws = BOT_STATE["ws"]
            if ws and target: join_room(ws, target)
            return

        if msg == "!leave":
            with BOT_STATE["state_lock"]: ws = BOT_STATE["ws"]
            if ws:
                leave_room(ws, room_id)
                rid_str = str(room_id)
                r_name = next((k for k,v in BOT_STATE["active_rooms"].items() if str(v) == rid_str), None)
                if r_name and r_name in BOT_STATE["target_rooms"]:
                     BOT_STATE["target_rooms"].remove(r_name)
            return

        if msg == "!help":
            send_msg(room_id, "🎮 **COMMANDS:**\n• `!tic 1` (Start)\n• `!flip`\n• `!score`\n• `!j <room>`/`!leave`")
            return

        if msg == "!score":
            bal = DatabaseManager.get_score(user)
            send_msg(room_id, f"💳 {user}: **{bal}** pts")
            return

        if msg == "!reset":
            key = get_game_key(room_id, user)
            with GAME_LOCK:
                if key in ACTIVE_GAMES:
                    ACTIVE_GAMES.pop(key)
                    send_msg(room_id, f"♻ Game reset for {user}.")
                else: send_msg(room_id, f"⚠ No active game.")
            return

        if msg.startswith("!flip"):
            if not cooldown_mgr.check_and_update(user, "flip", Config.COOLDOWN_FLIP):
                return
            handle_flip(user, msg, room_id)
            return

        if msg == "!tic 1":
            if not cooldown_mgr.check_and_update(user, "tic", Config.COOLDOWN_FLIP):
                return
            handle_tic_start(user, room_id)
            return

        if msg.startswith("!join"):
            handle_ttt_join(user, msg, room_id)
            return

        if msg.isdigit():
            # Very short cooldown for gameplay moves to feel responsive but prevents macro spam
            if not cooldown_mgr.check_and_update(user, "move", Config.COOLDOWN_GAME_MOVE):
                return
            handle_numeric_input(user, msg, room_id)

    except Exception as e: logger.error(f"Cmd Error: {e}")

def handle_tic_start(user, room_id):
    key = get_game_key(room_id, user)
    rid_str = str(room_id)
    
    with GAME_LOCK:
        for k, v in ACTIVE_GAMES.items():
            if str(v['room_id']) == rid_str and (v['p1'] == user or v['p2'] == user):
                send_msg(room_id, f"⚠ {user}, finish current game first.")
                return

        ACTIVE_GAMES[key] = {
            "host": user, "room_id": room_id, "phase": "SETUP_MODE", 
            "mode": None, "bet": 0, "board": [" "]*9, "turn": "X",
            "p1": user, "p2": None, "last_active": time.time(), "ended": False
        }
    send_msg(room_id, f"@{user} **Choose mode:**\n1) vs Bot\n2) vs Player\nReply `1` or `2`")

def handle_numeric_input(user, msg, room_id):
    key = get_game_key(room_id, user)
    rid_str = str(room_id)
    
    with GAME_LOCK:
        # Check if user is host setup
        if key in ACTIVE_GAMES:
            game = ACTIVE_GAMES[key]
            if game["phase"].startswith("SETUP_"):
                handle_setup_input(user, msg, game)
                return

        # Check if user is player in active game
        target_game = None
        for k, v in ACTIVE_GAMES.items():
            if str(v['room_id']) == rid_str and (v['p1'] == user or v['p2'] == user):
                target_game = v
                break
        
        if target_game and target_game["phase"] == "PLAYING" and not target_game.get("ended"):
             handle_ttt_move(user, int(msg), target_game)

def handle_setup_input(user, text, game):
    phase = game["phase"]
    rid = game["room_id"]
    game["last_active"] = time.time()

    if phase == "SETUP_MODE":
        if text == "1":
            game["mode"] = "bot"
            game["phase"] = "SETUP_BET_TYPE"
            send_msg(rid, f"@{user} **Bet?**\n1) Yes\n2) No")
        elif text == "2":
            game["mode"] = "pvp"
            game["phase"] = "SETUP_BET_TYPE"
            send_msg(rid, f"@{user} **Bet?**\n1) Yes\n2) No")
        else: send_msg(rid, "Reply `1` or `2`.")

    elif phase == "SETUP_BET_TYPE":
        if text == "1":
            game["phase"] = "SETUP_BET_AMOUNT"
            send_msg(rid, f"@{user} Enter bet amount (Min 100):")
        elif text == "2":
            game["bet"] = 0
            finalize_setup(game)
        else: send_msg(rid, "Reply `1` or `2`.")

    elif phase == "SETUP_BET_AMOUNT":
        try:
            amt = int(text)
            balance = DatabaseManager.get_score(user)
            if amt < 100: return send_msg(rid, "Minimum bet is 100.")
            if amt > balance: return send_msg(rid, f"Insufficient funds. Max: {balance}")
            game["bet"] = amt
            finalize_setup(game)
        except: send_msg(rid, "Enter a number.")

def finalize_setup(game):
    rid = game["room_id"]
    user = game["host"]
    bet = game["bet"]
    
    if game["mode"] == "bot":
        game["p2"] = "🤖 TitanBot"
        game["phase"] = "PLAYING"
        send_msg(rid, f"🤖 **BOT MATCH** (Bet: {bet})\n{user} (X) vs Bot (O)")
        render_and_send_board(game)
    else:
        game["phase"] = "WAITING_P2"
        send_msg(rid, f"🎮 **PvP LOBBY** (Bet: {bet})\nHost: {user}\nWaiting: `!join {user}`")
        render_and_send_board(game)

def handle_ttt_join(user, msg, room_id):
    parts = msg.split()
    if len(parts) < 2: return send_msg(room_id, "Usage: `!join <host>`")

    host_target = parts[1]
    target_key = get_game_key(room_id, host_target)
    rid_str = str(room_id)
    
    with GAME_LOCK:
        if target_key not in ACTIVE_GAMES:
            for k, v in ACTIVE_GAMES.items():
                if str(v['room_id']) == rid_str and v['host'].lower() == host_target.lower():
                    target_key = k
                    break
        
        if target_key not in ACTIVE_GAMES: return send_msg(room_id, "Game not found.")
        game = ACTIVE_GAMES[target_key]
        if game["phase"] != "WAITING_P2": return send_msg(room_id, "Lobby not available.")
        if user == game['host']: return send_msg(room_id, "Cannot join own game.")
        if game.get("bet", 0) > 0 and DatabaseManager.get_score(user) < game["bet"]:
            return send_msg(room_id, "Insufficient funds.")
            
        game["p2"] = user
        game["phase"] = "PLAYING"
        game["last_active"] = time.time()
    
    send_msg(room_id, f"⚔ **MATCH STARTED!** {user} joined.")
    render_and_send_board(game)

def handle_ttt_move(user, move, game):
    if move < 1 or move > 9: return
    rid = game["room_id"]
    
    with GAME_LOCK:
        if game.get("ended"): return 

        game["last_active"] = time.time()
        curr_turn = game["turn"]
        curr_player = game["p1"] if curr_turn == "X" else game["p2"]
        
        if game["mode"] == "bot" and (user != game["p1"] or curr_turn == "O"): return
        if game["mode"] != "bot" and user != curr_player: return

        idx = move - 1
        if game["board"][idx] != " ": return send_msg(rid, "Taken!")
        game["board"][idx] = curr_turn

    if check_game_over(game, user): return

    with GAME_LOCK:
        key = get_game_key(rid, game['host'])
        if key in ACTIVE_GAMES:
            if game["mode"] == "bot":
                game["turn"] = "O"
                # Pass IDs to thread, not the object, to avoid race conditions
                threading.Timer(1.0, run_bot_move, args=[key, rid]).start()
            else:
                game["turn"] = "O" if game["turn"] == "X" else "X"
                render_and_send_board(game)

def run_bot_move(game_key, room_id):
    try:
        with GAME_LOCK:
            if game_key not in ACTIVE_GAMES: return
            game = ACTIVE_GAMES[game_key]
            if game.get("ended"): return

            b = game["board"]
            avail = [i for i,x in enumerate(b) if x == " "]
            if not avail: return
            
            move = None
            wins = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
            # Check for win or block
            for s in ["O", "X"]:
                for x,y,z in wins:
                    if b[x]==s and b[y]==s and b[z]==" ": move=z; break
                    if b[x]==s and b[z]==s and b[y]==" ": move=y; break
                    if b[y]==s and b[z]==s and b[x]==" ": move=x; break
                if move: break
            
            if not move: move = random.choice(avail)
            game["board"][move] = "O"

        if check_game_over(game, "TitanBot"): return
        
        with GAME_LOCK:
            if game_key in ACTIVE_GAMES:
                game["turn"] = "X"
                render_and_send_board(game)
    except Exception as e:
        logger.error(f"Bot Move Error: {e}")

def check_game_over(game, last_mover):
    b = game["board"]
    win_line = None
    wins = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
    for x,y,z in wins:
        if b[x]==b[y]==b[z] and b[x]!=" ": 
            win_line = f"{x},{y},{z}"; break
            
    rid = game['room_id']
    bet = game.get("bet", 0)
    key = get_game_key(rid, game['host'])

    if win_line:
        render_and_send_board(game, win_line)
        if bet > 0:
            winner = last_mover
            loser = "TitanBot" if winner == game["p1"] and game["mode"] == "bot" else (game["p2"] if winner == game["p1"] else game["p1"])
            if "Bot" not in winner: DatabaseManager.update_score(winner, bet * 2)
            if "Bot" not in loser: DatabaseManager.update_score(loser, -bet)
        send_msg(rid, f"🏆 **{last_mover} WINS!**" + (f" (+{bet*2})" if bet>0 else ""))
        with GAME_LOCK: 
            game["ended"] = True
            if key in ACTIVE_GAMES: del ACTIVE_GAMES[key]
        return True
    elif " " not in b:
        render_and_send_board(game)
        send_msg(rid, f"🤝 **DRAW!**")
        with GAME_LOCK: 
            game["ended"] = True
            if key in ACTIVE_GAMES: del ACTIVE_GAMES[key]
        return True
    return False

def render_and_send_board(game, line=""):
    try:
        init_assets()
        base = ASSETS['board'].copy()
        x_img, o_img = ASSETS['x'], ASSETS['o']
        for i, c in enumerate(game["board"]):
            if c == 'X': base.paste(x_img, ((i%3)*300, (i//3)*300), x_img)
            elif c == 'O': base.paste(o_img, ((i%3)*300, (i//3)*300), o_img)
            else:
                num = ASSETS.get(str(i+1))
                if num: base.paste(num, ((i%3)*300, (i//3)*300), num)
        if line:
            d = ImageDraw.Draw(base)
            idx = [int(k) for k in line.split(',')]
            s, e = idx[0], idx[2]
            d.line([((s%3)*300+150, (s//3)*300+150), ((e%3)*300+150, (e//3)*300+150)], fill="gold", width=30)
        img_io = io.BytesIO()
        base.save(img_io, 'PNG')
        url = upload_image_to_howdies(img_io.getvalue())
        if url: send_msg(game['room_id'], "", "image", url)
        else: send_msg(game['room_id'], "⚠ Render Failed")
    except: pass

def handle_flip(user, msg, room_id):
    parts = msg.split()
    guess = None
    if len(parts) > 1:
        if parts[1].upper() in ["H","HEAD","HEADS"]: guess = "HEADS"
        elif parts[1].upper() in ["T","TAIL","TAILS"]: guess = "TAILS"
    
    result = random.choice(["HEADS", "TAILS"])
    
    def process_flip_async():
        send_msg(room_id, f"@{user} tossed coin! 🌪️")
        
        frames = []
        base_h = ASSETS['heads'].resize((200, 200))
        base_t = ASSETS['tails'].resize((200, 200))
        W, H = 400, 500
        for i in range(15):
            frame = Image.new('RGBA', (W, H), (0,0,0,0))
            prog = i / 14
            y_pos = 400 - (4 * prog * (1 - prog) * 350)
            scale = abs(math.cos(i * 1.5))
            w = int(200 * scale) if int(200*scale) > 0 else 1
            coin = (base_h if i % 2 == 0 else base_t).resize((w, 200))
            frame.paste(coin, ((W - w)//2, int(y_pos)), coin)
            frames.append(frame)
        
        img_io = io.BytesIO()
        frames[0].save(img_io, format='GIF', save_all=True, append_images=frames[1:], duration=50, loop=0, disposal=2)
        url = upload_image_to_howdies(img_io.getvalue(), is_gif=True)
        if url: send_msg(room_id, "", "image", url)
        
        time.sleep(3.5)
        res_img = ASSETS['heads'] if result == "HEADS" else ASSETS['tails']
        res_io = io.BytesIO()
        res_img.save(res_io, 'PNG')
        r_url = upload_image_to_howdies(res_io.getvalue())
        if r_url: send_msg(room_id, "", "image", r_url)
        
        txt = f"Result: **{result}**"
        if guess:
            if guess == result:
                nb = DatabaseManager.update_score(user, 50)
                txt += f"\n🎉 WON! (+50) Bal: {nb}"
            else:
                nb = DatabaseManager.update_score(user, -20)
                txt += f"\n❌ LOST (-20) Bal: {nb}"
        send_msg(room_id, txt)
    
    threading.Thread(target=process_flip_async).start()

# =============================================================================
# 7. FLASK ROUTES
# =============================================================================

@app.route('/')
def index(): return render_template_string(UI_TEMPLATE)

@app.route('/leaderboard')
def leaderboard():
    users = DatabaseManager.get_leaderboard(50)
    return render_template_string(LEADERBOARD_TEMPLATE, users=users)

@app.route('/connect', methods=['POST'])
def connect():
    if not rate_limiter.is_allowed(request.remote_addr): return jsonify({"status": "Limit Reached"}), 429
    d = request.json
    if not d or not d.get('u') or not d.get('p') or not d.get('r'): return jsonify({"status": "Bad Req"}), 400
    with BOT_STATE["state_lock"]:
        if BOT_STATE["should_run"]: return jsonify({"status": "Running"})
        BOT_STATE.update({"user":d['u'], "pass":d['p'], "target_rooms":d['r'].split(','), "should_run":True, "domain":request.url_root, "status":"STARTING"})
    threading.Thread(target=bot_thread_target, daemon=True).start()
    return jsonify({"status": "Starting"})

@app.route('/disconnect', methods=['POST'])
def disconnect():
    with BOT_STATE["state_lock"]:
        BOT_STATE["should_run"] = False
        if BOT_STATE["ws"]: BOT_STATE["ws"].close()
    return jsonify({"status": "Stopped"})

@app.route('/clear_data', methods=['POST'])
def clear_data():
    CHAT_HISTORY.clear(); DEBUG_LOGS.clear()
    return jsonify({"status": "Cleared"})

@app.route('/get_data')
def get_data():
    with BOT_STATE["state_lock"]:
        return jsonify({"status": BOT_STATE["status"], "rooms": list(BOT_STATE["active_rooms"].keys()), "chat": CHAT_HISTORY.get_all(), "debug": DEBUG_LOGS.get_all()})

@app.route('/download_logs')
def download_logs():
    return Response("\n".join([f"[{x['time']}] {x['dir']}: {x['data']}" for x in DEBUG_LOGS.get_all()]), mimetype="text/plain", headers={"Content-Disposition": "attachment;filename=logs.txt"})

LEADERBOARD_TEMPLATE = """
<!DOCTYPE html><html><head><title>TITAN RANKINGS</title><meta name="viewport" content="width=device-width, initial-scale=1"><style>
body{background:#050505;color:#fff;font-family:monospace;margin:0;padding:20px}
.card{background:#111;border:1px solid #333;padding:15px;margin-bottom:12px;display:flex;align-items:center}
.score{font-size:20px;color:#00ff41;font-weight:bold;margin-left:auto}
</style></head><body><h1 style="color:#00f3ff;text-align:center">TITAN LEGENDS</h1>
{% for u in users %}<div class="card"><div>#{{loop.index}} {{u[0]}} ({{u[2]}} Wins)</div><div class="score">{{u[1]}}</div></div>{% endfor %}</body></html>
"""

UI_TEMPLATE = """
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>TITAN V17</title><style>
body{margin:0;background:#050505;color:#e0e6ed;font-family:monospace;height:100vh;display:flex;flex-direction:column}
#login-view{position:absolute;top:0;left:0;width:100%;height:100%;z-index:99;display:flex;justify-content:center;align-items:center;background:#000}
.login-card{width:300px;padding:20px;background:#111;border:1px solid #333;text-align:center}
input{width:90%;padding:10px;margin-bottom:10px;background:#000;border:1px solid #333;color:#fff}
button{padding:10px;background:#00f3ff;border:none;cursor:pointer;width:100%;font-weight:bold}
#app-view{display:none;height:100%;flex-direction:column;width:100%}
header{height:50px;background:#111;border-bottom:1px solid #333;display:flex;align-items:center;justify-content:space-between;padding:0 15px}
.content{flex:1;position:relative;overflow:hidden}
.tab-content{position:absolute;top:0;left:0;width:100%;height:100%;display:none;flex-direction:column}
.active-tab{display:flex}
#chat-container{flex:1;overflow-y:auto;padding:15px}
.msg-row{margin-bottom:10px}
.bubble{background:#1e1e1e;padding:8px;display:inline-block;border-radius:8px;max-width:80%}
.debug-logs{flex:1;overflow-y:auto;padding:10px;background:#000;font-size:10px}
nav{height:50px;background:#000;border-top:1px solid #333;display:flex}
.nav-btn{flex:1;background:transparent;border:none;color:#555;cursor:pointer;font-weight:bold}
.active{color:#00f3ff;background:#111}
iframe{width:100%;height:100%;border:none}
#room-status{font-size:10px;color:#aaa;margin-right:10px}
</style></head><body>
<div id="login-view"><div class="login-card"><h2 style="color:#00f3ff">TITAN V17</h2><input id="u" placeholder="Username"><input id="p" type="password" placeholder="Password"><input id="r" placeholder="Room1,Room2"><button onclick="login()">CONNECT</button></div></div>
<div id="app-view"><header><span>TITAN PANEL</span><div style="display:flex;align-items:center"><span id="room-status"></span><span id="status-badge" style="font-weight:bold;margin-right:15px">OFFLINE</span><button onclick="logout()" style="width:auto;background:red;color:#fff;border:none;padding:5px 10px">X</button></div></header>
<div class="content"><div id="tab-chat" class="tab-content active-tab"><div id="chat-container"></div></div><div id="tab-lb" class="tab-content"><iframe src="/leaderboard"></iframe></div><div id="tab-debug" class="tab-content"><div style="padding:5px;border-bottom:1px solid #333"><a href="/download_logs" style="color:#00f3ff">Logs</a><button onclick="clearData()" style="width:auto;padding:2px 5px;margin-left:10px">Clear</button></div><div id="debug-log-area" class="debug-logs"></div></div></div>
<nav><button onclick="switchTab('chat')" id="btn-chat" class="nav-btn active">CHAT</button><button onclick="switchTab('lb')" id="btn-lb" class="nav-btn">RANKS</button><button onclick="switchTab('debug')" id="btn-debug" class="nav-btn">DEBUG</button></nav></div>
<script>
function switchTab(t){document.querySelectorAll('.tab-content').forEach(e=>e.classList.remove('active-tab'));document.querySelectorAll('.nav-btn').forEach(e=>e.classList.remove('active'));document.getElementById('tab-'+t).classList.add('active-tab');document.getElementById('btn-'+t).classList.add('active');if(t==='lb')document.querySelector('iframe').src='/leaderboard'}
function login(){const u=document.getElementById('u').value,p=document.getElementById('p').value,r=document.getElementById('r').value;fetch('/connect',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({u,p,r})}).then(r=>{if(r.status===200){document.getElementById('login-view').style.display='none';document.getElementById('app-view').style.display='flex'}})}
function logout(){fetch('/disconnect',{method:'POST'});location.reload()}
function clearData(){fetch('/clear_data',{method:'POST'})}
setInterval(()=>{fetch('/get_data').then(r=>r.json()).then(d=>{const b=document.getElementById('status-badge');b.innerText=d.status;b.style.color=d.status==='ONLINE'?'#0f0':'#f00';if(d.rooms)document.getElementById('room-status').innerText="Rooms: "+d.rooms.join(", ");const c=document.getElementById('chat-container');c.innerHTML=d.chat.map(m=>`<div class="msg-row" style="text-align:${m.type==='bot'?'right':'left'}"><div class="bubble"><b>${m.user}:</b> ${m.msg}</div></div>`).join('');const dbg=document.getElementById('debug-log-area');dbg.innerHTML=d.debug.slice(-50).reverse().map(l=>`<div>[${l.dir}] ${typeof l.data==='object'?JSON.stringify(l.data):l.data}</div>`).join('')})},1500)
</script></body></html>
"""

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, threaded=True)