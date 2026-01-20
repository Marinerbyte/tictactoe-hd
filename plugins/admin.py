import sys
import os

# --- IMPORTS ---
try:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from db import add_admin, remove_admin, get_all_admins
except Exception as e: print(f"DB Error: {e}")

# 🔥 CONFIGURATION
SECRET_PASSWORD = "admin123"  # Backup ke liye
OWNER_USERNAME = "yasin"      # Aapka naam

def setup(bot):
    print("[Admin System] Stealth Mode Loaded.")

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    user_id = data.get('userid', user)

    # 1. CLAIM ADMIN (!op) - HIDDEN
    if cmd == "op":
        # Agar user "yasin" hai
        if user.lower() == OWNER_USERNAME.lower():
            # Chup-chap database me add kar do
            add_admin(user_id)
            # Return True taaki command yahi khatam ho jaye,
            # aur bot koi message send na kare.
            return True

        # Agar koi aur password try kare (Optional)
        if args and args[0] == SECRET_PASSWORD:
            add_admin(user_id)
            return True # Inke liye bhi silence rakha hai
            
        return False

    # 2. MANAGE ADMINS (!admin add @user)
    if cmd == "admin":
        # Power Check
        current_admins = get_all_admins()
        is_owner = (user.lower() == OWNER_USERNAME.lower())
        is_db_admin = (str(user_id) in current_admins)
        
        # Agar power nahi hai, to ignore karo (No message = Stealth)
        if not (is_owner or is_db_admin):
            return False

        if len(args) < 2:
            bot.send_message(room_id, "Usage: `!admin add @user` or `!admin remove @user`")
            return True

        action = args[0].lower()
        target_name = args[1].replace("@", "")
        
        target_id = None
        if room_id in bot.room_details:
            target_id = bot.room_details[room_id]['id_map'].get(target_name.lower())
        
        if not target_id:
            bot.send_message(room_id, f"❌ User @{target_name} not found.")
            return True

        if action == "add":
            if add_admin(target_id):
                bot.send_message(room_id, f"✅ @{target_name} added to Admins.")
            else:
                bot.send_message(room_id, "⚠️ Already Admin.")
                
        elif action in ["remove", "del"]:
            if target_name.lower() == OWNER_USERNAME.lower():
                bot.send_message(room_id, "❌ Cannot remove Owner.")
                return True
            if remove_admin(target_id):
                bot.send_message(room_id, f"🗑️ @{target_name} removed.")
            else:
                bot.send_message(room_id, "⚠️ Failed.")
        
        elif action == "list":
             bot.send_message(room_id, f"👮 Admins Count: {len(current_admins)}")

        return True

    return False
