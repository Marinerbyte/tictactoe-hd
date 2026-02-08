import threading
import time
import random
import io
import requests
import traceback
from PIL import Image, ImageDraw, ImageOps, ImageFilter
import db
import utils

# ======================================================
# ⚙️ GLOBAL ENGINE CONFIGURATION
# ======================================================
# Default rewards (Admin can change these via !tchips / !tscore)
BOT_WIN_REWARD_CHIPS = 100
BOT_WIN_REWARD_SCORE = 50
PVP_WIN_REWARD_SCORE = 50

# Timers (Strictly enforced)
LOBBY_TIMEOUT = 120   # 2 minutes to start a game
MOVE_TIMEOUT = 90     # 90 seconds per move

# Extreme Concurrency & Memory Management
AV_CACHE = {}         # Global Avatar Cache to save bandwidth
GAMES = {}            # Isolated Room Boxes
GAMES_LOCK = threading.Lock()

def setup(bot):
    """Howdies Plugin Loader Confirmation"""
    print("[TicTacToe-HD] MASTER ENGINE v6.0 - STATUS: OPERATIONAL")

# ======================================================
# 🖼️ ADVANCED IMAGE & AVATAR SYSTEM
# ======================================================

def get_avatar_robust(user_id, username, avatar_url=None):
    """
    Multi-stage Avatar Fetcher:
    1. Memory Cache check (Fastest)
    2. Provided URL fetch (Direct)
    3. Platform ID API fetch (Official)
    4. Dicebear Adventurer Generation (Fallback)
    5. Initials Canvas (Last Resort)
    """
    if user_id in AV_CACHE:
        return AV_CACHE[user_id].copy()

    img = None
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    # Stage 1: Direct URL
    if avatar_url and str(avatar_url) != "None" and len(str(avatar_url)) > 10:
        try:
            r = requests.get(avatar_url, timeout=4, headers=headers)
            if r.status_code == 200:
                img = Image.open(io.BytesIO(r.content)).convert("RGBA")
        except: pass

    # Stage 2: Official Platform API
    if not img:
        try:
            api_av = f"https://api.howdies.app/api/avatar/{user_id}"
            r = requests.get(api_av, timeout=3, headers=headers)
            if r.status_code == 200:
                img = Image.open(io.BytesIO(r.content)).convert("RGBA")
        except: pass

    # Stage 3: Dicebear Dynamic Character
    if not img:
        try:
            dice_url = f"https://api.dicebear.com/9.x/adventurer/png?seed={username}&backgroundColor=b6e3f4"
            r = requests.get(dice_url, timeout=3)
            if r.status_code == 200:
                img = Image.open(io.BytesIO(r.content)).convert("RGBA")
        except: pass

    # Stage 4: High-Quality Initials Placeholder
    if not img:
        img = Image.new('RGBA', (260, 260), (30, 30, 50))
        d = ImageDraw.Draw(img)
        char = username[0].upper() if username else "?"
        utils.write_text(d, (130, 130), char, size=150, col="white", align="center")

    # Save to Cache and Return
    AV_CACHE[user_id] = img
    return img.copy()

def apply_round_corners(img, radius):
    """High-fidelity rounded corner masking"""
    mask = Image.new("L", img.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, img.size[0], img.size[1]), radius, fill=255)
    output = Image.new("RGBA", img.size, (0, 0, 0, 0))
    output.paste(img, (0, 0), mask)
    return output

# ======================================================
# 🎨 PREMIUM GRAPHICS: NEON BOARD & CHAMPION CARD
# ======================================================

