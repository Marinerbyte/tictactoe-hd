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
BOT_WIN_CHIPS = 100
BOT_WIN_SCORE = 50
PVP_WIN_SCORE = 50
LOBBY_TIMEOUT = 120 
MOVE_TIMEOUT = 90

GAMES = {}
GAMES_LOCK = threading.Lock()

def setup(bot):
    print("[TicTacToe-HD] Final Robust Engine Loaded.")

# ==========================================
# 🎨 GRAPHICS ENGINE (Neon & Premium)
# ==========================================

def get_avatar_image(user_id):
    """Howdies platform se user ki DP fetch karne ka logic"""
    try:
        # User ID ke basis pe avatar URL (Standard format)
        url = f"https://api.howdies.app/api/avatar/{user_id}"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            return Image.open(io.BytesIO(resp.content)).convert("RGBA")
        raise Exception("API Error")
    except:
        # Agar fetch fail ho toh placeholder
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

    # Avatar Fetch
    avatar_raw = get_avatar_image(winner_id)
    avatar = avatar_raw.resize((260, 260), Image.Resampling.LANCZOS)
    mask = Image.new('L', (260, 260), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, 260, 260), fill=255)
    
    cx, cy = W // 2, 220
    for r in range(140, 155, 2): d.ellipse([cx-r, cy-r, cx+r, cy+r], outline="#00F2FE", width=2)
    d.ellipse([cx-135, cy-135, cx+135, cy+135], outline="#FFD700", width=10)
    img.paste(avatar, (cx-130, cy-130), mask)

    utils.write_text(d, (W//2, 390), "CHAMPION", size=35, align="center", col="#FFD700", shadow=True)
    utils.write_text(d, (W//2, 450), winner_name.upper(), size=50, align="center", col="white", shadow=True)

    # RED COLOR CHIPS BADGE (As requested)
    badge_w, badge_h = 420, 100
    bx, by = W//2 - badge_w//2, 490
    d.rounded_rectangle([bx, by, bx+badge_w, by+badge_h], radius=25, fill=(255, 0, 0, 40), outline="#FF3131", width=3)

    utils.write_text(d, (W//2, by + 25), f"WON {chips_won} CHIPS", size=32, align="center", col="#FF3131")
    utils.write_text(d, (W//2, by + 68), f"+{score_won} SCORE", size=26, align="center", col="#00F2FE")

    return apply_round_corners(img, 50)

# ==========================================
# 📦 ENGINE BOX
# ==========================================
class TicBox:
    def __init__(self, room_id, p1_data):
        self.room_id = room_id
        self.lock = threading.Lock()
        self.status = "SELECT_MODE"
        self.last_act = time.time()
        self.p1 = p1_data
        self.p2 = None
        self.board = [str(i+1) for i in range(9)]
        self.mode = 0 # 1=Bot, 2=PVP
        self.bet = 0
        self.turn = None

def cleanup(rid):
    with GAMES_LOCK:
        if rid in GAMES: del GAMES[rid]

def check_win(board_data):
    # 'brd' variable use kiya taaki global naming conflict na ho
    w_conditions = [(0,1,2), (3,4,5), (6,7,8), (0,3,6), (1,4,7), (2,5,8), (0,4,8), (2,4,6)]
    for a, b, c in w_conditions:
        if board_data[a] == board_data[b] == board_data[c]:
            return board_data[a]
    if all(x in ['X', 'O'] for x in board_data):
        return 'DRAW'
    return None

def bot_brain(board_data):
    w_conditions = [(0,1,2), (3,4,5), (6,7,8), (0,3,6), (1,4,7), (2,5,8), (0,4,8), (2,4,6)]
    for a, b, c in w_conditions:
        if board_data[a] == 'O' and board_data[b] == 'O' and board_data[c] not in ['X','O']: return c
    for a, b, c in w_conditions:
        if board_data[a] == 'X' and board_data[b] == 'X' and board_data[c] not in ['X','O']: return c
    v = [i for i, x in enumerate(board_data) if x not in ['X','O']]
    return random.choice(v) if v else None

# ==========================================
# 📡 HANDLER
# ==========================================
def handle_command(bot, cmd, room_id, user, args, data):
    uid = str(data.get('userid'))

    # !stop (Admin)
    if cmd == "stop" and uid in db.get_all_admins():
        if room_id in GAMES:
            cleanup(room_id)
            bot.send_message(room_id, "🛑 Admin forced stop.")
        return True

    # !tic (On/Off)
    if cmd == "tic":
        act = args[0] if args else ""
        if act == "1":
            if room_id in GAMES:
                bot.send_message(room_id, "⚠️ Room Busy.")
                return True
            with GAMES_LOCK: GAMES[room_id] = TicBox(room_id, {'id': uid, 'name': user})
            bot.send_message(room_id, "🎮 **TIC TAC TOE SESSION**\n\n1️⃣ Play vs Bot\n2️⃣ PVP Betting (Type: `2 <amount>`)\n\n(120s timer active)")
            return True
        elif act == "0":
            g = GAMES.get(room_id)
            if not g: return True
            with g.lock:
                if uid == g.p1['id'] or uid in db.get_all_admins():
                    if g.status == "LOBBY" and g.bet > 0:
                        db.update_balance(g.p1['id'], g.p1['name'], chips_change=g.bet)
                    bot.send_message(room_id, "✅ Session Cancelled.")
                    cleanup(room_id)
            return True

    # !join
    if cmd == "join":
        g = GAMES.get(room_id)
        if not g or g.status != "LOBBY": return False
        with g.lock:
            if uid == g.p1['id']: return True
            if not db.check_and_deduct_chips(uid, user, g.bet):
                bot.send_message(room_id, f"❌ You need {g.bet} chips to join.")
                return True
            g.p2 = {'id': uid, 'name': user}
            g.status = "PLAYING"; g.turn = g.p1['id']; g.last_act = time.time()
            url = bot.upload_to_server(draw_premium_board(g.board))
            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": url, "text": f"⚔️ Match Started: @{g.p1['name']} vs @{g.p2['name']}"})
        return True

    # Movement & Modes
    if cmd.isdigit():
        g = GAMES.get(room_id)
        if not g: return False
        with g.lock:
            limit = 120 if g.status != "PLAYING" else 90
            if time.time() - g.last_act > limit:
                if g.status == "LOBBY" and g.bet > 0:
                    db.update_balance(g.p1['id'], g.p1['name'], chips_change=g.bet)
                bot.send_message(room_id, "⏰ Session Expired.")
                cleanup(room_id); return True

            # Select Mode
            if g.status == "SELECT_MODE" and uid == g.p1['id']:
                if cmd == "1":
                    g.mode = 1; g.p2 = {'id': 'BOT', 'name': 'Howdies AI'}; g.status = "PLAYING"
                    g.turn = g.p1['id']; g.last_act = time.time()
                    url = bot.upload_to_server(draw_premium_board(g.board))
                    bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": url, "text": "🤖 BOT MATCH: Type 1-9 to Move."})
                    return True
                elif cmd == "2":
                    try: bet = int(args[0]) if args else 0
                    except: bet = 0
                    if bet <= 0 or not db.check_and_deduct_chips(uid, user, bet):
                        bot.send_message(room_id, "❌ Valid chips bet required!"); return True
                    g.mode = 2; g.bet = bet; g.status = "LOBBY"; g.last_act = time.time()
                    bot.send_message(room_id, f"⚔️ PVP Lobby: {bet} chips. !join to enter.")
                    return True

            # Moves
            if g.status == "PLAYING" and g.turn == uid:
                idx = int(cmd) - 1
                if idx < 0 or idx > 8 or g.board[idx] in ['X', 'O']: return True
                g.board[idx] = 'X' if uid == g.p1['id'] else 'O'
                g.last_act = time.time()
                
                res = check_win(g.board)
                if res: finish_now(bot, g, res); return True
                
                if g.mode == 1:
                    move = bot_brain(g.board)
                    if move is not None:
                        g.board[move] = 'O'
                        res = check_win(g.board)
                        if res: finish_now(bot, g, res); return True
                else:
                    g.turn = g.p2['id'] if uid == g.p1['id'] else g.p1['id']
                
                url = bot.upload_to_server(draw_premium_board(g.board))
                bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": url, "text": "Board Updated..."})
                return True
    return False

def finish_now(bot, g, res):
    if res == "DRAW":
        if g.bet > 0: db.update_balance(g.p1['id'], g.p1['name'], chips_change=g.bet)
        if g.mode == 2: db.update_balance(g.p2['id'], g.p2['name'], chips_change=g.bet)
        bot.send_message(g.room_id, "🤝 DRAW! Refunded.")
    else:
        winner = g.p1 if res == 'X' else g.p2
        loser = g.p2 if res == 'X' else g.p1
        
        # BOT WIN NOTIFICATION
        if winner['id'] == 'BOT':
            url = bot.upload_to_server(draw_premium_board(g.board))
            bot.send_json({"handler": "chatroommessage", "roomid": g.room_id, "type": "image", "url": url, "text": "🤖 **Bot Victory!** You lost your bet."})
        else:
            chips = BOT_WIN_CHIPS if g.mode == 1 else g.bet * 2
            score = BOT_WIN_SCORE if g.mode == 1 else PVP_WIN_SCORE
            
            # DB Write
            db.add_game_result(winner['id'], winner['name'], "tictactoe", chips - (g.bet if g.mode == 2 else 0), is_win=True, points_reward=score)
            if g.mode == 2: db.add_game_result(loser['id'], loser['name'], "tictactoe", -g.bet, is_win=False)
            
            # Champion Graphics
            img = draw_victory_card(winner['name'], chips, score, winner['id'])
            url = bot.upload_to_server(img)
            bot.send_json({"handler": "chatroommessage", "roomid": g.room_id, "type": "image", "url": url, "text": f"🏆 Winner: @{winner['name']}"})
            
    cleanup(g.room_id)
