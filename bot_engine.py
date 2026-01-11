import websocket
import json
import threading
import time
import uuid
import requests
from plugin_loader import PluginManager
from game_engine import GameEngine
from db import init_db

# Howdies Config
API_URL = "https://api.howdies.app/api/login"
WS_URL = "wss://app.howdies.app/howdies?token={}"

class HowdiesBot:
    def __init__(self):
        self.token = None
        self.ws = None
        self.user_data = {}
        self.active_rooms = []
        self.logs = []
        self.running = False
        
        # Components
        init_db()
        self.plugins = PluginManager(self)
        self.games = GameEngine(self)

    def log(self, message):
        entry = f"[{time.strftime('%X')}] {message}"
        print(entry)
        self.logs.append(entry)
        if len(self.logs) > 100: 
            self.logs.pop(0)

    def login_api(self, username, password):
        try:
            payload = {"username": username, "password": password}
            r = requests.post(API_URL, json=payload)
            if r.status_code == 200:
                data = r.json()
                self.token = data.get('token') or data.get('data', {}).get('token')
                self.user_data = {"username": username, "password": password}
                return True, "Token received"
            return False, f"API Error: {r.text}"
        except Exception as e:
            return False, str(e)

    def connect_ws(self):
        if not self.token:
            self.log("No token available. Login first.")
            return

        url = WS_URL.format(self.token)
        self.ws = websocket.WebSocketApp(url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        
        self.running = True
        self.ws_thread = threading.Thread(target=self.ws.run_forever)
        self.ws_thread.start()

    def on_open(self, ws):
        self.log("WebSocket Connected")
        # Send Login Packet
        login_payload = {
            "handler": "login",
            "username": self.user_data['username'],
            "password": self.user_data['password']
        }
        self.send_json(login_payload)
        
        # Re-join active rooms if any
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

    # --- Updated handle_chat with safe game input filter ---
    def handle_chat(self, data):
        text = data.get("text", "")
        room = data.get("roomid")
        user = data.get("username", "Unknown")

        if not text:
            return

        # Case 1: Commands starting with "!" (e.g., !tic, !stop)
        if text.startswith("!"):
            parts = text[1:].split(" ")
            cmd = parts[0]
            args = parts[1:]
            self.plugins.handle_command(cmd, room, user, args)
        
        # Case 2: Game inputs without "!" (e.g., 1, 2, j)
        else:
            # Only forward input if a game is active in this room
            game = self.games.get_game(room)
            if not game:
                return  # No active game → ignore normal chat

            cmd = text.strip()
            args = []
            self.plugins.handle_command(cmd, room, user, args)

    def on_error(self, ws, error):
        self.log(f"WS Error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        self.log("WS Closed. Reconnecting in 5s..." if self.running else "WS Closed.")
        if self.running:
            time.sleep(5)
            self.connect_ws()

    def send_json(self, data):
        if self.ws and self.ws.sock and self.ws.sock.connected:
            self.ws.send(json.dumps(data))
        else:
            self.log("Cannot send: WS disconnected")

    # --- API Wrappers for Plugins ---
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
    
    def join_room(self, room_name, password=""):
        payload = {
            "handler": "joinchatroom",
            "id": uuid.uuid4().hex,
            "name": room_name,
            "roomPassword": password
        }
        self.send_json(payload)
        if room_name not in self.active_rooms:
            self.active_rooms.append(room_name)

    def disconnect(self):
        self.running = False
        if self.ws:
            self.ws.close()
