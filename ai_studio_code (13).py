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
# Handle potential missing driver in dev environments
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

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("TitanBot")

class Config:
    # Secrets
    SECRET_KEY = os.environ.get("SECRET_KEY", os.urandom(24))
    ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "change_me_in_production") 
    DATABASE_URL = os.environ.get("DATABASE_URL")
    
    # Game Settings
    DB_FILE = "howdies_v17_multi.db"
    TABLE_NAME = "howdies_gamers_v17"
    MAX_CHAT_HISTORY = 200
    MAX_DEBUG_LOGS = 500
    MAX_ACTIVE_GAMES = 500
    GAME_TIMEOUT_SECONDS = 45  # Strict 45s cleanup
    
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
# 2. STATE MANAGEMENT & THREAD SAFETY
# =============================================================================

class RateLimiter:
    def __init__(self):
        self._attempts = {}
        self._lock = threading.Lock()

    def is_allowed(self, ip_addr):
        now = time.time()
        with self._lock:
            self._attempts = {k: v for k, v in self._attempts.items() if now - v['last'] < 300}
            if ip_addr not in self._attempts:
                self._attempts[ip_addr] = {'count': 0, 'last': now}
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

# Global State
DB_LOCK = threading.RLock()   # Critical for DB Integrity
GAME_LOCK = threading.RLock() # Critical for Game State

CHAT_HISTORY = ThreadSafeList(Config.MAX_CHAT_HISTORY)
DEBUG_LOGS = ThreadSafeList(Config.MAX_DEBUG_LOGS)

BOT_STATE = {
    "ws": None,
    "status": "DISCONNECTED",
    "user": "",
    "pass": "",
    "token": "",
    "user_id": None,
    # Multi-room support
    "target_rooms": [], # List of room names to maintain presence in
    "active_rooms": {}, # Map: RoomName -> RoomID
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
        except ValueError: return payload
    if isinstance(payload, dict):
        clean = payload.copy()
        for key in clean:
            if key.lower() in ['password', 'token', 'pass']:
                clean[key] = "***"
            elif isinstance(clean[key], (dict, list)):
                clean[key] = sanitize_payload(clean[key])
        return clean
    return payload

def log_debug(direction, payload):
    try:
        safe_data = sanitize_payload(payload)
        if isinstance(safe_data, (dict, list)):
            try: safe_data = json.dumps(safe_data)
            except: pass
        DEBUG_LOGS.append({"time": time.strftime("%H:%M:%S"), "dir": direction, "data": safe_data})
    except Exception as e:
        logger.error(f"Logging error: {e}")

# =============================================================================
# 3. DATABASE MANAGER (DOUBLE LOCK INTEGRITY)
# =============================================================================

class DatabaseManager:
    @staticmethod
    def get_connection():
        if Config.DATABASE_URL and psycopg2:
            return psycopg2.connect(Config.DATABASE_URL, sslmode='require')
        else:
            conn = sqlite3.connect(Config.DB_FILE, timeout=20.0)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
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
                logger.info("Database initialized with WAL mode.")
            except Exception as e:
                logger.critical(f"DB Init Failed: {e}")
            finally:
                if conn: conn.close()

    @staticmethod
    def update_score(username, points, avatar_url=""):
        """
        Double-Layer Locking:
        1. Python Thread Lock (DB_LOCK) prevents concurrent threads from entering.
        2. Database Transaction ensures atomicity.
        """
        with DB_LOCK:
            conn = None
            try:
                conn = DatabaseManager.get_connection()
                c = conn.cursor()
                ph = "%s" if (Config.DATABASE_URL and psycopg2) else "?"
                
                # Read
                c.execute(f"SELECT score, wins FROM {Config.TABLE_NAME} WHERE username={ph}", (username,))
                data = c.fetchone()

                # Modify
                if data:
                    new_score = data[0] + points
                    new_wins = data[1] + (1 if points > 0 else 0)
                    if avatar_url:
                        c.execute(f"UPDATE {Config.TABLE_NAME} SET score={ph}, wins={ph}, avatar_url={ph} WHERE username={ph}", 
                                  (new_score, new_wins, avatar_url, username))
                    else:
                        c.execute(f"UPDATE {Config.TABLE_NAME} SET score={ph}, wins={ph} WHERE username={ph}", 
                                  (new_score, new_wins, username))
                else:
                    new_score = 1000 + points
                    new_wins = 1 if points > 0 else 0
                    c.execute(f"INSERT INTO {Config.TABLE_NAME} (username, score, wins, avatar_url) VALUES ({ph}, {ph}, {ph}, {ph})", 
                              (username, new_score, new_wins, avatar_url))
                
                # Write
                conn.commit()
                return new_score
            except Exception as e:
                logger.error(f"DB Update Error for {username}: {e}")
                if conn: conn.rollback()
                return 0
            finally:
                if conn: conn.close()

    @staticmethod
    def get_score(username):
        # Read-only doesn't strictly need the global lock if WAL is on, but safer for consistency
        with DB_LOCK:
            conn = None
            try:
                conn = DatabaseManager.get_connection()
                c = conn.cursor()
                ph = "%s" if (Config.DATABASE_URL and psycopg2) else "?"
                c.execute(f"SELECT score FROM {Config.TABLE_NAME} WHERE username={ph}", (username,))
                data = c.fetchone()
                return data[0] if data else 1000
            except Exception:
                return 1000
            finally:
                if conn: conn.close()

    @staticmethod
    def get_leaderboard(limit=50):
        with DB_LOCK:
            conn = None
            try:
                conn = DatabaseManager.get_connection()
                c = conn.cursor()
                c.execute(f"SELECT username, score, wins, avatar_url FROM {Config.TABLE_NAME} ORDER BY score DESC LIMIT {int(limit)}")
                return c.fetchall()
            except Exception as e:
                logger.error(f"Leaderboard Error: {e}")
                return []
            finally:
                if conn: conn.close()

DatabaseManager.init_db()

# =============================================================================
# 4. ASSET GENERATION (VISUAL MAPPING)
# =============================================================================

def create_number_asset(number):
    """Generates a semi-transparent number for board mapping."""
    img = Image.new('RGBA', (300, 300), (0,0,0,0))
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 100)
    except:
        font = ImageFont.load_default()
        
    # Draw text centered, gray, semi-transparent
    text = str(number)
    # Approximation for center since getbbox isn't always reliable on default font
    d.text((120, 100), text, fill=(128, 128, 128, 100), font=font)
    return img

