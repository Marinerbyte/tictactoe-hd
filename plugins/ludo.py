import sys
import os
import random
import time
import threading
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

# Assets
DICE_GIF = "https://media.tenor.com/2sWp_FhG2P4AAAAi/dice-roll.gif"
SAFE_SPOTS = [0, 8, 13, 21, 26, 34, 39, 47] 
TIMEOUT_SECONDS = 45
PENALTY = 2000

def setup(bot):
    global BOT_INSTANCE
    BOT_INSTANCE = bot
    print("[Ludo] Final Stable Engine Loaded.")

# --- MONITOR (TIMEOUTS) ---
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
                    # Timeout Logic
                    if curr and not curr['eliminated']:
                        if now - g.turn_start_time > TIMEOUT_SECONDS:
                            curr['eliminated'] = True
                            if BOT_INSTANCE:
                                BOT_INSTANCE.send_message(rid, f"⏰ **TIMEOUT!** @{curr['name']} eliminated! (-{PENALTY})")
                                add_game_result(curr['uid'], curr['name'], "ludo_penalty", -PENALTY, False)
                            
                            # Check active
                            active = [p for p in g.players if p and not p['eliminated']]
                            if len(active) < 2:
                                if len(active) == 1:
                                    w = active[0]
                                    add_game_result(w['uid'], w['name'], "ludo", g.pot, True)
                                    if BOT_INSTANCE: BOT_INSTANCE.send_message(rid, f"🏆 **{w['name']} WINS!** (Others left)")
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
# 🎨 GRAPHICS ENGINE (Fresh Draw Every Time)
# ==========================================

def get_coords(step, p_idx):
    # Fixed Path Logic
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

