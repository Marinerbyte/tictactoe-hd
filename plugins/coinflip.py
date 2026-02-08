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
    print("[CoinFlip-HD] Lightweight High-Speed Engine Loaded.")

# --- HELPERS ---

def get_coin_img(side):
    if side in COIN_CACHE: return COIN_CACHE[side]
    url = HEADS_URL if side == "heads" else TAILS_URL
    try:
        r = requests.get(url, timeout=5)
        img = Image.open(io.BytesIO(r.content)).convert("RGBA")
        COIN_CACHE[side] = img
        return img
    except:
        return Image.new('RGBA', (200, 200), (50, 50, 50))

def get_avatar_robust(user_id, username, avatar_url=None):
    if user_id in AV_CACHE: return AV_CACHE[user_id].copy()
    try:
        url = avatar_url if avatar_url else f"https://api.howdies.app/api/avatar/{user_id}"
        r = requests.get(url, timeout=3)
        img = Image.open(io.BytesIO(r.content)).convert("RGBA")
    except:
        img = Image.new('RGBA', (150, 150), (40, 40, 70))
        d = ImageDraw.Draw(img)
        utils.write_text(d, (75, 75), username[0].upper() if username else "?", size=60, col="white", align="center")
    AV_CACHE[user_id] = img
    return img.copy()

def apply_round_corners(img, radius):
    mask = Image.new("L", img.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0) + img.size, radius=radius, fill=255)
    out = Image.new("RGBA", img.size)
    out.paste(img, (0, 0), mask)
    return out

# ==========================================
# 🌀 LIGHTWEIGHT GIF ENGINE (Jump & Pause)
# ==========================================

