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
LIST_TIMEOUT = 20  # Role list ke liye timeout thoda zyada rakhte hain.
ITEMS_PER_PAGE = 10

# --- GLOBAL CACHE & SESSIONS ---
user_cache = {}
user_cache_lock = threading.Lock()
admin_sessions = {}
sessions_lock = threading.Lock()

# --- COMMAND MAPPING ---
# Maps !banlist to the role 'outcast_list' required by the API
ROLE_LIST_MAP = {
    'banlist': 'outcast_list', 'banned': 'outcast_list',
    'adminlist': 'admins_list', 'admins': 'admins_list',
    'ownerlist': 'owners_list', 'owners': 'owners_list',
    'memberlist': 'members_list', 'members': 'members_list'
}

# --- SYSTEM MESSAGE HANDLER (For Role Lists) ---
def handle_system_message(bot, data):
    """
    Yeh function bot_engine se aane wale non-chat messages ko handle karta hai.
    Specifically, yeh 'roleslist' ka intezaar karta hai.
    """
    handler = data.get("handler")
    if handler != "roleslist":
        return

    # Check karo ki yeh list kis admin ne request ki thi.
    request_id = data.get("id")
    with sessions_lock:
        session_to_update = None
        for uid, session in admin_sessions.items():
            if session.get("request_id") == request_id:
                session_to_update = session
                break
        
        if not session_to_update:
            return # Agar session nahi milta, to kuch mat karo.

        # Session me server se aayi user list ko save kar do.
        user_list_from_server = data.get("users", [])
        session_to_update['user_list'] = user_list_from_server
        session_to_update['timestamp'] = time.time() # Timer update kar do.
        
        # Admin ko list ka pehla page dikhao.
        display_role_list(bot, session_to_update)

# --- HELPER FUNCTIONS ---
def display_role_list(bot, session):
    """Role list ko format karke chat me dikhata hai."""
    page = session['page']
    user_list = session['user_list']
    role_name = session['role_name']
    
    start_index = (page - 1) * ITEMS_PER_PAGE
    end_index = start_index + ITEMS_PER_PAGE
    
    page_list = user_list[start_index:end_index]

    if not page_list:
        bot.send_message(session['room_id'], "No more users on the next page.")
        return

    response = f"📋 {role_name.replace('_', ' ').title()} (Page {page}) - Action in {LIST_TIMEOUT}s\n"
    response += "──────────────────\n"
    for i, u_data in enumerate(page_list):
        num = start_index + i + 1
        response += f"`{num}`: @{u_data['username']}\n"
    
    total_pages = (len(user_list) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    if page < total_pages:
        response += "──────────────────\n"
        response += "Type `!n` for the next page.\n"
    
    response += "Type `remove [number]` to remove user from this role."
    bot.send_message(session['room_id'], response)

def has_permission(username, user_id):
    if username.lower() == MASTER_ADMIN.lower(): return True
    db_admins = get_all_admins()
    if user_id and str(user_id) in db_admins: return True
    return False

# --- MAIN COMMAND HANDLER ---
def handle_command(bot, command, room_id, user, args, data):
    author_username = data.get('username')
    author_userid = data.get('userid') or data.get('userID')
    if author_username and author_userid:
        with user_cache_lock:
            user_cache[author_username.lower()] = str(author_userid)

    cmd = command.lower().strip()
    user_id = user_cache.get(user.lower())
    
    # Permission check for almost all commands.
    if cmd not in ["l", "list", "n", "remove"] and not has_permission(user, user_id):
        is_session_action = cmd in SESSION_ACTION_MAP and args and args[0].isdigit()
        if not is_session_action:
             # Regular commands are checked at the start. Session actions are checked inside.
             pass # Let it pass to be checked later.

    # --- MASTER ADMIN COMMANDS (!mas, !umas) ---
    if cmd in ["mas", "umas"]:
        if user.lower() != MASTER_ADMIN.lower(): return True
        if not args: return True
        target_user = args[0]
        target_id = user_cache.get(target_user.lower())
        if not target_id:
            bot.send_message(room_id, f"⚠️ User '{target_user}' needs to type in chat first.")
            return True
        if cmd == "mas" and add_admin(target_id): bot.send_message(room_id, f"✅ @{target_user} is now a sub-admin.")
        elif cmd == "umas" and remove_admin(target_id): bot.send_message(room_id, f"✅ @{target_user} is no longer a sub-admin.")
        return True

    # --- ADMIN LIST COMMAND ---
    if cmd == "admins":
        if not has_permission(user, user_id): return True
        db_admin_ids = get_all_admins()
        id_to_name_map = {uid: name for name, uid in user_cache.items()}
        online_admins = [f"🛡️ @{id_to_name_map.get(admin_id, f'UserID: {admin_id} (Inactive)').capitalize()}" for admin_id in db_admin_ids]
        response = f"👑 **Master Admin** 👑\n└─ @{MASTER_ADMIN.capitalize()}\n\n"
        response += "🛡️ **Sub-Admins** 🛡️\n" + ("\n".join(f"└─ {name}" for name in online_admins) if online_admins else "└─ No sub-admins found.")
        bot.send_message(room_id, response)
        return True

    # --- NEW: ROLE LIST COMMANDS (!banlist, !adminlist, etc.) ---
    if cmd in ROLE_LIST_MAP:
        if not has_permission(user, user_id): return True
        
        request_id = uuid.uuid4().hex
        role_to_get = ROLE_LIST_MAP[cmd]

        with sessions_lock:
            admin_sessions[user_id] = {
                'type': 'role_list',
                'request_id': request_id,
                'user_list': [], # Yeh list server se aane par bhari jayegi
                'page': 1,
                'room_id': room_id,
                'role_name': role_to_get,
                'timestamp': time.time() # Initial timestamp
            }
        
        payload = {
            "handler": "getroles",
            "id": request_id,
            "roomid": room_id,
            "role": role_to_get
        }
        bot.send_json(payload)
        bot.send_message(room_id, f"Requesting {role_to_get.replace('_', ' ')}... Please wait.")
        return True

    # --- NEW: REMOVE FROM ROLE LIST ACTION ---
    if cmd == "remove" and args and args[0].isdigit():
        if not has_permission(user, user_id): return True
        with sessions_lock: session = admin_sessions.get(user_id)

        if not session or session.get('type') != 'role_list' or time.time() - session['timestamp'] > LIST_TIMEOUT:
            bot.send_message(room_id, "⌛ Session expired or invalid. Please request a list again.")
            return True
        
        try:
            index = int(args[0]) - 1
            target = session['user_list'][index]
            target_id = target['userid']
            target_name = target['username']
            
            # User ko role list se hatane ke liye use 'member' role de do.
            bot.send_json({"handler": "changerole", "id": uuid.uuid4().hex, "roomid": room_id, "targetid": target_id, "role": "member"})
            bot.send_message(room_id, f"✅ Removed @{target_name} from the list (set role to member).")
            with sessions_lock: del admin_sessions[user_id] # Session close kar do.
            return True
        except (ValueError, IndexError):
            bot.send_message(room_id, "Invalid number.")
            return True


    # --- SESSION-BASED ACTIONS (k 1, l, n, etc.) from the previous version ---
    # This part remains the same. The logic is separated for clarity.
    # ... (Code for !l, !n, and actions like k 1 is the same as the previous version,
    # just ensure your session type check is correct)

    return False # Return False if no command was handled
