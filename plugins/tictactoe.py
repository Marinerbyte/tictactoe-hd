import time
import random
import threading
import traceback
import sys
import os
import uuid
import requests
import io
from PIL import Image, ImageDraw, ImageFilter, ImageOps

# --- UTILS & DB IMPORTS ---
try:
    import utils
except ImportError:
    print("[TicTacToe] Error: utils.py missing!")

try:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from db import add_game_result
except Exception as e:
    print(f"DB Error: {e}")

# --- GLOBAL STATE ---
games = {} 
games_lock = threading.Lock()
BOT_INSTANCE = None 
AVATAR_CACHE = {}

def setup(bot_ref):
    global BOT_INSTANCE
    BOT_INSTANCE = bot_ref
    print("[TicTacToe] Ultra HD 1:1 Visuals Loaded.")

# ==========================================
# 🖼️ ROBUST AVATAR ENGINE
# ==========================================

def get_robust_avatar(avatar_url, username):
    if avatar_url in AVATAR_CACHE:
        return AVATAR_CACHE[avatar_url].copy()
    try:
        if avatar_url:
            r = requests.get(avatar_url, timeout=5)
            if r.status_code == 200:
                img = Image.open(io.BytesIO(r.content)).convert("RGBA")
                AVATAR_CACHE[avatar_url] = img
                return img.copy()
    except: pass
    try:
        fb_url = f"https://api.dicebear.com/9.x/adventurer/png?seed={username}&backgroundColor=transparent"
        r = requests.get(fb_url, timeout=5)
        return Image.open(io.BytesIO(r.content)).convert("RGBA")
    except:
        return Image.new("RGBA", (100, 100), (40, 40, 45))

def apply_round_corners(img, radius):
    mask = Image.new('L', img.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0) + img.size, radius=radius, fill=255)
    output = Image.new('RGBA', img.size, (0, 0, 0, 0))
    output.paste(img, (0, 0), mask)
    return output

# ==========================================
# 🎨 GRAPHICS ENGINE (1:1 Ratio + Round Borders)
# ==========================================

