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
    print("[PenaltyStrike] Sports Engine Ready. Command: !pk")

# ==========================================
# 🖼️ ROBUST AVATAR ENGINE
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

# ==========================================
# 🖌️ CINEMATIC RENDERER (1:1 Ratio)
# ==========================================

def draw_penalty_board(username, user_av, result="VS", user_pos=None, bot_pos=None):
    W, H = 700, 700
    # 1. Base Turf Gradient
    base = utils.get_gradient(W, H, (10, 40, 10), (20, 80, 20))
    img = Image.new('RGBA', (W, H), (0,0,0,0))
    img.paste(base, (0,0))
    d = ImageDraw.Draw(img)

    # 2. DiceBear Shapes Background Texture
    for _ in range(3):
        shape_url = f"https://api.dicebear.com/9.x/shapes/png?seed={random.randint(1,9999)}&size=300"
        shape = get_robust_avatar(shape_url, "bg_shape")
        if shape:
            shape.putalpha(20) 
            img.paste(shape, (random.randint(-50, 450), random.randint(-50, 450)), shape)

    # 3. Outer Card Border
    border_col = "#FFD700" if result == "GOAL" else "#FFFFFF"
    if result == "SAVED": border_col = "#FF4444"
    d.rounded_rectangle([10, 10, W-10, H-10], radius=50, outline=border_col, width=6)

    # 4. Neon Goal Post
    gx1, gy1, gx2, gy2 = 120, 160, 580, 460
    d.rectangle([gx1, gy1, gx2, gy2], outline="white", width=6)
    # Net lines
    for i in range(gx1, gx2, 25): d.line([i, gy1, i, gy2], fill=(255,255,255,30), width=1)
    for i in range(gy1, gy2, 25): d.line([gx1, i, gx2, i], fill=(255,255,255,30), width=1)

    # 5. Position Mapping
    pos_map = {1: (gx1+30, gy1+80), 2: (W//2-85, gy1+80), 3: (gx2-190, gy1+80)}
    ball_map = {1: (gx1+70, gy1+140), 2: (W//2-45, gy2-100), 3: (gx2-150, gy1+140)}

    # 6. Bot (Goalkeeper) with Circle Highlight
    bot_av = get_robust_avatar(None, "GOALIE")
    bot_av = bot_av.resize((170, 170))
    b_xy = pos_map.get(bot_pos, (W//2-85, gy1+80))
    
    g_mask = Image.new('L', (170, 170), 0)
    ImageDraw.Draw(g_mask).ellipse((0, 0, 170, 170), fill=255)
    img.paste(bot_av, b_xy, g_mask)
    d.ellipse([b_xy[0]-2, b_xy[1]-2, b_xy[0]+172, b_xy[1]+172], outline=border_col, width=3)

    # 7. Ball & Goal Celebration Smoke
    if user_pos:
        bx, by = ball_map.get(user_pos)
        if result == "GOAL":
            smoke_layer = Image.new('RGBA', (W, H), (0,0,0,0))
            sd = ImageDraw.Draw(smoke_layer)
            for _ in range(12):
                sx, sy = bx + random.randint(-40, 40), by + random.randint(-40, 40)
                sr = random.randint(30, 70)
                sd.ellipse([sx, sy, sx+sr, sy+sr], fill=(255, 255, 255, 50))
            smoke_layer = smoke_layer.filter(ImageFilter.GaussianBlur(15))
            img = Image.alpha_composite(img, smoke_layer)
            d = ImageDraw.Draw(img)

        ball = utils.get_emoji("⚽", size=90)
        img.paste(ball, (bx, by), ball)

    # 8. Striker DP with Triple Glow Ring
    u_av = get_robust_avatar(user_av, username)
    u_av = u_av.resize((140, 140))
    u_mask = Image.new('L', (140, 140), 0)
    ImageDraw.Draw(u_mask).ellipse((0, 0, 140, 140), fill=255)
    
    ux, uy = 40, 520
    d.ellipse([ux-8, uy-8, ux+148, uy+148], outline=(255, 215, 0, 100), width=10) # Glow
    d.ellipse([ux-3, uy-3, ux+143, uy+143], outline="#FFD700", width=4)         # Gold
    img.paste(u_av, (ux, uy), u_mask)
    utils.write_text(d, (ux+70, uy+160), username.upper(), size=22, align="center", col="white", shadow=True)

    # 9. Result Overlay Text
    if result != "VS":
        overlay = Image.new('RGBA', (W, H), (0,0,0,165))
        img = Image.alpha_composite(img, overlay)
        d = ImageDraw.Draw(img)
        res_col = "#00FF00" if result == "GOAL" else "#FF4444"
        utils.write_text(d, (W//2, H//2 - 30), result, size=140, align="center", col=res_col, shadow=True)
        utils.write_text(d, (W//2, H//2 + 90), "TYPE !PK TO REMATCH", size=28, align="center", col="white")

    # Round Corners for the final card
    mask = Image.new('L', (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0,0,W,H], radius=50, fill=255)
    final = Image.new('RGBA', (W, H), (0,0,0,0))
    final.paste(img, (0,0), mask)
    return final

# ==========================================
# ⚙️ HANDLER (Updated Commands)
# ==========================================

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    uid = str(data.get('userid', user))
    av_url = data.get("avatar")

    with games_lock:
        game = penalty_games.get(room_id)

    # 1. Start Game (!pk 500)
    if cmd == "pk":
        if game: return True
        try:
            bet = int(args[0]) if args and args[0].isdigit() else 500
            if bet < 100:
                bot.send_message(room_id, "❌ Min bet is 100 CHIPS")
                return True
            
            # Deduct Chips
            add_game_result(uid, user, "penalty", -bet, False)
            
            with games_lock:
                penalty_games[room_id] = {"uid": uid, "name": user, "av": av_url, "bet": bet, "time": time.time()}
            
            img = draw_penalty_board(user, av_url)
            bot.send_json({"handler":"chatroommessage","roomid":room_id,"type":"image","url":utils.upload(bot, img),"text":"MATCH START"})
            bot.send_message(room_id, f"⚽ @{user}, Select target:\n1️⃣ Left | 2️⃣ Center | 3️⃣ Right")
        except: pass
        return True

    # 2. Direction Selection (1, 2, 3)
    if cmd in ["1", "2", "3"] and game:
        if uid != game["uid"]: return False
        
        user_choice = int(cmd)
        bot_choice = random.randint(1, 3)
        
        result = "GOAL" if user_choice != bot_choice else "SAVED"
        win_amt = game["bet"] * 2 if result == "GOAL" else 0
        
        if win_amt > 0:
            add_game_result(uid, game["name"], "penalty", win_amt, True)
        
        img = draw_penalty_board(game["name"], game["av"], result, user_choice, bot_choice)
        bot.send_json({"handler":"chatroommessage","roomid":room_id,"type":"image","url":utils.upload(bot, img),"text":result})
        
        if result == "GOAL":
            bot.send_message(room_id, f"🥅 **GOOOAAALLL!!!** @{game['name']} won {win_amt} CHIPS!")
        else:
            bot.send_message(room_id, f"🧤 **SAVED!** Hard luck @{game['name']}.")

        with games_lock: penalty_games.pop(room_id, None)
        return True

    # 3. Stop Game
    if cmd == "stop" and game:
        if uid == game["uid"] or user.lower() == "yasin":
            with games_lock: penalty_games.pop(room_id, None)
            bot.send_message(room_id, "🛑 Game stopped.")
        return True

    return False

# Cleanup loop
def auto_clean():
    while True:
        time.sleep(30)
        now = time.time()
        with games_lock:
            for rid in list(penalty_games.keys()):
                if now - penalty_games[rid]["time"] > 60:
                    penalty_games.pop(rid, None)
threading.Thread(target=auto_clean, daemon=True).start()
