import sys
import os
import uuid
import math
import time
from PIL import ImageDraw

# --- IMPORTS ---
try: import utils
except ImportError: print("[Admin] Error: utils.py not found!")

# --- STATE ---
pagination_state = {} 

def setup(bot):
    print("[Admin Tools] Smart Search Loaded.")

# ==========================================
# 🧠 SMART ID FINDER (CRITICAL FIX)
# ==========================================

def get_target_id(bot, room_id, username):
    """
    Dhundne ka pakka tareeka.
    Agar seedha nahi mila, to sab jagah dhundega.
    """
    target = username.lower().strip()
    
    # 1. Try Current Room Name
    r_name = bot.room_id_to_name_map.get(str(room_id))
    if r_name and r_name in bot.room_details:
        id_map = bot.room_details[r_name].get('id_map', {})
        if target in id_map: return id_map[target]

    # 2. Try Current Room ID
    if room_id in bot.room_details:
        id_map = bot.room_details[room_id].get('id_map', {})
        if target in id_map: return id_map[target]

    # 3. GLOBAL SEARCH (Jad se ilaaj)
    # Agar mapping tuti hai, tab bhi ye ID dhund nikalega
    for r_key, r_data in bot.room_details.items():
        id_map = r_data.get('id_map', {})
        if target in id_map:
            return id_map[target]

    return None

def force_refresh_list(bot, room_id):
    bot.send_json({"handler": "getusers", "id": uuid.uuid4().hex, "roomid": room_id})

# ==========================================
# 🎨 CARDS
# ==========================================

def draw_profile_card(data):
    username = data.get("username", "Unknown")
    W, H = 600, 400
    img = utils.create_canvas(W, H, (20, 20, 25))
    d = ImageDraw.Draw(img)
    
    d.rectangle([0, 0, W, 100], fill=(40, 50, 70))
    utils.write_text(d, (W//2, 50), "USER PROFILE", size=35, align="center", col="#00FFFF", shadow=True)
    
    pic = data.get("image", "")
    avatar_url = f"https://cdn.howdies.app/avatar?image={pic}" if pic else None
    if not avatar_url: avatar_url = f"https://api.dicebear.com/9.x/adventurer/png?seed={username}"
        
    av = utils.get_circle_avatar(avatar_url, size=150)
    if av:
        d.ellipse([45, 125, 205, 285], outline="white", width=4)
        img.paste(av, (50, 130), av)

    x_start = 230
    y_start = 140
    gap = 45
    
    utils.write_text(d, (x_start, y_start), f"@{username}", size=32, align="left", col="#FFD700")
    
    role = data.get("role", "Member")
    joined = data.get("created", "Unknown")[:10]
    
    utils.write_text(d, (x_start, y_start + gap*1.5), f"🔹 Role: {role.upper()}", size=22, col="white")
    utils.write_text(d, (x_start, y_start + gap*2.5), f"📅 Joined: {joined}", size=22, col="#AAA")
    
    return img

def draw_user_list(users_chunk, page, total_pages):
    W, H = 500, 600
    img = utils.create_canvas(W, H, (15, 15, 20))
    d = ImageDraw.Draw(img)
    
    d.rounded_rectangle([20, 20, 480, 80], radius=15, fill=(40, 40, 50), outline="#00FF00", width=2)
    utils.write_text(d, (W//2, 50), f"ONLINE USERS ({page}/{total_pages})", size=24, align="center", col="white", shadow=True)
    
    start_y = 110
    for i, u in enumerate(users_chunk):
        y = start_y + (i * 45)
        col = (30, 30, 35) if i % 2 == 0 else (25, 25, 30)
        d.rectangle([40, y, 460, y+35], fill=col)
        utils.write_text(d, (60, y+5), f"{i+1}. {u}", size=20, align="left", col="#DDD")
        d.ellipse([430, y+10, 445, y+25], fill="#00FF00")

    utils.write_text(d, (W//2, H-40), "Type !n for next page", size=18, align="center", col="#FFFF00")
    return img

# ==========================================
# ⚙️ HANDLER
# ==========================================

def process_system_message(bot, data):
    handler = data.get("handler")
    if handler == "profile":
        try:
            img = draw_profile_card(data)
            link = utils.upload(bot, img)
            if link and bot.active_rooms:
                r_name = bot.active_rooms[0]
                if r_name in bot.room_details:
                    rid = bot.room_details[r_name]['id']
                    bot.send_json({"handler": "chatroommessage", "roomid": rid, "type": "image", "url": link, "text": "Profile"})
        except: pass

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    target = args[0].replace("@", "") if args else None

    # 1. KICK (Improved)
    if cmd == "kick":
        if not target:
            bot.send_message(room_id, "Usage: `!kick @username`")
            return True
        
        # Smart Search
        uid = get_target_id(bot, room_id, target)
        
        if uid:
            bot.send_json({"handler": "kickuser", "id": uuid.uuid4().hex, "roomid": room_id, "to": str(uid)})
            bot.send_message(room_id, f"🦵 **Kicked** @{target}")
        else:
            # Last Resort: Refresh
            force_refresh_list(bot, room_id)
            bot.send_message(room_id, f"❌ ID not found for @{target}. Refreshing list...")
            
        return True

    # 2. INVITE
    if cmd == "invite":
        if not target: return True
        bot.send_json({"handler": "chatroominvite", "id": uuid.uuid4().hex, "roomid": room_id, "to": target})
        bot.send_message(room_id, f"📨 Invited @{target}")
        return True

    # 3. BAN
    if cmd == "ban":
        if not target: return True
        bot.send_json({"handler": "changerole", "id": uuid.uuid4().hex, "roomid": room_id, "target": target, "role": "outcast"})
        bot.send_message(room_id, f"🚫 Banning @{target}...")
        return True

    # 4. PROFILE
    if cmd == "profile":
        search_user = target if target else user
        bot.send_message(room_id, f"🔍 Searching profile for **@{search_user}**...")
        bot.send_json({"handler": "profile", "id": uuid.uuid4().hex, "username": search_user})
        return True

    # 5. USERS LIST
    if cmd in ["users", "list"]:
        # Smart Search for List
        room_data = None
        r_name = bot.room_id_to_name_map.get(str(room_id))
        
        if r_name and r_name in bot.room_details: room_data = bot.room_details[r_name]
        elif room_id in bot.room_details: room_data = bot.room_details[room_id]
        
        users = room_data.get('users', []) if room_data else []
        
        if not users:
            force_refresh_list(bot, room_id)
            bot.send_message(room_id, "🔄 List syncing... Type `!users` again.")
            return True
            
        pagination_state[room_id] = {'users': users, 'page': 1}
        total = math.ceil(len(users) / 10)
        chunk = users[:10]
        
        img = draw_user_list(chunk, 1, total)
        link = utils.upload(bot, img)
        bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "List"})
        return True

    # 6. NEXT PAGE
    if cmd == "n":
        state = pagination_state.get(room_id)
        if not state: return True
        
        users = state['users']
        page = state['page']
        total = math.ceil(len(users) / 10)
        
        if page >= total:
            bot.send_message(room_id, "🛑 End.")
            return True
            
        nxt = page + 1
        start = (nxt - 1) * 10
        chunk = users[start : start+10]
        state['page'] = nxt
        
        img = draw_user_list(chunk, nxt, total)
        link = utils.upload(bot, img)
        bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "List"})
        return True

    return False
