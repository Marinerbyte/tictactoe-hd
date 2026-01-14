import uuid
import threading
import time
import sys
import os

# --- DB (Permissions) ---
try:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    # Assume db.py has these functions: add_admin, remove_admin, get_all_admins
    # from db import add_admin, remove_admin, get_all_admins
except Exception as e:
    print(f"[Admin Plugin] DB Import Error: {e}")

# --- CONFIG ---
MASTER_ADMIN = "yasin"
ACTION_TIMEOUT = 10 # Seconds to wait for user list

# --- GLOBAL STATE ---
pending_actions = {} # Stores actions waiting for a user list
actions_lock = threading.Lock()

# --- PERMISSION CHECK ---
def has_permission(username):
    # db_admins = get_all_admins()
    # For now, only master admin
    return username.lower() == MASTER_ADMIN.lower()

# --- SYSTEM MESSAGE HANDLER (CRITICAL) ---
def handle_system_message(bot, data):
    """This function is called by bot_engine when a non-chat message arrives."""
    handler = data.get("handler")
    request_id = data.get("id")

    if handler == "userslist" and request_id in pending_actions:
        with actions_lock:
            action_data = pending_actions.pop(request_id)
        
        target_username = action_data['target_username']
        action_to_perform = action_data['action']
        room_id = action_data['room_id']

        # 1. Find the User ID from the received list
        target_user_id = None
        for user_obj in data.get("users", []):
            if user_obj.get('username', '').lower() == target_username.lower():
                target_user_id = user_obj.get('userid')
                break

        if not target_user_id:
            bot.send_message(room_id, f"⚠️ Action failed. User '@{target_username}' not found.")
            return

        # 2. Prepare the final payload with the correct ID
        payload = {
            "id": uuid.uuid4().hex,
            "roomid": room_id,
            "to": target_user_id
        }

        if action_to_perform == 'ban':
            payload['handler'] = 'changerole'
            payload['targetid'] = target_user_id
            payload['role'] = 'outcast'
            del payload['to']
        else:
            payload['handler'] = f"{action_to_perform}user"

        # 3. Send the command
        bot.send_json(payload)
        bot.send_message(room_id, f"✅ Action `{action_to_perform}` performed on @{target_username}.")

# --- MAIN COMMAND HANDLER ---
def handle_command(bot, command, room_id, user, args, data):
    if not has_permission(user):
        return False

    cmd = command.lower().strip()
    
    action_map = {
        'k': 'kick', 'kick': 'kick', 'b': 'ban', 'ban': 'ban',
        'm': 'mute', 'mute': 'mute', 'um': 'unmute', 'unmute': 'unmute'
    }

    if cmd in action_map:
        if not args:
            bot.send_message(room_id, f"Usage: `!{cmd} [username]`")
            return True

        target_username = args[0]
        action = action_map[cmd]
        
        # 1. Send a request to get the user list
        request_id = uuid.uuid4().hex
        bot.send_json({
            "handler": "getusers",
            "id": request_id,
            "roomid": room_id
        })

        # 2. Store the pending action
        with actions_lock:
            pending_actions[request_id] = {
                "target_username": target_username,
                "action": action,
                "room_id": room_id,
                "timestamp": time.time()
            }
        
        bot.send_message(room_id, f"🔍 Finding user '@{target_username}'...")
        
        # Optional: Timeout cleanup for pending actions
        # (A separate thread could clean actions older than ACTION_TIMEOUT)
        
        return True

    return False
