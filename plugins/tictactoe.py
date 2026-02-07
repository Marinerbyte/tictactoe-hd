import threading
import time
import random
import io
import requests
from PIL import Image, ImageDraw, ImageOps
import db
import utils

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
BOT_WIN_REWARD_CHIPS = 100
BOT_WIN_REWARD_SCORE = 50
PVP_WIN_REWARD_SCORE = 50
LOBBY_TIMEOUT = 120 
MOVE_TIMEOUT = 90

# Global Dictionary for Room-Level Isolation
GAMES = {}
GAMES_LOCK = threading.Lock()

def setup(bot):
    """Confirming plugin is loaded into the bot engine"""
    print("[TicTacToe-HD] Premium Engine with DP Fix & Red Text Loaded.")

# ==========================================
# 🖼️ IMAGE & AVATAR HELPERS
# ==========================================

def get_avatar(url, name):
    """Robust Avatar Fetcher: Direct URL or Fallback to Placeholder"""
    try:
        if not url or "None" in str(url):
            raise Exception("No URL provided")
        
        # Adding headers to mimic a browser for some CDN protections
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            return Image.open(io.BytesIO(resp.content)).convert("RGBA")
        raise Exception("Fetch Failed")
    except Exception as e:
        # Generate a cool initials-based placeholder if fetch fails
        img = Image.new('RGBA', (260, 260), (30, 30, 50))
        d = ImageDraw.Draw(img)
        # Using a default font to draw the first letter of name
        utils.write_text(d, (130, 130), name[0].upper(), size=120, col="white", align="center")
        return img

def apply_round_corners(im, rad):
    """Creates smooth rounded corners for any image"""
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

# ==========================================
# 🎨 GRAPHICS: BOARD & VICTORY CARD
# ==========================================

