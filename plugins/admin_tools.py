import sys
import os
import uuid
import math
from PIL import ImageDraw

# --- IMPORTS ---
try: import utils
except ImportError: print("[Admin] Error: utils.py not found!")

pagination_state = {} 

def setup(bot):
    print("[Admin Tools] Debug Version Loaded.")

# ==========================================
# 🧠 ID FINDER (Deep Search)
# ==========================================

def get_target_id(bot, room_id, username):
    target = username.lower().strip()
    
    # 1. Search in Current Room
    r_name = bot.room_id_to_name_map.get(str(room_id))
    
    # Kahan dhundna hai?
    sources = []
    if r_name and r_name in bot.room_details:
        sources.append(bot.room_details[r_name].get('id_map', {}))
    if room_id in bot.room_details:
        sources.append(bot.room_details[room_id].get('id_map', {}))
        
    # Match Logic
    for id_map in sources:
        # Direct Match
        if target in id_map: return id_map[target]
        
        # Partial Match (Agar username me farq ho)
        for name, uid in id_map.items():
            if target in name or name in target:
                return uid

    return None

# ==========================================
# ⚙️ COMMAND HANDLER
# ==========================================

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    target = args[0].replace("@", "") if args else None

    # 1. DEBUG COMMAND (Check Memory)
    if cmd == "debug":
        # Check Room Name
        r_name = bot.room_id_to_name_map.get(str(room_id), "Unknown")
        
        # Check Users List
        id_map = {}
        if r_name in bot.room_details:
            id_map = bot.room_details[r_name].get('id_map', {})
        elif room_id in bot.room_details:
            id_map = bot.room_details[room_id].get('id_map', {})
            
        count = len(id_map)
        
        msg = f"🛠️ **DEBUG REPORT**\n"
        msg += f"📍 Room ID: `{room_id}`\n"
        msg += f"🏷️ Name Map: `{r_name}`\n"
        msg += f"👥 Users in Memory: `{count}`\n\n"
        
        if count > 0:
            # Show first 5 users and their IDs
            sample = list(id_map.items())[:5]
            msg += "**Sample IDs:**\n"
            for name, uid in sample:
                msg += f"- {name}: `{uid}`\n"
        else:
            msg += "⚠️ **MEMORY EMPTY!** (Bot engine list save nahi kar raha)"
            # Auto Refresh request
            bot.send_json({"handler": "getusers", "id": uuid.uuid4().hex, "roomid": room_id})
            
        bot.send_message(room_id, msg)
        return True

    # 2. KICK (With Debug Info)
    if cmd == "kick":
        if not target:
            bot.send_message(room_id, "Usage: `!kick @username`")
            return True
        
        uid = get_target_id(bot, room_id, target)
        
        if uid:
            bot.send_json({
                "handler": "kickuser",
                "id": uuid.uuid4().hex,
                "roomid": room_id,
                "to": str(uid)
            })
            bot.send_message(room_id, f"🦵 Kicked **@{target}** (ID: {uid})")
        else:
            # Agar ID nahi mili, to Debug info do
            bot.send_message(room_id, f"❌ ID not found for **@{target}**. Type `!debug` to check memory.")
            
        return True

    # 3. KICK BY ID (Manual Override)
    # Agar automatic fail ho, to aap seedha ID daal kar kick kar sakte ho
    if cmd == "kickid":
        if not args: return True
        uid = args[0]
        bot.send_json({"handler": "kickuser", "id": uuid.uuid4().hex, "roomid": room_id, "to": str(uid)})
        bot.send_message(room_id, f"🦵 Force Kicked ID: `{uid}`")
        return True

    # 4. INVITE
    if cmd == "invite":
        if not target: return True
        bot.send_json({"handler": "chatroominvite", "id": uuid.uuid4().hex, "roomid": room_id, "to": target})
        bot.send_message(room_id, f"📨 Invited @{target}")
        return True

    # 5. PROFILE
    if cmd == "profile":
        search_user = target if target else user
        bot.send_message(room_id, f"🔍 Searching profile for **@{search_user}**...")
        bot.send_json({"handler": "profile", "id": uuid.uuid4().hex, "username": search_user})
        return True

    return False
