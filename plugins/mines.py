import time
import random
import threading
import sys
import os
import uuid
import requests
import io
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

# --- FONT STYLE ---
def to_small_caps(text):
    normal = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    small  = "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ"
    trans = str.maketrans(normal, small)
    return text.translate(trans)

def setup(bot_ref):
    global BOT_INSTANCE
    BOT_INSTANCE = bot_ref
    print("[CookieMines] Final Heavy & Complete Engine Loaded.")

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
# 🖌️ AVATAR & EFFECTS ENGINE
# ==========================================

def get_robust_avatar(url):
    """Howdies CDN se DP download karne ka solid tareeka"""
    if not url: return None
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            return Image.open(io.BytesIO(r.content)).convert("RGBA")
    except: return None

def local_circle_crop(img, size):
    if not img: return None
    try:
        img = img.resize((size, size), Image.Resampling.LANCZOS)
        mask = Image.new('L', (size, size), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, size, size), fill=255)
        out = Image.new('RGBA', (size, size), (0,0,0,0))
        out.paste(img, (0,0), mask)
        return out
    except: return None

def apply_burn_effect(img, intensity=180):
    smoke = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(smoke)
    W, H = img.size
    for _ in range(12):
        x, y = random.randint(0, W), random.randint(0, H)
        r = random.randint(10, 25)
        d.ellipse([x-r, y-r, x+r, y+r], fill=(0, 0, 0, intensity))
    smoke = smoke.filter(ImageFilter.GaussianBlur(8))
    return Image.alpha_composite(img, smoke)

def apply_glow_effect(img):
    glow = Image.new("RGBA", img.size, (255, 215, 0, 0))
    d = ImageDraw.Draw(glow)
    d.ellipse([5, 5, img.size[0]-5, img.size[1]-5], fill=(255, 215, 0, 60))
    glow = glow.filter(ImageFilter.GaussianBlur(10))
    return Image.alpha_composite(img, glow)

# ==========================================
# 🎨 RENDERING FUNCTIONS
# ==========================================

