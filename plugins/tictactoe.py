import time
import random
import threading
import sys
import os
import requests
import io
from PIL import Image, ImageDraw, ImageFilter, ImageOps

# --- UTILS & DB ---
try: import utils
except ImportError: print("[TicTacToe] Error: utils.py missing!")
try:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    import db
except Exception as e: print(f"DB Error: {e}")

# --- GLOBAL STATE ---
games = {} 
games_lock = threading.Lock()
AVATAR_CACHE = {}
BOT_REF = None

def setup(bot_ref):
    global BOT_REF
    BOT_REF = bot_ref
    threading.Thread(target=cleanup_loop, daemon=True).start()
    print("[TicTacToe] Standardized Stop Command & Refund System Ready.")

# ==========================================
# 🖼️ AVATAR ENGINE
# ==========================================

def get_avatar(avatar_url, username):
    if avatar_url and avatar_url in AVATAR_CACHE:
        return AVATAR_CACHE[avatar_url].copy()
    if avatar_url:
        try:
            r = requests.get(avatar_url, timeout=4)
            if r.status_code == 200:
                img = Image.open(io.BytesIO(r.content)).convert("RGBA")
                AVATAR_CACHE[avatar_url] = img
                return img.copy()
        except: pass
    try:
        fb_url = f"https://api.dicebear.com/9.x/adventurer/png?seed={username}&backgroundColor=transparent"
        r = requests.get(fb_url, timeout=4)
        if r.status_code == 200: return Image.open(io.BytesIO(r.content)).convert("RGBA")
    except: pass
    return Image.new("RGBA", (100, 100), (120, 120, 120, 255))

def apply_round_corners(img, radius):
    mask = Image.new('L', img.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0) + img.size, radius=radius, fill=255)
    output = Image.new('RGBA', img.size, (0, 0, 0, 0))
    output.paste(img, (0, 0), mask)
    return output

# ==========================================
# 🎨 GRAPHICS ENGINE
# ==========================================