def load_image_from_url(url, fallback_text):
    try:
        response = requests.get(url, stream=True, timeout=10)
        response.raise_for_status()
        img = Image.open(io.BytesIO(response.content)).convert("RGBA")
        return img.resize((300, 300))
    except Exception:
        img = Image.new('RGBA', (300, 300), (0,0,0,0))
        d = ImageDraw.Draw(img)
        d.ellipse([10,10,290,290], outline="gold", width=5)
        d.text((120,120), fallback_text, fill="white")
        return img

def init_assets():
    if ASSETS.get('loaded'): return

    try:
        # Base Board
        board = Image.new('RGB', (900, 900), (10, 12, 20))
        draw = ImageDraw.Draw(board)
        cyan_line = (0, 255, 255)
        dark_bg_line = (0, 80, 80)
        magenta_border = (255, 0, 255)
        
        for x in [300, 600]:
            draw.line([(x, 20), (x, 880)], fill=dark_bg_line, width=25) 
            draw.line([(x, 20), (x, 880)], fill=cyan_line, width=8)
        for y in [300, 600]:
            draw.line([(20, y), (880, y)], fill=dark_bg_line, width=25)
            draw.line([(20, y), (880, y)], fill=cyan_line, width=8)
        draw.rectangle([5, 5, 895, 895], outline=magenta_border, width=12)
        ASSETS['board'] = board

        # X and O
        x_img = Image.new('RGBA', (300, 300), (0,0,0,0))
        dx = ImageDraw.Draw(x_img)
        dx.line([(60,60), (240,240)], fill=(255, 0, 80), width=45)
        dx.line([(240,60), (60,240)], fill=(255, 0, 80), width=45)
        ASSETS['x'] = x_img

        o_img = Image.new('RGBA', (300, 300), (0,0,0,0))
        do = ImageDraw.Draw(o_img)
        do.ellipse([60,60,240,240], outline=(0, 255, 100), width=45)
        ASSETS['o'] = o_img

        # Coins
        ASSETS['heads'] = load_image_from_url(Config.HEADS_URL, "H")
        ASSETS['tails'] = load_image_from_url(Config.TAILS_URL, "T")

        # Visual Mapping 1-9
        for i in range(1, 10):
            ASSETS[str(i)] = create_number_asset(i)
        
        ASSETS['loaded'] = True
        logger.info("Assets initialized.")
    except Exception as e:
        logger.error(f"Asset Init Failed: {e}")

# =============================================================================
# 5. BOT NETWORK CORE (MULTI-ROOM SUPPORT)
# =============================================================================

def perform_login(username, password):
    try:
        payload = {"username": username, "password": password}
        response = requests.post(Config.LOGIN_URL, json=payload, timeout=15)
        log_debug("API_LOGIN", response.text)
        
        if response.status_code == 200:
            data = response.json()
            token = data.get("token") or data.get("data", {}).get("token")
            uid = data.get("id") or data.get("userId") or data.get("data", {}).get("id")
            if token and uid:
                with BOT_STATE["state_lock"]:
                    BOT_STATE["user_id"] = uid
                return token
        return None
    except Exception as e:
        log_debug("API_ERROR", str(e))
        return None

