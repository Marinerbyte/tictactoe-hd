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
    # In production, ensure this is set.
    ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "change_me_in_production") 
    DATABASE_URL = os.environ.get("DATABASE_URL")
    
    # Game Settings
    DB_FILE = "howdies_v17_pro.db"
    TABLE_NAME = "howdies_gamers_v17"
    MAX_CHAT_HISTORY = 200
    MAX_DEBUG_LOGS = 500
    MAX_ACTIVE_GAMES = 500  # Memory protection
    GAME_TIMEOUT_SECONDS = 45 # Strict 45s Rule
    
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
# 2. STATE MANAGEMENT, SECURITY & THREAD SAFETY
# =============================================================================

class RateLimiter:
    """Simple in-memory rate limiter for Admin endpoints."""
    def __init__(self):
        self._attempts = {}
        self._lock = threading.Lock()

    def is_allowed(self, ip_addr):
        now = time.time()
        with self._lock:
            # Cleanup old entries
            self._attempts = {k: v for k, v in self._attempts.items() if now - v['last'] < 300}
            
            if ip_addr not in self._attempts:
                self._attempts[ip_addr] = {'count': 0, 'last': now}
            
            entry = self._attempts[ip_addr]
            
            # Reset if time passed
            if now - entry['last'] > 60:
                entry['count'] = 0
                entry['last'] = now
                
            if entry['count'] >= 10: 
                return False
                
            entry['count'] += 1
            entry['last'] = now
            return True

rate_limiter = RateLimiter()

class ThreadSafeList:
    """Optimized Thread-safe list using deque for O(1) appends/pops."""
    def __init__(self, max_size):
        # Use deque with maxlen for automatic eviction
        self._list = collections.deque(maxlen=max_size)
        self._lock = threading.RLock()

    def append(self, item):
        with self._lock:
            self._list.append(item)

    def get_all(self):
        with self._lock:
            return list(self._list)
    
    def clear(self):
        with self._lock:
            self._list.clear()

# Global State
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
    """Recursively scrub sensitive fields from logs."""
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except ValueError:
            return payload
    
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
        # Convert back to string for consistent storage if it was dict
        if isinstance(safe_data, (dict, list)):
            try: safe_data = json.dumps(safe_data)
            except: pass
            
        DEBUG_LOGS.append({"time": time.strftime("%H:%M:%S"), "dir": direction, "data": safe_data})
    except Exception as e:
        logger.error(f"Logging error: {e}")

# =============================================================================
# 3. DATABASE MANAGER (DOUBLE LOCKING ADDED)
# =============================================================================

class DatabaseManager:
    @staticmethod
    def get_connection():
        """Context manager for DB connection with WAL mode for SQLite."""
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
                logger.info("Database initialized successfully.")
            except Exception as e:
                logger.critical(f"DB Init Failed: {e}")
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
                
                conn.commit()
                return new_score
            except Exception as e:
                logger.error(f"DB Update Error for {username}: {e}")
                return 0
            finally:
                if conn: conn.close()

    @staticmethod
    def get_score(username):
        # Read operations are safer with WAL, but locking ensures we don't read mid-write
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
# 4. ASSET GENERATION (Updated with 1-9 Mapping)
# =============================================================================

def create_number_asset(number):
    """Generates a semi-transparent number for board mapping."""
    img = Image.new('RGBA', (300, 300), (0,0,0,0))
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 100)
    except:
        font = ImageFont.load_default()
        
    text = str(number)
    # Simple centering
    d.text((120, 100), text, fill=(255, 255, 255, 80), font=font)
    return img

def create_fallback_coin(text, color_type):
    coin_size = 300
    img = Image.new('RGBA', (coin_size, coin_size), (0,0,0,0))
    d = ImageDraw.Draw(img)
    
    if color_type == "gold":
        main_color = (255, 215, 0)
        outline_color = (184, 134, 11)
    else:
        main_color = (192, 192, 192)
        outline_color = (105, 105, 105)

    d.ellipse([5, 5, 295, 295], fill=main_color, outline=outline_color, width=5)
    d.ellipse([25, 25, 275, 275], outline=(255, 255, 255, 100), width=3)
    
    try: font = ImageFont.truetype("arial.ttf", 150)
    except IOError: font = ImageFont.load_default()
    
    try:
        d.text((120, 100), text, fill=outline_color, font=font) 
    except Exception:
        pass
        
    return img

