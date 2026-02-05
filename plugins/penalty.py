import time
import random
import threading
import sys
import os
import uuid
import requests
import io
from PIL import Image, ImageDraw, ImageFilter, ImageOps

# --- UTILS & DB ---
try:
    import utils
except ImportError:
    print("[PenaltyStrike] Error: utils.py missing!")

try:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from db import add_game_result
except Exception as e:
    print(f"DB Error: {e}")

# --- GLOBAL STATE ---
penalty_games = {} 
games_lock = threading.Lock()
BOT_INSTANCE = None 
AVATAR_CACHE = {}

def setup(bot_ref):
    global BOT_INSTANCE
    BOT_INSTANCE = bot_ref
    print("[PenaltyStrike] Pro Visuals Engine Loaded.")

# ==========================================
# 🖼️ ROBUST AVATAR ENGINE (Direct Payload)
# ==========================================

def get_robust_avatar(avatar_url, username):
    if avatar_url in AVATAR_CACHE:
        return AVATAR_CACHE[avatar_url].copy()
    try:
        if avatar_url:
            r = requests.get(avatar_url, timeout=5)
            if r.status_code == 200:
                img = Image.open(io.BytesIO(r.content)).convert("RGBA")
                AVATAR_CACHE[avatar_url] = img
                return img.copy()
    except: pass
    try:
        fb_url = f"https://api.dicebear.com/9.x/adventurer/png?seed={username}&backgroundColor=transparent"
        r = requests.get(fb_url, timeout=5)
        return Image.open(io.BytesIO(r.content)).convert("RGBA")
    except:
        return Image.new("RGBA", (100, 100), (30, 30, 35))

def apply_round_corners(img, radius):
    mask = Image.new('L', img.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0) + img.size, radius=radius, fill=255)
    output = Image.new('RGBA', img.size, (0, 0, 0, 0))
    output.paste(img, (0, 0), mask)
    return output

# ==========================================
# 🎨 GRAPHICS ENGINE (1:1 Premium Card)
# ==========================================

