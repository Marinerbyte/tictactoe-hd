import os
import sys
import time
import uuid
import random
import requests
from PIL import Image, ImageDraw
import utils
import db

# --- GLOBAL MEMORY FOR PROFILE REQUESTS ---
pending_profiles = {} 

# --- FONT CONVERTERS (Standard Unicode - No Boxes) ---
def chat_bold(text):
    try:
        n = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        b = "𝐚𝐛𝐜𝐝𝐞𝐟𝐠𝐡𝐢𝐣𝐤𝐥𝐦𝐧𝐨𝐩𝐪𝐫𝐬𝐭𝐮𝐯𝐰𝐱𝐲𝐳𝐀𝐁𝐂𝐃𝐄𝐅𝐆𝐇𝐈𝐉𝐊𝐋𝐌𝐍𝐎𝐏𝐐𝐑𝐒𝐓𝐔𝐕𝐖𝐗𝐘𝐙𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗"
        return text.translate(str.maketrans(n, b))
    except: return text

def chat_small(text):
    try:
        n = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
        s = "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ"
        return text.translate(str.maketrans(n, s))
    except: return text

def setup(bot):
    print("[Economy] Premium System Active.")

# ==========================================
# 🎨 TTF CARD RENDERER (1:1 Ratio)
# ==========================================

def draw_visual_card(data, chips, wins):
    try:
        W, H = 600, 600
        username = str(data.get("username", "Unknown"))
        status = str(data.get("status", "Available"))[:40]
        followers = str(data.get("followersCount", 0))
        following = str(data.get("followingCount", 0))
        avatar_id = data.get("avatar")

        # 1. Background
        img = utils.get_gradient(W, H, (10, 10, 20), (40, 20, 60))
        d = ImageDraw.Draw(img, 'RGBA')

        # 2. Glass Panel
        d.rounded_rectangle([30, 30, 570, 570], radius=40, fill=(0, 0, 0, 150), outline=(255, 255, 255, 50), width=2)

        # 3. Avatar with Neon Ring
        avatar_url = f"https://cdn.howdies.app/avatar?image={avatar_id}" if avatar_id else None
        av_img = utils.get_circle_avatar(avatar_url, size=180)
        
        cx, cy = W//2, 140
        d.ellipse([cx-95, cy-95, cx+95, cy+95], outline="#00FFFF", width=6) # Cyan Ring
        
        if av_img:
            img.paste(av_img, (cx-90, cy-90), av_img)

        # 4. Text Rendering (TTF Only - NO UNICODE IN IMAGE)
        utils.write_text(d, (W//2, 270), username.upper(), size=45, align="center", col="white", shadow=True)
        utils.write_text(d, (W//2, 315), status, size=22, align="center", col="#00FFFF")

        # 5. Chips Balance Box
        d.rounded_rectangle([60, 370, 540, 450], radius=20, fill=(255, 255, 255, 20))
        utils.write_text(d, (100, 410), "CHIPS BALANCE", size=18, align="left", col="#AAAAAA")
        utils.write_text(d, (500, 410), f"{chips:,}", size=32, align="right", col="#FFD700")

        # 6. Bottom Stats
        utils.write_text(d, (150, 500), "FOLLOWERS", size=16, align="center", col="#999999")
        utils.write_text(d, (150, 530), followers, size=24, align="center", col="white")
        
        utils.write_text(d, (450, 500), "GAME WINS", size=16, align="center", col="#999999")
        utils.write_text(d, (450, 530), str(wins), size=24, align="center", col="#00FF7F")

        return img
    except Exception as e:
        print(f"[Economy] Render Error: {e}")
        return None

# ==========================================
# ⚙️ HANDLERS
# ==========================================

def handle_system_message(bot, data):
    # Yeh tab chalega jab server profile data bhejega
    if data.get("handler") == "profile":
        uname = data.get("username")
        if uname in pending_profiles:
            room_id = pending_profiles.pop(uname)
            
            try:
                # DB Stats Fetch
                conn = db.get_connection()
                cur = conn.cursor()
                ph = "%s" if db.DATABASE_URL.startswith("postgres") else "?"
                cur.execute(f"SELECT global_score, wins FROM users WHERE username = {ph}", (uname,))
                row = cur.fetchone()
                conn.close()
                
                chips = row[0] if row else 0
                wins = row[1] if row else 0
                
                # Render and Upload
                img = draw_visual_card(data, chips, wins)
                url = utils.upload(bot, img)
                if url:
                    bot.send_json({
                        "handler": "chatroommessage",
                        "roomid": room_id,
                        "type": "image",
                        "url": url,
                        "text": f"Profile of @{uname}"
                    })
            except: pass

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    user_lower = user.lower()
    
    # 1. PROFILE / SCORE / STATS
    if cmd in ["profile", "score", "stats"]:
        target = args[0].replace("@", "") if args else user
        pending_profiles[target] = room_id
        # Request data from server
        bot.send_json({
            "handler": "profile",
            "id": uuid.uuid4().hex,
            "username": target
        })
        return True

    # 2. GLOBAL LEADERBOARD
    if cmd == "global":
        try:
            conn = db.get_connection()
            cur = conn.cursor()
            cur.execute("SELECT username, global_score FROM users ORDER BY global_score DESC LIMIT 10")
            rows = cur.fetchall()
            conn.close()
            
            msg = f"🏆 {chat_bold('GLOBAL RANKING')} 🏆\n"
            msg += "──────────────────\n"
            for i, (name, score) in enumerate(rows):
                medal = ["🥇", "🥈", "🥉"][i] if i < 3 else "🔹"
                msg += f"{medal} {chat_small(name)} • {score:,}\n"
            msg += "──────────────────"
            bot.send_message(room_id, msg)
        except: pass
        return True

    # 3. HELP
    if cmd == "help" and args and args[0].lower() == "score":
        help_msg = f"📖 {chat_bold('ECONOMY HELP')}\n"
        help_msg += "━━━━━━━━━━━━━━━━━━\n"
        help_msg += f"💰 !score : Premium Card\n"
        help_msg += f"🏆 !global : Rankings\n"
        if user_lower == "yasin":
            help_msg += f"\n👑 MASTER:\n"
            help_msg += f"🔹 !set @user [amt]\n"
            help_msg += f"🔹 !reset @user\n"
        bot.send_message(room_id, help_msg)
        return True

    # 4. MASTER: SET
    if cmd == "set" and user_lower == "yasin" and len(args) >= 2:
        try:
            target = args[0].replace("@", "")
            amt = int(args[1])
            db.add_game_result(target, target, "admin", amt, False)
            bot.send_message(room_id, f"✅ {chat_bold(target)}'s chips set to {amt}.")
        except: pass
        return True

    return False
