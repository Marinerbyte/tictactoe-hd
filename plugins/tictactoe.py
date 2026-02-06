import time
import random
import threading
import sys
import os
import requests
import io
from PIL import Image, ImageDraw

# ==========================================
# 🔌 CONNECT TO DB (Folder Fix)
# ==========================================
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

try:
    import utils
    import db  # Tumhara Naya Powerful DB
except ImportError:
    print("[TicTacToe] Error: Core modules (db.py or utils.py) not found.")

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
games = {}
games_lock = threading.Lock()
AVATAR_CACHE = {}

# Rewards Config
REWARD_FREE_CHIPS = 100
REWARD_WIN_POINTS = 50
REWARD_LOSE_POINTS = 10

def setup(bot):
    print("[TicTacToe] Plugin Loaded (Economy Integrated).")

# ==========================================
# 🎨 GRAPHICS ENGINE
# ==========================================

def get_robust_avatar(url, name):
    """Crash-Proof Avatar Loader"""
    if url and url in AVATAR_CACHE: return AVATAR_CACHE[url].copy()
    try:
        if url and "http" in url:
            r = requests.get(url, timeout=3)
            img = Image.open(io.BytesIO(r.content)).convert("RGBA")
            AVATAR_CACHE[url] = img; return img
    except: pass
    try:
        # Fallback to DiceBear
        r = requests.get(f"https://api.dicebear.com/9.x/initials/png?seed={name}", timeout=3)
        return Image.open(io.BytesIO(r.content)).convert("RGBA")
    except: return Image.new("RGBA", (100,100), (50,50,50))

