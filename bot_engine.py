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
        self.user_id = None
        self.active_rooms = []
        self.logs = []
        self.running = False
        init_db()
        self.plugins = PluginManager(self)
        self.games = GameEngine(self)

    def log(self, message):
        entry = f"[{time.strftime('%X')}] {message}"
        print(entry)
        self.logs.append(entry)
        if len(self.logs) > 100: self.logs.pop(0)

    def login_api(self, username, password):
        try:
            payload = {"username": username, "password": password}
            r = requests.post(API_URL, json=payload)
            if r.status_code == 200:
                data = r.json()
                self.token = data.get('token') or data.get('data', {}).get('token')
                self.user_id = data.get('id') or data.get('user', {}).get('id') or data.get('data', {}).get('id')
                if not self.user_id: self.user_id = 0
                self.user_data = {"username": username, "password": password}
                self.log(f"Logged in as {username} (ID: {self.user_id})")
                return True, "Token received"
            return False, f"API Error: {r.text}"
        except Exception as e:
            return False, str(e)

    def connect_ws(self):
        if not self.token: return
        url = WS_URL.format(self.token)
        self.ws = websocket.WebSocketApp(url, on_open=self.on_open, on_message=self.on_message, on_error=self.on_error, on_close=self.on_close)
        self.running = True
        self.ws_thread = threading.Thread(target=self.ws.run_forever, kwargs={"ping_interval": 30, "ping_timeout": 10})
        self.ws_thread.start()

    def on_open(self, ws):
        self.log("WebSocket Connected")
        self.send_json({"handler": "login", "username": self.user_data.get('username'), "password": self.user_data.get('password')})
        for room in self.active_rooms: self.join_room(room)

    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            handler = data.get("handler")
            
            # --- FINAL FIX: Pass EVERYTHING to Plugin Manager ---
            # Hum yahan filter nahi karenge. Sab kuch plugin loader ke paas jayega.
            if handler == "chatroommessage":
                self.plugins.process_message(data)
                
        except Exception as e:
            self.log(f"Error parsing: {e}")

    def on_error(self, ws, error): self.log(f"WS Error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        self.log(f"WS Closed. Reconnecting...")
        if self.running:
            time.sleep(5)
            if self.user_data: self.login_api(self.user_data['username'], self.user_data['password'])
            self.connect_ws()

    def send_json(self, data):
        if self.ws and self.ws.sock and self.ws.sock.connected: self.ws.send(json.dumps(data))

    def send_message(self, room_id, text):
        self.send_json({"handler": "chatroommessage", "id": uuid.uuid4().hex, "type": "text", "roomid": room_id, "text": text, "url": "", "length": str(len(text))})
    
    def join_room(self, room_name, password=""):
        self.send_json({"handler": "joinchatroom", "id": uuid.uuid4().hex, "name": room_name, "roomPassword": password})
        if room_name not in self.active_rooms: self.active_rooms.append(room_name)

    def disconnect(self):
        self.running = False
        if self.ws: self.ws.close()
