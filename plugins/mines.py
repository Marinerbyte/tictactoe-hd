import time
import random
import threading
import sys
import os
import uuid
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
    print("[CookieMines] Final 3D Fixed.")

# --- CLEANUP ---
def game_cleanup_loop():
    while True:
        time.sleep(10); now = time.time(); to_remove = []
        with game_lock:
            for rid, g in games.items():
                if now - g.last_interaction > 180: to_remove.append(rid) # 3 Mins
        for rid in to_remove:
            if BOT_INSTANCE:
                try: BOT_INSTANCE.send_message(rid, "⌛ **Game Expired!** Room cleaned.")
                except: pass
            with game_lock:
                if rid in games:
                    g = games[rid]
                    if str(g.p1_id) in setup_pending: del setup_pending[str(g.p1_id)]
                    if g.p2_id and str(g.p2_id) in setup_pending: del setup_pending[str(g.p2_id)]
                    del games[rid]

if threading.active_count() < 10: threading.Thread(target=game_cleanup_loop, daemon=True).start()

# ==========================================
# 🎨 3D ARTIST SECTION
# ==========================================

def draw_3d_button(d, x, y, w, h, color, outline, text=None, text_col="white", press=False):
    """Helper to draw 3D buttons"""
    shadow = (max(0, color[0]-30), max(0, color[1]-30), max(0, color[2]-30))
    if not press:
        d.rounded_rectangle([x, y+4, x+w, y+h+4], radius=10, fill=shadow) # Shadow
        d.rounded_rectangle([x, y, x+w, y+h], radius=10, fill=color, outline=outline, width=1) # Main
        d.rectangle([x+5, y+2, x+w-5, y+15], fill=(255,255,255, 30)) # Highlight
        if text: utils.write_text(d, (x+w//2, y+h//2), text, size=24, align="center", col=text_col, shadow=True)
    else:
        d.rounded_rectangle([x, y+4, x+w, y+h+4], radius=10, fill=color, outline=outline, width=2)
        if text: utils.write_text(d, (x+w//2, y+h//2 + 4), text, size=24, align="center", col=text_col)

def draw_enhanced_board(board_config, revealed_list, lives_p1, lives_p2, current_turn_name, p1_name, p2_name, is_game_over=False):
    W, H = 500, 500
    img = utils.create_canvas(W, H, color=(30, 32, 40)) 
    d = ImageDraw.Draw(img)
    
    # 1. HEADER
    is_p1 = (current_turn_name == p1_name and not is_game_over)
    col1 = (50, 80, 50) if is_p1 else (40, 40, 45)
    out1 = "#00FF00" if is_p1 else "#555"
    d.rounded_rectangle([10, 10, 180, 70], radius=10, fill=col1, outline=out1, width=2)
    utils.write_text(d, (95, 25), f"@{p1_name[:7]}", size=18, align="center", col="white")
    utils.write_text(d, (95, 48), "❤️" * lives_p1, size=16, align="center")

    is_p2 = (current_turn_name == p2_name and not is_game_over)
    col2 = (50, 80, 50) if is_p2 else (40, 40, 45)
    out2 = "#00FF00" if is_p2 else "#555"
    d.rounded_rectangle([320, 10, 490, 70], radius=10, fill=col2, outline=out2, width=2)
    utils.write_text(d, (405, 25), f"@{p2_name[:7]}", size=18, align="center", col="white")
    utils.write_text(d, (405, 48), "❤️" * lives_p2, size=16, align="center")

    utils.write_text(d, (W//2, 40), "VS", size=26, align="center", col="#FFD700", shadow=True)

    # 2. GRID
    start_x, start_y = 55, 90
    box_w, box_h = 85, 85
    gap = 15
    
    cookie = utils.get_emoji("🍪", size=55)
    bomb = utils.get_emoji("💣", size=55)
    
    for i in range(12):
        row = i // 4; col = i % 4
        x = start_x + (col * (box_w + gap))
        y = start_y + (row * (box_h + gap))
        
        if not revealed_list[i]:
            draw_3d_button(d, x, y, box_w, box_h, (60, 70, 100), "#8899AA", str(i+1))
        else:
            if board_config[i] == 1:
                d.rounded_rectangle([x, y, x+box_w, y+box_h], radius=10, fill=(180, 40, 40), outline="#FF0000", width=3)
                if bomb: img.paste(bomb, (x+15, y+15), bomb)
            else:
                d.rounded_rectangle([x, y, x+box_w, y+box_h], radius=10, fill=(40, 140, 60), outline="#00FF00", width=3)
                if cookie: img.paste(cookie, (x+15, y+15), cookie)

    # 3. FOOTER
    status = f"Turn: {current_turn_name}" if not is_game_over else "GAME OVER"
    s_col = "#FFD700" if not is_game_over else "#FF5555"
    utils.write_text(d, (W//2, 475), status, size=20, align="center", col=s_col, shadow=True)
    return img

def draw_winner_card(name, reward, avatar=None):
    W, H = 500, 500
    img = utils.create_canvas(W, H, (20, 10, 30))
    d = ImageDraw.Draw(img)
    for i in range(0, 360, 30):
        d.line([(W//2, H//2), (W//2 + 250, H//2 + 250)], fill=(255, 215, 0, 50), width=5)
    trophy = utils.get_emoji("👑", size=100)
    if trophy: img.paste(trophy, (W//2 - 50, 30), trophy)
    if avatar:
        av = utils.get_circle_avatar(avatar, size=150)
        if av: 
            img.paste(av, (W//2 - 75, 140), av)
            d.ellipse([W//2-80, 135, W//2+80, 295], outline="#FFD700", width=6)
    utils.write_text(d, (W//2, 330), "CHAMPION!", size=45, align="center", col="#FFD700", shadow=True)
    utils.write_text(d, (W//2, 380), f"@{name}", size=30, align="center", col="white", shadow=True)
    if reward > 0:
        utils.write_text(d, (W//2, 430), f"Won {reward} Coins", size=25, align="center", col="#00FF00")
    return img

def draw_blast_card(name, lives, avatar=None):
    W, H = 500, 500
    img = utils.create_canvas(W, H, (50, 10, 10))
    d = ImageDraw.Draw(img)
    skull = utils.get_emoji("💀", size=150)
    if skull: img.paste(skull, (W//2 - 75, 50), skull)
    if avatar:
        av = utils.get_circle_avatar(avatar, size=120)
        if av: 
            img.paste(av, (W//2 - 60, 220), av)
            d.line([W//2-50, 220, W//2+50, 340], fill="red", width=8)
            d.line([W//2+50, 220, W//2-50, 340], fill="red", width=8)
    utils.write_text(d, (W//2, 370), "ELIMINATED?", size=40, align="center", col="red", shadow=True)
    utils.write_text(d, (W//2, 430), f"Lives: {lives}", size=25, align="center", col="#FFAA00")
    return img

def draw_setup_board():
    W, H = 500, 500
    img = utils.create_canvas(W, H, (20, 20, 25))
    d = ImageDraw.Draw(img)
    start_x, start_y = 55, 100
    box_w, box_h = 85, 60
    gap = 15
    for i in range(12):
        row = i // 4; col = i % 4
        x = start_x + (col * (box_w + gap))
        y = start_y + (row * (box_h + gap))
        d.rounded_rectangle([x, y, x+box_w, y+box_h], radius=5, fill=(40, 50, 60), outline="#555", width=1)
        utils.write_text(d, (x+42, y+30), str(i+1), size=20, align="center", col="#AAA")
    utils.write_text(d, (W//2, 40), "🔒 SECRET MISSION", size=35, align="center", col="#FEE75C", shadow=True)
    utils.write_text(d, (W//2, 400), "Select 4 numbers from above", size=22, align="center", col="white")
    utils.write_text(d, (W//2, 440), "Example Reply: 1 5 9 12", size=20, align="center", col="#00FF00")
    return img

# ==========================================
# ⚙️ LOGIC
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
        amt = int(args[0]) if args and args[0].isdigit() else 500
        with game_lock:
            if room_id in games: return True
            g = MinesGame(room_id, uid, user); g.bet = amt; g.p1_avatar = av_url
            if amt > 0: add_game_result(uid, user, "mines", -amt, False)
            games[room_id] = g
        bot.send_message(room_id, f"💣 **Mines!** Bet: {amt}\nPlayer 2: Type `!join` to start.")
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
        msg = "Hide 4 bombs (1-12).\nReply example: `2 5 8 11`"
        bot.send_dm_image(g.p1_name, link, msg)
        bot.send_dm_image(g.p2_name, link, msg)
        return True

    # 4. DM SETUP (FIXED LOGIC)
    if str(uid) in setup_pending:
        # Combine command + args and clean it
        full_text = f"{command} {' '.join(args)}"
        clean_text = full_text.replace(',', ' ')
        nums = [int(s) for s in clean_text.split() if s.isdigit()]
        
        if len(nums) == 4 and all(1<=n<=12 for n in nums) and len(set(nums))==4:
            rid = setup_pending[str(uid)]
            with game_lock:
                if rid in games:
                    g = games[rid]
                    g.touch()
                    idxs = [n-1 for n in nums]
                    if str(uid) == str(g.p1_id):
                        for i in idxs: g.board_p1[i] = 1
                        g.p1_ready = True
                    elif str(uid) == str(g.p2_id):
                        for i in idxs: g.board_p2[i] = 1
                        g.p2_ready = True
                    
                    # ✅ REQUESTED DM REPLY
                    bot.send_dm(user, "Your bombs has been placed ✅ now go back and play in room\n⚠️ **DON'T REVEAL THIS**")
                    
                    if g.p1_ready and g.p2_ready:
                        g.state = 'playing'
                        del setup_pending[str(g.p1_id)]; del setup_pending[str(g.p2_id)]
                        
                        bot.send_message(rid, "🔥 **Game Started!**")
                        link = utils.upload(bot, draw_enhanced_board(g.board_p2, g.revealed_p2, g.lives_p1, g.lives_p2, g.p1_name, g.p1_name, g.p2_name))
                        bot.send_json({"handler": "chatroommessage", "roomid": rid, "type": "image", "url": link, "text": "Start"})
            return True
        else:
            bot.send_dm(user, "❌ Invalid! Send 4 unique numbers.\nExample: `1 5 9 12`")
            return True

    # 5. PLAY
    with game_lock:
        g = games.get(room_id)
        if not g or g.state != 'playing': return False
        if cmd.isdigit() and 1 <= int(cmd) <= 12:
            idx = int(cmd)-1
            is_p1 = (g.turn == 'P1')
            if (is_p1 and str(uid)!=str(g.p1_id)) or (not is_p1 and str(uid)!=str(g.p2_id)): return False
            
            g.touch()
            tgt_rev = g.revealed_p2 if is_p1 else g.revealed_p1
            tgt_brd = g.board_p2 if is_p1 else g.board_p1
            
            if tgt_rev[idx]:
                bot.send_message(room_id, "🚫 Already open.")
                return True
            
            tgt_rev[idx] = True
            hit = (tgt_brd[idx] == 1)
            name = g.p1_name if is_p1 else g.p2_name
            av = g.p1_avatar if is_p1 else g.p2_avatar
            
            if not hit:
                 bot.send_message(room_id, f"😋 **Saved!** @{user} ate a tasty cookie.")

            if hit:
                if is_p1: g.lives_p1 -= 1
                else: g.lives_p2 -= 1
                lives = g.lives_p1 if is_p1 else g.lives_p2
                link = utils.upload(bot, draw_blast_card(name, lives, av))
                bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "BOOM"})

            winner, win_id, win_av = None, None, None
            loser_id = None
            if g.lives_p1 == 0: 
                winner=g.p2_name; win_id=g.p2_id; win_av=g.p2_avatar
                loser_id = g.p1_id
            elif g.lives_p2 == 0: 
                winner=g.p1_name; win_id=g.p1_id; win_av=g.p1_avatar
                loser_id = g.p2_id
            
            if winner:
                rew = g.bet*2 if g.bet>0 else 0
                add_game_result(win_id, winner, "mines", rew, True)
                link = utils.upload(bot, draw_winner_card(winner, rew, win_av))
                bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "WIN"})
                bot.send_message(room_id, f"🎉 **{winner} WINS!**")
                
                # KICK LOSER
                if loser_id:
                     bot.send_message(room_id, "👋 Kicking loser in 3s...")
                     time.sleep(3)
                     bot.send_json({"handler": "kickuser", "id": uuid.uuid4().hex, "roomid": room_id, "to": str(loser_id)})

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
