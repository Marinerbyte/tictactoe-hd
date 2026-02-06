import time
import random
import threading
import sys
import os
import requests
import io
from PIL import Image, ImageDraw, ImageOps, ImageFilter

# --- UTILS & DB ---
try: import utils
except ImportError: print("[Mines] Error: utils.py missing!")

try:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    import db
except Exception as e: print(f"DB Error: {e}")

# --- GLOBAL STATE ---
games = {} 
setup_pending = {} # {user_id: room_id}
game_lock = threading.Lock()
AVATAR_CACHE = {}

def to_small_caps(text):
    normal = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    small  = "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ"
    trans = str.maketrans(normal, small)
    return text.translate(trans)

def setup(bot_ref):
    threading.Thread(target=cleanup_loop, daemon=True).start()
    print("[Mines] Dual Mode (Bot/PvP) Engine Loaded.")

# ==========================================
# 🖼️ STICK AVATAR LOGIC (Source of Truth)
# ==========================================

def get_robust_avatar(avatar_url, username):
    if avatar_url and avatar_url in AVATAR_CACHE:
        return AVATAR_CACHE[avatar_url].copy()
    if avatar_url:
        try:
            r = requests.get(avatar_url, timeout=4)
            if r.status_code == 200:
                img = Image.open(io.BytesIO(r.content)).convert("RGBA")
                AVATAR_CACHE[avatar_url] = img
                return img.copy()
        except: pass
    try:
        fb_url = f"https://api.dicebear.com/9.x/adventurer/png?seed={username}&backgroundColor=transparent"
        r = requests.get(fb_url, timeout=4)
        if r.status_code == 200:
            return Image.open(io.BytesIO(r.content)).convert("RGBA")
    except: pass
    return Image.new("RGBA", (100, 100), (120, 120, 120, 255))

def circle_crop(img, size):
    img = img.resize((size, size), Image.Resampling.LANCZOS)
    mask = Image.new('L', (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size, size), fill=255)
    output = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    output.paste(img, (0, 0), mask)
    return output

# ==========================================
# 🖌️ RENDERING ENGINE
# ==========================================