def draw_premium_board(board):
    """Generates the main 3x3 Neon Tic Tac Toe Board"""
    W, H = 700, 700
    base = utils.get_gradient(W, H, (10, 10, 25), (40, 20, 90))
    img = Image.new('RGBA', (W, H))
    img.paste(base, (0, 0))
    d = ImageDraw.Draw(img)

    # Stylish Neon Outer Borders
    for i in range(6):
        alpha = 150 - (i * 20)
        d.rounded_rectangle([2+i, 2+i, W-2-i, H-2-i], radius=45, outline=f"#EC4899{alpha:02x}", width=2)

    utils.write_text(d, (W // 2, 65), "TIC TAC TOE", size=55, align="center", col="#00F2FE", shadow=True)

    grid_size = 510; box_size = grid_size // 3
    sx, sy = (W - grid_size) // 2, 140

    for i in range(9):
        r, c = i // 3, i % 3
        x, y = sx + c * box_size, sy + r * box_size
        # Dark Box Background
        d.rounded_rectangle([x+6, y+6, x+box_size-6, y+box_size-6], radius=22, fill=(20, 20, 45, 200))
        # Blue Glow Border
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
            # Ghost numbers for empty cells
            utils.write_text(d, (cx, cy), symbol, size=35, col=(255, 255, 255, 40), align="center")

    return apply_round_corners(img, 45)

def draw_victory_card(winner_name, chips_won, score_won, avatar_url):
    """The Final Champion Card: Now with Fixed Colors and DP"""
    W, H = 600, 600
    base = utils.get_gradient(W, H, (30, 10, 60), (10, 80, 120))
    img = Image.new('RGBA', (W, H))
    img.paste(base, (0, 0))
    d = ImageDraw.Draw(img)

    # Multi-layered Golden Frame
    for i in range(8):
        alpha = 255 - (i * 30)
        d.rounded_rectangle([i, i, W-i, H-i], radius=50, outline=f"#FFD700{alpha:02x}", width=2)

    # DP / Avatar processing
    avatar_raw = get_avatar(avatar_url, winner_name)
    avatar = avatar_raw.resize((260, 260), Image.Resampling.LANCZOS)
    mask = Image.new('L', (260, 260), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, 260, 260), fill=255)
    
    cx, cy = W // 2, 220
    # Outer Rings
    for r in range(140, 155, 2): d.ellipse([cx-r, cy-r, cx+r, cy+r], outline="#00F2FE", width=2)
    d.ellipse([cx-135, cy-135, cx+135, cy+135], outline="#FFD700", width=10)
    img.paste(avatar, (cx-130, cy-130), mask)

    # Championship Text
    utils.write_text(d, (W//2, 390), "CHAMPION", size=35, align="center", col="#FFD700", shadow=True)
    utils.write_text(d, (W//2, 455), winner_name.upper(), size=55, align="center", col="white", shadow=True)

    # REWARDS BADGE: Greenish Box + RED TEXT
    badge_w, badge_h = 420, 110
    bx, by = W//2 - badge_w//2, 485
    # Transparent Green Box (Original style as requested)
    d.rounded_rectangle([bx, by, bx+badge_w, by+badge_h], radius=25, fill=(0, 255, 127, 40), outline="#00FF7F", width=3)

    # WON CHIPS: RED TEXT (Fixed)
    utils.write_text(d, (W//2, by + 30), f"WON {chips_won} CHIPS", size=32, align="center", col="#FF0000")
    # SCORE REWARD: BLUE TEXT
    utils.write_text(d, (W//2, by + 75), f"+{score_won} SCORE REWARD", size=26, align="center", col="#00F2FE")

    return apply_round_corners(img, 50)

# ==========================================
# 📦 GAME ENGINE CORE
# ==========================================

class TicTacToeBox:
    """Isolated game logic per room to prevent data leaking"""
    def __init__(self, room_id, p1_data):
        self.room_id = room_id
        self.lock = threading.Lock()
        self.status = "SELECT_MODE" # SELECT_MODE, LOBBY, PLAYING
        self.last_act = time.time()
        
        self.p1 = p1_data # {'id', 'name', 'av'}
        self.p2 = None
        self.board = [str(i+1) for i in range(9)]
        self.mode = 0 # 1=Bot, 2=PVP
        self.bet = 0
        self.turn = None

def cleanup_room(rid):
    """Safely destroys game box and clears memory"""
    with GAMES_LOCK:
        if rid in GAMES: del GAMES[rid]

def check_victory(brd):
    """Checks board for 3-in-a-row or Draw"""
    win_lines = [(0,1,2), (3,4,5), (6,7,8), (0,3,6), (1,4,7), (2,5,8), (0,4,8), (2,4,6)]
    for a, b, c in win_lines:
        if brd[a] == brd[b] == brd[c]: return brd[a]
    if all(x in ['X', 'O'] for x in brd): return 'DRAW'
    return None

def bot_brain(brd):
    """AI logic: Win, Block, or Random"""
    lines = [(0,1,2), (3,4,5), (6,7,8), (0,3,6), (1,4,7), (2,5,8), (0,4,8), (2,4,6)]
    # Win if possible
    for a, b, c in lines:
        if brd[a] == 'O' and brd[b] == 'O' and brd[c] not in ['X','O']: return c
        if brd[a] == 'O' and brd[c] == 'O' and brd[b] not in ['X','O']: return b
        if brd[b] == 'O' and brd[c] == 'O' and brd[a] not in ['X','O']: return a
    # Block Player
    for a, b, c in lines:
        if brd[a] == 'X' and brd[b] == 'X' and brd[c] not in ['X','O']: return c
        if brd[a] == 'X' and brd[c] == 'X' and brd[b] not in ['X','O']: return b
        if brd[b] == 'X' and brd[c] == 'X' and brd[a] not in ['X','O']: return a
    # Random move
    valid = [i for i, x in enumerate(brd) if x not in ['X','O']]
    return random.choice(valid) if valid else None

# ==========================================
# 📡 HANDLER & COMMANDS
# ==========================================

def handle_command(bot, cmd, room_id, user, args, data):
    uid = str(data.get('userid'))
    avatar_url = data.get('avatar') or f"https://api.howdies.app/api/avatar/{uid}"

    # !stop (ADMIN ONLY)
    if cmd == "stop" and uid in db.get_all_admins():
        if room_id in GAMES:
            cleanup_room(room_id)
            bot.send_message(room_id, "🛑 Admin forced game termination.")
        return True

    # !tic (Session Manager)
    if cmd == "tic":
        act = args[0] if args else ""
        if act == "1":
            if room_id in GAMES:
                bot.send_message(room_id, "⚠️ A session is already active in this room.")
                return True
            # Setup Player 1
            p1 = {'id': uid, 'name': user, 'av': avatar_url}
            with GAMES_LOCK:
                GAMES[room_id] = TicTacToeBox(room_id, p1)
            bot.send_message(room_id, "🎮 **TIC TAC TOE SESSION START**\n\nOptions:\n1️⃣ Play with Bot\n2️⃣ PVP (Example: `2 500`)\n\n(120s timer active)")
            return True

        elif act == "0":
            g = GAMES.get(room_id)
            if not g: return True
            with g.lock:
                if uid == g.p1['id'] or uid in db.get_all_admins():
                    if g.status == "LOBBY" and g.bet > 0:
                        db.update_balance(g.p1['id'], g.p1['name'], chips_change=g.bet) # Refund P1
                    bot.send_message(room_id, "✅ Game Session Off.")
                    cleanup_room(room_id)
            return True

    # !join (PVP ONLY)
    if cmd == "join":
        g = GAMES.get(room_id)
        if not g or g.status != "LOBBY": return False
        with g.lock:
            if uid == g.p1['id']: return True # Self-play block
            # Deduct P2 bet instantly
            if not db.check_and_deduct_chips(uid, user, g.bet):
                bot.send_message(room_id, f"❌ @{user} You need {g.bet} chips to join!")
                return True
            # Setup P2
            g.p2 = {'id': uid, 'name': user, 'av': avatar_url}
            g.status = "PLAYING"; g.turn = g.p1['id']; g.last_act = time.time()
            url = bot.upload_to_server(draw_premium_board(g.board))
            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": url, "text": f"⚔️ Match On!\n@{g.p1['name']} vs @{g.p2['name']}\nTurn: @{g.p1['name']}"})
        return True

    # INPUT: Mode Selection OR Moves (Numbers 1-9)
    if cmd.isdigit():
        g = GAMES.get(room_id)
        if not g: return False
        
        with g.lock:
            # 1. TIMEOUT ENGINE
            limit = LOBBY_TIMEOUT if g.status != "PLAYING" else MOVE_TIMEOUT
            if time.time() - g.last_act > limit:
                if g.status == "LOBBY" and g.bet > 0:
                    db.update_balance(g.p1['id'], g.p1['name'], chips_change=g.bet)
                bot.send_message(room_id, "⏰ Game Cleaned up due to inactivity.")
                cleanup_room(room_id); return True

            # 2. SELECT MODE PHASE
            if g.status == "SELECT_MODE" and uid == g.p1['id']:
                if cmd == "1": # Play with Bot
                    g.mode = 1; g.p2 = {'id': 'BOT', 'name': 'Howdies AI', 'av': ''}; g.status = "PLAYING"
                    g.turn = g.p1['id']; g.last_act = time.time()
                    url = bot.upload_to_server(draw_premium_board(g.board))
                    bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": url, "text": "🤖 BOT MATCH STARTED!\nMove (X) with 1-9:"})
                    return True
                
                elif cmd == "2": # Setup PVP
                    try: bet = int(args[0]) if args else 0
                    except: bet = 0
                    if bet <= 0:
                        bot.send_message(room_id, "⚠️ Invalid bet. Use `2 100`."); return True
                    # Deduct P1 bet instantly
                    if not db.check_and_deduct_chips(uid, user, bet):
                        bot.send_message(room_id, "❌ Not enough chips!"); return True
                    g.mode = 2; g.bet = bet; g.status = "LOBBY"; g.last_act = time.time()
                    bot.send_message(room_id, f"⚔️ PVP Lobby: {bet} chips.\nType !join to accept.")
                    return True

            # 3. GAMEPLAY PHASE
            if g.status == "PLAYING" and g.turn == uid:
                idx = int(cmd) - 1
                if idx < 0 or idx > 8 or g.board[idx] in ['X', 'O']: return True
                
                # Player Move
                g.board[idx] = 'X' if uid == g.p1['id'] else 'O'
                g.last_act = time.time()
                
                res = check_victory(g.board)
                if res:
                    process_finish(bot, g, res)
                    return True
                
                # Turn Logic
                if g.mode == 1: # BOT MODE
                    b_idx = bot_brain(g.board)
                    if b_idx is not None:
                        g.board[b_idx] = 'O'
                        res = check_victory(g.board)
                        if res:
                            process_finish(bot, g, res)
                            return True
                else: # PVP TURN SWAP
                    g.turn = g.p2['id'] if uid == g.p1['id'] else g.p1['id']
                
                url = bot.upload_to_server(draw_premium_board(g.board))
                current = g.p1['name'] if g.turn == g.p1['id'] else g.p2['name']
                bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": url, "text": f"Next Move: @{current}"})
                return True

    return False

def process_finish(bot, g, res):
    """Handles rewards, refunds, winner card and room destruction"""
    if res == "DRAW":
        # Refund Chips to anyone who paid
        if g.bet > 0:
            db.update_balance(g.p1['id'], g.p1['name'], chips_change=g.bet)
            if g.mode == 2: db.update_balance(g.p2['id'], g.p2['name'], chips_change=g.bet)
        bot.send_message(g.room_id, "🤝 **DRAW!** All chips have been refunded.")
    
    else:
        winner = g.p1 if res == 'X' else g.p2
        loser = g.p2 if res == 'X' else g.p1
        
        if winner['id'] == 'BOT':
            # Notification if player loses to AI
            url = bot.upload_to_server(draw_premium_board(g.board))
            bot.send_json({"handler": "chatroommessage", "roomid": g.room_id, "type": "image", "url": url, "text": "🤖 **Bot Victory!** Better luck next time."})
        else:
            chips_reward = BOT_WIN_REWARD_CHIPS if g.mode == 1 else g.bet * 2
            score_reward = BOT_WIN_REWARD_SCORE if g.mode == 1 else PVP_WIN_REWARD_SCORE
            
            # Database Write
            # add_game_result parameters: (uid, name, game_name, chips_change, is_win, score_change)
            # PVP Net win is chips_reward - bet (because bet was already deducted)
            db.add_game_result(winner['id'], winner['name'], "tictactoe", chips_reward - (g.bet if g.mode == 2 else 0), is_win=True, points_reward=score_reward)
            if g.mode == 2:
                db.add_game_result(loser['id'], loser['name'], "tictactoe", -g.bet, is_win=False)

            # Generate Victory Graphics
            # We pass winner['av'] which was saved during !tic 1 or !join
            img = draw_victory_card(winner['name'], chips_reward, score_reward, winner['av'])
            url = bot.upload_to_server(img)
            bot.send_json({"handler": "chatroommessage", "roomid": g.room_id, "type": "image", "url": url, "text": f"🏆 {winner['name']} Won!"})
            
    cleanup_room(g.room_id)