def draw_board(board, p1, p2, turn):
    """High Quality 1:1 Board"""
    W, H = 700, 700
    img = utils.create_canvas(W, H, (20, 20, 35)) # Dark Theme
    d = ImageDraw.Draw(img)
    
    # Border
    utils.draw_rounded_card(W-10, H-10, 40, (0,0,0,0), outline="#EC4899", wth=4)
    utils.write_text(d, (W//2, 50), "TIC TAC TOE", 40, "white", "center")
    
    # Grid
    gs = 540; bs = gs//3; mx, my = (W-gs)//2, 120
    for i in range(9):
        r, c = i//3, i%3
        bx, by = mx+c*bs, my+r*bs
        
        # Box Design
        d.rounded_rectangle([bx+5, by+5, bx+bs-5, by+bs-5], 20, outline="#4facfe", width=3)
        
        sym = board[i]
        cx, cy = bx+bs//2, by+bs//2
        
        if sym == 'X': 
            utils.write_text(d, (cx, cy), "X", 80, "#FF4444", "center", shadow=True)
        elif sym == 'O': 
            utils.write_text(d, (cx, cy), "O", 80, "#44FFFF", "center", shadow=True)
        else: 
            utils.write_text(d, (cx, cy), str(i+1), 30, (80,80,80), "center")
    
    # Turn Info
    curr_name = p1 if turn=='X' else p2
    utils.write_text(d, (W//2, 660), f"TURN: {curr_name}", 25, "yellow", "center")
    return img

# ==========================================
# 🧠 GAME LOGIC
# ==========================================

class TTTGame:
    def __init__(self, rid, pid, name, av):
        self.rid=rid; self.p1=pid; self.p1n=name; self.p1av=av
        self.p2=None; self.p2n=None; self.p2av=None
        self.board=[None]*9
        self.turn='X'; self.bet=0; self.mode=0; self.state='lobby'

def check_win(b):
    wins = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
    for x,y,z in wins:
        if b[x] and b[x]==b[y]==b[z]: return b[x]
    if None not in b: return 'd' # Draw
    return None

def bot_move(b):
    e = [i for i,x in enumerate(b) if x is None]
    if not e: return None
    # 1. Win if possible, 2. Block enemy, 3. Random
    for s in ['O', 'X']:
        for m in e:
            b[m]=s
            if check_win(b)==s: b[m]=None; return m
            b[m]=None
    return random.choice(e)

# ==========================================
# 🎮 COMMAND HANDLER
# ==========================================

def handle_command(bot, cmd, rid, user, args, data):
    uid = str(data.get('userid', user))
    av = data.get('avatar') or data.get('icon')
    
    with games_lock: 
        g = games.get(rid)
    
    cmd = cmd.lower().strip()

    # --- 1. START GAME ---
    if cmd == "tic":
        if g: return True
        with games_lock: games[rid] = TTTGame(rid, uid, user, av)
        bot.send_message(rid, "🎮 TicTacToe!\n1️⃣ Vs Bot (Win 100)\n2️⃣ PvP (Bet Betting)")
        return True
    
    if not g: return False
    
    # --- 2. STOP GAME ---
    if cmd == "stop" and uid == g.p1:
        with games_lock: del games[rid]
        # Note: Agar betting ho chuki thi aur game start nahi hua, to manual refund karna pad sakta hai.
        # Lekin 'lobby' state me paise nahi kate hote, to safe hai.
        bot.send_message(rid, "🛑 Game Stopped.")
        return True

    # --- 3. MODE SELECTION ---
    if g.state == 'lobby' and uid == g.p1:
        if cmd == "1": # VS BOT
            g.mode=1; g.p2="BOT"; g.p2n="Bot"; g.state='play'
            # Start Image
            threading.Thread(target=lambda: bot.send_json({"handler":"chatroommessage","roomid":rid,"type":"image","url":utils.upload(bot, draw_board(g.board, g.p1n, "Bot", 'X'))})).start()
            return True
        
        if cmd == "2": # PVP
            g.state='bet'
            bot.send_message(rid, "💰 Enter bet amount: (e.g., `!bet 500`)")
            return True

    # --- 4. BETTING (Strict Check) ---
    if g.state == 'bet' and uid == g.p1 and cmd == "bet":
        try:
            amt = int(args[0])
            if amt < 100:
                bot.send_message(rid, "⚠️ Minimum bet is 100.")
                return True
            
            # ⚡ CORE LOGIC: Check & Deduct
            if db.check_and_deduct(uid, user, amt):
                g.bet = amt
                g.state = 'wait'
                bot.send_message(rid, f"⚔️ Bet Placed: {amt} Chips.\nWaiting for opponent... Type `!join`")
            else:
                bot.send_message(rid, "❌ You don't have enough chips!")
        except: pass
        return True

    # --- 5. JOINING (Strict Check) ---
    if g.state == 'wait' and cmd == "join" and uid != g.p1:
        # ⚡ CORE LOGIC: Deduct from P2
        if db.check_and_deduct(uid, user, g.bet):
            g.p2=uid; g.p2n=user; g.p2av=av
            g.state='play'
            threading.Thread(target=lambda: bot.send_json({"handler":"chatroommessage","roomid":rid,"type":"image","url":utils.upload(bot, draw_board(g.board, g.p1n, g.p2n, 'X'))})).start()
        else:
            bot.send_message(rid, "❌ You don't have enough chips to join!")
        return True

    # --- 6. GAMEPLAY ---
    if g.state == 'play' and cmd.isdigit():
        idx = int(cmd)-1
        curr = g.p1 if g.turn=='X' else g.p2
        
        # Validation
        if not (0<=idx<=8) or g.board[idx] or uid != curr: return False
        
        g.board[idx] = g.turn
        res = check_win(g.board)
        
        if res:
            # === GAME OVER LOGIC ===
            if res == 'd':
                bot.send_message(rid, "🤝 Draw! Money Refunded.")
                if g.mode == 2:
                    # Refund Chips (Points = 0)
                    db.add_game_result(g.p1, g.p1n, "tictactoe", g.bet, 0, 'refund')
                    db.add_game_result(g.p2, g.p2n, "tictactoe", g.bet, 0, 'refund')
            
            else:
                # Winner Identified
                win_id = g.p1 if res=='X' else g.p2
                win_nm = g.p1n if res=='X' else g.p2n
                lose_id = g.p2 if res=='X' else g.p1
                
                if win_id == "BOT":
                    bot.send_message(rid, "🤖 Bot Wins! Better luck next time.")
                    # Player loses (0 Chips, 10 Points)
                    db.add_game_result(g.p1, g.p1n, "tictactoe", 0, REWARD_LOSE_POINTS, 'loss')
                
                else:
                    # Real Player Wins
                    chips_won = 0
                    if g.mode == 1: # Vs Bot
                        chips_won = REWARD_FREE_CHIPS # 100 Chips
                    else: # PvP
                        chips_won = g.bet * 2 # Double Money
                    
                    # Winner Gets: Chips + 50 Points
                    db.add_game_result(win_id, win_nm, "tictactoe", chips_won, REWARD_WIN_POINTS, 'win')
                    
                    # Loser Gets: 0 Chips + 10 Points (Only in PvP)
                    if g.mode == 2:
                        db.add_game_result(lose_id, "Loser", "tictactoe", 0, REWARD_LOSE_POINTS, 'loss')

                    bot.send_message(rid, f"🏆 {win_nm} Wins {chips_won} Chips! (+{REWARD_WIN_POINTS} Points)")

            with games_lock: del games[rid]
            return True

        # Switch Turn
        g.turn = 'O' if g.turn=='X' else 'X'
        
        # Bot Turn (If active)
        if g.mode==1 and g.turn=='O':
            m = bot_move(g.board)
            if m is not None:
                g.board[m]='O'
                if check_win(g.board):
                    bot.send_message(rid, "🤖 Bot Wins!")
                    db.add_game_result(g.p1, g.p1n, "tictactoe", 0, REWARD_LOSE_POINTS, 'loss')
                    with games_lock: del games[rid]
                    return True
                g.turn='X'

        # Next Image
        threading.Thread(target=lambda: bot.send_json({"handler":"chatroommessage","roomid":rid,"type":"image","url":utils.upload(bot, draw_board(g.board, g.p1n, g.p2n, g.turn))})).start()
        return True
    
    return False
