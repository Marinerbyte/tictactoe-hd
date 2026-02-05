import os
import sys
import time
import uuid
import random
import requests
import threading
from PIL import Image, ImageDraw
import utils
import db

# --- GLOBAL MEMORY ---
pending_profiles = {} 

# --- UNICODE FONTS (For Chat) ---
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
    print("[Economy] Final Heavy-Duty Plugin Loaded.")

# ==========================================
# 🎨 PREMIUM TTF RENDERER (Clean English Only)
# ==========================================

def draw_visual_card(username, chips, wins, followers="0", following="0", bio="Howdies User", avatar_id=None):
    try:
        W, H = 600, 600
        # Background
        img = utils.get_gradient(W, H, (10, 10, 20), (30, 20, 50))
        d = ImageDraw.Draw(img, 'RGBA')
        
        # Glass Panel
        d.rounded_rectangle([30, 30, 570, 570], radius=40, fill=(0, 0, 0, 150), outline=(255, 255, 255, 40), width=2)
        
        # Avatar logic
        avatar_url = f"https://cdn.howdies.app/avatar?image={avatar_id}" if avatar_id else None
        av_img = utils.get_circle_avatar(avatar_url, size=180)
        
        cx, cy = W//2, 140
        d.ellipse([cx-95, cy-95, cx+95, cy+95], outline="#00FFFF", width=5) # Neon Ring
        
        if av_img:
            img.paste(av_img, (cx-90, cy-90), av_img)

        # Name & Bio
        utils.write_text(d, (W//2, 270), username.upper(), size=45, align="center", col="white", shadow=True)
        utils.write_text(d, (W//2, 315), bio[:40], size=20, align="center", col="#00FFFF")

        # Chips Box
        d.rounded_rectangle([60, 370, 540, 450], radius=20, fill=(255, 255, 255, 20))
        utils.write_text(d, (100, 410), "CHIPS BALANCE", size=18, align="left", col="#AAAAAA")
        utils.write_text(d, (500, 410), f"{chips:,}", size=32, align="right", col="#FFD700")

        # Stats
        stat_y = 500
        utils.write_text(d, (150, stat_y), "FOLLOWERS", size=15, align="center", col="#999999")
        utils.write_text(d, (150, stat_y+30), str(followers), size=24, align="center", col="white")
        
        utils.write_text(d, (450, stat_y), "GAME WINS", size=15, align="center", col="#999999")
        utils.write_text(d, (450, stat_y+30), str(wins), size=24, align="center", col="#00FF7F")

        return img
    except Exception as e:
        print(f"Render Error: {e}")
        return None

# ==========================================
# ⚙️ HANDLERS
# ==========================================

def handle_system_message(bot, data):
    if data.get("handler") == "profile":
        uname = data.get("username", "").lower()
        if uname in pending_profiles:
            req_data = pending_profiles.pop(uname)
            room_id = req_data['room_id']
            
            # DB Stats
            try:
                conn = db.get_connection()
                cur = conn.cursor()
                ph = "%s" if db.DATABASE_URL.startswith("postgres") else "?"
                cur.execute(f"SELECT global_score, wins FROM users WHERE username = {ph}", (data.get("username"),))
                row = cur.fetchone()
                conn.close()
                
                chips = row[0] if row else 0
                wins = row[1] if row else 0
                
                img = draw_visual_card(
                    username=data.get("username"),
                    chips=chips,
                    wins=wins,
                    followers=data.get("followersCount", "0"),
                    following=data.get("followingCount", "0"),
                    bio=data.get("status", "Available"),
                    avatar_id=data.get("avatar")
                )
                url = utils.upload(bot, img)
                if url:
                    bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": url, "text": f"Profile: @{data.get('username')}"})
            except: pass

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    user_lower = user.lower()
    ph = "%s" if db.DATABASE_URL.startswith("postgres") else "?"

    # 1. PROFILE / STATS
    if cmd in ["profile", "score", "stats"]:
        target = args[0].replace("@", "") if args else user
        target_lower = target.lower()
        
        # Immediate confirmation
        bot.send_message(room_id, f"🔍 {chat_small('fetching profile for')} @{target}...")
        
        pending_profiles[target_lower] = {"room_id": room_id, "time": time.time()}
        bot.send_json({"handler": "profile", "id": uuid.uuid4().hex, "username": target})
        return True

    # 2. GLOBAL
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
            bot.send_message(room_id, msg)
        except: 
            bot.send_message(room_id, "❌ Database busy.")
        return True

    # 3. HELP
    if cmd == "help" and args and args[0].lower() == "score":
        msg = f"📖 {chat_bold('ECONOMY HELP')}\n━━━━━━━━━━━━━━\n"
        msg += f"💰 !score : Premium Card\n🏆 !global : Rankings\n"
        if user_lower == "yasin":
            msg += f"\n👑 MASTER:\n🔹 !set @user [amt]\n🔹 !wipeall"
        bot.send_message(room_id, msg)
        return True

    # 4. MASTER: SET
    if cmd == "set" and user_lower == "yasin" and len(args) >= 2:
        try:
            target = args[0].replace("@", "")
            amt = int(args[1])
            # db.py function: add_game_result(user_id, username, game_name, amount, is_win)
            # Hum user_id ki jagah username bhej rahe hain agar ID nahi hai
            db.add_game_result(target, target, "admin_set", amt, False)
            bot.send_message(room_id, f"✅ @{target}'s chips updated to {amt}.")
        except: 
            bot.send_message(room_id, "❌ Usage: !set @user 1000")
        return True

    # 5. MASTER: WIPEALL
    if cmd == "wipeall" and user_lower == "yasin":
        try:
            conn = db.get_connection()
            cur = conn.cursor()
            cur.execute("DELETE FROM users")
            cur.execute("DELETE FROM game_stats")
            conn.commit(); conn.close()
            bot.send_message(room_id, "🔥 DATABASE WIPED.")
        except: pass
        return True

    return False
