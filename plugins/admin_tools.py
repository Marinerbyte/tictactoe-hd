import sys
import os
import uuid
import math
from PIL import ImageDraw

# --- IMPORTS ---
try: import utils
except ImportError: print("[Admin] Error: utils.py not found!")

# --- STATE ---
pagination_state = {} 

def setup(bot):
    print("[Admin Tools] Stable Version Loaded.")

# ==========================================
# 🧠 SIMPLE & SOLID ID FINDER
# ==========================================

def get_target_id(bot, room_id, username):
    """
    Ye wahi function hai jo pehle kaam kar raha tha.
    Sirf current room check karega (Reliable).
    """
    target = username.lower().strip()
    
    # 1. Room Name se data nikalo
    r_name = bot.room_id_to_name_map.get(str(room_id))
    if r_name and r_name in bot.room_details:
        id_map = bot.room_details[r_name].get('id_map', {})
        if target in id_map: return id_map[target]
        
    # 2. Room ID se data nikalo (Backup)
    if room_id in bot.room_details:
        id_map = bot.room_details[room_id].get('id_map', {})
        if target in id_map: return id_map[target]

    return None

def force_refresh_list(bot, room_id):
    bot.send_json({"handler": "getusers", "id": uuid.uuid4().hex, "roomid": room_id})

# ==========================================
# 🎨 VISUALS
# ==========================================