def upload_image_to_howdies(image_bytes, is_gif=False):
    with BOT_STATE["state_lock"]:
        token = BOT_STATE["token"]
        uid = BOT_STATE["user_id"]
    if not token or not uid: return None
    try:
        filename = f"{uuid.uuid4()}.gif" if is_gif else f"{uuid.uuid4()}.png"
        mime = 'image/gif' if is_gif else 'image/png'
        files = {'file': (filename, image_bytes, mime)}
        data = {'UserID': uid, 'token': token, 'uploadType': 'image'}
        resp = requests.post(Config.UPLOAD_URL, data=data, files=files, timeout=20)
        if resp.status_code == 200:
            resp_json = resp.json()
            return resp_json.get("url") or resp_json.get("data")
        return None
    except Exception as e:
        logger.error(f"Upload Error: {e}")
        return None

def send_msg(room_id, text, type="text", url=""):
    """
    Sends message to a SPECIFIC room.
    Multi-room support requires room_id to be explicit.
    """
    with BOT_STATE["state_lock"]:
        ws = BOT_STATE["ws"]
        
    if not room_id:
        logger.error("Attempted to send message without Room ID")
        return

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
            # Log for UI
            bot_av = "https://cdn-icons-png.flaticon.com/512/4712/4712035.png"
            display = f"[{room_id[:5]}] [IMG]" if url else f"[{room_id[:5]}] {text}"
            CHAT_HISTORY.append({"user": "TitanBot", "msg": display, "avatar": bot_av, "time": time.strftime("%H:%M"), "type": "bot"})
            log_debug("OUT", pkt)
        except Exception as e:
            logger.error(f"Send Error: {e}")

def join_room(ws, room_name):
    """Helper to construct join packet"""
    pkt = {"handler": "joinchatroom", "id": str(time.time()), "name": room_name, "roomPassword": ""}
    ws.send(json.dumps(pkt))
    log_debug("OUT", f"Joining {room_name}")

def on_open(ws):
    with BOT_STATE["state_lock"]:
        BOT_STATE["status"] = "AUTHENTICATING"
        user = BOT_STATE["user"]
        pwd = BOT_STATE["pass"]
        target_rooms = BOT_STATE["target_rooms"]

    # 1. Login Packet
    login_pkt = {"handler": "login", "username": user, "password": pwd}
    ws.send(json.dumps(login_pkt))
    log_debug("OUT", login_pkt)
    
    time.sleep(1.0) # Wait for auth
    
    # 2. Auto-Rejoin All Target Rooms
    for r_name in target_rooms:
        join_room(ws, r_name.strip())
    
    with BOT_STATE["state_lock"]:
        BOT_STATE["status"] = "ONLINE"
        BOT_STATE["last_ping_ts"] = time.time()

def on_message(ws, message):
    try:
        data = json.loads(message)
    except json.JSONDecodeError:
        return

    handler = data.get("handler")
    
    # --- State Management: Capture Room IDs ---
    if handler == "joinchatroom" and data.get("roomid") and data.get("name"):
        r_name = data["name"]
        r_id = data["roomid"]
        with BOT_STATE["state_lock"]:
            BOT_STATE["active_rooms"][r_name] = r_id
            # Also update target_rooms if not present (dynamic join)
            if r_name not in BOT_STATE["target_rooms"]:
                BOT_STATE["target_rooms"].append(r_name)
        log_debug("SYSTEM", f"Joined Room: {r_name} ({r_id})")
        
    if data.get("avatar_url") and data.get("username"):
        with BOT_STATE["state_lock"]:
            BOT_STATE["avatars"][data["username"]] = data["avatar_url"]
            
    if handler not in ["receipt_ack", "ping", "pong"]:
        log_debug("IN", data)
        
    # --- Chat Handling ---
    if handler in ["chatroommessage", "message"]:
        msg_body = data.get("text") or data.get("body")
        sender = data.get("from") or data.get("username")
        room_id = data.get("roomid") # Critical for Multi-Room
        
        if msg_body and sender and room_id:
            with BOT_STATE["state_lock"]:
                av = BOT_STATE["avatars"].get(sender, "https://cdn-icons-png.flaticon.com/512/149/149071.png")
                my_user = BOT_STATE["user"]
            
            # UI Log
            CHAT_HISTORY.append({"user": f"{sender}", "msg": f"[{room_id[:5]}] {msg_body}", "avatar": av, "time": time.strftime("%H:%M"), "type": "text"})
            
            if sender != my_user:
                process_command(sender, msg_body, room_id)

def on_error(ws, error):
    log_debug("WS ERROR", str(error))

