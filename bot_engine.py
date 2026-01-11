import websocket
import json
import threading
import time
import uuid
import requests
from plugin_loader import PluginManager
from game_engine import GameEngine
from db import init_db

API_URL = "https://api.howdies.app/api/login"
WS_URL = "wss://app.howdies.app/howdies?token={}"


class HowdiesBot:
    def __init__(self):
        self.token = None
        self.ws = None
        self.user_data = {}
        self.user_id = 0
        self.active_rooms = []
        self.logs = []
        self.running = False

        # Components
        init_db()
        self.plugins = PluginManager(self)
        self.games = GameEngine(self)

    # ──────────────── Logger ────────────────
    def log(self, message):
        entry = f"[{time.strftime('%X')}] {message}"
        print(entry)
        self.logs.append(entry)
        if len(self.logs) > 100:
            self.logs.pop(0)

    # ──────────────── Login ────────────────
    def login_api(self, username, password):
        try:
            payload = {"username": username, "password": password}
            r = requests.post(API_URL, json=payload)
            if r.status_code != 200:
                return False, f"API Error: {r.text}"

            data = r.json()
            self.token = data.get("token") or data.get("data", {}).get("token")
            self.user_id = (
                data.get("id")
                or data.get("user", {}).get("id")
                or data.get("data", {}).get("id")
                or 0
            )
            if not self.token:
                return False, "Token missing"

            self.user_data = {"username": username, "password": password}
            self.log(f"Logged in as {username} (ID: {self.user_id})")
            return True, "Login successful"
        except Exception as e:
            return False, str(e)

    # ──────────────── Connect WS ────────────────
    def connect_ws(self):
        if not self.token:
            self.log("No token available. Login first.")
            return

        url = WS_URL.format(self.token)
        self.ws = websocket.WebSocketApp(
            url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
        )

        self.running = True
        self.ws_thread = threading.Thread(
            target=self.ws.run_forever,
            kwargs={"ping_interval": 30, "ping_timeout": 10},
            daemon=True,
        )
        self.ws_thread.start()

    # ──────────────── WS Events ────────────────
    def on_open(self, ws):
        self.log("WebSocket Connected")
        for room in self.active_rooms:
            self.join_room(room)

    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            handler = data.get("handler")
            if handler == "chatroommessage":
                self.handle_chat(data)
        except Exception as e:
            self.log(f"Error parsing message: {e}")

    def on_error(self, ws, error):
        self.log(f"WS Error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        self.log(f"WS Closed ({close_status_code}). Reconnecting in 5s...")
        if self.running:
            time.sleep(5)
            threading.Thread(target=self._reconnect, daemon=True).start()

    def _reconnect(self):
        u = self.user_data.get("username")
        p = self.user_data.get("password")
        if u and p:
            self.log("Refreshing Token...")
            self.login_api(u, p)
        self.connect_ws()

    # ──────────────── Handle Chat ────────────────
    def handle_chat(self, data):
        text = data.get("text", "")
        room = data.get("roomid")
        user = data.get("username", "Unknown")

        if not text:
            return

        # Extract avatar URL safely
        avatar_file = data.get("avatar")
        avatar_url = f"https://cdn.howdies.app/avatar?image={avatar_file}" if avatar_file else None

        # Commands vs Normal text
        if text.startswith("!"):
            parts = text[1:].split(" ")
            cmd = parts[0]
            args = parts[1:]
        else:
            active_game = self.games.get_game(room)
            if active_game:
                cmd = text.strip()
                args = []
            else:
                return  # Not a command, no active game

        # Dispatch command safely with avatar support
        try:
            handled = self.plugins.handle_command(cmd, room, user, args, avatar_url=avatar_url)
            if not handled:
                self.plugins.handle_command(cmd, room, user, args)  # fallback
        except Exception as e:
            self.log(f"Plugin dispatch error: {e}")

    # ──────────────── Send Helpers ────────────────
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
            "length": str(len(text)),
        }
        self.send_json(payload)

    # ──────────────── Room Join ────────────────
    def join_room(self, room_id, password="", from_ui=False):
        """
        Join a room.
        from_ui=True -> Room joined via UI button, don't send join payload
        """
        if room_id not in self.active_rooms:
            self.active_rooms.append(room_id)

        if from_ui:
            self.log(f"Room '{room_id}' joined via UI. Not sending join payload.")
            return

        payload = {
            "handler": "joinchatroom",
            "id": uuid.uuid4().hex,
            "roomid": room_id,
            "roomPassword": password,
        }
        self.send_json(payload)
        self.log(f"Sent join payload for room '{room_id}'")

    # ──────────────── Disconnect ────────────────
    def disconnect(self):
        self.running = False
        if self.ws:
            self.ws.close()
