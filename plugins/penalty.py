import threading
import time
import random
import io
import requests
from PIL import Image, ImageDraw
import db
import utils

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
WIN_SCORE_REWARD = 50
GAME_TIMEOUT = 60 # 60 Seconds to shoot

# Global Registry
GAMES = {} 
GAMES_LOCK = threading.Lock()

def setup(bot):
    print("[Penalty] Premium Sports Engine Loaded.")

# ==========================================
# 🖼️ AVATAR & GRAPHICS SYSTEM
# ==========================================

def get_avatar(user_id, name):
    """Robust Avatar Fetcher (Same as TTT)"""
    try:
        url = f"https://api.howdies.app/api/avatar/{user_id}"
        resp = requests.get(url, timeout=4)
        if resp.status_code == 200:
            return Image.open(io.BytesIO(resp.content)).convert("RGBA")
        raise Exception
    except:
        img = Image.new('RGBA', (260, 260), (30, 30, 60))
        d = ImageDraw.Draw(img)
        utils.write_text(d, (130, 130), name[0].upper(), size=120, col="white", align="center")
        return img

def draw_penalty_board(username, result="VS", user_choice=None, bot_choice=None, win_amt=0, user_id=None):
    W, H = 700, 700
    # Stadium Grass Gradient
    base = utils.get_gradient(W, H, (10, 50, 20), (20, 90, 40))
    img = Image.new('RGBA', (W, H))
    img.paste(base, (0, 0))
    d = ImageDraw.Draw(img)

    # Goal Post (White Border)
    d.rounded_rectangle([50, 50, 650, 450], radius=10, outline="white", width=8)
    # Net pattern
    for i in range(60, 640, 30):
        d.line([(i, 50), (i, 450)], fill=(255, 255, 255, 50), width=1)
    for i in range(60, 440, 30):
        d.line([(50, i), (650, i)], fill=(255, 255, 255, 50), width=1)

    # Goalkeeper (Bot) Position
    bot_x = 350 # Center default
    if bot_choice == 1: bot_x = 180 # Left
    if bot_choice == 3: bot_x = 520 # Right
    
    # Draw Goalkeeper (Red Jersey)
    d.ellipse([bot_x-40, 250, bot_x+40, 330], fill="#FF4444", outline="white", width=2)
    d.rectangle([bot_x-20, 330, bot_x+20, 400], fill="#FF4444")

    # Football (User Shot)
    if user_choice:
        ball_x = 350
        if user_choice == 1: ball_x = 180
        if user_choice == 3: ball_x = 520
        # Ball
        d.ellipse([ball_x-25, 380, ball_x+25, 430], fill="white", outline="black", width=2)

    # User Avatar Bubble (Bottom Center)
    if user_id:
        av = get_avatar(user_id, username).resize((120, 120))
        mask = Image.new('L', (120, 120), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, 120, 120), fill=255)
        img.paste(av, (290, 550), mask)

    # Result Overlay
    if result == "GOAL":
        utils.write_text(d, (W//2, 200), "GOAL!", size=100, align="center", col="#00FF00", shadow=True)
        utils.write_text(d, (W//2, 500), f"WON {win_amt} CHIPS", size=40, align="center", col="#FFD700", shadow=True)
    elif result == "SAVED":
        utils.write_text(d, (W//2, 200), "SAVED!", size=100, align="center", col="#FF0000", shadow=True)
    else:
        # Initial Instructions
        utils.write_text(d, (W//2, 500), f"PLAYER: @{username.upper()}", size=35, align="center", col="white")
        utils.write_text(d, (W//2, 630), "AIM: 1 (Left) | 2 (Center) | 3 (Right)", size=25, align="center", col="#AAAAAA")

    return img

# ==========================================
# 📦 GAME LOGIC
# ==========================================

class PenaltyGame:
    def __init__(self, uid, name, bet):
        self.uid = uid
        self.name = name
        self.bet = bet
        self.start_time = time.time()

def cleanup(room_id):
    with GAMES_LOCK:
        if room_id in GAMES: del GAMES[room_id]

def handle_command(bot, cmd, room_id, user, args, data):
    uid = str(data.get('userid'))
    
    # 1. BOSS STOP (!endpk)
    if cmd == "endpk" and bot.is_boss(user, uid):
        if room_id in GAMES:
            cleanup(room_id)
            bot.send_message(room_id, "🛑 Boss stopped the match.")
        return True

    # 2. START GAME (!pk <bet>)
    if cmd == "pk":
        if room_id in GAMES:
            bot.send_message(room_id, "⚠️ Match in progress."); return True
        
        try:
            bet = int(args[0]) if args else 100
            if bet <= 0: return True
            
            # ECONOMY: Check & Deduct
            if not db.check_and_deduct_chips(uid, user, bet):
                bot.send_message(room_id, f"❌ You need {bet} chips to play!")
                return True
                
            with GAMES_LOCK:
                GAMES[room_id] = PenaltyGame(uid, user, bet)
            
            img = draw_penalty_board(user, "VS", user_id=uid)
            url = bot.upload_to_server(img)
            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": url, "text": f"⚽ Penalty Shootout! Bet: {bet}"})
            return True
            
        except: return False

    # 3. SHOOT (1, 2, 3)
    if cmd in ["1", "2", "3"]:
        g = GAMES.get(room_id)
        if not g: return False
        
        # Concurrency: Check User
        if g.uid != uid: return False
        
        # Timeout Check
        if time.time() - g.start_time > GAME_TIMEOUT:
            cleanup(room_id)
            bot.send_message(room_id, "⏰ Time Up! Goalkeeper left.")
            return True

        # LOGIC
        user_shot = int(cmd)
        bot_save = random.randint(1, 3)
        
        # Win Condition: User shot != Bot save position
        is_goal = (user_shot != bot_save)
        
        if is_goal:
            win_chips = g.bet * 2
            win_score = WIN_SCORE_REWARD
            result_text = "GOAL"
            
            # DB UPDATE: Net profit (Total - Bet)
            # Kyunki bet pehle hi kat chuki hai, hum Total Winnings add nahi karenge
            # Hum seedha wallet update karenge
            
            # Wait! DB Logic:
            # check_and_deduct ne bet kaat li.
            # Agar jeeta, toh usse (Bet * 2) wapas milna chahiye.
            # db.add_game_result balance update kar dega.
            
            db.add_game_result(uid, user, "penalty", win_chips, is_win=True, points_reward=win_score)
            
            msg = f"⚽ **GOAL!** You won {win_chips} chips!"
        else:
            win_chips = 0
            win_score = 0
            result_text = "SAVED"
            # Loss record
            db.add_game_result(uid, user, "penalty", 0, is_win=False)
            msg = f"🧤 **SAVED!** Goalkeeper caught it. You lost {g.bet} chips."

        # Graphics
        img = draw_penalty_board(user, result_text, user_shot, bot_save, win_chips, uid)
        url = bot.upload_to_server(img)
        
        bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": url, "text": msg})
        
        cleanup(room_id)
        return True

    return False
