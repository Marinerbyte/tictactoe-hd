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
WIN_SCORE_REWARD = 30
COIN_HEADS_URL = "https://www.dropbox.com/scl/fi/jxin556171p1jxc9ijjt8/file_00000000e1647209a0f1041e0faf6aa7.png?rlkey=qaho82a5zc2edarlyrn0pk0nd&st=syo1hqsh&dl=1"
COIN_TAILS_URL = "https://www.dropbox.com/scl/fi/0icyzmbn04dw1r2wburaw/file_00000000a67472099de1c5aa86bf3f9d.png?rlkey=9cy19hi5h704cy36onshi9wgr&st=8jts2yc9&dl=1"

# Caching for performance
COIN_IMAGES = {}
AV_CACHE = {}

def setup(bot):
    print("[CoinFlip-HD] Illusion Visuals Engine Loaded.")

# ==========================================
# 🖼️ GRAPHICS & AVATAR HELPERS
# ==========================================

def get_avatar_cached(user_id, username, avatar_url=None):
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

def get_coin(side):
    """Fetches and caches Head/Tail PNGs"""
    if side in COIN_IMAGES: return COIN_IMAGES[side].copy()
    url = COIN_HEADS_URL if side == "heads" else COIN_TAILS_URL
    try:
        r = requests.get(url, timeout=5)
        img = Image.open(io.BytesIO(r.content)).convert("RGBA")
        COIN_IMAGES[side] = img
        return img.copy()
    except Exception as e:
        print(f"Coin Fetch Error: {e}")
        return Image.new('RGBA', (300, 300), (50, 50, 50))

def apply_round_corners(img, radius):
    mask = Image.new("L", img.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0) + img.size, radius, fill=255)
    out = Image.new("RGBA", img.size)
    out.paste(img, (0, 0), mask)
    return out

# ==========================================
# 🎨 CINEMATIC ILLUSION BOARD
# ==========================================

def draw_flip_card(username, user_id, avatar_url, result_side, is_win, bet, win_amt):
    W, H = 750, 500
    # Deep Space Gradient
    base = utils.get_gradient(W, H, (10, 15, 35), (30, 10, 60))
    img = Image.new('RGBA', (W, H))
    img.paste(base, (0, 0))
    d = ImageDraw.Draw(img)

    # Neon Outer Frame
    frame_col = "#00FF00" if is_win else "#FF0000"
    for i in range(5):
        alpha = 150 - (i * 25)
        d.rounded_rectangle([i, i, W-i, H-i], radius=40, outline=f"{frame_col}{alpha:02x}", width=2)

    # 🌀 ILLUSION BACKGROUND (Motion Blur effect)
    # Drawing multiple faint circles to simulate a fast spin
    for i in range(10):
        s = 150 + (i * 15)
        alpha = 60 - (i * 5)
        d.ellipse([W//2 - s, H//2 - s - 40, W//2 + s, H//2 + s - 40], outline=(255, 255, 255, alpha), width=1)

    # 🪙 THE COIN (The Main Result)
    coin_img = get_coin(result_side).resize((220, 220), Image.Resampling.LANCZOS)
    # Coin Shadow/Glow
    glow_col = (0, 255, 127, 100) if is_win else (255, 49, 49, 100)
    d.ellipse([W//2 - 120, H//2 - 160, W//2 + 120, H//2 + 80], fill=glow_col) # Glow behind coin
    img.paste(coin_img, (W//2 - 110, H//2 - 150), coin_img)

    # 👤 PLAYER DP (Left Side)
    av = get_avatar_cached(user_id, username, avatar_url).resize((140, 140))
    av_mask = Image.new('L', (140, 140), 0)
    ImageDraw.Draw(av_mask).ellipse((0, 0, 140, 140), fill=255)
    img.paste(av, (40, H//2 - 100), av_mask)
    d.ellipse([40, H//2 - 100, 180, H//2 + 40], outline="white", width=4)
    utils.write_text(d, (110, H//2 + 60), username.upper(), size=24, align="center", col="white")

    # 📊 RESULT INFO (Right Side)
    res_text = "WINNER" if is_win else "LOOSER"
    res_col = "#00FF00" if is_win else "#FF4444"
    utils.write_text(d, (W - 150, H//2 - 110), res_text, size=40, align="center", col=res_col, shadow=True)
    
    # RED TEXT FOR CHIPS (As requested)
    status_text = f"+{win_amt} Chips" if is_win else f"-{bet} Chips"
    utils.write_text(d, (W - 150, H//2 - 40), status_text, size=32, align="center", col="#FF0000")
    
    if is_win:
        utils.write_text(d, (W - 150, H//2 + 20), f"+{WIN_SCORE_REWARD} Score", size=26, align="center", col="#00F2FE")

    # Bottom Footer
    footer_text = f"RESULT: {result_side.upper()}"
    utils.write_text(d, (W//2, H - 60), footer_text, size=35, align="center", col="#FFD700", shadow=True)

    return apply_round_corners(img, 40)

# ==========================================
# 📡 COMMAND HANDLER
# ==========================================

def handle_command(bot, cmd, room_id, user, args, data):
    uid = str(data.get('userid'))
    av_url = data.get('avatar')

    # 1. Flip Command: !flip <h/t> <amt>
    if cmd == "flip":
        if len(args) < 2:
            bot.send_message(room_id, "Usage: !flip <heads/tails> <amount>")
            return True

        choice_raw = args[0].lower()
        if choice_raw in ['h', 'head', 'heads']: choice = "heads"
        elif choice_raw in ['t', 'tail', 'tails']: choice = "tails"
        else:
            bot.send_message(room_id, "❌ Pick 'heads' or 'tails'.")
            return True

        try:
            bet = int(args[1])
            if bet < 100:
                bot.send_message(room_id, "❌ Minimum bet is 100 chips.")
                return True
            
            # ECONOMY: Atomic check and deduct
            if not db.check_and_deduct_chips(uid, user, bet):
                bot.send_message(room_id, f"❌ @{user}, insufficient chips (Need {bet})!")
                return True

            # FLIP LOGIC
            result_side = random.choice(['heads', 'tails'])
            is_win = (choice == result_side)
            win_amt = bet * 2 if is_win else 0

            # DATABASE SYNC
            if is_win:
                # Add net profit and score
                db.add_game_result(uid, user, "coinflip", win_amt - bet, True, WIN_SCORE_REWARD)
            else:
                # Log loss
                db.add_game_result(uid, user, "coinflip", -bet, False, 0)

            # RENDER & SEND
            img = draw_flip_card(user, uid, av_url, result_side, is_win, bet, win_amt)
            url = bot.upload_to_server(img)
            
            # Text notification
            msg = f"🪙 It's **{result_side.upper()}**! "
            msg += f"Congratulations @{user}, you won {win_amt} chips!" if is_win else f"Sorry @{user}, you lost the bet."
            
            bot.send_json({
                "handler": "chatroommessage",
                "roomid": room_id,
                "type": "image",
                "url": url,
                "text": msg
            })
            return True

        except ValueError:
            bot.send_message(room_id, "❌ Invalid amount format.")
            return True

    return False
