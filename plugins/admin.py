import uuid
import sys
import os

# --- DB IMPORTS ---
try:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from db import add_admin, remove_admin, get_all_admins
except: pass

SUPER_OWNER = "yasin" 

def is_admin(bot, user_id, username):
    if username and username.lower() == SUPER_OWNER.lower(): return True
    if user_id and str(user_id) in get_all_admins(): return True
    return False

def handle_command(bot, command, room_id, user, args, data):
    user_id = data.get('userid', data.get('id'))
    
    if not is_admin(bot, user_id, user): return False

    cmd = command.lower().strip()
    
    # --- HELPER: FIND ID FROM MEMORY (FAST) ---
    def get_target_id(target_name):
        target_clean = target_name.replace("@", "").lower().strip()
        # Bot ki memory check karo (room_id_to_name map se name nikalo)
        r_name = bot.room_id_to_name_map.get(str(room_id))
        
        if r_name and r_name in bot.room_details:
            # Direct Dictionary Lookup! No Waiting!
            id_map = bot.room_details[r_name].get('id_map', {})
            return id_map.get(target_clean)
        return None

    # --- COMMANDS ---
    
    # 1. INVITE
    if cmd in ['i', 'invite']:
        if not args: return True
        target = args[0].replace("@", "").strip()
        bot.send_json({"handler": "chatroominvite", "id": uuid.uuid4().hex, "roomid": room_id, "to": target})
        bot.send_message(room_id, f"📨 Invited @{target}")
        return True

    # 2. MASTER ADMIN (DB)
    if cmd == 'mas':
        if not args: return True
        tid = get_target_id(args[0])
        if tid:
            if add_admin(tid): bot.send_message(room_id, f"✅ Added Admin: {args[0]}")
            else: bot.send_message(room_id, "⚠️ Already Admin.")
        else:
            bot.send_message(room_id, "❌ User nahi mila (List update ho rahi hai, dobara try karo).")
            bot.send_json({"handler": "getusers", "id": uuid.uuid4().hex, "roomid": room_id}) # Fallback refresh
        return True

    if cmd == 'rmas':
        if not args: return True
        tid = get_target_id(args[0])
        if tid:
            remove_admin(tid)
            bot.send_message(room_id, f"🗑️ Removed Admin: {args[0]}")
        else: bot.send_message(room_id, "❌ User nahi mila.")
        return True

    # 3. MODERATION
    valid_cmds = {'k': 'kick', 'kick': 'kick', 'b': 'ban', 'ban': 'ban', 'm': 'mute', 'mute': 'mute', 'um': 'unmute'}
    
    if cmd in valid_cmds:
        if not args: return True
        action = valid_cmds[cmd]
        tid = get_target_id(args[0])
        
        if not tid:
            bot.send_message(room_id, "❌ User ID nahi mili. (Kya wo room me hai?)")
            # Refresh list silently for next time
            bot.send_json({"handler": "getusers", "id": uuid.uuid4().hex, "roomid": room_id})
            return True

        req_id = uuid.uuid4().hex
        if action == 'kick':
            bot.send_json({"handler": "kickuser", "id": req_id, "roomid": room_id, "to": tid})
            bot.send_message(room_id, f"👞 Kick: {args[0]}")
        elif action == 'ban':
            bot.send_json({"handler": "changerole", "id": req_id, "roomid": room_id, "targetid": tid, "role": "outcast"})
            bot.send_message(room_id, f"🔨 Ban: {args[0]}")
        elif action == 'mute':
            bot.send_json({"handler": "muteuser", "id": req_id, "roomid": room_id, "to": tid})
            bot.send_message(room_id, f"🤐 Mute: {args[0]}")
        elif action == 'unmute':
            bot.send_json({"handler": "unmuteuser", "id": req_id, "roomid": room_id, "to": tid})
            bot.send_message(room_id, f"🔊 Unmute: {args[0]}")
        
        return True

    return False