def draw_premium_board(board):
    W, H = 700, 700
    # ✨ Ultra Premium 3D Gradient Base
    base = utils.get_gradient(W, H, (10, 10, 25), (40, 20, 90))
    img = Image.new('RGBA', (W, H), (0,0,0,0))
    img.paste(base, (0,0))
    d = ImageDraw.Draw(img)
    
    # 💎 Outer Glow Frame
    for i in range(6):
        alpha = 150 - (i * 20)
        d.rounded_rectangle([2+i, 2+i, W-2-i, H-2-i], radius=45, outline=f"#EC4899{alpha:02x}", width=2)
    
    # 🏷️ Title with Neon Effect
    utils.write_text(d, (W//2, 65), "TIC TAC TOE", size=55, align="center", col="#00F2FE", shadow=True)
    
    grid_sz = 510
    box_sz = grid_sz // 3
    mx, my = (W - grid_sz)//2, 140
    
    for i in range(9):
        r, c = i // 3, i % 3
        bx, by = mx + c * box_sz, my + r * box_sz
        
        # 📦 3D Box Effect
        # Inner Shadow
        d.rounded_rectangle([bx+6, by+6, bx+box_sz-6, by+box_sz-6], radius=22, fill=(20, 20, 45, 200))
        # Bevel/Highlight
        d.rounded_rectangle([bx+8, by+8, bx+box_sz-8, by+box_sz-8], radius=20, outline="#4facfe", width=3)
        # 3D Depth Bottom
        d.line([(bx+15, by+box_sz-8), (bx+box_sz-15, by+box_sz-8)], fill="#0061ff", width=4)
        
        symbol = board[i]
        cx, cy = bx + box_sz//2, by + box_sz//2
        
        if symbol == 'X':
            # ❌ Neon Red X with 3D shadow
            s = 40
            d.line([(cx-s+4, cy-s+4), (cx+s+4, cy+s+4)], fill=(0,0,0,100), width=14)
            d.line([(cx+s+4, cy-s+4), (cx-s+4, cy+s+4)], fill=(0,0,0,100), width=14)
            d.line([(cx-s, cy-s), (cx+s, cy+s)], fill="#FF3131", width=14) 
            d.line([(cx+s, cy-s), (cx-s, cy+s)], fill="#FF3131", width=14)
            # Glossy Highlight
            d.line([(cx-s, cy-s), (cx-s+15, cy-s+15)], fill="white", width=4)
            
        elif symbol == 'O':
            # ⭕ Neon Green O with 3D shadow
            s = 45
            d.ellipse([cx-s+4, cy-s+4, cx+s+4, cy+s+4], outline=(0,0,0,100), width=14)
            d.ellipse([cx-s, cy-s, cx+s, cy+s], outline="#39FF14", width=14)
            # Glossy Highlight
            d.arc([cx-s+5, cy-s+5, cx+s-5, cy+s-5], start=200, end=250, fill="white", width=5)
        else:
            utils.write_text(d, (cx, cy), str(i+1), size=35, col=(255, 255, 255, 30), align="center")
            
    return apply_round_corners(img, 45)

def draw_victory_card(winner_name, chips_won, avatar_url):
    W, H = 600, 600
    # 🌈 Magical Victory Gradient
    base = utils.get_gradient(W, H, (30, 10, 60), (10, 80, 120))
    img = Image.new('RGBA', (W, H), (0,0,0,0))
    img.paste(base, (0,0))
    d = ImageDraw.Draw(img)
    
    # 🌟 Golden 3D Frame
    for i in range(8):
        alpha = 255 - (i * 30)
        d.rounded_rectangle([i, i, W-i, H-i], radius=50, outline=f"#FFD700{alpha:02x}", width=2)
    
    # 👤 Avatar with Multi-layer Glow
    avatar_raw = get_avatar(avatar_url, winner_name)
    avatar = avatar_raw.resize((260, 260), Image.Resampling.LANCZOS)
    mask = Image.new('L', (260, 260), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, 260, 260), fill=255)
    
    cx, cy = W//2, 220
    # Outer Rainbow Glow
    for r in range(140, 155, 2):
        d.ellipse([cx-r, cy-r, cx+r, cy+r], outline="#00F2FE", width=2)
    # Golden Inner Border
    d.ellipse([cx-135, cy-135, cx+135, cy+135], outline="#FFD700", width=10)
    img.paste(avatar, (cx-130, cy-130), mask)
    
    # 🏆 Texts with 3D Shadows
    utils.write_text(d, (W//2, 390), "CHAMPION", size=35, align="center", col="#FFD700", shadow=True)
    utils.write_text(d, (W//2, 455), winner_name.upper(), size=55, align="center", col="white", shadow=True)
    
    # Chips Badge Effect
    # Custom drawn rounded rect to avoid font issues with boxes
    badge_w, badge_h = 360, 55
    bx, by = W//2 - badge_w//2, 510
    d.rounded_rectangle([bx, by, bx+badge_w, by+badge_h], radius=25, fill=(0, 255, 127, 50), outline="#00FF7F", width=3)
    utils.write_text(d, (W//2, 538), f"WON {chips_won} CHIPS", size=32, align="center", col="#00FF7F")
    
    return apply_round_corners(img, 50)

# ==========================================
# 💰 REFUND HELPER (Rule 6)
# ==========================================

def refund_chips(g):
    """Refunds bet to both players if PvP, or to p1 if Vs Bot"""
    if g.mode == 2: # PvP Mode
        if g.p1_id:
            db.update_balance(g.p1_id, g.p1_name, g.bet, 0)
        if g.p2_id and g.p2_id != "BOT":
            db.update_balance(g.p2_id, g.p2_name, g.bet, 0)
    elif g.mode == 1: # Bot Mode (Refund bet if any)
        if g.p1_id and g.bet > 0:
            db.update_balance(g.p1_id, g.p1_name, g.bet, 0)

# ==========================================
# 🧠 HANDLERS
# ==========================================

def handle_end(bot, rid, g, result):
    if result == 'draw':
        bot.send_message(rid, "🤝 **DRAW!** Bet refunded to balance.")
        refund_chips(g)
    else:
        winner_id = g.p1_id if result == 'X' else g.p2_id
        winner_name = g.p1_name if result == 'X' else g.p2_name
        winner_av = g.p1_av if result == 'X' else g.p2_av
        chips = (g.bet * 2) if g.mode == 2 else 100
        if winner_id != "BOT":
            # Add reward chips and 50 points (Score)
            db.add_game_result(winner_id, winner_name, "tictactoe", chips, True, 50)
            win_url = utils.upload(bot, draw_victory_card(winner_name, chips, winner_av))
            bot.send_json({"handler": "chatroommessage", "roomid": rid, "type": "image", "url": win_url, "text": "Champion!"})
        else: bot.send_message(rid, "🤖 **Bot Wins!**")
    with games_lock:
        if rid in games: del games[rid]

def check_winner(b):
    win_pos = [(0,1,2), (3,4,5), (6,7,8), (0,3,6), (1,4,7), (2,5,8), (0,4,8), (2,4,6)]
    for a, b1, c in win_pos:
        if b[a] and b[a] == b[b1] == b[c]: return b[a]
    return 'draw' if None not in b else None

class TicTacToeGame:
    def __init__(self, room_id, p1_id, p1_name, p1_av):
        self.room_id = room_id
        self.p1_id = p1_id; self.p1_name = p1_name; self.p1_av = p1_av
        self.p2_id = None; self.p2_name = None; self.p2_av = None
        self.board = [None]*9; self.turn = 'X'; self.bet = 0; self.mode = None; self.state = 'lobby'
        self.last_activity = time.time()
    def touch(self): self.last_activity = time.time()

# ==========================================
# 📨 MAIN COMMAND HANDLER
# ==========================================

def handle_command(bot, command, room_id, user, args, data):
    # ✅ FIX 0: Normalize Command Prefix
    text = data.get("text", "").lower().strip()
    cmd = command.lower().strip()
    
    # ✅ FIX 1: UID Consistency (Always String)
    uid = str(data.get('userid', ''))
    av_url = data.get("avatar") 

    # ✅ FIX 2 & 7: STANDARD STOP COMMAND (Safety & Refund)
    if cmd == "stop" or text == "!stop":
        with games_lock:
            g = games.get(room_id)
            if not g:
                bot.send_message(room_id, "⚠️ No active game in this room.")
                return True
            
            # ✅ Debug Trace (Rule 5)
            print(f"[Debug] UID: {uid} | P1: {g.p1_id} | P2: {g.p2_id} | State: {g.state}")

            # Allow P1 or joined P2 to stop (Works in all states: Rule 2)
            if uid == g.p1_id or (g.p2_id and uid == g.p2_id):
                refund_chips(g) # Rule 3 & 6
                bot.send_message(room_id, "🛑 **Game Stopped.** Chips refunded.")
                if room_id in games: del games[room_id] # Rule 4
                return True
            else:
                bot.send_message(room_id, "🚫 Only joined players can stop.")
                return True

    # Global Initialization
    if cmd == "tic":
        with games_lock:
            if room_id in games: return True
            games[room_id] = TicTacToeGame(room_id, uid, user, av_url)
        bot.send_message(room_id, f"🎮 **TIC TAC TOE**\n@{user}, choose:\n1️⃣ Vs Bot\n2️⃣ PvP (Bet)")
        return True

    with games_lock: g = games.get(room_id)
    if not g: return False

    # Mode Selection
    if g.state == 'lobby' and uid == g.p1_id:
        if cmd == "1":
            g.mode = 1; g.p2_name = "Bot"; g.p2_id = "BOT"; g.state = 'playing'; g.touch()
            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": utils.upload(bot, draw_premium_board(g.board)), "text": "Bot Start"})
            return True
        if cmd == "2":
            g.mode = 2; g.state = 'betting'; bot.send_message(room_id, "💰 **Bet amount?**")
            return True

    # PvP Setup
    if g.state == 'betting' and uid == g.p1_id and cmd == "bet":
        try:
            amt = int(args[0])
            if db.check_and_deduct_chips(uid, user, amt):
                g.bet = amt; g.state = 'waiting'; g.touch()
                bot.send_message(room_id, f"⚔️ @{user} bet **{amt} Chips**. Type `!join`.")
            else: bot.send_message(room_id, "❌ Not enough chips!")
        except: pass
        return True

    if g.state == 'waiting' and cmd == "join" and uid != g.p1_id:
        if db.check_and_deduct_chips(uid, user, g.bet):
            g.p2_id = uid; g.p2_name = user; g.p2_av = av_url; g.state = 'playing'; g.touch()
            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": utils.upload(bot, draw_premium_board(g.board)), "text": "Match Start"})
        else: bot.send_message(room_id, f"❌ Need {g.bet} Chips!")
        return True

    # Gameplay
    if g.state == 'playing' and cmd.isdigit():
        idx = int(cmd) - 1
        if not (0 <= idx <= 8) or g.board[idx]: return True
        if uid != (g.p1_id if g.turn == 'X' else g.p2_id): return False
        g.board[idx] = g.turn; g.touch()
        res = check_winner(g.board)
        if res: handle_end(bot, room_id, g, res); return True
        g.turn = 'O' if g.turn == 'X' else 'X'
        if g.mode == 1 and g.turn == 'O': # Bot Turn
            empty = [i for i, x in enumerate(g.board) if x is None]
            g.board[random.choice(empty)] = 'O'
            res = check_winner(g.board)
            if res: handle_end(bot, room_id, g, res); return True
            g.turn = 'X'
        bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": utils.upload(bot, draw_premium_board(g.board)), "text": "Move"})
        return True
    return False

# ==========================================
# ⏰ CLEANUP (Auto-Refund on Inactivity)
# ==========================================

def cleanup_loop():
    while True:
        time.sleep(15)
        now = time.time()
        with games_lock:
            to_del = []
            for rid, g in list(games.items()):
                if now - g.last_activity > 90:
                    to_del.append(rid)
            for rid in to_del:
                g = games[rid]
                refund_chips(g) # Same standard refund logic
                if BOT_REF:
                    BOT_REF.send_message(rid, "⏳ **Timeout!** Game closed and chips refunded.")
                del games[rid]