def create_flip_gif(final_side):
    W, H = 400, 400 # Optimized resolution
    frames = []
    h_img = get_coin_img("heads").resize((180, 180), Image.Resampling.LANCZOS)
    t_img = get_coin_img("tails").resize((180, 180), Image.Resampling.LANCZOS)
    
    anim_frames = 12 # Optimized frame count
    pause_frames = 6 
    
    for i in range(anim_frames + pause_frames):
        # Optimized gradient background
        frame = utils.get_gradient(W, H, (10, 40, 10), (20, 80, 20))
        d = ImageDraw.Draw(frame)
        d.rounded_rectangle([5, 5, W-5, H-5], radius=35, outline="white", width=3)
        
        if i < anim_frames:
            # Physics Jump (Parabola)
            jump = -100 * math.sin((i / anim_frames) * math.pi)
            angle = (i / anim_frames) * math.pi * 5 # Fast 2.5 rotations
            width_factor = abs(math.cos(angle))
            current_face = h_img if math.cos(angle) > 0 else t_img
        else:
            # Result Pause
            jump = 0
            width_factor = 1.0
            current_face = h_img if final_side == "heads" else t_img

        new_w = max(1, int(180 * width_factor))
        resized_coin = current_face.resize((new_w, 180), Image.Resampling.LANCZOS)
        
        # Ground Shadow
        sw = int(100 * (1 + (jump/200)))
        d.ellipse([W//2 - sw//2, H-80, W//2 + sw//2, H-60], fill=(0,0,0,80))
        
        frame.paste(resized_coin, (W//2 - new_w//2, int(H//2 - 90 + jump)), resized_coin)
        frames.append(frame)
        
    out = io.BytesIO()
    # Speed set to 70ms for natural look
    frames[0].save(out, format='GIF', save_all=True, append_images=frames[1:], duration=70, loop=0, optimize=True)
    return out.getvalue()

# ==========================================
# 🏆 LIGHTWEIGHT RESULT CARD
# ==========================================

def draw_result_card(username, user_id, av_url, result_side, is_win, bet, win_total):
    W, H = 550, 550 # Light-weight resolution
    base = utils.get_gradient(W, H, (10, 40, 10), (20, 80, 20)) 
    img = Image.new('RGBA', (W, H))
    img.paste(base, (0,0))
    d = ImageDraw.Draw(img)

    border_col = "#00FF00" if is_win else "#FF0000"
    d.rounded_rectangle([8, 8, W-8, H-8], radius=45, outline=border_col, width=5)

    # Header
    utils.write_text(d, (W//2, 45), "COIN FLIP", size=35, align="center", col="white", shadow=True)

    # Result Coin
    coin_res = get_coin_img(result_side).resize((220, 220), Image.Resampling.LANCZOS)
    # Result Glow
    gc = (0, 255, 127, 60) if is_win else (255, 49, 49, 60)
    d.ellipse([W//2-130, 110, W//2+130, 370], fill=gc)
    img.paste(coin_res, (W//2 - 110, 130), coin_res)

    # Winner/Loser Text
    res_txt = "VICTORY" if is_win else "DEFEAT"
    utils.write_text(d, (W//2, 400), res_txt, size=65, align="center", col=border_col, shadow=True)

    # Striker Info (Bottom Left)
    av = get_avatar_robust(user_id, username, av_url).resize((100, 100))
    av_mask = Image.new('L', (100, 100), 0)
    ImageDraw.Draw(av_mask).ellipse((0, 0, 100, 100), fill=255)
    img.paste(av, (30, 420), av_mask)
    d.ellipse([30, 420, 130, 520], outline="white", width=3)
    utils.write_text(d, (80, 530), username.upper()[:10], size=18, align="center", col="white")

    # Winnings (RED TEXT)
    chips_txt = f"+{win_total} Chips" if is_win else f"-{bet} Chips"
    utils.write_text(d, (W-30, 450), chips_txt, size=38, align="right", col="#FF0000") # RED
    
    if is_win:
        utils.write_text(d, (W-30, 500), f"+{WIN_SCORE} Score", size=24, align="right", col="#00F2FE")

    return apply_round_corners(img, 40)

# ==========================================
# 📡 HANDLER
# ==========================================

def handle_command(bot, cmd, room_id, user, args, data):
    uid = str(data.get('userid'))
    av_url = data.get('avatar')

    if cmd == "flip":
        if len(args) < 2:
            bot.send_message(room_id, "Usage: !flip <h/t> <amt>"); return True

        # Input Check
        side_in = args[0].lower()
        if side_in in ['h', 'heads']: choice = "heads"
        elif side_in in ['t', 'tails']: choice = "tails"
        else: return True

        try:
            bet = int(args[1])
            if bet < 100: bot.send_message(room_id, "Minimum bet 100."); return True
            
            # ECONOMY
            if not db.check_and_deduct_chips(uid, user, bet):
                bot.send_message(room_id, f"❌ @{user}, Need {bet} chips!"); return True

            result_side = random.choice(['heads', 'tails'])
            is_win = (choice == result_side)
            win_total = bet * 2 if is_win else 0

            # 1. GENERATE & SEND GIF (Optimized Size)
            gif_data = create_flip_gif(result_side)
            gif_url = bot.upload_to_server(gif_data, file_type='gif')
            bot.send_json({"handler":"chatroommessage","roomid":room_id,"type":"image","url":gif_url,"text":"Flipping..."})

            # 2. DELAYED CARD (Async to prevent blocking)
            def delayed_card():
                time.sleep(1.8) # Adjusted for faster GIF duration
                # DB Sync
                if is_win:
                    db.add_game_result(uid, user, "coinflip", win_total - bet, True, WIN_SCORE)
                else:
                    db.add_game_result(uid, user, "coinflip", -bet, False, 0)
                
                # Card Render
                card = draw_result_card(user, uid, av_url, result_side, is_win, bet, win_total)
                card_url = bot.upload_to_server(card)
                bot.send_json({"handler":"chatroommessage","roomid":room_id,"type":"image","url":card_url,"text":f"{result_side.upper()}!"})

            threading.Thread(target=delayed_card).start()
            return True

        except: return True

    return False
