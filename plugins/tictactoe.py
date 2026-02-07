import threading
import time
import random
import io
import requests
from PIL import Image, ImageDraw
import db
import utils

# ==========================================
# ⚙️ SETTINGS & ADMIN CONFIG
# ==========================================
BOT_REWARD_CHIPS = 100
BOT_REWARD_SCORE = 50
LOBBY_TIMEOUT = 120  # 2 Minutes
MOVE_TIMEOUT = 90    # 1.5 Minutes

# GLOBAL REGISTRY (Room Isolation)
GAMES = {}
GAMES_LOCK = threading.Lock()

def setup(bot):
    """Howdies Plugin Loader requires this to confirm loading."""
    print("[TicTacToe] Premium Game Engine Loaded.")

# ==========================================
# 🎨 GRAPHICS ENGINE (The User's Aesthetic)
# ==========================================
def get_avatar_image(url):
    try:
        if not url: raise Exception
        resp = requests.get(url, timeout=5)
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
        x = start_x + col * box_size; y = start_y + row * box_size
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
    d.rounded_rectangle([bx, by, bx+badge_w, by+badge_h], radius=25, fill=(0, 0, 0, 150), outline="#00FF7F", width=3)
    utils.write_text(d, (W//2, by + 25), f"WON {chips_won} CHIPS", size=30, align="center", col="#00FF7F")
    utils.write_text(d, (W//2, by + 65), f"+{score_won} SCORE", size=28, align="center", col="#00F2FE")
    return apply_round_corners(img, 50)

# ==========================================
# 📦 GAME ENGINE
# ==========================================
class TicTacToeBox:
    def __init__(self, room_id, p1_data):
        self.room_id = room_id
        self.lock = threading.Lock()
        self.status = "SELECT_MODE" 
        self.last_activity = time.time()
        self.p1 = p1_data
        self.p2 = None
        self.board = [str(i+1) for i in range(9)]
        self.mode = 0 # 1=Bot, 2=PVP
        self.bet = 0
        self.turn = None

def cleanup_game(room_id):
    with GAMES_LOCK:
        if room_id in GAMES: del GAMES[room_id]

def check_winner(board):
    wins = [(0,1,2), (3,4,5), (6,7,8), (0,3,6), (1,4,7), (2,5,8), (0,4,8), (2,4,6)]
    for a, b, c in wins:
        if board[a] == board[b] == board[c]: return board[a]
    if all(x in ['X', 'O'] for x in board): return 'DRAW'
    return None

def get_bot_move(board):
    wins = [(0,1,2), (3,4,5), (6,7,8), (0,3,6), (1,4,7), (2,5,8), (0,4,8), (2,4,6)]
    for a, b, c in wins:
        if board[a] == 'O' and board[b] == 'O' and board[c] not in ['X', 'O']: return c
        if board[a] == 'O' and board[c] == 'O' and board[b] not in ['X', 'O']: return b
        if board[b] == 'O' and board[c] == 'O' and board[a] not in ['X', 'O']: return a
    for a, b, c in wins:
        if board[a] == 'X' and board[b] == 'X' and board[c] not in ['X', 'O']: return c
        if board[a] == 'X' and board[c] == 'X' and board[b] not in ['X', 'O']: return b
        if board[b] == 'X' and board[c] == 'X' and board[a] not in ['X', 'O']: return a
    v = [i for i, x in enumerate(board) if x not in ['X', 'O']]
    return random.choice(v) if v else None

# ==========================================
# 📡 COMMAND HANDLER
# ==========================================
def handle_command(bot, cmd, room_id, user, args, data):
    user_id = str(data.get('userid'))
    
    # 1. ADMIN FORCE STOP
    if cmd == "!stop":
        if user_id in db.get_all_admins():
            if room_id in GAMES:
                cleanup_game(room_id)
                bot.send_message(room_id, "🛑 Admin forced game end.")
            return True
        return False

    # 2. START SESSION / CANCEL
    if cmd == "!tic":
        action = args[0] if args else ""
        if action == "1":
            if room_id in GAMES:
                bot.send_message(room_id, "⚠️ Session already active.")
                return True
            p1 = {'id': user_id, 'name': user, 'avatar': ""}
            with GAMES_LOCK: GAMES[room_id] = TicTacToeBox(room_id, p1)
            bot.send_message(room_id, "🎮 **TIC TAC TOE ON**\n\n1️⃣ Play vs BOT (Reward: 100c)\n2️⃣ PVP (Type: `2 <bet>`)\n\n(120s timer active)")
            return True
        elif action == "0":
            game = GAMES.get(room_id)
            if not game: return True
            with game.lock:
                if user_id == game.p1['id'] or user_id in db.get_all_admins():
                    if game.status == "LOBBY" and game.bet > 0:
                        db.update_balance(game.p1['id'], game.p1['name'], chips_change=game.bet)
                    bot.send_message(room_id, "✅ Game Closed.")
                    cleanup_game(room_id)
            return True

    # 3. JOIN PVP
    if cmd == "!join":
        game = GAMES.get(room_id)
        if not game or game.status != "LOBBY": return False
        with game.lock:
            if user_id == game.p1['id']: return True
            if not db.check_and_deduct_chips(user_id, user, game.bet):
                bot.send_message(room_id, "❌ No Chips!")
                return True
            game.p2 = {'id': user_id, 'name': user, 'avatar': ""}
            game.status = "PLAYING"; game.turn = game.p1['id']; game.last_activity = time.time()
            url = utils.upload(bot, draw_premium_board(game.board))
            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": url, "text": f"Match: @{game.p1['name']} vs @{game.p2['name']}"})
        return True

    # 4. MODE & MOVES (NUMBERS)
    if cmd.isdigit():
        game = GAMES.get(room_id)
        if not game: return False
        with game.lock:
            # Timeout Check
            limit = LOBBY_TIMEOUT if game.status != "PLAYING" else MOVE_TIMEOUT
            if time.time() - game.last_activity > limit:
                if game.status == "LOBBY" and game.bet > 0:
                    db.update_balance(game.p1['id'], game.p1['name'], chips_change=game.bet)
                bot.send_message(room_id, "⏰ Time Up! Cleaned.")
                cleanup_game(room_id); return True

            # Mode Select
            if game.status == "SELECT_MODE" and user_id == game.p1['id']:
                if cmd == "1":
                    game.mode = 1; game.p2 = {'id': 'BOT', 'name': 'AI'}; game.status = "PLAYING"
                    game.turn = game.p1['id']; game.last_activity = time.time()
                    url = utils.upload(bot, draw_premium_board(game.board))
                    bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": url, "text": "BOT GAME START (X)"})
                    return True
                elif cmd == "2":
                    try: bet = int(args[0]) if args else 0
                    except: bet = 0
                    if bet <= 0 or not db.check_and_deduct_chips(user_id, user, bet):
                        bot.send_message(room_id, "❌ Invalid bet or no chips!"); return True
                    game.mode = 2; game.bet = bet; game.status = "LOBBY"; game.last_activity = time.time()
                    bot.send_message(room_id, f"⚔️ PVP Lobby: {bet} chips. Type !join")
                    return True

            # Gameplay
            if game.status == "PLAYING" and game.turn == user_id:
                idx = int(cmd) - 1
                if idx < 0 or idx > 8 or game.board[idx] in ['X', 'O']: return True
                game.board[idx] = 'X' if user_id == game.p1['id'] else 'O'
                game.last_activity = time.time()
                res = check_winner(game.board)
                if res: finish_game(bot, game, res); return True
                
                if game.mode == 1:
                    bm = get_bot_move(game.board)
                    if bm is not None: game.board[bm] = 'O'
                    res = check_winner(game.board)
                    if res: finish_game(bot, game, res); return True
                else:
                    game.turn = game.p2['id'] if user_id == game.p1['id'] else game.p1['id']
                
                url = utils.upload(bot, draw_premium_board(game.board))
                bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": url, "text": "Next Move..."})
                return True
    return False

def finish_game(bot, game, res):
    if res == "DRAW":
        if game.bet > 0: db.update_balance(game.p1['id'], game.p1['name'], chips_change=game.bet)
        if game.mode == 2: db.update_balance(game.p2['id'], game.p2['name'], chips_change=game.bet)
        bot.send_message(game.room_id, "🤝 Draw! Refunded.")
    else:
        win = game.p1 if res == 'X' else game.p2
        if win['id'] == 'BOT':
            bot.send_message(game.room_id, "🤖 Bot Wins!")
        else:
            chips = BOT_REWARD_CHIPS if game.mode == 1 else game.bet * 2
            score = BOT_REWARD_SCORE if game.mode == 1 else 50
            db.add_game_result(win['id'], win['name'], "tictactoe", chips - (game.bet if game.mode == 2 else 0), is_win=True, points_reward=score)
            av = bot.get_user_avatar(win['id']) if hasattr(bot, 'get_user_avatar') else ""
            img = draw_victory_card(win['name'], chips, score, av)
            url = utils.upload(bot, img)
            bot.send_json({"handler": "chatroommessage", "roomid": game.room_id, "type": "image", "url": url, "text": "CHAMPION!"})
    cleanup_game(game.room_id)
