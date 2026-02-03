import time
import random
import threading
import sys
import os
import uuid
from PIL import Image, ImageDraw, ImageOps, ImageFilter

# --- IMPORTS ---
try: import utils
except ImportError: print("[Mines] Error: utils.py not found!")

try:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from db import add_game_result
except Exception as e: print(f"DB Import Error: {e}")

# --- GLOBALS ---
games = {}; setup_pending = {}; game_lock = threading.Lock(); BOT_INSTANCE = None

# --- FONT & TEXT STYLE ---
def to_small_caps(text):
    normal = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    small  = "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ"
    trans = str.maketrans(normal, small)
    return text.translate(trans)

def setup(bot_ref):
    global BOT_INSTANCE
    BOT_INSTANCE = bot_ref
    print("[CookieMines] Modern 3D Personal Board Loaded.")

# ==========================================
# 🕒 AUTO-CLEANUP (120 SECONDS)
# ==========================================
def game_cleanup_loop():
    while True:
        time.sleep(10); now = time.time(); to_remove = []
        with game_lock:
            for rid, g in games.items():
                if now - g.last_interaction > 120: to_remove.append(rid)
        for rid in to_remove:
            if BOT_INSTANCE:
                try: BOT_INSTANCE.send_message(rid, to_small_caps("⌛ game expired due to inactivity."))
                except: pass
            with game_lock:
                if rid in games:
                    g = games[rid]
                    if str(g.p1_id) in setup_pending: del setup_pending[str(g.p1_id)]
                    if g.p2_id and str(g.p2_id) in setup_pending: del setup_pending[str(g.p2_id)]
                    del games[rid]

if threading.active_count() < 15: 
    threading.Thread(target=game_cleanup_loop, daemon=True).start()

# ==========================================
# 🖌️ INDEPENDENT IMAGE HELPERS
# ==========================================

def local_circle_crop(img, size):
    try:
        img = img.resize((size, size), Image.Resampling.LANCZOS).convert("RGBA")
        mask = Image.new('L', (size, size), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, size, size), fill=255)
        out = Image.new('RGBA', (size, size), (0,0,0,0))
        out.paste(img, (0,0), mask)
        return out
    except: return img

def apply_glow(img, col=(255, 215, 0, 80)):
    glow = Image.new("RGBA", img.size, (0,0,0,0))
    d = ImageDraw.Draw(glow)
    d.ellipse([5, 5, img.size[0]-5, img.size[1]-5], fill=col)
    glow = glow.filter(ImageFilter.GaussianBlur(10))
    return Image.alpha_composite(img, glow)

# ==========================================
# 🎨 MODERN 3D RENDERING ENGINE
# ==========================================

