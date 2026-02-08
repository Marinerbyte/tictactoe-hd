import threading
import time
import random
import io
import requests
from PIL import Image, ImageDraw, ImageOps, ImageFilter
import db
import utils

# ==========================================
# ⚙️ CONFIGURATION & LINKS
# ==========================================
WIN_SCORE = 30
GIF_HEADS = "https://www.dropbox.com/scl/fi/4whxj4eouati7b9lj3vuj/coin_heads_3d.gif?rlkey=2ojhelepejxx4h3gln6ykmde8&st=ug1sr2vx&dl=1"
GIF_TAILS = "https://www.dropbox.com/scl/fi/oc0hg4h5h51h95fz5quy5/coin_tails_3d.gif?rlkey=m4i6zx2e0lfjqr9rktymfk345&st=9yl8qy8l&dl=1"

PNG_HEADS = "https://www.dropbox.com/scl/fi/jxin556171p1jxc9ijjt8/file_00000000e1647209a0f1041e0faf6aa7.png?rlkey=qaho82a5zc2edarlyrn0pk0nd&st=syo1hqsh&dl=1"
PNG_TAILS = "https://www.dropbox.com/scl/fi/0icyzmbn04dw1r2wburaw/file_00000000a67472099de1c5aa86bf3f9d.png?rlkey=9cy19hi5h704cy36onshi9wgr&st=8jts2yc9&dl=1"

AV_CACHE = {}
COIN_PNG_CACHE = {}

def setup(bot):
    print("[CoinFlip-HD] Centered Trophy Engine Loaded.")

# --- HELPERS ---

def get_avatar_robust(user_id, username, avatar_url=None):
    if user_id in AV_CACHE: return AV_CACHE[user_id].copy()
    try:
        url = avatar_url if avatar_url else f"https://api.howdies.app/api/avatar/{user_id}"
        r = requests.get(url, timeout=3)
        img = Image.open(io.BytesIO(r.content)).convert("RGBA")
    except:
        img = Image.new('RGBA', (200, 200), (30, 30, 50))
        d = ImageDraw.Draw(img)
        utils.write_text(d, (100, 100), username[0].upper() if username else "?", size=100, col="white", align="center")
    AV_CACHE[user_id] = img
    return img.copy()

def get_static_coin(side):
    if side in COIN_PNG_CACHE: return COIN_PNG_CACHE[side].copy()
    url = PNG_HEADS if side == "heads" else PNG_TAILS
    try:
        r = requests.get(url, timeout=5)
        img = Image.open(io.BytesIO(r.content)).convert("RGBA")
        COIN_PNG_CACHE[side] = img
        return img.copy()
    except: return Image.new('RGBA', (200, 200), (50, 50, 50))

def apply_round_corners(img, radius):
    mask = Image.new("L", img.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0) + img.size, radius=radius, fill=255)
    out = Image.new("RGBA", img.size)
    out.paste(img, (0, 0), mask)
    return out

# ==========================================
# 🏆 THE CENTERED CHAMPION CARD
# ==========================================

