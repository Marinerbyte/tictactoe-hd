import threading
import time
import random
import io
import requests
from PIL import Image, ImageDraw
import db
import utils

# ==========================================
# ⚙️ SETTINGS
# ==========================================
BOT_REWARD_CHIPS = 100
BOT_REWARD_SCORE = 50
TIMEOUT_SECONDS = 120  # 2 Minutes cleanup timer

# GLOBAL REGISTRY
GAMES = {}
GAMES_LOCK = threading.Lock()

# ==========================================
# 🎨 GRAPHICS (PREMIUM NEON)
# ==========================================
def get_avatar_image(url):
    try:
        if not url: raise Exception
        resp = requests.get(url, timeout=3)
        img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
        return img
    except:
        return Image.new('RGBA', (200, 200), (50, 50, 50))

def apply_round_corners(im, rad):
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
    W, H = 700, 700
    base = utils.get_gradient(W, H, (10, 10, 25), (40, 20, 90))
    img = Image.new('RGBA', (W, H))
    img.paste(base, (0, 0))
    d = ImageDraw.Draw(img)

    for i in range(6):
        alpha = 150 - (i * 20)
        d.rounded_rectangle([2+i, 2+i, W-2-i, H-2-i], radius=45, outline=f"#EC4899{alpha:02x}", width=2)

    utils.write_text(d, (W // 2, 65), "TIC TAC TOE", size=55, align="center", col="#00F2FE", shadow=True)

    grid_size = 510; box_size = grid_size // 3
    start_x = (W - grid_size) // 2; start_y = 140

    for i in range(9):
        row = i // 3; col = i % 3
        x = start_x + col * box_size
        y = start_y + row * box_size

        d.rounded_rectangle([x+6, y+6, x+box_size-6, y+box_size-6], radius=22, fill=(20, 20, 45, 200))
        d.rounded_rectangle([x+8, y+8, x+box_size-8, y+box_size-8], radius=20, outline="#4facfe", width=3)

        symbol = board[i]
        cx = x + box_size // 2; cy = y + box_size // 2

        if symbol == 'X':
            s = 40
            d.line([(cx-s, cy-s), (cx+s, cy+s)], fill="#FF3131", width=14)
            d.line([(cx+s, cy-s), (cx-s, cy+s)], fill="#FF3131", width=14)
        elif symbol == 'O':
            s = 45
            d.ellipse([cx-s, cy-s, cx+s, cy+s], outline="#39FF14", width=14)
        else:
            utils.write_text(d, (cx, cy), symbol, size=35, col=(255, 255, 255, 40), align="center")

    return apply_round_corners(img, 45)

def draw_victory_card(winner_name, chips_won, score_won, avatar_url):
    W, H = 600, 600
    base = utils.get_gradient(W, H, (30, 10, 60), (10, 80, 120))
    img = Image.new('RGBA', (W, H))
    img.paste(base, (0, 0))
    d = ImageDraw.Draw(img)

    for i in range(8):
        alpha = 255 - (i * 30)
        d.rounded_rectangle([i, i, W-i, H-i], radius=50, outline=f"#FFD700{alpha:02x}", width=2)

    avatar = get_avatar_image(avatar_url).resize((260, 260), Image.Resampling.LANCZOS)
    mask = Image.new('L', (260, 260), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, 260, 260), fill=255)

    cx, cy = W // 2, 220
    for r in range(140, 155, 2): d.ellipse([cx-r, cy-r, cx+r, cy+r], outline="#00F2FE", width=2)
    d.ellipse([cx-135, cy-135, cx+135, cy+135], outline="#FFD700", width=10)
    img.paste(avatar, (cx-130, cy-130), mask)

    utils.write_text(d, (W//2, 390), "CHAMPION", size=35, align="center", col="#FFD700", shadow=True)
    utils.write_text(d, (W//2, 450), winner_name.upper(), size=50, align="center", col="white", shadow=True)

    badge_w, badge_h = 400, 90
    bx, by = W//2 - badge_w//2, 490
    d.rounded_rectangle([bx, by, bx+badge_w, by+badge_h], radius=25, fill=(0, 0, 0, 100), outline="#00FF7F", width=3)
    utils.write_text(d, (W//2, by + 25), f"WON {chips_won} CHIPS", size=30, align="center", col="#00FF7F")
    utils.write_text(d, (W//2, by + 65), f"+{score_won} SCORE", size=28, align="center", col="#00F2FE")

    return apply_round_corners(img, 50)

# ==========================================
# 📦 GAME ENGINE (ISOLATED BOX)
# ==========================================
class TicTacToeBox:
    def __init__(self, room_id, p1_data):
        self.room_id = room_id
        self.lock = threading.Lock()
        
        # State: SELECT_MODE -> LOBBY -> PLAYING
        self.status = "SELECT_MODE" 
        self.last_activity = time.time()
        
        # Players
        self.p1 = p1_data # Creator
        self.p2 = None
        
        # Game Data
        self.board = [str(i+1) for i in range(9)]
        self.mode = 0   # 1=Bot, 2=PVP
        self.bet = 0
        self.turn = None

    def check_expiry(self):
        # 120 Seconds Timeout rule (Strict)
        if time.time() - self.last_activity > TIMEOUT_SECONDS:
            return True
        return False

# ==========================================
# 🧹 CLEANUP & MEMORY
# ==========================================
def cleanup_game(room_id):
    with GAMES_LOCK:
        if room_id in GAMES:
            del GAMES[room_id]

def get_game(room_id):
    with GAMES_LOCK:
        return GAMES.get(room_id)

# ==========================================
# 🎮 LOGIC & BOT
# ==========================================
def check_winner(board):
    wins = [(0,1,2), (3,4,5), (6,7,8), (0,3,6), (1,4,7), (2,5,8), (0,4,8), (2,4,6)]
    for a, b, c in wins:
        if board[a] == board[b] == board[c]: return board[a]
    if all(x in ['X', 'O'] for x in board): return 'DRAW'
    return None

def get_bot_move(board):
    # 1. Win
    wins = [(0,1,2), (3,4,5), (6,7,8), (0,3,6), (1,4,7), (2,5,8), (0,4,8), (2,4,6)]
    for a, b, c in wins:
        if board[a] == 'O' and board[b] == 'O' and board[c] not in ['X', 'O']: return c
        if board[a] == 'O' and board[c] == 'O' and board[b] not in ['X', 'O']: return b
        if board[b] == 'O' and board[c] == 'O' and board[a] not in ['X', 'O']: return a
    # 2. Block
    for a, b, c in wins:
        if board[a] == 'X' and board[b] == 'X' and board[c] not in ['X', 'O']: return c
        if board[a] == 'X' and board[c] == 'X' and board[b] not in ['X', 'O']: return b
        if board[b] == 'X' and board[c] == 'X' and board[a] not in ['X', 'O']: return a
    # 3. Random
    valid = [i for i, x in enumerate(board) if x not in ['X', 'O']]
    return random.choice(valid) if valid else None

# ==========================================
# 📡 COMMAND HANDLER
# ==========================================
def handle_command(bot, cmd, room_id, user, args, data):
    user_id = data.get('userid')
    
    # 1. ADMIN FORCE STOP (!stop)
    if cmd == "!stop":
        if user_id in db.get_all_admins():
            if get_game(room_id):
                cleanup_game(room_id)
                bot.send_message(room_id, "🛑 Admin forcefully stopped the game.")
            return True
        return False

    # 2. PLAYER CANCEL (!tic 0)
    if cmd == "!tic" and args and args[0] == "0":
        game = get_game(room_id)
        if not game: return True # Nothing to stop
        
        with game.lock:
            # Check ownership (Only P1 or P2 can cancel lobby, or Admin)
            if user_id != game.p1['id'] and (not game.p2 or user_id != game.p2['id']):
                bot.send_message(room_id, "⚠️ Only the player who started can cancel.")
                return True
                
            # Refund if PVP Lobby
            if game.status == "LOBBY" and game.bet > 0:
                db.update_balance(game.p1['id'], game.p1['name'], chips_change=game.bet)
                bot.send_message(room_id, f"✅ Game Cancelled. {game.bet} Chips refunded.")
            else:
                bot.send_message(room_id, "✅ Game Cancelled.")
                
            cleanup_game(room_id)
        return True

    # 3. START SESSION (!tic 1)
    if cmd == "!tic" and args and args[0] == "1":
        if get_game(room_id):
            bot.send_message(room_id, "⚠️ A game session is already active.")
            return True
            
        # Create Session
        p1 = {'id': user_id, 'name': user, 'avatar': bot.get_user_avatar(user_id) if hasattr(bot, 'get_user_avatar') else ""}
        with GAMES_LOCK:
            GAMES[room_id] = TicTacToeBox(room_id, p1)
            
        bot.send_message(room_id, f"🎮 **Tic Tac Toe Session ON**\n\nChoose Mode:\nType **1** ▶️ Play vs BOT (Win: 100 Chips + 50 Score)\nType **2 <bet>** ▶️ PVP (Example: `2 500`)\n\n(Session closes in 120s)")
        return True

    # 4. JOIN PVP (!join)
    if cmd == "!join":
        game = get_game(room_id)
        if not game: return False
        
        with game.lock:
            if game.status != "LOBBY": 
                bot.send_message(room_id, "No lobby available to join.")
                return True
                
            if game.p1['id'] == user_id: return True # Self join block
            
            # Check Balance
            if not db.check_and_deduct_chips(user_id, user, game.bet):
                bot.send_message(room_id, f"❌ Insufficient Chips! Need {game.bet}.")
                return True
                
            # Start PVP
            game.p2 = {'id': user_id, 'name': user, 'avatar': bot.get_user_avatar(user_id) if hasattr(bot, 'get_user_avatar') else ""}
            game.status = "PLAYING"
            game.turn = game.p1['id'] # P1 starts
            game.last_activity = time.time()
            
            img_url = utils.upload(bot, draw_premium_board(game.board))
            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": img_url, "text": f"⚔️ MATCH STARTED!\n@{game.p1['name']} (X) vs @{game.p2['name']} (O)\nTurn: @{game.p1['name']}"})
        return True

    # 5. HANDLING INPUTS (Mode Selection OR Moves)
    # Checks if message is strictly numeric or "2 <amount>"
    is_num = cmd.isdigit()
    is_pvp_setup = (cmd == "2" and args and args[0].isdigit())
    
    if is_num or is_pvp_setup:
        game = get_game(room_id)
        if not game: return False
        
        with game.lock:
            # A. TIMEOUT CHECK
            if game.check_expiry():
                if game.status == "LOBBY" and game.bet > 0:
                    db.update_balance(game.p1['id'], game.p1['name'], chips_change=game.bet) # Refund
                cleanup_game(room_id)
                bot.send_message(room_id, "⏰ Session Expired (120s Timeout).")
                return True

            # B. MODE SELECTION PHASE
            if game.status == "SELECT_MODE":
                if user_id != game.p1['id']: return True # Only creator selects
                
                # --- BOT MODE ---
                if cmd == "1":
                    game.mode = 1
                    game.p2 = {'id': 'BOT', 'name': 'AI Bot', 'avatar': ''}
                    game.status = "PLAYING"
                    game.turn = game.p1['id']
                    game.last_activity = time.time()
                    
                    img_url = utils.upload(bot, draw_premium_board(game.board))
                    bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": img_url, "text": f"🤖 BOT MATCH STARTED!\nWin Reward: {BOT_REWARD_CHIPS} Chips + {BOT_REWARD_SCORE} Score\nYour Turn (X): Type 1-9"})
                    return True

                # --- PVP MODE ---
                elif cmd == "2" or (cmd == "2" and args):
                    try:
                        bet_amount = int(args[0]) if args else 0
                    except: bet_amount = 0
                    
                    if bet_amount <= 0:
                        bot.send_message(room_id, "⚠️ Invalid Bet. Usage: `2 100`")
                        return True
                        
                    # Check Creator Balance
                    if not db.check_and_deduct_chips(user_id, user, bet_amount):
                        bot.send_message(room_id, f"❌ You don't have {bet_amount} chips.")
                        return True
                        
                    game.mode = 2
                    game.bet = bet_amount
                    game.status = "LOBBY"
                    game.last_activity = time.time()
                    bot.send_message(room_id, f"⚔️ **PVP LOBBY CREATED**\nBet: {bet_amount} Chips\nWaiting for Player 2...\nType **!join** to accept.\n(Timeout: 120s)")
                    return True
            
            # C. GAMEPLAY PHASE (Moves 1-9)
            elif game.status == "PLAYING":
                if not is_num: return True
                move_idx = int(cmd) - 1
                if move_idx < 0 or move_idx > 8: return True
                
                if game.turn != user_id: return True # Not turn
                if game.board[move_idx] in ['X', 'O']: 
                    bot.send_message(room_id, "⚠️ Box occupied.")
                    return True
                
                # EXECUTE MOVE
                game.last_activity = time.time()
                symbol = 'X' if user_id == game.p1['id'] else 'O'
                game.board[move_idx] = symbol
                
                # Check Win
                res = check_winner(game.board)
                if res:
                    finish_game(bot, game, res)
                    return True
                
                # Next Turn Logic
                if game.mode == 2:
                    game.turn = game.p2['id'] if user_id == game.p1['id'] else game.p1['id']
                    next_name = game.p1['name'] if game.turn == game.p1['id'] else game.p2['name']
                    img_url = utils.upload(bot, draw_premium_board(game.board))
                    bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": img_url, "text": f"Turn: @{next_name}"})
                
                elif game.mode == 1:
                    # Bot Turn
                    bot_move = get_bot_move(game.board)
                    if bot_move is not None:
                        game.board[bot_move] = 'O'
                        res = check_winner(game.board)
                        if res:
                            finish_game(bot, game, res)
                            return True
                    img_url = utils.upload(bot, draw_premium_board(game.board))
                    bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": img_url, "text": "Your Turn (X)"})
                
                return True

    return False

def finish_game(bot, game, result):
    # 1. DRAW
    if result == "DRAW":
        if game.bet > 0: # Refund PVP
            db.update_balance(game.p1['id'], game.p1['name'], chips_change=game.bet)
            if game.mode == 2:
                db.update_balance(game.p2['id'], game.p2['name'], chips_change=game.bet)
        
        img_url = utils.upload(bot, draw_premium_board(game.board))
        bot.send_json({"handler": "chatroommessage", "roomid": game.room_id, "type": "image", "url": img_url, "text": "🤝 DRAW! Refunded."})
        cleanup_game(game.room_id)
        return

    # 2. WINNER DECIDED
    winner = game.p1 if result == 'X' else game.p2
    
    # Bot Wins
    if winner['id'] == 'BOT':
        img_url = utils.upload(bot, draw_premium_board(game.board))
        bot.send_json({"handler": "chatroommessage", "roomid": game.room_id, "type": "image", "url": img_url, "text": "🤖 Bot Won! Try again."})
        cleanup_game(game.room_id)
        return

    # Player Wins
    chips_won = 0
    score_won = 0
    
    if game.mode == 1: # Bot Mode Reward
        chips_won = BOT_REWARD_CHIPS
        score_won = BOT_REWARD_SCORE
        db.add_game_result(winner['id'], winner['name'], "tictactoe_bot", chips_won, is_win=True, points_reward=score_won)
    else: # PVP Reward
        total_pot = game.bet * 2
        chips_won = total_pot - game.bet
        score_won = 50 # Standard PVP score
        db.add_game_result(winner['id'], winner['name'], "tictactoe_pvp", chips_won, is_win=True, points_reward=score_won)
        # Log Loser
        loser = game.p2 if result == 'X' else game.p1
        db.add_game_result(loser['id'], loser['name'], "tictactoe_pvp", -game.bet, is_win=False)

    # Send Winner Card
    win_img = draw_victory_card(winner['name'], chips_won + (game.bet if game.mode == 2 else 0), score_won, winner['avatar'])
    win_url = utils.upload(bot, win_img)
    bot.send_json({"handler": "chatroommessage", "roomid": game.room_id, "type": "image", "url": win_url, "text": f"🏆 {winner['name']} Wins!"})
    
    cleanup_game(game.room_id)
