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
    print("[Admin Tools] Kick Fix Loaded.")

# ==========================================
# 🧠 ID FINDER
# ==========================================
def get_target_id(bot, room_id, username):
    target = username.lower().strip()
    r_name = bot.room_id_to_name_map.get(str(room_id))
    
    sources = []
    if r_name and r_name in bot.room_details:
        sources.append(bot.room_details[r_name].get('id_map', {}))
    if room_id in bot.room_details:
        sources.append(bot.room_details[room_id].get('id_map', {}))
        
    for id_map in sources:
        if target in id_map: return id_map[target]
        # Partial match
        for name, uid in id_map.items():
            if target in name: return uid
    return None

def force_refresh_list(bot, room_id):
    bot.send_json({"handler": "getusers", "id": uuid.uuid4().hex, "roomid": room_id})

# ==========================================
# ⚙️ COMMAND HANDLER
# ==========================================

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    target = args[0].replace("@", "") if args else None

    # 1. KICK (Double Shot Strategy)
    if cmd == "kick":
        if not target:
            bot.send_message(room_id, "Usage: `!kick @username`")
            return True
        
        uid = get_target_id(bot, room_id, target)
        
        if uid:
            # TRY 1: Send as String ("10132")
            bot.send_json({
                "handler": "kickuser",
                "id": uuid.uuid4().hex,
                "roomid": room_id,
                "to": str(uid)
            })
            
            # TRY 2: Send as Integer (10132) - Just in case
            try:
                bot.send_json({
                    "handler": "kickuser",
                    "id": uuid.uuid4().hex,
                    "roomid": room_id,
                    "to": int(uid)
                })
            except: pass

            bot.send_message(room_id, f"🦵 **Attempting to Kick** @{target} (ID: {uid})")
            
            # Advice if fails
            bot.send_message(room_id, "ℹ️ *Agar kick nahi hua, to check karein ki Bot 'Admin' hai ya nahi.*")
        else:
            force_refresh_list(bot, room_id)
            bot.send_message(room_id, f"❌ ID nahi mili. List refresh kar di hai.")
            
        return True

    # 2. DEBUG
    if cmd == "debug":
        r_name = bot.room_id_to_name_map.get(str(room_id), "Unknown")
        id_map = {}
        if r_name in bot.room_details: id_map = bot.room_details[r_name].get('id_map', {})
        elif room_id in bot.room_details: id_map = bot.room_details[room_id].get('id_map', {})
        
        msg = f"📊 Users in Memory: {len(id_map)}"
        bot.send_message(room_id, msg)
        return True

    # 3. INVITE
    if cmd == "invite":
        if not target: return True
        bot.send_json({"handler": "chatroominvite", "id": uuid.uuid4().hex, "roomid": room_id, "to": target})
        bot.send_message(room_id, f"📨 Invited @{target}")
        return True

    return False