def draw_premium_board(board, p1_name, p2_name, turn):
    # 1:1 Strict Ratio
    W, H = 700, 700
    base = utils.get_gradient(W, H, (15, 15, 30), (35, 25, 60))
    img = Image.new('RGBA', (W, H), (0,0,0,0))
    img.paste(base, (0,0))
    d = ImageDraw.Draw(img)

    # Outer Border (Card Look)
    d.rounded_rectangle([5, 5, W-5, H-5], radius=40, outline="#EC4899", width=4)

    # 1. Header (Clean Text Only)
    utils.write_text(d, (W//2, 60), "TIC TAC TOE", size=45, align="center", col="white", shadow=True)

    # 2. Bigger Grid
    grid_sz = 540
    box_sz = grid_sz // 3
    mx, my = (W - grid_sz)//2, 120
    
    for i in range(9):
        r, c = i // 3, i % 3
        bx, by = mx + c * box_sz, my + r * box_sz
        
        # Premium Neon Boxes
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

    # 3. Footer
    curr_player = p1_name if turn == 'X' else p2_name
    utils.write_text(d, (W//2, 650), f"TURN: {curr_player.upper()}", size=30, align="center", col="#00FFFF")
    
    return apply_round_corners(img, 40)

def draw_victory_card(winner_name, chips_won, avatar_url):
    W, H = 600, 600
    base = utils.get_gradient(W, H, (20, 10, 40), (60, 20, 80))
    img = Image.new('RGBA', (W, H), (0,0,0,0))
    img.paste(base, (0,0))
    d = ImageDraw.Draw(img)
    
    # 3D Effect Outer Border
    d.rounded_rectangle([5, 5, W-5, H-5], radius=50, outline=(255, 215, 0, 150), width=8) # Main Gold
    d.rounded_rectangle([12, 12, W-12, H-12], radius=45, outline=(0, 0, 0, 100), width=2) # Inner shadow

    # Avatar Handling
    avatar = get_robust_avatar(avatar_url, winner_name)
    avatar = avatar.resize((240, 240), Image.Resampling.LANCZOS)
    mask = Image.new('L', (240, 240), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, 240, 240), fill=255)
    
    cx, cy = W//2, 210
    # Glowing Ring
    d.ellipse([cx-135, cy-135, cx+135, cy+135], outline=(236, 72, 153, 120), width=15)
    d.ellipse([cx-125, cy-125, cx+125, cy+125], outline="#FFD700", width=6)
    img.paste(avatar, (cx-120, cy-120), mask)

    # Winner Text
    utils.write_text(d, (W//2, 380), "CHAMPION", size=32, align="center", col="#FFD700")
    utils.write_text(d, (W//2, 450), winner_name.upper(), size=55, align="center", col="white", shadow=True)
    utils.write_text(d, (W//2, 530), f"WON {chips_won} CHIPS", size=38, align="center", col="#00FF7F")
    
    return apply_round_corners(img, 50)

# ==========================================
# 🧠 SMART AI & LOGIC
# ==========================================

def get_smart_move(board):
    empty = [i for i, x in enumerate(board) if x is None]
    for m in empty:
        board[m] = 'O'
        if check_winner(board) == 'O': 
            board[m] = None; return m
        board[m] = None
    for m in empty:
        board[m] = 'X'
        if check_winner(board) == 'X': 
            board[m] = None; return m
        board[m] = None
    if 4 in empty: return 4
    corners = [i for i in [0, 2, 6, 8] if i in empty]
    if corners: return random.choice(corners)
    return random.choice(empty)

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

# ==========================================
# 📨 HANDLERS
# ==========================================

def handle_end(bot, rid, g, result):
    winner_uid = None; winner_name = ""; winner_av = ""; reward = 0
    if result == 'draw':
        bot.send_message(rid, "🤝 DRAW! CHIPS refunded.")
        if g.mode == 2:
            add_game_result(g.p1_id, g.p1_name, "tictactoe", g.bet, False)
            add_game_result(g.p2_id, g.p2_name, "tictactoe", g.bet, False)
    else:
        winner_uid = g.p1_id if result == 'X' else g.p2_id
        winner_name = g.p1_name if result == 'X' else g.p2_name
        winner_av = g.p1_av if result == 'X' else g.p2_av
        
        if g.mode == 1:
            if winner_uid == "BOT":
                bot.send_message(rid, "🤖 Smart Bot Wins!")
            else: reward = 500
        else: reward = g.bet * 2

        if winner_uid != "BOT":
            add_game_result(winner_uid, winner_name, "tictactoe", reward, True)
            def victory_task():
                img = draw_victory_card(winner_name, reward, winner_av)
                url = utils.upload(bot, img)
                if url: bot.send_json({"handler":"chatroommessage","roomid":rid,"type":"image","url":url,"text":f"Winner: @{winner_name}"})
            threading.Thread(target=victory_task).start()

    with games_lock:
        if rid in games: del games[rid]

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip(); uid = str(data.get('userid', user))
    av_url = data.get("avatar") 

    with games_lock: g = games.get(room_id)
    
    if cmd == "tic":
        if g: return True
        with games_lock: games[room_id] = TicTacToeGame(room_id, uid, user, av_url)
        bot.send_message(room_id, f"🎮 TIC TAC TOE\n@{user}, choose:\n1️⃣ Vs Bot (Win 500 CHIPS)\n2️⃣ Multiplayer (Bet Required)")
        return True

    if not g: return False

    if cmd == "stop" and (uid == g.p1_id or user.lower() == "yasin"):
        with games_lock: 
            if room_id in games: del games[room_id]
        bot.send_message(room_id, "🛑 Game has been stopped.")
        return True

    if g.state == 'lobby' and uid == g.p1_id:
        if cmd == "1":
            g.mode = 1; g.p2_name = "Smart Bot"; g.p2_id = "BOT"; g.state = 'playing'; g.touch()
            def start_task():
                img = draw_premium_board(g.board, g.p1_name, "Smart Bot", 'X')
                bot.send_json({"handler":"chatroommessage","roomid":room_id,"type":"image","url":utils.upload(bot, img),"text":"Game Start"})
            threading.Thread(target=start_task).start()
            return True
        if cmd == "2":
            g.mode = 2; g.state = 'betting'; bot.send_message(room_id, "💰 Bet amount? (e.g. `!bet 500`)")
            return True

    if g.state == 'betting' and uid == g.p1_id and cmd == "bet":
        try:
            amt = int(args[0])
            if amt < 100: return True
            g.bet = amt; g.state = 'waiting'; g.touch()
            add_game_result(uid, user, "tictactoe", -amt, False)
            bot.send_message(room_id, f"⚔️ @{user} is waiting! Bet: {amt} CHIPS. Type `!join`.")
        except: pass
        return True

    if g.state == 'waiting' and cmd == "join" and uid != g.p1_id:
        g.p2_id = uid; g.p2_name = user; g.p2_av = av_url; g.state = 'playing'; g.touch()
        add_game_result(uid, user, "tictactoe", -g.bet, False)
        def join_task():
            img = draw_premium_board(g.board, g.p1_name, g.p2_name, 'X')
            bot.send_json({"handler":"chatroommessage","roomid":room_id,"type":"image","url":utils.upload(bot, img),"text":"Battle Start"})
        threading.Thread(target=join_task).start()
        return True

    if g.state == 'playing' and cmd.isdigit():
        idx = int(cmd)-1
        if not (0<=idx<=8) or g.board[idx] or uid != (g.p1_id if g.turn == 'X' else g.p2_id): return False
        g.board[idx] = g.turn; g.touch(); res = check_winner(g.board)
        if res: handle_end(bot, room_id, g, res); return True
        g.turn = 'O' if g.turn == 'X' else 'X'
        
        if g.mode == 1 and g.turn == 'O':
            b_move = get_smart_move(g.board); g.board[b_move] = 'O'; res = check_winner(g.board)
            if res: handle_end(bot, room_id, g, res); return True
            g.turn = 'X'

        def update_task():
            img = draw_premium_board(g.board, g.p1_name, g.p2_name, g.turn)
            bot.send_json({"handler":"chatroommessage","roomid":room_id,"type":"image","url":utils.upload(bot, img),"text":"Move"})
        threading.Thread(target=update_task).start()
        return True
    return False

def cleanup_loop():
    while True:
        time.sleep(20); now = time.time(); to_del = []
        with games_lock:
            for rid, g in games.items():
                if now - g.last_interaction > 90: to_del.append(rid)
            for rid in to_del:
                if rid in games: del games[rid]
threading.Thread(target=cleanup_loop, daemon=True).start()