def draw_board_fresh(players, pot):
    """Draws the ENTIRE board from scratch (No Caching issues)"""
    CELL = 40
    W, H = CELL*15, CELL*15 + 80
    OY = 80
    
    img = utils.create_canvas(W, H, (35, 40, 45))
    d = ImageDraw.Draw(img)
    
    colors = {0:("#FF4444","#880000"), 1:("#44FF44","#008800"), 2:("#FFFF44","#888800"), 3:("#4444FF","#000088")}
    
    # 1. Background Grid
    d.rectangle([0, OY, W, H], fill="white", outline="black", width=2)
    
    # 2. Bases
    bases = [(0,0,0), (9,0,1), (9,9,2), (0,9,3)]
    for bx, by, pid in bases:
        x, y = bx*CELL, by*CELL+OY
        size = 6*CELL
        d.rectangle([x, y, x+size, y+size], fill=colors[pid][0], outline="black")
        d.rectangle([x+30, y+30, x+size-30, y+size-30], fill="white")
        p = players[pid]
        if p:
            if p.get('av_img'):
                try: 
                    # Resize fresh every time
                    av = p['av_img'].resize((100, 100))
                    img.paste(av, (x+70, y+70), av)
                except: pass
            utils.write_text(d, (x+size//2, y+size-25), f"@{p['name'][:8]}", size=18, align="center", col="black")
        else:
            utils.write_text(d, (x+size//2, y+size//2), "EMPTY", size=20, align="center", col="#AAA")

    # 3. Path Colors
    # Red(Left), Green(Top), Yellow(Right), Blue(Bottom)
    d.rectangle([CELL, 7*CELL+OY, 6*CELL, 8*CELL+OY], fill=colors[0][0])
    d.rectangle([7*CELL, CELL+OY, 8*CELL, 6*CELL+OY], fill=colors[1][0])
    d.rectangle([9*CELL, 7*CELL+OY, 14*CELL, 8*CELL+OY], fill=colors[2][0])
    d.rectangle([7*CELL, 9*CELL+OY, 8*CELL, 14*CELL+OY], fill=colors[3][0])
    
    # Grid Lines
    for i in range(16):
        d.line([i*CELL, OY, i*CELL, 15*CELL+OY], fill="black")
        d.line([0, i*CELL+OY, 15*CELL, i*CELL+OY], fill="black")

    # 4. Center Home
    cx, cy = 7.5*CELL, 7.5*CELL+OY
    d.polygon([(6*CELL, 6*CELL+OY), (9*CELL, 6*CELL+OY), (cx, cy)], fill=colors[1][0], outline="black")
    d.polygon([(9*CELL, 6*CELL+OY), (9*CELL, 9*CELL+OY), (cx, cy)], fill=colors[2][0], outline="black")
    d.polygon([(9*CELL, 9*CELL+OY), (6*CELL, 9*CELL+OY), (cx, cy)], fill=colors[3][0], outline="black")
    d.polygon([(6*CELL, 9*CELL+OY), (6*CELL, 6*CELL+OY), (cx, cy)], fill=colors[0][0], outline="black")
    
    utils.write_text(d, (cx, cy-15), "POT", size=16, align="center", col="white", shadow=True)
    utils.write_text(d, (cx, cy+5), str(pot), size=20, align="center", col="#FFD700", shadow=True)

    # 5. Tokens
    occupants = {}
    for i, p in enumerate(players):
        if not p or p['pos'] == -1 or p['eliminated']: continue
        gx, gy = get_coords(p['pos'], i)
        key = (gx, gy)
        if key not in occupants: occupants[key] = []
        occupants[key].append(i)
        
    for (gx, gy), p_idxs in occupants.items():
        bx = gx * CELL + CELL//2
        by = gy * CELL + CELL//2 + OY
        
        for idx, p_idx in enumerate(p_idxs):
            shift = (idx - (len(p_idxs)-1)/2) * 10
            tx, ty = bx + shift, by - shift
            
            # Token
            d.ellipse([tx-16, ty-16, tx+16, ty+16], fill=colors[p_idx][0], outline="white", width=2)
            # Mini Avatar
            p = players[p_idx]
            if p.get('av_img'):
                try:
                    mini = p['av_img'].resize((24, 24))
                    img.paste(mini, (int(tx-12), int(ty-12)), mini)
                except: pass

    # 6. Header
    turn_p = next((p for p in players if p and p['turn']), None)
    status = f"Turn: @{turn_p['name']}" if turn_p else "Game Over"
    utils.write_text(d, (W//2, 40), status, size=28, align="center", col="white", shadow=True)
    
    return img

# ==========================================
# ⚙️ LOGIC
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
        
    def add_player(self, uid, name, av_url):
        for i in range(4):
            if self.players[i] is None:
                # Pre-fetch avatar
                av = utils.get_circle_avatar(av_url, size=150)
                self.players[i] = {'id': i, 'uid': uid, 'name': name, 'av_img': av, 'pos': -1, 'turn': False, 'eliminated': False}
                self.pot += self.bet
                return i
        return -1

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
        
        # Kill
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
    av = f"https://cdn.howdies.app/avatar?image={data.get('avatar')}" if data.get('avatar') else None
    cmd = command.lower().strip()
    
    if cmd == "ludo":
        bet = int(args[0]) if args and args[0].isdigit() else 0
        with game_lock:
            if room_id in games: return True
            g = LudoGame(room_id, bet)
            g.add_player(uid, user, av)
            if bet > 0: add_game_result(uid, user, "ludo", -bet, False)
            games[room_id] = g
        bot.send_message(room_id, f"🎲 **Ludo!** Bet: {bet}\n`!join` to enter.")
        return True

    if cmd == "join":
        with game_lock:
            g = games.get(room_id)
            if not g or g.state != 'waiting': return False
            if any(p and str(p['uid']) == str(uid) for p in g.players): return True
            idx = g.add_player(uid, user, av)
            if idx != -1:
                if g.bet > 0: add_game_result(uid, user, "ludo", -g.bet, False)
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
            g.turn_start_time = time.time()
            
            # Initial Board
            img = draw_board_fresh(g.players, g.pot)
            link = utils.upload(bot, img)
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
        # 1. Illusion GIF (Text/JSON directly)
        bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": DICE_GIF, "text": "Rolling"})
        time.sleep(2)
        
        dice = random.randint(1, 6)
        
        with game_lock:
            g = games.get(room_id)
            if not g: return
            g.last_interaction = time.time()
            
            res = g.move(g.turn_idx, dice)
            
            # Winner?
            if res == "win":
                w = g.players[g.turn_idx]['name']
                add_game_result(uid, w, "ludo", g.pot, True)
                bot.send_message(room_id, f"🏆 **{w} WINS!** +{g.pot}")
                del games[room_id]
                return
            
            msg = f"🎲 **Rolled {dice}**. "
            if res == "open": msg += "🔓 Unlocked!"
            elif res.startswith("kill"): msg += f"⚔️ Killed {res.split()[1]}!"
            elif res == "stuck": 
                msg += "Locked."
                g.next_turn()
            elif res == "bounce":
                msg += "Bounce."
                g.next_turn()
            else:
                if dice != 6: g.next_turn()
                else: msg += "Roll again!"
            
            # 2. Draw Fresh Board
            img = draw_board_fresh(g.players, g.pot)
            link = utils.upload(bot, img)
            
            if link:
                bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Board"})
            else:
                bot.send_message(room_id, "❌ Board Upload Failed.")
                
            if res != "win":
                nxt = g.players[g.turn_idx]['name']
                bot.send_message(room_id, f"{msg}\n👉 @{nxt}")
                
    except Exception as e:
        print(f"Ludo Error: {e}")
