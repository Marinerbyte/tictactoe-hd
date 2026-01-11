import websocket
import json
import threading
import time
import uuid
import requests

from plugin_loader import PluginManager
from game_engine import GameEngine
from db import init_db

# ──────────────────────────────────────────────
# Howdies Config
# ──────────────────────────────────────────────

API_URL = "https://api.howdies.app/api/login"
WS_URL = "wss://app.howdies.app/howdies?token={}"

# ──────────────────────────────────────────────
# Bot Class
# ──────────────────────────────────────────────

class HowdiesBot:
    def __init__(self):
        self.token = None
        self.ws = None
        self.user_data = {}
        self.user_id = 0
        self.active_rooms = []
        self.logs = []
        self.running = False

        # Init components
        init_db()
        self.plugins = PluginManager(self)
        self.games = GameEngine(self)

    # ──────────────────────────────────────────
    # Logger
    # ──────────────────────────────────────────

    def log(self, message):
        entry = f"[{time.strftime('%X')}] {message}"
        print(entry)
        self.logs.append(entry)
        if len(self.logs) > 100:
            self.logs.pop(0)

    # ──────────────────────────────────────────
    # Login via REST API
    # ──────────────────────────────────────────

    def login_api(self, username, password):
        try:
            payload = {
                "username": username,
                "password": password
            }

            r = requests.post(API_URL, json=payload)
            if r.status_code != 200:
                return False, r.text

            data = r.json()

            self.token = (
                data.get("token")
                or data.get("data", {}).get("token")
            )

            self.user_id = (
                data.get("id")
                or data.get("user", {}).get("id")
                or data.get("data", {}).get("id")
                or 0
            )

            if not self.token:
                return False, "Token missing"

            self.user_data = {
                "username": username
            }

            self.log(f"Logged in as {username} (ID: {self.user_id})")
            return True, "Login successful"

        except Exception as e:
            return False, str(e)

    # ──────────────────────────────────────────
    # WebSocket Connect
    # ──────────────────────────────────────────

    def connect_ws(self):
        if not self.token:
            self.log("Login first")
            return

        url = WS_URL.format(self.token)

        self.ws = websocket.WebSocketApp(
            url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )

        self.running = True
        threading.Thread(target=self.ws.run_forever, daemon=True).start()

    def on_open(self, ws):
        self.log("WebSocket connected")

        # Token auth already done, no WS login payload needed
        for room in self.active_rooms:
            self.join_room(room)

    # ──────────────────────────────────────────
    # Incoming Messages
    # ──────────────────────────────────────────

    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            handler = data.get("handler")

            if handler == "chatroommessage":
                self.handle_chat(data)

        except Exception as e:
            self.log(f"Parse error: {e}")

    # ──────────────────────────────────────────
    # CHAT HANDLER (UPDATED + AVATAR SUPPORT)
    # ──────────────────────────────────────────

    def handle_chat(self, data):
        text = data.get("text", "")
        room = data.get("roomid")
        user = data.get("username", "Unknown")

        # Avatar extraction
        avatar_file = data.get("avatar")
        avatar_url = None
        if avatar_file:
            avatar_url = f"https://cdn.howdies.app/avatar?image={avatar_file}"

        if not text:
            return

        # Commands
        if text.startswith("!"):
            parts = text[1:].split(" ")
            cmd = parts[0]
            args = parts[1:]

            self.plugins.handle_command(
                cmd=cmd,
                room=room,
                user=user,
                args=args,
                avatar_url=avatar_url
            )

        # Game input
        else:
            active_game = self.games.get_game(room)
            if active_game:
                self.plugins.handle_command(
                    cmd=text.strip(),
                    room=room,
                    user=user,
                    args=[],
                    avatar_url=avatar_url
                )

    # ──────────────────────────────────────────
    # Send Helpers
    # ──────────────────────────────────────────

    def send_json(self, data):
        if self.ws and self.ws.sock and self.ws.sock.connected:
            self.ws.send(json.dumps(data))

    def send_message(self, room_id, text):
        payload = {
            "handler": "chatroommessage",
            "id": uuid.uuid4().hex,
            "type": "text",
            "roomid": room_id,
            "text": text,
            "url": "",
            "length": str(len(text))
        }
        self.send_json(payload)

    # ──────────────────────────────────────────
    # Room Join
    # ──────────────────────────────────────────

    def join_room(self, room_id, password=""):
        payload = {
            "handler": "joinchatroom",
            "id": uuid.uuid4().hex,
            "roomid": room_id,
            "roomPassword": password
        }

        self.send_json(payload)

        if room_id not in self.active_rooms:
            self.active_rooms.append(room_id)

    # ──────────────────────────────────────────
    # Errors / Close
    # ──────────────────────────────────────────

    def on_error(self, ws, error):
        self.log(f"WS error: {error}")

    def on_close(self, ws, code, msg):
        self.log("WebSocket closed")

        if self.running:
            time.sleep(5)
            self.connect_ws()

    def disconnect(self):
        self.running = False
        if self.ws:
            self.ws.close()
