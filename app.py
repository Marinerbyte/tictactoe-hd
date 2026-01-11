# app.py
import os
import json
import time
import threading
import uuid
import websocket
import ssl
import importlib
import sqlite3
import psycopg2
import requests

from flask import Flask, request, jsonify

app = Flask(__name__)

# ============================================================
# CONFIG & LOCKS
# ============================================================
DB_LOCK = threading.Lock()
GAME_LOCK = threading.Lock()
PLUGIN_LOCK = threading.Lock()
BOT = {
    "status": "DISCONNECTED",
    "user": os.environ.get("BOT_USER", ""),
    "pass": os.environ.get("BOT_PASS", ""),
    "rooms": {},           # room_name: ws_instance
    "token": "",
    "user_id": None,
    "domain": os.environ.get("BOT_DOMAIN", ""),
    "should_run": False,
    "avatars": {}
}
ACTIVE_GAMES = {}          # room_name: {game_name: {...}}
PLUGINS = {}               # plugin_name: module

# ============================================================
# DATABASE
# ============================================================
DATABASE_URL = os.environ.get("DATABASE_URL")
USE_SQLITE = False if DATABASE_URL else True
DB_FILE_NAME = "bot.db"

def get_db():
    if USE_SQLITE:
        return sqlite3.connect(DB_FILE_NAME, check_same_thread=False)
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def init_db():
    with DB_LOCK:
        conn = get_db()
        c = conn.cursor()
        # Users table
        c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username VARCHAR(255) PRIMARY KEY,
            score INTEGER DEFAULT 1000,
            wins INTEGER DEFAULT 0,
            avatar_url TEXT
        )
        ''')
        conn.commit()
        conn.close()

def update_score(username, points, avatar_url=None):
    with DB_LOCK:
        conn = get_db()
        c = conn.cursor()
        ph = "?" if USE_SQLITE else "%s"
        c.execute(f"SELECT score, wins FROM users WHERE username={ph}", (username,))
        data = c.fetchone()
        if data:
            new_score = data[0] + points
            new_wins = data[1] + (1 if points > 0 else 0)
            if avatar_url:
                c.execute(f"UPDATE users SET score={ph}, wins={ph}, avatar_url={ph} WHERE username={ph}", 
                          (new_score, new_wins, avatar_url, username))
            else:
                c.execute(f"UPDATE users SET score={ph}, wins={ph} WHERE username={ph}", (new_score, new_wins, username))
        else:
            new_score = 1000 + points
            new_wins = 1 if points > 0 else 0
            c.execute(f"INSERT INTO users (username, score, wins, avatar_url) VALUES ({ph},{ph},{ph},{ph})",
                      (username, new_score, new_wins, avatar_url))
        conn.commit()
        conn.close()
        return new_score

init_db()

# ============================================================
# PLUGIN SYSTEM
# ============================================================
PLUGIN_FOLDER = "plugins"

def load_plugin(plugin_name):
    with PLUGIN_LOCK:
        if plugin_name in PLUGINS:
            return PLUGINS[plugin_name]
        try:
            module = importlib.import_module(f"{PLUGIN_FOLDER}.{plugin_name}")
            if hasattr(module, "setup"):
                module.setup(BOT, ACTIVE_GAMES, update_score)
            PLUGINS[plugin_name] = module
            print(f"[PLUGIN] Loaded: {plugin_name}")
            return module
        except Exception as e:
            print(f"[PLUGIN ERROR] {plugin_name}: {e}")
            return None

def unload_plugin(plugin_name):
    with PLUGIN_LOCK:
        if plugin_name in PLUGINS:
            try:
                if hasattr(PLUGINS[plugin_name], "teardown"):
                    PLUGINS[plugin_name].teardown()
                del PLUGINS[plugin_name]
                print(f"[PLUGIN] Unloaded: {plugin_name}")
            except Exception as e:
                print(f"[PLUGIN ERROR] Unload {plugin_name}: {e}")

# ============================================================
# WEBSOCKET BOT CORE (Multi-Room)
# ============================================================
def perform_login(username, password):
    try:
        resp = requests.post("https://api.howdies.app/api/login", json={"username": username, "password": password}, timeout=15)
        data = resp.json()
        token = data.get("token") or data.get("data", {}).get("token")
        user_id = data.get("id") or data.get("data", {}).get("id")
        BOT["user_id"] = user_id
        return token
    except Exception as e:
        print(f"[LOGIN ERROR] {e}")
        return None

def start_room(room_name):
    if room_name in BOT["rooms"]:
        print(f"[ROOM] Already connected: {room_name}")
        return

    def run_ws():
        while BOT["should_run"]:
            if not BOT["token"]:
                BOT["token"] = perform_login(BOT["user"], BOT["pass"])
                if not BOT["token"]:
                    time.sleep(5)
                    continue
            url = f"wss://app.howdies.app/howdies?token={BOT['token']}"
            ws = websocket.WebSocketApp(url, on_open=lambda ws: on_open(ws, room_name),
                                        on_message=lambda ws, msg: on_message(ws, msg, room_name),
                                        on_error=on_error, on_close=on_close)
            BOT["rooms"][room_name] = ws
            ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
            time.sleep(5)

    threading.Thread(target=run_ws, daemon=True).start()

def on_open(ws, room_name):
    print(f"[WS] Connected to {room_name}")
    join_pkt = {"handler": "joinchatroom", "id": str(time.time()), "name": room_name, "roomPassword": ""}
    ws.send(json.dumps(join_pkt))

def on_message(ws, message, room_name):
    try:
        data = json.loads(message)
        sender = data.get("from") or data.get("username")
        text = data.get("text")
        if sender and text:
            # Call all plugins safely
            with PLUGIN_LOCK:
                for p in PLUGINS.values():
                    try:
                        if hasattr(p, "on_message"):
                            p.on_message(sender, text, room_name)
                    except Exception as e:
                        print(f"[PLUGIN MSG ERROR] {e}")
    except Exception as e:
        print(f"[MSG ERROR] {e}")

def on_error(ws, error):
    print(f"[WS ERROR] {error}")

def on_close(ws, code, msg):
    print(f"[WS CLOSED] {code} | {msg}")

# ============================================================
# DASHBOARD ENDPOINTS
# ============================================================
MASTER_USER = os.environ.get("MASTER_USER", "admin")
MASTER_PASS = os.environ.get("MASTER_PASS", "admin")

@app.route("/dashboard/login", methods=["POST"])
def dashboard_login():
    data = request.json
    if data.get("user") == MASTER_USER and data.get("pass") == MASTER_PASS:
        return jsonify({"status": "ok"})
    return jsonify({"status": "fail"})

@app.route("/dashboard/start_room", methods=["POST"])
def dashboard_start_room():
    data = request.json
    room_name = data.get("room")
    if not room_name: return jsonify({"status": "fail", "msg": "No room"})
    start_room(room_name)
    return jsonify({"status": "ok", "room": room_name})

@app.route("/dashboard/load_plugin", methods=["POST"])
def dashboard_load_plugin():
    data = request.json
    plugin_name = data.get("plugin")
    if not plugin_name: return jsonify({"status": "fail", "msg": "No plugin"})
    mod = load_plugin(plugin_name)
    return jsonify({"status": "ok" if mod else "fail", "plugin": plugin_name})

@app.route("/dashboard/unload_plugin", methods=["POST"])
def dashboard_unload_plugin():
    data = request.json
    plugin_name = data.get("plugin")
    if not plugin_name: return jsonify({"status": "fail", "msg": "No plugin"})
    unload_plugin(plugin_name)
    return jsonify({"status": "ok", "plugin": plugin_name})

# ============================================================
# RUN BOT
# ============================================================
def start_bot():
    BOT["should_run"] = True
    print("[BOT] Starting...")

if __name__ == "__main__":
    start_bot()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
