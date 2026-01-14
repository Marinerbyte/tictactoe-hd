import uuid
import threading
import time
import sys
import os

# --- DB IMPORT ---
try:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from db import add_admin, remove_admin, get_all_admins
except Exception as e:
    print(f"[Admin Plugin] DB Import Error: {e}")

# --- CONFIGURATION ---
MASTER_ADMIN = "yasin"
LIST_TIMEOUT = 15
ITEMS_PER_PAGE = 10

# --- GLOBAL STATE & MAPPINGS ---
admin_sessions = {}
sessions_lock = threading.Lock()

ROLE_LIST_MAP = {'banlist': 'outcast_list', 'banned': 'outcast_list', 'adminlist': 'admins_list', 'ownerlist': 'owners_list', 'memberlist': 'members_list'}
ACTION_MAP = {
    'k': 'kick', 'kick': 'kick', 'b': 'outcast', 'ban': 'outcast', 'm': 'member', 'member': 'member',
    'mu': 'mute', 'mute': 'mute', 'um': 'unmute', 'unmute': 'unmute', 'o': 'owner', 'owner': 'owner',
    'a': 'admin', 'admin': 'admin', 'i': 'invite', 'invite': 'invite'
}
ROLE_ACTIONS = ['outcast', 'member', 'owner', 'admin']

# --- SYSTEM MESSAGE HANDLER ---
def handle_system_message(bot, data):
    if data.get("handler") != "roleslist": return
    request_id = data.get("id")
    with sessions_lock:
        session = next((s for s in admin_sessions.values() if s.get("request_id") == request_id), None)
        if not session: return
        session['user_list'] = data.get("users", [])
        session['timestamp'] = time.time()
        display_list(bot, session)

