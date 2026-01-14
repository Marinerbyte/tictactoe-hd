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

# --- SYSTEM MESSAGE HANDLER (For Role Lists) ---
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
        username = u_data.get('username', 'Unknown')
        response += f"`{start_index + i + 1}`: @{username}\n"
    
    total_pages = (len(user_list) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    if page < total_pages: response += "─" * 22 + "\nType `!n` for the next page.\n"
    response += prompt
    bot.send_message(session['room_id'], response)

def has_permission(username, user_id):
    if username.lower() == MASTER_ADMIN.lower(): return True
    db_admins = get_all_admins()
    return user_id and str(user_id) in db_admins

def perform_action(bot, room_id, target_id, target_name, action):
    if not target_id: return
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

    if cmd in ["mas", "umas"]:
        if user.lower() != MASTER_ADMIN.lower(): return True
        if not args: return True
        target_user = args[0]
        target_id = user_cache.get(target_user.lower())
        if not target_id:
            bot.send_message(room_id, f"⚠️ User '{target_user}' needs to type in chat first.")
            return True
        if cmd == "mas": add_admin(target_id) and bot.send_message(room_id, f"✅ @{target_user} is now a sub-admin.")
        else: remove_admin(target_id) and bot.send_message(room_id, f"✅ @{target_user} is no longer a sub-admin.")
        return True

    if not has_permission(user, user_id): return False

    if cmd == "admins":
        db_admin_ids = get_all_admins()
        id_to_name_map = {uid: name.capitalize() for name, uid in user_cache.items()}
        admin_names = [f"🛡️ @{id_to_name_map.get(admin_id, f'UserID: {admin_id}')}" for admin_id in db_admin_ids]
        response = f"👑 **Master Admin** 👑\n└─ @{MASTER_ADMIN.capitalize()}\n\n"
        response += "🛡️ **Sub-Admins** 🛡️\n" + ("\n".join(f"└─ {name}" for name in admin_names) if admin_names else "└─ No sub-admins.")
        bot.send_message(room_id, response)
        return True

    if cmd in ["l", "list"]:
        current_users = bot.room_details.get(room_id, {}).get('users', [])
        search_term = args[0].lower() if args else None
        filtered_list = [{'username': u_name, 'user_id': user_cache.get(u_name.lower())} for u_name in current_users if user_cache.get(u_name.lower()) and (not search_term or u_name.lower().startswith(search_term))]
        if not filtered_list:
            bot.send_message(room_id, "No matching users found.")
            return True
        with sessions_lock:
            admin_sessions[user_id] = {'type': 'user_list', 'user_list': filtered_list, 'page': 1, 'room_id': room_id, 'timestamp': time.time()}
            display_list(bot, admin_sessions[user_id])
        return True

    if cmd in ROLE_LIST_MAP:
        request_id, role_to_get = uuid.uuid4().hex, ROLE_LIST_MAP[cmd]
        with sessions_lock:
            admin_sessions[user_id] = {'type': 'role_list', 'request_id': request_id, 'user_list': [], 'page': 1, 'room_id': room_id, 'role_name': role_to_get, 'timestamp': time.time()}
        bot.send_json({"handler": "getroles", "id": request_id, "roomid": room_id, "role": role_to_get})
        bot.send_message(room_id, f"Requesting {role_to_get.replace('_', ' ')}... Please wait.")
        return True

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
                target = session['user_list'][index]
                target_name, target_id = target['username'], target.get('user_id') or target.get('userid')
                
                if session['type'] == 'user_list' and cmd in ACTION_MAP:
                    perform_action(bot, room_id, target_id, target_name, ACTION_MAP[cmd])
                elif session['type'] == 'role_list' and cmd == 'remove':
                    perform_action(bot, room_id, target_id, target_name, 'member')
                
                del admin_sessions[user_id]
                return True

    if cmd in ACTION_MAP and args:
        target_user = args[0]
        target_id = user_cache.get(target_user.lower())
        if not target_id:
            bot.send_message(room_id, f"⚠️ User '{target_user}' not found or hasn't spoken yet.")
            return True
        perform_action(bot, room_id, target_id, target_user, ACTION_MAP[cmd])
        return True

    return False
