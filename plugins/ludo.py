import sys
import os
import random
import time
import threading
from PIL import Image, ImageDraw, ImageFont

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

# --- ASSETS ---
# Smooth 3D Dice Roll GIF
DICE_GIF = "https://media.tenor.com/2sWp_FhG2P4AAAAi/dice-roll.gif"

# Static Dice Results (Fast Load)
DICE_FACES = {
    1: "https://img.icons8.com/3d-fluency/100/1-circle.png",
    2: "https://img.icons8.com/3d-fluency/100/2-circle.png",
    3: "https://img.icons8.com/3d-fluency/100/3-circle.png",
    4: "https://img.icons8.com/3d-fluency/100/4-circle.png",
    5: "https://img.icons8.com/3d-fluency/100/5-circle.png",
    6: "https://img.icons8.com/3d-fluency/100/6-circle.png"
}

# Game Config
SAFE_SPOTS = [0, 8, 13, 21, 26, 34, 39, 47] 
TIMEOUT_SECONDS = 45
PENALTY = 2000

def setup(bot):
    global BOT_INSTANCE
    BOT_INSTANCE = bot
    print("[Ludo] Cute & Light Engine Loaded.")

# --- TIMEOUT MONITOR ---
def game_monitor_loop():
    while True:
        time.sleep(5)
        if not games: continue
        now = time.time()
        to_remove = []
        with game_lock:
            for rid, g in list(games.items()):
                if g.state == 'playing':
                    curr = g.players[g.turn_idx]
                    if curr and not curr['eliminated']:
                        if now - g.turn_start_time > TIMEOUT_SECONDS:
                            curr['eliminated'] = True
                            if BOT_INSTANCE:
                                BOT_INSTANCE.send_message(rid, f"⏰ **TIMEOUT!** @{curr['name']} eliminated! (-{PENALTY})")
                                add_game_result(curr['uid'], curr['name'], "ludo_penalty", -PENALTY, False)
                            
                            active = [p for p in g.players if p and not p['eliminated']]
                            if len(active) < 2:
                                if len(active) == 1:
                                    w = active[0]
                                    add_game_result(w['uid'], w['name'], "ludo", g.pot, True)
                                    if BOT_INSTANCE: BOT_INSTANCE.send_message(rid, f"🏆 **{w['name']} WINS!** +{g.pot}")
                                to_remove.append(rid)
                            else:
                                g.next_turn()
                                nxt = g.players[g.turn_idx]['name']
                                if BOT_INSTANCE: BOT_INSTANCE.send_message(rid, f"👉 Next: @{nxt}")

                if now - g.last_interaction > 300: to_remove.append(rid)
        for rid in to_remove:
            if rid in games: del games[rid]

if threading.active_count() < 10: threading.Thread(target=game_monitor_loop, daemon=True).start()

# ==========================================
# 🎨 GRAPHICS ENGINE (Lightweight & Cute)
# ==========================================

def get_coords(step, p_idx):
    # Standard Ludo Path Map
    path = [
        (1,6), (2,6), (3,6), (4,6), (5,6), (6,5), (6,4), (6,3), (6,2), (6,1), (6,0),
        (7,0), (8,0), (8,1), (8,2), (8,3), (8,4), (8,5), (8,6), (9,6), (10,6), (11,6), (12,6), (13,6), (14,6),
        (14,7), (14,8), (13,8), (12,8), (11,8), (10,8), (9,8), (8,8), (8,9), (8,10), (8,11), (8,12), (8,13), (8,14),
        (7,14), (6,14), (6,13), (6,12), (6,11), (6,10), (6,9), (6,8), (5,8), (4,8), (3,8), (2,8), (1,8), (0,8), (0,7)
    ]
    off = p_idx * 13
    if step < 51: return path[(step + off) % 52]
    else:
        # Home Run
        hs = step - 50
        if p_idx==0: return (hs, 7)
        if p_idx==1: return (7, hs)
        if p_idx==2: return (14-hs, 7)
        if p_idx==3: return (7, 14-hs)
    return (7,7)

