import threading
import time
import random
import io
import requests
from PIL import Image, ImageDraw, ImageOps
import db
import utils

# ==========================================
# ⚙️ SETTINGS & ADMIN CONTROL
# ==========================================
# Default values (Admin can change runtime via !tchips/!tscore)
REWARDS = {
    "bot_chips": 100,
    "bot_score": 50,
    "pvp_score": 50
}

# Timers
LOBBY_TIMEOUT = 120  # 120 seconds before lobby cleanup
MOVE_TIMEOUT = 90    # 90 seconds before move cleanup

# Room Isolation (Dabba system)
GAMES = {}
GAMES_LOCK = threading.Lock()

def setup(bot):
    """Howdies Loader confirms plugin activation"""
    print("[TicTacToe-HD] Ultimate Premium Engine Activated.")

# ==========================================
# 🎨 GRAPHICS ENGINE (The Premium Boards)
# ==========================================

def get_avatar_image(url):
    try:
        if not url: raise Exception
        resp = requests.get(url, timeout=5)
        img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
        return img
    except:
        # Placeholder if avatar fails
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
    # Gradient Background
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
    start_x = (W - grid_size) // 2; start_y = 140

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

def draw_victory_card(winner_name, chips_won, score_won, avatar_url):
    W, H = 600, 600
    base = utils.get_gradient(W, H, (30, 10, 60), (10, 80, 120))
    img = Image.new('RGBA', (W, H))
    img.paste(base, (0, 0))
    d = ImageDraw.Draw(img)

    # Golden border
    for i in range(8):
        alpha = 255 - (i * 30)
        d.rounded_rectangle([i, i, W-i, H-i], radius=50, outline=f"#FFD700{alpha:02x}", width=2)

    # Avatar Handling
    avatar_raw = get_avatar_image(avatar_url)
    avatar = avatar_raw.resize((260, 260), Image.Resampling.LANCZOS)
    mask = Image.new('L', (260, 260), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, 260, 260), fill=255)
    cx, cy = W // 2, 220

    # Glow effect
    for r in range(140, 155, 2):
        d.ellipse([cx-r, cy-r, cx+r, cy+r], outline="#00F2FE", width=2)
    d.ellipse([cx-135, cy-135, cx+135, cy+135], outline="#FFD700", width=10)
    img.paste(avatar, (cx-130, cy-130), mask)

    # Text
    utils.write_text(d, (W//2, 390), "CHAMPION", size=35, align="center", col="#FFD700", shadow=True)
    utils.write_text(d, (W//2, 450), winner_name.upper(), size=50, align="center", col="white", shadow=True)

    # Rewards Badge (Expanded to show Score)
    badge_w, badge_h = 420, 95
    bx, by = W//2 - badge_w//2, 490
    d.rounded_rectangle([bx, by, bx+badge_w, by+badge_h], radius=25, fill=(0, 255, 127, 40), outline="#00FF7F", width=3)

    utils.write_text(d, (W//2, by + 25), f"WON {chips_won} CHIPS", size=30, align="center", col="#00FF7F")
    utils.write_text(d, (W//2, by + 65), f"+{score_won} SCORE", size=28, align="center", col="#00F2FE")

    return apply_round_corners(img, 50)

# ==========================================
# 📦 GAME ENGINE (ISOLATED)
# ==========================================
class TicTacToeBox:
    def __init__(self, room_id, p1_data):
        self.room_id = room_id
        self.lock = threading.Lock()
        self.status = "SELECT_MODE" 
        self.last_activity = time.time()
        self.p1 = p1_data # {'id', 'name'}
        self.p2 = None
        self.board = [str(i+1) for i in range(9)]
        self.mode = 0 # 1=Bot, 2=PVP
        self.bet = 0
        self.turn = None

def cleanup_room(room_id):
    with GAMES_LOCK:
        if room_id in GAMES:
            del GAMES[room_id]

def check_win(b):
    w = [(0,1,2), (3,4,5), (6,7,8), (0,3,6), (1,4,7), (2,5,8), (0,4,8), (2,4,6)]
    for a,b,c in w:
        if b[a] == b[b] == b[c]: return b[a]
    if all(x in ['X', 'O'] for x in b): return 'DRAW'
    return None

def bot_logic(b):
    w = [(0,1,2), (3,4,5), (6,7,8), (0,3,6), (1,4,7), (2,5,8), (0,4,8), (2,4,6)]
    # Win
    for a,b,c in w:
        if b[a] == 'O' and b[b] == 'O' and b[c] not in ['X','O']: return c
    # Block
    for a,b,c in w:
        if b[a] == 'X' and b[b] == 'X' and b[c] not in ['X','O']: return c
    # Random
    v = [i for i, x in enumerate(b) if x not in ['X','O']]
    return random.choice(v) if v else None

# ==========================================
# 📡 COMMAND HANDLER
# ==========================================
def handle_command(bot, cmd, room_id, user, args, data):
    # Using bot_engine's standardized userid
    uid = str(data.get('userid'))

    # --- Admin Config Commands ---
    if cmd == "tchips":
        if uid in db.get_all_admins():
            try: REWARDS["bot_chips"] = int(args[0]); bot.send_message(room_id, f"✅ Bot win chips set to {args[0]}")
            except: pass
            return True
    if cmd == "tscore":
        if uid in db.get_all_admins():
            try: REWARDS["bot_score"] = int(args[0]); bot.send_message(room_id, f"✅ Bot win score set to {args[0]}")
            except: pass
            return True

    # --- !stop (Admin Force) ---
    if cmd == "stop":
        if uid in db.get_all_admins():
            if room_id in GAMES:
                cleanup_room(room_id)
                bot.send_message(room_id, "🛑 Admin forced game shutdown.")
            return True

    # --- !tic (System Controller) ---
    if cmd == "tic":
        action = args[0] if args else ""
        
        # !tic 1 (START)
        if action == "1":
            if room_id in GAMES:
                bot.send_message(room_id, "⚠️ Room already has a pending session.")
                return True
            p1 = {'id': uid, 'name': user}
            with GAMES_LOCK:
                GAMES[room_id] = TicTacToeBox(room_id, p1)
            bot.send_message(room_id, "🎮 **TIC TAC TOE SESSION ON**\n\nChoose Game Type:\nType **1** ▶️ Play with Bot\nType **2 <amount>** ▶️ PVP Betting\n\n(120s timer active)")
            return True

        # !tic 0 (OFF/CANCEL)
        elif action == "0":
            g = GAMES.get(room_id)
            if not g: return True
            with g.lock:
                if uid == g.p1['id'] or uid in db.get_all_admins():
                    if g.status == "LOBBY" and g.bet > 0:
                        db.update_balance(g.p1['id'], g.p1['name'], chips_change=g.bet) # Refund
                    bot.send_message(room_id, "✅ Game Session Terminated.")
                    cleanup_room(room_id)
            return True

    # --- !join (PVP Entry) ---
    if cmd == "join":
        g = GAMES.get(room_id)
        if not g or g.status != "LOBBY": return False
        with g.lock:
            if uid == g.p1['id']: return True
            if not db.check_and_deduct_chips(uid, user, g.bet):
                bot.send_message(room_id, f"❌ Insufficient Chips! Need {g.bet}")
                return True
            g.p2 = {'id': uid, 'name': user}
            g.status = "PLAYING"; g.turn = g.p1['id']; g.last_activity = time.time()
            url = bot.upload_to_server(draw_premium_board(g.board))
            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": url, "text": f"Match Started!\n@{g.p1['name']} vs @{g.p2['name']}\nTurn: @{g.p1['name']}"})
        return True

    # --- Input Processing (Numbers 1-9 & Modes) ---
    if cmd.isdigit():
        g = GAMES.get(room_id)
        if not g: return False
        
        with g.lock:
            # 1. Timeout Checks
            limit = LOBBY_TIMEOUT if g.status != "PLAYING" else MOVE_TIMEOUT
            if time.time() - g.last_activity > limit:
                if g.status == "LOBBY" and g.bet > 0:
                    db.update_balance(g.p1['id'], g.p1['name'], chips_change=g.bet)
                bot.send_message(room_id, "⏰ Game Box Cleaned due to inactivity.")
                cleanup_room(room_id); return True

            # 2. Selecting Mode
            if g.status == "SELECT_MODE" and uid == g.p1['id']:
                if cmd == "1":
                    g.mode = 1; g.p2 = {'id': 'BOT', 'name': 'Howdies AI'}; g.status = "PLAYING"
                    g.turn = g.p1['id']; g.last_activity = time.time()
                    url = bot.upload_to_server(draw_premium_board(g.board))
                    bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": url, "text": "BOT MATCH STARTED!\nWin Reward: 100c\nYour Move (X):"})
                    return True
                elif cmd == "2":
                    try: bet = int(args[0]) if args else 0
                    except: bet = 0
                    if bet <= 0 or not db.check_and_deduct_chips(uid, user, bet):
                        bot.send_message(room_id, "❌ Valid bet & chips required!"); return True
                    g.mode = 2; g.bet = bet; g.status = "LOBBY"; g.last_activity = time.time()
                    bot.send_message(room_id, f"⚔️ PVP Lobby Created! Bet: {bet} chips.\nType !join to play.")
                    return True

            # 3. Gameplay Moves
            if g.status == "PLAYING" and g.turn == uid:
                idx = int(cmd) - 1
                if idx < 0 or idx > 8 or g.board[idx] in ['X', 'O']: return True
                
                g.board[idx] = 'X' if uid == g.p1['id'] else 'O'
                g.last_activity = time.time()
                
                res = check_win(g.board)
                if res: finish_up(bot, g, res); return True
                
                # Mode 1: Bot Moves Immediately
                if g.mode == 1:
                    bm = bot_logic(g.board)
                    if bm is not None: g.board[bm] = 'O'
                    res = check_win(g.board)
                    if res: finish_up(bot, g, res); return True
                else:
                    # PVP Turn Swap
                    g.turn = g.p2['id'] if uid == g.p1['id'] else g.p1['id']
                
                url = bot.upload_to_server(draw_premium_board(g.board))
                msg = f"Turn: @{g.p1['name'] if g.turn == g.p1['id'] else g.p2['name']}"
                bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": url, "text": msg})
                return True
    return False

def finish_up(bot, g, res):
    if res == "DRAW":
        if g.bet > 0: db.update_balance(g.p1['id'], g.p1['name'], chips_change=g.bet)
        if g.mode == 2: db.update_balance(g.p2['id'], g.p2['name'], chips_change=g.bet)
        bot.send_message(g.room_id, "🤝 **DRAW!** All chips refunded.")
    else:
        winner = g.p1 if res == 'X' else g.p2
        if winner['id'] == 'BOT':
            url = bot.upload_to_server(draw_premium_board(g.board))
            bot.send_json({"handler": "chatroommessage", "roomid": g.room_id, "type": "image", "url": url, "text": "🤖 **Bot Wins!** Better luck next time."})
        else:
            chips = REWARDS["bot_chips"] if g.mode == 1 else g.bet * 2
            score = REWARDS["bot_score"] if g.mode == 1 else REWARDS["pvp_score"]
            # Save to DB
            db.add_game_result(winner['id'], winner['name'], "tictactoe", chips - (g.bet if g.mode == 2 else 0), is_win=True, points_reward=score)
            
            # Show Winner Card
            img = draw_victory_card(winner['name'], chips, score, "")
            url = bot.upload_to_server(img)
            bot.send_json({"handler": "chatroommessage", "roomid": g.room_id, "type": "image", "url": url, "text": f"🏆 {winner['name']} is the Champion!"})
    cleanup_room(g.room_id)
