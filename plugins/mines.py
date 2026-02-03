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

# --- FONT STYLE ---
def to_small_caps(text):
    normal = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    small  = "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ"
    trans = str.maketrans(normal, small)
    return text.translate(trans)

def setup(bot_ref):
    global BOT_INSTANCE
    BOT_INSTANCE = bot_ref
    print("[CookieMines] Visual Vibe Engine Loaded.")

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
                try: BOT_INSTANCE.send_message(rid, to_small_caps("⌛ Game Expired! Inactivity timeout."))
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
# 🖌️ VIBE EFFECTS HELPERS
# ==========================================

def apply_burn_effect(img):
    """Adds a black smoke/burned overlay to the image"""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    W, H = img.size
    # Drawing random black smoke particles
    for _ in range(10):
        x, y = random.randint(0, W), random.randint(0, H)
        r = random.randint(10, 30)
        d.ellipse([x-r, y-r, x+r, y+r], fill=(0, 0, 0, 160))
    overlay = overlay.filter(ImageFilter.GaussianBlur(10))
    return Image.alpha_composite(img, overlay)

# ==========================================
# 🎨 DYNAMIC BOARD RENDERER
# ==========================================

def draw_grid_board(game):
    """Main Game Board with DP + Item + Effects"""
    W, H = 500, 520
    img = utils.create_canvas(W, H, color=(20, 20, 30)) 
    d = ImageDraw.Draw(img)
    
    # 1. Header (Scores)
    for i, (name, lives, active) in enumerate([(game.p1_name, game.lives_p1, game.turn=='P1'), 
                                               (game.p2_name, game.lives_p2, game.turn=='P2')]):
        x_off = 10 if i == 0 else 310
        border = "#00FF00" if active else "#555"
        d.rounded_rectangle([x_off, 10, x_off+180, 75], radius=12, fill=(40, 40, 55), outline=border, width=2)
        utils.write_text(d, (x_off+90, 25), f"@{name[:8]}", size=16, align="center")
        utils.write_text(d, (x_off+90, 50), "❤️" * lives, size=14, align="center")

    # 2. Grid (12 boxes)
    start_x, start_y, box_sz, gap = 55, 100, 85, 15
    for i in range(12):
        row, col = i // 4, i % 4
        x, y = start_x + (col * (box_sz + gap)), start_y + (row * (box_sz + gap))
        
        rev_p1, rev_p2 = game.revealed_p1[i], game.revealed_p2[i]
        
        if not (rev_p1 or rev_p2):
            # Closed Box 3D
            shadow = (30, 40, 60)
            d.rounded_rectangle([x, y+4, x+box_sz, y+box_sz+4], radius=12, fill=shadow)
            d.rounded_rectangle([x, y, x+box_sz, y+box_sz], radius=12, fill=(60, 75, 110), outline="#8899AA", width=1)
            utils.write_text(d, (x+box_sz//2, y+box_sz//2), str(i+1), size=26, align="center")
        else:
            # Open Box Logic
            is_bomb = (game.board_p1[i] == 1 or game.board_p2[i] == 1)
            box_fill = (180, 40, 40) if is_bomb else (40, 150, 70)
            d.rounded_rectangle([x, y, x+box_sz, y+box_sz], radius=12, fill=box_fill, outline="white", width=2)
            
            # --- Draw Item (Cookie/Bomb) ---
            item_emoji = "💣" if is_bomb else "🍪"
            item_icon = utils.get_emoji(item_emoji, size=50)
            if item_icon:
                # Place item in center
                img.paste(item_icon, (x+17, y+10), item_icon)

            # --- Draw User DP on top ---
            p_av = game.p1_av if rev_p1 else game.p2_av
            user_dp = utils.get_image(p_av)
            if user_dp:
                user_dp = utils.circle_crop(user_dp, size=55)
                if is_bomb:
                    # Apply Dark/Gray filter to DP for bomb vibe
                    user_dp = ImageOps.grayscale(user_dp).convert("RGBA")
                    # Paste with a slight offset to show item behind
                    img.paste(user_dp, (x+15, y+25), user_dp)
                else:
                    img.paste(user_dp, (x+15, y+25), user_dp)
                # DP Border
                d.ellipse([x+15, y+25, x+70, y+80], outline="white", width=2)

            # --- Apply Smoke Effect if Bomb ---
            if is_bomb:
                # Small smoke overlay inside the box
                box_area = img.crop((x, y, x+box_sz, y+box_sz))
                burned = apply_burn_effect(box_area)
                img.paste(burned, (x, y))

    utils.write_text(d, (W//2, 480), to_small_caps(f"turn: {game.p1_name if game.turn=='P1' else game.p2_name}"), size=20, align="center", col="#FFD700")
    return img

def draw_setup_board():
    """Lobby DM Board"""
    W, H = 500, 500
    img = utils.create_canvas(W, H, (25, 25, 30))
    d = ImageDraw.Draw(img)
    start_x, start_y, box_w, box_h, gap = 55, 110, 85, 65, 15
    for i in range(12):
        row, col = i // 4, i % 4
        x, y = start_x + (col * (box_w + gap)), start_y + (row * (box_h + gap))
        d.rounded_rectangle([x, y, x+box_w, y+box_h], radius=10, fill=(40, 50, 70), outline="#AAA")
        utils.write_text(d, (x+box_w//2, y+box_h//2), str(i+1), size=24, align="center", col="white")
    utils.write_text(d, (W//2, 50), to_small_caps("hide your bombs"), size=38, align="center", col="#FEE75C", shadow=True)
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
        self.p1_ready = self.p2_ready = False
        self.turn = 'P1'; self.last_interaction = time.time()
    def touch(self): self.last_interaction = time.time()

def handle_command(bot, command, room_id, user, args, data):
    global games, setup_pending
    uid = data.get('userid', user)
    av_id = data.get("avatar")
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

    if cmd == "join":
        with game_lock:
            g = games.get(room_id)
            if not g or g.state != 'waiting_join' or str(g.p1_id) == str(uid): return False
            g.p2_id, g.p2_name, g.p2_av = uid, user, av_url
            if g.bet > 0: add_game_result(uid, user, "mines", -g.bet, False)
            g.state = 'setup_phase'; g.touch()
            setup_pending[str(g.p1_id)] = room_id; setup_pending[str(g.p2_id)] = room_id
        bot.send_message(room_id, to_small_caps("✅ match found! check DM to set your traps."))
        link = utils.upload(bot, draw_setup_board())
        bot.send_dm_image(g.p1_name, link, "Reply with 4 unique numbers (1-12) to hide bombs.")
        bot.send_dm_image(g.p2_name, link, "Reply with 4 unique numbers (1-12) to hide bombs.")
        return True

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
                    bot.send_dm(user, "Traps set! Battle starting soon...")
                    if g.p1_ready and g.p2_ready:
                        g.state = 'playing'; del setup_pending[str(g.p1_id)]; del setup_pending[str(g.p2_id)]
                        bot.send_message(rid, to_small_caps("🔥 Let the hunt begin!"))
                        link = utils.upload(bot, draw_grid_board(g))
                        bot.send_json({"handler": "chatroommessage", "roomid": rid, "type": "image", "url": link, "text": "START"})
            return True

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
                bot.send_message(room_id, f"💥 **BOOM!** @{user} hit a bomb!")
            else:
                bot.send_message(room_id, f"🍪 **YUM!** @{user} found a cookie!")

            # Check Winner
            win_uid = None
            if g.lives_p1 <= 0: win_uid, win_name, win_av, loser_id = g.p2_id, g.p2_name, g.p2_av, g.p1_id
            elif g.lives_p2 <= 0: win_uid, win_name, win_av, loser_id = g.p1_id, g.p1_name, g.p1_av, g.p2_id
            
            if win_uid:
                from mines import draw_winner_card
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
