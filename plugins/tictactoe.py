import threading
import time
import random
import io
import requests
import uuid
from PIL import Image, ImageDraw, ImageOps, ImageFilter
import db
import utils

# ======================================================
# ⚙️ GLOBAL CONFIGURATION & REWARDS
# ======================================================
# Ye rewards Admin runtime pe badal sakta hai
SETTINGS = {
    "bot_win_chips": 100,    # Bot se jeetne par inaam
    "bot_win_score": 50,     # Bot se jeetne par permanent score
    "pvp_win_score": 50,     # PVP jeetne par points
    "lobby_timeout": 120,    # Lobby wait time (120 seconds)
    "move_timeout": 90       # Ek move ka time (90 seconds)
}

# ROOM ISOLATION REGISTRY
# Har room ka apna dabba (TicBox instance) yahan store hoga
GAMES = {}
GAMES_LOCK = threading.Lock()

def setup(bot):
    """Howdies Plugin Loader confirmation"""
    print("[TicTacToe-HD] CRASH-PROOF PREMIUM ENGINE LOADED.")

# ======================================================
# 🎨 PREMIUM GRAPHICS ENGINE (Neon & Gold Theme)
# ======================================================

def get_avatar_image(url):
    """Fetches user avatar and handles failure safely"""
    try:
        if not url: raise Exception("No URL")
        resp = requests.get(url, timeout=5)
        img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
        return img
    except:
        # Default placeholder agar internet ya URL kharab ho
        return Image.new('RGBA', (200, 200), (30, 30, 50))

def apply_round_corners(im, rad):
    """Utility to make any image have rounded corners"""
    circle = Image.new('L', (rad * 2, rad * 2), 0)
    draw = ImageDraw.Draw(circle)
    draw.ellipse((0, 0, rad * 2, rad * 2), fill=255)
    alpha = Image.new('L', im.size, 255)
    w, h = im.size
    alpha.paste(circle.crop((0, 0, rad, rad)), (0, 0))
    alpha.paste(circle.crop((0, rad, rad, rad * 2)), (0, h - rad))
    alpha.paste(circle.crop((rad, 0, rad * 2, rad)), (w - rad, 0))
    alpha.paste(circle.crop((rad, rad, rad * 2, rad * 2)), (w - rad, h - rad))
    im.putalpha(alpha)
    return im