def draw_3d_box(d, x, y, size, text, color=(60, 100, 200)):
    """Draws a premium 3D numbered box"""
    # Shadow
    d.rounded_rectangle([x, y+6, x+size, y+size+6], radius=15, fill=(20, 30, 50))
    # Main Face
    d.rounded_rectangle([x, y, x+size, y+size], radius=15, fill=color, outline="#8899AA", width=1)
    # Highlight
    d.rounded_rectangle([x+5, y+5, x+size-5, y+size//2], radius=12, fill=(255, 255, 255, 40))
    # Text
    utils.write_text(d, (x+size//2, y+size//2), text, size=30, align="center", shadow=True)

def draw_grid_board(game):
    """Board showing current player's stats and the grid"""
    W, H = 500, 600 # Height increased for better header
    img = utils.create_canvas(W, H, color=(15, 15, 25)) 
    d = ImageDraw.Draw(img)

    # Determine current player
    is_p1 = (game.turn == 'P1')
    curr_name = game.p1_name if is_p1 else game.p2_name
    curr_av = game.p1_av if is_p1 else game.p2_av
    curr_lives = game.lives_p1 if is_p1 else game.lives_p2

    # 1. PREMIUM HEADER (Current Player Only)
    d.rounded_rectangle([20, 20, 480, 120], radius=25, fill=(40, 50, 80), outline="#00FFFF", width=2)
    
    # Draw Player Avatar in Header
    av_img = utils.get_image(curr_av)
    if av_img:
        av_img = local_circle_crop(av_img, size=80)
        img.paste(av_img, (40, 30), av_img)
        d.ellipse([38, 28, 122, 112], outline="white", width=3)
    
    # Player Info
    utils.write_text(d, (140, 40), to_small_caps(curr_name), size=24, align="left", col="white")
    utils.write_text(d, (140, 75), f"LIVES: {'❤️'*curr_lives}", size=18, align="left")
    utils.write_text(d, (440, 55), "YOUR TURN", size=14, align="right", col="#00FFFF")

    # 2. THE GRID (4x3 = 12 Boxes)
    start_x, start_y, box_sz, gap = 55, 160, 85, 15
    for i in range(12):
        row, col = i // 4, i % 4
        x, y = start_x + (col * (box_sz + gap)), start_y + (row * (box_sz + gap))
        
        rev_p1, rev_p2 = game.revealed_p1[i], game.revealed_p2[i]
        
        if not (rev_p1 or rev_p2):
            draw_3d_box(d, x, y, box_sz, str(i+1))
        else:
            # Box is Open
            is_bomb = (game.board_p1[i] == 1 or game.board_p2[i] == 1)
            box_col = (150, 40, 40) if is_bomb else (40, 160, 80)
            d.rounded_rectangle([x, y, x+box_sz, y+box_sz], radius=15, fill=box_col, outline="white", width=2)
            
            # Draw Item (Cookie/Bomb)
            icon = utils.get_emoji("💣" if is_bomb else "🍪", size=50)
            if icon: img.paste(icon, (x+17, y+10), icon)
            
            # Draw Small DP of whoever opened it
            opener_av = game.p1_av if rev_p1 else game.p2_av
            u_dp = utils.get_image(opener_av)
            if u_dp:
                u_dp = local_circle_crop(u_dp, size=50)
                if is_bomb: u_dp = ImageOps.grayscale(u_dp).convert("RGBA")
                img.paste(u_dp, (x+17, y+25), u_dp)
                d.ellipse([x+17, y+25, x+67, y+75], outline="white", width=2)
            
            # Vibe Effects
            box_area = img.crop((x, y, x+box_sz, y+box_sz))
            if not is_bomb: box_area = apply_glow(box_area)
            img.paste(box_area, (x, y))

    utils.write_text(d, (W//2, 570), to_small_caps("type a number to play"), size=16, align="center", col="#888")
    return img

def draw_blast_card(name, lives, avatar_url=None):
    W, H = 512, 512
    img = utils.get_gradient(W, H, (40, 0, 0), (10, 0, 0)).convert("RGBA")
    d = ImageDraw.Draw(img)
    boom = utils.get_emoji("💥", size=350)
    if boom: img.paste(boom, (W//2-175, H//2-200), boom)
    if avatar_url:
        u_dp = utils.get_image(avatar_url)
        if u_dp:
            u_dp = local_circle_crop(u_dp, size=200)
            u_dp = ImageOps.grayscale(u_dp).convert("RGBA")
            img.paste(u_dp, (W//2-100, H//2-100), u_dp)
            d.ellipse([W//2-102, H//2-102, W//2+102, H//2+102], outline="red", width=4)
    utils.write_text(d, (W//2, 420), to_small_caps(f"@{name} blasted"), size=35, align="center", col="white")
    return img

def draw_winner_card(name, reward, avatar_url=None):
    W, H = 512, 512
    img = utils.create_canvas(W, H, (10, 10, 20)); d = ImageDraw.Draw(img)
    trophy = utils.get_sticker("win", size=300)
    if trophy:
        img.paste(trophy, (W//2 - 150, 40), trophy)
        if avatar_url:
            u_dp = utils.get_image(avatar_url)
            if u_dp:
                u_dp = local_circle_crop(u_dp, size=115)
                img.paste(u_dp, (W//2 - 57, 100), u_dp)
    utils.write_text(d, (W//2, 380), to_small_caps(name), size=40, align="center", col="#FFD700")
    utils.write_text(d, (W//2, 440), f"WON {reward} COINS", size=25, align="center", col="#00FF00")
    return img

# ==========================================
# ⚙️ LOGIC & HANDLER
# ==========================================
class MinesGame:
    def __init__(self, room_id, p1_id, p1_name, p1_av):
        self.room_id = room_id; self.p1_id = p1_id; self.p1_name = p1_name; self.p1_av = p1_av
        self.p2_id = self.p2_name = self.p2_av = None
        self.state = 'waiting_join'; self.bet = 500
        self.board_p1 = [0]*12; self.board_p2 = [0]*12
        self.revealed_p1 = [False]*12; self.revealed_p2 = [False]*12
        self.lives_p1 = self.lives_p2 = 3
        self.turn = 'P1'; self.last_interaction = time.time()
    def touch(self): self.last_interaction = time.time()

def handle_command(bot, command, room_id, user, args, data):
    global games, setup_pending
    uid = data.get('userid', user)
    av_id = data.get("avatar")
    av_url = f"https://cdn.howdies.app/avatar?image={av_id}" if av_id else None
    cmd = command.lower().strip()

    # 1. CREATE
    if cmd == "mines":
        amt = int(args[0]) if args and args[0].isdigit() else 500
        with game_lock:
            if room_id in games: return True
            games[room_id] = MinesGame(room_id, uid, user, av_url)
            games[room_id].bet = amt
            if amt > 0: add_game_result(uid, user, "mines", -amt, False)
        bot.send_message(room_id, to_small_caps(f"💣 Mines lobby! @{user} is ready. Type !join."))
        return True

    # 2. JOIN
    if cmd == "join":
        with game_lock:
            g = games.get(room_id)
            if not g or g.state != 'waiting_join' or str(g.p1_id) == str(uid): return False
            g.p2_id, g.p2_name, g.p2_av = uid, user, av_url
            if g.bet > 0: add_game_result(uid, user, "mines", -g.bet, False)
            g.state = 'setup_phase'; g.touch()
            setup_pending[str(g.p1_id)] = room_id; setup_pending[str(g.p2_id)] = room_id
        
        bot.send_message(room_id, to_small_caps("✅ match found! check DM to set traps."))
        # Local import/reference for DM board
        from mines import draw_setup_board
        link = utils.upload(bot, draw_setup_board())
        bot.send_dm_image(g.p1_name, link, "Reply with 4 unique numbers (1-12) to hide bombs.")
        bot.send_dm_image(g.p2_name, link, "Reply with 4 unique numbers (1-12) to hide bombs.")
        return True

    # 3. DM SETUP
    if str(uid) in setup_pending:
        nums = [int(s) for s in command.replace(',', ' ').split() if s.isdigit()]
        if len(nums) == 4 and all(1<=n<=12 for n in nums):
            rid = setup_pending[str(uid)]
            with game_lock:
                g = games.get(rid)
                if g:
                    g.touch()
                    if str(uid) == str(g.p1_id):
                        for i in [n-1 for n in nums]: g.board_p1[i] = 1
                        g.p1_ready = True
                    else:
                        for i in [n-1 for n in nums]: g.board_p2[i] = 1
                        g.p2_ready = True
                    bot.send_dm(user, "Traps set! Wait for opponent.")
                    if g.p1_ready and g.p2_ready:
                        g.state = 'playing'; del setup_pending[str(g.p1_id)]; del setup_pending[str(g.p2_id)]
                        bot.send_message(rid, to_small_caps("🔥 hunting season is open!"))
                        link = utils.upload(bot, draw_grid_board(g))
                        bot.send_json({"handler": "chatroommessage", "roomid": rid, "type": "image", "url": link, "text": "START"})
            return True

    # 4. GAMEPLAY
    with game_lock:
        g = games.get(room_id)
        if not g or g.state != 'playing': return False
        if cmd.isdigit() and 1 <= int(cmd) <= 12:
            idx = int(cmd)-1; is_p1 = (g.turn == 'P1')
            if (is_p1 and str(uid)!=str(g.p1_id)) or (not is_p1 and str(uid)!=str(g.p2_id)): return False
            g.touch()
            if g.revealed_p1[idx] or g.revealed_p2[idx]: return True
            
            if is_p1: g.revealed_p1[idx] = True
            else: g.revealed_p2[idx] = True
            
            hit = ((g.board_p2 if is_p1 else g.board_p1)[idx] == 1)
            
            if hit:
                if is_p1: g.lives_p1 -= 1
                else: g.lives_p2 -= 1
                link = utils.upload(bot, draw_blast_card(user, g.lives_p1 if is_p1 else g.lives_p2, g.p1_av if is_p1 else g.p2_av))
                bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "BOOM"})
            else:
                bot.send_message(room_id, to_small_caps(f"😋 @{user} found a cookie!"))

            # Winner Check
            win_uid = None
            if g.lives_p1 <= 0: win_uid, win_name, win_av, loser_id = g.p2_id, g.p2_name, g.p2_av, g.p1_id
            elif g.lives_p2 <= 0: win_uid, win_name, win_av, loser_id = g.p1_id, g.p1_name, g.p1_av, g.p2_id
            
            if win_uid:
                rew = g.bet*2; add_game_result(win_uid, win_name, "mines", rew, True)
                w_link = utils.upload(bot, draw_winner_card(win_name, rew, win_av))
                bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": w_link, "text": "WIN"})
                bot.send_json({"handler": "kickuser", "id": uuid.uuid4().hex, "roomid": int(room_id), "to": int(loser_id)})
                del games[room_id]; return True
            
            if not hit: g.turn = 'P2' if is_p1 else 'P1'
            u_link = utils.upload(bot, draw_grid_board(g))
            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": u_link, "text": "TURN"})
            return True
    return False