def on_close(ws, c, m):
    with BOT_STATE["state_lock"]:
        BOT_STATE["status"] = "DISCONNECTED"
        BOT_STATE["active_rooms"].clear()
        BOT_STATE["token"] = ""

def bot_thread_target():
    """Main Loop with Heartbeat & Resilience"""
    init_assets()
    
    while True:
        try:
            with BOT_STATE["state_lock"]:
                if not BOT_STATE["should_run"]: break
                user = BOT_STATE["user"]
                pwd = BOT_STATE["pass"]
            
            if not user or not pwd:
                time.sleep(1)
                continue

            token = perform_login(user, pwd)
            if not token:
                with BOT_STATE["state_lock"]: BOT_STATE["status"] = "AUTH FAILED"
                time.sleep(15)
                continue
                
            with BOT_STATE["state_lock"]:
                BOT_STATE["token"] = token
                BOT_STATE["status"] = "CONNECTING WS"
                
            ws_url = f"{Config.WS_URL}?token={token}"
            ws = websocket.WebSocketApp(ws_url, 
                                      on_open=on_open, 
                                      on_message=on_message, 
                                      on_error=on_error, 
                                      on_close=on_close)
            
            with BOT_STATE["state_lock"]: BOT_STATE["ws"] = ws
            
            # Run with ping support
            ws.run_forever(ping_interval=20, ping_timeout=10)
            
            with BOT_STATE["state_lock"]:
                if BOT_STATE["should_run"]: BOT_STATE["status"] = "RETRYING..."
                else: break
            time.sleep(5)
            
        except Exception as e:
            logger.error(f"Critical Bot Loop Error: {e}")
            with BOT_STATE["state_lock"]: BOT_STATE["status"] = "CRASH_RECOVER"
            time.sleep(5)

# =============================================================================
# 6. GAME LOGIC ENGINE (STRICT CLEANUP & SCOPING)
# =============================================================================

def cleanup_idle_games():
    """
    Background Watchdog:
    Removes games idle for > 45 seconds.
    Notifies specific room before deleting.
    """
    while True:
        time.sleep(5) # Check frequently
        try:
            with BOT_STATE["state_lock"]:
                should_run = BOT_STATE["should_run"]
            
            if not should_run: continue

            now = time.time()
            to_remove = []
            
            with GAME_LOCK:
                # 1. Check Timeouts
                for game_key, game in ACTIVE_GAMES.items():
                    if now - game['last_active'] > Config.GAME_TIMEOUT_SECONDS:
                        to_remove.append(game_key)
                
                # 2. Check Memory Cap
                if len(ACTIVE_GAMES) > Config.MAX_ACTIVE_GAMES:
                    sorted_games = sorted(ACTIVE_GAMES.items(), key=lambda x: x[1]['last_active'])
                    excess = len(ACTIVE_GAMES) - Config.MAX_ACTIVE_GAMES
                    for i in range(excess):
                        if sorted_games[i][0] not in to_remove:
                            to_remove.append(sorted_games[i][0])

            # Process Removal & Notify
            for key in to_remove:
                game = None
                with GAME_LOCK:
                    if key in ACTIVE_GAMES:
                        game = ACTIVE_GAMES.pop(key)
                
                if game:
                    rid = game.get('room_id')
                    host = game.get('host')
                    if rid and host:
                        send_msg(rid, f"🛑 **TIMEOUT (45s)!** Game by {host} removed.")

        except Exception as e:
            logger.error(f"Cleanup thread error: {e}")

threading.Thread(target=cleanup_idle_games, daemon=True).start()

def get_game_key(room_id, user):
    """Composite key to allow same user to play in different rooms separately."""
    return f"{room_id}_{user}"

