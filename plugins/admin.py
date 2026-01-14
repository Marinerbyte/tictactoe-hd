import uuid
import threading
import time
import sys
import os

# --- DB IMPORT ---
try:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    # NOTE: add_admin, remove_admin, get_all_admins needs to be created in db.py
    # For now, we will use a simple permission check.
except Exception as e:
    print(f"[Admin Plugin] DB Import Error: {e}")

# --- CONFIGURATION ---
MASTER_ADMIN = "yasin" # Case-insensitive

# --- PERMISSION CHECK ---
def has_permission(username):
    # For now, only the master admin has permission.
    # Later, you can add your DB check here: `if get_all_admins()...`
    return username.lower() == MASTER_ADMIN.lower()

# --- HELPER: Find User ID from Bot's Memory ---
def get_user_id_by_name(bot, room_id, username):
    """Finds a user's ID from the live user list in bot_engine."""
    room_data = bot.room_details.get(room_id)
    if not room_data or not room_data.get('users_full'):
        return None
    
    # Search in the full user data list
    for user_obj in room_data['users_full']:
        if user_obj.get('username', '').lower() == username.lower():
            return user_obj.get('userid')
    return None

# --- MAIN COMMAND HANDLER ---
def handle_command(bot, command, room_id, user, args, data):
    # Only admins can use this plugin
    if not has_permission(user):
        return False

    cmd = command.lower().strip()
    
    # --- Action Commands (kick, ban, mute, etc.) ---
    if cmd in ['k', 'kick', 'b', 'ban', 'm', 'mute', 'um', 'unmute']:
        if not args:
            bot.send_message(room_id, f"Usage: `!{cmd} [username]`")
            return True

        target_username = args[0]
        
        # 1. Find the User ID from the bot's live data
        target_user_id = get_user_id_by_name(bot, room_id, target_username)

        if not target_user_id:
            bot.send_message(room_id, f"⚠️ User '@{target_username}' not found in this room.")
            return True

        # 2. Prepare the correct payload
        action_map = {
            'k': 'kick', 'kick': 'kick', 'b': 'ban', 'ban': 'ban',
            'm': 'mute', 'mute': 'mute', 'um': 'unmute', 'unmute': 'unmute'
        }
        action = action_map[cmd]
        
        payload = {
            "id": uuid.uuid4().hex,
            "roomid": room_id,
            "to": target_user_id  # <-- THE CRITICAL FIX: USE 'to' WITH THE NUMERIC ID
        }

        if action == 'ban':
            # Ban is a role change to 'outcast'
            payload['handler'] = 'changerole'
            payload['targetid'] = target_user_id
            payload['role'] = 'outcast'
            del payload['to'] # Not needed for changerole
        else:
            payload['handler'] = f"{action}user"

        # 3. Send the command
        bot.send_json(payload)
        bot.send_message(room_id, f"✅ Action `{action}` performed on @{target_username}.")
        return True

    return False
