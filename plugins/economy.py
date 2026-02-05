import os
import io
import sys
import time
from PIL import Image, ImageDraw, ImageFilter, ImageOps
import utils
import db

# --- FONT STYLES (Unicode Magic) ---
def to_bold(text):
    # a-z -> 𝐚-𝐳
    normal = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    bold = "𝐚𝐛𝐜𝐝𝐞𝐟𝐠𝐡𝐢𝐣𝐤𝐥𝐦𝐧𝐨𝐩𝐪𝐫𝐬𝐭𝐮𝐯𝐰𝐱𝐲𝐳𝐀𝐁𝐂𝐃𝐄𝐅𝐆𝐇𝐈𝐉𝐊𝐋𝐌𝐍𝐎𝐏𝐐𝐑𝐒𝐓𝐔𝐕𝐖𝐗𝐘𝐙𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗"
    trans = str.maketrans(normal, bold)
    return text.translate(trans)

def to_small_caps(text):
    # a-z -> ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ
    normal = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    small = "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ"
    trans = str.maketrans(normal, small)
    return text.translate(trans)

# --- CONFIG ---
MASTER_USER = "yasin"
CURRENCY = "Chips 🎰"

def setup(bot):
    print("[Economy] Advanced Stats System Ready.")

# ==========================================
# 🎨 VISUAL SCORE CARD (1:1 Premium Design)
# ==========================================

