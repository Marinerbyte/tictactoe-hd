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
    import db # Naye foundation wala DB
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
    print("[PenaltyStrike] Sports Engine Linked to Foundation DB.")

# ==========================================
# 💰 CURRENCY FORMATTER
# ==========================================
def format_val(n):
    """10000 -> 10k logic"""
    if n >= 10000:
        return f"{n // 1000}k"
    return f"{n:,}"

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
def draw_penalty_board(username, user_av, result="VS", user_pos=None, bot_pos=None, win_amt=0):
    W, H = 700, 700
    base = utils.get_gradient(W, H, (10, 40, 10), (20, 80, 20))
    img = Image.new('RGBA', (W, H), (0,0,0,0))
    img.paste(base, (0,0))
    d = ImageDraw.Draw(img)

    # DiceBear Background Texture
    for _ in range(3):
        shape = get_robust_avatar(f"https://api.dicebear.com/9.x/shapes/png?seed={random.randint(1,999)}&size=300", "bg")
        if shape: shape.putalpha(20); img.paste(shape, (random.randint(-50, 450), random.randint(-50, 450)), shape)

    # Border Color
    border_col = "#FFD700" if result == "GOAL" else "#FFFFFF"
    if result == "SAVED": border_col = "#FF4444"
    d.rounded_rectangle([10, 10, W-10, H-10], radius=50, outline=border_col, width=6)

    # Goal Area
    gx1, gy1, gx2, gy2 = 120, 160, 580, 460
    d.rectangle([gx1, gy1, gx2, gy2], outline="white", width=6)
    for i in range(gx1, gx2, 25): d.line([i, gy1, i, gy2], fill=(255,255,255,30), width=1)
    for i in range(gy1, gy2, 25): d.line([gx1, i, gx2, i], fill=(255,255,255,30), width=1)

    pos_map = {1: (gx1+30, gy1+80), 2: (W//2-85, gy1+80), 3: (gx2-190, gy1+80)}
    ball_map = {1: (gx1+70, gy1+140), 2: (W//2-45, gy2-100), 3: (gx2-150, gy1+140)}

    # Goalkeeper (Bot)
    bot_av = get_robust_avatar(None, "GOALIE").resize((170, 170))
    b_xy = pos_map.get(bot_pos, (W//2-85, gy1+80))
    g_mask = Image.new('L', (170, 170), 0)
    ImageDraw.Draw(g_mask).ellipse((0, 0, 170, 170), fill=255)
    img.paste(bot_av, b_xy, g_mask)
    d.ellipse([b_xy[0]-2, b_xy[1]-2, b_xy[0]+172, b_xy[1]+172], outline=border_col, width=3)

    # Ball & Smoke
    if user_pos:
        bx, by = ball_map.get(user_pos)
        if result == "GOAL":
            smoke = Image.new('RGBA', (W, H), (0,0,0,0))
            sd = ImageDraw.Draw(smoke)
            for _ in range(12):
                sx, sy = bx + random.randint(-40, 40), by + random.randint(-40, 40)
                sr = random.randint(30, 70)
                sd.ellipse([sx, sy, sx+sr, sy+sr], fill=(255, 255, 255, 50))
            img = Image.alpha_composite(img, smoke.filter(ImageFilter.GaussianBlur(15)))
            d = ImageDraw.Draw(img)
        ball = utils.get_emoji("⚽", size=90)
        img.paste(ball, (bx, by), ball)

    # User DP with Triple Glow Ring
    u_av = get_robust_avatar(user_av, username).resize((140, 140))
    u_mask = Image.new('L', (140, 140), 0)
    ImageDraw.Draw(u_mask).ellipse((0, 0, 140, 140), fill=255)
    ux, uy = 40, 520
    d.ellipse([ux-8, uy-8, ux+148, uy+148], outline=(255, 215, 0, 100), width=10)
    d.ellipse([ux-3, uy-3, ux+143, uy+143], outline="#FFD700", width=4)
    img.paste(u_av, (ux, uy), u_mask)
    utils.write_text(d, (ux+70, uy+160), username.upper(), size=22, align="center", col="white", shadow=True)

    # Result Big Text
    if result != "VS":
        overlay = Image.new('RGBA', (W, H), (0,0,0,165))
        img = Image.alpha_composite(img, overlay); d = ImageDraw.Draw(img)
        res_col = "#00FF00" if result == "GOAL" else "#FF4444"
        utils.write_text(d, (W//2, H//2 - 30), result, size=140, align="center", col=res_col, shadow=True)
        
        # Display Reward in 'k' format
        msg = "TYPE !PK TO REMATCH"
        if result == "GOAL": msg = f"WON {format_val(win_amt)} CHIPS"
        utils.write_text(d, (W//2, H//2 + 90), msg, size=35, align="center", col="white")

    # Corner Rounding
    mask = Image.new('L', (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0,0,W,H], radius=50, fill=255)
    final = Image.new('RGBA', (W, H), (0,0,0,0))
    final.paste(img, (0,0), mask)
    return final

# ==========================================
# ⚙️ HANDLER
# ==========================================
def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    uid = str(data.get('userid', user))
    av_id = data.get("avatar")
    av_url = f"https://cdn.howdies.app/avatar?image={av_id}" if av_id else None

    with games_lock:
        game = penalty_games.get(room_id)

    # 1. Start Game
    if cmd == "pk":
        if game: return True
        try:
            bet = int(args[0]) if args and args[0].isdigit() else 500
            if bet < 500:
                bot.send_message(room_id, "❌ Minimum bet is 500 CHIPS to play!")
                return True
            
            # --- FOUNDATION DB CALL: Bet Deduction ---
            if db.update_balance(uid, user, -bet):
                with games_lock:
                    penalty_games[room_id] = {"uid": uid, "name": user, "av": av_url, "bet": bet, "time": time.time()}
                
                img = draw_penalty_board(user, av_url)
                bot.send_json({"handler":"chatroommessage","roomid":room_id,"type":"image","url":utils.upload(bot, img),"text":"MATCH START"})
                bot.send_message(room_id, f"⚽ @{user}, Where do you want to shoot? (1, 2, 3)\nBet: {format_val(bet)} CHIPS")
            else:
                bot.send_message(room_id, "❌ Database error during betting.")
        except: pass
        return True

    # 2. Strike Logic
    if cmd in ["1", "2", "3"] and game:
        if uid != game["uid"]: return False
        
        user_choice = int(cmd)
        bot_choice = random.randint(1, 3)
        result = "GOAL" if user_choice != bot_choice else "SAVED"
        
        is_win = (result == "GOAL")
        win_amt = game["bet"] * 2 if is_win else 0
        
        # --- FOUNDATION DB CALL: Add Result (Chips + Points + Stats) ---
        # Note: If loss, we send 0 profit but is_win=False to log the loss
        db.add_game_result(uid, game["name"], "penalty", win_amt, is_win)
        
        img = draw_penalty_board(game["name"], game["av"], result, user_choice, bot_choice, win_amt)
        bot.send_json({"handler":"chatroommessage","roomid":room_id,"type":"image","url":utils.upload(bot, img),"text":result})
        
        if is_win:
            bot.send_message(room_id, f"🥅 **GOAL!** @{game['name']} scored and won {format_val(win_amt)} CHIPS!")
        else:
            bot.send_message(room_id, f"🧤 **SAVED!** @{game['name']} missed and lost {format_val(game['bet'])}.")

        with games_lock: penalty_games.pop(room_id, None)
        return True

    # 3. Stop
    if cmd == "stop" and game:
        if uid == game["uid"] or user.lower() == "yasin":
            with games_lock: penalty_games.pop(room_id, None)
            bot.send_message(room_id, "🛑 Session Stopped.")
        return True

    return False

# Auto Clean
def auto_clean():
    while True:
        time.sleep(30); now = time.time()
        with games_lock:
            for rid in list(penalty_games.keys()):
                if now - penalty_games[rid]["time"] > 60: penalty_games.pop(rid, None)
threading.Thread(target=auto_clean, daemon=True).start()
