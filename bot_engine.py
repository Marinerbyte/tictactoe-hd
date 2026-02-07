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
        
        # Room Data Storage
        self.room_details = {}
        self.room_id_to_name_map = {}
        
        self.lock = threading.Lock() 
        init_db()
        self.plugins = PluginManager(self)
        
        # ==========================================
        # 👑 BOSS JUGAD (Location 1)
        # ==========================================
        self.boss_list = ["yasin"] 
        
        self.log("Bot Engine Ready.")

    # ==========================================
    # 👑 BOSS CHECK FUNCTION (Location 2)
    # ==========================================
    def is_boss(self, username, user_id):
        """Global Boss Check: Plugins isse use karenge"""
        if username and username.lower() in self.boss_list:
            return True
        import db
        try:
            admins = db.get_all_admins()
            if user_id and str(user_id) in [str(a) for a in admins]:
                return True
        except:
            pass
        return False

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
        # Ping Interval 15s (Stable Connection)
        self.ws_thread = threading.Thread(target=lambda: self.ws.run_forever(ping_interval=15, ping_timeout=10)); self.ws_thread.daemon = True; self.ws_thread.start()

    def on_open(self, ws):
        self.log("WebSocket Connected.")
        self.send_json({"handler": "login", "username": self.user_data.get('username'), "password": self.user_data.get('password')})
        with self.lock:
            rooms = list(self.active_rooms)
        for room in rooms: self.join_room(room)

    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            
            # ======================================================
            # 🛠️ THE UNIVERSAL EXTRACTOR (Jad se ilaaj)
            # ======================================================
            # Server alag-alag naam se data bhejta hai, hum yahan fix kar rahe hain.
            
            # 1. USERNAME FIX
            # Agar 'username' nahi mila, to 'from' ya 'sender' check karo
            final_username = (
                data.get("username") or 
                data.get("from") or 
                data.get("sender") or 
                data.get("to")
            )
            
            # 2. USER ID FIX
            # CamelCase 'userId' aur normal 'userid' dono check karo
            final_userid = (
                data.get("userid") or 
                data.get("userId") or 
                data.get("id") or 
                data.get("user_id") or
                data.get("from_id")
            )

            # 3. Data me Wapas Daal Do (Standardization)
            if final_username: data["username"] = final_username
            if final_userid: data["userid"] = str(final_userid)
            
            # ======================================================

            handler = data.get("handler")

            # --- SYSTEM MESSAGE PASS ---
            if hasattr(self.plugins, 'process_system_message'):
                self.plugins.process_system_message(data)

            room_name = None
            room_id = str(data.get("roomid"))
            
            # Room Name Resolution
            if room_id in self.room_id_to_name_map:
                room_name = self.room_id_to_name_map[room_id]
            elif data.get("name"):
                 room_name = data.get("name")
            elif room_id in self.room_details:
                 room_name = room_id

            # Auto-Create Room Data
            if room_name and room_name not in self.room_details:
                with self.lock:
                    self.room_details[room_name] = {
                        'id': room_id, 
                        'users': [], 
                        'id_map': {}, 
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

            # 2. Handle Private Messages (DMs)
            elif handler in ["message", "privatemessage"] and not data.get("roomid"):
                self.plugins.process_message(data)            

            # 3. Join Success
            elif handler == "joinchatroom":
                self.log(f"Joined {room_name}")
                if room_id: self.send_json({"handler": "getusers", "id": uuid.uuid4().hex, "roomid": room_id})
            
            # 4. Handling User Lists (KICK FIX)
            elif handler in ["activeoccupants", "userslist"] and room_name:
                raw_users = data.get("users", [])
                new_users = []
                new_map = {}
                
                for u in raw_users:
                    # Yahan bhi Extractor logic use kar rahe hain manual
                    uname = u.get('username')
                    uid = str(u.get('userid') or u.get('userId') or u.get('id'))
                    
                    if uname and uid:
                        new_users.append(uname)
                        new_map[uname.lower()] = uid # ID Save ho gayi
                
                with self.lock:
                    self.room_details[room_name]['users'] = new_users
                    self.room_details[room_name]['id_map'] = new_map
                self.log(f"Updated list for {room_name}: {len(new_users)} users mapped.")

            # 5. User Join (Update Map)
            elif handler == "userjoin" and room_name:
                u = data.get("username")
                uid = data.get("userid") # Upar Extractor se mil gaya hoga
                with self.lock:
                    if u not in self.room_details[room_name]['users']:
                        self.room_details[room_name]['users'].append(u)
                    if uid:
                        self.room_details[room_name]['id_map'][u.lower()] = uid

            # 6. User Leave
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

    # ==========================================
    # ---  REQUIRED FUNCTIONS  ---
    # ==========================================

    def upload_to_server(self, image_bytes, file_type='png'):
        import io
        try:
            if not isinstance(image_bytes, (bytes, bytearray)):
                img_byte_arr = io.BytesIO()
                image_bytes.save(img_byte_arr, format=file_type.upper())
                image_bytes = img_byte_arr.getvalue()

            url = "https://api.howdies.app/api/upload"
            mime = 'image/gif' if file_type.lower() == 'gif' else 'image/png'
            files = {'file': (f'upload.{file_type}', image_bytes, mime)}
            data = {'token': self.token, 'uploadType': 'image', 'UserID': self.user_id if self.user_id else 0}
            
            r = requests.post(url, files=files, data=data, timeout=15)
            if r.status_code == 200:
                res = r.json()
                return res.get('url') or res.get('data', {}).get('url')
            return None
        except: return None

    def send_dm(self, username, text):
        if not username: return
        self.send_json({"handler": "message", "id": uuid.uuid4().hex, "type": "text", "to": username, "text": text})

    def send_dm_image(self, username, image_url, text=""):
        if not username or not image_url: return
        self.send_json({"handler": "message", "id": uuid.uuid4().hex, "type": "image", "to": username, "url": image_url, "text": text})

    def join_room(self, room_name, password=""):
        self.send_json({"handler": "joinchatroom", "id": uuid.uuid4().hex, "name": room_name, "roomPassword": password})
    
    def disconnect(self):
        self.running = False
        if self.ws: self.ws.close()
