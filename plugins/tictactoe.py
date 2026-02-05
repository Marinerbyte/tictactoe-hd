import time
import random
import threading
import traceback
import sys
import os
import uuid
import requests
import io
from PIL import Image, ImageDraw, ImageFilter

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
AVATAR_CACHE = {} # Cache for DP to avoid repeated downloads

def setup(bot_ref):
    global BOT_INSTANCE
    BOT_INSTANCE = bot_ref
    print("[TicTacToe] Fixed UI & Robust Avatar System Loaded.")

# ==========================================
# 🖼️ ROBUST AVATAR ENGINE
# ==========================================

def get_robust_avatar(avatar_url, username):
    """Downloads DP safely, uses caching and provides DiceBear fallback."""
    if avatar_url in AVATAR_CACHE:
        return AVATAR_CACHE[avatar_url].copy()

    try:
        if avatar_url:
            # Safe download with timeout
            r = requests.get(avatar_url, timeout=5)
            if r.status_code == 200:
                img = Image.open(io.BytesIO(r.content)).convert("RGBA")
                AVATAR_CACHE[avatar_url] = img
                return img.copy()
    except:
        pass

    # Fallback to DiceBear if download fails or URL is missing
    try:
        fb_url = f"https://api.dicebear.com/9.x/adventurer/png?seed={username}&backgroundColor=transparent"
        r = requests.get(fb_url, timeout=5)
        img = Image.open(io.BytesIO(r.content)).convert("RGBA")
        return img
    except:
        # Absolute fallback: simple gray circle
        return Image.new("RGBA", (100, 100), (50, 50, 50))

def circle_crop(img, size):
    """Crops an image into a circle."""
    img = img.resize((size, size), Image.Resampling.LANCZOS)
    mask = Image.new('L', (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size, size), fill=255)
    output = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    output.paste(img, (0, 0), mask)
    return output

# ==========================================
# 🎨 GRAPHICS ENGINE (1:1 Ratio)
# ==========================================

