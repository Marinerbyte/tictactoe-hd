import time
import random
import threading
import sys
import os
import re
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
    print("[CookieMines] Final Pro Version Loaded.")

# --- CLEANUP (Fixed Timeout Issue) ---
def game_cleanup_loop():
    while True:
        time.sleep(10); now = time.time(); to_remove = []
        with game_lock:
            for rid, g in games.items():
                # 120 Seconds (2 Min) timeout agar koi activity na ho
                if now - g.last_interaction > 120: to_remove.append(rid)
        for rid in to_remove:
            if BOT_INSTANCE:
                try: BOT_INSTANCE.send_message(rid, "⌛ **Game Timeout!** No activity for 2 mins.")
                except: pass
            with game_lock:
                if rid in games:
                    g = games[rid]
                    if str(g.p1_id) in setup_pending: del setup_pending[str(g.p1_id)]
                    if g.p2_id and str(g.p2_id) in setup_pending: del setup_pending[str(g.p2_id)]
                    del games[rid]

if threading.active_count() < 10: threading.Thread(target=game_cleanup_loop, daemon=True).start()

# ==========================================
# 🎨 ARTIST SECTION (Next Level Visuals)
# ==========================================

def draw_enhanced_board(board_config, revealed_list, lives_p1, lives_p2, current_turn_name, p1_name, p2_name, is_game_over=False):
    # COMPACT SIZE: 500x580
    W, H = 500, 580
    img = utils.create_canvas(W, H, color=(25, 25, 30)) # Deep Matte Black
    d = ImageDraw.Draw(img)
    
    # 1. HEADER (Cyberpunk Style)
    # P1 Box
    is_p1_turn = (current_turn_name == p1_name and not is_game_over)
    p1_bg = (40, 60, 40) if is_p1_turn else (30, 30, 35)
    p1_out = "#00FF00" if is_p1_turn else "#555"
    
    d.rounded_rectangle([20, 20, 200, 90], radius=15, fill=p1_bg, outline=p1_out, width=3)
    utils.write_text(d, (110, 40), f"@{p1_name[:8]}", size=20, align="center", col="#FFF")
    utils.write_text(d, (110, 65), "❤️" * lives_p1, size=18, align="center")

    # P2 Box
    is_p2_turn = (current_turn_name == p2_name and not is_game_over)
    p2_bg = (40, 60, 40) if is_p2_turn else (30, 30, 35)
    p2_out = "#00FF00" if is_p2_turn else "#555"
    
    d.rounded_rectangle([300, 20, 480, 90], radius=15, fill=p2_bg, outline=p2_out, width=3)
    utils.write_text(d, (390, 40), f"@{p2_name[:8]}", size=20, align="center", col="#FFF")
    utils.write_text(d, (390, 65), "❤️" * lives_p2, size=18, align="center")

    # VS Badge (Neon Glow)
    d.ellipse([225, 30, 275, 80], fill="#111", outline="#FFD700", width=2)
    utils.write_text(d, (250, 55), "VS", size=22, align="center", col="#FFD700", shadow=False)

    # 2. STATUS BAR
    msg = f"Waiting for: {current_turn_name}" if not is_game_over else "GAME OVER"
    col = "#FFFF00" if not is_game_over else "#FF4444"
    
    d.rounded_rectangle([80, 110, 420, 145], radius=10, fill=(20,20,20), outline="#333", width=1)
    utils.write_text(d, (W//2, 128), msg, size=20, align="center", col=col)

    # 3. THE GRID (3D Buttons)
    start_x, start_y = 50, 170
    box_w, box_h = 90, 90
    gap = 15
    
    cookie = utils.get_emoji("🍪", size=55)
    bomb = utils.get_emoji("💥", size=55)
    
    for i in range(12):
        row = i // 4; col = i % 4
        x = start_x + (col * (box_w + gap))
        y = start_y + (row * (box_h + gap))
        
        if not revealed_list[i]:
            # HIDDEN STATE (3D Button Look)
            # Shadow/Bottom
            d.rounded_rectangle([x, y+5, x+box_w, y+box_h+5], radius=12, fill=(40, 40, 50))
            # Main Top
            d.rounded_rectangle([x, y, x+box_w, y+box_h], radius=12, fill=(60, 60, 75), outline="#888", width=1)
            # Number
            utils.write_text(d, (x+45, y+45), str(i+1), size=28, align="center", col="#DDD", shadow=True)
        else:
            # REVEALED STATE
            if board_config[i] == 1:
                # BOMB (Glowing Red)
                d.rounded_rectangle([x, y, x+box_w, y+box_h], radius=12, fill=(100, 20, 20), outline="#FF0000", width=3)
                if bomb: img.paste(bomb, (x+17, y+17), bomb)
            else:
                # SAFE (Glowing Green)
                d.rounded_rectangle([x, y, x+box_w, y+box_h], radius=12, fill=(20, 100, 40), outline="#00FF00", width=3)
                if cookie: img.paste(cookie, (x+17, y+17), cookie)

    # Footer
    utils.write_text(d, (W//2, 555), "Type a number (1-12) to Eat", size=14, col="#666", align="center")
    return img

def draw_setup_board():
    """Top Secret Blueprint Style for DM"""
    W, H = 600, 400
    img = utils.create_canvas(W, H, (10, 15, 20)) # Blueprint Blue/Black
    d = ImageDraw.Draw(img)
    
    # Header
    d.rectangle([0, 0, W, 60], fill=(20, 30, 40))
    utils.write_text(d, (W//2, 30), "⚠ TOP SECRET MISSION ⚠", size=28, align="center", col="#FF4444", shadow=True)
    
    # Grid Reference (Visual Aid)
    start_x, start_y = 60, 80
    box_w, box_h = 100, 60
    gap = 20
    
    for i in range(12):
        row = i // 4; col = i % 4
        x = start_x + (col * (box_w + gap))
        y = start_y + (row * (box_h + gap))
        
        d.rounded_rectangle([x, y, x+box_w, y+box_h], radius=5, fill=(30, 40, 50), outline="#555", width=1)
        utils.write_text(d, (x+50, y+30), str(i+1), size=24, align="center", col="#88CCFF")

    utils.write_text(d, (W//2, 350), "Select 4 numbers from above grid", size=20, align="center", col="#FFF")
    return img

def draw_result_card(name, lives, type="blast", avatar=None):
    W, H = 500, 350
    # Dynamic Gradient based on event
    if type == "blast": c1, c2 = (150, 0, 0), (50, 0, 0)
    else: c1, c2 = (255, 215, 0), (200, 140, 0)
    
    img = utils.get_gradient(W, H, c1, c2)
    d = ImageDraw.Draw(img)
    
    icon = utils.get_emoji("💥", size=120) if type == "blast" else utils.get_emoji("🏆", size=120)
    if icon: img.paste(icon, (W//2 - 60, 40), icon)
    
    title = "BOOM!" if type == "blast" else "VICTORY!"
    col = "#FFF" if type == "blast" else "#FFF"
    
    utils.write_text(d, (W//2, 190), title, size=50, align="center", col=col, shadow=True)
    utils.write_text(d, (W//2, 250), f"@{name}", size=30, align="center", col="white", shadow=True)
    
    if type == "blast":
        utils.write_text(d, (W//2, 290), f"Lives Remaining: {lives}", size=20, align="center", col="#FFCCCC")
    
    return img

# ==========================================
# ⚙️ GAME LOGIC
# ==========================================
class MinesGame:
    def __init__(self, room_id, p1_id, p1_name):
        self.room_id = room_id; self.p1_id = p1_id; self.p1_name = p1_name
        self.p2_id = None; self.p2_name = None; self.p1_avatar = None; self.p2_avatar = None
        self.state = 'waiting_join'; self.bet = 500
        self.board_p1 = [0]*12; self.board_p2 = [0]*12
        self.revealed_p1 = [False]*12; self.revealed_p2 = [False]*12
        self.lives_p1 = 3; self.lives_p2 = 3
        self.p1_ready = False; self.p2_ready = False
        self.turn = 'P1'
        self.last_interaction = time.time()
    
    def touch(self): self.last_interaction = time.time()

def handle_command(bot, command, room_id, user, args, data):
    global games, setup_pending
    uid = data.get('userid', user)
    av_file = data.get("avatar")
    av_url = f"https://cdn.howdies.app/avatar?image={av_file}" if av_file else None
    cmd = command.lower().strip()

    # 1. NEW GAME
    if cmd == "mines":
        amt = int(args[0]) if args and args[0].isdigit() else 500
        with game_lock:
            if room_id in games: return True
            g = MinesGame(room_id, uid, user); g.bet = amt; g.p1_avatar = av_url
            if amt > 0: add_game_result(uid, user, "mines", -amt, False)
            games[room_id] = g
            g.touch() # Update Time
        
        bot.send_message(room_id, f"💣 **Mines Challenge!**\nBet: {amt} Coins\nPlayer 2: Type `!join` to accept.")
        return True

    # 2. STOP
    if cmd == "stop":
        with game_lock:
            if room_id in games:
                # Cleanup pending
                g = games[room_id]
                if str(g.p1_id) in setup_pending: del setup_pending[str(g.p1_id)]
                if g.p2_id and str(g.p2_id) in setup_pending: del setup_pending[str(g.p2_id)]
                
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
            g.touch() # Update Time
            
            setup_pending[str(g.p1_id)] = room_id
            setup_pending[str(g.p2_id)] = room_id
        
        bot.send_message(room_id, "✅ **Match Found!** check your **DM** immediately.")
        
        link = utils.upload(bot, draw_setup_board())
        
        # Detailed Instructions
        msg = (
            "💣 **MISSION BRIEFING** 💣\n\n"
            "You must hide **4 Bombs** on your board.\n"
            "Pick 4 unique numbers from the grid (1-12).\n\n"
            "👇 **HOW TO REPLY:**\n"
            "Simply type numbers separated by space.\n"
            "Example: `1 3 7 12`\n\n"
            "Reply NOW to set your defense!"
        )
        
        bot.send_dm_image(g.p1_name, link, msg)
        bot.send_dm_image(g.p2_name, link, msg)
        return True

    # 4. DM SETUP LOGIC
    if str(uid) in setup_pending:
        # Allow comma or space separator
        clean_txt = command.replace(',', ' ')
        nums = [int(s) for s in clean_txt.split() if s.isdigit()]
        
        # Check for 4 unique numbers 1-12
        if len(nums) == 4 and all(1<=n<=12 for n in nums) and len(set(nums))==4:
            rid = setup_pending[str(uid)]
            with game_lock:
                if rid in games:
                    g = games[rid]
                    g.touch() # Update Time
                    idxs = [n-1 for n in nums]
                    
                    if str(uid) == str(g.p1_id):
                        for i in idxs: g.board_p1[i] = 1
                        g.p1_ready = True
                    elif str(uid) == str(g.p2_id):
                        for i in idxs: g.board_p2[i] = 1
                        g.p2_ready = True
                    
                    # REQUESTED REPLY
                    bot.send_dm(user, "Done ✅ selected now go back in room")

                    if g.p1_ready and g.p2_ready:
                        g.state = 'playing'
                        del setup_pending[str(g.p1_id)]; del setup_pending[str(g.p2_id)]
                        
                        bot.send_message(rid, "🔥 **All Bombs Set! Game Started!**")
                        link = utils.upload(bot, draw_enhanced_board(g.board_p2, g.revealed_p2, g.lives_p1, g.lives_p2, g.p1_name, g.p1_name, g.p2_name))
                        bot.send_json({"handler": "chatroommessage", "roomid": rid, "type": "image", "url": link, "text": "Start"})
            return True
        else:
            bot.send_dm(user, "❌ **Invalid!** Send exactly 4 unique numbers (1-12).\nExample: `2 5 8 12`")
            return True

    # 5. GAMEPLAY
    with game_lock:
        g = games.get(room_id)
        if not g or g.state != 'playing': return False

        if cmd.isdigit() and 1 <= int(cmd) <= 12:
            idx = int(cmd)-1
            is_p1 = (g.turn == 'P1')
            if (is_p1 and str(uid)!=str(g.p1_id)) or (not is_p1 and str(uid)!=str(g.p2_id)): return False
            
            g.touch() # Update Time on Move
            
            tgt_rev = g.revealed_p2 if is_p1 else g.revealed_p1
            tgt_brd = g.board_p2 if is_p1 else g.board_p1
            
            if tgt_rev[idx]:
                bot.send_message(room_id, "🚫 Box already opened.")
                return True
            
            tgt_rev[idx] = True
            hit = (tgt_brd[idx] == 1)
            name = g.p1_name if is_p1 else g.p2_name
            av = g.p1_avatar if is_p1 else g.p2_avatar
            
            # --- SAFE MOVE FEEDBACK (REQUESTED) ---
            if not hit:
                 bot.send_message(room_id, f"😋 **Safe!** @{user} ate a tasty cookie.")

            # --- BOMB HIT ---
            if hit:
                if is_p1: g.lives_p1 -= 1
                else: g.lives_p2 -= 1
                lives = g.lives_p1 if is_p1 else g.lives_p2
                link = utils.upload(bot, draw_result_card(name, lives, "blast", av))
                bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "BOOM"})
            
            # CHECK WINNER
            winner, win_id, win_av = None, None, None
            if g.lives_p1 == 0: winner=g.p2_name; win_id=g.p2_id; win_av=g.p2_avatar
            elif g.lives_p2 == 0: winner=g.p1_name; win_id=g.p1_id; win_av=g.p1_avatar
            
            if winner:
                rew = g.bet*2 if g.bet>0 else 0
                add_game_result(win_id, winner, "mines", rew, True)
                link = utils.upload(bot, draw_result_card(winner, 0, "win", win_av))
                bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "WIN"})
                bot.send_message(room_id, f"🎉 **{winner} WINS!** +{rew} Coins")
                del games[room_id]
                return True
            
            # NEXT TURN
            g.turn = 'P2' if is_p1 else 'P1'
            nxt = g.p2_name if is_p1 else g.p1_name
            nxt_brd = g.board_p1 if is_p1 else g.board_p2
            nxt_rev = g.revealed_p1 if is_p1 else g.revealed_p2
            
            link = utils.upload(bot, draw_enhanced_board(nxt_brd, nxt_rev, g.lives_p1, g.lives_p2, nxt, g.p1_name, g.p2_name))
            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Turn"})
            return True
            
    return False
