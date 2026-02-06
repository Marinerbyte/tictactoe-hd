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
    print("[TicTacToe] Stop Logic Fixed & Feedback Added.")

# ==========================================
# 🖼️ AVATAR ENGINE
# ==========================================

def get_robust_avatar(avatar_url, username):
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
        if r.status_code == 200:
            return Image.open(io.BytesIO(r.content)).convert("RGBA")
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
    base = utils.get_gradient(W, H, (15, 15, 30), (35, 25, 60))
    img = Image.new('RGBA', (W, H), (0,0,0,0))
    img.paste(base, (0,0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([5, 5, W-5, H-5], radius=40, outline="#EC4899", width=4)
    utils.write_text(d, (W//2, 60), "TIC TAC TOE", size=45, align="center", col="white", shadow=True)

    grid_sz = 540
    box_sz = grid_sz // 3
    mx, my = (W - grid_sz)//2, 120
    for i in range(9):
        r, c = i // 3, i % 3
        bx, by = mx + c * box_sz, my + r * box_sz
        d.rounded_rectangle([bx+8, by+8, bx+box_sz-8, by+box_sz-8], radius=20, outline="#4facfe", width=4)
        symbol = board[i]
        cx, cy = bx + box_sz//2, by + box_sz//2
        if symbol == 'X':
            s = 45
            d.line([(cx-s, cy-s), (cx+s, cy+s)], fill="#ff4d4d", width=16) 
            d.line([(cx+s, cy-s), (cx-s, cy+s)], fill="#ff4d4d", width=16)
        elif symbol == 'O':
            s = 50
            d.ellipse([cx-s, cy-s, cx+s, cy+s], outline="#2ecc71", width=16)
        else:
            utils.write_text(d, (cx, cy), str(i+1), size=40, col=(255, 255, 255, 40), align="center")
    return apply_round_corners(img, 40)

def draw_victory_card(winner_name, chips_won, avatar_url):
    W, H = 600, 600
    base = utils.get_gradient(W, H, (20, 10, 40), (60, 20, 80))
    img = Image.new('RGBA', (W, H), (0,0,0,0))
    img.paste(base, (0,0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([5, 5, W-5, H-5], radius=50, outline="#FFD700", width=8)

    avatar = get_robust_avatar(avatar_url, winner_name)
    avatar = avatar.resize((240, 240), Image.Resampling.LANCZOS)
    mask = Image.new('L', (240, 240), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, 240, 240), fill=255)
    
    cx, cy = W//2, 210
    d.ellipse([cx-130, cy-130, cx+130, cy+130], outline="#EC4899", width=12)
    d.ellipse([cx-122, cy-122, cx+122, cy+122], outline="white", width=4)
    img.paste(avatar, (cx-120, cy-120), mask)

    utils.write_text(d, (W//2, 370), "🏆 CHAMPION 🏆", size=30, align="center", col="#FFD700")
    utils.write_text(d, (W//2, 435), winner_name.upper(), size=50, align="center", col="white", shadow=True)
    utils.write_text(d, (W//2, 520), f"WON {chips_won} CHIPS", size=38, align="center", col="#00FF7F")
    
    return apply_round_corners(img, 50)

# ==========================================
# 🧠 COMMON GAME-OVER HANDLER
# ==========================================

def handle_end(bot, rid, g, result):
    # Normalize ID for end check
    rid_str = str(rid)
    if result == 'draw':
        bot.send_message(rid, "🤝 **DRAW!** Chips refunded.")
        if g.mode == 2:
            db.update_balance(g.p1_id, g.p1_name, g.bet, 0)
            db.update_balance(g.p2_id, g.p2_name, g.bet, 0)
    else:
        w_id = g.p1_id if result == 'X' else g.p2_id
        w_name = g.p1_name if result == 'X' else g.p2_name
        w_av = g.p1_av if result == 'X' else g.p2_av
        chips = (g.bet * 2) if g.mode == 2 else 100
        
        if w_id != "BOT":
            db.add_game_result(w_id, w_name, "tictactoe", chips, True, 50)
            img_url = utils.upload(bot, draw_victory_card(w_name, chips, w_av))
            bot.send_json({"handler":"chatroommessage","roomid":rid,"type":"image","url":img_url,"text":f"Champion: @{w_name}"})
        else:
            bot.send_message(rid, "🤖 **Smart Bot Wins!** No chips for you.")

    with games_lock:
        if rid_str in games: del games[rid_str]

def check_winner(b):
    win_pos = [(0,1,2), (3,4,5), (6,7,8), (0,3,6), (1,4,7), (2,5,8), (0,4,8), (2,4,6)]
    for a, b1, c in win_pos:
        if b[a] and b[a] == b[b1] == b[c]: return b[a]
    if None not in b: return 'draw'
    return None

class TicTacToeGame:
    def __init__(self, room_id, p1_id, p1_name, p1_av):
        self.room_id = str(room_id)
        self.p1_id = p1_id; self.p1_name = p1_name; self.p1_av = p1_av
        self.p2_id = None; self.p2_name = None; self.p2_av = None
        self.board = [None]*9
        self.turn = 'X'; self.bet = 0; self.mode = None; self.state = 'lobby'
        self.last_interaction = time.time()
    def touch(self): self.last_interaction = time.time()

# ==========================================
# 📨 COMMAND HANDLER
# ==========================================

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    uid = str(data.get('userid', user))
    rid = str(room_id) # ✅ Normalize Room ID to string immediately
    av_url = data.get("avatar") 

    # --- 🛡️ STOP COMMAND (Bulletproof Fix) ---
    if cmd == "stop":
        with games_lock:
            g = games.get(rid)
            if not g:
                # Agar game hai hi nahi, toh reply do
                bot.send_message(rid, "⚠️ No active game in this room.")
                return True
            
            is_joined = (uid == g.p1_id or (g.p2_id and uid == g.p2_id))
            is_admin = uid in db.get_all_admins()

            if is_joined or is_admin:
                if g.mode == 2:
                    db.update_balance(g.p1_id, g.p1_name, g.bet, 0)
                    if g.p2_id and g.p2_id != "BOT":
                        db.update_balance(g.p2_id, g.p2_name, g.bet, 0)
                
                bot.send_message(rid, "🛑 **Game Stopped.** Refund processed.")
                if rid in games: del games[rid]
                return True
            else:
                bot.send_message(rid, f"🚫 @{user}, only players or admins can stop this.")
                return True

    with games_lock: g = games.get(rid)
    
    if cmd == "tic":
        if g: return True
        with games_lock: games[rid] = TicTacToeGame(rid, uid, user, av_url)
        bot.send_message(rid, f"🎮 **TIC TAC TOE**\n@{user}, Choose Mode:\n1️⃣ Vs Bot\n2️⃣ PvP (Bet)")
        return True

    if not g: return False

    # Lobby State
    if g.state == 'lobby' and uid == g.p1_id:
        if cmd == "1":
            g.mode = 1; g.p2_name = "Smart Bot"; g.p2_id = "BOT"; g.state = 'playing'; g.touch()
            bot.send_json({"handler":"chatroommessage","roomid":rid,"type":"image","url":utils.upload(bot, draw_premium_board(g.board)),"text":"Bot Game Start"})
            return True
        if cmd == "2":
            g.mode = 2; g.state = 'betting'; bot.send_message(rid, "💰 **Bet amount?**")
            return True

    # Betting & Joining
    if g.state == 'betting' and uid == g.p1_id and cmd == "bet":
        try:
            amt = int(args[0])
            if db.check_and_deduct_chips(uid, user, amt):
                g.bet = amt; g.state = 'waiting'; g.touch()
                bot.send_message(rid, f"⚔️ @{user} bet **{amt} Chips**. Type `!join`.")
            else: bot.send_message(rid, "❌ Not enough chips!")
        except: pass
        return True

    if g.state == 'waiting' and cmd == "join" and uid != g.p1_id:
        if db.check_and_deduct_chips(uid, user, g.bet):
            g.p2_id = uid; g.p2_name = user; g.p2_av = av_url; g.state = 'playing'; g.touch()
            bot.send_json({"handler":"chatroommessage","roomid":rid,"type":"image","url":utils.upload(bot, draw_premium_board(g.board)),"text":"PvP Start"})
        else: bot.send_message(rid, f"❌ Need {g.bet} Chips!")
        return True

    # Playing State
    if g.state == 'playing' and cmd.isdigit():
        idx = int(cmd)-1
        if not (0<=idx<=8) or g.board[idx] or uid != (g.p1_id if g.turn == 'X' else g.p2_id): return False
        
        g.board[idx] = g.turn; g.touch()
        res = check_winner(g.board)
        if res:
            handle_end(bot, rid, g, res)
            return True
        
        g.turn = 'O' if g.turn == 'X' else 'X'
        
        # Bot Move
        if g.mode == 1 and g.turn == 'O':
            empty = [i for i, x in enumerate(g.board) if x is None]
            g.board[random.choice(empty)] = 'O'
            res = check_winner(g.board)
            if res:
                handle_end(bot, rid, g, res)
                return True
            g.turn = 'X'

        img_url = utils.upload(bot, draw_premium_board(g.board))
        bot.send_json({"handler":"chatroommessage","roomid":rid,"type":"image","url":img_url,"text":"Move"})
        return True

    return False

# ==========================================
# ⏰ CLEANUP (Auto-Refund on 90s)
# ==========================================

def cleanup_loop():
    while True:
        time.sleep(15) 
        now = time.time()
        with games_lock:
            to_del = []
            for rid, g in list(games.items()):
                if now - g.last_interaction > 90:
                    to_del.append(rid)
            
            for rid in to_del:
                g = games[rid]
                if g.mode == 2:
                    db.update_balance(g.p1_id, g.p1_name, g.bet, 0)
                    if g.p2_id and g.p2_id != "BOT":
                        db.update_balance(g.p2_id, g.p2_name, g.bet, 0)
                
                if BOT_REF:
                    BOT_REF.send_message(rid, "⏳ **Timeout!** Game closed and chips refunded.")
                
                if rid in games: del games[rid]
