import websocket
import json
import threading
import time
import uuid
import requests
from plugin_loader import PluginManager
from db import init_db

API_URL = "https://api.howdies.app/api/login"
WS_URL = "wss://app.howdies.app/howdies?token={}"

class HowdiesBot:
    def __init__(self):
        self.token = None; self.ws = None; self.user_data = {}
        self.user_id = None; self.active_rooms = []; self.logs = []
        self.running = False; self.start_time = time.time()
        self.room_details = {}
        init_db()
        self.plugins = PluginManager(self)
        self.log("Bot Initialized. Ready to connect.")

    def log(self, message):
        entry = f"[{time.strftime('%X')}] {message}"
        print(entry)
        self.logs.append(entry)
        if len(self.logs) > 150: self.logs.pop(0)

    def login_api(self, username, password):
        self.log(f"Attempting API login for user: {username}...")
        try:
            r = requests.post(API_URL, json={"username": username, "password": password}, timeout=10)
            if r.status_code == 200:
                data = r.json()
                self.token = data.get('token') or data.get('data', {}).get('token')
                self.user_id = data.get('id') or data.get('user', {}).get('id') or data.get('data', {}).get('id')
                self.user_data = {"username": username, "password": password}
                self.log(f"SUCCESS: Logged in as {username} (ID: {self.user_id})")
                return True, "Login successful!"
            
            self.log(f"ERROR: Login failed. Status: {r.status_code}, Response: {r.text}")
            return False, f"API Error: {r.text}"
        except Exception as e:
            self.log(f"ERROR: Exception during login: {e}")
            return False, str(e)

    def connect_ws(self):
        if not self.token: self.log("ERROR: Cannot connect, no token available."); return
        
        self.log("Connection: Attempting to connect to WebSocket...")
        url = WS_URL.format(self.token)
        self.ws = websocket.WebSocketApp(url,
                                         on_open=self.on_open,
                                         on_message=self.on_message,
                                         on_error=self.on_error,
                                         on_close=self.on_close)
        self.running = True
        self.ws_thread = threading.Thread(target=lambda: self.ws.run_forever(ping_interval=30, ping_timeout=10))
        self.ws_thread.daemon = True
        self.ws_thread.start()

    def on_open(self, ws):
        self.log("SUCCESS: WebSocket Connected. Authenticating...")
        self.start_time = time.time()
        
        # --- THIS IS THE FIX ---
        # Connect hote hi server ko batao ki "Main aa gaya hu"
        self.send_json({
            "handler": "login",
            "username": self.user_data.get('username'),
            "password": self.user_data.get('password')
        })
        
        # Re-join rooms if it was a reconnection
        for room in self.active_rooms:
            self.join_room(room)

    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            handler = data.get("handler")
            room_name = data.get("roomid") or data.get("name")

            if handler == "chatroommessage":
                if room_name and room_name in self.room_details:
                    author = data.get('username', 'Unknown')
                    text = data.get('text', '')
                    author_class = 'bot' if author == self.user_data.get('username') else 'user'
                    log_entry = {'author': author, 'text': text, 'type': author_class}
                    self.room_details[room_name]['chat_log'].append(log_entry)
                    if len(self.room_details[room_name]['chat_log']) > 50:
                        self.room_details[room_name]['chat_log'].pop(0)
                self.plugins.process_message(data)
            
            elif handler == "userjoin" and room_name in self.room_details:
                user = data.get("username")
                if user not in self.room_details[room_name]['users']:
                    self.room_details[room_name]['users'].append(user)
                    self.log(f"EVENT: User '{user}' joined '{room_name}'")

            elif handler == "userleave" and room_name in self.room_details:
                user = data.get("username")
                if user in self.room_details[room_name]['users']:
                    self.room_details[room_name]['users'].remove(user)
                    self.log(f"EVENT: User '{user}' left '{room_name}'")
            
            elif handler == "joinchatroom" and room_name:
                users = [u.get('username') for u in data.get("users", [])]
                self.room_details[room_name] = {'users': users, 'chat_log': []}
                if room_name not in self.active_rooms:
                    self.active_rooms.append(room_name)
                self.log(f"SUCCESS: Joined '{room_name}' with {len(users)} users.")

        except Exception as e:
            self.log(f"ERROR: Failed to process message - {e}")

    def on_error(self, ws, error):
        self.log(f"ERROR: WebSocket error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        self.log("Connection: WebSocket Closed. Reconnecting in 5 seconds...")
        if self.running:
            time.sleep(5)
            self.connect_ws()

    def send_json(self, data):
        if self.ws and self.ws.sock and self.ws.sock.connected:
            self.ws.send(json.dumps(data))
        else:
            self.log("ERROR: Cannot send, WebSocket not connected.")

    def send_message(self, room_id, text):
        self.send_json({"handler": "chatroommessage", "id": uuid.uuid4().hex, "type": "text", "roomid": room_id, "text": text, "url": ""})
    
    def join_room(self, room_name, password=""):
        self.log(f"Action: Joining room '{room_name}'...")
        self.send_json({"handler": "joinchatroom", "id": uuid.uuid4().hex, "name": room_name, "roomPassword": password})
    
    def disconnect(self):
        self.log("Action: Disconnecting bot...")
        self.running = False
        self.room_details = {}
        self.active_rooms = []
        if self.ws:
            self.ws.close()
