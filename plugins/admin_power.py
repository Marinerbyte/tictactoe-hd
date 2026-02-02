import uuid
import time

# --- CONFIG ---
# Sirf yasin ya bot admins hi ye commands chala payenge
MASTER_USER = "yasin"

def setup(bot):
    print("[Admin Power] Moderation Plugin Loaded.")

def get_uid(bot, room_id, username):
    """Room details se username ki integer ID nikalta hai"""
    target = username.lower().replace("@", "")
    
    # Bot engine ke room_details mein check karte hain
    for room_name, details in bot.room_details.items():
        if details.get('id') == str(room_id):
            id_map = details.get('id_map', {})
            return id_map.get(target)
    return None

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    
    # --- SECURITY CHECK ---
    # Sirf Master User ya Bot Admins hi ye commands use kar sakte hain
    # (Note: bot.admins table db.py se aati hai)
    from db import get_all_admins
    is_admin = str(data.get("userid")) in get_all_admins()
    if user.lower() != MASTER_USER and not is_admin:
        return False

    if not args and cmd not in ["leave"]:
        return False

    target_name = args[0].replace("@", "") if args else ""

    # ==========================================
    # 🛡️ MODERATION (KICK / MUTE / UNMUTE)
    # ==========================================
    
    if cmd in ["k", "kick"]:
        uid = get_uid(bot, room_id, target_name)
        if uid:
            bot.send_json({
                "handler": "kickuser",
                "id": uuid.uuid4().hex,
                "roomid": int(room_id),
                "to": int(uid)
            })
            bot.send_message(room_id, f"🦵 **@{target_name}** has been kicked.")
        else:
            bot.send_message(room_id, f"❌ ID not found for @{target_name}")
        return True

    elif cmd in ["m", "mute"]:
        uid = get_uid(bot, room_id, target_name)
        if uid:
            bot.send_json({
                "handler": "muteuser",
                "id": uuid.uuid4().hex,
                "roomid": int(room_id),
                "to": int(uid)
            })
            bot.send_message(room_id, f"🤐 **@{target_name}** is now muted.")
        return True

    elif cmd in ["um", "unmute"]:
        uid = get_uid(bot, room_id, target_name)
        if uid:
            bot.send_json({
                "handler": "unmuteuser",
                "id": uuid.uuid4().hex,
                "roomid": int(room_id),
                "to": int(uid)
            })
            bot.send_message(room_id, f"🔊 **@{target_name}** is unmuted.")
        return True

    # ==========================================
    # 👑 ROLES (OWNER / ADMIN / MEMBER / BAN)
    # ==========================================

    elif cmd in ["o", "a", "mbr", "out", "none"]:
        role_map = {
            "o": "owner",
            "a": "admin",
            "mbr": "member",
            "out": "outcast", # This is basically BAN
            "none": "none"
        }
        target_role = role_map[cmd]
        bot.send_json({
            "handler": "changerole",
            "id": uuid.uuid4().hex,
            "roomid": int(room_id),
            "target": target_name,
            "role": target_role
        })
        bot.send_message(room_id, f"🎭 **@{target_name}** role set to: {target_role}")
        return True

    # ==========================================
    # 📌 ROOM SETTINGS (PIN / DESC)
    # ==========================================

    elif cmd == "pin":
        text = " ".join(args)
        bot.send_json({
            "handler": "pinnedmessageupdate",
            "id": uuid.uuid4().hex,
            "roomid": int(room_id),
            "to": int(room_id),
            "pinnedMessage": text
        })
        bot.send_message(room_id, "📌 Pinned message updated.")
        return True

    elif cmd == "desc":
        text = " ".join(args)
        bot.send_json({
            "handler": "chatroomsettingsupdate",
            "id": uuid.uuid4().hex,
            "roomid": int(room_id),
            "to": int(room_id),
            "Description": text[:40] # 40 chars limit
        })
        bot.send_message(room_id, "📝 Room description updated.")
        return True

    # ==========================================
    # ✉️ SMART INVITE (DM + CARD)
    # ==========================================

    elif cmd == "i":
        # Room name dhundte hain
        room_name = "Room"
        for r_name, details in bot.room_details.items():
            if details.get('id') == str(room_id):
                room_name = r_name
                break
        
        # DM Invite
        bot.send_json({
            "handler": "message",
            "id": uuid.uuid4().hex,
            "type": "text",
            "to": target_name,
            "text": f"📩 You are invited to join {room_name}",
            "contents": {
                "col": 1,
                "data": [{"t": room_name, "bc": "orange", "tc": "#fff", "r": int(room_id)}]
            }
        })
        bot.send_message(room_id, f"📩 Invite card sent to **@{target_name}**")
        return True

    return False