def draw_light_board(players, pot):
    # Optimized Size (Fast Upload)
    CELL = 40
    W, H = CELL * 15, CELL * 15 + 60
    OY = 60
    
    # 1. Dark Theme Background
    img = utils.create_canvas(W, H, (30, 32, 40)) 
    d = ImageDraw.Draw(img)
    
    # Colors: Red, Green, Yellow, Blue
    cols = {
        0: ("#E74C3C", "#C0392B"), # Red
        1: ("#2ECC71", "#27AE60"), # Green
        2: ("#F1C40F", "#F39C12"), # Yellow
        3: ("#3498DB", "#2980B9")  # Blue
    }
    
    # Cute Emojis for Bases
    mascots = {0: "🦁", 1: "🐸", 2: "🐤", 3: "🐳"}

    # 2. Draw Grid Background
    d.rectangle([0, OY, W, H], fill="white")

    # 3. Draw Bases (The 4 Houses)
    bases = [(0,0,0), (9,0,1), (9,9,2), (0,9,3)]
    for bx, by, pid in bases:
        x, y = bx*CELL, by*CELL+OY
        size = 6*CELL
        c_main = cols[pid][0]
        
        # Outer Box
        d.rectangle([x, y, x+size, y+size], fill=c_main, outline="black", width=2)
        # Inner White Box
        d.rectangle([x+30, y+30, x+size-30, y+size-30], fill="white", outline="black", width=1)
        
        # Mascot Emoji
        utils.write_text(d, (x+70, y+60), mascots[pid], size=60, align="center", shadow=False)
        
        # Player Name
        p = players[pid]
        if p:
            name = f"@{p['name'][:8]}"
            if p['pos'] == -1: name += " (Base)"
            utils.write_text(d, (x+size//2, y+size-30), name, size=18, align="center", col="black")
        else:
            utils.write_text(d, (x+size//2, y+size-30), "WAITING", size=16, align="center", col="#AAA")

    # 4. Draw Paths
    # Fill safe zones/home paths
    d.rectangle([CELL, 7*CELL+OY, 6*CELL, 8*CELL+OY], fill=cols[0][0]) # Red
    d.rectangle([7*CELL, CELL+OY, 8*CELL, 6*CELL+OY], fill=cols[1][0]) # Green
    d.rectangle([9*CELL, 7*CELL+OY, 14*CELL, 8*CELL+OY], fill=cols[2][0]) # Yellow
    d.rectangle([7*CELL, 9*CELL+OY, 8*CELL, 14*CELL+OY], fill=cols[3][0]) # Blue
    
    # Grid Lines
    for i in range(16):
        d.line([i*CELL, OY, i*CELL, 15*CELL+OY], fill="black")
        d.line([0, i*CELL+OY, 15*CELL, i*CELL+OY], fill="black")

    # 5. Center Home (Triangles)
    cx, cy = 7.5*CELL, 7.5*CELL+OY
    tri_coords = [
        ([(6*CELL, 6*CELL+OY), (9*CELL, 6*CELL+OY), (cx, cy)], cols[1][0]), # Top
        ([(9*CELL, 6*CELL+OY), (9*CELL, 9*CELL+OY), (cx, cy)], cols[2][0]), # Right
        ([(9*CELL, 9*CELL+OY), (6*CELL, 9*CELL+OY), (cx, cy)], cols[3][0]), # Bottom
        ([(6*CELL, 9*CELL+OY), (6*CELL, 6*CELL+OY), (cx, cy)], cols[0][0])  # Left
    ]
    for pts, color in tri_coords:
        d.polygon(pts, fill=color, outline="black")
    
    # Pot Info
    utils.write_text(d, (cx, cy-12), "POT", size=14, align="center", col="white", shadow=True)
    utils.write_text(d, (cx, cy+8), str(pot), size=18, align="center", col="#FFD700", shadow=True)

    # 6. Tokens (Logic for Overlap + Initials)
    occupants = {}
    for i, p in enumerate(players):
        if not p or p['pos'] == -1 or p['eliminated']: continue
        gx, gy = get_coords(p['pos'], i)
        key = (gx, gy)
        if key not in occupants: occupants[key] = []
        occupants[key].append(i)
        
    for (gx, gy), p_idxs in occupants.items():
        base_x = gx * CELL + CELL//2
        base_y = gy * CELL + CELL//2 + OY
        
        for idx, p_idx in enumerate(p_idxs):
            # Shift if overlap
            shift = (idx - (len(p_idxs)-1)/2) * 8
            tx, ty = base_x + shift, base_y - shift
            
            p = players[p_idx]
            col = cols[p_idx][0]
            
            # Token Circle
            d.ellipse([tx-15, ty-15, tx+15, ty+15], fill=col, outline="white", width=2)
            
            # Initial (First Letter)
            initial = p['name'][0].upper()
            utils.write_text(d, (tx, ty), initial, size=18, align="center", col="white", shadow=True)

    # 7. Header Status
    turn_p = next((p for p in players if p and p['turn']), None)
    if turn_p:
        status = f"Turn: @{turn_p['name']} ({mascots[turn_p['id']]})"
        col = "white"
    else:
        status = "Game Over"
        col = "#AAA"
        
    utils.write_text(d, (W//2, 30), status, size=24, align="center", col=col, shadow=True)
    
    return img

# ==========================================
# ⚙️ GAME LOGIC
# ==========================================

class LudoGame:
    def __init__(self, room_id, bet):
        self.room_id = room_id
        self.bet = bet
        self.pot = 0
        self.players = [None]*4
        self.state = 'waiting'
        self.turn_idx = 0
        self.last_interaction = time.time()
        self.turn_start_time = 0
        
    def add_player(self, uid, name):
        for i in range(4):
            if self.players[i] is None:
                # No avatar download needed -> Super Fast
                self.players[i] = {
                    'id': i, 'uid': uid, 'name': name, 
                    'pos': -1, 'turn': False, 'eliminated': False
                }
                self.pot += self.bet
                return i
        return -1

    def start_game(self):
        self.state = 'playing'
        self.players[0]['turn'] = True
        self.turn_start_time = time.time()

    def next_turn(self):
        start = self.turn_idx
        while True:
            self.turn_idx = (self.turn_idx + 1) % 4
            p = self.players[self.turn_idx]
            if p and not p['eliminated']:
                for pl in self.players:
                    if pl: pl['turn'] = False
                p['turn'] = True
                self.turn_start_time = time.time()
                return p
            if self.turn_idx == start: return None

    def move(self, p_idx, dice):
        p = self.players[p_idx]
        if p['pos'] == -1:
            if dice == 6: p['pos'] = 0; return "open"
            return "stuck"
        
        new = p['pos'] + dice
        if new == 56: p['pos'] = 56; return "win"
        if new > 56: return "bounce"
        
        kill = None
        if new not in SAFE_SPOTS:
            gx, gy = get_coords(new, p_idx)
            for i, en in enumerate(self.players):
                if en and i != p_idx and en['pos'] > -1 and en['pos'] < 51:
                    egx, egy = get_coords(en['pos'], i)
                    if gx == egx and gy == egy:
                        en['pos'] = -1; kill = en['name']
        
        p['pos'] = new
        return f"kill {kill}" if kill else "move"

def handle_command(bot, command, room_id, user, args, data):
    uid = data.get('userid', user)
    cmd = command.lower().strip()
    
    if cmd == "ludo":
        bet = int(args[0]) if args and args[0].isdigit() else 0
        with game_lock:
            if room_id in games: return True
            g = LudoGame(room_id, bet)
            g.add_player(uid, user)
            if bet>0: add_game_result(uid, user, "ludo", -bet, False)
            games[room_id] = g
        bot.send_message(room_id, f"🎲 **Ludo!** Bet: {bet}\n`!join` to enter.")
        return True

    if cmd == "join":
        with game_lock:
            g = games.get(room_id)
            if not g or g.state != 'waiting': return False
            if any(p and str(p['uid']) == str(uid) for p in g.players): return True
            idx = g.add_player(uid, user)
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
            g.start_game()
            link = utils.upload(bot, draw_light_board(g.players, g.pot))
            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Start"})
            bot.send_message(room_id, f"🚦 Go! @{g.players[0]['name']} `!roll`")
        return True

    if cmd == "roll":
        with game_lock:
            g = games.get(room_id)
            if not g or g.state != 'playing': return True
            p = g.players[g.turn_idx]
            if str(p['uid']) != str(uid): return True
        utils.run_in_bg(process_turn, bot, room_id, uid)
        return True

    if cmd == "stop":
        with game_lock:
            if room_id in games: del games[room_id]
            bot.send_message(room_id, "🛑 Stopped.")
        return True
    return False

def process_turn(bot, room_id, uid):
    try:
        # 1. Illusion GIF (Faster)
        bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": DICE_GIF, "text": "Rolling"})
        time.sleep(2)
        
        dice = random.randint(1, 6)
        
        with game_lock:
            g = games.get(room_id)
            if not g: return
            g.last_interaction = time.time()
            res = g.move(g.turn_idx, dice)
            
            # Winner Logic
            if res == "win":
                w = g.players[g.turn_idx]['name']
                add_game_result(uid, w, "ludo", g.pot, True)
                bot.send_message(room_id, f"🏆 **{w} WINS!** +{g.pot}")
                del games[room_id]
                return
            
            msg = ""
            if res == "open": msg = "🔓 Unlocked!"
            elif res.startswith("kill"): msg = f"⚔️ Killed {res.split()[1]}!"
            elif res == "stuck": 
                g.next_turn()
            elif res == "bounce":
                g.next_turn()
            else:
                if dice != 6: g.next_turn()
                else: msg = "Roll again!"
            
            # 2. Send Dice (Static URL - No Upload)
            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": DICE_FACES[dice], "text": str(dice)})
            
            # 3. Draw & Upload Board
            img = draw_light_board(g.players, g.pot)
            link = utils.upload(bot, img)
            
            if link:
                bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Board"})
            
            if res != "win":
                nxt = g.players[g.turn_idx]['name']
                if msg: bot.send_message(room_id, msg)
                bot.send_message(room_id, f"👉 @{nxt}'s Turn")
                
    except Exception as e:
        print(f"Ludo Error: {e}")
