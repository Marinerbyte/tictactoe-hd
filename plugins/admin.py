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
    print(f"Admin DB Import Error: {e}")

# --- CONFIGURATION ---
MASTER_ADMIN = "yasin"
LIST_TIMEOUT = 15  # Timeout set to 15 seconds as requested
ITEMS_PER_PAGE = 10

# --- GLOBAL STATE ---
user_cache = {}
user_cache_lock = threading.Lock()
admin_sessions = {}
sessions_lock = threading.Lock()

# --- MAPPINGS ---
ROLE_LIST_MAP = {
    'banlist': 'outcast_list', 'banned': 'outcast_list', 'adminlist': 'admins_list',
    'ownerlist': 'owners_list', 'memberlist': 'members_list'
}
ACTION_MAP = {
    'k': 'kick', 'kick': 'kick', 'b': 'outcast', 'ban': 'outcast',
    'm': 'member', 'member': 'member', 'mu': 'mute', 'mute': 'mute',
    'um': 'unmute', 'unmute': 'unmute', 'o': 'owner', 'owner': 'owner',
    'a': 'admin', 'admin': 'admin', 'i': 'invite', 'invite': 'invite'
}
ROLE_ACTIONS = ['outcast', 'member', 'owner', 'admin']

# --- SYSTEM MESSAGE HANDLER (For !banlist, etc.) ---
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
    """Universal function to display any kind of list (role or user)."""
    list_type = session['type']
    page = session['page']
    user_list = session['user_list']
    
    title = ""
    action_prompt = ""
    if list_type == 'role_list':
        title = session['role_name'].replace('_', ' ').title()
        action_prompt = "Type `remove [number]` to remove from role."
    elif list_type == 'user_list':
        title = "Room User List"
        action_prompt = "Type `[action] [number]` (e.g., k 1)."

    start_index = (page - 1) * ITEMS_PER_PAGE
    page_list = user_list[start_index : start_index + ITEMS_PER_PAGE]
    if not page_list:
        bot.send_message(session['room_id'], "No more users on this page.")
        return

    response = f"📋 {title} (Page {page}) - Actions for {LIST_TIMEOUT}s\n" + "─" * 22 + "\n"
    for i, u_data in enumerate(page_list):
        # user_list from !l has 'user_id' key, from roles it has 'userid'
        username = u_data.get('username', 'Unknown')
        response += f"`{start_index + i + 1}`: @{username}\n"
    
    total_pages = (len(user_list) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    if page < total_pages: response += "─" * 22 + "\nType `!n` for the next page.\n"
    response += action_prompt
    bot.send_message(session['room_id'], response)

def has_permission(username, user_id):
    if username.lower() == MASTER_ADMIN.lower(): return True
    db_admins = get_all_admins()
    return user_id and str(user_id) in db_admins

def perform_action(bot, room_id, target_id, target_name, action):
    # This is a central function to avoid repeating code.
    if action == 'kick': bot.send_json({"handler": "kickuser", "id": uuid.uuid4().hex, "roomid": room_id, "to": target_id})
    elif action == 'mute': bot.send_json({"handler": "muteuser", "id": uuid.uuid4().hex, "roomid": room_id, "to": target_id})
    elif action == 'unmute': bot.send_json({"handler": "unmuteuser", "id": uuid.uuid4().hex, "roomid": room_id, "to": target_id})
    elif action == 'invite': bot.send_json({"handler": "chatroominvite", "id": uuid.uuid4().hex, "roomid": room_id, "userid": target_id})
    elif action in ROLE_ACTIONS: bot.send_json({"handler": "changerole", "id": uuid.uuid4().hex, "roomid": room_id, "targetid": target_id, "role": action})
    bot.send_message(room_id, f"✅ Action `{action}` performed on @{target_name}.")

# --- MAIN COMMAND HANDLER ---
def handle_command(bot, command, room_id, user, args, data):
    author_username, author_userid = data.get('username'), data.get('userid') or data.get('userID')
    if author_username and author_userid:
        with user_cache_lock: user_cache[author_username.lower()] = str(author_userid)

    cmd = command.lower().strip()
    user_id = user_cache.get(user.lower())

    # Master Admin commands are checked first as they are special.
    if cmd in ["mas", "umas"]:
        if user.lower() != MASTER_ADMIN.lower(): return True
        # ... (Master admin logic is the same)
        return True

    # Check permission for all other commands.
    if not has_permission(user, user_id): return False

    # --- LIST-BASED COMMANDS & ACTIONS ---
    # General User List (!l, !list)
    if cmd in ["l", "list"]:
        current_users = bot.room_details.get(room_id, {}).get('users', [])
        search_term = args[0].lower() if args else None
        
        filtered_list = []
        for u_name in current_users:
            u_id = user_cache.get(u_name.lower())
            if u_id and (not search_term or u_name.lower().startswith(search_term)):
                filtered_list.append({'username': u_name, 'user_id': u_id})

        if not filtered_list:
            bot.send_message(room_id, "No matching users found in the room.")
            return True

        with sessions_lock:
            admin_sessions[user_id] = {'type': 'user_list', 'user_list': filtered_list, 'page': 1, 'room_id': room_id, 'timestamp': time.time()}
            display_list(bot, admin_sessions[user_id])
        return True

    # Role-based Lists (!banlist, etc.)
    if cmd in ROLE_LIST_MAP:
        request_id, role_to_get = uuid.uuid4().hex, ROLE_LIST_MAP[cmd]
        with sessions_lock:
            admin_sessions[user_id] = {'type': 'role_list', 'request_id': request_id, 'user_list': [], 'page': 1, 'room_id': room_id, 'role_name': role_to_get, 'timestamp': time.time()}
        bot.send_json({"handler": "getroles", "id": request_id, "roomid": room_id, "role": role_to_get})
        bot.send_message(room_id, f"Requesting {role_to_get.replace('_', ' ')}... Please wait.")
        return True

    # Actions on Active Lists (!n, remove 1, k 1, etc.)
    with sessions_lock: session = admin_sessions.get(user_id)
    if session and time.time() - session['timestamp'] < LIST_TIMEOUT:
        # Pagination
        if cmd == 'n':
            session['page'] += 1
            session['timestamp'] = time.time() # Reset timer
            display_list(bot, session)
            return True

        # Action by number
        if args and args[0].isdigit():
            index = int(args[0]) - 1
            if 0 <= index < len(session['user_list']):
                target = session['user_list'][index]
                target_name = target['username']
                # Get the correct user ID key
                target_id = target.get('user_id') or target.get('userid')

                # Action for Role Lists (!banlist -> remove 1)
                if cmd == "remove" and session['type'] == 'role_list':
                    perform_action(bot, room_id, target_id, target_name, 'member')
                    with sessions_lock: del admin_sessions[user_id]
                    return True
                
                # Action for User Lists (!l -> k 1)
                elif cmd in ACTION_MAP and session['type'] == 'user_list':
                    perform_action(bot, room_id, target_id, target_name, ACTION_MAP[cmd])
                    with sessions_lock: del admin_sessions[user_id]
                    return True

    # --- DIRECT COMMANDS (!kick username) ---
    if cmd in ACTION_MAP and args:
        target_user, target_id = args[0], user_cache.get(args[0].lower())
        if not target_id:
            bot.send_message(room_id, f"⚠️ User '{target_user}' not found or hasn't spoken yet.")
            return True
        perform_action(bot, room_id, target_id, target_user, ACTION_MAP[cmd])
        return True
    
    # Admin List command is separate as it doesn't create a session
    if cmd == "admins":
        # ... (admin list logic is the same)
        return True

    return False
