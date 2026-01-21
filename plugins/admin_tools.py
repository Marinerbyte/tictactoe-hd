import sys
import os
import uuid
import math
from PIL import ImageDraw

# --- IMPORTS ---
try: import utils
except ImportError: print("[Admin] Error: utils.py not found!")

# --- STATE ---
# Pagination ke liye: {room_id: {'users': [], 'page': 0}}
pagination_state = {} 

def setup(bot):
    print("[Admin Tools] Direct Action Engine Loaded.")

# ==========================================
# 🎨 ARTIST SECTION (Cards)
# ==========================================

def draw_profile_card(data):
    """Profile data aane par ye card banega"""
    username = data.get("username", "Unknown")
    
    # Background
    W, H = 600, 400
    img = utils.create_canvas(W, H, (20, 20, 25))
    d = ImageDraw.Draw(img)
    
    # 1. Header Gradient
    d.rectangle([0, 0, W, 120], fill=(40, 50, 70))
    utils.write_text(d, (W//2, 60), "USER PROFILE", size=35, align="center", col="#00FFFF", shadow=True)
    
    # 2. Avatar
    # Profile pic server path se
    pic = data.get("image", "")
    avatar_url = f"https://cdn.howdies.app/avatar?image={pic}" if pic else None
    
    if avatar_url:
        av = utils.get_circle_avatar(avatar_url, size=140)
    else:
        # Fallback to DiceBear
        av = utils.get_circle_avatar(f"https://api.dicebear.com/9.x/adventurer/png?seed={username}", size=140)
        
    if av:
        # Border ring
        d.ellipse([45, 135, 195, 285], outline="white", width=4)
        img.paste(av, (50, 140), av)

    # 3. Info Stats
    x_start = 220
    y_start = 150
    gap = 40
    
    # Username
    utils.write_text(d, (x_start, y_start), f"@{username}", size=30, align="left", col="#FFD700")
    
    # Other Details (Adjust keys based on exact API response)
    role = data.get("role", "Member")
    joined = data.get("created", "N/A")[:10] # Date only
    
    utils.write_text(d, (x_start, y_start + gap*1.5), f"🔹 Role: {role.upper()}", size=20, col="white")
    utils.write_text(d, (x_start, y_start + gap*2.5), f"📅 Joined: {joined}", size=20, col="#AAA")
    
    # Footer
    utils.write_text(d, (W//2, H-30), "Howdies Database", size=16, align="center", col="#555")
    
    return img

def draw_user_list(room_name, users_chunk, page, total_pages):
    """User List Card"""
    W, H = 500, 600
    img = utils.create_canvas(W, H, (15, 15, 20))
    d = ImageDraw.Draw(img)
    
    # Header
    d.rounded_rectangle([20, 20, 480, 80], radius=15, fill=(40, 40, 50), outline="#00FF00", width=2)
    utils.write_text(d, (W//2, 50), f"ONLINE USERS ({page}/{total_pages})", size=24, align="center", col="white", shadow=True)
    
    # List
    start_y = 110
    for i, u in enumerate(users_chunk):
        y = start_y + (i * 45)
        # Row Bg
        col = (30, 30, 35) if i % 2 == 0 else (25, 25, 30)
        d.rectangle([40, y, 460, y+35], fill=col)
        # Name
        utils.write_text(d, (60, y+5), f"{i+1}. {u}", size=20, align="left", col="#DDD")
        # Online Dot
        d.ellipse([430, y+10, 445, y+25], fill="#00FF00")

    # Footer Instruction
    utils.write_text(d, (W//2, H-40), "Type !n for next page", size=18, align="center", col="#FFFF00")
    
    return img

# ==========================================
# ⚙️ SYSTEM HANDLER (Incoming Data)
# ==========================================

def process_system_message(bot, data):
    """Server se jab data wapas aaye (Profile etc)"""
    handler = data.get("handler")
    
    # PROFILE DATA RECEIVED
    if handler == "profile":
        # Check kisne manga tha (Agar tracking logic ho, abhi ke liye public bhejte hain)
        # Profile data doesn't always have roomid in response, so we send to active room or skip
        # Note: Howdies 'profile' response usually doesn't carry room_id. 
        # Hum last active room guess karenge ya message ignore karenge agar room id na ho.
        
        # Creating Card
        img = draw_profile_card(data)
        link = utils.upload(bot, img)
        
        # Send to the last known room of the bot (Best guess)
        if link and bot.active_rooms:
            target_room = bot.active_rooms[0] # Default to first room
            bot.send_json({"handler": "chatroommessage", "roomid": bot.room_details[target_room]['id'], "type": "image", "url": link, "text": "Profile"})

# ==========================================
# ⚙️ COMMAND HANDLER
# ==========================================

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    
    # Helper to get target username
    target = args[0].replace("@", "") if args else None

    # 1. INVITE (!invite username) - Direct
    if cmd == "invite":
        if not target:
            bot.send_message(room_id, "Usage: `!invite @username`")
            return True
        
        bot.send_json({
            "handler": "chatroominvite",
            "id": uuid.uuid4().hex,
            "roomid": room_id,
            "to": target  # Direct Username allowed per docs
        })
        bot.send_message(room_id, f"📨 Invited **@{target}**")
        return True

    # 2. PROMOTE (!admin add @user) - Direct
    if cmd == "admin" and args and args[0] == "add":
        if len(args) < 2: return True
        target = args[1].replace("@", "")
        
        bot.send_json({
            "handler": "changerole",
            "id": uuid.uuid4().hex,
            "roomid": room_id,
            "target": target, # Direct Username
            "role": "admin"
        })
        bot.send_message(room_id, f"👮 Promoting **@{target}**...")
        return True

    # 3. OWNER (!owner @user) - Direct
    if cmd == "owner":
        if not target: return True
        # Owner requires UserID usually, but let's try target logic or lookup
        # Lookup ID
        uid = bot.room_details.get(bot.room_id_to_name_map.get(room_id, room_id), {}).get('id_map', {}).get(target.lower())
        
        if uid:
            bot.send_json({
                "handler": "changerole",
                "id": uuid.uuid4().hex,
                "roomid": room_id,
                "targetid": uid, # Requires ID per docs
                "role": "owner"
            })
            bot.send_message(room_id, f"👑 Transferring ownership to **@{target}**...")
        else:
            bot.send_message(room_id, "⚠️ User ID not found in room (Needs to be present).")
        return True

    # 4. BAN (!ban @user) -> Sets role to 'outcast'
    if cmd == "ban":
        if not target: return True
        
        bot.send_json({
            "handler": "changerole",
            "id": uuid.uuid4().hex,
            "roomid": room_id,
            "target": target, # Direct Username
            "role": "outcast"
        })
        bot.send_message(room_id, f"🚫 Banning **@{target}**...")
        return True

    # 5. KICK (!kick @user)
    if cmd == "kick":
        if not target: return True
        
        # Kick requires ID strictly.
        uid = bot.room_details.get(bot.room_id_to_name_map.get(room_id, room_id), {}).get('id_map', {}).get(target.lower())
        
        if uid:
            bot.send_json({
                "handler": "kickuser",
                "id": uuid.uuid4().hex,
                "roomid": room_id,
                "to": uid
            })
            bot.send_message(room_id, f"🦵 Kicking **@{target}**...")
        else:
            # Fallback: Try banning/outcasting via username if kick fails lookup
            bot.send_message(room_id, f"⚠️ ID not found. Trying Force Ban...")
            bot.send_json({
                "handler": "changerole",
                "id": uuid.uuid4().hex,
                "roomid": room_id,
                "target": target,
                "role": "outcast"
            })
        return True

    # 6. PROFILE (!profile @user)
    if cmd == "profile":
        if not target: target = user
        
        bot.send_message(room_id, f"🔍 Fetching profile for **@{target}**...")
        # Send Request
        bot.send_json({
            "handler": "profile",
            "id": uuid.uuid4().hex,
            "username": target # Direct Username
        })
        return True

    # 7. GET USERS (!users / !list)
    if cmd in ["users", "list"]:
        # Get list from memory
        r_name = bot.room_id_to_name_map.get(room_id, room_id)
        room_data = bot.room_details.get(r_name)
        
        if not room_data:
            bot.send_message(room_id, "⚠️ Data syncing... Try `!refresh` first.")
            return True
            
        all_users = room_data.get('users', [])
        
        # Save state
        pagination_state[room_id] = {'users': all_users, 'page': 1}
        
        # Generate Page 1
        total_pages = math.ceil(len(all_users) / 10)
        chunk = all_users[:10]
        
        img = draw_user_list(r_name, chunk, 1, total_pages)
        link = utils.upload(bot, img)
        bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "List"})
        return True

    # 8. NEXT PAGE (!n)
    if cmd == "n":
        state = pagination_state.get(room_id)
        if not state: return True # No list active
        
        users = state['users']
        current_page = state['page']
        total_pages = math.ceil(len(users) / 10)
        
        if current_page >= total_pages:
            bot.send_message(room_id, "🛑 End of list.")
            return True
            
        # Next Page
        next_page = current_page + 1
        start = (next_page - 1) * 10
        end = start + 10
        chunk = users[start:end]
        
        # Update State
        state['page'] = next_page
        
        img = draw_user_list("Room", chunk, next_page, total_pages)
        link = utils.upload(bot, img)
        bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Next"})
        return True

    return False