def load_image_from_url(url, fallback_text, color_type):
    try:
        response = requests.get(url, stream=True, timeout=10)
        response.raise_for_status()
        img = Image.open(io.BytesIO(response.content)).convert("RGBA")
        return img.resize((300, 300))
    except Exception as e:
        logger.warning(f"Asset Download Failed ({fallback_text}): {e}")
        return create_fallback_coin(fallback_text, color_type)

def init_assets():
    if ASSETS.get('loaded'): return

    try:
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

        x_img = Image.new('RGBA', (300, 300), (0,0,0,0))
        dx = ImageDraw.Draw(x_img)
        dx.line([(60,60), (240,240)], fill=(255, 0, 80), width=45)
        dx.line([(240,60), (60,240)], fill=(255, 0, 80), width=45)
        ASSETS['x'] = x_img

        o_img = Image.new('RGBA', (300, 300), (0,0,0,0))
        do = ImageDraw.Draw(o_img)
        do.ellipse([60,60,240,240], outline=(0, 255, 100), width=45)
        ASSETS['o'] = o_img

        ASSETS['heads'] = load_image_from_url(Config.HEADS_URL, "H", "gold")
        ASSETS['tails'] = load_image_from_url(Config.TAILS_URL, "T", "silver")
        
        # Load 1-9 Overlays
        for i in range(1, 10):
            ASSETS[str(i)] = create_number_asset(i)
        
        ASSETS['loaded'] = True
        logger.info("Assets initialized.")
    except Exception as e:
        logger.error(f"Asset Init Failed: {e}")

