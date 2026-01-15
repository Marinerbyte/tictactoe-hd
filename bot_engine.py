import websocket
import json
import threading
import time
import uuid
import requests
import traceback
from plugin_loader import PluginManager
from db import init_db

# --- CONFIGURATION ---
API_LOGIN_URL = "https://api.howdies.app/api/login"
WS_URL_TEMPLATE = "wss://app.howdies.app/howdies?token={}"

class HowdiesBot:
    def __init__(self):
        # --- CORE STATE ---
        self.token = None
        self.ws = None
        self.user_data = {}  # Stores username, password, user_id
        self.user_id = None
        
        # --- UI & DATA STATE ---
        self.active_rooms = []  # List of room names
        self.logs = []          # System logs for UI
        self.room_details = {}  # { 'RoomName': { 'id': '...', 'users': [], 'chat_log': [] } }
        self.room_id_to_name = {} # Map ID -> Name for quick lookups
        
        # --- THREAD SAFETY ---
        # UI reads data while WS writes data. This lock prevents crashes/corruption.
        self.data_lock = threading.Lock()
        
        self.running = False
        self.start_time = time.time()
        
        # --- SUBSYSTEMS ---
        init_db()  # Database connection setup
        self.plugins = PluginManager(self) # Pass bot instance to plugins
        
        self.log("Bot Engine Initialized. Waiting for start command...")

    # --- LOGGING FOR UI ---
    def log(self, message):
        """Logs messages to the in-memory list for the UI Dashboard."""
        timestamp = time.strftime('%H:%M:%S')
        entry = f"[{timestamp}] {message}"
        print(entry) # Print to console
        with self.data_lock:
            self.logs.append(entry)
            if len(self.logs) > 200: self.logs.pop(0)

    # --- AUTHENTICATION (HTTP) ---
    def login_api(self, username, password):
        """Step 1: Get Token from API"""
        self.log(f"Attempting API login for user: {username}...")
        try:
            payload = {"username": username, "password": password}
            r = requests.post(API_LOGIN_URL, json=payload, timeout=15)
            
            if r.status_code == 200:
                data = r.json()
                # Handle different API response structures safely
                self.token = data.get('token') or data.get('data', {}).get('token')
                
                # Extract User ID (Crucial for game/admin logic)
                self.user_id = data.get('id') or data.get('user', {}).get('id') or data.get('data', {}).get('id')
                
                if not self.token:
                    return False, "Login success but Token not found in response."

                self.user_data = {"username": username, "password": password}
                self.log(f"Login Successful! UserID: {self.user_id}")
                return True, "Login successful!"
            
            else:
                self.log(f"Login Failed. Status: {r.status_code} | Body: {r.text}")
                return False, f"API Error: {r.text}"
                
        except Exception as e:
            self.log(f"Login Exception: {str(e)}")
            return False, str(e)

    # --- WEBSOCKET CONNECTION ---
    def connect_ws(self):
        """Step 2: Connect to WebSocket"""
        if not self.token:
            self.log("Error: Cannot connect. No token available.")
            return

        self.log("Connecting to WebSocket...")
        url = WS_URL_TEMPLATE.format(self.token)
        
        # Initialize WebSocket
        self.ws = websocket.WebSocketApp(
            url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        
        self.running = True
        
        # Run in separate thread so Flask (UI) doesn't freeze
        self.ws_thread = threading.Thread(
            target=lambda: self.ws.run_forever(ping_interval=30, ping_timeout=10)
        )
        self.ws_thread.daemon = True
        self.ws_thread.start()

    # --- WS HANDLERS ---
    def on_open(self, ws):
        self.log("WebSocket Connected! Sending Login Packet...")
        self.start_time = time.time()
        
        # Send Login Packet (Protocol Requirement)
        self.send_json({
            "handler": "login",
            "username": self.user_data.get('username'),
            "password": self.user_data.get('password')
        })
        
        # Re-join previous rooms if any
        with self.data_lock:
            rooms_to_join = list(self.active_rooms)
            
        for room in rooms_to_join:
            self.join_room(room)

    def on_message(self, ws, message):
        """
        The Brain of the Bot.
        Parses every incoming message and routes it to UI and Plugins.
        """
        try:
            data = json.loads(message)
            handler = data.get("handler")
            
            # --- 1. DETERMINE ROOM CONTEXT ---
            room_id = str(data.get("roomid", ""))
            room_name = data.get("name") # Sometimes in packet
            
            # Resolve Room Name from ID if missing
            if not room_name and room_id in self.room_id_to_name:
                room_name = self.room_id_to_name[room_id]
            elif not room_name and room_id in self.room_details: # Fallback
                room_name = room_id

            # Attach resolved name back to data for plugins
            data['resolved_room_name'] = room_name

            # --- 2. ADMIN/SYSTEM PLUGIN HOOK (CRITICAL) ---
            # This allows admin.py to see 'userslist' or 'getusers' responses
            # to map Usernames -> IDs for Kicking/Banning.
            self.plugins.process_system_message(data)

            # --- 3. UI UPDATES & CHAT HOOK ---
            with self.data_lock:
                
                # A. Handle Chat Messages
                if handler == "chatroommessage":
                    # Pass to Plugins (Command processing)
                    self.plugins.process_message(data)
                    
                    # Update UI Log
                    if room_name and room_name in self.room_details:
                        author = data.get('username', 'Unknown')
                        # Determine message type for UI styling
                        msg_type = 'bot' if author == self.user_data.get('username') else 'user'
                        
                        log_entry = {
                            'author': author,
                            'text': data.get('text', ''),
                            'type': msg_type,
                            'url': data.get('url', '') # For images
                        }
                        
                        self.room_details[room_name]['chat_log'].append(log_entry)
                        # Keep memory clean (last 50 msgs)
                        if len(self.room_details[room_name]['chat_log']) > 50:
                            self.room_details[room_name]['chat_log'].pop(0)

                # B. Handle Room Joining Success
                elif handler == "joinchatroom":
                    if room_name:
                        # Initialize Room Data Structure
                        if room_name not in self.room_details:
                            self.room_details[room_name] = {
                                'id': room_id,
                                'users': [],
                                'chat_log': []
                            }
                        # Map ID to Name
                        self.room_id_to_name[room_id] = room_name
                        if room_name not in self.active_rooms:
                            self.active_rooms.append(room_name)
                        
                        self.log(f"Successfully Joined: {room_name} (ID: {room_id})")
                        
                        # Trigger a user fetch for Admin ID mapping
                        self.send_json({
                            "handler": "getusers",
                            "id": uuid.uuid4().hex,
                            "roomid": room_id
                        })

                # C. Handle User Lists (Docs: 'getusers' returns this or 'activeoccupants')
                elif handler in ["userslist", "activeoccupants"] and room_name:
                    # Logic to update UI user list
                    raw_users = data.get("users", [])
                    # Extract just usernames for simple UI list
                    user_list = [u.get('username') for u in raw_users]
                    if room_name in self.room_details:
                        self.room_details[room_name]['users'] = user_list
                        # self.log(f"Updated user list for {room_name}")

                # D. Handle User Join/Leave
                elif handler == "userjoin" and room_name in self.room_details:
                    u = data.get("username")
                    if u and u not in self.room_details[room_name]['users']:
                        self.room_details[room_name]['users'].append(u)
                        
                elif handler == "userleave" and room_name in self.room_details:
                    u = data.get("username")
                    if u in self.room_details[room_name]['users']:
                        self.room_details[room_name]['users'].remove(u)

        except Exception as e:
            self.log(f"Core Error (on_message): {e}")
            traceback.print_exc()

    def on_error(self, ws, error):
        self.log(f"WebSocket Error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        self.log(f"Disconnected from Server. ({close_status_code})")
        if self.running:
            self.log("Attempting reconnection in 5 seconds...")
            time.sleep(5)
            # Re-spawn thread to avoid recursion depth issues
            new_thread = threading.Thread(target=self.connect_ws)
            new_thread.daemon = True
            new_thread.start()

    # --- ACTIONS (Available to Plugins) ---
    
    def send_json(self, data):
        """Raw method to send JSON payloads to WebSocket"""
        try:
            if self.ws and self.ws.sock and self.ws.sock.connected:
                self.ws.send(json.dumps(data))
            else:
                self.log("Warning: Attempted to send data while disconnected.")
        except Exception as e:
            self.log(f"Send Error: {e}")

    def send_message(self, room_id, text):
        """Helper to send a standard chat message"""
        # Ensure ID is string
        rid = str(room_id)
        self.send_json({
            "handler": "chatroommessage",
            "id": uuid.uuid4().hex,
            "type": "text",
            "roomid": rid,
            "text": str(text)
        })

    def join_room(self, room_name, password=""):
        """Helper to join a room"""
        self.log(f"Queueing Join: {room_name}")
        self.send_json({
            "handler": "joinchatroom",
            "id": uuid.uuid4().hex,
            "name": room_name,
            "roomPassword": password
        })

    def disconnect(self):
        """Clean shutdown"""
        self.log("Shutting down bot...")
        self.running = False
        if self.ws:
            self.ws.close()
        
        # Clean UI State
        with self.data_lock:
            self.active_rooms = []
            self.room_details = {}
            self.room_id_to_name = {}