def draw_premium_board(board):
    """Generates the 700x700 Cinematic Neon Board"""
    W, H = 700, 700
    base = utils.get_gradient(W, H, (10, 10, 25), (40, 20, 90))
    img = Image.new('RGBA', (W, H))
    img.paste(base, (0, 0))
    d = ImageDraw.Draw(img)

    # Multi-layered Neon Border Glow
    for i in range(6):
        alpha = 150 - (i * 20)
        d.rounded_rectangle([2+i, 2+i, W-2-i, H-2-i], radius=45, outline=f"#EC4899{alpha:02x}", width=2)

    utils.write_text(d, (W // 2, 65), "TIC TAC TOE", size=55, align="center", col="#00F2FE", shadow=True)

    grid_size = 510
    box_size = grid_size // 3
    sx, sy = (W - grid_size) // 2, 140

    for i in range(9):
        r, c = i // 3, i % 3
        x, y = sx + c * box_size, sy + r * box_size
        
        # Stylized Cell
        d.rounded_rectangle([x+6, y+6, x+box_size-6, y+box_size-6], radius=22, fill=(20, 20, 45, 200))
        d.rounded_rectangle([x+8, y+8, x+box_size-8, y+box_size-8], radius=20, outline="#4facfe", width=3)

        symbol = str(board[i])
        cx, cy = x + box_size // 2, y + box_size // 2
        
        if symbol == 'X':
            # Red Neon X
            s = 40
            d.line([(cx-s, cy-s), (cx+s, cy+s)], fill="#FF3131", width=14)
            d.line([(cx+s, cy-s), (cx-s, cy+s)], fill="#FF3131", width=14)
        elif symbol == 'O':
            # Green Neon O
            s = 45
            d.ellipse([cx-s, cy-s, cx+s, cy+s], outline="#39FF14", width=14)
        else:
            # Ghost number for empty cells
            utils.write_text(d, (cx, cy), symbol, size=35, col=(255, 255, 255, 40), align="center")

    return apply_round_corners(img, 45)

def draw_victory_card(winner_name, chips_won, score_won, user_id, avatar_url):
    """Premium 600x600 Victory Card with RED TEXT logic"""
    W, H = 600, 600
    base = utils.get_gradient(W, H, (30, 10, 60), (10, 80, 120))
    img = Image.new('RGBA', (W, H))
    img.paste(base, (0, 0))
    d = ImageDraw.Draw(img)

    # 8-Layer Golden Frame
    for i in range(8):
        alpha = 255 - (i * 30)
        d.rounded_rectangle([i, i, W-i, H-i], radius=50, outline=f"#FFD700{alpha:02x}", width=2)

    # DP with mask and resize
    av_raw = get_avatar_robust(user_id, winner_name, avatar_url)
    av = av_raw.resize((260, 260), Image.Resampling.LANCZOS)
    mask = Image.new('L', (260, 260), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, 260, 260), fill=255)
    
    cx, cy = W // 2, 220
    # DP Glow Rings
    for r in range(140, 155, 2): d.ellipse([cx-r, cy-r, cx+r, cy+r], outline="#00F2FE", width=2)
    d.ellipse([cx-135, cy-135, cx+135, cy+135], outline="#FFD700", width=10)
    img.paste(av, (cx-130, cy-130), mask)

    utils.write_text(d, (W//2, 390), "CHAMPION", size=35, align="center", col="#FFD700", shadow=True)
    utils.write_text(d, (W//2, 450), winner_name.upper(), size=55, align="center", col="white", shadow=True)

    # Rewards Badge (Original greenish-transparent background)
    bw, bh = 420, 110
    bx, by = W//2 - bw//2, 485
    d.rounded_rectangle([bx, by, bx+bw, by+bh], radius=25, fill=(0, 255, 127, 40), outline="#00FF7F", width=3)

    # --- TEXT COLORS (FIXED AS PER REQUEST) ---
    # WON CHIPS in RED
    utils.write_text(d, (W//2, by + 30), f"WON {chips_won} CHIPS", size=32, align="center", col="#FF0000")
    # SCORE in BLUE
    utils.write_text(d, (W//2, by + 72), f"+{score_won} SCORE REWARD", size=26, align="center", col="#00F2FE")

    return apply_round_corners(img, 50)

# ======================================================
# 📦 ENGINE CORE: ROOM ISOLATION & LOGIC
# ======================================================

class TicBox:
    """Thread-safe isolated game dabba per room"""
    def __init__(self, room_id, p1_data):
        self.room_id = room_id
        self.lock = threading.Lock()
        self.status = "SELECT_MODE" # SELECT_MODE, LOBBY, PLAYING
        self.last_act = time.time()
        
        # Participants
        self.p1 = p1_data # {id, name, av}
        self.p2 = None
        
        # State
        self.board = [str(i+1) for i in range(9)]
        self.mode = 0  # 1=Bot, 2=PVP
        self.bet = 0
        self.turn = None

def cleanup_room(rid):
    """Memory Management: Clean reference to allow Garbage Collection"""
    with GAMES_LOCK:
        if rid in GAMES:
            del GAMES[rid]

def check_victory_sanitized(brd):
    """Crash-proof win check (Only X and O)"""
    wins = [(0,1,2), (3,4,5), (6,7,8), (0,3,6), (1,4,7), (2,5,8), (0,4,8), (2,4,6)]
    for a, b, c in wins:
        if brd[a] in ['X', 'O'] and brd[a] == brd[b] == brd[c]:
            return brd[a]
    if all(x in ['X', 'O'] for x in brd):
        return 'DRAW'
    return None

def bot_brain_logic(brd):
    """Industrial AI: Strategic Win/Block priority"""
    lines = [(0,1,2), (3,4,5), (6,7,8), (0,3,6), (1,4,7), (2,5,8), (0,4,8), (2,4,6)]
    # Win First, then Block
    for symbol in ['O', 'X']:
        for a, b, c in lines:
            if brd[a] == symbol and brd[b] == symbol and brd[c] not in ['X','O']: return c
            if brd[a] == symbol and brd[c] == symbol and brd[b] not in ['X','O']: return b
            if brd[b] == symbol and brd[c] == symbol and brd[a] not in ['X','O']: return a
    # Take Center if available
    if brd[4] == '5': return 4
    # Take Corners
    corners = [i for i in [0,2,6,8] if brd[i] not in ['X','O']]
    if corners: return random.choice(corners)
    # Random Valid
    valid = [i for i, x in enumerate(brd) if x not in ['X','O']]
    return random.choice(valid) if valid else None

# --- ASYNC BOT EXECUTION (Scaling friendly) ---

def process_bot_async(bot, g):
    """Handles Bot turn without blocking main thread"""
    with g.lock:
        # State Guard
        if g.status != "PLAYING" or g.mode != 1 or g.turn != 'BOT':
            return
        
        idx = bot_brain_logic(g.board)
        if idx is not None:
            g.board[idx] = 'O'
            res = check_victory_sanitized(g.board)
            if res:
                handle_match_termination(bot, g, res)
                return
            
            # Match continues, return turn to player
            g.turn = g.p1['id']
            g.last_act = time.time()
            img_url = bot.upload_to_server(draw_premium_board(g.board))
            bot.send_json({"handler": "chatroommessage", "roomid": g.room_id, "type": "image", "url": img_url, "text": "BOT moved! Your baari (X):"})

# ======================================================
# 📡 COMMAND DISPATCHER
# ======================================================

def handle_command(bot, cmd, room_id, user, args, data):
    # Normalized ID mapping from Bot Engine
    uid = str(data.get('userid'))
    current_av = data.get('avatar')

    # --- 1. ADMIN BOSS SUITE (!sync logic) ---
    if cmd in ["stop", "tchips", "tscore"] and bot.is_boss(user, uid):
        if cmd == "stop":
            cleanup_room(room_id)
            bot.send_message(room_id, "🛑 Boss forced match termination.")
        return True

    # --- 2. SESSION CONTROLLER (!tic) ---
    if cmd == "tic":
        action = args[0] if args else ""
        
        # Start Session
        if action == "1":
            if room_id in GAMES:
                bot.send_message(room_id, "⚠️ Active session already exists."); return True
            with GAMES_LOCK:
                GAMES[room_id] = TicBox(room_id, {'id': uid, 'name': user, 'av': current_av})
            bot.send_message(room_id, "🎮 **TIC TAC TOE SESSION START**\n\nOptions:\n1️⃣ Play with BOT (100c)\n2️⃣ PVP Betting (Type: `2 <bet>`)\n\n(120s lobby timer active)")
            return True

        # Kill Session / Surrender
        elif action == "0":
            g = GAMES.get(room_id)
            if not g: return True
            with g.lock:
                if bot.is_boss(user, uid) or uid == g.p1['id']:
                    # Refund logic for open lobby
                    if g.status == "LOBBY" and g.bet > 0:
                        db.update_balance(g.p1['id'], g.p1['name'], chips_change=g.bet)
                    bot.send_message(room_id, "✅ Match Session terminated."); cleanup_room(room_id)
            return True

    # --- 3. MATCH JOINER (!join) ---
    if cmd == "join":
        g = GAMES.get(room_id)
        if not g or g.status != "LOBBY": return False
        
        with g.lock:
            if uid == g.p1['id']: return True # Anti self-play
            
            # Atomic P2 Bet Deduction
            if not db.check_and_deduct_chips(uid, user, g.bet):
                bot.send_message(room_id, f"❌ Need {g.bet} chips to join!"); return True
            
            # Initialize PVP Match
            g.p2 = {'id': uid, 'name': user, 'av': current_av}
            g.status = "PLAYING"
            g.turn = g.p1['id'] # P1 always X
            g.last_act = time.time()
            
            url = bot.upload_to_server(draw_premium_board(g.board))
            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": url, "text": f"⚔️ MATCH START!\n@{g.p1['name']} (X) vs @{g.p2['name']} (O)"})
        return True

    # --- 4. NUMERIC INPUT HANDLER (Moves & Modes) ---
    if cmd.isdigit():
        g = GAMES.get(room_id)
        if not g: return False
        
        # High Concurrency Lock with Timeout (2s)
        if not g.lock.acquire(timeout=2): return False
        
        try:
            # A. TIMEOUT PROTECTION
            limit = 120 if g.status != "PLAYING" else 90
            if time.time() - g.last_act > limit:
                if g.status == "LOBBY" and g.bet > 0:
                    db.update_balance(g.p1['id'], g.p1['name'], chips_change=g.bet) # Auto Refund
                bot.send_message(room_id, "⏰ Game Cleaned up due to inactivity.")
                cleanup_room(room_id); return True

            # B. MODE SELECTION PHASE
            if g.status == "SELECT_MODE" and uid == g.p1['id']:
                if cmd == "1": # BOT MODE
                    g.mode = 1; g.p2 = {'id': 'BOT', 'name': 'Howdies AI', 'av': ''}; g.status = "PLAYING"
                    g.turn = uid; g.last_act = time.time()
                    url = bot.upload_to_server(draw_premium_board(g.board))
                    bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": url, "text": "🤖 BOT MATCH START!\nYour Move (X):"})
                    return True
                
                elif cmd == "2": # PVP MODE
                    try:
                        bet_amt = int(args[0]) if args else 0
                    except:
                        bet_amt = 0
                    
                    if bet_amt <= 0:
                        bot.send_message(room_id, "⚠️ Invalid bet. Use `2 100`."); return True
                    
                    # Atomic P1 Bet Deduction
                    if not db.check_and_deduct_chips(uid, user, bet_amt):
                        bot.send_message(room_id, "❌ Not enough chips!"); return True
                    
                    g.mode = 2; g.bet = bet_amt; g.status = "LOBBY"; g.last_act = time.time()
                    bot.send_message(room_id, f"⚔️ PVP LOBBY: {bet_amt} chips bet.\nWaiting for Player 2...\nType !join to accept.")
                    return True

            # C. GAMEPLAY PHASE
            if g.status == "PLAYING" and g.turn == uid:
                idx = int(cmd) - 1
                if idx < 0 or idx > 8 or g.board[idx] in ['X', 'O']:
                    return True # Silent ignore invalid moves
                
                # Execute Player Move
                g.board[idx] = 'X' if uid == g.p1['id'] else 'O'
                g.last_act = time.time()
                
                victory_res = check_victory_sanitized(g.board)
                if victory_res:
                    handle_match_termination(bot, g, victory_res)
                    return True
                
                if g.mode == 1: # Trigger Async Bot Move
                    g.turn = 'BOT' # Block player turn
                    threading.Timer(0.8, process_bot_async, [bot, g]).start()
                else: # Swap Turn PVP
                    g.turn = g.p2['id'] if uid == g.p1['id'] else g.p1['id']
                    url = bot.upload_to_server(draw_premium_board(g.board))
                    current_n = g.p1['name'] if g.turn == g.p1['id'] else g.p2['name']
                    bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": url, "text": f"Baari: @{current_n}"})
                
                return True

        except Exception:
            print("[TTT Critical Error]")
            traceback.print_exc()
        finally:
            g.lock.release()

    return False

# ======================================================
# 🏁 MATCH FINISH HANDLER: REWARDS & CLEANUP
# ======================================================

def handle_match_termination(bot, g, result):
    """Finalizing Match: Payouts, Visuals and Room Destruction"""
    
    if result == "DRAW":
        # Full Refund for PVP
        if g.bet > 0:
            db.update_balance(g.p1['id'], g.p1['name'], chips_change=g.bet)
            if g.mode == 2: db.update_balance(g.p2['id'], g.p2['name'], chips_change=g.bet)
        # Log zero result in stats
        db.add_game_result(g.p1['id'], g.p1['name'], "tictactoe", 0, is_win=False)
        bot.send_message(g.room_id, "🤝 **DRAW!** Bets have been refunded.")
    
    else:
        winner = g.p1 if result == 'X' else g.p2
        loser = g.p2 if result == 'X' else g.p1
        
        if winner['id'] == 'BOT':
            # Bot Victory: Reveal board and notify
            url = bot.upload_to_server(draw_premium_board(g.board))
            bot.send_json({"handler": "chatroommessage", "roomid": g.room_id, "type": "image", "url": url, "text": "🤖 **BOT WON!** Better luck next time."})
        else:
            # Player Victory: Calculate rewards
            chips_final = BOT_WIN_REWARD_CHIPS if g.mode == 1 else g.bet * 2
            score_final = BOT_WIN_REWARD_SCORE if g.mode == 1 else PVP_WIN_REWARD_SCORE
            
            # Atomic DB Sync (Net Profit logic)
            db.add_game_result(winner['id'], winner['name'], "tictactoe", chips_final - (g.bet if g.mode == 2 else 0), is_win=True, points_reward=score_final)
            if g.mode == 2:
                db.add_game_result(loser['id'], loser['name'], "tictactoe", -g.bet, is_win=False)

            # High Fidelity Winner Card
            img = draw_victory_card(winner['name'], chips_final, score_final, winner['id'], winner['av'])
            win_url = bot.upload_to_server(img)
            bot.send_json({"handler": "chatroommessage", "roomid": g.room_id, "type": "image", "url": win_url, "text": f"🏆 {winner['name']} Won!"})
            
    cleanup_room(g.room_id)
