import sys
import os
import random
import time
import threading
import math
from PIL import Image, ImageDraw

# --- IMPORTS ---
try: import utils
except ImportError: print("[Ludo] Error: utils.py not found!")

try:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from db import add_game_result
except Exception as e: print(f"DB Import Error: {e}")

# --- GLOBALS ---
games = {}
game_lock = threading.Lock()
BOT_INSTANCE = None

DICE_GIF = "https://media.tenor.com/2sWp_FhG2P4AAAAi/dice-roll.gif"

# Config
SAFE_SPOTS = [0, 8, 13, 21, 26, 34, 39, 47] 
TOTAL_STEPS = 51

def setup(bot):
    global BOT_INSTANCE
    BOT_INSTANCE = bot
    print("[Ludo] Stable Engine Loaded.")

# --- CLEANUP ---
def game_cleanup_loop():
    while True:
        time.sleep(10); now = time.time(); to_remove = []
        with game_lock:
            for rid, g in games.items():
                if now - g.last_interaction > 300: to_remove.append(rid)
        for rid in to_remove:
            with game_lock:
                if rid in games: del games[rid]

if threading.active_count() < 10: threading.Thread(target=game_cleanup_loop, daemon=True).start()

# ==========================================
# 🎨 GRAPHICS (Internal Dice Generator)
# ==========================================

def draw_dice_face(number):
    """Draws a Dice locally using PIL (Crash Proof)"""
    size = 200
    img = Image.new("RGBA", (size, size), (0,0,0,0))
    d = ImageDraw.Draw(img)
    
    # White Box with Border
    d.rounded_rectangle([10, 10, 190, 190], radius=30, fill="white", outline="#AAA", width=2)
    
    # Dot positions
    dots = []
    c = size // 2
    l = size // 4
    r = size * 3 // 4
    
    if number == 1: dots = [(c, c)]
    elif number == 2: dots = [(l, l), (r, r)]
    elif number == 3: dots = [(l, l), (c, c), (r, r)]
    elif number == 4: dots = [(l, l), (r, l), (l, r), (r, r)]
    elif number == 5: dots = [(l, l), (r, l), (c, c), (l, r), (r, r)]
    elif number == 6: dots = [(l, l), (r, l), (l, c), (r, c), (l, r), (r, r)]
    
    for x, y in dots:
        d.ellipse([x-15, y-15, x+15, y+15], fill="black")
        
    return img

def get_coordinates(global_step, color_idx):
    path_map = [
        (1,6), (2,6), (3,6), (4,6), (5,6), (6,5), (6,4), (6,3), (6,2), (6,1), (6,0),
        (7,0), (8,0), (8,1), (8,2), (8,3), (8,4), (8,5), (9,6), (10,6), (11,6), (12,6), (13,6), (14,6),
        (14,7), (14,8), (13,8), (12,8), (11,8), (10,8), (9,8), (8,9), (8,10), (8,11), (8,12), (8,13), (8,14),
        (7,14), (6,14), (6,13), (6,12), (6,11), (6,10), (6,9), (5,8), (4,8), (3,8), (2,8), (1,8), (0,8), (0,7)
    ]
    offset = color_idx * 13
    if global_step < 51:
        actual_idx = (global_step + offset) % 52
        return path_map[actual_idx]
    else:
        home_steps = global_step - 50
        if color_idx == 0: return (home_steps, 7)
        if color_idx == 1: return (7, home_steps)
        if color_idx == 2: return (14-home_steps, 7)
        if color_idx == 3: return (7, 14-home_steps)
    return (7,7)