# --- HELPER FUNCTIONS ---
def display_list(bot, session):
    list_type, page, user_list = session['type'], session['page'], session['user_list']
    title = "Room User List" if list_type == 'user_list' else session['role_name'].replace('_', ' ').title()
    prompt = "Type `[action] [num]` (e.g., k 1)" if list_type == 'user_list' else "Type `remove [num]`"
    start_index = (page - 1) * ITEMS_PER_PAGE
    page_list = user_list[start_index : start_index + ITEMS_PER_PAGE]
    if not page_list:
        bot.send_message(session['room_id'], "No more users on this page.")
        return
    response = f"📋 {title} (Page {page}) - Actions for {LIST_TIMEOUT}s\n" + "─" * 22 + "\n"
    for i, u_data in enumerate(page_list):
        response += f"`{start_index + i + 1}`: @{u_data.get('username', 'Unknown')}\n"
    total_pages = (len(user_list) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    if page < total_pages: response += "─" * 22 + "\nType `!n` for the next page.\n"
    response += prompt
    bot.send_message(session['room_id'], response)

def has_permission(username, user_id, bot):
    # User cache is only used here to get the ID for permission check, not for actions.
    if username.lower() == MASTER_ADMIN.lower(): return True
    
    # We need to get the user_id if it's not available
    current_user_id = None
    with bot.plugins.plugins.get('admin').user_cache_lock:
        current_user_id = bot.plugins.plugins.get('admin').user_cache.get(username.lower())

    db_admins = get_all_admins()
    return current_user_id and str(current_user_id) in db_admins

def perform_action(bot, room_id, target_name):
    """
    ULTIMATE FIX: This function now ONLY uses username for ALL actions.
    No more dependency on user_cache for actions.
    """
    # This is a dummy function now, the logic is handled directly in the command handler
    # to make it clearer and less error-prone.
    pass

# --- MAIN COMMAND HANDLER ---
def handle_command(bot, command, room_id, user, args, data):
    # User cache is still useful for permission checks and getting user IDs when needed,
    # but actions will not depend on it.
    author_username, author_userid = data.get('username'), data.get('userid') or data.get('userID')
    if author_username and author_userid:
        # Lazy load user_cache if not present
        if not hasattr(sys.modules[__name__], 'user_cache'):
            setattr(sys.modules[__name__], 'user_cache', {})
            setattr(sys.modules[__name__], 'user_cache_lock', threading.Lock())
        
        with sys.modules[__name__].user_cache_lock:
            sys.modules[__name__].user_cache[author_username.lower()] = str(author_userid)

    cmd = command.lower().strip()
    
    # We need user_id for permission check
    user_id = None
    if hasattr(sys.modules[__name__], 'user_cache_lock'):
        with sys.modules[__name__].user_cache_lock:
            user_id = sys.modules[__name__].user_cache.get(user.lower())

    if cmd in ["mas", "umas"]:
        if user.lower() != MASTER_ADMIN.lower(): return True
        if not args: return True
        target_user = args[0]
        target_id_to_add = None
        if hasattr(sys.modules[__name__], 'user_cache_lock'):
             with sys.modules[__name__].user_cache_lock:
                target_id_to_add = sys.modules[__name__].user_cache.get(target_user.lower())
        
        if not target_id_to_add:
            bot.send_message(room_id, f"⚠️ User '{target_user}' needs to type in chat first for me to learn their ID.")
            return True
        if cmd == "mas": add_admin(target_id_to_add) and bot.send_message(room_id, f"✅ @{target_user} is now a sub-admin.")
        else: remove_admin(target_id_to_add) and bot.send_message(room_id, f"✅ @{target_user} is no longer a sub-admin.")
        return True

    # Pass the bot instance to the permission function
    if not has_permission(user, user_id, bot): return False

    if cmd in ACTION_MAP and args:
        target_user = args[0]
        action = ACTION_MAP[cmd]
        
        payload = {
            "id": uuid.uuid4().hex,
            "roomid": room_id,
        }
        
        # THE REAL FIX: Set the correct target key based on the action
        if action in ROLE_ACTIONS:
            payload["handler"] = "changerole"
            payload["target"] = target_user
            payload["role"] = action
        elif action == 'kick':
            payload["handler"] = "kickuser"
            payload["tousername"] = target_user # Using username
        elif action == 'mute':
            payload["handler"] = "muteuser"
            payload["tousername"] = target_user # Using username
        elif action == 'unmute':
            payload["handler"] = "unmuteuser"
            payload["tousername"] = target_user # Using username
        elif action == 'invite':
            payload["handler"] = "chatroominvite"
            payload["to"] = target_user # Using username
            
        bot.send_json(payload)
        bot.send_message(room_id, f"✅ Action `{action}` sent for @{target_user}.")
        return True

    # Handle list-based actions
    with sessions_lock: session = admin_sessions.get(user_id)
    if session and time.time() - session['timestamp'] < LIST_TIMEOUT:
        if cmd == 'n':
            session['page'] += 1
            session['timestamp'] = time.time()
            display_list(bot, session)
            return True

        if args and args[0].isdigit():
            index = int(args[0]) - 1
            if 0 <= index < len(session['user_list']):
                target_user_info = session['user_list'][index]
                target_name = target_user_info['username']
                action_to_perform = None

                if session['type'] == 'user_list' and cmd in ACTION_MAP:
                    action_to_perform = ACTION_MAP[cmd]
                elif session['type'] == 'role_list' and cmd == 'remove':
                    action_to_perform = 'member'

                if action_to_perform:
                    # Reuse the same logic as direct commands
                    direct_action_cmd = action_to_perform
                    direct_action_payload = {
                        "id": uuid.uuid4().hex,
                        "roomid": room_id,
                    }
                    if direct_action_cmd in ROLE_ACTIONS:
                        direct_action_payload["handler"] = "changerole"
                        direct_action_payload["target"] = target_name
                        direct_action_payload["role"] = direct_action_cmd
                    else: # kick, mute, etc.
                        direct_action_payload["handler"] = f"{direct_action_cmd}user"
                        direct_action_payload["tousername"] = target_name

                    bot.send_json(direct_action_payload)
                    bot.send_message(room_id, f"✅ Action `{action_to_perform}` sent for @{target_name}.")
                    del admin_sessions[user_id]
                return True

    # Handle list creation
    if cmd in ["l", "list"]:
        current_users = bot.room_details.get(room_id, {}).get('users', [])
        # ... (list creation logic remains the same)
        return True

    return False
