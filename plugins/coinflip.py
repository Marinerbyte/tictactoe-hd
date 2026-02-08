import threading
import time
import random
import io
import requests
from PIL import Image, ImageDraw, ImageOps, ImageFilter
import db
import utils

# ==========================================
# ⚙️ CONFIGURATION & GIF LINKS
# ==========================================
WIN_SCORE = 30
# Pre-made 3D GIFs provided by you
GIF_HEADS = "https://www.dropbox.com/scl/fi/4whxj4eouati7b9lj3vuj/coin_heads_3d.gif?rlkey=2ojhelepejxx4h3gln6ykmde8&st=ug1sr2vx&dl=1"
GIF_TAILS = "https://www.dropbox.com/scl/fi/oc0hg4h5h51h95fz5quy5/coin_tails_3d.gif?rlkey=m4i6zx2e0lfjqr9rktymfk345&st=9yl8qy8l&dl=1"

# Static PNGs for the final result card
PNG_HEADS = "https://www.dropbox.com/scl/fi/jxin556171p1jxc9ijjt8/file_00000000e1647209a0f1041e0faf6aa7.png?rlkey=qaho82a5zc2edarlyrn0pk0nd&st=syo1hqsh&dl=1"
PNG_TAILS = "https://www.dropbox.com/scl/fi/0icyzmbn04dw1r2wburaw/file_00000000a67472099de1c5aa86bf3f9d.png?rlkey=9cy19hi5h704cy36onshi9wgr&st=8jts2yc9&dl=1"

AV_CACHE = {}
COIN_PNG_CACHE = {}

def setup(bot):
    print("[CoinFlip-HD] Pre-made 3D GIF Engine Loaded.")

# --- HELPERS ---

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

def get_static_coin(side):
    if side in COIN_PNG_CACHE: return COIN_PNG_CACHE[side].copy()
    url = PNG_HEADS if side == "heads" else PNG_TAILS
    try:
        r = requests.get(url, timeout=5)
        img = Image.open(io.BytesIO(r.content)).convert("RGBA")
        COIN_PNG_CACHE[side] = img
        return img.copy()
    except:
        return Image.new('RGBA', (200, 200), (50, 50, 50))

def apply_round_corners(img, radius):
    mask = Image.new("L", img.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0) + img.size, radius=radius, fill=255)
    out = Image.new("RGBA", img.size)
    out.paste(img, (0, 0), mask)
    return out

# ==========================================
# 🏆 PREMIUM RESULT CARD
# ==========================================

def draw_result_card(username, user_id, av_url, result_side, is_win, bet, win_total):
    W, H = 600, 600
    # Turf Green Gradient (Penalty Style)
    base = utils.get_gradient(W, H, (10, 45, 15), (25, 95, 30))
    img = Image.new('RGBA', (W, H))
    img.paste(base, (0,0))
    d = ImageDraw.Draw(img)

    border_col = "#00FF00" if is_win else "#FF0000"
    d.rounded_rectangle([10, 10, W-10, H-10], radius=50, outline=border_col, width=6)

    # Header
    utils.write_text(d, (W//2, 50), "FLIP RESULT", size=40, align="center", col="white", shadow=True)

    # Result Coin Image
    coin_img = get_static_coin(result_side).resize((250, 250), Image.Resampling.LANCZOS)
    # Result Glow
    gc = (0, 255, 127, 80) if is_win else (255, 49, 49, 80)
    d.ellipse([W//2-130, 120, W//2+130, 380], fill=gc)
    img.paste(coin_img, (W//2 - 125, 130), coin_img)

    # Winner/Loser Title
    res_txt = "VICTORY" if is_win else "DEFEAT"
    utils.write_text(d, (W//2, 420), res_txt, size=75, align="center", col=border_col, shadow=True)

    # Player Info (Bottom Left)
    av = get_avatar_robust(user_id, username, av_url).resize((110, 110))
    av_mask = Image.new('L', (110, 110), 0)
    ImageDraw.Draw(av_mask).ellipse((0, 0, 110, 110), fill=255)
    img.paste(av, (35, 455), av_mask)
    d.ellipse([35, 455, 145, 565], outline="white", width=3)
    utils.write_text(d, (90, 575), username.upper()[:10], size=20, align="center", col="white")

    # Winnings (RED TEXT AS REQUESTED)
    chips_txt = f"+{win_total} Chips" if is_win else f"-{bet} Chips"
    utils.write_text(d, (W-40, 480), chips_txt, size=40, align="right", col="#FF0000") # RED
    
    if is_win:
        utils.write_text(d, (W-40, 535), f"+{WIN_SCORE} Score", size=25, align="right", col="#00F2FE")

    return apply_round_corners(img, 45)

# ==========================================
# 📡 COMMAND HANDLER
# ==========================================

def handle_command(bot, cmd, room_id, user, args, data):
    uid = str(data.get('userid'))
    av_url = data.get('avatar')

    if cmd == "flip":
        if len(args) < 2:
            bot.send_message(room_id, "Usage: !flip <h/t> <amount>"); return True

        # Side Selection
        input_side = args[0].lower()
        if input_side in ['h', 'heads', 'head']: choice = "heads"
        elif input_side in ['t', 'tails', 'tail']: choice = "tails"
        else: return True

        try:
            bet = int(args[1])
            if bet < 100: bot.send_message(room_id, "❌ Minimum bet 100 chips."); return True
            
            # ECONOMY SYNC
            if not db.check_and_deduct_chips(uid, user, bet):
                bot.send_message(room_id, f"❌ @{user}, Not enough chips!"); return True

            # Decide Result
            result_side = random.choice(['heads', 'tails'])
            is_win = (choice == result_side)
            win_total = bet * 2 if is_win else 0

            # 1. SEND PRE-MADE 3D GIF (Super Fast)
            target_gif = GIF_HEADS if result_side == "heads" else GIF_TAILS
            bot.send_json({
                "handler": "chatroommessage",
                "roomid": room_id,
                "type": "image",
                "url": target_gif,
                "text": f"@{user} uchal raha hai sika..."
            })

            # 2. DELAYED RESULT CARD
            def show_result():
                # GIF plays for ~2 seconds
                time.sleep(2.2) 
                
                # Update DB
                if is_win:
                    db.add_game_result(uid, user, "coinflip", win_total - bet, True, WIN_SCORE)
                else:
                    db.add_game_result(uid, user, "coinflip", -bet, False, 0)
                
                # Render Card
                card = draw_result_card(user, uid, av_url, result_side, is_win, bet, win_total)
                card_url = bot.upload_to_server(card)
                bot.send_json({
                    "handler": "chatroommessage",
                    "roomid": room_id,
                    "type": "image",
                    "url": card_url,
                    "text": f"It's {result_side.upper()}!"
                })

            threading.Thread(target=show_result).start()
            return True

        except: return True

    return False