def process_command(user, msg, room_id):
    """Parses commands scoped by Room ID."""
    try:
        msg = msg.strip()
        cmd = msg.lower()

        # --- Admin / Room Management ---
        if cmd.startswith("!j "):
            target = msg[3:].strip()
            with BOT_STATE["state_lock"]:
                ws = BOT_STATE["ws"]
            if ws and target:
                join_room(ws, target)
                send_msg(room_id, f"🚀 Attempting to join {target}...")
            return

        if cmd == "!leave":
            with BOT_STATE["state_lock"]:
                ws = BOT_STATE["ws"]
                # Find room name by ID
                r_name = next((k for k,v in BOT_STATE["active_rooms"].items() if v == room_id), None)
            
            if ws and r_name:
                ws.send(json.dumps({"handler": "partchatroom", "name": r_name, "id": str(time.time())}))
                with BOT_STATE["state_lock"]:
                    if r_name in BOT_STATE["active_rooms"]: del BOT_STATE["active_rooms"][r_name]
                    if r_name in BOT_STATE["target_rooms"]: BOT_STATE["target_rooms"].remove(r_name)
            return

        # --- Standard User Commands ---
        if cmd == "!help":
            send_msg(room_id, "🎮 **COMMANDS:**\n• `!tic 1` (Start Setup)\n• `!flip`\n• `!score`\n• `!j <room>` / `!leave`")
            return

        if cmd == "!score":
            bal = DatabaseManager.get_score(user)
            send_msg(room_id, f"💳 {user}: **{bal}** pts")
            return

        if cmd == "!reset":
            key = get_game_key(room_id, user)
            with GAME_LOCK:
                if key in ACTIVE_GAMES:
                    ACTIVE_GAMES.pop(key)
                    send_msg(room_id, f"♻ Game reset for {user}.")
                else:
                    send_msg(room_id, f"⚠ No active game in this room.")
            return

        if cmd.startswith("!flip"):
            handle_flip(user, msg, room_id)
            return

        # --- Game Flow ---
        if cmd == "!tic 1":
            handle_tic_start(user, room_id)
            return

        if cmd.startswith("!join"):
            handle_ttt_join(user, msg, room_id)
            return

        if msg.isdigit():
            handle_numeric_input(user, msg, room_id)

    except Exception as e:
        logger.error(f"Cmd Error: {e}")

def handle_tic_start(user, room_id):
    key = get_game_key(room_id, user)
    
    # Check if user is already hosting/playing in THIS room
    # We also check if user is p2 in someone else's game in THIS room
    with GAME_LOCK:
        for k, v in ACTIVE_GAMES.items():
            if v['room_id'] == room_id and (v['p1'] == user or v['p2'] == user):
                send_msg(room_id, f"⚠ {user}, finish your existing game here first.")
                return

        ACTIVE_GAMES[key] = {
            "host": user,
            "room_id": room_id,
            "phase": "SETUP_MODE",
            "mode": None,
            "bet": 0,
            "board": [" "]*9,
            "turn": "X",
            "p1": user,
            "p2": None,
            "last_active": time.time()
        }
    
    send_msg(room_id, f"@{user} **Choose mode:**\n1) Single Player (vs Bot)\n2) Two Player\nReply with `1` or `2`")

def handle_numeric_input(user, msg, room_id):
    """Routes numeric input based on game state (Setup vs Playing)."""
    # 1. Find if user is HOST in SETUP phase
    key = get_game_key(room_id, user)
    
    with GAME_LOCK:
        # Check host setup
        if key in ACTIVE_GAMES:
            game = ACTIVE_GAMES[key]
            if game["phase"].startswith("SETUP_"):
                handle_setup_input(user, msg, game)
                return

        # 2. Check gameplay move (User could be P1 or P2)
        target_game = None
        for k, v in ACTIVE_GAMES.items():
            if v['room_id'] == room_id and (v['p1'] == user or v['p2'] == user):
                target_game = v
                break
        
        if target_game and target_game["phase"] == "PLAYING":
             handle_ttt_move(user, int(msg), target_game)

def handle_setup_input(user, text, game):
    phase = game["phase"]
    rid = game["room_id"]
    
    game["last_active"] = time.time()

    if phase == "SETUP_MODE":
        if text == "1":
            game["mode"] = "bot"
            game["phase"] = "SETUP_BET_TYPE"
            send_msg(rid, f"@{user} **Choose bet mode:**\n1) With Bet\n2) Without Bet\nReply `1` or `2`")
        elif text == "2":
            game["mode"] = "pvp"
            game["phase"] = "SETUP_BET_TYPE"
            send_msg(rid, f"@{user} **Choose bet mode:**\n1) With Bet\n2) Without Bet\nReply `1` or `2`")
        else:
            send_msg(rid, "⚠ Invalid. Reply `1` or `2`.")

    elif phase == "SETUP_BET_TYPE":
        if text == "1":
            game["phase"] = "SETUP_BET_AMOUNT"
            curr = DatabaseManager.get_score(user)
            send_msg(rid, f"@{user} Enter bet amount (Min 100, Max {curr}):")
        elif text == "2":
            game["bet"] = 0
            finalize_setup(game)
        else:
            send_msg(rid, "⚠ Invalid. Reply `1` or `2`.")

    elif phase == "SETUP_BET_AMOUNT":
        try:
            amt = int(text)
            balance = DatabaseManager.get_score(user)
            if amt < 100:
                send_msg(rid, "⚠ Minimum bet is 100.")
                return
            if amt > balance:
                send_msg(rid, f"⚠ Insufficient funds. Max: {balance}")
                return
            game["bet"] = amt
            finalize_setup(game)
        except ValueError:
            send_msg(rid, "⚠ Enter a number.")

