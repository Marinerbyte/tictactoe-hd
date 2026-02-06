import time
import random
import threading
import sys
import os
from PIL import Image, ImageDraw
import utils
import db

# --- GLOBAL STATE ---
games = {} 
games_lock = threading.Lock()
AVATAR_CACHE = {}

def setup(bot_ref):
    print("[TicTacToe] PvP Economy System Integrated.")

# ==========================================
# 🖼️ AVATAR & RENDERING (Existing Styles)
# ==========================================
def get_robust_avatar(url, username):
    try:
        if url:
            r = utils.requests.get(url, timeout=5)
            if r.status_code == 200:
                return Image.open(utils.io.BytesIO(r.content)).convert("RGBA")
    except: pass
    return Image.new("RGBA", (100, 100), (40, 40, 45))

def draw_premium_board(board, p1_name, p2_name, turn):
    W, H = 700, 700
    img = utils.get_gradient(W, H, (15, 15, 30), (35, 25, 60))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([5, 5, W-5, H-5], radius=40, outline="#EC4899", width=4)
    utils.write_text(d, (W//2, 60), "TIC TAC TOE", size=45, align="center", col="white")
    
    grid_sz = 450
    box_sz = grid_sz // 3
    mx, my = (W - grid_sz)//2, 120
    for i in range(9):
        r, c = i // 3, i % 3
        bx, by = mx + c * box_sz, my + r * box_sz
        d.rectangle([bx+5, by+5, bx+box_sz-5, by+box_sz-5], outline="#4facfe", width=2)
        symbol = board[i]
        if symbol:
            col = "#ff4d4d" if symbol == 'X' else "#4facfe"
            utils.write_text(d, (bx+box_sz//2, by+box_sz//2), symbol, size=60, align="center", col=col)
    
    curr = p1_name if turn == 'X' else p2_name
    utils.write_text(d, (W//2, 630), f"TURN: {curr.upper()}", size=30, align="center", col="#00FFFF")
    return img

# ==========================================
# 🧠 GAME LOGIC
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
        self.p2_id = None; self.p2_name = None; self.p2_av = None
        self.board = [None]*9
        self.turn = 'X'; self.bet = 0; self.mode = None; self.state = 'lobby'
        self.last_interaction = time.time()
    def touch(self): self.last_interaction = time.time()

# ==========================================
# 📨 HANDLERS
# ==========================================

def handle_end(bot, rid, g, result):
    """Game khatam hone par Points aur Chips dena"""
    if result == 'draw':
        bot.send_message(rid, "🤝 **DRAW!** Chips sabko wapas mil gaye.")
        # Refund Chips
        if g.mode == 2:
            db.update_balance(g.p1_id, g.p1_name, g.bet, 0)
            db.update_balance(g.p2_id, g.p2_name, g.bet, 0)
    else:
        winner_uid = g.p1_id if result == 'X' else g.p2_id
        winner_name = g.p1_name if result == 'X' else g.p2_name
        
        points_reward = 50 # Fixed Reputation
        chips_reward = 0

        if g.mode == 1: # Vs Bot
            chips_reward = 50 if winner_uid != "BOT" else 0
        else: # Vs Player
            chips_reward = g.bet * 2 # Dono ki bet winner ko

        if winner_uid != "BOT":
            db.add_game_result(winner_uid, winner_name, "tictactoe", chips_reward, True, points_reward)
            bot.send_message(rid, f"🏆 **{winner_name} Wins!**\nReward: {chips_reward} Chips & {points_reward} Points.")
        else:
            bot.send_message(rid, "🤖 **Smart Bot Wins!** Player ko kuch nahi mila.")

    with games_lock:
        if rid in games: del games[rid]

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip(); uid = str(data.get('userid', user))
    av_url = data.get("avatar") 

    with games_lock: g = games.get(room_id)
    
    if cmd == "tic":
        if g: return True
        with games_lock: games[room_id] = TicTacToeGame(room_id, uid, user, av_url)
        bot.send_message(room_id, f"🎮 **TIC TAC TOE**\n@{user}, Mode select karo:\n1️⃣ Vs Bot\n2️⃣ Multiplayer (Bet)")
        return True

    if not g: return False

    # Lobby State
    if g.state == 'lobby' and uid == g.p1_id:
        if cmd == "1":
            g.mode = 1; g.p2_name = "Smart Bot"; g.p2_id = "BOT"; g.state = 'playing'; g.touch()
            bot.send_message(room_id, "🤖 **Vs Bot Started!** (No chips required)")
            return True
        if cmd == "2":
            g.mode = 2; g.state = 'betting'; bot.send_message(room_id, "💰 **Bet kitni hogi?** (e.g. `!bet 500`)")
            return True

    # Betting State (Host sets bet)
    if g.state == 'betting' and uid == g.p1_id and cmd == "bet":
        try:
            amt = int(args[0])
            if db.check_and_deduct_chips(uid, user, amt):
                g.bet = amt; g.state = 'waiting'; g.touch()
                bot.send_message(room_id, f"⚔️ @{user} ne **{amt} Chips** ki bet lagayi! Type `!join` to accept.")
            else:
                bot.send_message(room_id, f"❌ @{user}, balance kam hai!")
        except: pass
        return True

    # Waiting State (Player 2 joins)
    if g.state == 'waiting' and cmd == "join" and uid != g.p1_id:
        if db.check_and_deduct_chips(uid, user, g.bet):
            g.p2_id = uid; g.p2_name = user; g.p2_av = av_url; g.state = 'playing'; g.touch()
            bot.send_message(room_id, f"🔥 @{user} joined! Game shuru.")
            # Initial Board
            img = draw_premium_board(g.board, g.p1_name, g.p2_name, 'X')
            bot.send_json({"handler":"chatroommessage","roomid":room_id,"type":"image","url":utils.upload(bot, img),"text":"Match Start"})
        else:
            bot.send_message(room_id, f"❌ @{user}, tere paas {g.bet} chips nahi hain!")
        return True

    # Stop / Refund Logic
    if cmd == "stop" and (uid == g.p1_id or user.lower() == "yasin"):
        if g.bet > 0:
            db.update_balance(g.p1_id, g.p1_name, g.bet, 0)
            if g.p2_id and g.p2_id != "BOT":
                db.update_balance(g.p2_id, g.p2_name, g.bet, 0)
        bot.send_message(room_id, "🛑 Game stopped. Chips refunded.")
        with games_lock: del games[room_id]
        return True

    # Playing State
    if g.state == 'playing' and cmd.isdigit():
        idx = int(cmd)-1
        if not (0<=idx<=8) or g.board[idx] or uid != (g.p1_id if g.turn == 'X' else g.p2_id): return False
        
        g.board[idx] = g.turn; g.touch()
        res = check_winner(g.board)
        if res: handle_end(bot, room_id, g, res); return True
        
        g.turn = 'O' if g.turn == 'X' else 'X'
        
        # Smart Bot Move
        if g.mode == 1 and g.turn == 'O':
            empty = [i for i, x in enumerate(g.board) if x is None]
            b_move = random.choice(empty)
            g.board[b_move] = 'O'; res = check_winner(g.board)
            if res: handle_end(bot, room_id, g, res); return True
            g.turn = 'X'

        img = draw_premium_board(g.board, g.p1_name, g.p2_name, g.turn)
        bot.send_json({"handler":"chatroommessage","roomid":room_id,"type":"image","url":utils.upload(bot, img),"text":"Move"})
        return True

    return False

# Cleanup with Refund
def cleanup_loop():
    while True:
        time.sleep(30); now = time.time(); to_del = []
        with games_lock:
            for rid, g in games.items():
                if now - g.last_interaction > 120: 
                    # Refund logic
                    if g.bet > 0:
                        db.update_balance(g.p1_id, g.p1_name, g.bet, 0)
                        if g.p2_id and g.p2_id != "BOT":
                            db.update_balance(g.p2_id, g.p2_name, g.bet, 0)
                    to_del.append(rid)
            for rid in to_del: del games[rid]

threading.Thread(target=cleanup_loop, daemon=True).start()