def draw_user_list(users_chunk, page, total_pages):
    W, H = 500, 600
    img = utils.create_canvas(W, H, (15, 15, 20))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([20, 20, 480, 80], radius=15, fill=(40, 40, 50), outline="#00FF00", width=2)
    utils.write_text(d, (W//2, 50), f"ONLINE MEMBERS ({page}/{total_pages})", size=24, align="center", col="white", shadow=True)
    start_y = 110
    for i, u in enumerate(users_chunk):
        y = start_y + (i * 45)
        col = (30, 30, 35) if i % 2 == 0 else (25, 25, 30)
        d.rectangle([40, y, 460, y+35], fill=col)
        utils.write_text(d, (60, y+5), f"{i+1}. {u}", size=20, align="left", col="#DDD")
        d.ellipse([430, y+10, 445, y+25], fill="#00FF00")
    utils.write_text(d, (W//2, H-40), "Type !n for next page", size=18, align="center", col="#FFFF00")
    return img

def draw_profile_card(data):
    username = data.get("username", "Unknown")
    W, H = 600, 400
    img = utils.create_canvas(W, H, (20, 20, 25))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 100], fill=(40, 50, 70))
    utils.write_text(d, (W//2, 50), "USER PROFILE", size=35, align="center", col="#00FFFF", shadow=True)
    pic = data.get("image", "")
    avatar_url = f"https://cdn.howdies.app/avatar?image={pic}" if pic else f"https://api.dicebear.com/9.x/adventurer/png?seed={username}"
    av = utils.get_circle_avatar(avatar_url, size=150)
    if av:
        d.ellipse([45, 125, 205, 285], outline="white", width=4)
        img.paste(av, (50, 130), av)
    x_start = 230
    y_start = 140
    utils.write_text(d, (x_start, y_start), f"@{username}", size=32, align="left", col="#FFD700")
    role = data.get("role", "Member")
    joined = data.get("created", "Unknown")[:10]
    utils.write_text(d, (x_start, y_start + 45*1.5), f"🔹 Role: {role.upper()}", size=22, col="white")
    utils.write_text(d, (x_start, y_start + 45*2.5), f"📅 Joined: {joined}", size=22, col="#AAA")
    return img

# ==========================================
# ⚙️ HANDLERS
# ==========================================

def process_system_message(bot, data):
    if data.get("handler") == "profile":
        try:
            link = utils.upload(bot, draw_profile_card(data))
            if link and bot.active_rooms:
                r_name = bot.active_rooms[0]
                if r_name in bot.room_details:
                    rid = bot.room_details[r_name]['id']
                    bot.send_json({"handler": "chatroommessage", "roomid": rid, "type": "image", "url": link, "text": "Profile"})
        except: pass

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    target_name = args[0].replace("@", "") if args else None

    # --- 1. KICK (!k) ---
    if cmd in ["k", "kick"]:
        if not target_name: return True
        
        uid = get_target_id(bot, room_id, target_name)
        if uid:
            # Ye wahi code hai jo chala tha
            bot.send_json({"handler": "kickuser", "id": uuid.uuid4().hex, "roomid": room_id, "to": str(uid)})
            bot.send_message(room_id, f"🦵 **Kicked** @{target_name}")
        else:
            force_refresh_list(bot, room_id)
            bot.send_message(room_id, "❌ ID nahi mili. Refreshing...")
        return True

    # --- 2. BAN (!b) ---
    if cmd in ["b", "ban"]:
        if not target_name: return True
        
        uid = get_target_id(bot, room_id, target_name)
        if uid:
            # Ab ye bhi ID use karega (Jaise Kick ne kiya)
            bot.send_json({"handler": "changerole", "id": uuid.uuid4().hex, "roomid": room_id, "targetid": str(uid), "role": "outcast"})
            bot.send_message(room_id, f"🚫 **Banned** @{target_name} (ID: {uid})")
        else:
            force_refresh_list(bot, room_id)
            bot.send_message(room_id, "❌ ID nahi mili. Refreshing...")
        return True

    # --- 3. OWNER (!o) ---
    if cmd in ["o", "owner"]:
        if not target_name: return True
        
        uid = get_target_id(bot, room_id, target_name)
        if uid:
            bot.send_json({"handler": "changerole", "id": uuid.uuid4().hex, "roomid": room_id, "targetid": str(uid), "role": "owner"})
            bot.send_message(room_id, f"👑 **Owner:** @{target_name}")
        else:
            force_refresh_list(bot, room_id)
            bot.send_message(room_id, "❌ ID nahi mili. Refreshing...")
        return True

    # --- 4. ADMIN (!a) ---
    if cmd in ["a", "admin"]:
        if not args or len(args) < 2: return True
        action = args[0].lower()
        target = args[1].replace("@", "")
        
        uid = get_target_id(bot, room_id, target)
        
        if not uid:
            force_refresh_list(bot, room_id)
            bot.send_message(room_id, "❌ ID nahi mili. Refreshing...")
            return True

        if action == "add":
            bot.send_json({"handler": "changerole", "id": uuid.uuid4().hex, "roomid": room_id, "targetid": str(uid), "role": "admin"})
            bot.send_message(room_id, f"👮 Promoted **@{target}**")
            
        elif action in ["remove", "rem"]:
            bot.send_json({"handler": "changerole", "id": uuid.uuid4().hex, "roomid": room_id, "targetid": str(uid), "role": "member"})
            bot.send_message(room_id, f"⬇️ Demoted **@{target}**")
            
        return True

    # --- 5. INVITE (!i) ---
    if cmd in ["i", "invite"]:
        if not target_name: return True
        # Invite Username par chalta hai (Docs confirmed)
        bot.send_json({"handler": "chatroominvite", "id": uuid.uuid4().hex, "roomid": room_id, "to": target_name})
        bot.send_message(room_id, f"📨 Invited @{target_name}")
        return True

    # --- 6. PROFILE (!pro) ---
    if cmd in ["pro", "profile"]:
        target = target_name if target_name else user
        bot.send_message(room_id, f"🔍 Profile: **@{target}**...")
        bot.send_json({"handler": "profile", "id": uuid.uuid4().hex, "username": target})
        return True

    # --- 7. LIST (!u) ---
    if cmd in ["u", "users", "list"]:
        r_name = bot.room_id_to_name_map.get(str(room_id))
        room_data = bot.room_details.get(r_name) if r_name else bot.room_details.get(room_id)
        
        users = room_data.get('users', []) if room_data else []
        
        if not users:
            force_refresh_list(bot, room_id)
            bot.send_message(room_id, "🔄 Syncing...")
            return True
            
        pagination_state[room_id] = {'users': users, 'page': 1}
        total = math.ceil(len(users) / 10)
        chunk = users[:10]
        
        img = draw_user_list(chunk, 1, total)
        link = utils.upload(bot, img)
        bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "List"})
        return True

    # --- 8. NEXT (!n) ---
    if cmd == "n":
        state = pagination_state.get(room_id)
        if not state: return True
        users = state['users']; page = state['page']
        total = math.ceil(len(users) / 10)
        
        if page >= total: return True
        nxt = page + 1
        start = (nxt - 1) * 10
        chunk = users[start : start+10]
        state['page'] = nxt
        
        img = draw_user_list(chunk, nxt, total)
        link = utils.upload(bot, img)
        bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "List"})
        return True

    return False
