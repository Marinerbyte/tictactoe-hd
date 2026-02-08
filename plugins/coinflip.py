import threading
import time
import random
import io
import requests
import traceback
from PIL import Image, ImageDraw, ImageOps, ImageFilter
import db
import utils

# ==========================================
# ⚙️ CONFIGURATION & LINKS
# ==========================================
WIN_SCORE = 30
# Catbox Fast Links
GIF_HEADS = "https://files.catbox.moe/4tizr3.gif"
GIF_TAILS = "https://files.catbox.moe/n91naf.gif"
PNG_HEADS = "https://files.catbox.moe/d2ygml.png"
PNG_TAILS = "https://files.catbox.moe/v670kn.png"

AV_CACHE = {}

def setup(bot):
    print("[CoinFlip-HD] High-Fidelity Engine Loaded.")

# --- HELPERS ---

def get_avatar_robust(user_id, username, avatar_url=None):
    if user_id in AV_CACHE: return AV_CACHE[user_id].copy()
    img = None
    try:
        # UserID based URL or Socket URL
        url = avatar_url if (avatar_url and "http" in str(avatar_url)) else f"https://api.howdies.app/api/avatar/{user_id}"
        r = requests.get(url, timeout=4, headers={'User-Agent': 'Mozilla/5.0'})
        if r.status_code == 200:
            img = Image.open(io.BytesIO(r.content)).convert("RGBA")
    except: pass
    
    if not img:
        img = Image.new('RGBA', (260, 260), (30, 30, 50))
        d = ImageDraw.Draw(img)
        char = username[0].upper() if username else "?"
        utils.write_text(d, (130, 130), char, size=120, col="white", align="center")
    
    AV_CACHE[user_id] = img
    return img.copy()

def get_static_coin(side):
    url = PNG_HEADS if side == "heads" else PNG_TAILS
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return Image.open(io.BytesIO(r.content)).convert("RGBA")
    except: pass
    return Image.new('RGBA', (200, 200), (50, 50, 50))

def apply_round_corners(img, radius):
    mask = Image.new("L", img.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0) + img.size, radius=radius, fill=255)
    out = Image.new("RGBA", img.size, (0,0,0,0))
    out.paste(img, (0, 0), mask)
    return out

# ==========================================
# 🏆 THE CENTERED CHAMPION POSTER
# ==========================================

def draw_result_card(username, user_id, av_url, result_side, is_win, bet, win_total):
    W, H = 600, 850
    # Turf Green Gradient (Penalty Style)
    base = utils.get_gradient(W, H, (10, 40, 20), (20, 10, 50))
    img = Image.new('RGBA', (W, H))
    img.paste(base, (0, 0))
    d = ImageDraw.Draw(img)

    main_col = "#00FF00" if is_win else "#FF0000"
    for i in range(6):
        alpha = 180 - (i * 30)
        d.rounded_rectangle([i, i, W-i, H-i], radius=50, outline=f"{main_col}{alpha:02x}", width=2)

    # 1. DECORATIONS (Manual Stars/Dots)
    for _ in range(25):
        dx, dy = random.randint(30, W-30), random.randint(30, 500)
        d.ellipse([dx, dy, dx+4, dy+4], fill="#FFD700")

    # 2. CENTERED LARGE HERO DP
    av_size = 280
    av_raw = get_avatar_robust(user_id, username, av_url).resize((av_size, av_size), Image.Resampling.LANCZOS)
    mask = Image.new('L', (av_size, av_size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, av_size, av_size), fill=255)
    
    cx, cy = W // 2, 230
    glow_col = (0, 255, 127, 80) if is_win else (255, 49, 49, 80)
    d.ellipse([cx-155, cy-155, cx+155, cy+155], fill=glow_col)
    d.ellipse([cx-145, cy-145, cx+145, cy+145], outline="white", width=4)
    img.paste(av_raw, (cx-140, cy-140), mask)

    # 3. CENTERED NAME
    utils.write_text(d, (W//2, 420), username.upper(), size=50, align="center", col="white", shadow=True)
    
    # 4. RED CHIPS TEXT (As requested)
    chips_label = f"+{win_total} CHIPS" if is_win else f"-{bet} CHIPS"
    utils.write_text(d, (W//2, 485), chips_label, size=42, align="center", col="#FF0000")

    # 5. RESULT BANNER
    banner_w, banner_h = 350, 75
    bx, by = W//2 - banner_w//2, 550
    res_txt = "VICTORY" if is_win else "DEFEAT"
    d.rounded_rectangle([bx, by, bx+banner_w, by+banner_h], radius=25, fill=main_col)
    utils.write_text(d, (W//2, by + 37), res_txt, size=45, align="center", col="black")

    # 6. RESULT COIN
    coin_img = get_static_coin(result_side).resize((220, 220), Image.Resampling.LANCZOS)
    img.paste(coin_img, (W//2 - 110, 630), coin_img)
    utils.write_text(d, (W//2, H-30), f"IT WAS {result_side.upper()}", size=30, align="center", col="#FFD700")

    if is_win:
        utils.write_text(d, (W//2, 525), f"+{WIN_SCORE} SCORE", size=24, align="center", col="#00F2FE")

    return apply_round_corners(img, 50)

# ==========================================
# 📡 COMMAND HANDLER
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
            if bet < 50: bot.send_message(room_id, "Minimum bet is 50 chips."); return True
            
            # ECONOMY
            if not db.check_and_deduct_chips(uid, user, bet):
                bot.send_message(room_id, f"❌ @{user}, you need {bet} chips!"); return True

            result_side = random.choice(['heads', 'tails'])
            is_win = (choice == result_side)
            win_total = bet * 2 if is_win else 0

            # 1. SEND PRE-MADE GIF (Catbox is fast)
            bot.send_json({
                "handler": "chatroommessage",
                "roomid": room_id,
                "type": "image",
                "url": GIF_HEADS if result_side == "heads" else GIF_TAILS,
                "text": f"@{user} is flipping a coin..."
            })

            # 2. DELAYED RESULT (Thread Protected)
            def show_result_async():
                try:
                    time.sleep(2.5)
                    # Database Atomic Sync
                    if is_win:
                        db.add_game_result(uid, user, "coinflip", win_total - bet, True, WIN_SCORE)
                    else:
                        db.add_game_result(uid, user, "coinflip", -bet, False, 0)
                    
                    # Generate Card
                    card = draw_result_card(user, uid, av_url, result_side, is_win, bet, win_total)
                    
                    # Safe Upload
                    img_byte_arr = io.BytesIO()
                    card.save(img_byte_arr, format='PNG')
                    card_url = bot.upload_to_server(img_byte_arr.getvalue(), file_type='png')
                    
                    if card_url:
                        bot.send_json({
                            "handler": "chatroommessage",
                            "roomid": room_id,
                            "type": "image",
                            "url": card_url,
                            "text": f"Natija: {result_side.upper()}!"
                        })
                except:
                    traceback.print_exc()

            threading.Thread(target=show_result_async, daemon=True).start()
            return True
        except:
            return True

    return False
