import os
import time
import threading
import psycopg2
import uuid

# --- CONFIG ---
DB_URL = os.environ.get("NILU_DATABASE_URL")
MASTER_USER = "yasin"

# --- DATABASE HANDLERS ---
def db_exec(query, params=(), fetch=False):
    if not DB_URL: return None
    conn = None
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute(query, params)
        res = cur.fetchall() if fetch else None
        conn.commit()
        return res
    except Exception as e:
        print(f"[RoomManager DB Error] {e}")
        return None
    finally:
        if conn: conn.close()

def init_room_db():
    # 1. Saved Rooms with Requester (Owner)
    db_exec("CREATE TABLE IF NOT EXISTS saved_rooms (room_name TEXT PRIMARY KEY, requester TEXT)")
    # 2. Bot Settings (For Default Room)
    db_exec("CREATE TABLE IF NOT EXISTS bot_settings (key TEXT PRIMARY KEY, value TEXT)")

def set_default_room(room_name):
    db_exec("INSERT INTO bot_settings (key, value) VALUES ('default_room', %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", (room_name,))

def get_default_room():
    res = db_exec("SELECT value FROM bot_settings WHERE key = 'default_room'", (), True)
    return res[0][0] if res else None

def save_room(room_name, requester):
    db_exec("INSERT INTO saved_rooms (room_name, requester) VALUES (%s, %s) ON CONFLICT (room_name) DO UPDATE SET requester = EXCLUDED.requester", (room_name, requester))

def get_saved_rooms_data():
    return db_exec("SELECT room_name, requester FROM saved_rooms", (), True) or []

def remove_room(room_name):
    db_exec("DELETE FROM saved_rooms WHERE room_name = %s", (room_name,))

def clear_all_rooms():
    db_exec("DELETE FROM saved_rooms")

def get_room_requester(room_name):
    res = db_exec("SELECT requester FROM saved_rooms WHERE room_name = %s", (room_name,), True)
    return res[0][0] if res else None

# ==========================================
# ⚡ ADVANCED AUTO-JOIN LOGIC
# ==========================================
def auto_join_task(bot):
    print("[RoomManager] Initializing Startup Sequence...")
    time.sleep(3) # Initial Boot Wait

    # 1. Join Default Room First
    def_room = get_default_room()
    if def_room:
        print(f"[RoomManager] Joining Default Room: {def_room}")
        bot.join_room(def_room)
        time.sleep(5) # Wait after default room join

    # 2. Join Saved Rooms Slowly
    rooms_data = get_saved_rooms_data()
    if not rooms_data:
        print("[RoomManager] No saved rooms to join.")
        return

    print(f"[RoomManager] Joining {len(rooms_data)} saved rooms...")
    for room_name, requester in rooms_data:
        if not bot.running: break
        if room_name == def_room: continue # Already joined
        
        print(f"[RoomManager] Auto-Joining: {room_name}")
        bot.join_room(room_name)
        time.sleep(4) # 4 second gap to avoid spam filters
    
    print("[RoomManager] Startup sequence complete.")

# ==========================================
# 🔌 PLUGIN SETUP
# ==========================================
def setup(bot):
    init_room_db()
    threading.Thread(target=auto_join_task, args=(bot,), daemon=True).start()

# ==========================================
# 📨 COMMAND HANDLER
# ==========================================
def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    user_lower = user.lower()
    
    # 1. DEFAULT ROOM SET (!def roomname)
    if cmd == "def":
        if user_lower != MASTER_USER: return False
        if not args:
            bot.send_message(room_id, "Usage: `!def <roomname>`")
            return True
        # Join the full name (fix for symbols/spaces)
        target_room = " ".join(args)
        set_default_room(target_room)
        bot.send_message(room_id, f"🏠 **Default Room** set to: {target_room}")
        return True

    # 2. JOIN COMMAND (!j roomname [sv])
    if cmd in ["j", "join"]:
        if not args: return True
        
        # Room name fix: Join all args except the last one if last one is 'sv'
        save_mode = False
        if len(args) > 1 and args[-1].lower() == "sv":
            save_mode = True
            target_room = " ".join(args[:-1])
        else:
            target_room = " ".join(args)

        bot.join_room(target_room)
        
        if save_mode:
            save_room(target_room, user_lower)
            bot.send_message(room_id, f"✅ Joined & Saved: **{target_room}** (Owner: @{user})")
        else:
            bot.send_message(room_id, f"🚀 Temporary Join: **{target_room}**")
        return True

    # 3. LEAVE COMMAND (!leave)
    if cmd == "leave":
        current_room_name = bot.room_id_to_name_map.get(room_id)
        if not current_room_name: return False

        requester = get_room_requester(current_room_name)
        
        # PERMISSION CHECK: Master or the person who saved the room
        if user_lower == MASTER_USER or (requester and user_lower == requester.lower()):
            remove_room(current_room_name)
            bot.send_message(room_id, f"👋 Leaving room and removing from auto-join. Bye!")
            bot.send_json({"handler": "leavechatroom", "id": uuid.uuid4().hex, "roomid": room_id})
        else:
            bot.send_message(room_id, f"🚫 @{user}, only the room requester or Master can make me leave.")
        return True

    # 4. DELETE SPECIFIC ROOM (!del roomname)
    if cmd == "del":
        if user_lower != MASTER_USER: return False
        if not args: return True
        
        # Clear All check
        if args[0].lower() == "all":
            clear_all_rooms()
            bot.send_message(room_id, "🗑️ **All saved rooms** deleted from list.")
            return True
        
        target_room = " ".join(args)
        remove_room(target_room)
        bot.send_message(room_id, f"❌ Removed **{target_room}** from saved list.")
        return True

    # 5. ROOMS LIST
    if cmd == "rooms":
        if user_lower != MASTER_USER: return False
        rooms_data = get_saved_rooms_data()
        if rooms_data:
            msg = "**📂 Saved Rooms:**\n" + "\n".join([f"- {r} (By: {u})" for r, u in rooms_data])
        else:
            msg = "📂 No rooms saved."
        bot.send_message(room_id, msg)
        return True

    return False
