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

def setup(bot_ref):
    print("[TicTacToe] Ultra HD 1:1 Economy Version Loaded.")

# ==========================================
# 🖼️ AVATAR ENGINE
# ==========================================

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
    fb_url = f"https://api.dicebear.com/9.x/adventurer/png?seed={username}&backgroundColor=transparent"
    try:
        r = requests.get(fb_url, timeout=5)
        return Image.open(io.BytesIO(r.content)).convert("RGBA")
    except: return Image.new("RGBA", (100, 100), (40, 40, 45))

def apply_round_corners(img, radius):
    mask = Image.new('L', img.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0) + img.size, radius=radius, fill=255)
    output = Image.new('RGBA', img.size, (0, 0, 0, 0))
    output.paste(img, (0, 0), mask)
    return output

# ==========================================
# 🎨 GRAPHICS ENGINE (Board & Winner Card)
# ==========================================

def draw_premium_board(board, p1_name, p2_name, turn):
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
            d.ellipse([cx-s, cy-s, cx+s, cy+s], outline="#4facfe", width=16)
        else:
            utils.write_text(d, (cx, cy), str(i+1), size=35, col=(255, 255, 255, 15), align="center")

    curr_player = p1_name if turn == 'X' else p2_name
    utils.write_text(d, (W//2, 650), f"TURN: {curr_player.upper()}", size=30, align="center", col="#00FFFF")
    return apply_round_corners(img, 40)

def draw_victory_card(winner_name, chips_won, points_won, avatar_url):
    """Bhai ye hai tera naya Mast Winner Card"""
    W, H = 600, 600
    # Premium Dark Gradient
    base = utils.get_gradient(W, H, (20, 10, 40), (60, 20, 80))
    img = Image.new('RGBA', (W, H), (0,0,0,0))
    img.paste(base, (0,0))
    d = ImageDraw.Draw(img)
    
    # Gold Neon Border
    d.rounded_rectangle([5, 5, W-5, H-5], radius=50, outline="#FFD700", width=8)

    # Winner Avatar Logic
    avatar = get_robust_avatar(avatar_url, winner_name)
    avatar = avatar.resize((240, 240), Image.Resampling.LANCZOS)
    mask = Image.new('L', (240, 240), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, 240, 240), fill=255)
    
    cx, cy = W//2, 210
    # Double Ring Glow
    d.ellipse([cx-130, cy-130, cx+130, cy+130], outline="#EC4899", width=12)
    d.ellipse([cx-122, cy-122, cx+122, cy+122], outline="white", width=4)
    img.paste(avatar, (cx-120, cy-120), mask)

    # Championship Text (TTF via utils)
    utils.write_text(d, (W//2, 370), "🏆 CHAMPION 🏆", size=30, align="center", col="#FFD700")
    utils.write_text(d, (W//2, 435), winner_name.upper(), size=50, align="center", col="white", shadow=True)
    
    # Reward Section
    reward_text = f"+{chips_won} Chips | +{points_won} Points"
    utils.write_text(d, (W//2, 520), reward_text, size=35, align="center", col="#00FF7F")
    
    return apply_round_corners(img, 50)

# ==========================================
# 🧠 LOGIC & HANDLERS
# ==========================================

def check_winner(b):
    win_pos = [(0,1,2), (3,4,5), (6,7,8), (0,3,6), (1,4,7), (2,5,8), (0,4,8), (2,4,6)]
    for a, b1, c in win_pos:
        if b[a] and b[a] == b[b1] == b[c]: return b[a]
    if None not in b: return 'draw'
    return None

class TicTacToeGame:
    def __init__(self, room_id, p1_id, p1_name, p1_av):
        self.room_id = room_id
        self.p1_id = p1_id; self.p1_name = p1_name; self.p1_av = p1_av
        self.p2_id = self.p2_name = self.p2_av = None
        self.board = [None]*9
        self.turn = 'X'; self.bet = 0; self.mode = None; self.state = 'lobby'
        self.last_interaction = time.time()
    def touch(self): self.last_interaction = time.time()

def handle_end(bot, rid, g, result):
    if result == 'draw':
        bot.send_message(rid, "🤝 **DRAW!** Chips sabko wapas mil gaye.")
        if g.mode == 2:
            db.update_balance(g.p1_id, g.p1_name, g.bet, 0)
            db.update_balance(g.p2_id, g.p2_name, g.bet, 0)
    else:
        winner_uid = g.p1_id if result == 'X' else g.p2_id
        winner_name = g.p1_name if result == 'X' else g.p2_name
        winner_av = g.p1_av if result == 'X' else g.p2_av
        
        points_won = 50 # Fixed
        chips_won = (g.bet * 2) if g.mode == 2 else 50 # PvP vs Bot rewards

        if winner_uid != "BOT":
            db.add_game_result(winner_uid, winner_name, "tictactoe", chips_won, True, points_won)
            # Winner Card Task
            def victory_task():
                img = draw_victory_card(winner_name, chips_won, points_won, winner_av)
                url = utils.upload(bot, img)
                if url: bot.send_json({"handler":"chatroommessage","roomid":rid,"type":"image","url":url,"text":f"Champion: @{winner_name}"})
            threading.Thread(target=victory_task).start()
        else: bot.send_message(rid, "🤖 **Smart Bot Wins!** Player ko kuch nahi mila.")

    with games_lock:
        if rid in games: del games[rid]

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip(); uid = str(data.get('userid', user))
    av_id = data.get("avatar")
    av_url = f"https://cdn.howdies.app/avatar?image={av_id}" if av_id else None

    with games_lock: g = games.get(room_id)
    
    if cmd == "tic":
        if g: return True
        with games_lock: games[room_id] = TicTacToeGame(room_id, uid, user, av_url)
        bot.send_message(room_id, f"🎮 **TIC TAC TOE**\n@{user}, Choose Mode:\n1️⃣ Vs Bot\n2️⃣ Multiplayer (Bet)")
        return True

    if not g: return False

    # Stop Logic (Refund if PvP)
    if cmd == "stop" and (uid == g.p1_id or user.lower() == "yasin"):
        if g.mode == 2:
            db.update_balance(g.p1_id, g.p1_name, g.bet, 0)
            if g.p2_id and g.p2_id != "BOT": db.update_balance(g.p2_id, g.p2_name, g.bet, 0)
        bot.send_message(room_id, "🛑 Game stopped and chips refunded.")
        with games_lock: del games[room_id]
        return True

    # 1. Start Vs Bot (Instant Board)
    if g.state == 'lobby' and uid == g.p1_id and cmd == "1":
        g.mode = 1; g.p2_name = "Smart Bot"; g.p2_id = "BOT"; g.state = 'playing'; g.touch()
        def start_task():
            img = draw_premium_board(g.board, g.p1_name, "Smart Bot", 'X')
            bot.send_json({"handler":"chatroommessage","roomid":room_id,"type":"image","url":utils.upload(bot, img),"text":"Match Start"})
        threading.Thread(target=start_task).start()
        return True

    # 2. Multiplayer Setup
    if g.state == 'lobby' and uid == g.p1_id and cmd == "2":
        g.mode = 2; g.state = 'betting'; bot.send_message(room_id, "💰 **Bet amount?** (e.g. `!bet 500`)")
        return True

    if g.state == 'betting' and uid == g.p1_id and cmd == "bet":
        try:
            amt = int(args[0])
            if db.check_and_deduct_chips(uid, user, amt):
                g.bet = amt; g.state = 'waiting'; g.touch()
                bot.send_message(room_id, f"⚔️ @{user} bet **{amt} Chips**. Type `!join` to play!")
            else: bot.send_message(room_id, "❌ Balance kam hai!")
        except: pass
        return True

    if g.state == 'waiting' and cmd == "join" and uid != g.p1_id:
        if db.check_and_deduct_chips(uid, user, g.bet):
            g.p2_id = uid; g.p2_name = user; g.p2_av = av_url; g.state = 'playing'; g.touch()
            def join_task():
                img = draw_premium_board(g.board, g.p1_name, g.p2_name, 'X')
                bot.send_json({"handler":"chatroommessage","roomid":room_id,"type":"image","url":utils.upload(bot, img),"text":"PvP Start"})
            threading.Thread(target=join_task).start()
        else: bot.send_message(room_id, f"❌ Need {g.bet} Chips!")
        return True

    # 3. Playing
    if g.state == 'playing' and cmd.isdigit():
        idx = int(cmd)-1
        if not (0<=idx<=8) or g.board[idx] or uid != (g.p1_id if g.turn == 'X' else g.p2_id): return False
        
        g.board[idx] = g.turn; g.touch()
        res = check_winner(g.board)
        if res: handle_end(bot, room_id, g, res); return True
        
        g.turn = 'O' if g.turn == 'X' else 'X'
        
        if g.mode == 1 and g.turn == 'O': # Bot move
            empty = [i for i, x in enumerate(g.board) if x is None]
            b_move = random.choice(empty)
            g.board[b_move] = 'O'; res = check_winner(g.board)
            if res: handle_end(bot, room_id, g, res); return True
            g.turn = 'X'

        img = draw_premium_board(g.board, g.p1_name, g.p2_name, g.turn)
        bot.send_json({"handler":"chatroommessage","roomid":room_id,"type":"image","url":utils.upload(bot, img),"text":"Move"})
        return True

    return False

# Automatic Cleanup (with Refunds)
def cleanup_loop():
    while True:
        time.sleep(30); now = time.time(); to_del = []
        with games_lock:
            for rid, g in games.items():
                if now - g.last_interaction > 120:
                    if g.mode == 2:
                        db.update_balance(g.p1_id, g.p1_name, g.bet, 0)
                        if g.p2_id and g.p2_id != "BOT": db.update_balance(g.p2_id, g.p2_name, g.bet, 0)
                    to_del.append(rid)
            for rid in to_del: del games[rid]
threading.Thread(target=cleanup_loop, daemon=True).start()