def draw_3d_box(d, x, y, size, text):
    radius = 15
    d.rounded_rectangle([x, y+6, x+size, y+size+6], radius=radius, fill=(20, 30, 50))
    d.rounded_rectangle([x, y, x+size, y+size], radius=radius, fill=(60, 90, 160), outline="#8899AA", width=1)
    d.rounded_rectangle([x+5, y+5, x+size-5, y+size//2.3], radius=12, fill=(255, 255, 255, 40))
    utils.write_text(d, (x+size//2, y+size//2), text, size=30, align="center", shadow=True)

def draw_grid_board(game):
    W, H = 500, 600 
    img = utils.create_canvas(W, H, color=(15, 15, 20)) 
    d = ImageDraw.Draw(img)
    is_p1 = (game.turn == 'P1')
    curr_name = game.p1_name if is_p1 else game.p2_name
    curr_av = game.p1_av if is_p1 else game.p2_av
    curr_lives = game.lives_p1 if is_p1 else game.lives_p2

    d.rounded_rectangle([20, 20, 480, 130], radius=25, fill=(45, 55, 85), outline="#00FFFF", width=3)
    p_img = get_robust_avatar(curr_av)
    if p_img:
        p_img = local_circle_crop(p_img, size=90)
        img.paste(p_img, (40, 40), p_img)
        d.ellipse([38, 38, 132, 132], outline="white", width=3)
    utils.write_text(d, (150, 45), to_small_caps(curr_name), size=26, align="left", col="white")
    utils.write_text(d, (150, 85), f"LIVES: {'❤️'*curr_lives}", size=20, align="left")

    start_x, start_y, box_sz, gap = 55, 170, 85, 15
    for i in range(12):
        row, col = i // 4, i % 4
        x, y = start_x + (col * (box_sz + gap)), start_y + (row * (box_sz + gap))
        rev_p1, rev_p2 = game.revealed_p1[i], game.revealed_p2[i]
        if not (rev_p1 or rev_p2):
            draw_3d_box(d, x, y, box_sz, str(i+1))
        else:
            is_bomb = (game.board_p1[i] == 1 or game.board_p2[i] == 1)
            box_col = (160, 40, 40) if is_bomb else (40, 160, 80)
            d.rounded_rectangle([x, y, x+box_sz, y+box_sz], radius=15, fill=box_col, outline="white", width=2)
            item = utils.get_emoji("💣" if is_bomb else "🍪", size=55)
            if item: img.paste(item, (x+15, y+5), item)
            u_dp = get_robust_avatar(game.p1_av if rev_p1 else game.p2_av)
            if u_dp:
                u_dp = local_circle_crop(u_dp, size=55)
                if is_bomb: u_dp = ImageOps.grayscale(u_dp).convert("RGBA")
                img.paste(u_dp, (x+15, y+25), u_dp)
                d.ellipse([x+15, y+25, x+70, y+80], outline="white", width=2)
            # Effects
            box_area = img.crop((x, y, x+box_sz, y+box_sz))
            if is_bomb: box_area = apply_burn_effect(box_area)
            else: box_area = apply_glow_effect(box_area)
            img.paste(box_area, (x, y))
    return img

def draw_blast_card(name, lives, avatar_url=None):
    W, H = 512, 512
    img = utils.get_gradient(W, H, (50, 0, 0), (20, 0, 0)).convert("RGBA")
    d = ImageDraw.Draw(img)
    boom = utils.get_emoji("💥", size=380)
    if boom: img.paste(boom, (W//2-190, H//2-200), boom)
    if avatar_url:
        u_dp = get_robust_avatar(avatar_url)
        if u_dp:
            u_dp = local_circle_crop(u_dp, size=210)
            u_dp = ImageOps.grayscale(u_dp).convert("RGBA")
            u_dp = apply_burn_effect(u_dp, intensity=220)
            img.paste(u_dp, (W//2-105, H//2-105), u_dp)
            d.ellipse([W//2-107, H//2-107, W//2+107, H//2+107], outline="red", width=5)
    utils.write_text(d, (W//2, 430), to_small_caps(f"@{name} hit a mine"), size=35, align="center", col="white", shadow=True)
    return img

def draw_winner_card(name, reward, avatar_url=None):
    W, H = 512, 512
    img = utils.create_canvas(W, H, (10, 10, 20)); d = ImageDraw.Draw(img)
    d.rounded_rectangle([15, 15, W-15, H-15], radius=35, outline="#FFD700", width=6)
    trophy = utils.get_sticker("win", size=320)
    if trophy:
        img.paste(trophy, (W//2-160, 40), trophy)
        u_dp = get_robust_avatar(avatar_url)
        if u_dp:
            u_dp = local_circle_crop(u_dp, size=115)
            img.paste(u_dp, (W//2-57, 100), u_dp)
    utils.write_text(d, (W//2, 390), to_small_caps(name), size=42, align="center", col="#FFD700")
    utils.write_text(d, (W//2, 450), f"WINNER: {reward} COINS", size=26, align="center", col="#00FF00")
    return img

def draw_setup_board():
    W, H = 500, 500; img = utils.create_canvas(W, H, (25, 30, 45)); d = ImageDraw.Draw(img)
    start_x, start_y, bx_w, bx_h, gap = 55, 110, 85, 65, 15
    for i in range(12):
        row, col = i // 4, i % 4
        x, y = start_x + (col * (bx_w + gap)), start_y + (row * (bx_h + gap))
        d.rounded_rectangle([x, y, x+bx_w, y+bx_h], radius=10, fill=(50, 60, 90), outline="#DDD")
        utils.write_text(d, (x+bx_w//2, y+bx_h//2), str(i+1), size=24, align="center", col="white")
    utils.write_text(d, (W//2, 50), to_small_caps("hide your bombs"), size=35, align="center", col="#FEE75C", shadow=True)
    return img

# ==========================================
# ⚙️ LOGIC HANDLER
# ==========================================
class MinesGame:
    def __init__(self, room_id, p1_id, p1_name, p1_av):
        self.room_id = room_id; self.p1_id = p1_id; self.p1_name = p1_name; self.p1_av = p1_av
        self.p2_id = self.p2_name = self.p2_av = None
        self.state = 'waiting_join'; self.bet = 500
        self.board_p1 = [0]*12; self.board_p2 = [0]*12
        self.revealed_p1 = [False]*12; self.revealed_p2 = [False]*12
        self.lives_p1 = self.lives_p2 = 3
        self.p1_ready = self.p2_ready = False
        self.turn = 'P1'; self.last_interaction = time.time()
    def touch(self): self.last_interaction = time.time()

def handle_command(bot, command, room_id, user, args, data):
    global games, setup_pending
    uid = str(data.get('userid', user)); av_id = data.get("avatar")
    av_url = f"https://cdn.howdies.app/avatar?image={av_id}" if av_id else None
    cmd = command.lower().strip()

    if cmd == "mines":
        amt = int(args[0]) if args and args[0].isdigit() else 500
        with game_lock:
            if room_id in games: return True
            games[room_id] = MinesGame(room_id, uid, user, av_url)
            games[room_id].bet = amt
            if amt > 0: add_game_result(uid, user, "mines", -amt, False)
        bot.send_message(room_id, to_small_caps(f"💣 Mines lobby! @{user} wants to battle. Type !join."))
        return True

    if cmd == "stop" and room_id in games:
        with game_lock:
            if uid == games[room_id].p1_id or user == "yasin":
                del games[room_id]; bot.send_message(room_id, to_small_caps("🛑 game stopped by host."))
        return True

    if cmd == "join":
        with game_lock:
            g = games.get(room_id)
            if not g or g.state != 'waiting_join' or g.p1_id == uid: return False
            g.p2_id, g.p2_name, g.p2_av = uid, user, av_url
            if g.bet > 0: add_game_result(uid, user, "mines", -g.bet, False)
            g.state = 'setup_phase'; g.touch()
            setup_pending[g.p1_id] = room_id; setup_pending[g.p2_id] = room_id
        bot.send_message(room_id, to_small_caps("✅ match found! check DM to set bombs."))
        link = utils.upload(bot, draw_setup_board())
        instr = "Reply with 4 unique numbers (1-12) to hide your bombs. Example: 1 5 8 11"
        bot.send_dm_image(g.p1_name, link, instr)
        bot.send_dm(g.p1_name, instr) # Text instruction backup
        bot.send_dm_image(g.p2_name, link, instr)
        bot.send_dm(g.p2_name, instr)
        return True

    if uid in setup_pending:
        nums = [int(s) for s in command.replace(',', ' ').split() if s.isdigit()]
        if len(nums) == 4 and all(1<=n<=12 for n in nums):
            rid = setup_pending[uid]
            with game_lock:
                g = games.get(rid)
                if g:
                    g.touch()
                    if uid == g.p1_id:
                        for i in [n-1 for n in nums]: g.board_p1[i] = 1
                        g.p1_ready = True
                    else:
                        for i in [n-1 for n in nums]: g.board_p2[i] = 1
                        g.p2_ready = True
                    bot.send_dm(user, "Bombs placed! Go back to the room.")
                    if g.p1_ready and g.p2_ready:
                        g.state = 'playing'; del setup_pending[g.p1_id]; del setup_pending[g.p2_id]
                        bot.send_message(rid, to_small_caps("🔥 battle is live!"))
                        link = utils.upload(bot, draw_grid_board(g))
                        bot.send_json({"handler": "chatroommessage", "roomid": rid, "type": "image", "url": link, "text": "START"})
            return True

    with game_lock:
        g = games.get(room_id)
        if not g or g.state != 'playing': return False
        if cmd.isdigit() and 1 <= int(cmd) <= 12:
            idx = int(cmd)-1; is_p1 = (g.turn == 'P1')
            if (is_p1 and uid!=g.p1_id) or (not is_p1 and uid!=g.p2_id): return False
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