def finalize_setup(game):
    rid = game["room_id"]
    user = game["host"]
    bet = game["bet"]
    
    if game["mode"] == "bot":
        game["p2"] = "🤖 TitanBot"
        game["phase"] = "PLAYING"
        send_msg(rid, f"🤖 **BOT MATCH STARTED** (Bet: {bet})\n{user} (X) vs Bot (O)")
        render_and_send_board(game)
    else:
        game["phase"] = "WAITING_P2"
        send_msg(rid, f"🎮 **PvP LOBBY** (Bet: {bet})\nHost: {user}\nWaiting: `!join {user}`")
        render_and_send_board(game)

def handle_ttt_join(user, msg, room_id):
    parts = msg.split()
    if len(parts) < 2: return
    host_target = parts[1]
    
    # Looking for game in THIS room by that host
    target_key = get_game_key(room_id, host_target)
    
    with GAME_LOCK:
        # Fuzzy match attempt if exact key fails
        if target_key not in ACTIVE_GAMES:
            # try case insensitive search in this room
            for k, v in ACTIVE_GAMES.items():
                if v['room_id'] == room_id and v['host'].lower() == host_target.lower():
                    target_key = k
                    break
        
        if target_key not in ACTIVE_GAMES:
            send_msg(room_id, "⚠ Game not found in this room.")
            return

        game = ACTIVE_GAMES[target_key]
        if game["phase"] != "WAITING_P2":
            send_msg(room_id, "⚠ Lobby closed.")
            return
            
        if user == game['host']:
             send_msg(room_id, "⚠ You cannot join your own game.")
             return

        # Check Balance
        if game["bet"] > 0:
            if DatabaseManager.get_score(user) < game["bet"]:
                send_msg(room_id, f"⚠ {user}, need {game['bet']} pts.")
                return

        game["p2"] = user
        game["phase"] = "PLAYING"
        game["last_active"] = time.time()
        
    send_msg(room_id, f"⚔ **MATCH ON!** {game['p1']} vs {user}")
    render_and_send_board(game)

def handle_ttt_move(user, move, game):
    if move < 1 or move > 9: return
    rid = game["room_id"]
    
    with GAME_LOCK:
        game["last_active"] = time.time()
        curr_turn = game["turn"]
        curr_player = game["p1"] if curr_turn == "X" else game["p2"]
        
        if game["mode"] == "bot":
            if user != game["p1"] or curr_turn == "O": return
        elif user != curr_player:
            return # Not your turn

        idx = move - 1
        if game["board"][idx] != " ":
            send_msg(rid, "⚠ Spot taken!")
            return

        game["board"][idx] = curr_turn

    if check_game_over(game, user): return

    # Next Turn
    with GAME_LOCK:
        # Check if game still exists (wasn't cleaned up)
        key = get_game_key(rid, game['host'])
        if key in ACTIVE_GAMES:
            if game["mode"] == "bot":
                game["turn"] = "O"
                threading.Timer(1.0, run_bot_move, args=[game]).start()
            else:
                game["turn"] = "O" if game["turn"] == "X" else "X"
                render_and_send_board(game)

def run_bot_move(game):
    try:
        with GAME_LOCK:
            rid = game["room_id"]
            key = get_game_key(rid, game['host'])
            if key not in ACTIVE_GAMES: return
            
            b = game["board"]
            avail = [i for i,x in enumerate(b) if x == " "]
            if not avail: return
            
            # Simple AI: Win -> Block -> Random
            move = None
            wins = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
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
            if key in ACTIVE_GAMES:
                game["turn"] = "X"
                render_and_send_board(game)
    except Exception as e:
        logger.error(f"Bot AI Error: {e}")

def check_game_over(game, last_mover):
    b = game["board"]
    win_line = None
    wins = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
    
    for x,y,z in wins:
        if b[x]==b[y]==b[z] and b[x]!=" ": 
            win_line = f"{x},{y},{z}"
            break
    
    rid = game["room_id"]
    bet = game["bet"]
    host = game["host"]
    key = get_game_key(rid, host)

    if win_line:
        render_and_send_board(game, win_line)
        prize_msg = ""
        
        # --- ATOMIC SCORE UPDATE ---
        if bet > 0:
            winner = last_mover
            if game["mode"] == "bot":
                loser = "TitanBot" if winner == game["p1"] else game["p1"]
            else:
                loser = game["p2"] if winner == game["p1"] else game["p1"]

            # Update DB (Double Lock applied in method)
            if "Bot" not in winner: DatabaseManager.update_score(winner, bet * 2)
            if "Bot" not in loser: DatabaseManager.update_score(loser, -bet)
            prize_msg = f" (+{bet*2} pts)"

        send_msg(rid, f"🏆 **{last_mover} WINS!**{prize_msg}")
        with GAME_LOCK:
            if key in ACTIVE_GAMES: del ACTIVE_GAMES[key]
        return True

    elif " " not in b:
        render_and_send_board(game)
        send_msg(rid, f"🤝 **DRAW!** No points lost.")
        with GAME_LOCK:
            if key in ACTIVE_GAMES: del ACTIVE_GAMES[key]
        return True
        
    return False