def draw_premium_board(board, p1_name, p2_name, turn, pool):
    # 1:1 Strict Ratio
    W, H = 700, 700
    # Midnight Gradient Background
    img = utils.get_gradient(W, H, (10, 15, 30), (30, 10, 50))
    d = ImageDraw.Draw(img, 'RGBA')

    # 1. Clean Header (Reduced Height, No Emojis)
    # Header box
    d.rounded_rectangle([20, 20, 680, 110], radius=20, fill=(0, 0, 0, 150), outline="#EC4899", width=2)
    utils.write_text(d, (W//2, 45), "TIC TAC TOE", size=32, align="center", col="white", shadow=True)
    utils.write_text(d, (W//2, 85), f"POOL: {pool} CHIPS", size=22, align="center", col="#2ecc71")

    # 2. Enhanced Grid (Premium Separated Boxes)
    grid_sz = 450
    box_sz = grid_sz // 3
    mx, my = (W - grid_sz)//2, 140
    
    for i in range(9):
        r, c = i // 3, i % 3
        bx = mx + c * box_sz
        by = my + r * box_sz
        
        # Draw individual neon boxes
        # Border color based on status (slight glow effect)
        d.rounded_rectangle([bx+5, by+5, bx+box_sz-5, by+box_sz-5], radius=15, outline="#4facfe", width=3)
        
        symbol = board[i]
        cx, cy = bx + box_sz//2, by + box_sz//2
        
        if symbol == 'X':
            s = 35
            d.line([(cx-s, cy-s), (cx+s, cy+s)], fill="#ff4d4d", width=12)
            d.line([(cx+s, cy-s), (cx-s, cy+s)], fill="#ff4d4d", width=12)
        elif symbol == 'O':
            s = 40
            d.ellipse([cx-s, cy-s, cx+s, cy+s], outline="#4facfe", width=12)
        else:
            # Subtle number hint
            utils.write_text(d, (cx, cy), str(i+1), size=25, col=(255, 255, 255, 20), align="center")

    # 3. Footer Area
    footer_y = 620
    curr_player = p1_name if turn == 'X' else p2_name
    utils.write_text(d, (W//2, footer_y), f"TURN: {curr_player}", size=26, align="center", col="white")
    utils.write_text(d, (W//2, footer_y + 40), "Type 1-9 to play", size=18, align="center", col="#8888AA")
    
    return img

def draw_victory_card(winner_name, chips_won, avatar_url):
    # 1:1 Ratio
    W, H = 600, 600
    img = utils.get_gradient(W, H, (15, 12, 41), (48, 43, 99))
    d = ImageDraw.Draw(img, 'RGBA')
    
    # DiceBear Decorative Shapes Background
    for _ in range(3):
        seed = random.randint(1, 9999)
        shape_url = f"https://api.dicebear.com/9.x/shapes/png?seed={seed}&size=250&backgroundColor=transparent"
        shape_img = get_robust_avatar(shape_url, "shape")
        if shape_img:
            shape_img.putalpha(45)
            img.paste(shape_img, (random.randint(0, 350), random.randint(0, 350)), shape_img)

    # Avatar Handling (Robust)
    avatar = get_robust_avatar(avatar_url, winner_name)
    avatar = circle_crop(avatar, 250)
    
    cx, cy = W//2, 220
    # Neon Ring
    d.ellipse([cx-135, cy-135, cx+135, cy+135], outline=(236, 72, 153, 100), width=12)
    d.ellipse([cx-128, cy-128, cx+128, cy+128], outline="#EC4899", width=6)
    img.paste(avatar, (cx-125, cy-125), avatar)

    # Winner Text
    utils.write_text(d, (W//2, 400), "CHAMPION", size=30, align="center", col="#FBB03B")
    utils.write_text(d, (W//2, 460), winner_name.upper(), size=45, align="center", col="white", shadow=True)
    utils.write_text(d, (W//2, 530), f"WON {chips_won} CHIPS", size=32, align="center", col="#2ecc71")
    
    return img

# ==========================================
# 🧠 GAME LOGIC (STRICTLY PRESERVED)
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
    av_url = data.get("avatar") # DIRECTLY FROM PAYLOAD

    with games_lock: g = games.get(room_id)
    
    if cmd == "tic":
        if g: return True
        with games_lock: games[room_id] = TicTacToeGame(room_id, uid, user, av_url)
        bot.send_message(room_id, f"🎮 TIC TAC TOE\n@{user}, choose:\n1️⃣ Vs Bot (Win 500 CHIPS)\n2️⃣ Multiplayer (Bet Required)")
        return True

    if not g: return False

    # !stop Command Fix
    if cmd == "stop" and (uid == g.p1_id or user.lower() == "yasin"):
        with games_lock: 
            if room_id in games: del games[room_id]
        bot.send_message(room_id, "🛑 Game has been stopped.")
        return True

    if g.state == 'lobby' and uid == g.p1_id:
        if cmd == "1":
            g.mode = 1; g.p2_name = "Smart Bot"; g.p2_id = "BOT"; g.state = 'playing'; g.touch()
            def start_task():
                img = draw_premium_board(g.board, g.p1_name, "Smart Bot", 'X', 500)
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
            img = draw_premium_board(g.board, g.p1_name, g.p2_name, 'X', g.bet*2)
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
            pool_val = 500 if g.mode == 1 else g.bet*2
            img = draw_premium_board(g.board, g.p1_name, g.p2_name, g.turn, pool_val)
            bot.send_json({"handler":"chatroommessage","roomid":room_id,"type":"image","url":utils.upload(bot, img),"text":"Move"})
        threading.Thread(target=update_task).start()
        return True
    return False

# Cleanup Thread
def cleanup_loop():
    while True:
        time.sleep(20); now = time.time(); to_del = []
        with games_lock:
            for rid, g in games.items():
                if now - g.last_interaction > 90: to_del.append(rid)
            for rid in to_del:
                if rid in games: del games[rid]
threading.Thread(target=cleanup_loop, daemon=True).start()
