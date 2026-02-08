import threading
import time
import random
import io
import requests
from PIL import Image, ImageDraw, ImageOps, ImageFilter
import db
import utils

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
WIN_SCORE_REWARD = 50
GAME_TIMEOUT = 60 # 60 seconds to take a shot

# Global Registry for Room Isolation
PENALTY_GAMES = {}
PENALTY_LOCK = threading.Lock()

def setup(bot):
    """Howdies Plugin Loader confirmation"""
    print("[PenaltyStrike-HD] Pro Visuals Engine Loaded & Ready.")

# ==========================================
# 🖼️ AVATAR & GRAPHICS HELPERS
# ==========================================

def get_avatar(user_id, username, avatar_url=None):
    """Robust Avatar Fetch: Direct -> ID -> Dicebear"""
    if avatar_url and str(avatar_url) != "None":
        try:
            r = requests.get(avatar_url, timeout=3, headers={'User-Agent': 'Mozilla/5.0'})
            if r.status_code == 200:
                return Image.open(io.BytesIO(r.content)).convert("RGBA")
        except: pass

    try:
        url = f"https://api.howdies.app/api/avatar/{user_id}"
        r = requests.get(url, timeout=3)
        if r.status_code == 200:
            return Image.open(io.BytesIO(r.content)).convert("RGBA")
    except: pass

    try:
        url = f"https://api.dicebear.com/9.x/adventurer/png?seed={username}"
        r = requests.get(url, timeout=3)
        return Image.open(io.BytesIO(r.content)).convert("RGBA")
    except:
        return Image.new('RGBA', (260, 260), (30, 30, 60))

def apply_round_corners(img, radius):
    mask = Image.new("L", img.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0) + img.size, radius, fill=255)
    out = Image.new("RGBA", img.size)
    out.paste(img, (0, 0), mask)
    return out

# ==========================================
# 🎨 PREMIUM GRAPHICS ENGINE
# ==========================================

