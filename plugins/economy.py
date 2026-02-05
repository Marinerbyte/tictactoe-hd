import os
import io
import sys
import time
import uuid
import random
from PIL import Image, ImageDraw, ImageFilter
import utils
import db

# --- STATE ---
pending_requests = {} # { "username": "room_id" }

# --- UNICODE FONTS (Sirf Chat Messages ke liye) ---
def chat_bold(text):
    n = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    b = "𝐚𝐛𝐜𝐝𝐞𝐟𝐠𝐡𝐢𝐣𝐤𝐥𝐦𝐧𝐨𝐩𝐪𝐫𝐬𝐭𝐮𝐯𝐰𝐱𝐲𝐳𝐀𝐁𝐂𝐃𝐄𝐅𝐆𝐇𝐈𝐉𝐊𝐋𝐌𝐍𝐎𝐏𝐐𝐑𝐒𝐓𝐔𝐕𝐖𝐗𝐘𝐙𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗"
    return text.translate(str.maketrans(n, b))

def chat_small(text):
    n = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    s = "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ"
    return text.translate(str.maketrans(n, s))

def setup(bot):
    print("[Economy] Premium Profile & Chips System Activated.")

# ==========================================
# 🎨 PREMIUM TTF CARD RENDERER (No Unicode)
# ==========================================

def draw_profile_card(data, chips, wins):
    W, H = 600, 600
    # Clean text from data
    username = str(data.get("username", "Unknown"))
    bio = str(data.get("status", "No Bio Set"))[:45]
    followers = str(data.get("followersCount", 0))
    following = str(data.get("followingCount", 0))
    avatar_id = data.get("avatar")

    # 1. Background: Midnight Royal Gradient
    img = utils.get_gradient(W, H, (10, 10, 26), (38, 20, 72))
    d = ImageDraw.Draw(img, 'RGBA')

    # Decorative Abstract Shapes
    for _ in range(5):
        shape = utils.get_image(f"https://api.dicebear.com/9.x/shapes/png?seed={uuid.uuid4()}&size=200")
        if shape:
            shape.putalpha(25)
            img.paste(shape, (random.randint(-50, 500), random.randint(-50, 500)), shape)

    # 2. Glassmorphism Card Frame
    d.rounded_rectangle([30, 30, 570, 570], radius=45, fill=(0, 0, 0, 140), outline=(255, 255, 255, 40), width=2)

    # 3. DP logic (Ring + Glow)
    avatar_url = f"https://cdn.howdies.app/avatar?image={avatar_id}" if avatar_id else None
    av_img = utils.get_circle_avatar(avatar_url, size=200)
    
    cx, cy = W//2, 150
    # Neon Cyan Ring
    d.ellipse([cx-108, cy-108, cx+108, cy+108], outline=(0, 255, 255, 60), width=12)
    d.ellipse([cx-102, cy-102, cx+102, cy+102], outline="#00FFFF", width=5)
    
    if av_img:
        img.paste(av_img, (cx-100, cy-100), av_img)

    # 4. Text Sections (Using Only TTF via utils.write_text)
    # Name
    utils.write_text(d, (W//2, 275), username.upper(), size=45, align="center", col="white", shadow=True)
    
    # Bio
    utils.write_text(d, (W//2, 325), bio, size=20, align="center", col="#00E5FF")

    # 5. Chips Info Box
    d.rounded_rectangle([70, 375, 530, 460], radius=20, fill=(255, 255, 255, 15))
    utils.write_text(d, (100, 418), "CHIPS BALANCE", size=18, align="left", col="#BBBBBB")
    utils.write_text(d, (500, 418), f"{chips:,}", size=34, align="right", col="#FFD700")

    # 6. Bottom Stats Grid
    stat_y = 500
    # Followers
    utils.write_text(d, (150, stat_y), "FOLLOWERS", size=15, align="center", col="#999999")
    utils.write_text(d, (150, stat_y+30), followers, size=25, align="center", col="white")
    
    # Following
    utils.write_text(d, (300, stat_y), "FOLLOWING", size=15, align="center", col="#999999")
    utils.write_text(d, (300, stat_y+30), following, size=25, align="center", col="white")
    
    # Wins
    utils.write_text(d, (450, stat_y), "GAME WINS", size=15, align="center", col="#999999")
    utils.write_text(d, (450, stat_y+30), str(wins), size=25, align="center", col="#00FF7F")

    # Finishing Touch
    d.text((W//2, 565), "₊˚ ✧ ━━━━⊱⋆⊰━━━━ ✧ ₊˚", fill=(255,255,255,30), anchor="mm")

    return img

# ==========================================
# ⚙️ SYSTEM HANDLERS
# ==========================================

def handle_system_message(bot, data):
    handler = data.get("handler")
    if handler == "profile":
        username = data.get("username")
        if username in pending_requests:
            room_id = pending_requests.pop(username)
            
            # DB Stats Fetch
            conn = db.get_connection()
            cur = conn.cursor()
            ph = "%s" if db.DATABASE_URL.startswith("postgres") else "?"
            cur.execute(f"SELECT global_score, wins FROM users WHERE username = {ph}", (username,))
            row = cur.fetchone()
            conn.close()
            
            chips = row[0] if row else 0
            wins = row[1] if row else 0
            
            # Async Processing
            def process():
                img = draw_profile_card(data, chips, wins)
                url = utils.upload(bot, img)
                if url:
                    bot.send_json({
                        "handler": "chatroommessage",
                        "roomid": room_id,
                        "type": "image",
                        "url": url,
                        "text": f"Profile of @{username}"
                    })
            utils.run_in_bg(process)

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    uid = str(data.get('userid', user))
    ph = "%s" if db.DATABASE_URL.startswith("postgres") else "?"

    # 1. PROFILE COMMAND
    if cmd in ["profile", "stats", "score"]:
        target = args[0].replace("@", "") if args else user
        pending_requests[target] = room_id
        # Request data from server
        bot.send_json({
            "handler": "profile",
            "id": uuid.uuid4().hex,
            "username": target
        })
        return True

    # 2. GLOBAL LEADERBOARD (Uses Unicode for Chat)
    if cmd == "global":
        conn = db.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT username, global_score FROM users ORDER BY global_score DESC LIMIT 10")
        rows = cur.fetchall()
        conn.close()
        
        msg = f"🏆 {chat_bold('GLOBAL RANKING')} 🏆\n"
        msg += "──────────────\n"
        for i, (name, score) in enumerate(rows):
            medal = ["🥇", "🥈", "🥉"][i] if i < 3 else "🔹"
            msg += f"{medal} {chat_small(name)} • {score:,}\n"
        msg += "──────────────"
        bot.send_message(room_id, msg)
        return True

    # 3. ADMIN COMMANDS (Sirf yasin ke liye)
    if user.lower() == "yasin":
        if cmd == "set" and len(args) >= 2:
            target, amt = args[0].replace("@", ""), int(args[1])
            db.add_game_result(target, target, "admin", amt, False) # Using simplified DB call
            bot.send_message(room_id, f"✅ {chat_bold(target)}'s chips updated to {amt}.")
            return True

    return False
