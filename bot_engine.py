import websocket
import json
import threading
import time
import uuid
import requests
import traceback
from plugin_loader import PluginManager
from db import init_db

API_URL = "https://api.howdies.app/api/login"
WS_URL = "wss://app.howdies.app/howdies?token={}"

class HowdiesBot:
    def __init__(self):
        self.token = None; self.ws = None; self.user_data = {}
        self.user_id = None; self.active_rooms = []; self.logs = []
        self.running = False; self.start_time = time.time()
        
        # --- DATA STRUCTURE ---
        # room_details ab aisa dikhega:
        # { 
        #   'RoomName': {
        #       'id': '...', 
        #       'users': ['name1', 'name2'],  <-- UI ke liye
        #       'id_map': {'name1': 'id1', 'name2': 'id2'}, <-- ADMIN ke liye (CRITICAL)
        #       'chat_log': []
        #    }
        # }
        self.room_details = {}
        self.room_id_to_name_map = {}
        
        self.lock = threading.Lock() 
        init_db()
        self.plugins = PluginManager(self)
        self.log("Bot Engine Ready.")

    def log(self, message):
        entry = f"[{time.strftime('%X')}] {message}"
        print(entry)
        with self.lock:
            self.logs.append(entry)
            if len(self.logs) > 200: self.logs.pop(0)

    def login_api(self, username, password):
        self.log(f"Login attempt: {username}")
        try:
            r = requests.post(API_URL, json={"username": username, "password": password}, timeout=15)
            if r.status_code == 200:
                data = r.json()
                self.token = data.get('token') or data.get('data', {}).get('token')
                self.user_id = data.get('id') or data.get('user', {}).get('id') or data.get('data', {}).get('id')
                self.user_data = {"username": username, "password": password}
                self.log(f"API Login Success. ID: {self.user_id}")
                return True, "Success"
            return False, f"API Error: {r.text}"
        except Exception as e:
            return False, str(e)

    def connect_ws(self):
        if not self.token: return
        self.log("WebSocket Connecting...")
        url = WS_URL.format(self.token)
        self.ws = websocket.WebSocketApp(url, on_open=self.on_open, on_message=self.on_message, on_error=self.on_error, on_close=self.on_close)
        self.running = True
        self.ws_thread = threading.Thread(target=lambda: self.ws.run_forever(ping_interval=30, ping_timeout=10)); self.ws_thread.daemon = True; self.ws_thread.start()

    def on_open(self, ws):
        self.log("WebSocket Connected.")
        self.send_json({"handler": "login", "username": self.user_data.get('username'), "password": self.user_data.get('password')})
        with self.lock:
            rooms = list(self.active_rooms)
        for room in rooms: self.join_room(room)

    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            handler = data.get("handler")
            
            # --- DEBUG LOG (Admin issue pakadne ke liye) ---
            if handler in ["userslist", "activeoccupants"]:
                print(f"[DEBUG] List Received: {len(data.get('users', []))} users")

            # --- SYSTEM MESSAGE PASS ---
            if hasattr(self.plugins, 'process_system_message'):
                self.plugins.process_system_message(data)

            room_name = None
            room_id = str(data.get("roomid"))
            
            # Smart Room Name Resolution
            if room_id in self.room_id_to_name_map:
                room_name = self.room_id_to_name_map[room_id]
            elif data.get("name"):
                 room_name = data.get("name")
            elif room_id in self.room_details:
                 room_name = room_id

            # --- AUTO-CREATE ROOM DATA ---
            if room_name and room_name not in self.room_details:
                with self.lock:
                    self.room_details[room_name] = {
                        'id': room_id, 
                        'users': [], 
                        'id_map': {}, # <-- ID STORE HOGA YAHAN
                        'chat_log': []
                    }
                    if room_name not in self.active_rooms: self.active_rooms.append(room_name)
                    if room_id: self.room_id_to_name_map[room_id] = room_name

            # 1. Chat Processing
            if handler == "chatroommessage":
                if room_name:
                    author = data.get('username', 'Unknown')
                    mtype = 'bot' if author == self.user_data.get('username') else 'user'
                    with self.lock:
                        self.room_details[room_name]['chat_log'].append({'author': author, 'text': data.get('text', ''), 'type': mtype})
                self.plugins.process_message(data)
            
            # 2. Join Success -> Ask for List
            elif handler == "joinchatroom":
                self.log(f"Joined {room_name}")
                if room_id: self.send_json({"handler": "getusers", "id": uuid.uuid4().hex, "roomid": room_id})
            
            # 3. Handling User Lists (CRITICAL FIX)
            elif handler in ["activeoccupants", "userslist"] and room_name:
                raw_users = data.get("users", [])
                new_users = []
                new_map = {}
                
                for u in raw_users:
                    uname = u.get('username')
                    uid = str(u.get('userid') or u.get('id')) # Dono check karo
                    if uname and uid:
                        new_users.append(uname)
                        new_map[uname.lower()] = uid # Lowercase for easy search
                
                with self.lock:
                    self.room_details[room_name]['users'] = new_users
                    self.room_details[room_name]['id_map'] = new_map # IDs Saved!
                self.log(f"Updated list for {room_name}: {len(new_users)} users mapped.")

            # 4. Single User Join (Update Map)
            elif handler == "userjoin" and room_name:
                u = data.get("username")
                uid = str(data.get("userid") or data.get("id"))
                with self.lock:
                    if u not in self.room_details[room_name]['users']:
                        self.room_details[room_name]['users'].append(u)
                    if uid:
                        self.room_details[room_name]['id_map'][u.lower()] = uid

            # 5. Single User Leave
            elif handler == "userleave" and room_name:
                u = data.get("username")
                with self.lock:
                    if u in self.room_details[room_name]['users']:
                        self.room_details[room_name]['users'].remove(u)
                    if u.lower() in self.room_details[room_name]['id_map']:
                        del self.room_details[room_name]['id_map'][u.lower()]

        except Exception as e:
            traceback.print_exc()
    
    def on_error(self, ws, error): self.log(f"WS Error: {error}")
    def on_close(self, ws, _, __): 
        if self.running: 
            time.sleep(5); threading.Thread(target=self.connect_ws, daemon=True).start()

    def send_json(self, data):
        if self.ws and self.ws.sock and self.ws.sock.connected: self.ws.send(json.dumps(data))

    def send_message(self, room_id, text):
        self.send_json({"handler": "chatroommessage", "id": uuid.uuid4().hex, "type": "text", "roomid": room_id, "text": text})
    
    def join_room(self, room_name, password=""):
        self.send_json({"handler": "joinchatroom", "id": uuid.uuid4().hex, "name": room_name, "roomPassword": password})
    
    def disconnect(self):
        self.running = False; self.ws.close()