def draw_ludo_board(players):
    CELL = 50
    W, H = CELL * 15, CELL * 15 + 100
    OY = 100
    img = utils.create_canvas(W, H, (30, 30, 35))
    d = ImageDraw.Draw(img)
    
    d.rectangle([0, OY, W, H], fill="white", outline="black", width=2)
    
    colors = {0:("#FF4500","#FFD700"), 1:("#32CD32","#ADFF2F"), 2:("#FFD700","#FFFFE0"), 3:("#1E90FF","#87CEFA")}
    bases = [(0,0,"Red"), (9,0,"Green"), (9,9,"Yellow"), (0,9,"Blue")]
    
    for i, (bx, by, name) in enumerate(bases):
        x, y = bx*CELL, by*CELL+OY
        size = 6*CELL
        d.rectangle([x, y, x+size, y+size], fill=colors[i][0], outline="black", width=2)
        d.rectangle([x+CELL, y+CELL, x+size-CELL, y+size-CELL], fill="white", outline="black", width=2)
        
        p = players[i]
        if p:
            utils.write_text(d, (x+size//2, y+size-30), f"@{p['name'][:8]}", size=20, align="center", col="black")
            if p['av']:
                av = utils.get_circle_avatar(p['av'], size=100)
                if av: img.paste(av, (x+size//2-50, y+size//2-50), av)

    for i in range(15):
        for j in range(15):
            if not ((i<6 and j<6) or (i>8 and j<6) or (i>8 and j>8) or (i<6 and j>8)):
                px, py = i*CELL, j*CELL+OY
                d.rectangle([px, py, px+CELL, py+CELL], outline="black", width=1)
                if j==7 and 0<i<6: d.rectangle([px, py, px+CELL, py+CELL], fill=colors[0][0], outline="black")
                if i==7 and 0<j<6: d.rectangle([px, py, px+CELL, py+CELL], fill=colors[1][0], outline="black")
                if j==7 and 8<i<14: d.rectangle([px, py, px+CELL, py+CELL], fill=colors[2][0], outline="black")
                if i==7 and 8<j<14: d.rectangle([px, py, px+CELL, py+CELL], fill=colors[3][0], outline="black")

    center_box = [6*CELL, 6*CELL + OY, 9*CELL, 9*CELL + OY]
    d.polygon([(6*CELL, 6*CELL+OY), (9*CELL, 6*CELL+OY), (7.5*CELL, 7.5*CELL+OY)], fill=colors[1][0], outline="black") 
    d.polygon([(9*CELL, 6*CELL+OY), (9*CELL, 9*CELL+OY), (7.5*CELL, 7.5*CELL+OY)], fill=colors[2][0], outline="black") 
    d.polygon([(9*CELL, 9*CELL+OY), (6*CELL, 9*CELL+OY), (7.5*CELL, 7.5*CELL+OY)], fill=colors[3][0], outline="black") 
    d.polygon([(6*CELL, 9*CELL+OY), (6*CELL, 6*CELL+OY), (7.5*CELL, 7.5*CELL+OY)], fill=colors[0][0], outline="black") 
    utils.write_text(d, (7.5*CELL, 7.5*CELL + OY), "HOME", size=25, align="center", col="white", shadow=True)

    pos_map = {}
    for i, p in enumerate(players):
        if not p or p['pos'] == -1: continue
        gx, gy = get_coordinates(p['pos'], i)
        if (gx, gy) not in pos_map: pos_map[(gx,gy)] = []
        pos_map[(gx,gy)].append(i)

    for (gx, gy), p_idxs in pos_map.items():
        cx = gx*CELL + CELL//2
        cy = gy*CELL + CELL//2 + OY
        shift = 10 if len(p_idxs) > 1 else 0
        for idx, p_idx in enumerate(p_idxs):
            off_x = (idx - (len(p_idxs)-1)/2) * shift
            token_col = colors[p_idx][0]
            d.ellipse([cx-18+off_x, cy-18, cx+18+off_x, cy+18], fill=token_col, outline="white", width=2)
            if players[p_idx]['av']:
                av = utils.get_circle_avatar(players[p_idx]['av'], size=30)
                if av: img.paste(av, (int(cx-15+off_x), int(cy-15)), av)

    utils.write_text(d, (W//2, 30), "🎲 LUDO: ONE TOKEN", size=40, align="center", col="#FFD700", shadow=True)
    turn_p = next((p for p in players if p and p['turn']), None)
    if turn_p:
        utils.write_text(d, (W//2, 70), f"Turn: @{turn_p['name']}", size=25, align="center", col="white")

    return img

# ==========================================
# ⚙️ LOGIC
# ==========================================

class LudoGame:
    def __init__(self, room_id, bet):
        self.room_id = room_id
        self.bet = bet
        self.players = [None] * 4
        self.state = 'waiting'
        self.turn_idx = 0
        self.last_interaction = time.time()
        
    def add_player(self, uid, name, av):
        for i in range(4):
            if self.players[i] is None:
                self.players[i] = {'id': i, 'uid': uid, 'name': name, 'av': av, 'pos': -1, 'turn': False}
                return i
        return -1

    def next_turn(self):
        start = self.turn_idx
        while True:
            self.turn_idx = (self.turn_idx + 1) % 4
            p = self.players[self.turn_idx]
            if p:
                for pl in self.players: 
                    if pl: pl['turn'] = False
                p['turn'] = True
                return p
            if self.turn_idx == start: return None

    def move_token(self, p_idx, dice):
        p = self.players[p_idx]
        if p['pos'] == -1:
            if dice == 6: 
                p['pos'] = 0
                return "open"
            return "stuck"
        
        new_pos = p['pos'] + dice
        if new_pos > 56: return "bounce"
        if new_pos == 56: 
            p['pos'] = 56
            return "win"
            
        my_global = (new_pos + (p_idx * 13)) % 52
        if new_pos > 50: my_global = -100 
        
        killed = None
        if my_global not in SAFE_SPOTS and my_global != -100:
            for i, enemy in enumerate(self.players):
                if enemy and i != p_idx and enemy['pos'] != -1 and enemy['pos'] <= 50:
                    enemy_global = (enemy['pos'] + (i * 13)) % 52
                    if enemy_global == my_global:
                        enemy['pos'] = -1
                        killed = enemy['name']
        
        p['pos'] = new_pos
        return f"kill {killed}" if killed else "move"

def handle_command(bot, command, room_id, user, args, data):
    uid = data.get('userid', user)
    av_file = data.get("avatar")
    av = f"https://cdn.howdies.app/avatar?image={av_file}" if av_file else None
    cmd = command.lower().strip()
    
    if cmd == "ludo":
        bet = int(args[0]) if args and args[0].isdigit() else 0
        with game_lock:
            if room_id in games: return True
            g = LudoGame(room_id, bet)
            g.add_player(uid, user, av)
            if bet>0: add_game_result(uid, user, "ludo", -bet, False)
            games[room_id] = g
        bot.send_message(room_id, f"🎲 **Ludo Created!** Bet: {bet}\nType `!join`")
        return True

    if cmd == "join":
        with game_lock:
            g = games.get(room_id)
            if not g or g.state != 'waiting': return False
            if any(p and str(p['uid']) == str(uid) for p in g.players): return True
            idx = g.add_player(uid, user, av)
            if idx != -1:
                if g.bet>0: add_game_result(uid, user, "ludo", -g.bet, False)
                bot.send_message(room_id, f"✅ **{user}** Joined!")
        return True

    if cmd == "start":
        with game_lock:
            g = games.get(room_id)
            if not g or g.state != 'waiting': return False
            if sum(1 for p in g.players if p) < 2:
                bot.send_message(room_id, "⚠️ Need 2 players.")
                return True
            g.state = 'playing'
            g.players[0]['turn'] = True
            link = utils.upload(bot, draw_ludo_board(g.players))
            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Start"})
            bot.send_message(room_id, f"🚦 Go! @{g.players[0]['name']} `!roll`")
        return True

    if cmd == "roll":
        utils.run_in_bg(process_turn, bot, room_id, uid)
        return True

    if cmd == "stop":
        with game_lock:
            if room_id in games: del games[room_id]
            bot.send_message(room_id, "🛑 Stopped.")
        return True
    return False

def process_turn(bot, room_id, uid):
    with game_lock:
        g = games.get(room_id)
        if not g: return
        curr_p = g.players[g.turn_idx]
        if str(curr_p['uid']) != str(uid): return

    bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": DICE_GIF, "text": "Rolling"})
    time.sleep(2.5)
    
    dice = random.randint(1, 6)
    with game_lock:
        g = games.get(room_id)
        if not g: return
        result = g.move_token(g.turn_idx, dice)
        
        # Internal Draw (Crash Proof)
        dice_img = draw_dice_face(dice)
        dice_link = utils.upload(bot, dice_img)
        bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": dice_link, "text": str(dice)})
        
        if result == "win":
            rew = g.bet * sum(1 for p in g.players if p)
            add_game_result(uid, curr_p['name'], "ludo", rew, True)
            bot.send_message(room_id, f"🏆 {curr_p['name']} Wins {rew} Coins!")
            del games[room_id]
            return
            
        msg = f"Rolled {dice}. "
        if result == "open": msg += "Unlocked!"
        elif result.startswith("kill"): msg += f"⚔️ Killed {result.split()[1]}!"
        elif result == "stuck": 
            msg += "Need 6 to open."
            g.next_turn()
        elif result == "bounce":
            msg += "Too high."
            g.next_turn()
        else:
            if dice != 6: g.next_turn()
            else: msg += "Roll again!"
            
        link = utils.upload(bot, draw_ludo_board(g.players))
        bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Board"})
        
        if result != "win":
            next_name = g.players[g.turn_idx]['name']
            bot.send_message(room_id, f"{msg}\n👉 @{next_name}'s Turn")