# =============================================================================
# 5. BOT NETWORK CORE (Multi-Room & Crash Fix)
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
    CRITICAL FIX: Forces room_id to string to prevent subscriptable error.
    """
    with BOT_STATE["state_lock"]:
        ws = BOT_STATE["ws"]
        
    if not room_id:
        logger.error("Attempted to send message without Room ID")
        return
        
    # FIX: Force String
    rid_str = str(room_id)

    if ws and ws.sock and ws.sock.connected:
        pkt = {
            "handler": "chatroommessage", 
            "id": str(time.time()), 
            "type": type, 
            "roomid": rid_str, 
            "text": text, 
            "url": url, 
            "length": "0"
        }
        try:
            ws.send(json.dumps(pkt))
            bot_av = "https://cdn-icons-png.flaticon.com/512/4712/4712035.png"
            # FIX: Slicing safe string
            display = f"[{rid_str[:5]}] [IMG]" if url else f"[{rid_str[:5]}] {text}"
            CHAT_HISTORY.append({"user": "TitanBot", "msg": display, "avatar": bot_av, "time": time.strftime("%H:%M"), "type": "bot"})
            log_debug("OUT", pkt)
        except Exception as e:
            logger.error(f"Send Error: {e}")

def join_room(ws, room_name):
    pkt = {"handler": "joinchatroom", "id": str(time.time()), "name": room_name, "roomPassword": ""}
    ws.send(json.dumps(pkt))
    log_debug("OUT", f"Joining {room_name}")

def leave_room(ws, room_id):
    pkt = {"handler": "leavechatroom", "id": str(time.time()), "roomid": str(room_id)}
    ws.send(json.dumps(pkt))
    log_debug("OUT", f"Leaving {room_id}")

def on_open(ws):
    with BOT_STATE["state_lock"]:
        BOT_STATE["status"] = "AUTHENTICATING"
        user = BOT_STATE["user"]
        pwd = BOT_STATE["pass"]
        target_rooms = BOT_STATE["target_rooms"]

    login_pkt = {"handler": "login", "username": user, "password": pwd}
    ws.send(json.dumps(login_pkt))
    log_debug("OUT", login_pkt)
    
    time.sleep(1.0)
    
    # Auto-Rejoin All Target Rooms
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
    
    # State Updates & Room Capture
    if handler == "joinchatroom" and data.get("roomid") and data.get("name"):
        r_name = data["name"]
        r_id = str(data.get("roomid")) # FIX: Force String
        with BOT_STATE["state_lock"]:
            BOT_STATE["active_rooms"][r_name] = r_id
            if r_name not in BOT_STATE["target_rooms"]:
                BOT_STATE["target_rooms"].append(r_name)
        log_debug("SYSTEM", f"Joined Room: {r_name} ({r_id})")
        
    if data.get("avatar_url") and data.get("username"):
        with BOT_STATE["state_lock"]:
            BOT_STATE["avatars"][data["username"]] = data["avatar_url"]
            
    if handler not in ["receipt_ack", "ping", "pong"]:
        log_debug("IN", data)
        
    # Handle Chat
    if handler in ["chatroommessage", "message"]:
        msg_body = data.get("text") or data.get("body")
        sender = data.get("from") or data.get("username")
        
        # FIX: Handle Room ID safely as string
        raw_rid = data.get("roomid")
        room_id = str(raw_rid) if raw_rid is not None else None
        
        if msg_body and sender and room_id:
            with BOT_STATE["state_lock"]:
                av = BOT_STATE["avatars"].get(sender, "https://cdn-icons-png.flaticon.com/512/149/149071.png")
                my_user = BOT_STATE["user"]
            
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
    """Main Bot Loop."""
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
                with BOT_STATE["state_lock"]:
                    BOT_STATE["status"] = "AUTH FAILED"
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
            
            with BOT_STATE["state_lock"]:
                BOT_STATE["ws"] = ws
            
            ws.run_forever(ping_interval=20, ping_timeout=10)
            
            with BOT_STATE["state_lock"]:
                if BOT_STATE["should_run"]:
                    BOT_STATE["status"] = "RETRYING..."
                else:
                    break
            time.sleep(5)
            
        except Exception as e:
            logger.error(f"Critical Bot Loop Error: {e}")
            with BOT_STATE["state_lock"]:
                BOT_STATE["status"] = "CRASH_RECOVER"
            time.sleep(5)

# =============================================================================
# 6. GAME LOGIC ENGINE (Fixed 45s Cleanup & Keys)
# =============================================================================

def cleanup_idle_games():
    """Removes games idle for > 45 seconds."""
    while True:
        time.sleep(5)
        try:
            with BOT_STATE["state_lock"]:
                should_run = BOT_STATE["should_run"]
            if not should_run: continue

            now = time.time()
            to_remove = []
            
            with GAME_LOCK:
                # 1. Timeout Check (45s Rule)
                for key, game in ACTIVE_GAMES.items():
                    if now - game['last_active'] > Config.GAME_TIMEOUT_SECONDS:
                        to_remove.append(key)
                
                # 2. Hard Cap Check
                if len(ACTIVE_GAMES) > Config.MAX_ACTIVE_GAMES:
                    sorted_games = sorted(ACTIVE_GAMES.items(), key=lambda x: x[1]['last_active'])
                    excess = len(ACTIVE_GAMES) - Config.MAX_ACTIVE_GAMES
                    for i in range(excess):
                        if sorted_games[i][0] not in to_remove:
                            to_remove.append(sorted_games[i][0])

            # Process Removal
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
    """Composite key for Multi-Room Support."""
    return f"{room_id}_{user}"

def process_command(user, msg, room_id):
    """Parses and routes commands scoped by Room ID."""
    try:
        msg = msg.strip().lower()

        # Multi-Room Commands
        if msg.startswith("!j "):
            target = msg[3:].strip()
            with BOT_STATE["state_lock"]: ws = BOT_STATE["ws"]
            if ws and target:
                join_room(ws, target)
            return

        if msg == "!leave":
            with BOT_STATE["state_lock"]: ws = BOT_STATE["ws"]
            if ws:
                leave_room(ws, room_id)
                # Cleanup local state
                r_name = next((k for k,v in BOT_STATE["active_rooms"].items() if v == room_id), None)
                if r_name and r_name in BOT_STATE["target_rooms"]:
                     BOT_STATE["target_rooms"].remove(r_name)
            return

        if msg == "!help":
            send_msg(room_id, "🎮 **COMMANDS:**\n• `!tic 1` (Start)\n• `!flip`\n• `!score`\n• `!j <room>`/`!leave`")
            return

        if msg == "!score":
            bal = DatabaseManager.get_score(user)
            with BOT_STATE["state_lock"]:
                domain = BOT_STATE.get('domain', '')
            link = f" | 🏆 Rank: {domain}leaderboard" if domain else ""
            send_msg(room_id, f"💳 {user}: **{bal}** pts{link}")
            return

        if msg == "!reset":
            key = get_game_key(room_id, user)
            with GAME_LOCK:
                if key in ACTIVE_GAMES:
                    ACTIVE_GAMES.pop(key)
                    send_msg(room_id, f"♻ Game reset for {user}.")
                else:
                    send_msg(room_id, f"⚠ No active game found.")
            return

        if msg.startswith("!flip"):
            handle_flip(user, msg, room_id)
            return

        if msg == "!tic 1":
            handle_tic_start(user, room_id)
            return

        if msg.startswith("!join"):
            handle_ttt_join(user, msg, room_id)
            return

        if msg.isdigit():
            handle_numeric_input(user, msg, room_id)

    except Exception as e:
        logger.error(f"Cmd Error: {e}")

def handle_tic_start(user, room_id):
    key = get_game_key(room_id, user)
    
    with GAME_LOCK:
        # Check if user is already playing in THIS room
        for k, v in ACTIVE_GAMES.items():
            if v['room_id'] == room_id and (v['p1'] == user or v['p2'] == user):
                send_msg(room_id, f"⚠ {user}, finish current game first.")
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
    
    send_msg(room_id, f"@{user} **Choose mode:**\n1) vs Bot\n2) vs Player\nReply `1` or `2`")

def handle_numeric_input(user, msg, room_id):
    # 1. Check for Host Setup
    key = get_game_key(room_id, user)
    
    with GAME_LOCK:
        if key in ACTIVE_GAMES:
            game = ACTIVE_GAMES[key]
            if game["phase"].startswith("SETUP_"):
                handle_setup_input(user, msg, game)
                return

        # 2. Check for Gameplay Move (User can be p1 or p2)
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
    
    with GAME_LOCK:
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
            else:
                send_msg(rid, f"⚠ Reply `1` or `2`.")

        elif phase == "SETUP_BET_TYPE":
            if text == "1":
                game["phase"] = "SETUP_BET_AMOUNT"
                curr_score = DatabaseManager.get_score(user)
                send_msg(rid, f"@{user} Enter bet amount (Min 100):")
            elif text == "2":
                game["bet"] = 0
                finalize_setup(game)
            else:
                send_msg(rid, f"⚠ Reply `1` or `2`.")

        elif phase == "SETUP_BET_AMOUNT":
            try:
                amt = int(text)
                balance = DatabaseManager.get_score(user)
                if amt < 100:
                    send_msg(rid, f"⚠ Minimum bet is 100.")
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
    if len(parts) < 2:
        send_msg(room_id, "Usage: `!join <host>`")
        return

    host_target = parts[1]
    
    # Logic to find game in THIS room
    target_key = get_game_key(room_id, host_target)
    
    with GAME_LOCK:
        # Try exact match, then fuzzy
        if target_key not in ACTIVE_GAMES:
            for k, v in ACTIVE_GAMES.items():
                if v['room_id'] == room_id and v['host'].lower() == host_target.lower():
                    target_key = k
                    break
        
        if target_key not in ACTIVE_GAMES:
            send_msg(room_id, "⚠ Game not found in this room.")
            return

        game = ACTIVE_GAMES[target_key]
        
        if game["phase"] != "WAITING_P2":
            send_msg(room_id, "⚠ Lobby not available.")
            return

        if user == game['host']:
             send_msg(room_id, "⚠ Cannot join own game.")
             return

        if game.get("bet", 0) > 0:
            if DatabaseManager.get_score(user) < game["bet"]:
                send_msg(room_id, f"⚠ Need {game['bet']} pts to join.")
                return
            
        game["p2"] = user
        game["phase"] = "PLAYING"
        game["last_active"] = time.time()
    
    send_msg(room_id, f"⚔ **MATCH STARTED!**\n{user} joined {game['p1']}.")
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
            return

        idx = move - 1
        if game["board"][idx] != " ":
            send_msg(rid, "⚠ Taken!")
            return

        game["board"][idx] = curr_turn

    if check_game_over(game, user): return

    with GAME_LOCK:
        # Re-check existence
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
            
    rid = game['room_id']
    bet = game.get("bet", 0)
    key = get_game_key(rid, game['host'])

    if win_line:
        render_and_send_board(game, win_line)
        prize_msg = ""
        
        if bet > 0:
            winner = last_mover
            if game["mode"] == "bot":
                loser = "TitanBot" if winner == game["p1"] else game["p1"]
            else:
                loser = game["p2"] if winner == game["p1"] else game["p1"]

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
            if c == 'X': base.paste(x_img, ((i%3)*300, (i//3)*300), x_img)
            elif c == 'O': base.paste(o_img, ((i%3)*300, (i//3)*300), o_img)
            else:
                # 1-9 Overlay
                num = ASSETS.get(str(i+1))
                if num: base.paste(num, ((i%3)*300, (i//3)*300), num)
            
        if line:
            draw = ImageDraw.Draw(base)
            try:
                idx = [int(k) for k in line.split(',')]
                s, e = idx[0], idx[2]
                draw.line([((s%3)*300+150, (s//3)*300+150), ((e%3)*300+150, (e//3)*300+150)], fill="#ffd700", width=30)
            except ValueError: pass

        img_io = io.BytesIO()
        base.save(img_io, 'PNG')
        uploaded_url = upload_image_to_howdies(img_io.getvalue())
        
        if uploaded_url:
            send_msg(game['room_id'], "", "image", uploaded_url)
        else:
            send_msg(game['room_id'], "⚠ Render Failed")
    except Exception as e:
        logger.error(f"Render Logic Error: {e}")

def handle_flip(user, msg, room_id):
    parts = msg.split()
    guess = None
    if len(parts) > 1:
        raw_guess = parts[1].upper()
        if raw_guess in ["H", "HEAD", "HEADS"]: guess = "HEADS"
        elif raw_guess in ["T", "TAIL", "TAILS"]: guess = "TAILS"
    
    result = random.choice(["HEADS", "TAILS"])
    
    def process_flip_async():
        try:
            send_msg(room_id, f"@{user} tossed the coin! 🌪️")
            
            # ANIMATION
            frames = []
            base_h = ASSETS['heads'].resize((200, 200))
            base_t = ASSETS['tails'].resize((200, 200))
            W, H = 400, 500
            total_frames = 15
            
            for i in range(total_frames):
                frame = Image.new('RGBA', (W, H), (0,0,0,0))
                progress = i / (total_frames - 1)
                height = 4 * progress * (1 - progress) * 350
                y_pos = 400 - height
                scale = abs(math.cos(i * 1.5))
                w = int(200 * scale)
                if w < 1: w = 1
                coin = (base_h if i % 2 == 0 else base_t).resize((w, 200))
                frame.paste(coin, ((W - w)//2, int(y_pos)), coin)
                frames.append(frame)
            
            img_io = io.BytesIO()
            frames[0].save(img_io, format='GIF', save_all=True, append_images=frames[1:], duration=50, loop=0, disposal=2)
            spin_url = upload_image_to_howdies(img_io.getvalue(), is_gif=True)
            if spin_url: send_msg(room_id, "", "image", spin_url)
            
            time.sleep(3.5)
            
            # RESULT
            res_img = ASSETS['heads'] if result == "HEADS" else ASSETS['tails']
            res_io = io.BytesIO()
            res_img.save(res_io, 'PNG')
            res_url = upload_image_to_howdies(res_io.getvalue())
            if res_url: send_msg(room_id, "", "image", res_url)
            
            outcome_text = f"✨ Result: **{result}**"
            if guess:
                if guess == result:
                    new_bal = DatabaseManager.update_score(user, 50)
                    outcome_text += f"\n🎉 **YOU WON!** (+50 pts)\n💰 Balance: {new_bal}"
                else:
                    new_bal = DatabaseManager.update_score(user, -20)
                    outcome_text += f"\n❌ **YOU LOST** (-20 pts)\n💰 Balance: {new_bal}"
            else:
                new_bal = DatabaseManager.get_score(user)
                outcome_text += f"\n💰 Balance: {new_bal}"

            time.sleep(0.5)
            send_msg(room_id, outcome_text)
        except Exception as e:
            logger.error(f"Flip Error: {e}")
    
    threading.Thread(target=process_flip_async).start()

# =============================================================================
# 7. FLASK ROUTES (ADMIN PANEL & UI)
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
        return jsonify({"status": "Too Many Attempts. Wait 60s."}), 429

    d = request.json
    # Support multiple rooms comma separated
    if not d or not d.get('u') or not d.get('p') or not d.get('r'):
        return jsonify({"status": "Missing credentials"}), 400

    with BOT_STATE["state_lock"]:
        if BOT_STATE["should_run"]:
            return jsonify({"status": "Already Running"})
            
        BOT_STATE.update({
            "user": d['u'],
            "pass": d['p'],
            "target_rooms": d['r'].split(','),
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
        status = BOT_STATE["status"]
        rooms = list(BOT_STATE["active_rooms"].keys())
    
    return jsonify({
        "status": status, 
        "rooms": rooms,
        "chat": CHAT_HISTORY.get_all(), 
        "debug": DEBUG_LOGS.get_all()
    })

@app.route('/download_logs')
def download_logs():
    logs = DEBUG_LOGS.get_all()
    log_str = "\n".join([f"[{x['time']}] {x['dir']}: {x['data']}" for x in logs])
    return Response(log_str, mimetype="text/plain", headers={"Content-Disposition": "attachment;filename=titan_logs.txt"})

@app.route('/render')
def render():
    try:
        b_str = request.args.get('b', '_________')
        w_line = request.args.get('w', '')
        
        init_assets()
        base = ASSETS['board'].copy()
        x_img, o_img = ASSETS['x'], ASSETS['o']
        
        for i, c in enumerate(b_str):
            if i < 9:
                if c == 'X': base.paste(x_img, ((i%3)*300, (i//3)*300), x_img)
                elif c == 'O': base.paste(o_img, ((i%3)*300, (i//3)*300), o_img)
                
        if w_line:
            draw = ImageDraw.Draw(base)
            idx = [int(k) for k in w_line.split(',') if k.isdigit()]
            if len(idx) == 3:
                s, e = idx[0], idx[2]
                draw.line([((s%3)*300+150, (s//3)*300+150), ((e%3)*300+150, (e//3)*300+150)], fill="#ffd700", width=25)
                
        img_io = io.BytesIO()
        base.save(img_io, 'PNG')
        img_io.seek(0)
        return send_file(img_io, mimetype='image/png')
    except Exception as e:
        logger.error(f"Render Error: {e}")
        return "Render Error", 500

# =============================================================================
# 8. HTML TEMPLATES (The Full UI)
# =============================================================================

LEADERBOARD_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>TITAN RANKINGS</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { background: #050505; color: #fff; font-family: monospace; margin: 0; padding: 20px; }
        .card { background: #111; border: 1px solid #333; padding: 15px; margin-bottom: 12px; display: flex; align-items: center; }
        .avatar { width: 50px; height: 50px; border-radius: 50%; margin-right: 15px; object-fit: cover; }
        .info { flex: 1; }
        .score { font-size: 20px; color: #00ff41; font-weight: bold; }
    </style>
</head>
<body>
    <h1 style="color:#00f3ff;text-align:center">TITAN LEGENDS</h1>
    {% for u in users %}
    <div class="card">
        <div style="font-size:20px;width:40px">#{{loop.index}}</div>
        <img class="avatar" src="{{ u[3] or 'https://via.placeholder.com/50' }}" onerror="this.src='https://via.placeholder.com/50'">
        <div class="info">
            <div style="font-weight:bold;font-size:18px">{{ u[0] }}</div>
            <div style="color:#888">Wins: {{ u[2] }}</div>
        </div>
        <div class="score">{{ u[1] }}</div>
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
        #login-view { position: absolute; top:0; left:0; width:100%; height:100%; z-index: 99; display: flex; justify-content: center; align-items: center; background: #000; }
        .login-card { width: 300px; padding: 20px; background: #111; border: 1px solid #333; text-align: center; }
        input { width: 90%; padding: 10px; margin-bottom: 10px; background: #000; border: 1px solid #333; color: #fff; }
        button { padding: 10px; background: #00f3ff; border: none; cursor: pointer; width: 100%; font-weight: bold; }
        #app-view { display: none; height: 100%; flex-direction: column; width: 100%; }
        header { height: 50px; background: #111; border-bottom: 1px solid #333; display: flex; align-items: center; justify-content: space-between; padding: 0 15px; }
        .content { flex: 1; position: relative; overflow: hidden; }
        .tab-content { position: absolute; top:0; left:0; width:100%; height:100%; display: none; flex-direction: column; }
        .active-tab { display: flex; }
        #chat-container { flex: 1; overflow-y: auto; padding: 15px; }
        .msg-row { margin-bottom: 10px; }
        .bubble { background: #1e1e1e; padding: 8px; display: inline-block; border-radius: 8px; max-width: 80%; word-wrap: break-word; }
        .debug-logs { flex: 1; overflow-y: auto; padding: 10px; background: #000; font-size: 10px; }
        nav { height: 50px; background: #000; border-top: 1px solid #333; display: flex; }
        .nav-btn { flex: 1; background: transparent; border: none; color: #555; cursor: pointer; font-weight: bold; }
        .active { color: #00f3ff; background: #111; }
        iframe { width: 100%; height: 100%; border: none; }
        #room-status { font-size: 10px; color: #aaa; margin-right: 10px; }
    </style>
</head>
<body>
    <div id="login-view">
        <div class="login-card">
            <h2 style="color:#00f3ff">TITAN V17</h2>
            <input id="u" placeholder="Howdies Username">
            <input id="p" type="password" placeholder="Password">
            <input id="r" placeholder="Room1,Room2,Room3">
            <button onclick="login()">CONNECT</button>
        </div>
    </div>
    <div id="app-view">
        <header>
            <span>TITAN PANEL</span>
            <div style="display:flex;align-items:center">
                <span id="room-status"></span>
                <span id="status-badge" style="font-weight:bold;margin-right:15px">OFFLINE</span>
                <button onclick="logout()" style="width:auto;background:red;color:#fff;border:none;padding:5px 10px">X</button>
            </div>
        </header>
        <div class="content">
            <div id="tab-chat" class="tab-content active-tab">
                <div id="chat-container"></div>
            </div>
            <div id="tab-lb" class="tab-content">
                <iframe src="/leaderboard"></iframe>
            </div>
            <div id="tab-debug" class="tab-content">
                <div style="padding:5px;border-bottom:1px solid #333">
                    <a href="/download_logs" style="color:#00f3ff">Download Logs</a>
                    <button onclick="clearData()" style="width:auto;padding:2px 5px;margin-left:10px">Clear</button>
                </div>
                <div id="debug-log-area" class="debug-logs"></div>
            </div>
        </div>
        <nav>
            <button onclick="switchTab('chat')" id="btn-chat" class="nav-btn active">CHAT</button>
            <button onclick="switchTab('lb')" id="btn-lb" class="nav-btn">RANKS</button>
            <button onclick="switchTab('debug')" id="btn-debug" class="nav-btn">DEBUG</button>
        </nav>
    </div>
    <script>
        function switchTab(t) {
            document.querySelectorAll('.tab-content').forEach(e=>e.classList.remove('active-tab'));
            document.querySelectorAll('.nav-btn').forEach(e=>e.classList.remove('active'));
            document.getElementById('tab-'+t).classList.add('active-tab');
            document.getElementById('btn-'+t).classList.add('active');
            if(t==='lb') document.querySelector('iframe').src = '/leaderboard';
        }
        function login() {
            const u=document.getElementById('u').value, p=document.getElementById('p').value, r=document.getElementById('r').value;
            if(!u||!p||!r) return alert("Fill all!");
            fetch('/connect', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({u,p,r})})
            .then(r=>{
                if(r.status===429) return alert("Too many attempts. Wait 60s.");
                if(r.status!==200) return alert("Error connecting");
                document.getElementById('login-view').style.display='none';
                document.getElementById('app-view').style.display='flex';
            });
        }
        function logout() { fetch('/disconnect', {method:'POST'}); location.reload(); }
        function clearData() { fetch('/clear_data', {method: 'POST'}); }
        setInterval(() => {
            fetch('/get_data').then(r=>r.json()).then(d => {
                const badge = document.getElementById('status-badge');
                badge.innerText = d.status;
                badge.style.color = (d.status==='ONLINE' || d.status.includes('CONNECT')) ?'#0f0':'#666';
                if(d.status.includes('RETRY')) badge.style.color = 'orange';
                if(d.status.includes('FAIL')) badge.style.color = 'red';
                
                if(d.rooms) document.getElementById('room-status').innerText = "Rooms: " + d.rooms.join(", ");
                
                const c = document.getElementById('chat-container');
                c.innerHTML = d.chat.map(m => `
                    <div class="msg-row" style="text-align:${m.type==='bot'?'right':'left'}">
                        <div class="bubble"><b>${m.user}:</b> ${m.msg}</div>
                    </div>`).join('');
                
                const dbg = document.getElementById('debug-log-area');
                dbg.innerHTML = d.debug.slice(-50).reverse().map(l => {
                    const dataStr = typeof l.data === 'object' ? JSON.stringify(l.data) : l.data;
                    return `<div style="margin-bottom:5px;border-bottom:1px solid #222"><span style="color:${l.dir==='IN'?'#0f0':'#0ff'}">[${l.dir}]</span> ${dataStr}</div>`
                }).join('');
            });
        }, 1500);
    </script>
</body>
</html>
"""

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, threaded=True)