import threading
import time
import random
import io
import requests
import math
from PIL import Image, ImageDraw, ImageOps, ImageFilter
import db
import utils

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
WIN_SCORE = 30
HEADS_URL = "https://www.dropbox.com/scl/fi/jxin556171p1jxc9ijjt8/file_00000000e1647209a0f1041e0faf6aa7.png?rlkey=qaho82a5zc2edarlyrn0pk0nd&st=syo1hqsh&dl=1"
TAILS_URL = "https://www.dropbox.com/scl/fi/0icyzmbn04dw1r2wburaw/file_00000000a67472099de1c5aa86bf3f9d.png?rlkey=9cy19hi5h704cy36onshi9wgr&st=8jts2yc9&dl=1"

COIN_CACHE = {}
AV_CACHE = {}

def setup(bot):
    print("[CoinFlip-HD] Animated GIF Illusion Engine Loaded.")

# ==========================================
# 🖼️ IMAGE FETCHERS
# ==========================================

def get_coin_img(side):
    if side in COIN_CACHE: return COIN_CACHE[side]
    url = HEADS_URL if side == "heads" else TAILS_URL
    try:
        r = requests.get(url, timeout=5)
        img = Image.open(io.BytesIO(r.content)).convert("RGBA")
        COIN_CACHE[side] = img
        return img
    except:
        return Image.new('RGBA', (300, 300), (50, 50, 50))

def get_avatar_robust(user_id, username, avatar_url=None):
    if user_id in AV_CACHE: return AV_CACHE[user_id].copy()
    try:
        url = avatar_url if avatar_url else f"https://api.howdies.app/api/avatar/{user_id}"
        r = requests.get(url, timeout=3)
        img = Image.open(io.BytesIO(r.content)).convert("RGBA")
    except:
        img = Image.new('RGBA', (200, 200), (30, 30, 60))
        d = ImageDraw.Draw(img)
        utils.write_text(d, (100, 100), username[0].upper(), size=80, col="white", align="center")
    AV_CACHE[user_id] = img
    return img.copy()

def apply_round_corners(img, radius):
    mask = Image.new("L", img.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0) + img.size, radius, fill=255)
    out = Image.new("RGBA", img.size)
    out.paste(img, (0, 0), mask)
    return out

# ==========================================
# 🌀 GIF GENERATOR (The 3D Illusion)
# ==========================================

def create_flip_gif(final_side):
    W, H = 500, 500
    frames = []
    h_img = get_coin_img("heads").resize((250, 250))
    t_img = get_coin_img("tails").resize((250, 250))
    
    # Generate 12 frames for a smooth flip
    for i in range(12):
        frame = utils.get_gradient(W, H, (10, 40, 10), (20, 80, 20)) # Penalty Turf
        d = ImageDraw.Draw(frame)
        d.rounded_rectangle([5, 5, W-5, H-5], radius=40, outline="white", width=4)
        
        # Calculate rotation width (Cosine wave for 3D effect)
        angle = (i / 12.0) * math.pi * 4 # 2 full rotations
        width_factor = abs(math.cos(angle))
        current_img = h_img if math.cos(angle) > 0 else t_img
        
        new_w = max(1, int(250 * width_factor))
        resized_coin = current_img.resize((new_w, 250), Image.Resampling.LANCZOS)
        
        # Paste centered
        frame.paste(resized_coin, (W//2 - new_w//2, H//2 - 125), resized_coin)
        frames.append(frame)
        
    out = io.BytesIO()
    frames[0].save(out, format='GIF', save_all=True, append_images=frames[1:], duration=60, loop=0)
    return out.getvalue()

# ==========================================
# 🏆 RESULT CARD (Penalty Style)
# ==========================================

def draw_result_card(username, user_id, av_url, result_side, is_win, bet, win_amt):
    W, H = 700, 700
    base = utils.get_gradient(W, H, (10, 40, 10), (20, 80, 20)) # Penalty Turf
    img = Image.new('RGBA', (W, H))
    img.paste(base, (0,0))
    d = ImageDraw.Draw(img)

    border_col = "#00FF00" if is_win else "#FF0000"
    d.rounded_rectangle([10, 10, W-10, H-10], radius=50, outline=border_col, width=6)

    # Header
    utils.write_text(d, (W//2, 60), "COIN FLIP RESULT", size=45, align="center", col="white", shadow=True)

    # Result Coin
    coin_res = get_coin_img(result_side).resize((280, 280), Image.Resampling.LANCZOS)
    img.paste(coin_res, (W//2 - 140, 150), coin_res)

    # Winner/Loser Banner
    res_txt = "WINNER" if is_win else "LOOSER"
    utils.write_text(d, (W//2, 480), res_txt, size=80, align="center", col=border_col, shadow=True)

    # Player Info
    av = get_avatar_robust(user_id, username, av_url).resize((130, 130))
    av_mask = Image.new('L', (130, 130), 0)
    ImageDraw.Draw(av_mask).ellipse((0, 0, 130, 130), fill=255)
    img.paste(av, (40, 520), av_mask)
    d.ellipse([40, 520, 170, 650], outline="white", width=4)
    utils.write_text(d, (105, 665), username.upper(), size=25, align="center", col="white")

    # Chips & Score (RED TEXT)
    chips_txt = f"+{win_amt} Chips" if is_win else f"-{bet} Chips"
    utils.write_text(d, (W-50, 560), chips_txt, size=45, align="right", col="#FF0000") # RED
    
    if is_win:
        utils.write_text(d, (W-50, 620), f"+{WIN_SCORE} Score", size=30, align="right", col="#00F2FE")

    return apply_round_corners(img, 50)

# ==========================================
# 📡 HANDLER
# ==========================================

def handle_command(bot, cmd, room_id, user, args, data):
    uid = str(data.get('userid'))
    av_url = data.get('avatar')

    if cmd == "flip":
        if len(args) < 2:
            bot.send_message(room_id, "Usage: !flip <h/t> <amt>"); return True

        # Side Logic
        choice_in = args[0].lower()
        if choice_in in ['h', 'heads']: choice = "heads"
        elif choice_in in ['t', 'tails']: choice = "tails"
        else: return True

        try:
            bet = int(args[1])
            if bet < 100: bot.send_message(room_id, "❌ Min bet 100."); return True
            
            # ECONOMY
            if not db.check_and_deduct_chips(uid, user, bet):
                bot.send_message(room_id, "❌ Insufficient chips!"); return True

            result_side = random.choice(['heads', 'tails'])
            is_win = (choice == result_side)
            win_total = bet * 2 if is_win else 0

            # 1. SEND ANIMATED GIF (The Illusion)
            gif_data = create_flip_gif(result_side)
            gif_url = bot.upload_to_server(gif_data, file_type='gif')
            bot.send_json({"handler":"chatroommessage","roomid":room_id,"type":"image","url":gif_url,"text":"Flipping..."})

            # 2. WAIT AND SEND RESULT CARD
            def delayed_result():
                time.sleep(1.5) # Wait for GIF to play
                if is_win:
                    db.add_game_result(uid, user, "coinflip", win_total - bet, True, WIN_SCORE)
                else:
                    db.add_game_result(uid, user, "coinflip", -bet, False, 0)
                
                card = draw_result_card(user, uid, av_url, result_side, is_win, bet, win_total)
                card_url = bot.upload_to_server(card)
                bot.send_json({"handler":"chatroommessage","roomid":room_id,"type":"image","url":card_url,"text":f"{result_side.upper()}!"})

            threading.Thread(target=delayed_result).start()
            return True

        except: return True

    return False
