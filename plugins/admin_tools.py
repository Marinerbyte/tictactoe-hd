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
    print("[Admin Tools] Brute Force Loaded.")

# ==========================================
# 🧠 BRUTE FORCE ID FINDER (Jad Se Nikalo)
# ==========================================

def find_user_id_anywhere(bot, username):
    """
    Ye function room-woom nahi dekhta.
    Ye bot ki puri memory me jahan bhi wo naam dikhega, ID utha layega.
    """
    target = username.lower().strip()
    
    # Bot ki saari known rooms check karo
    for room_name, room_data in bot.room_details.items():
        id_map = room_data.get('id_map', {})
        
        # 1. Direct Match
        if target in id_map:
            return id_map[target]
            
        # 2. Partial Match (Agar naam milta julta ho)
        for name, uid in id_map.items():
            if target == name: # Exact match scan
                return uid
                
    return None

def force_refresh_list(bot, room_id):
    bot.send_json({"handler": "getusers", "id": uuid.uuid4().hex, "roomid": room_id})

# ==========================================
# 🎨 VISUALS (Cards)
# ==========================================

def draw_profile_card(data):
    username = data.get("username", "Unknown")
    W, H = 600, 400
    img = utils.create_canvas(W, H, (20, 20, 25))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 100], fill=(40, 50, 70))
    utils.write_text(d, (W//2, 50), "USER PROFILE", size=35, align="center", col="#00FFFF", shadow=True)
    pic = data.get("image", "")
    avatar_url = f"https://cdn.howdies.app/avatar?image={pic}" if pic else f"https://api.dicebear.com/9.x/notionists/png?seed={username}"
    av = utils.get_circle_avatar(avatar_url, size=150)
    if av:
        d.ellipse([45, 125, 205, 285], outline="white", width=4)
        img.paste(av, (50, 130), av)
    x_start = 230
    y_start = 140
    utils.write_text(d, (x_start, y_start), f"@{username}", size=32, align="left", col="#FFD700")
    role = data.get("role", "Member")
    joined = data.get("created", "Unknown")[:10]
    utils.write_text(d, (x_start, y_start + 70), f"🔹 Role: {role.upper()}", size=22, col="white")
    utils.write_text(d, (x_start, y_start + 110), f"📅 Joined: {joined}", size=22, col="#AAA")
    return img

def draw_user_list(users_chunk, page, total_pages):
    W, H = 500, 600
    img = utils.create_canvas(W, H, (15, 15, 20))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([20, 20, 480, 80], radius=15, fill=(40, 40, 50), outline="#00FF00", width=2)
    utils.write_text(d, (W//2, 50), f"ONLINE MEMBERS ({page}/{total_pages})", size=24, align="center", col="white", shadow=True)
    start_y = 110
    for i, u in enumerate(users_chunk):
        y = start_y + (i * 45)
        d.rectangle([40, y, 460, y+35], fill=(30, 30, 35))
        utils.write_text(d, (60, y+5), f"{i+1}. {u}", size=20, align="left", col="#DDD")
    utils.write_text(d, (W//2, H-40), "Type !n for next page", size=18, align="center", col="#FFFF00")
    return img

# ==========================================
# ⚙️ HANDLER
# ==========================================

def process_system_message(bot, data):
    if data.get("handler") == "profile":
        try:
            link = utils.upload(bot, draw_profile_card(data))
            if link and bot.active_rooms:
                # Broadcast to active room
                r_name = bot.active_rooms[0]
                if r_name in bot.room_details:
                    rid = bot.room_details[r_name]['id']
                    bot.send_json({"handler": "chatroommessage", "roomid": rid, "type": "image", "url": link, "text": "Profile"})
        except: pass

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    target_name = args[0].replace("@", "") if args else None

    # --- 0. CHECK/DEBUG (!check @user) ---
    if cmd == "check":
        if not target_name: return True
        uid = find_user_id_anywhere(bot, target_name)
        if uid:
            bot.send_message(room_id, f"✅ **Found:** @{target_name} -> ID: `{uid}`")
        else:
            bot.send_message(room_id, f"❌ **Not Found:** @{target_name} (Memory me nahi hai)")
            force_refresh_list(bot, room_id)
        return True

    # --- 1. KICK (!k / !kick) ---
    if cmd in ["k", "kick"]:
        if not target_name: return True
        
        uid = find_user_id_anywhere(bot, target_name)
        if uid:
            # METHOD 1: String ID
            bot.send_json({"handler": "kickuser", "id": uuid.uuid4().hex, "roomid": room_id, "to": str(uid)})
            # METHOD 2: Int ID (Backup)
            try: bot.send_json({"handler": "kickuser", "id": uuid.uuid4().hex, "roomid": room_id, "to": int(uid)})
            except: pass
            
            bot.send_message(room_id, f"🦵 **Kicked** @{target_name}")
        else:
            force_refresh_list(bot, room_id)
            bot.send_message(room_id, "❌ ID nahi mili. Refreshing...")
        return True

    # --- 2. BAN (!b / !ban) ---
    if cmd in ["b", "ban"]:
        if not target_name: return True
        
        uid = find_user_id_anywhere(bot, target_name)
        if uid:
            # ID Based
            bot.send_json({"handler": "changerole", "id": uuid.uuid4().hex, "roomid": room_id, "targetid": str(uid), "role": "outcast"})
        else:
            # Username Based (Backup)
            bot.send_json({"handler": "changerole", "id": uuid.uuid4().hex, "roomid": room_id, "target": target_name, "role": "outcast"})
            
        bot.send_message(room_id, f"🚫 **Banned** @{target_name}")
        return True

    # --- 3. OWNER (!o / !owner) ---
    if cmd in ["o", "owner"]:
        if not target_name: return True
        
        uid = find_user_id_anywhere(bot, target_name)
        if uid:
            bot.send_json({"handler": "changerole", "id": uuid.uuid4().hex, "roomid": room_id, "targetid": str(uid), "role": "owner"})
            bot.send_message(room_id, f"👑 **Owner:** @{target_name}")
        else:
            bot.send_message(room_id, "❌ User ID not found.")
        return True

    # --- 4. ADMIN (!a / !admin) ---
    if cmd in ["a", "admin"]:
        if not args or len(args) < 2: return True
        action = args[0].lower()
        target = args[1].replace("@", "")
        uid = find_user_id_anywhere(bot, target)
        
        if not uid:
            bot.send_message(room_id, "❌ ID not found.")
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
        bot.send_json({"handler": "chatroominvite", "id": uuid.uuid4().hex, "roomid": room_id, "to": target_name})
        bot.send_message(room_id, f"📨 Invited @{target_name}")
        return True

    # --- 6. PROFILE (!pro) ---
    if cmd in ["pro", "profile"]:
        target = target_name if target_name else user
        bot.send_message(room_id, f"🔍 Profile: **@{target}**")
        bot.send_json({"handler": "profile", "id": uuid.uuid4().hex, "username": target})
        return True

    # --- 7. USERS LIST (!u) ---
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
