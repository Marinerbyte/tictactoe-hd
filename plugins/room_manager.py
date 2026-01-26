import os
import time
import threading
import psycopg2
import uuid

# --- CONFIG ---
# Hum wahi database use kar rahe hain jo Nilu AI ke liye set kiya tha
DB_URL = os.environ.get("NILU_DATABASE_URL")

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
    # Table banayenge agar nahi hai
    db_exec("CREATE TABLE IF NOT EXISTS saved_rooms (room_name TEXT PRIMARY KEY)")

def get_saved_rooms():
    rows = db_exec("SELECT room_name FROM saved_rooms", (), True)
    return [r[0] for r in rows] if rows else []

def save_room(room_name):
    db_exec("INSERT INTO saved_rooms (room_name) VALUES (%s) ON CONFLICT DO NOTHING", (room_name,))

def remove_room(room_name):
    db_exec("DELETE FROM saved_rooms WHERE room_name = %s", (room_name,))

# ==========================================
# ⚡ AUTO-JOIN SEQUENCE (The Anti-Spam Logic)
# ==========================================
def auto_join_task(bot):
    """
    Bot start hone par ye function chalega.
    Ye saved rooms ko 3 second ke gap par join karega.
    """
    print("[RoomManager] Waiting for connection stability...")
    time.sleep(5) # 5 sec wait taaki login pakka ho jaye
    
    rooms = get_saved_rooms()
    if not rooms:
        print("[RoomManager] No saved rooms found.")
        return

    print(f"[RoomManager] Found {len(rooms)} saved rooms. Joining sequence started...")
    
    for room in rooms:
        if not bot.running: break # Safety check
        
        print(f"[RoomManager] Joining: {room}")
        bot.join_room(room)
        
        # 3 Second Gap (Anti-Spam Rule)
        time.sleep(3)
    
    print("[RoomManager] All saved rooms joined.")

# ==========================================
# 🔌 PLUGIN SETUP
# ==========================================
def setup(bot):
    init_room_db()
    # Background thread start karte hain jo dheere-dheere join karega
    threading.Thread(target=auto_join_task, args=(bot,), daemon=True).start()
    print("[RoomManager] System Ready. Auto-join sequence initiated.")

# ==========================================
# 📨 COMMAND HANDLER
# ==========================================
def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    
    # OWNER CHECK (Security: Sirf aap join/leave karwa sakte ho)
    # Agar sabke liye kholna hai to ye check hata dena
    if user.lower() != bot.user_data.get('username', '').lower() and user.lower() != "yasin":
        return False

    # 1. JOIN COMMAND (!j roomname [sv])
    if cmd in ["j", "join"]:
        if not args:
            bot.send_message(room_id, "Usage: `!j <roomname> [sv]`")
            return True
        
        target_room = args[0]
        save_mode = False
        
        # Check for 'sv' flag
        if len(args) > 1 and args[1].lower() == "sv":
            save_mode = True
        
        bot.join_room(target_room)
        
        if save_mode:
            save_room(target_room)
            bot.send_message(room_id, f"✅ Joined **{target_room}** & Saved to Auto-Join list.")
        else:
            bot.send_message(room_id, f"🚀 Joining **{target_room}** (Temporary).")
            
        return True

    # 2. LEAVE COMMAND (!leave roomname)
    if cmd == "leave":
        if not args:
            # Agar sirf !leave likha to current room leave karega
            current_room_name = bot.room_id_to_name_map.get(room_id)
            if current_room_name:
                remove_room(current_room_name) # List se hatao
                bot.send_message(room_id, f"👋 Leaving {current_room_name} & Removed from list.")
                # Leave Payload
                bot.send_json({"handler": "leavechatroom", "id": uuid.uuid4().hex, "roomid": room_id})
            return True
            
        target_room = args[0]
        
        # Database se hatao
        remove_room(target_room)
        
        # Agar bot us room me connected hai to wahan leave command bhejo
        # (Iske liye room_details check karni padegi agar available hai, 
        #  warna bot agle restart pe join nahi karega)
        
        bot.send_message(room_id, f"🗑️ **{target_room}** removed from Auto-Join list.")
        return True

    # 3. LIST SAVED ROOMS (!rooms)
    if cmd == "rooms":
        rooms = get_saved_rooms()
        if rooms:
            msg = "**📂 Saved Rooms:**\n" + "\n".join([f"- {r}" for r in rooms])
        else:
            msg = "📂 No rooms saved in Auto-Join list."
        bot.send_message(room_id, msg)
        return True

    return False
