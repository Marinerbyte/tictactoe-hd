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

def setup(bot_ref):
    global BOT_INSTANCE
    BOT_INSTANCE = bot_ref
    print("[CookieMines] Ultra Premium 3D Loaded.")

# --- FONT STYLE HELPER ---
def to_small_caps(text):
    normal = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    small  = "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ"
    trans = str.maketrans(normal, small)
    return text.translate(trans)

# ==========================================
# 🕒 AUTO-CLEANUP (120 SECONDS)
# ==========================================
def game_cleanup_loop():
    while True:
        time.sleep(10); now = time.time(); to_remove = []
        with game_lock:
            for rid, g in games.items():
                if now - g.last_interaction > 120: 
                    to_remove.append(rid)
        
        for rid in to_remove:
            if BOT_INSTANCE:
                try: BOT_INSTANCE.send_message(rid, to_small_caps("⌛ Game Expired! Inactivity timeout (120s)."))
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
# 🎨 PREMIUM GRAPHICS SECTION
# ==========================================

def draw_winner_pro(username, avatar_url, score):
    """Trophy ke andar player ki DP wala card"""
    W, H = 500, 500
    img = utils.create_canvas(W, H, (20, 10, 30))
    d = ImageDraw.Draw(img)
    # Gold Neon Frame
    d.rounded_rectangle([15, 15, W-15, H-15], radius=30, outline="#FFD700", width=4)
    # Trophy
    trophy = utils.get_sticker("win", size=300)
    if trophy:
        img.paste(trophy, (W//2 - 150, 40), trophy)
        # DP inside Trophy
        user_dp = utils.get_image(avatar_url)
        if user_dp:
            user_dp = utils.circle_crop(user_dp, size=110)
            img.paste(user_dp, (W//2 - 55, 105), user_dp)
            d.ellipse([W//2-57, 103, W//2+57, 217], outline="white", width=3)
    
    utils.write_text(d, (W//2, 360), to_small_caps(username), size=40, align="center", col="white")
    utils.write_text(d, (W//2, 420), to_small_caps("champion found"), size=30, align="center", col="#FFD700")
    return img

def draw_move_pro(username, avatar_url, item_type="cookie", lives=None):
    """Cookie/Bomb card with Player DP"""
    W, H = 500, 400
    bg = (25, 40, 30) if item_type == "cookie" else (50, 10, 10)
    img = utils.create_canvas(W, H, bg)
    d = ImageDraw.Draw(img)
    
    accent = "#00FF00" if item_type == "cookie" else "#FF0000"
    d.rounded_rectangle([15, 15, W-15, H-15], radius=25, outline=accent, width=3)

    # Item Emoji
    item_img = utils.get_emoji("🍪" if item_type == "cookie" else "💣", size=200)
    if item_img:
        img.paste(item_img, (W//2 - 100, 40), item_img)

    # Player DP on top of item
    user_dp = utils.get_image(avatar_url)
    if user_dp:
        user_dp = utils.circle_crop(user_dp, size=90)
        img.paste(user_dp, (W//2 + 20, 150), user_dp)
        d.ellipse([W//2 + 18, 148, W//2 + 112, 242], outline="white", width=3)

    msg = f"@{username} found a cookie!" if item_type == "cookie" else f"BOOM! @{username} hit a bomb!"
    utils.write_text(d, (W//2, 320), to_small_caps(msg), size=22, align="center", col="white")
    if lives is not None:
        utils.write_text(d, (W//2, 360), f"LIVES: {'❤️'*lives}", size=18, align="center")
    return img

def draw_3d_button(d, x, y, w, h, color, outline, text=None, text_col="white", press=False):
    shadow = (max(0, color[0]-30), max(0, color[1]-30), max(0, color[2]-30))
    if not press:
        d.rounded_rectangle([x, y+4, x+w, y+h+4], radius=10, fill=shadow)
        d.rounded_rectangle([x, y, x+w, y+h], radius=10, fill=color, outline=outline, width=1)
        if text: utils.write_text(d, (x+w//2, y+h//2), text, size=24, align="center", col=text_col, shadow=True)
    else:
        d.rounded_rectangle([x, y+4, x+w, y+h+4], radius=10, fill=color, outline=outline, width=2)
        if text: utils.write_text(d, (x+w//2, y+h//2 + 4), text, size=24, align="center", col=text_col)

def draw_grid_board(game):
    """Main Game Grid"""
    W, H = 500, 500
    img = utils.create_canvas(W, H, color=(30, 32, 40)) 
    d = ImageDraw.Draw(img)
    
    # Simple Header
    p1_active = (game.turn == 'P1')
    c1 = (50, 80, 50) if p1_active else (40, 40, 45)
    d.rounded_rectangle([10, 10, 180, 60], radius=10, fill=c1, outline="#555")
    utils.write_text(d, (95, 20), f"@{game.p1_name[:7]}", size=16, align="center")
    utils.write_text(d, (95, 40), "❤️" * game.lives_p1, size=14, align="center")

    p2_active = (game.turn == 'P2')
    c2 = (50, 80, 50) if p2_active else (40, 40, 45)
    d.rounded_rectangle([310, 10, 490, 60], radius=10, fill=c2, outline="#555")
    utils.write_text(d, (400, 20), f"@{game.p2_name[:7]}", size=16, align="center")
    utils.write_text(d, (400, 40), "❤️" * game.lives_p2, size=14, align="center")

    # 6x2 or 4x3 Grid (Using 12 boxes)
    start_x, start_y, box_sz, gap = 55, 90, 85, 15
    for i in range(12):
        row, col = i // 4, i % 4
        x, y = start_x + (col * (box_sz + gap)), start_y + (row * (box_sz + gap))
        if not (game.revealed_p1[i] or game.revealed_p2[i]):
            draw_3d_button(d, x, y, box_sz, box_sz, (60, 70, 100), "#8899AA", str(i+1))
        else:
            is_bomb = (game.board_p1[i] == 1 or game.board_p2[i] == 1)
            fill = (180, 40, 40) if is_bomb else (40, 140, 60)
            d.rounded_rectangle([x, y, x+box_sz, y+box_sz], radius=10, fill=fill)
            icon = "💣" if is_bomb else "🍪"
            item = utils.get_emoji(icon, size=50)
            if item: img.paste(item, (x+17, y+17), item)

    utils.write_text(d, (W//2, 460), to_small_caps(f"turn: {game.p1_name if p1_active else game.p2_name}"), size=20, align="center", col="#FFD700")
    return img

# ==========================================
# ⚙️ LOGIC
# ==========================================
class MinesGame:
    def __init__(self, room_id, p1_id, p1_name, p1_av):
        self.room_id = room_id; self.p1_id = p1_id; self.p1_name = p1_name; self.p1_av = p1_av
        self.p2_id = None; self.p2_name = None; self.p2_av = None
        self.state = 'waiting_join'; self.bet = 500
        self.board_p1 = [0]*12; self.board_p2 = [0]*12
        self.revealed_p1 = [False]*12; self.revealed_p2 = [False]*12
        self.lives_p1 = 3; self.lives_p2 = 3
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
        bot.send_message(room_id, to_small_caps(f"💣 Mines lobby! Bet: {amt}. Type !join to play."))
        return True

    if cmd == "join":
        with game_lock:
            g = games.get(room_id)
            if not g or g.state != 'waiting_join' or str(g.p1_id) == str(uid): return False
            g.p2_id, g.p2_name, g.p2_av = uid, user, av_url
            if g.bet > 0: add_game_result(uid, user, "mines", -g.bet, False)
            g.state = 'setup_phase'; g.touch()
            setup_pending[str(g.p1_id)] = room_id; setup_pending[str(g.p2_id)] = room_id
        bot.send_message(room_id, to_small_caps("✅ match found! check DM to hide your bombs."))
        from mines import draw_setup_board
        link = utils.upload(bot, draw_setup_board())
        bot.send_dm_image(g.p1_name, link, "Reply with 4 numbers (1-12) to hide bombs.")
        bot.send_dm_image(g.p2_name, link, "Reply with 4 numbers (1-12) to hide bombs.")
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
                    bot.send_dm(user, "Bombs placed! Go back to the room.")
                    if g.p1_ready and g.p2_ready:
                        g.state = 'playing'; del setup_pending[str(g.p1_id)]; del setup_pending[str(g.p2_id)]
                        bot.send_message(rid, to_small_caps("🔥 battle begins!"))
                        task_link = utils.upload(bot, draw_grid_board(g))
                        bot.send_json({"handler": "chatroommessage", "roomid": rid, "type": "image", "url": task_link, "text": "START"})
            return True

    with game_lock:
        g = games.get(room_id)
        if not g or g.state != 'playing': return False
        if cmd.isdigit() and 1 <= int(cmd) <= 12:
            idx = int(cmd)-1; is_p1 = (g.turn == 'P1')
            if (is_p1 and str(uid)!=str(g.p1_id)) or (not is_p1 and str(uid)!=str(g.p2_id)): return False
            
            g.touch(); tgt_rev = g.revealed_p2 if is_p1 else g.revealed_p1
            if tgt_rev[idx]: return True
            
            tgt_rev[idx] = True; hit = ((g.board_p2 if is_p1 else g.board_p1)[idx] == 1)
            p_name = user; p_av = av_url
            
            if hit:
                if is_p1: g.lives_p1 -= 1
                else: g.lives_p2 -= 1
                curr_lives = g.lives_p1 if is_p1 else g.lives_p2
                link = utils.upload(bot, draw_move_pro(p_name, p_av, "bomb", curr_lives))
                bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "BOOM"})
            else:
                link = utils.upload(bot, draw_move_pro(p_name, p_av, "cookie"))
                bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "COOKIE"})

            winner_uid = None
            if g.lives_p1 <= 0: winner_uid, win_name, win_av, loser_id = g.p2_id, g.p2_name, g.p2_av, g.p1_id
            elif g.lives_p2 <= 0: winner_uid, win_name, win_av, loser_id = g.p1_id, g.p1_name, g.p1_av, g.p2_id
            
            if winner_uid:
                rew = g.bet*2; add_game_result(winner_uid, win_name, "mines", rew, True)
                w_link = utils.upload(bot, draw_winner_pro(win_name, win_av, rew))
                bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": w_link, "text": "WIN"})
                
                # --- FIXED KICK ---
                bot.send_json({"handler": "kickuser", "id": uuid.uuid4().hex, "roomid": int(room_id), "to": int(loser_id)})
                del games[room_id]; return True
            
            if not hit: g.turn = 'P2' if is_p1 else 'P1'
            u_link = utils.upload(bot, draw_grid_board(g))
            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": u_link, "text": "TURN"})
            return True
    return False
