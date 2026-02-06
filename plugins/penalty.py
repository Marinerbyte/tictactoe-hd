import time
import random
import threading
import sys
import os
import requests
import io
from PIL import Image, ImageDraw, ImageFilter
import utils
import db

# --- GLOBAL STATE ---
penalty_games = {} 
games_lock = threading.Lock()
AVATAR_CACHE = {}

def setup(bot_ref):
    print("[PenaltyStrike] Updated to Points & Chips System.")

def get_robust_avatar(avatar_url, username):
    if avatar_url in AVATAR_CACHE: return AVATAR_CACHE[avatar_url].copy()
    try:
        if avatar_url:
            r = requests.get(avatar_url, timeout=5)
            if r.status_code == 200:
                img = Image.open(io.BytesIO(r.content)).convert("RGBA")
                AVATAR_CACHE[avatar_url] = img
                return img.copy()
    except: pass
    return Image.new("RGBA", (100, 100), (30, 30, 35))

def draw_penalty_board(username, user_av, result="VS", user_pos=None, bot_pos=None, win_amt=0, pts_amt=0):
    W, H = 700, 700
    img = utils.get_gradient(W, H, (10, 40, 10), (20, 80, 20))
    d = ImageDraw.Draw(img)
    
    border_col = "#FFD700" if result == "GOAL" else "#FFFFFF"
    if result == "SAVED": border_col = "#FF4444"
    d.rounded_rectangle([10, 10, W-10, H-10], radius=50, outline=border_col, width=6)

    # Goal Area
    gx1, gy1, gx2, gy2 = 120, 160, 580, 460
    d.rectangle([gx1, gy1, gx2, gy2], outline="white", width=6)

    # Goalkeeper (Bot)
    b_xy = {1: (150, 240), 2: (265, 240), 3: (380, 240)}.get(bot_pos, (265, 240))
    d.ellipse([b_xy[0], b_xy[1], b_xy[0]+170, b_xy[1]+170], fill="#333", outline=border_col, width=3)
    
    # Result Overlay
    if result != "VS":
        res_col = "#00FF00" if result == "GOAL" else "#FF4444"
        utils.write_text(d, (W//2, H//2), result, size=120, align="center", col=res_col, shadow=True)
        if result == "GOAL":
            utils.write_text(d, (W//2, H//2 + 100), f"+{win_amt} Chips | +{pts_amt} Points", size=30, align="center", col="white")
    else:
        utils.write_text(d, (W//2, 80), f"PLAYER: {username.upper()}", size=30, align="center", col="white")

    return img

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    uid = str(data.get('userid', user))
    av_id = data.get("avatar")
    av_url = f"https://cdn.howdies.app/avatar?image={av_id}" if av_id else None

    with games_lock:
        game = penalty_games.get(room_id)

    # 1. Start Game (!pk <bet>)
    if cmd == "pk":
        if game: return True
        try:
            bet = int(args[0]) if args and args[0].isdigit() else 50
            
            # --- ECONOMY CHECK & DEDUCTION ---
            # Hum pehle hi chips kaat rahe hain
            if db.check_and_deduct_chips(uid, user, bet):
                with games_lock:
                    penalty_games[room_id] = {"uid": uid, "name": user, "av": av_url, "bet": bet, "time": time.time()}
                
                img = draw_penalty_board(user, av_url)
                bot.send_json({"handler":"chatroommessage","roomid":room_id,"type":"image","url":utils.upload(bot, img),"text":"MATCH START"})
                bot.send_message(room_id, f"⚽ @{user}, Shot direction? (1, 2, 3)\nBet: {bet} Chips")
            else:
                bot.send_message(room_id, f"❌ @{user}, Chips nahi hain! (Need {bet})")
        except Exception as e:
            print(f"Error pk: {e}")
        return True

    # 2. Shooting Logic (1, 2, 3)
    if cmd in ["1", "2", "3"] and game:
        if uid != game["uid"]: return False
        
        user_choice = int(cmd)
        bot_choice = random.randint(1, 3)
        is_goal = (user_choice != bot_choice)
        result = "GOAL" if is_goal else "SAVED"
        
        # --- REWARD CALCULATION (BOT RULES) ---
        win_chips = 0
        win_points = 0
        
        if is_goal:
            win_points = 50 # Fixed Points
            # Chips limited to 100 as per your rule
            win_chips = min(game["bet"] * 2, 100) 
            
            # --- UPDATE DATABASE ---
            # Chips_won is the amount we ADD back to user
            db.add_game_result(uid, game["name"], "penalty", win_chips, True, win_points)
        else:
            # Loser: No points, no chips back (already deducted)
            db.add_game_result(uid, game["name"], "penalty", 0, False, 0)

        # Render and Send
        img = draw_penalty_board(game["name"], game["av"], result, user_choice, bot_choice, win_chips, win_points)
        bot.send_json({"handler":"chatroommessage","roomid":room_id,"type":"image","url":utils.upload(bot, img),"text":result})
        
        if is_goal:
            bot.send_message(room_id, f"🥅 **GOAL!** @{game['name']} jeet gaya!\nReceived: {win_chips} Chips & {win_points} Points.")
        else:
            bot.send_message(room_id, f"🧤 **SAVED!** @{game['name']} haar gaya. Chips gaye!")

        with games_lock: penalty_games.pop(room_id, None)
        return True

    return False
