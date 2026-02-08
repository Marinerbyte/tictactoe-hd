import threading
import time
import random
import io
import requests
import math
import traceback
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

def setup(bot):
    print("[CoinFlip-HD] Crash-Proof Trophy Engine Loaded.")

# --- HELPERS ---

def get_avatar_robust(user_id, username, avatar_url=None):
    if user_id in AV_CACHE: return AV_CACHE[user_id].copy()
    img = None
    try:
        url = avatar_url if (avatar_url and str(avatar_url) != "None") else f"https://api.howdies.app/api/avatar/{user_id}"
        r = requests.get(url, timeout=4, headers={'User-Agent': 'Mozilla/5.0'})
        if r.status_code == 200:
            img = Image.open(io.BytesIO(r.content)).convert("RGBA")
    except: pass
    
    if not img:
        img = Image.new('RGBA', (240, 240), (40, 40, 70))
        d = ImageDraw.Draw(img)
        char = username[0].upper() if username else "?"
        utils.write_text(d, (120, 120), char, size=100, col="white", align="center")
    
    AV_CACHE[user_id] = img
    return img.copy()

def get_static_coin(side):
    url = PNG_HEADS if side == "heads" else PNG_TAILS
    try:
        r = requests.get(url, timeout=5)
        return Image.open(io.BytesIO(r.content)).convert("RGBA")
    except:
        return Image.new('RGBA', (200, 200), (50, 50, 50))

def apply_round_corners(img, radius):
    mask = Image.new("L", img.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0) + img.size, radius=radius, fill=255)
    out = Image.new("RGBA", img.size, (0,0,0,0))
    out.paste(img, (0, 0), mask)
    return out

# ==========================================
# 🏆 THE CENTERED CHAMPION CARD
# ==========================================

def draw_result_card(username, user_id, av_url, result_side, is_win, bet, win_total):
    W, H = 600, 850
    # Premium Dark Gradient
    base = utils.get_gradient(W, H, (15, 15, 30), (40, 20, 80))
    img = Image.new('RGBA', (W, H))
    img.paste(base, (0, 0))
    d = ImageDraw.Draw(img)

    # Main Outer Frame
    border_col = "#00FF00" if is_win else "#FF0000"
    for i in range(6):
        alpha = 200 - (i * 30)
        d.rounded_rectangle([i, i, W-i, H-i], radius=50, outline=f"{border_col}{alpha:02x}", width=2)

    # 1. DECORATIONS (Stars/Dots) - Drawn manually to avoid font crashes
    for _ in range(15):
        px, py = random.randint(50, W-50), random.randint(50, H-300)
        dot_size = random.randint(2, 5)
        d.ellipse([px, py, px+dot_size, py+dot_size], fill="#FFD700")

    # 2. LARGE CENTERED DP
    av_size = 260
    av_raw = get_avatar_robust(user_id, username, av_url).resize((av_size, av_size), Image.Resampling.LANCZOS)
    mask = Image.new('L', (av_size, av_size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, av_size, av_size), fill=255)
    
    cx, cy = W // 2, 230
    # DP Glow Effect
    glow_col = (0, 255, 127, 80) if is_win else (255, 49, 49, 80)
    for r in range(135, 155, 4):
        d.ellipse([cx-r, cy-r, cx+r, cy+r], outline=f"{border_col}40", width=2)
    
    d.ellipse([cx-135, cy-135, cx+135, cy+135], fill=glow_col)
    img.paste(av_raw, (cx-130, cy-130), mask)

    # 3. USERNAME (Centered)
    utils.write_text(d, (W//2, 400), username.upper(), size=45, align="center", col="white", shadow=True)

    # 4. CHIPS RESULT (RED TEXT - Center)
    chips_txt = f"+{win_total} CHIPS" if is_win else f"-{bet} CHIPS"
    utils.write_text(d, (W//2, 460), chips_txt, size=38, align="center", col="#FF0000")

    # 5. RESULT BANNER
    res_txt = "VICTORY" if is_win else "DEFEAT"
    banner_w, banner_h = 320, 70
    bx, by = W//2 - banner_w//2, 520
    d.rounded_rectangle([bx, by, bx+banner_w, by+banner_h], radius=20, fill=border_col)
    utils.write_text(d, (W//2, by + 35), res_txt, size=40, align="center", col="black")

    # 6. RESULT COIN
    coin_img = get_static_coin(result_side).resize((200, 200), Image.Resampling.LANCZOS)
    img.paste(coin_img, (W//2 - 100, 610), coin_img)
    utils.write_text(d, (W//2, 820), f"RESULT: {result_side.upper()}", size=28, align="center", col="#FFD700")

    if is_win:
        utils.write_text(d, (W//2, 505), f"+{WIN_SCORE} SCORE", size=22, align="center", col="#00F2FE")

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
                bot.send_message(room_id, f"❌ @{user}, Insufficient chips!"); return True

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

            # 2. ASYNC DELAYED CARD (With Error Protection)
            def show_result():
                try:
                    time.sleep(2.5) 
                    # DB Updates
                    if is_win:
                        db.add_game_result(uid, user, "coinflip", win_total - bet, True, WIN_SCORE)
                    else:
                        db.add_game_result(uid, user, "coinflip", -bet, False, 0)
                    
                    # Generate Card
                    card = draw_result_card(user, uid, av_url, result_side, is_win, bet, win_total)
                    card_url = utils.upload(bot, card) # Consistent with penalty.py
                    
                    bot.send_json({
                        "handler": "chatroommessage",
                        "roomid": room_id,
                        "type": "image",
                        "url": card_url,
                        "text": f"RESULT: {result_side.upper()}"
                    })
                except Exception:
                    print("[CoinFlip Error] Crash in result thread:")
                    traceback.print_exc()

            threading.Thread(target=show_result, daemon=True).start()
            return True
        except:
            traceback.print_exc()
            return True

    return False
