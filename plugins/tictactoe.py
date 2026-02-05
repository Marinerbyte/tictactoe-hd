import time
import random
import threading
import traceback
import sys
import os
import uuid
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

def setup(bot_ref):
    global BOT_INSTANCE
    BOT_INSTANCE = bot_ref
    print("[TicTacToe] Smart AI & Chips Economy System Ready.")

# ==========================================
# 🎨 GRAPHICS ENGINE (Board & Winner Card)
# ==========================================

def draw_premium_board(board, p1_name, p2_name, turn, pool):
    W, H = 600, 750
    # 1. Midnight Gradient Background
    img = utils.get_gradient(W, H, (10, 15, 30), (30, 10, 50))
    d = ImageDraw.Draw(img, 'RGBA')

    # 2. Header Panel (Glassmorphism)
    d.rounded_rectangle([40, 30, 560, 150], radius=30, fill=(0,0,0,160), outline="#EC4899", width=3)
    utils.write_text(d, (W//2, 65), "NEON TIC-TAC-TOE", size=35, align="center", col="#FBB03B", shadow=True)
    utils.write_text(d, (W//2, 115), f"🎰 POOL: {pool} CHIPS", size=25, align="center", col="#2ecc71")

    # 3. Smart Neon Grid
    grid_sz = 450
    cell = grid_sz // 3
    mx, my = (W - grid_sz)//2, 200
    for i in range(1, 3):
        d.line([(mx + cell*i, my), (mx + cell*i, my + grid_sz)], fill="#EC4899", width=6)
        d.line([(mx, my + cell*i), (mx + grid_sz, my + cell*i)], fill="#EC4899", width=6)

    # 4. Symbols
    for i in range(9):
        r, c = i // 3, i % 3
        cx, cy = mx + c*cell + cell//2, my + r*cell + cell//2
        symbol = board[i]
        if symbol == 'X':
            s = 40
            d.line([(cx-s, cy-s), (cx+s, cy+s)], fill="#ff4d4d", width=14)
            d.line([(cx+s, cy-s), (cx-s, cy+s)], fill="#ff4d4d", width=14)
        elif symbol == 'O':
            s = 45
            d.ellipse([cx-s, cy-s, cx+s, cy+s], outline="#4facfe", width=14)
        else:
            utils.write_text(d, (cx, cy), str(i+1), size=30, col=(255,255,255,30), align="center")

    utils.write_text(d, (W//2, 700), f"👉 Turn: {p1_name if turn == 'X' else p2_name}", size=28, align="center", col="white")
    return img

def draw_victory_card(winner_name, chips_won, avatar_url):
    W, H = 600, 600 # 1:1 Ratio
    img = utils.get_gradient(W, H, (15, 12, 41), (48, 43, 99))
    d = ImageDraw.Draw(img, 'RGBA')
    
    # DiceBear Decorative Shapes Background
    for _ in range(3):
        seed = random.randint(1, 9999)
        shape_url = f"https://api.dicebear.com/9.x/shapes/png?seed={seed}&size=250&backgroundColor=transparent"
        shape_img = utils.get_image(shape_url)
        if shape_img:
            shape_img.putalpha(45)
            img.paste(shape_img, (random.randint(0,350), random.randint(0,350)), shape_img)

    # Avatar with Glowing Neon Ring
    if not avatar_url:
        avatar_url = f"https://api.dicebear.com/9.x/adventurer/png?seed={winner_name}&size=300"
    
    avatar = utils.get_image(avatar_url)
    if avatar:
        avatar = avatar.resize((280, 280), Image.Resampling.LANCZOS)
        mask = Image.new('L', (280, 280), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, 280, 280), fill=255)
        cx, cy = W//2, 220
        r = 145
        d.ellipse([cx-r-10, cy-r-10, cx+r+10, cy+r+10], outline=(236, 72, 153, 100), width=15)
        d.ellipse([cx-r, cy-r, cx+r, cy+r], outline="#EC4899", width=8)
        img.paste(avatar, (cx-140, cy-140), mask)

    # Champion Branding
    d.rounded_rectangle([120, 390, 480, 455], radius=20, fill=(0,0,0,180), outline="#FBB03B", width=3)
    utils.write_text(d, (W//2, 423), "🎉 CHAMPION 🎉", size=32, align="center", col="#FBB03B", shadow=True)
    utils.write_text(d, (W//2, 500), winner_name.upper(), size=50, align="center", col="white", shadow=True)
    utils.write_text(d, (W//2, 560), f"WON {chips_won} CHIPS", size=30, align="center", col="#2ecc71")
    return img

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
    win_msg = ""; winner_uid = None; winner_name = ""; winner_av = ""; reward = 0
    if result == 'draw':
        win_msg = "🤝 **DRAW!** Chips refunded."
        if g.mode == 2:
            add_game_result(g.p1_id, g.p1_name, "tictactoe", g.bet, False)
            add_game_result(g.p2_id, g.p2_name, "tictactoe", g.bet, False)
        bot.send_message(rid, win_msg)
    else:
        winner_uid = g.p1_id if result == 'X' else g.p2_id
        winner_name = g.p1_name if result == 'X' else g.p2_name
        winner_av = g.p1_av if result == 'X' else g.p2_av
        if g.mode == 1:
            if winner_uid == "BOT":
                bot.send_message(rid, "🤖 **Smart Bot Wins!** Better luck next time yasin.")
            else: reward = 500
        else: reward = g.bet * 2

        if winner_uid != "BOT":
            add_game_result(winner_uid, winner_name, "tictactoe", reward, True)
            def victory():
                img = draw_victory_card(winner_name, reward, winner_av)
                url = utils.upload(bot, img)
                if url: bot.send_json({"handler":"chatroommessage","roomid":rid,"type":"image","url":url,"text":f"Winner: @{winner_name}"})
            utils.run_in_bg(victory)
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
        bot.send_message(room_id, f"🎮 **Neon Tic-Tac-Toe**\n@{user}, choose:\n1️⃣ Vs Bot (Free | Win 500)\n2️⃣ Multiplayer (Bet Required)")
        return True
    if not g: return False
    if cmd == "stop" and (uid == g.p1_id or user.lower() == "yasin"):
        with games_lock: del games[room_id]
        bot.send_message(room_id, "🛑 Game Stopped.")
        return True
    if g.state == 'lobby' and uid == g.p1_id:
        if cmd == "1":
            g.mode = 1; g.p2_name = "Smart Bot"; g.p2_id = "BOT"; g.state = 'playing'; g.touch()
            def start():
                img = draw_premium_board(g.board, g.p1_name, "Smart Bot", 'X', 500)
                bot.send_json({"handler":"chatroommessage","roomid":room_id,"type":"image","url":utils.upload(bot, img),"text":"Start"})
            utils.run_in_bg(start); return True
        if cmd == "2":
            g.mode = 2; g.state = 'betting'; bot.send_message(room_id, "💰 Bet amount? (e.g. `!bet 500`)"); return True
    if g.state == 'betting' and uid == g.p1_id and cmd == "bet":
        try:
            amt = int(args[0])
            if amt < 100: return True
            g.bet = amt; g.state = 'waiting'; g.touch(); add_game_result(uid, user, "tictactoe", -amt, False)
            bot.send_message(room_id, f"⚔️ @{user} is waiting! Bet: {amt} Chips. Type `!join`.")
        except: pass
        return True
    if g.state == 'waiting' and cmd == "join" and uid != g.p1_id:
        g.p2_id = uid; g.p2_name = user; g.p2_av = av_url; g.state = 'playing'; g.touch(); add_game_result(uid, user, "tictactoe", -g.bet, False)
        def vs():
            img = draw_premium_board(g.board, g.p1_name, g.p2_name, 'X', g.bet*2)
            bot.send_json({"handler":"chatroommessage","roomid":room_id,"type":"image","url":utils.upload(bot, img),"text":"VS"})
        utils.run_in_bg(vs); return True
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
        def update():
            img = draw_premium_board(g.board, g.p1_name, g.p2_name, g.turn, (500 if g.mode==1 else g.bet*2))
            bot.send_json({"handler":"chatroommessage","roomid":room_id,"type":"image","url":utils.upload(bot, img),"text":"Move"})
        utils.run_in_bg(update); return True
    return False

# Cleanup Thread
def cleanup():
    while True:
        time.sleep(20); now = time.time(); to_del = []
        with games_lock:
            for rid, g in games.items():
                if now - g.last_interaction > 90: to_del.append(rid)
        for rid in to_del:
            if BOT_INSTANCE: BOT_INSTANCE.send_message(rid, "⌛ Game Expired.")
            with games_lock:
                if rid in games: del games[rid]
threading.Thread(target=cleanup, daemon=True).start()