def draw_score_card(username, avatar_url, chips, total_wins, mines_stats, ttt_stats):
    W, H = 600, 600
    # Deep Dark Blue-Black Gradient
    img = utils.get_gradient(W, H, (10, 10, 20), (30, 30, 50))
    d = ImageDraw.Draw(img, 'RGBA')

    # Borders & Decorative Elements
    d.rectangle([10, 10, 590, 590], outline=(255, 215, 0, 80), width=2)
    d.text((W//2, 40), "₊˚ ✧ ━━━━⊱⋆⊰━━━━ ✧ ₊˚", fill="#FFD700", anchor="mm")

    # 1. User DP with Gold Ring
    av_img = utils.get_image(avatar_url) if avatar_url else None
    if not av_img:
        av_img = utils.get_image(f"https://api.dicebear.com/9.x/adventurer/png?seed={username}")
    
    if av_img:
        av_img = av_img.resize((150, 150), Image.Resampling.LANCZOS)
        mask = Image.new('L', (150, 150), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, 150, 150), fill=255)
        
        # Ring
        d.ellipse([W//2-80, 70, W//2+80, 230], outline="#FFD700", width=5)
        img.paste(av_img, (W//2-75, 75), mask)

    # 2. Username & Global Rank
    utils.write_text(d, (W//2, 260), to_bold(username.upper()), size=40, align="center", col="white", shadow=True)
    utils.write_text(d, (W//2, 305), to_small_caps("global chip holder"), size=20, align="center", col="#AAAAAA")

    # 3. Main Stats (Chips & Wins)
    # Glass Box for Chips
    d.rounded_rectangle([50, 330, 550, 420], radius=20, fill=(0,0,0,120), outline="#FFD700", width=1)
    utils.write_text(d, (W//2, 360), to_small_caps("total chips"), size=18, align="center", col="#FFD700")
    utils.write_text(d, (W//2, 395), f"🎰 {chips:,}", size=35, align="center", col="white")

    # 4. Game Wise Stats (Divided)
    y_start = 450
    # Mines Column
    utils.write_text(d, (150, y_start), "💣 " + to_small_caps("mines"), size=22, align="center", col="#FF4444")
    utils.write_text(d, (150, y_start+35), f"𝐖: {mines_stats[0]} | 𝐋: {mines_stats[1]}", size=20, align="center", col="white")
    
    # TTT Column
    utils.write_text(d, (450, y_start), "❌ " + to_small_caps("tictactoe"), size=22, align="center", col="#4facfe")
    utils.write_text(d, (450, y_start+35), f"𝐖: {ttt_stats[0]} | 𝐋: {ttt_stats[1]}", size=20, align="center", col="white")

    # Footer Border
    d.text((W//2, 560), "─── ⋆⋅☆⋅⋆ ───", fill="#888888", anchor="mm")
    
    return img

# ==========================================
# ⚙️ LOGIC & COMMANDS
# ==========================================

def get_detailed_stats(uid):
    conn = db.get_connection()
    cur = conn.cursor()
    # Fetch Specific Games
    cur.execute("SELECT game_name, wins FROM game_stats WHERE user_id = %s", (str(uid),))
    rows = cur.fetchall()
    conn.close()
    
    stats = {"mines": [0, 0], "tictactoe": [0, 0]}
    for name, wins in rows:
        if name in stats: stats[name][0] = wins
    # Losses estimate (for visual purposes) or you can track real losses in DB if needed
    return stats

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    uid = str(data.get('userid', user))
    av_url = data.get("avatar")
    ph = "%s" if db.DATABASE_URL.startswith("postgres") else "?"

    # 1. !score - Personal Visual Card
    if cmd == "score":
        try:
            conn = db.get_connection()
            cur = conn.cursor()
            cur.execute(f"SELECT global_score, wins FROM users WHERE user_id = {ph}", (uid,))
            row = cur.fetchone()
            conn.close()

            chips = row[0] if row else 0
            total_w = row[1] if row else 0
            g_stats = get_detailed_stats(uid)

            def process():
                img = draw_score_card(user, av_url, chips, total_w, g_stats["mines"], g_stats["tictactoe"])
                url = utils.upload(bot, img)
                if url:
                    bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": url, "text": f"Stats: {user}"})
            utils.run_in_bg(process)
            return True
        except: return True

    # 2. !global - Leaderboard List
    if cmd == "global":
        conn = db.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT username, global_score FROM users ORDER BY global_score DESC LIMIT 10")
        rows = cur.fetchall()
        conn.close()
        
        msg = f"🏆 ━━⊱ {to_bold('GLOBAL RANKING')} ⊰━━ 🏆\n"
        msg += "﹌﹌﹌﹌﹌﹌﹌﹌﹌﹌﹌﹌\n"
        for i, (name, score) in enumerate(rows):
            icon = ["🥇", "🥈", "🥉"][i] if i < 3 else "🔹"
            msg += f"{icon} `#{i+1}` **{to_small_caps(name)}** • {score:,}\n"
        msg += "﹌﹌﹌﹌﹌﹌﹌﹌﹌﹌﹌﹌"
        bot.send_message(room_id, msg)
        return True

    # 3. ADMIN POWER (yasin only)
    if user.lower() == MASTER_USER:
        # !set @user 5000
        if cmd == "set":
            if not args: return True
            target = args[0].replace("@", "")
            amount = int(args[1])
            # Getting ID from bot mapping
            target_id = None
            for r_name, details in bot.room_details.items():
                if target.lower() in details.get('id_map', {}):
                    target_id = details['id_map'][target.lower()]
                    break
            
            if target_id:
                conn = db.get_connection()
                cur = conn.cursor()
                cur.execute(f"UPDATE users SET global_score = {ph} WHERE user_id = {ph}", (amount, target_id))
                conn.commit(); conn.close()
                bot.send_message(room_id, f"✅ @{target} score set to {amount} {CURRENCY}")
            return True

        # !reset @user
        if cmd == "reset":
            if not args: return True
            target = args[0].replace("@", "")
            target_id = None
            for r_name, details in bot.room_details.items():
                if target.lower() in details.get('id_map', {}):
                    target_id = details['id_map'][target.lower()]
                    break
            if target_id:
                conn = db.get_connection()
                cur = conn.cursor()
                cur.execute(f"UPDATE users SET global_score = 0, wins = 0 WHERE user_id = {ph}", (target_id,))
                cur.execute(f"DELETE FROM game_stats WHERE user_id = {ph}", (target_id,))
                conn.commit(); conn.close()
                bot.send_message(room_id, f"🧹 {to_small_caps('stats cleared for')} @{target}")
            return True

        # !wipeall
        if cmd == "wipeall":
            conn = db.get_connection()
            cur = conn.cursor()
            cur.execute("DELETE FROM users")
            cur.execute("DELETE FROM game_stats")
            conn.commit(); conn.close()
            bot.send_message(room_id, "🔥 **DATABASE WIPED.** All game data and scores are now zero.")
            return True

    return False