def draw_premium_board(board):
    """Generates the 700x700 Neon Gameplay Board"""
    W, H = 700, 700
    # Futuristic Gradient Background
    base = utils.get_gradient(W, H, (10, 10, 25), (40, 20, 90))
    img = Image.new('RGBA', (W, H))
    img.paste(base, (0, 0))
    d = ImageDraw.Draw(img)

    # Multi-layered Neon Glow Borders
    for i in range(6):
        alpha = 150 - (i * 20)
        d.rounded_rectangle(
            [2+i, 2+i, W-2-i, H-2-i],
            radius=45,
            outline=f"#EC4899{alpha:02x}",
            width=2
        )

    utils.write_text(d, (W // 2, 65), "TIC TAC TOE", size=55, align="center", col="#00F2FE", shadow=True)

    # Grid Dimensions
    grid_size = 510
    box_size = grid_size // 3
    start_x = (W - grid_size) // 2
    start_y = 140

    for i in range(9):
        row, col = i // 3, i % 3
        x = start_x + col * box_size
        y = start_y + row * box_size

        # Cell Background
        d.rounded_rectangle([x+6, y+6, x+box_size-6, y+box_size-6], radius=22, fill=(20, 20, 45, 200))
        # Cell Border
        d.rounded_rectangle([x+8, y+8, x+box_size-8, y+box_size-8], radius=20, outline="#4facfe", width=3)

        symbol = board[i]
        cx, cy = x + box_size // 2, y + box_size // 2

        if symbol == 'X':
            s = 40
            d.line([(cx-s, cy-s), (cx+s, cy+s)], fill="#FF3131", width=14)
            d.line([(cx+s, cy-s), (cx-s, cy+s)], fill="#FF3131", width=14)
        elif symbol == 'O':
            s = 45
            d.ellipse([cx-s, cy-s, cx+s, cy+s], outline="#39FF14", width=14)
        else:
            # Ghost number for empty cells
            utils.write_text(d, (cx, cy), symbol, size=35, col=(255, 255, 255, 40), align="center")

    return apply_round_corners(img, 45)

def draw_victory_card(winner_name, chips_won, score_won, avatar_url):
    """Generates the 600x600 Champion Victory Card"""
    W, H = 600, 600
    base = utils.get_gradient(W, H, (30, 10, 60), (10, 80, 120))
    img = Image.new('RGBA', (W, H))
    img.paste(base, (0, 0))
    d = ImageDraw.Draw(img)

    # Golden border glow
    for i in range(8):
        alpha = 255 - (i * 30)
        d.rounded_rectangle([i, i, W-i, H-i], radius=50, outline=f"#FFD700{alpha:02x}", width=2)

    # Avatar with masking
    avatar_raw = get_avatar_image(avatar_url)
    avatar = avatar_raw.resize((260, 260), Image.Resampling.LANCZOS)
    mask = Image.new('L', (260, 260), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, 260, 260), fill=255)
    
    cx, cy = W // 2, 220
    # Golden ring glow
    for r in range(140, 155, 2):
        d.ellipse([cx-r, cy-r, cx+r, cy+r], outline="#00F2FE", width=2)
    d.ellipse([cx-135, cy-135, cx+135, cy+135], outline="#FFD700", width=10)
    img.paste(avatar, (cx-130, cy-130), mask)

    # Typography
    utils.write_text(d, (W//2, 390), "CHAMPION", size=35, align="center", col="#FFD700", shadow=True)
    utils.write_text(d, (W//2, 455), winner_name.upper(), size=55, align="center", col="white", shadow=True)

    # Rewards Badge
    badge_w, badge_h = 420, 100
    bx, by = W//2 - badge_w//2, 490
    d.rounded_rectangle([bx, by, bx+badge_w, by+badge_h], radius=25, fill=(0, 255, 127, 40), outline="#00FF7F", width=3)

    utils.write_text(d, (W//2, by + 25), f"WON {chips_won} CHIPS", size=32, align="center", col="#00FF7F")
    utils.write_text(d, (W//2, by + 68), f"+{score_won} SCORE REWARD", size=26, align="center", col="#00F2FE")

    return apply_round_corners(img, 50)

# ======================================================
# 📦 ENGINE CORE (State Management)
# ======================================================

class TicBox:
    """Isolated game instance per room"""
    def __init__(self, room_id, p1_id, p1_name):
        self.room_id = room_id
        self.lock = threading.Lock()
        self.status = "SELECT_MODE" # SELECT_MODE, LOBBY, PLAYING
        self.last_act = time.time()
        
        self.p1 = {'id': p1_id, 'name': p1_name}
        self.p2 = None
        self.board = [str(i+1) for i in range(9)]
        self.mode = 0 # 1=Bot, 2=PVP
        self.bet = 0
        self.turn = None

def cleanup_room(rid):
    """Safely destroys game box to free RAM"""
    with GAMES_LOCK:
        if rid in GAMES:
            del GAMES[rid]

def check_victory(brd):
    """Checks for win or draw"""
    wins = [(0,1,2), (3,4,5), (6,7,8), (0,3,6), (1,4,7), (2,5,8), (0,4,8), (2,4,6)]
    for a, b, c in wins:
        if brd[a] == brd[b] == brd[c]:
            return brd[a]
    if all(x in ['X', 'O'] for x in brd):
        return 'DRAW'
    return None

def get_ai_move(brd):
    """Strategic Bot Logic"""
    wins = [(0,1,2), (3,4,5), (6,7,8), (0,3,6), (1,4,7), (2,5,8), (0,4,8), (2,4,6)]
    # 1. Try to win
    for a, b, c in wins:
        if brd[a] == 'O' and brd[b] == 'O' and brd[c] not in ['X','O']: return c
        if brd[a] == 'O' and brd[c] == 'O' and brd[b] not in ['X','O']: return b
        if brd[b] == 'O' and brd[c] == 'O' and brd[a] not in ['X','O']: return a
    # 2. Block user
    for a, b, c in wins:
        if brd[a] == 'X' and brd[b] == 'X' and brd[c] not in ['X','O']: return c
        if brd[a] == 'X' and brd[c] == 'X' and brd[b] not in ['X','O']: return b
        if brd[b] == 'X' and brd[c] == 'X' and brd[a] not in ['X','O']: return a
    # 3. Random valid move
    valid = [i for i, x in enumerate(brd) if x not in ['X','O']]
    return random.choice(valid) if valid else None

# ======================================================
# 📡 HANDLER & COMMANDS
# ======================================================

def handle_command(bot, cmd, room_id, user, args, data):
    # Normalized User ID from Universal Extractor
    uid = str(data.get('userid'))

    # --- ADMIN CONFIGS ---
    if cmd == "tchips" and uid in db.get_all_admins():
        try:
            val = int(args[0])
            SETTINGS["bot_win_chips"] = val
            bot.send_message(room_id, f"✅ Bot win chips reward set to {val}")
        except: pass
        return True

    if cmd == "tscore" and uid in db.get_all_admins():
        try:
            val = int(args[0])
            SETTINGS["bot_win_score"] = val
            bot.send_message(room_id, f"✅ Bot win score reward set to {val}")
        except: pass
        return True

    # --- !stop (Admin Emergency Force Close) ---
    if cmd == "stop":
        if uid in db.get_all_admins():
            if room_id in GAMES:
                cleanup_room(room_id)
                bot.send_message(room_id, "🛑 Admin forced game termination.")
            return True

    # --- !tic (Session Control) ---
    if cmd == "tic":
        sub = args[0] if args else ""
        
        # !tic 1 -> START SESSION
        if sub == "1":
            if room_id in GAMES:
                bot.send_message(room_id, "⚠️ A game session is already active in this room.")
                return True
            with GAMES_LOCK:
                GAMES[room_id] = TicBox(room_id, uid, user)
            bot.send_message(room_id, "🎮 **TIC TAC TOE SESSION STARTED**\n\nChoose Mode:\n1️⃣ Play with BOT\n2️⃣ PVP (Example: `2 500` for 500 chips bet)\n\n(120s lobby timer active)")
            return True

        # !tic 0 -> CANCEL / OFF
        elif sub == "0":
            g = GAMES.get(room_id)
            if not g: return True
            with g.lock:
                if uid == g.p1['id'] or uid in db.get_all_admins():
                    # Refund logic if PVP lobby was open
                    if g.status == "LOBBY" and g.bet > 0:
                        db.update_balance(g.p1['id'], g.p1['name'], chips_change=g.bet)
                    bot.send_message(room_id, "✅ Tic Tac Toe Session Closed.")
                    cleanup_room(room_id)
            return True

    # --- !join (PVP Entry) ---
    if cmd == "join":
        g = GAMES.get(room_id)
        if not g or g.status != "LOBBY": return False
        with g.lock:
            if uid == g.p1['id']: return True # Prevent self-play
            
            # Strict economy check
            if not db.check_and_deduct_chips(uid, user, g.bet):
                bot.send_message(room_id, f"❌ @{user} You need {g.bet} chips to join.")
                return True
            
            # Initialize match
            g.p2 = {'id': uid, 'name': user}
            g.status = "PLAYING"
            g.turn = g.p1['id']
            g.last_act = time.time()
            
            url = bot.upload_to_server(draw_premium_board(g.board))
            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": url, "text": f"Match Started!\n@{g.p1['name']} vs @{g.p2['name']}\nTurn: @{g.p1['name']}"})
        return True

    # --- Number Input (Mode Select or Game Move) ---
    if cmd.isdigit():
        g = GAMES.get(room_id)
        if not g: return False
        
        with g.lock:
            # 1. Inactivity Timeout Control
            limit = SETTINGS["lobby_timeout"] if g.status != "PLAYING" else SETTINGS["move_timeout"]
            if time.time() - g.last_act > limit:
                if g.status == "LOBBY" and g.bet > 0:
                    db.update_balance(g.p1['id'], g.p1['name'], chips_change=g.bet)
                bot.send_message(room_id, "⏰ Game Box terminated due to inactivity.")
                cleanup_room(room_id); return True

            # 2. Phase: Selecting Mode (Only Creator P1)
            if g.status == "SELECT_MODE" and uid == g.p1['id']:
                if cmd == "1":
                    g.mode = 1; g.p2 = {'id': 'BOT', 'name': 'Howdies AI'}; g.status = "PLAYING"
                    g.turn = g.p1['id']; g.last_act = time.time()
                    url = bot.upload_to_server(draw_premium_board(g.board))
                    bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": url, "text": "🤖 BOT GAME STARTED!\nYour Turn (X):"})
                    return True
                
                elif cmd == "2":
                    try: bet = int(args[0]) if args else 0
                    except: bet = 0
                    if bet <= 0 or not db.check_and_deduct_chips(uid, user, bet):
                        bot.send_message(room_id, "❌ Valid chips bet required to create PVP lobby!"); return True
                    g.mode = 2; g.bet = bet; g.status = "LOBBY"; g.last_act = time.time()
                    bot.send_message(room_id, f"⚔️ PVP LOBBY: {bet} chips. Waiting for Player 2...\nType !join to accept.")
                    return True

            # 3. Phase: Gameplay Moves
            if g.status == "PLAYING" and g.turn == uid:
                idx = int(cmd) - 1
                if idx < 0 or idx > 8 or g.board[idx] in ['X', 'O']:
                    return True # Ignore invalid moves
                
                # Execute Player Move
                g.board[idx] = 'X' if uid == g.p1['id'] else 'O'
                g.last_act = time.time()
                
                res = check_victory(g.board)
                if res:
                    process_finish(bot, g, res)
                    return True
                
                # Turn Logic
                if g.mode == 1:
                    # Bot moves instantly
                    b_idx = get_ai_move(g.board)
                    if b_idx is not None:
                        g.board[b_idx] = 'O'
                        res = check_victory(g.board)
                        if res:
                            process_finish(bot, g, res)
                            return True
                else:
                    # Swap Turn in PVP
                    g.turn = g.p2['id'] if uid == g.p1['id'] else g.p1['id']
                
                # Update Chat Board
                url = bot.upload_to_server(draw_premium_board(g.board))
                next_player = g.p1['name'] if g.turn == g.p1['id'] else g.p2['name']
                bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": url, "text": f"Next Move: @{next_player}"})
                return True

    return False

def process_finish(bot, g, res):
    """Handles payouts, graphics and data storage after match ends"""
    if res == "DRAW":
        # Refund chips if PVP
        if g.bet > 0:
            db.update_balance(g.p1['id'], g.p1['name'], chips_change=g.bet)
            if g.mode == 2:
                db.update_balance(g.p2['id'], g.p2['name'], chips_change=g.bet)
        bot.send_message(g.room_id, "🤝 **DRAW!** All bets have been refunded.")
    
    else:
        winner = g.p1 if res == 'X' else g.p2
        loser = g.p2 if res == 'X' else g.p1
        
        # Bot Wins
        if winner['id'] == 'BOT':
            url = bot.upload_to_server(draw_premium_board(g.board))
            bot.send_json({"handler": "chatroommessage", "roomid": g.room_id, "type": "image", "url": url, "text": "🤖 **Bot Victory!** Try again next time."})
        
        # Player Wins
        else:
            if g.mode == 1:
                chips_won = SETTINGS["bot_win_chips"]
                score_won = SETTINGS["bot_win_score"]
                db.add_game_result(winner['id'], winner['name'], "tictactoe", chips_won, is_win=True, points_reward=score_won)
            else:
                chips_won = g.bet * 2
                score_won = SETTINGS["pvp_win_score"]
                # Pay Winner (Net profit is g.bet)
                db.add_game_result(winner['id'], winner['name'], "tictactoe", chips_won - g.bet, is_win=True, points_reward=score_won)
                # Log Loser
                db.add_game_result(loser['id'], loser['name'], "tictactoe", -g.bet, is_win=False)

            # Champion Graphics
            av_url = bot.get_user_avatar(winner['id']) if hasattr(bot, 'get_user_avatar') else ""
            img = draw_victory_card(winner['name'], chips_won, score_won, av_url)
            win_url = bot.upload_to_server(img)
            bot.send_json({"handler": "chatroommessage", "roomid": g.room_id, "type": "image", "url": win_url, "text": f"🏆 {winner['name']} is the winner!"})
            
    cleanup_room(g.room_id)