def draw_3d_box(d, x, y, size, text):
    radius = 15
    d.rounded_rectangle([x, y+6, x+size, y+size+6], radius=radius, fill=(20, 30, 50))
    d.rounded_rectangle([x, y, x+size, y+size], radius=radius, fill=(60, 90, 160), outline="#8899AA", width=2)
    utils.write_text(d, (x+size//2, y+size//2), text, size=30, align="center", col=(255,255,255,40))

def draw_grid_board(game):
    W, H = 500, 580 
    img = utils.create_canvas(W, H, color=(15, 15, 20))
    d = ImageDraw.Draw(img)
    
    is_p1 = (game.turn == 'P1')
    curr_name = game.p1_name if is_p1 else game.p2_name
    curr_av = game.p1_av if is_p1 else game.p2_av
    curr_lives = game.lives_p1 if is_p1 else game.lives_p2
    
    d.rounded_rectangle([15, 10, 485, 110], radius=20, fill=(45, 55, 85), outline="#00FFFF", width=3)
    p_img = circle_crop(get_robust_avatar(curr_av, curr_name), 80)
    img.paste(p_img, (30, 20), p_img)
    
    utils.write_text(d, (130, 35), f"PLAYER: {curr_name.upper()}", size=24, align="left", col="white")
    utils.write_text(d, (130, 70), f"LIVES: {'❤️' * curr_lives}", size=22, align="left")

    target_board = game.board_p1 if is_p1 else game.board_p2
    revealed = game.revealed_p1 if is_p1 else game.revealed_p2
    
    start_x, start_y, bx_sz, gap = 55, 130, 85, 15
    for i in range(12):
        row, col = i // 4, i % 4
        x, y = start_x + (col * (bx_sz + gap)), start_y + (row * (bx_sz + gap))
        if not revealed[i]:
            draw_3d_box(d, x, y, bx_sz, str(i+1))
        else:
            is_bomb = (target_board[i] == 1)
            box_col = (180, 50, 50) if is_bomb else (50, 180, 80)
            d.rounded_rectangle([x, y, x+bx_sz, y+bx_sz], radius=15, fill=box_col, outline="white", width=2)
            icon = utils.get_emoji("💣" if is_bomb else "🍪", size=50)
            img.paste(icon, (x+17, y+10), icon)
    return img

def draw_blast_card(name, avatar_url):
    W, H = 500, 500
    img = utils.create_canvas(W, H, (35, 0, 0))
    d = ImageDraw.Draw(img)
    boom = utils.get_emoji("💥", size=300)
    img.paste(boom, (100, 50), boom)
    p_img = circle_crop(get_robust_avatar(avatar_url, name), 200)
    p_img = ImageOps.grayscale(p_img).convert("RGBA")
    img.paste(p_img, (150, 150), p_img)
    utils.write_text(d, (250, 420), to_small_caps(f"{name} HIT A BOMB!"), size=35, align="center", col="red")
    return img

def draw_winner_card(name, reward, pts, avatar_url):
    W, H = 500, 500
    img = utils.create_canvas(W, H, (10, 30, 10))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([10, 10, 490, 490], radius=50, outline="#FFD700", width=8)
    p_img = circle_crop(get_robust_avatar(avatar_url, name), 180)
    img.paste(p_img, (160, 50), p_img)
    utils.write_text(d, (250, 280), "🏆 CHAMPION 🏆", size=30, align="center", col="#FFD700")
    utils.write_text(d, (250, 340), name.upper(), size=45, align="center", col="white")
    utils.write_text(d, (250, 420), f"+{reward} Chips | +{pts} Points", size=30, align="center", col="#00FF7F")
    return img

def draw_setup_instructions():
    W, H = 500, 500
    img = utils.create_canvas(W, H, (25, 30, 45))
    d = ImageDraw.Draw(img)
    utils.write_text(d, (250, 40), "SET 4 BOMBS (1-12)", size=35, align="center", col="#FFD700")
    start_x, start_y, bx_w, bx_h, gap = 55, 100, 85, 75, 15
    for i in range(12):
        row, col = i // 4, i % 4
        x, y = start_x + (col * (bx_w + gap)), start_y + (row * (bx_h + gap))
        d.rounded_rectangle([x, y, x+bx_w, y+bx_h], radius=10, fill=(50, 60, 90), outline="#DDD")
        utils.write_text(d, (x+bx_w//2, y+bx_h//2), str(i+1), size=24, align="center", col="white")
    return img

# ==========================================
# ⚙️ GAME CLASS
# ==========================================

class MinesGame:
    def __init__(self, room_id, p1_id, p1_name, p1_av):
        self.room_id = room_id
        self.p1_id = p1_id; self.p1_name = p1_name; self.p1_av = p1_av
        self.p2_id = self.p2_name = self.p2_av = None
        self.state = 'lobby'; self.mode = None; self.bet = 0
        self.board_p1 = [0]*12; self.board_p2 = [0]*12
        self.revealed_p1 = [False]*12; self.revealed_p2 = [False]*12
        self.lives_p1 = 3; self.lives_p2 = 3
        self.turn = 'P1'; self.last_interaction = time.time()
    def touch(self): self.last_interaction = time.time()

# ==========================================
# 📨 HANDLERS
# ==========================================

def handle_command(bot, command, room_id, user, args, data):
    global games, setup_pending
    uid = str(data.get('userid', user))
    av_url = data.get("avatar") 
    cmd = command.lower().strip()

    # --- DM SETUP ---
    if uid in setup_pending and not room_id:
        nums = [int(s) for s in command.replace(',', ' ').split() if s.isdigit()]
        unique_nums = list(set(nums))
        if len(unique_nums) == 4 and all(1 <= n <= 12 for n in unique_nums):
            parent_room = setup_pending[uid]
            with game_lock:
                g = games.get(parent_room)
                if not g: return False
                if uid == g.p1_id: g.board_p2 = [1 if i+1 in unique_nums else 0 for i in range(12)]
                else: g.board_p1 = [1 if i+1 in unique_nums else 0 for i in range(12)]
                bot.send_dm(user, "✅ Bombs placed! Waiting for opponent...")
                del setup_pending[uid]
                if sum(g.board_p1) == 4 and sum(g.board_p2) == 4:
                    g.state = 'playing'
                    bot.send_message(parent_room, "🔥 **Match Start!**")
                    url = utils.upload(bot, draw_grid_board(g))
                    bot.send_json({"handler": "chatroommessage", "roomid": parent_room, "type": "image", "url": url, "text": "GO!"})
            return True
        return False

    # --- ROOM ACTIONS ---
    with game_lock: g = games.get(room_id)

    if cmd == "mines":
        if g: return True
        with game_lock: games[room_id] = MinesGame(room_id, uid, user, av_url)
        bot.send_message(room_id, f"💣 **MINES**\n@{user}, Mode select karein:\n1️⃣ Vs Bot (Free | Win +2000 Chips & +100 Pts)\n2️⃣ Multiplayer (Bet Required)")
        return True

    if not g: return False

    # Mode 1: Vs Bot Setup
    if g.state == 'lobby' and uid == g.p1_id and cmd == "1":
        g.mode = 1; g.state = 'playing'; g.touch()
        # Bot hides 4 bombs
        bombs = random.sample(range(12), 4)
        for b in bombs: g.board_p1[b] = 1
        url = utils.upload(bot, draw_grid_board(g))
        bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": url, "text": "Bot Game Start"})
        return True

    # Mode 2: PvP Setup
    if g.state == 'lobby' and uid == g.p1_id and cmd == "2":
        g.mode = 2; g.state = 'betting'; bot.send_message(room_id, "💰 **Bet amount?** (e.g. `!bet 500`)")
        return True

    if g.state == 'betting' and uid == g.p1_id and cmd == "bet":
        try:
            amt = int(args[0])
            if db.check_and_deduct_chips(uid, user, amt):
                g.bet = amt; g.state = 'waiting'; g.touch()
                bot.send_message(room_id, f"⚔️ @{user} bet **{amt} Chips**. Type `!join` to accept!")
            else: bot.send_message(room_id, "❌ Balance kam hai!")
        except: pass
        return True

    if g.state == 'waiting' and cmd == "join" and uid != g.p1_id:
        if db.check_and_deduct_chips(uid, user, g.bet):
            g.p2_id, g.p2_name, g.p2_av = uid, user, av_url
            g.state = 'setup'; setup_pending[g.p1_id] = room_id; setup_pending[g.p2_id] = room_id
            bot.send_message(room_id, "✅ Match! Check DMs to hide 4 bombs.")
            setup_img = utils.upload(bot, draw_setup_instructions())
            bot.send_dm_image(g.p1_name, setup_img, f"Hide bombs for @{g.p2_name}. Reply 4 numbers (1-12).")
            bot.send_dm_image(g.p2_name, setup_img, f"Hide bombs for @{g.p1_name}. Reply 4 numbers (1-12).")
        else: bot.send_message(room_id, f"❌ Need {g.bet} Chips!")
        return True

    if cmd.isdigit() and g and g.state == 'playing':
        if g.mode == 1: # Vs Bot Logic
            if uid != g.p1_id: return False
            idx = int(cmd) - 1
            if not (0 <= idx <= 11) or g.revealed_p1[idx]: return True
            g.revealed_p1[idx] = True; g.touch()
            if g.board_p1[idx] == 1:
                g.lives_p1 -= 1
                blast_url = utils.upload(bot, draw_blast_card(user, av_url))
                bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": blast_url, "text": "BOOM!"})
                if g.lives_p1 <= 0:
                    bot.send_message(room_id, f"💀 **GAME OVER!** Behtar koshish karein.")
                    with game_lock: del games[room_id]; return True
            else:
                bot.send_message(room_id, f"🍪 Found a cookie!")
                # Win Check: Bot mode win if all 8 cookies found
                found = sum(1 for i in range(12) if g.revealed_p1[i] and g.board_p1[i] == 0)
                if found == 8:
                    reward, pts = 2000, 100
                    db.add_game_result(uid, user, "mines", reward, True, pts)
                    url = utils.upload(bot, draw_winner_card(user, reward, pts, av_url))
                    bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": url, "text": "Winner!"})
                    with game_lock: del games[room_id]; return True
        else: # PvP Logic
            is_p1 = (g.turn == 'P1'); curr_uid = g.p1_id if is_p1 else g.p2_id
            if uid != curr_uid: return False
            idx = int(cmd) - 1
            if not (0 <= idx <= 11) or (g.revealed_p1[idx] if is_p1 else g.revealed_p2[idx]): return True
            if is_p1: g.revealed_p1[idx] = True
            else: g.revealed_p2[idx] = True
            g.touch(); target_board = g.board_p1 if is_p1 else g.board_p2
            if target_board[idx] == 1:
                if is_p1: g.lives_p1 -= 1
                else: g.lives_p2 -= 1
                blast_url = utils.upload(bot, draw_blast_card(user, av_url))
                bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": blast_url, "text": "BOOM!"})
                if (is_p1 and g.lives_p1 <= 0) or (not is_p1 and g.lives_p2 <= 0):
                    winner_id = g.p2_id if is_p1 else g.p1_id
                    winner_name = g.p2_name if is_p1 else g.p1_name
                    winner_av = g.p2_av if is_p1 else g.p1_av
                    reward, pts = g.bet * 2, 50
                    db.add_game_result(winner_id, winner_name, "mines", reward, True, pts)
                    url = utils.upload(bot, draw_winner_card(winner_name, reward, pts, winner_av))
                    bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": url, "text": "Winner!"})
                    threading.Thread(target=lambda: (time.sleep(3), bot.send_json({"handler": "kickuser", "roomid": int(room_id), "to": int(uid)}))).start()
                    with game_lock: del games[room_id]; return True
            else: bot.send_message(room_id, f"🍪 found a cookie!")
            g.turn = 'P2' if is_p1 else 'P1'

        url = utils.upload(bot, draw_grid_board(g))
        bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": url, "text": "Next"})
        return True

    if cmd == "stop" and g and (uid == g.p1_id or user.lower() == "yasin"):
        if g.mode == 2:
            db.update_balance(g.p1_id, g.p1_name, g.bet, 0)
            if g.p2_id: db.update_balance(g.p2_id, g.p2_name, g.bet, 0)
        bot.send_message(room_id, "🛑 Game stopped and bet refunded.")
        with game_lock: del games[room_id]
        return True
    return False

def cleanup_loop():
    while True:
        time.sleep(30); now = time.time(); to_del = []
        with game_lock:
            for rid, g in list(games.items()):
                if now - g.last_interaction > 120:
                    if g.mode == 2:
                        db.update_balance(g.p1_id, g.p1_name, g.bet, 0)
                        if g.p2_id: db.update_balance(g.p2_id, g.p2_name, g.bet, 0)
                    to_del.append(rid)
            for rid in to_del: del games[rid]
