import threading
import time
import random
import io
import requests
from PIL import Image, ImageDraw
import db
import utils # assumes utils.py handles gradient & text

# --- CONFIG ---
BOT_REWARD_CHIPS = 100
BOT_REWARD_SCORE = 50
LOBBY_TIMEOUT = 120
MOVE_TIMEOUT = 90

# Room Isolation Box
GAMES = {}
GAMES_LOCK = threading.Lock()

def setup(bot):
    print("[TicTacToe] High-Stakes Engine Loaded.")

# ==========================================
# 🎨 GRAPHICS ENGINE
# ==========================================

def get_avatar_image(url):
    try:
        if not url: raise Exception
        resp = requests.get(url, timeout=5)
        return Image.open(io.BytesIO(resp.content)).convert("RGBA")
    except:
        return Image.new('RGBA', (200, 200), (40, 40, 60))

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
    grid_size = 510; box_size = grid_size // 3; start_x = (W - grid_size) // 2; start_y = 140
    for i in range(9):
        row, col = i // 3, i % 3
        x, y = start_x + col * box_size, start_y + row * box_size
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

def draw_victory_card(name, chips, score, av_url):
    W, H = 600, 600
    base = utils.get_gradient(W, H, (30, 10, 60), (10, 80, 120))
    img = Image.new('RGBA', (W, H))
    img.paste(base, (0, 0))
    d = ImageDraw.Draw(img)
    for i in range(8):
        alpha = 255 - (i * 30)
        d.rounded_rectangle([i, i, W-i, H-i], radius=50, outline=f"#FFD700{alpha:02x}", width=2)
    avatar = get_avatar_image(av_url).resize((260, 260), Image.Resampling.LANCZOS)
    mask = Image.new('L', (260, 260), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, 260, 260), fill=255)
    cx, cy = W // 2, 220
    for r in range(140, 155, 2): d.ellipse([cx-r, cy-r, cx+r, cy+r], outline="#00F2FE", width=2)
    d.ellipse([cx-135, cy-135, cx+135, cy+135], outline="#FFD700", width=10)
    img.paste(avatar, (cx-130, cy-130), mask)
    utils.write_text(d, (W//2, 390), "CHAMPION", size=35, align="center", col="#FFD700", shadow=True)
    utils.write_text(d, (W//2, 450), name.upper(), size=50, align="center", col="white", shadow=True)
    badge_w, badge_h = 400, 90; bx, by = W//2 - badge_w//2, 490
    d.rounded_rectangle([bx, by, bx+badge_w, by+badge_h], radius=25, fill=(0, 0, 0, 150), outline="#00FF7F", width=3)
    utils.write_text(d, (W//2, by + 25), f"WON {chips} CHIPS", size=30, align="center", col="#00FF7F")
    utils.write_text(d, (W//2, by + 65), f"+{score} SCORE", size=28, align="center", col="#00F2FE")
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
        self.p1 = p1_data # {id, name, av}
        self.p2 = None
        self.board = [str(i+1) for i in range(9)]
        self.mode = 0 # 1=Bot, 2=PVP
        self.bet = 0
        self.turn = None

def cleanup(rid):
    with GAMES_LOCK:
        if rid in GAMES: del GAMES[rid]

def check_win(b):
    w = [(0,1,2), (3,4,5), (6,7,8), (0,3,6), (1,4,7), (2,5,8), (0,4,8), (2,4,6)]
    for a,b,c in w:
        if b[a] == b[b] == b[c]: return b[a]
    if all(x in ['X', 'O'] for x in b): return 'DRAW'
    return None

def bot_move(b):
    w = [(0,1,2), (3,4,5), (6,7,8), (0,3,6), (1,4,7), (2,5,8), (0,4,8), (2,4,6)]
    for a,b,c in w:
        if b[a] == 'O' and b[b] == 'O' and b[c] not in ['X','O']: return c
    for a,b,c in w:
        if b[a] == 'X' and b[b] == 'X' and b[c] not in ['X','O']: return c
    v = [i for i, x in enumerate(b) if x not in ['X','O']]
    return random.choice(v) if v else None

# ==========================================
# 📡 HANDLER
# ==========================================
def handle_command(bot, cmd, room_id, user, args, data):
    uid = str(data.get('userid'))

    # Admin Force Stop
    if cmd == "stop":
        if uid in db.get_all_admins():
            cleanup(room_id)
            bot.send_message(room_id, "🛑 Admin forced game end.")
            return True
        return False

    # Main Command: !tic
    if cmd == "tic":
        act = args[0] if args else ""
        if act == "1":
            if room_id in GAMES:
                bot.send_message(room_id, "⚠️ Room Busy.")
                return True
            p1 = {'id': uid, 'name': user, 'av': ""}
            with GAMES_LOCK: GAMES[room_id] = TicBox(room_id, p1)
            bot.send_message(room_id, "🎮 **TIC TAC TOE ON**\n\n1️⃣ Play vs BOT (100c Reward)\n2️⃣ PVP (Type: `2 <bet>`)\n\n(120s timer active)")
            return True
        
        if act == "0":
            g = GAMES.get(room_id)
            if not g: return True
            with g.lock:
                if uid == g.p1['id'] or uid in db.get_all_admins():
                    if g.status == "LOBBY" and g.bet > 0:
                        db.update_balance(g.p1['id'], g.p1['name'], chips_change=g.bet)
                    bot.send_message(room_id, "✅ Game Cancelled.")
                    cleanup(room_id)
            return True

    # Join PVP
    if cmd == "join":
        g = GAMES.get(room_id)
        if not g or g.status != "LOBBY": return False
        with g.lock:
            if uid == g.p1['id']: return True
            if not db.check_and_deduct_chips(uid, user, g.bet):
                bot.send_message(room_id, "❌ No Chips!")
                return True
            g.p2 = {'id': uid, 'name': user, 'av': ""}
            g.status = "PLAYING"; g.turn = g.p1['id']; g.last_act = time.time()
            url = bot.upload_to_server(draw_premium_board(g.board))
            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": url, "text": f"Match Start: @{g.p1['name']} vs @{g.p2['name']}"})
        return True

    # Input Handling (Numbers)
    if cmd.isdigit():
        g = GAMES.get(room_id)
        if not g: return False
        with g.lock:
            # Timeout Check
            limit = LOBBY_TIMEOUT if g.status != "PLAYING" else MOVE_TIMEOUT
            if time.time() - g.last_act > limit:
                if g.status == "LOBBY" and g.bet > 0:
                    db.update_balance(g.p1['id'], g.p1['name'], chips_change=g.bet)
                bot.send_message(room_id, "⏰ Time Up! Memory Cleaned.")
                cleanup(room_id); return True

            # Mode Selection
            if g.status == "SELECT_MODE" and uid == g.p1['id']:
                if cmd == "1":
                    g.mode = 1; g.p2 = {'id': 'BOT', 'name': 'AI Bot'}; g.status = "PLAYING"
                    g.turn = g.p1['id']; g.last_act = time.time()
                    url = bot.upload_to_server(draw_premium_board(g.board))
                    bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": url, "text": "BOT GAME START (X)"})
                    return True
                elif cmd == "2":
                    try: bet = int(args[0]) if args else 0
                    except: bet = 0
                    if bet <= 0 or not db.check_and_deduct_chips(uid, user, bet):
                        bot.send_message(room_id, "❌ Invalid Bet/Chips!"); return True
                    g.mode = 2; g.bet = bet; g.status = "LOBBY"; g.last_act = time.time()
                    bot.send_message(room_id, f"⚔️ PVP Lobby: {bet} chips. Type !join")
                    return True

            # Game Moves
            if g.status == "PLAYING" and g.turn == uid:
                idx = int(cmd) - 1
                if idx < 0 or idx > 8 or g.board[idx] in ['X', 'O']: return True
                g.board[idx] = 'X' if uid == g.p1['id'] else 'O'
                g.last_act = time.time()
                res = check_win(g.board)
                if res: finish(bot, g, res); return True
                
                if g.mode == 1:
                    bm = bot_move(g.board)
                    if bm is not None: g.board[bm] = 'O'
                    res = check_win(g.board)
                    if res: finish(bot, g, res); return True
                else:
                    g.turn = g.p2['id'] if uid == g.p1['id'] else g.p1['id']
                
                url = bot.upload_to_server(draw_premium_board(g.board))
                bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": url, "text": "Next Turn..."})
                return True
    return False

def finish(bot, g, res):
    if res == "DRAW":
        if g.bet > 0: db.update_balance(g.p1['id'], g.p1['name'], chips_change=g.bet)
        if g.mode == 2: db.update_balance(g.p2['id'], g.p2['name'], chips_change=g.bet)
        bot.send_message(g.room_id, "🤝 Draw! Refunded.")
    else:
        win = g.p1 if res == 'X' else g.p2
        if win['id'] == 'BOT':
            bot.send_message(g.room_id, "🤖 Bot Wins!")
        else:
            chips = BOT_REWARD_CHIPS if g.mode == 1 else g.bet * 2
            score = BOT_REWARD_SCORE if g.mode == 1 else 50
            db.add_game_result(win['id'], win['name'], "tictactoe", chips - (g.bet if g.mode == 2 else 0), is_win=True, points_reward=score)
            img = draw_victory_card(win['name'], chips, score, "")
            url = bot.upload_to_server(img)
            bot.send_json({"handler": "chatroommessage", "roomid": g.room_id, "type": "image", "url": url, "text": "CHAMPION!"})
    cleanup(g.room_id)
