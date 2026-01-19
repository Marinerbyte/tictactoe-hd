import time
import random
import threading
import sys
import os
from PIL import ImageDraw

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
    print("[CookieMines] 4-Bomb Edition Loaded.")

# --- CLEANUP ---
def game_cleanup_loop():
    while True:
        time.sleep(10); now = time.time(); to_remove = []
        with game_lock:
            for rid, g in games.items():
                if now - g.last_interaction > 90: to_remove.append(rid)
        for rid in to_remove:
            if BOT_INSTANCE:
                try: BOT_INSTANCE.send_message(rid, "⌛ Timeout! Game cleaned.")
                except: pass
            with game_lock:
                if rid in games:
                    g = games[rid]
                    if str(g.p1_id) in setup_pending: del setup_pending[str(g.p1_id)]
                    if g.p2_id and str(g.p2_id) in setup_pending: del setup_pending[str(g.p2_id)]
                    del games[rid]

if threading.active_count() < 10: threading.Thread(target=game_cleanup_loop, daemon=True).start()

# ==========================================
# 🎨 VISUALS (Compact & High Quality)
# ==========================================

def draw_enhanced_board(board_config, revealed_list, lives_p1, lives_p2, current_turn_name, p1_name, p2_name, is_game_over=False):
    # SIZE ADJUSTED: 500x550 (Compact like TicTacToe)
    W, H = 500, 550
    img = utils.create_canvas(W, H, color=(35, 39, 42)) # Discord Dark
    d = ImageDraw.Draw(img)
    
    # --- HEADER (Compact) ---
    # P1 Box
    active_col = "#00FF00" if not is_game_over else "#555"
    p1_border = active_col if current_turn_name == p1_name else "#444"
    
    d.rounded_rectangle([20, 20, 180, 80], radius=10, fill=(44, 47, 51), outline=p1_border, width=3)
    utils.write_text(d, (100, 35), f"@{p1_name[:8]}", size=18, align="center", col="#FFF")
    utils.write_text(d, (100, 60), "❤️" * lives_p1, size=16, align="center")

    # P2 Box
    p2_border = active_col if current_turn_name == p2_name else "#444"
    d.rounded_rectangle([320, 20, 480, 80], radius=10, fill=(44, 47, 51), outline=p2_border, width=3)
    utils.write_text(d, (400, 35), f"@{p2_name[:8]}", size=18, align="center", col="#FFF")
    utils.write_text(d, (400, 60), "❤️" * lives_p2, size=16, align="center")

    # VS Badge
    d.ellipse([225, 30, 275, 80], fill="#FFD700", outline="white", width=2)
    utils.write_text(d, (250, 55), "VS", size=20, align="center", col="black", shadow=False)

    # Status Text
    msg = f"Turn: {current_turn_name}" if not is_game_over else "GAME OVER"
    col = "#FFD700" if not is_game_over else "#FF4444"
    utils.write_text(d, (W//2, 100), msg, size=20, align="center", col=col, shadow=True)

    # --- THE GRID (4x3) ---
    start_x, start_y = 50, 130
    box_w, box_h = 90, 90
    gap = 15
    
    cookie = utils.get_emoji("🍪", size=60)
    bomb = utils.get_emoji("💥", size=60)
    lock = utils.get_emoji("🔒", size=40)

    for i in range(12):
        row = i // 4; col = i % 4
        x = start_x + (col * (box_w + gap))
        y = start_y + (row * (box_h + gap))
        
        if not revealed_list[i]:
            # HIDDEN (Blue/Grey Theme)
            d.rounded_rectangle([x, y, x+box_w, y+box_h], radius=12, fill=(88, 101, 242), outline="white", width=2)
            d.rounded_rectangle([x+2, y+2, x+box_w-2, y+box_h-5], radius=12, fill=(60, 70, 180)) # 3D depth
            
            # Number or Lock
            utils.write_text(d, (x+45, y+45), str(i+1), size=28, align="center", col="white", shadow=True)
        else:
            # REVEALED
            if board_config[i] == 1:
                # BOMB
                d.rounded_rectangle([x, y, x+box_w, y+box_h], radius=12, fill="#ED4245", outline="#500", width=2)
                if bomb: img.paste(bomb, (x+15, y+15), bomb)
            else:
                # SAFE
                d.rounded_rectangle([x, y, x+box_w, y+box_h], radius=12, fill="#57F287", outline="#050", width=2)
                if cookie: img.paste(cookie, (x+15, y+15), cookie)

    # Footer (Simple)
    utils.write_text(d, (W//2, 530), "Type a number (1-12) to Eat", size=14, col="#888", align="center")
    return img

def draw_setup_board():
    W, H = 500, 300
    img = utils.create_canvas(W, H, (30,30,35))
    d = ImageDraw.Draw(img)
    utils.write_text(d, (W//2, 50), "🔒 SECRET SETUP", size=35, align="center", col="#FEE75C", shadow=True)
    utils.write_text(d, (W//2, 120), "Hide 4 Bombs in DM", size=25, align="center", col="white")
    
    # Example Box
    d.rounded_rectangle([100, 160, 400, 240], radius=10, fill=(40,40,50), outline="#AAA", width=2)
    utils.write_text(d, (250, 200), "Example: 1 5 9 12", size=25, align="center", col="#57F287")
    return img

def draw_result_card(name, lives, type="blast", avatar=None):
    W, H = 500, 350
    color = (100, 20, 20) if type == "blast" else (20, 80, 20)
    img = utils.create_canvas(W, H, color)
    d = ImageDraw.Draw(img)
    
    icon = utils.get_emoji("💥", size=120) if type == "blast" else utils.get_emoji("🏆", size=120)
    if icon: img.paste(icon, (W//2 - 60, 40), icon)
    
    title = "BOOM!" if type == "blast" else "VICTORY!"
    col = "#FF4444" if type == "blast" else "#FEE75C"
    
    utils.write_text(d, (W//2, 190), title, size=50, align="center", col=col, shadow=True)
    utils.write_text(d, (W//2, 250), f"@{name}", size=30, align="center", col="white")
    
    if type == "blast":
        utils.write_text(d, (W//2, 290), f"Lives: {lives}", size=20, align="center", col="#FAA")
    
    return img

# ==========================================
# ⚙️ LOGIC
# ==========================================
class MinesGame:
    def __init__(self, room_id, p1_id, p1_name):
        self.room_id = room_id; self.p1_id = p1_id; self.p1_name = p1_name
        self.p2_id = None; self.p2_name = None; self.p1_avatar = None; self.p2_avatar = None
        self.state = 'waiting_join'; self.bet = 500 # Default Bet 500
        self.board_p1 = [0]*12; self.board_p2 = [0]*12
        self.revealed_p1 = [False]*12; self.revealed_p2 = [False]*12
        self.lives_p1 = 3; self.lives_p2 = 3
        self.p1_ready = False; self.p2_ready = False
        self.turn = 'P1'; self.last_interaction = time.time()
    def touch(self): self.last_interaction = time.time()

def handle_command(bot, command, room_id, user, args, data):
    global games, setup_pending
    uid = data.get('userid', user)
    av_file = data.get("avatar")
    av_url = f"https://cdn.howdies.app/avatar?image={av_file}" if av_file else None
    cmd = command.lower().strip()

    # 1. NEW GAME
    if cmd == "mines":
        # Default 500 if not provided
        amt = int(args[0]) if args and args[0].isdigit() else 500
        
        with game_lock:
            if room_id in games: return True
            g = MinesGame(room_id, uid, user); g.bet = amt; g.p1_avatar = av_url
            if amt > 0: add_game_result(uid, user, "mines", -amt, False)
            games[room_id] = g
        bot.send_message(room_id, f"💣 **Mines!** Bet: {amt}\nWaiting for Player 2 (`!join`)")
        return True

    # 2. STOP
    if cmd == "stop":
        with game_lock:
            if room_id in games:
                del games[room_id]
                bot.send_message(room_id, "🛑 Game Cancelled.")
        return True

    # 3. JOIN
    if cmd == "join":
        with game_lock:
            g = games.get(room_id)
            if not g or g.state != 'waiting_join': return False
            if str(g.p1_id) == str(uid): return True
            g.p2_id = uid; g.p2_name = user; g.p2_avatar = av_url
            if g.bet > 0: add_game_result(uid, user, "mines", -g.bet, False)
            g.state = 'setup_phase'
            setup_pending[str(g.p1_id)] = room_id; setup_pending[str(g.p2_id)] = room_id
        
        bot.send_message(room_id, "✅ **Match Found!** Check your **DM** immediately.")
        
        link = utils.upload(bot, draw_setup_board())
        msg = (
            "💣 **SETUP PHASE**\n"
            "You need to hide **4 Bombs**.\n"
            "Send 4 numbers (1-12) separated by space.\n\n"
            "👉 Reply Example: `1 3 7 12`"
        )
        bot.send_dm_image(g.p1_name, link, msg)
        bot.send_dm_image(g.p2_name, link, msg)
        return True

    # 4. DM SETUP (4 Bombs Logic)
    if str(uid) in setup_pending:
        nums = [int(s) for s in command.split() if s.isdigit()]
        if not nums and args: nums = [int(s) for s in args if s.isdigit()]
        
        # Check for 4 Numbers now
        if len(nums) == 4 and all(1<=n<=12 for n in nums) and len(set(nums))==4:
            rid = setup_pending[str(uid)]
            with game_lock:
                if rid in games:
                    g = games[rid]
                    idxs = [n-1 for n in nums]
                    
                    if str(uid) == str(g.p1_id):
                        for i in idxs: g.board_p1[i] = 1
                        g.p1_ready = True
                        bot.send_dm(user, "Done ✅ - Waiting for opponent...")
                    elif str(uid) == str(g.p2_id):
                        for i in idxs: g.board_p2[i] = 1
                        g.p2_ready = True
                        bot.send_dm(user, "Done ✅ - Waiting for opponent...")
                    
                    if g.p1_ready and g.p2_ready:
                        g.state = 'playing'
                        del setup_pending[str(g.p1_id)]; del setup_pending[str(g.p2_id)]
                        bot.send_message(rid, "🔥 **Game Started!**")
                        link = utils.upload(bot, draw_enhanced_board(g.board_p2, g.revealed_p2, g.lives_p1, g.lives_p2, g.p1_name, g.p1_name, g.p2_name))
                        bot.send_json({"handler": "chatroommessage", "roomid": rid, "type": "image", "url": link, "text": "Start"})
            return True
        else:
            bot.send_dm(user, "❌ **Error!**\nPlease send exactly **4 unique numbers** (1-12).\nExample: `2 5 8 11`")
            return True

    # 5. PLAY
    with game_lock:
        g = games.get(room_id)
        if not g or g.state != 'playing': return False
        if cmd.isdigit() and 1 <= int(cmd) <= 12:
            idx = int(cmd)-1
            is_p1 = (g.turn == 'P1')
            if (is_p1 and str(uid)!=str(g.p1_id)) or (not is_p1 and str(uid)!=str(g.p2_id)): return False
            
            tgt_rev = g.revealed_p2 if is_p1 else g.revealed_p1
            tgt_brd = g.board_p2 if is_p1 else g.board_p1
            
            if tgt_rev[idx]:
                bot.send_message(room_id, "🚫 Box already opened.")
                return True
            
            tgt_rev[idx] = True
            hit = (tgt_brd[idx] == 1)
            name = g.p1_name if is_p1 else g.p2_name
            av = g.p1_avatar if is_p1 else g.p2_avatar
            
            if hit:
                if is_p1: g.lives_p1 -= 1
                else: g.lives_p2 -= 1
                lives = g.lives_p1 if is_p1 else g.lives_p2
                link = utils.upload(bot, draw_result_card(name, lives, "blast", av))
                bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "BOOM"})
            
            winner, win_id, win_av = None, None, None
            if g.lives_p1 == 0: winner=g.p2_name; win_id=g.p2_id; win_av=g.p2_avatar
            elif g.lives_p2 == 0: winner=g.p1_name; win_id=g.p1_id; win_av=g.p1_avatar
            
            if winner:
                rew = g.bet*2 if g.bet>0 else 0
                add_game_result(win_id, winner, "mines", rew, True)
                link = utils.upload(bot, draw_result_card(winner, 0, "win", win_av))
                bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "WIN"})
                bot.send_message(room_id, f"🎉 {winner} Wins +{rew}!")
                del games[room_id]
                return True
            
            g.turn = 'P2' if is_p1 else 'P1'
            nxt = g.p2_name if is_p1 else g.p1_name
            nxt_brd = g.board_p1 if is_p1 else g.board_p2
            nxt_rev = g.revealed_p1 if is_p1 else g.revealed_p2
            
            link = utils.upload(bot, draw_enhanced_board(nxt_brd, nxt_rev, g.lives_p1, g.lives_p2, nxt, g.p1_name, g.p2_name))
            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Turn"})
            return True
            
    return False
