import threading
import time
import random
import io
import requests
from PIL import Image, ImageDraw, ImageOps
import db
import utils

# ==========================================
# ⚙️ SETTINGS & REWARDS
# ==========================================
BOT_WIN_REWARD_CHIPS = 100
BOT_WIN_REWARD_SCORE = 50
PVP_WIN_REWARD_SCORE = 50
LOBBY_TIMEOUT = 120 
MOVE_TIMEOUT = 90

# Global Registry for Room Isolation
GAMES = {}
GAMES_LOCK = threading.Lock()

def setup(bot):
    """Howdies Plugin Loader confirmation"""
    print("[TicTacToe-HD] ULTIMATE PREMIUM ENGINE LOADED.")

# ==========================================
# 🎨 GRAPHICS ENGINE (The Premium Boards)
# ==========================================

def get_avatar_image(user_id):
    """Fetches user avatar from Howdies API using UserID"""
    try:
        # Howdies Avatar API Endpoint
        url = f"https://api.howdies.app/api/avatar/{user_id}"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            return Image.open(io.BytesIO(resp.content)).convert("RGBA")
        raise Exception("API Error")
    except:
        # Placeholder if avatar fails
        return Image.new('RGBA', (200, 200), (30, 30, 50))

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

    # Neon Border
    for i in range(6):
        alpha = 150 - (i * 20)
        d.rounded_rectangle([2+i, 2+i, W-2-i, H-2-i], radius=45, outline=f"#EC4899{alpha:02x}", width=2)

    utils.write_text(d, (W // 2, 65), "TIC TAC TOE", size=55, align="center", col="#00F2FE", shadow=True)

    grid_size = 510; box_size = grid_size // 3
    sx, sy = (W - grid_size) // 2, 140

    for i in range(9):
        r, c = i // 3, i % 3
        x, y = sx + c * box_size, sy + r * box_size
        d.rounded_rectangle([x+6, y+6, x+box_size-6, y+box_size-6], radius=22, fill=(20, 20, 45, 200))
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
            utils.write_text(d, (cx, cy), symbol, size=35, col=(255, 255, 255, 40), align="center")

    return apply_round_corners(img, 45)

def draw_victory_card(winner_name, chips_won, score_won, winner_id):
    W, H = 600, 600
    base = utils.get_gradient(W, H, (30, 10, 60), (10, 80, 120))
    img = Image.new('RGBA', (W, H))
    img.paste(base, (0, 0))
    d = ImageDraw.Draw(img)

    for i in range(8):
        alpha = 255 - (i * 30)
        d.rounded_rectangle([i, i, W-i, H-i], radius=50, outline=f"#FFD700{alpha:02x}", width=2)

    # Avatar Handling
    av_raw = get_avatar_image(winner_id)
    av = av_raw.resize((260, 260), Image.Resampling.LANCZOS)
    mask = Image.new('L', (260, 260), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, 260, 260), fill=255)
    
    cx, cy = W // 2, 220
    for r in range(140, 155, 2): d.ellipse([cx-r, cy-r, cx+r, cy+r], outline="#00F2FE", width=2)
    d.ellipse([cx-135, cy-135, cx+135, cy+135], outline="#FFD700", width=10)
    img.paste(av, (cx-130, cy-130), mask)

    utils.write_text(d, (W//2, 390), "CHAMPION", size=35, align="center", col="#FFD700", shadow=True)
    utils.write_text(d, (W//2, 450), winner_name.upper(), size=50, align="center", col="white", shadow=True)

    # RED COLOR CHIPS BADGE
    badge_w, badge_h = 420, 105
    bx, by = W//2 - badge_w//2, 485
    d.rounded_rectangle([bx, by, bx+badge_w, by+badge_h], radius=25, fill=(255, 0, 0, 40), outline="#FF3131", width=3)

    utils.write_text(d, (W//2, by + 30), f"WON {chips_won} CHIPS", size=32, align="center", col="#FF3131")
    utils.write_text(d, (W//2, by + 72), f"+{score_won} SCORE REWARD", size=26, align="center", col="#00F2FE")

    return apply_round_corners(img, 50)

# ==========================================
# 📦 ENGINE CORE (Dabba System)
# ==========================================
class TicTacToeBox:
    def __init__(self, room_id, p1_data):
        self.room_id = room_id
        self.lock = threading.Lock()
        self.status = "SELECT_MODE" # SELECT_MODE, LOBBY, PLAYING
        self.last_act = time.time()
        self.p1 = p1_data # {id, name}
        self.p2 = None
        self.board = [str(i+1) for i in range(9)]
        self.mode = 0 # 1=Bot, 2=PVP
        self.bet = 0
        self.turn = None

def cleanup_room(rid):
    with GAMES_LOCK:
        if rid in GAMES: del GAMES[rid]

def check_win(board_list):
    wins = [(0,1,2), (3,4,5), (6,7,8), (0,3,6), (1,4,7), (2,5,8), (0,4,8), (2,4,6)]
    for a, b, c in wins:
        if board_list[a] == board_list[b] == board_list[c]:
            return board_list[a]
    if all(x in ['X', 'O'] for x in board_list):
        return 'DRAW'
    return None

def bot_brain(board_list):
    wins = [(0,1,2), (3,4,5), (6,7,8), (0,3,6), (1,4,7), (2,5,8), (0,4,8), (2,4,6)]
    # 1. Win
    for a, b, c in wins:
        if board_list[a] == 'O' and board_list[b] == 'O' and board_list[c] not in ['X','O']: return c
        if board_list[a] == 'O' and board_list[c] == 'O' and board_list[b] not in ['X','O']: return b
        if board_list[b] == 'O' and board_list[c] == 'O' and board_list[a] not in ['X','O']: return a
    # 2. Block
    for a, b, c in wins:
        if board_list[a] == 'X' and board_list[b] == 'X' and board_list[c] not in ['X','O']: return c
        if board_list[a] == 'X' and board_list[c] == 'X' and board_list[b] not in ['X','O']: return b
        if board_list[b] == 'X' and board_list[c] == 'X' and board_list[a] not in ['X','O']: return a
    # 3. Random
    valid = [i for i, x in enumerate(board_list) if x not in ['X','O']]
    return random.choice(valid) if valid else None

# ==========================================
# 📡 HANDLER & COMMANDS
# ==========================================
def handle_command(bot, cmd, room_id, user, args, data):
    # Normalized ID from bot_engine
    uid = str(data.get('userid'))

    # !stop (Admin only)
    if cmd == "stop" and uid in db.get_all_admins():
        if room_id in GAMES:
            cleanup_room(room_id)
            bot.send_message(room_id, "🛑 Admin forced game shutdown.")
        return True

    # !tic controller
    if cmd == "tic":
        act = args[0] if args else ""
        if act == "1":
            if room_id in GAMES:
                bot.send_message(room_id, "⚠️ Room is busy.")
                return True
            with GAMES_LOCK:
                GAMES[room_id] = TicTacToeBox(room_id, {'id': uid, 'name': user})
            bot.send_message(room_id, "🎮 **TIC TAC TOE**\n\nChoose Mode:\nType **1** ▶️ Play with Bot\nType **2 <bet>** ▶️ PVP Betting\n\n(120s Lobby Timer Active)")
            return True
        elif act == "0":
            g = GAMES.get(room_id)
            if not g: return True
            with g.lock:
                if uid == g.p1['id'] or uid in db.get_all_admins():
                    if g.status == "LOBBY" and g.bet > 0:
                        db.update_balance(g.p1['id'], g.p1['name'], chips_change=g.bet)
                    bot.send_message(room_id, "✅ Session Closed.")
                    cleanup_room(room_id)
            return True

    # !join
    if cmd == "join":
        g = GAMES.get(room_id)
        if not g or g.status != "LOBBY": return False
        with g.lock:
            if uid == g.p1['id']: return True
            # Deduct P2 bet instantly
            if not db.check_and_deduct_chips(uid, user, g.bet):
                bot.send_message(room_id, f"❌ Need {g.bet} chips to join!")
                return True
            g.p2 = {'id': uid, 'name': user}
            g.status = "PLAYING"; g.turn = g.p1['id']; g.last_act = time.time()
            img = draw_premium_board(g.board)
            url = bot.upload_to_server(img)
            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": url, "text": f"Match Started!\n@{g.p1['name']} vs @{g.p2['name']}"})
        return True

    # Movement and Mode Setup (Numbers)
    if cmd.isdigit():
        g = GAMES.get(room_id)
        if not g: return False
        with g.lock:
            # Check Timeout
            limit = LOBBY_TIMEOUT if g.status != "PLAYING" else MOVE_TIMEOUT
            if time.time() - g.last_act > limit:
                if g.status == "LOBBY" and g.bet > 0:
                    db.update_balance(g.p1['id'], g.p1['name'], chips_change=g.bet)
                bot.send_message(room_id, "⏰ Session Expired. Memory cleaned.")
                cleanup_room(room_id); return True

            # Step 1: Select Mode
            if g.status == "SELECT_MODE" and uid == g.p1['id']:
                if cmd == "1": # VS BOT
                    g.mode = 1; g.p2 = {'id': 'BOT', 'name': 'AI'}; g.status = "PLAYING"
                    g.turn = g.p1['id']; g.last_act = time.time()
                    url = bot.upload_to_server(draw_premium_board(g.board))
                    bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": url, "text": "🤖 BOT GAME START (X):"})
                    return True
                elif cmd == "2": # PVP
                    try: bet = int(args[0]) if args else 0
                    except: bet = 0
                    if bet <= 0:
                        bot.send_message(room_id, "⚠️ Usage: `2 100` (min bet 1)"); return True
                    # Deduct P1 bet instantly
                    if not db.check_and_deduct_chips(uid, user, bet):
                        bot.send_message(room_id, "❌ Not enough chips!"); return True
                    g.mode = 2; g.bet = bet; g.status = "LOBBY"; g.last_act = time.time()
                    bot.send_message(room_id, f"⚔️ PVP Lobby: {bet} chips. Type !join to accept.")
                    return True

            # Step 2: Gameplay
            if g.status == "PLAYING" and g.turn == uid:
                idx = int(cmd) - 1
                if idx < 0 or idx > 8 or g.board[idx] in ['X', 'O']: return True
                
                g.board[idx] = 'X' if uid == g.p1['id'] else 'O'
                g.last_act = time.time()
                
                win_res = check_win(g.board)
                if win_res:
                    handle_finish(bot, g, win_res)
                    return True
                
                if g.mode == 1: # BOT TURN
                    b_idx = bot_brain(g.board)
                    if b_idx is not None:
                        g.board[b_idx] = 'O'
                        win_res = check_win(g.board)
                        if win_res:
                            handle_finish(bot, g, win_res)
                            return True
                else: # PVP Turn Swap
                    g.turn = g.p2['id'] if uid == g.p1['id'] else g.p1['id']
                
                url = bot.upload_to_server(draw_premium_board(g.board))
                bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": url, "text": "Board Updated..."})
                return True
    return False

def handle_finish(bot, g, result):
    # DRAW
    if result == "DRAW":
        if g.bet > 0: # Refund PVP Bets
            db.update_balance(g.p1['id'], g.p1['name'], chips_change=g.bet)
            if g.mode == 2:
                db.update_balance(g.p2['id'], g.p2['name'], chips_change=g.bet)
        bot.send_message(g.room_id, "🤝 **DRAW!** Chips Refunded.")
    
    # WINNER
    else:
        winner = g.p1 if result == 'X' else g.p2
        loser = g.p2 if result == 'X' else g.p1

        if winner['id'] == 'BOT':
            # Notification for Bot Win + Board
            url = bot.upload_to_server(draw_premium_board(g.board))
            bot.send_json({"handler": "chatroommessage", "roomid": g.room_id, "type": "image", "url": url, "text": "🤖 **BOT WON!** Better luck next time."})
        else:
            chips = BOT_WIN_REWARD_CHIPS if g.mode == 1 else g.bet * 2
            score = BOT_WIN_REWARD_SCORE if g.mode == 1 else PVP_WIN_REWARD_SCORE
            
            # Atomic DB Update
            # In PVP: add_game_result calculates net profit (chips won - bet)
            db.add_game_result(winner['id'], winner['name'], "tictactoe", chips - (g.bet if g.mode == 2 else 0), is_win=True, points_reward=score)
            if g.mode == 2:
                db.add_game_result(loser['id'], loser['name'], "tictactoe", -g.bet, is_win=False)
            
            # Victory Graphics
            img = draw_victory_card(winner['name'], chips, score, winner['id'])
            url = bot.upload_to_server(img)
            bot.send_json({"handler": "chatroommessage", "roomid": g.room_id, "type": "image", "url": url, "text": f"🏆 Winner: @{winner['name']}"})
            
    cleanup_room(g.room_id)