def render_and_send_board(game, line=""):
    try:
        init_assets()
        base = ASSETS['board'].copy()
        x_img, o_img = ASSETS['x'], ASSETS['o']
        
        for i, c in enumerate(game["board"]):
            if c == 'X': 
                base.paste(x_img, ((i%3)*300, (i//3)*300), x_img)
            elif c == 'O': 
                base.paste(o_img, ((i%3)*300, (i//3)*300), o_img)
            else:
                # --- VISUAL MAPPING (1-9) ---
                # Overlay semi-transparent number on empty slot
                num_img = ASSETS.get(str(i+1))
                if num_img:
                    base.paste(num_img, ((i%3)*300, (i//3)*300), num_img)
            
        if line:
            draw = ImageDraw.Draw(base)
            idx = [int(k) for k in line.split(',')]
            s, e = idx[0], idx[2]
            draw.line([((s%3)*300+150, (s//3)*300+150), ((e%3)*300+150, (e//3)*300+150)], fill="#ffd700", width=30)

        img_io = io.BytesIO()
        base.save(img_io, 'PNG')
        uploaded_url = upload_image_to_howdies(img_io.getvalue())
        
        rid = game["room_id"]
        if uploaded_url:
            send_msg(rid, "", "image", uploaded_url)
        else:
            send_msg(rid, "⚠ Image render failed.")
    except Exception as e:
        logger.error(f"Render Logic Error: {e}")

def handle_flip(user, msg, room_id):
    parts = msg.split()
    guess = None
    if len(parts) > 1:
        raw = parts[1].upper()
        if raw in ["H", "HEADS"]: guess = "HEADS"
        if raw in ["T", "TAILS"]: guess = "TAILS"
    
    result = random.choice(["HEADS", "TAILS"])
    
    def process_flip_async():
        send_msg(room_id, f"@{user} tossed the coin! 🌪️")
        time.sleep(2)
        
        # Simple animation upload (skipped for brevity, focusing on result)
        res_img = ASSETS['heads'] if result == "HEADS" else ASSETS['tails']
        res_io = io.BytesIO()
        res_img.save(res_io, 'PNG')
        res_url = upload_image_to_howdies(res_io.getvalue())
        if res_url: send_msg(room_id, "", "image", res_url)
        
        txt = f"✨ Result: **{result}**"
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
def index():
    return render_template_string(UI_TEMPLATE)

@app.route('/leaderboard')
def leaderboard():
    users = DatabaseManager.get_leaderboard(50)
    return render_template_string(LEADERBOARD_TEMPLATE, users=users)

@app.route('/connect', methods=['POST'])
def connect():
    if not rate_limiter.is_allowed(request.remote_addr):
        return jsonify({"status": "Rate limit"}), 429

    d = request.json
    # 'r' can now be "Room1,Room2,Room3"
    if not d or not d.get('u') or not d.get('p') or not d.get('r'):
        return jsonify({"status": "Missing info"}), 400

    with BOT_STATE["state_lock"]:
        if BOT_STATE["should_run"]:
            return jsonify({"status": "Already Running"})
            
        rooms_input = d['r'].split(',')
        BOT_STATE.update({
            "user": d['u'],
            "pass": d['p'],
            "target_rooms": rooms_input, # Store list
            "should_run": True,
            "domain": request.url_root,
            "status": "STARTING..."
        })
        
    threading.Thread(target=bot_thread_target, daemon=True).start()
    return jsonify({"status": "Starting..."})

@app.route('/disconnect', methods=['POST'])
def disconnect():
    with BOT_STATE["state_lock"]:
        BOT_STATE["should_run"] = False
        if BOT_STATE["ws"]:
            try: BOT_STATE["ws"].close()
            except: pass
    return jsonify({"status": "Stopped"})

@app.route('/clear_data', methods=['POST'])
def clear_data():
    CHAT_HISTORY.clear()
    DEBUG_LOGS.clear()
    return jsonify({"status": "Cleared"})

@app.route('/get_data')
def get_data():
    with BOT_STATE["state_lock"]:
        st = BOT_STATE["status"]
        rooms = list(BOT_STATE["active_rooms"].keys())
    return jsonify({
        "status": st,
        "rooms": rooms,
        "chat": CHAT_HISTORY.get_all(), 
        "debug": DEBUG_LOGS.get_all()
    })

@app.route('/download_logs')
def download_logs():
    logs = DEBUG_LOGS.get_all()
    log_str = "\n".join([f"[{x['time']}] {x['dir']}: {x['data']}" for x in logs])
    return Response(log_str, mimetype="text/plain", headers={"Content-Disposition": "attachment;filename=titan_logs.txt"})

# =============================================================================
# 8. UI TEMPLATES
# =============================================================================

LEADERBOARD_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body { background: #050505; color: #fff; font-family: monospace; padding: 20px; }
        .card { background: #111; border: 1px solid #333; padding: 10px; margin-bottom: 5px; display: flex; align-items: center; }
        .score { color: #00ff41; font-weight: bold; margin-left: auto; }
    </style>
</head>
<body>
    <h3 style="color:#00f3ff;text-align:center">TITAN RANKINGS</h3>
    {% for u in users %}
    <div class="card">
        <span>#{{loop.index}} {{ u[0] }}</span>
        <span class="score">{{ u[1] }}</span>
    </div>
    {% endfor %}
</body>
</html>
"""

UI_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TITAN V17 PRO</title>
    <style>
        body { margin: 0; background: #050505; color: #e0e6ed; font-family: monospace; height: 100vh; display: flex; flex-direction: column; }
        #login-view { position: absolute; width:100%; height:100%; z-index: 99; display: flex; justify-content: center; align-items: center; background: #000; }
        .login-card { width: 300px; padding: 20px; background: #111; border: 1px solid #333; text-align: center; }
        input { width: 90%; padding: 10px; margin-bottom: 10px; background: #000; border: 1px solid #333; color: #fff; }
        button { padding: 10px; background: #00f3ff; border: none; cursor: pointer; width: 100%; font-weight: bold; }
        #app-view { display: none; height: 100%; flex-direction: column; width: 100%; }
        header { height: 40px; background: #111; border-bottom: 1px solid #333; display: flex; align-items: center; padding: 0 10px; justify-content: space-between; }
        .content { flex: 1; overflow: hidden; display: flex; }
        #chat-col { flex: 2; border-right: 1px solid #333; overflow-y: auto; padding: 10px; display: flex; flex-direction: column; }
        #info-col { flex: 1; display: flex; flex-direction: column; }
        .msg-row { margin-bottom: 5px; font-size: 12px; }
        .active-rooms { font-size: 10px; color: #888; margin-top: 5px; }
    </style>
</head>
<body>
    <div id="login-view">
        <div class="login-card">
            <h2 style="color:#00f3ff">TITAN V17</h2>
            <input id="u" placeholder="Username">
            <input id="p" type="password" placeholder="Password">
            <input id="r" placeholder="Room1,Room2,Room3">
            <button onclick="login()">CONNECT MULTI-ROOM</button>
        </div>
    </div>
    <div id="app-view">
        <header>
            <span id="status-badge" style="font-weight:bold">OFFLINE</span>
            <button onclick="logout()" style="width:auto;background:red;color:#fff;padding:2px 8px;">STOP</button>
        </header>
        <div class="content">
            <div id="chat-col"></div>
            <div id="info-col">
                <iframe src="/leaderboard" style="flex:1;border:none;border-bottom:1px solid #333"></iframe>
                <div style="flex:1;background:#000;padding:5px;font-size:10px;overflow-y:auto" id="debug-area"></div>
            </div>
        </div>
        <div style="padding:5px;background:#111;text-align:center">
             <span id="room-list" class="active-rooms"></span>
        </div>
    </div>
    <script>
        function login() {
            const u=document.getElementById('u').value, p=document.getElementById('p').value, r=document.getElementById('r').value;
            fetch('/connect', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({u,p,r})})
            .then(r=>{
                if(r.status===200) {
                    document.getElementById('login-view').style.display='none';
                    document.getElementById('app-view').style.display='flex';
                } else alert("Error");
            });
        }
        function logout() { fetch('/disconnect', {method:'POST'}); location.reload(); }
        
        setInterval(() => {
            fetch('/get_data').then(r=>r.json()).then(d => {
                const b = document.getElementById('status-badge');
                b.innerText = d.status;
                b.style.color = d.status==='ONLINE'?'#0f0':'#f00';
                
                document.getElementById('room-list').innerText = "Active: " + d.rooms.join(", ");
                
                const c = document.getElementById('chat-col');
                c.innerHTML = d.chat.slice(-50).map(m => `
                    <div class="msg-row" style="color:${m.type==='bot'?'#00f3ff':'#ddd'}">
                        <b>${m.user}:</b> ${m.msg}
                    </div>`).join('');
                c.scrollTop = c.scrollHeight;
                
                const dbg = document.getElementById('debug-area');
                dbg.innerHTML = d.debug.slice(-20).reverse().map(l => `<div>[${l.dir}] ${typeof l.data==='object'?JSON.stringify(l.data):l.data}</div>`).join('');
            });
        }, 2000);
    </script>
</body>
</html>
"""

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, threaded=True)