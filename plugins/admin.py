import uuid
import threading
import time
import sys
import os

# --- DB IMPORTS ---
try:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from db import add_admin, remove_admin, get_all_admins
except Exception as e:
    print(f"[Admin Plugin] DB Import Error: {e}")

# --- CONFIG ---
# Ye 'GOD' user hai. Ise koi touch nahi kar sakta.
SUPER_OWNER = "yasin" 

# --- GLOBAL STATE ---
pending_room_actions = {} 
action_lock = threading.Lock()

# --- PERMISSION CHECK ---
def is_admin(bot, user_id, username):
    """Admin check: Super Owner OR Database Admin"""
    # 1. Check Super Owner
    if username and username.lower() == SUPER_OWNER.lower():
        return True
    
    # 2. Check Database (ID se)
    if user_id:
        db_admins = get_all_admins() # db.py se list aayegi
        if str(user_id) in db_admins:
            return True
    
    return False

# --- SYSTEM MESSAGE HANDLER (The Engine) ---
def handle_system_message(bot, data):
    handler = data.get("handler")
    
    # Jab server users ki list bhejta hai
    if handler in ["activeoccupants", "userslist"]:
        room_id = str(data.get("roomid"))
        
        with action_lock:
            # Agar is room ke liye koi action pending nahi hai to return
            if room_id not in pending_room_actions:
                return 
            action_data = pending_room_actions.pop(room_id)
        
        target_name = action_data['target_clean']
        action_type = action_data['action']
        requester_room = action_data['room_id']
        
        # List me Target ko dhoondo
        users_list = data.get("users", [])
        target_user_id = None
        target_real_name = target_name 
        
        for u in users_list:
            if u.get('username', '').lower() == target_name:
                target_user_id = str(u.get('userid') or u.get('id'))
                target_real_name = u.get('username')
                break
        
        # Agar user room me nahi mila
        if not target_user_id:
            bot.send_message(requester_room, f"⚠️ User @{target_name} is room me nahi dikh raha.")
            return

        # --- SAFETY CHECK (NEW) ---
        # Owner ya Bot ko kick/ban hone se bachana
        if target_real_name.lower() == SUPER_OWNER.lower() or target_real_name == bot.user_data.get('username'):
            bot.send_message(requester_room, "🛡️ **Security Alert:** Main Owner ya khud ko Kick/Ban nahi kar sakta!")
            return

        # --- DATABASE ACTIONS ---
        req_id = uuid.uuid4().hex
        
        if action_type == 'mas':
            if add_admin(target_user_id):
                bot.send_message(requester_room, f"✅ **@{target_real_name}** ab Permanent Admin hai (DB Saved).")
            else:
                bot.send_message(requester_room, f"⚠️ **@{target_real_name}** pehle se Admin hai.")

        elif action_type == 'rmas':
            if remove_admin(target_user_id):
                bot.send_message(requester_room, f"🗑️ **@{target_real_name}** ko Admin list se hata diya.")
            else:
                bot.send_message(requester_room, f"⚠️ **@{target_real_name}** Admin list me nahi tha.")

        # --- MODERATION ACTIONS ---
        elif action_type == 'kick':
            bot.send_json({"handler": "kickuser", "id": req_id, "roomid": room_id, "to": target_user_id})
            bot.send_message(requester_room, f"👞 Kicking @{target_real_name}...")
            
        elif action_type == 'ban':
            # Role: Outcast (Blacklist)
            bot.send_json({"handler": "changerole", "id": req_id, "roomid": room_id, "targetid": target_user_id, "role": "outcast"})
            bot.send_message(requester_room, f"🔨 Banning @{target_real_name} (Role: Outcast)...")
            
        elif action_type == 'unban':
            # Role: Member (Wapas normal karna)
            bot.send_json({"handler": "changerole", "id": req_id, "roomid": room_id, "targetid": target_user_id, "role": "member"})
            bot.send_message(requester_room, f"🕊️ Unbanning @{target_real_name} (Role: Member)...")

        elif action_type == 'mute':
            bot.send_json({"handler": "muteuser", "id": req_id, "roomid": room_id, "to": target_user_id})
            bot.send_message(requester_room, f"🤐 Muted @{target_real_name}.")

        elif action_type == 'unmute':
            bot.send_json({"handler": "unmuteuser", "id": req_id, "roomid": room_id, "to": target_user_id})
            bot.send_message(requester_room, f"🔊 Unmuted @{target_real_name}.")

# --- MAIN COMMAND HANDLER ---
def handle_command(bot, command, room_id, user, args, data):
    
    user_id = data.get('userid', data.get('id'))
    
    # 1. PERMISSION CHECK
    if not is_admin(bot, user_id, user):
        return False

    cmd = command.lower().strip()
    
    # --- 2. INVITE COMMAND (Direct) ---
    if cmd in ['i', 'invite']:
        if not args:
            bot.send_message(room_id, "Usage: `!i @username`")
            return True
        
        target = args[0].replace("@", "").strip()
        bot.send_json({
            "handler": "chatroominvite",
            "id": uuid.uuid4().hex,
            "roomid": room_id,
            "to": target 
        })
        bot.send_message(room_id, f"📨 Invited: @{target}")
        return True

    # --- 3. COMMANDS JO ID MAANGTE HAIN ---
    valid_cmds = {
        'mas': 'mas',          # Add DB Admin
        'rmas': 'rmas',        # Remove DB Admin
        'k': 'kick', 'kick': 'kick', 
        'b': 'ban', 'ban': 'ban',
        'ub': 'unban', 'unban': 'unban', # New Command
        'm': 'mute', 'mute': 'mute', 
        'um': 'unmute', 'unmute': 'unmute'
    }

    if cmd in valid_cmds:
        if not args:
            bot.send_message(room_id, f"Usage: !{cmd} @username")
            return True

        target_clean = args[0].replace("@", "").lower().strip()
        action = valid_cmds[cmd]
        
        # Step 1: User List Request
        bot.send_json({
            "handler": "getusers",
            "id": uuid.uuid4().hex,
            "roomid": room_id
        })

        # Step 2: Store Pending Action
        with action_lock:
            pending_room_actions[str(room_id)] = {
                "target_clean": target_clean,
                "action": action,
                "room_id": room_id,
                "timestamp": time.time()
            }
        return True

    return False