def draw_penalty_card(username, user_id, user_av, result="VS", user_pos=None, bot_pos=None, win_amt=0):
    W, H = 700, 700
    # Turf Green Gradient
    base = utils.get_gradient(W, H, (10, 40, 10), (20, 80, 20))
    img = Image.new('RGBA', (W, H))
    img.paste(base, (0,0))
    d = ImageDraw.Draw(img)

    # Rounded Card Border
    border_col = "#FFFFFF"
    if result == "GOAL": border_col = "#00FF00"
    if result == "SAVED": border_col = "#FF0000"
    d.rounded_rectangle([10, 10, W-10, H-10], radius=50, outline=border_col, width=6)

    # 1. Header
    utils.write_text(d, (W//2, 60), "PENALTY STRIKE", size=50, align="center", col="white", shadow=True)

    # 2. Goal Post
    gx1, gy1, gx2, gy2 = 120, 160, 580, 460
    d.rectangle([gx1, gy1, gx2, gy2], outline="white", width=8)
    for i in range(gx1, gx2, 30): d.line([i, gy1, i, gy2], fill=(255,255,255,40), width=1)
    for i in range(gy1, gy2, 30): d.line([gx1, i, gx2, i], fill=(255,255,255,40), width=1)

    # 3. Goalkeeper (Bot)
    # 1: Left, 2: Center, 3: Right
    b_x_map = {1: gx1 + 50, 2: W//2 - 80, 3: gx2 - 210}
    bx = b_x_map.get(bot_pos, W//2 - 80)
    
    goalie_img = Image.new('RGBA', (160, 160), (0,0,0,0))
    gd = ImageDraw.Draw(goalie_img)
    gd.ellipse([0, 0, 160, 160], fill="#333", outline="#FFD700", width=4)
    utils.write_text(gd, (80, 80), "GK", size=60, col="#FFD700", align="center")
    img.paste(goalie_img, (bx, 220), goalie_img)

    # 4. Ball Position
    if user_pos:
        ball_x_map = {1: gx1 + 60, 2: W//2 - 40, 3: gx2 - 140}
        ball_y = gy1 + 100 if result == "GOAL" else gy1 + 200
        # Simple Ball Drawing
        d.ellipse([ball_x_map[user_pos], ball_y, ball_x_map[user_pos]+80, ball_y+80], fill="white", outline="black", width=2)

    # 5. Striker Info (Bottom)
    av = get_avatar(user_id, username, user_av).resize((130, 130))
    av_mask = Image.new('L', (130, 130), 0)
    ImageDraw.Draw(av_mask).ellipse((0, 0, 130, 130), fill=255)
    img.paste(av, (40, 520), av_mask)
    d.ellipse([40, 520, 170, 650], outline="white", width=4)
    utils.write_text(d, (105, 665), username.upper(), size=25, align="center", col="white")

    # 6. Result Big Text
    if result != "VS":
        res_col = "#00FF00" if result == "GOAL" else "#FF0000"
        utils.write_text(d, (W//2, H//2), result, size=130, align="center", col=res_col, shadow=True)
        if result == "GOAL":
            # WON CHIPS in RED as requested
            utils.write_text(d, (W//2, H//2 + 110), f"WON {win_amt} CHIPS", size=35, align="center", col="#FF0000")

    return apply_round_corners(img, 50)

# ==========================================
# 📦 GAME LOGIC BOX
# ==========================================

class PenaltyBox:
    def __init__(self, uid, name, av, bet):
        self.uid = uid
        self.name = name
        self.av = av
        self.bet = bet
        self.last_act = time.time()

def cleanup(rid):
    with PENALTY_LOCK:
        if rid in PENALTY_GAMES: del PENALTY_GAMES[rid]

# ==========================================
# 📡 COMMAND HANDLER
# ==========================================

def handle_command(bot, cmd, room_id, user, args, data):
    uid = str(data.get('userid'))
    av_url = data.get('avatar')

    # 1. ADMIN STOP
    if cmd == "stoppk" and bot.is_boss(user, uid):
        cleanup(room_id)
        bot.send_message(room_id, "🛑 Penalty match stopped by Boss.")
        return True

    # 2. START GAME (!pk <bet>)
    if cmd == "pk":
        if room_id in PENALTY_GAMES:
            bot.send_message(room_id, "⚠️ A match is already live."); return True
        
        try:
            bet = int(args[0]) if args and args[0].isdigit() else 500
            if bet < 100:
                bot.send_message(room_id, "❌ Minimum bet is 100."); return True
            
            # ECONOMY: Atomic check and deduct
            if not db.check_and_deduct_chips(uid, user, bet):
                bot.send_message(room_id, f"❌ @{user}, you need {bet} chips!"); return True
            
            with PENALTY_LOCK:
                PENALTY_GAMES[room_id] = PenaltyBox(uid, user, av_url, bet)
            
            img = draw_penalty_card(user, uid, av_url)
            url = bot.upload_to_server(img)
            bot.send_json({"handler":"chatroommessage","roomid":room_id,"type":"image","url":url,"text":f"Match Started! Bet: {bet}"})
            bot.send_message(room_id, f"⚽ @{user}, Shot direction?\nType: 1 (Left) | 2 (Center) | 3 (Right)")
            return True
        except: traceback.print_exc(); return False

    # 3. SHOOTING (Numeric Input)
    if cmd in ["1", "2", "3"]:
        with PENALTY_LOCK:
            game = PENALTY_GAMES.get(room_id)
        
        if not game or game.uid != uid: return False
        
        # Timeout Check
        if time.time() - game.last_act > GAME_TIMEOUT:
            bot.send_message(room_id, "⏰ Time's up! Match void.")
            cleanup(room_id); return True

        user_choice = int(cmd)
        bot_choice = random.randint(1, 3)
        
        # Logic: If user shoots where bot doesn't jump -> GOAL
        is_goal = (user_choice != bot_choice)
        result = "GOAL" if is_goal else "SAVED"
        win_amt = game.bet * 2 if is_goal else 0
        
        # DATABASE SYNC
        if is_goal:
            # add_game_result handles score + chips profit
            db.add_game_result(uid, game.name, "penalty", win_amt - game.bet, True, WIN_SCORE_REWARD)
        else:
            db.add_game_result(uid, game.name, "penalty", -game.bet, False, 0)

        # Render Final Card
        img = draw_penalty_card(game.name, uid, game.av, result, user_choice, bot_choice, win_amt)
        url = bot.upload_to_server(img)
        
        bot.send_json({"handler":"chatroommessage","roomid":room_id,"type":"image","url":url,"text":result})
        
        if is_goal:
            bot.send_message(room_id, f"🥅 **GOAL!** @{game.name} won {win_amt} chips!")
        else:
            bot.send_message(room_id, f"🧤 **SAVED!** Goalkeeper caught it. Lost {game.bet} chips.")

        cleanup(room_id)
        return True

    return False