def draw_penalty_card(username, user_av, result="VS", user_pos=None, bot_pos=None):
    W, H = 700, 700
    # Turf Green Gradient
    base = utils.get_gradient(W, H, (10, 40, 10), (20, 80, 20))
    img = Image.new('RGBA', (W, H), (0,0,0,0))
    img.paste(base, (0,0))
    d = ImageDraw.Draw(img)

    # Rounded Card Border
    border_col = "#FFFFFF"
    if result == "GOAL": border_col = "#00FF00"
    if result == "SAVED": border_col = "#FF0000"
    d.rounded_rectangle([10, 10, W-10, H-10], radius=50, outline=border_col, width=5)

    # 1. Header
    utils.write_text(d, (W//2, 60), "PENALTY STRIKE", size=45, align="center", col="white", shadow=True)

    # 2. Draw Goal Post
    gx1, gy1, gx2, gy2 = 120, 180, 580, 480
    d.rectangle([gx1, gy1, gx2, gy2], outline="white", width=6)
    # Net pattern
    for i in range(gx1, gx2, 30): d.line([i, gy1, i, gy2], fill=(255,255,255,40), width=1)
    for i in range(gy1, gy2, 30): d.line([gx1, i, gx2, i], fill=(255,255,255,40), width=1)

    # 3. Goalkeeper Logic (Bot)
    # Default center, or jump left/right
    pos_map = {1: (gx1+20, gy1+80), 2: (W//2-80, gy1+80), 3: (gx2-180, gy1+80)}
    b_xy = pos_map.get(bot_pos, (W//2-80, gy1+80))
    
    bot_av = get_robust_avatar(None, "BOT_GOALIE")
    bot_av = bot_av.resize((160, 160))
    # Circle mask for goalie
    g_mask = Image.new('L', (160, 160), 0)
    ImageDraw.Draw(g_mask).ellipse((0, 0, 160, 160), fill=255)
    img.paste(bot_av, b_xy, g_mask)
    d.ellipse([b_xy[0], b_xy[1], b_xy[0]+160, b_xy[1]+160], outline="#FFD700", width=4)

    # 4. Ball Logic
    if user_pos:
        ball = utils.get_emoji("⚽", size=80)
        ball_pos_map = {1: (gx1+60, gy1+120), 2: (W//2-40, gy2-100), 3: (gx2-140, gy1+120)}
        img.paste(ball, ball_pos_map.get(user_pos), ball)

    # 5. User DP (The Striker)
    u_av = get_robust_avatar(user_av, username)
    u_av = u_av.resize((130, 130))
    u_mask = Image.new('L', (130, 130), 0)
    ImageDraw.Draw(u_mask).ellipse((0, 0, 130, 130), fill=255)
    img.paste(u_av, (40, 530), u_mask)
    d.ellipse([40, 530, 170, 660], outline="white", width=3)
    utils.write_text(d, (105, 675), username.upper(), size=22, align="center", col="white")

    # 6. Result Big Text Overlay
    if result != "VS":
        # Dim background for result
        overlay = Image.new('RGBA', (W, H), (0,0,0,150))
        img = Image.alpha_composite(img, overlay)
        d = ImageDraw.Draw(img)
        res_col = "#00FF00" if result == "GOAL" else "#FF0000"
        utils.write_text(d, (W//2, H//2), result, size=120, align="center", col=res_col, shadow=True)
        utils.write_text(d, (W//2, H//2 + 100), "TAP !KICK TO REMATCH", size=30, align="center", col="white")

    return apply_round_corners(img, 50)

# ==========================================
# ⚙️ HANDLER
# ==========================================

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    uid = str(data.get('userid', user))
    av_url = data.get("avatar")

    with games_lock:
        game = penalty_games.get(room_id)

    # 1. Start Game (!kick 500)
    if cmd == "kick":
        if game: return True
        try:
            bet = int(args[0]) if args and args[0].isdigit() else 500
            if bet < 100:
                bot.send_message(room_id, "❌ Min bet is 100 CHIPS")
                return True
            
            # Deduct Chips
            add_game_result(uid, user, "penalty", -bet, False)
            
            with games_lock:
                penalty_games[room_id] = {
                    "uid": uid, "name": user, "av": av_url, "bet": bet, 
                    "time": time.time()
                }
            
            img = draw_penalty_card(user, av_url)
            bot.send_json({
                "handler":"chatroommessage",
                "roomid":room_id,
                "type":"image",
                "url":utils.upload(bot, img),
                "text":"GAME START"
            })
            bot.send_message(room_id, f"⚽ @{user}, Where to shoot?\nType: 1 (Left) | 2 (Center) | 3 (Right)")
        except: pass
        return True

    # 2. Player Decision (1, 2, 3)
    if cmd in ["1", "2", "3"] and game:
        if uid != game["uid"]: return False
        
        user_choice = int(cmd)
        bot_choice = random.randint(1, 3) # Bot chooses a random side
        
        result = "GOAL" if user_choice != bot_choice else "SAVED"
        win_amt = game["bet"] * 2 if result == "GOAL" else 0
        
        if win_amt > 0:
            add_game_result(uid, game["name"], "penalty", win_amt, True)
        
        img = draw_penalty_card(game["name"], game["av"], result, user_choice, bot_choice)
        bot.send_json({
            "handler":"chatroommessage",
            "roomid":room_id,
            "type":"image",
            "url":utils.upload(bot, img),
            "text":result
        })
        
        if result == "GOAL":
            bot.send_message(room_id, f"🥅 GOOAAALLL!!! @{game['name']} won {win_amt} CHIPS!")
        else:
            bot.send_message(room_id, f"🧤 SAVED! @{game['name']} lost the bet.")

        with games_lock: penalty_games.pop(room_id, None)
        return True

    # 3. Stop Command
    if cmd == "stop" and game:
        if uid == game["uid"] or user.lower() == "yasin":
            with games_lock: penalty_games.pop(room_id, None)
            bot.send_message(room_id, "🛑 Game stopped.")
        return True

    return False

# Cleanup loop for inactive games
def auto_clean():
    while True:
        time.sleep(30)
        now = time.time()
        with games_lock:
            for rid in list(penalty_games.keys()):
                if now - penalty_games[rid]["time"] > 60:
                    penalty_games.pop(rid, None)
threading.Thread(target=auto_clean, daemon=True).start()