def draw_result_card(username, user_id, av_url, result_side, is_win, bet, win_total):
    W, H = 600, 800 # Vertical layout for centered mapping
    base = utils.get_gradient(W, H, (10, 40, 20), (20, 10, 50))
    img = Image.new('RGBA', (W, H))
    img.paste(base, (0, 0))
    d = ImageDraw.Draw(img)

    # Main Frame
    border_col = "#00FF00" if is_win else "#FF0000"
    for i in range(5):
        alpha = 255 - (i * 40)
        d.rounded_rectangle([i, i, W-i, H-i], radius=50, outline=f"{border_col}{alpha:02x}", width=2)

    # 1. LARGE CENTERED DP
    av_size = 240
    av_raw = get_avatar_robust(user_id, username, av_url).resize((av_size, av_size), Image.Resampling.LANCZOS)
    mask = Image.new('L', (av_size, av_size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, av_size, av_size), fill=255)
    
    cx, cy = W // 2, 220
    # DP Glow
    glow_col = (0, 255, 127, 80) if is_win else (255, 49, 49, 80)
    d.ellipse([cx-140, cy-140, cx+140, cy+140], fill=glow_col)
    d.ellipse([cx-125, cy-125, cx+125, cy+125], outline="white", width=5)
    img.paste(av_raw, (cx-120, cy-120), mask)

    # 2. DECORATIVE ELEMENTS (Stars/Flowers)
    # Mapping some stars around the subject
    decor_pos = [(80, 80), (W-80, 80), (80, 400), (W-80, 400), (cx-180, cy), (cx+180, cy)]
    for px, py in decor_pos:
        utils.write_text(d, (px, py), random.choice(["★", "✿"]), size=30, col="#FFD700", align="center")

    # 3. CENTERED USERNAME
    utils.write_text(d, (W//2, 380), username.upper(), size=45, align="center", col="white", shadow=True)

    # 4. RESULT BANNER
    banner_w, banner_h = 350, 70
    bx, by = W//2 - banner_w//2, 440
    res_txt = "VICTORY" if is_win else "DEFEAT"
    d.rounded_rectangle([bx, by, bx+banner_w, by+banner_h], radius=20, fill=border_col)
    utils.write_text(d, (W//2, by + 35), res_txt, size=40, align="center", col="black")

    # 5. RESULT COIN (Below Banner)
    coin_img = get_static_coin(result_side).resize((180, 180), Image.Resampling.LANCZOS)
    img.paste(coin_img, (W//2 - 90, 530), coin_img)
    utils.write_text(d, (W//2, 730), f"IT'S {result_side.upper()}", size=30, align="center", col="#FFD700")

    # 6. EARNINGS (RED TEXT - Fixed Center)
    chips_txt = f"+{win_total} CHIPS" if is_win else f"-{bet} CHIPS"
    utils.write_text(d, (W//2, 415), chips_txt, size=35, align="center", col="#FF0000") # RED TEXT
    
    if is_win:
        utils.write_text(d, (W//2, 520), f"+{WIN_SCORE} SCORE", size=24, align="center", col="#00F2FE")

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

        input_side = args[0].lower()
        if input_side in ['h', 'heads', 'head']: choice = "heads"
        elif input_side in ['t', 'tails', 'tail']: choice = "tails"
        else: return True

        try:
            bet = int(args[1])
            if bet < 100: bot.send_message(room_id, "❌ Min bet 100 chips."); return True
            
            # ECONOMY
            if not db.check_and_deduct_chips(uid, user, bet):
                bot.send_message(room_id, f"❌ @{user}, Not enough chips!"); return True

            result_side = random.choice(['heads', 'tails'])
            is_win = (choice == result_side)
            win_total = bet * 2 if is_win else 0

            # 1. SEND PRE-MADE GIF
            bot.send_json({
                "handler": "chatroommessage",
                "roomid": room_id,
                "type": "image",
                "url": GIF_HEADS if result_side == "heads" else GIF_TAILS,
                "text": f"@{user} is flipping a coin..."
            })

            # 2. DELAYED CENTERED CARD
            def show_result():
                time.sleep(2.5) 
                if is_win:
                    db.add_game_result(uid, user, "coinflip", win_total - bet, True, WIN_SCORE)
                else:
                    db.add_game_result(uid, user, "coinflip", -bet, False, 0)
                
                card = draw_result_card(user, uid, av_url, result_side, is_win, bet, win_total)
                card_url = bot.upload_to_server(card)
                bot.send_json({
                    "handler": "chatroommessage",
                    "roomid": room_id,
                    "type": "image",
                    "url": card_url,
                    "text": f"RESULT: {result_side.upper()}"
                })

            threading.Thread(target=show_result).start()
            return True
        except: return True

    return False
