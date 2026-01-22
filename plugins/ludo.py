import sys
import os
import random
import time
import threading
import math
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

# Illusion GIF (Cached automatically by utils if used once)
DICE_GIF_URL = "https://media.tenor.com/2sWp_FhG2P4AAAAi/dice-roll.gif"
CACHED_GIF_LINK = None

# Config
SAFE_SPOTS = [0, 8, 13, 21, 26, 34, 39, 47] 
TIMEOUT_SECONDS = 45
PENALTY_AMOUNT = 2000

def setup(bot):
    global BOT_INSTANCE
    BOT_INSTANCE = bot
    print("[Ludo] Penalty Engine Loaded.")

# --- BACKGROUND MONITOR (TIMEOUTS & CLEANUP) ---
def game_monitor_loop():
    while True:
        time.sleep(5) # Check every 5 seconds
        if not games: continue
        
        now = time.time()
        to_remove = []
        
        with game_lock:
            for rid, g in list(games.items()):
                # 1. Check Turn Timeout
                if g.state == 'playing':
                    curr_p = g.players[g.turn_idx]
                    if curr_p and not curr_p['eliminated']:
                        # Agar 45 sec se jyada ho gaye
                        if now - g.turn_start_time > TIMEOUT_SECONDS:
                            # ELIMINATE PLAYER
                            curr_p['eliminated'] = True
                            
                            # Penalty
                            add_game_result(curr_p['uid'], curr_p['name'], "ludo_penalty", -PENALTY_AMOUNT, False)
                            
                            if BOT_INSTANCE:
                                BOT_INSTANCE.send_message(rid, f"⏰ **TIMEOUT!** @{curr_p['name']} eliminated & fined 2000 coins.")
                            
                            # Check active players
                            active = [p for p in g.players if p and not p['eliminated']]
                            if len(active) < 2:
                                # Game Over (Not enough players)
                                if len(active) == 1:
                                    winner = active[0]
                                    rew = g.pot
                                    add_game_result(winner['uid'], winner['name'], "ludo", rew, True)
                                    if BOT_INSTANCE:
                                        BOT_INSTANCE.send_message(rid, f"🏆 **{winner['name']} WINS** by default! (Others eliminated)")
                                to_remove.append(rid)
                            else:
                                # Next Turn
                                g.next_turn()
                                nxt = g.players[g.turn_idx]['name']
                                if BOT_INSTANCE:
                                    BOT_INSTANCE.send_message(rid, f"👉 Next Turn: @{nxt}")

                # 2. Check Stale Game (Agar game start hi nahi hua aur pada hai)
                if now - g.last_interaction > 300: # 5 Mins
                    to_remove.append(rid)

        # Cleanup dead games
        for rid in to_remove:
            if rid in games:
                del games[rid]
                if BOT_INSTANCE:
                    try: BOT_INSTANCE.send_message(rid, "🗑️ Game Closed.")
                    except: pass

if threading.active_count() < 10: 
    threading.Thread(target=game_monitor_loop, daemon=True).start()

# ==========================================
# 🎨 GRAPHICS ENGINE (With Name Tags)
# ==========================================

def get_coordinates(global_step, p_idx):
    # Ludo Path Logic
    main_path = [
        (1,6), (2,6), (3,6), (4,6), (5,6), (6,5), (6,4), (6,3), (6,2), (6,1), (6,0),
        (7,0), (8,0), (8,1), (8,2), (8,3), (8,4), (8,5), (8,6), (9,6), (10,6), (11,6), (12,6), (13,6), (14,6),
        (14,7), (14,8), (13,8), (12,8), (11,8), (10,8), (9,8), (8,8), (8,9), (8,10), (8,11), (8,12), (8,13), (8,14),
        (7,14), (6,14), (6,13), (6,12), (6,11), (6,10), (6,9), (6,8), (5,8), (4,8), (3,8), (2,8), (1,8), (0,8), (0,7)
    ]
    offset = p_idx * 13
    if global_step < 51: return main_path[(global_step + offset) % 52]
    else:
        home_step = global_step - 50
        if p_idx == 0: return (home_step, 7)
        if p_idx == 1: return (7, home_step)
        if p_idx == 2: return (14-home_step, 7)
        if p_idx == 3: return (7, 14-home_step)
    return (7,7)

def create_static_board(players, pot):
    CELL = 40
    W, H = CELL * 15, CELL * 15 + 80
    OY = 80
    img = utils.create_canvas(W, H, (35, 40, 45))
    d = ImageDraw.Draw(img)
    
    colors = {0:("#FF4444","#880000"), 1:("#44FF44","#008800"), 2:("#FFFF44","#888800"), 3:("#4444FF","#000088")}
    
    d.rectangle([0, OY, W, H], fill="white", outline="black", width=2)
    
    # BASES
    bases = [(0,0,0), (9,0,1), (9,9,2), (0,9,3)]
    for bx, by, pid in bases:
        x, y = bx*CELL, by*CELL + OY
        size = 6*CELL
        d.rectangle([x, y, x+size, y+size], fill=colors[pid][0], outline="black")
        d.rectangle([x+30, y+30, x+size-30, y+size-30], fill="white")
        
        p = players[pid]
        if p:
            # Avatar in Base
            if p.get('av_img'):
                try: img.paste(p['av_img'].resize((100, 100)), (x+70, y+70), p['av_img'].resize((100, 100)))
                except: pass
            utils.write_text(d, (x+size//2, y+size-25), f"@{p['name'][:8]}", size=18, align="center", col="black")
        else:
            utils.write_text(d, (x+size//2, y+size//2), "EMPTY", size=20, align="center", col="#AAA")

    # PATHS
    d.rectangle([6*CELL, OY, 9*CELL, 15*CELL+OY], fill="white")
    d.rectangle([0, 6*CELL+OY, 15*CELL, 9*CELL+OY], fill="white")
    d.rectangle([CELL, 7*CELL+OY, 6*CELL, 8*CELL+OY], fill=colors[0][0])
    d.rectangle([7*CELL, CELL+OY, 8*CELL, 6*CELL+OY], fill=colors[1][0])
    d.rectangle([9*CELL, 7*CELL+OY, 14*CELL, 8*CELL+OY], fill=colors[2][0])
    d.rectangle([7*CELL, 9*CELL+OY, 8*CELL, 14*CELL+OY], fill=colors[3][0])
    
    for i in range(16):
        d.line([i*CELL, OY, i*CELL, 15*CELL+OY], fill="black", width=1)
        d.line([0, i*CELL+OY, 15*CELL, i*CELL+OY], fill="black", width=1)

    # CENTER
    cx, cy = 7.5*CELL, 7.5*CELL + OY
    d.polygon([(6*CELL, 6*CELL+OY), (9*CELL, 6*CELL+OY), (cx, cy)], fill=colors[1][0], outline="black")
    d.polygon([(9*CELL, 6*CELL+OY), (9*CELL, 9*CELL+OY), (cx, cy)], fill=colors[2][0], outline="black")
    d.polygon([(9*CELL, 9*CELL+OY), (6*CELL, 9*CELL+OY), (cx, cy)], fill=colors[3][0], outline="black")
    d.polygon([(6*CELL, 9*CELL+OY), (6*CELL, 6*CELL+OY), (cx, cy)], fill=colors[0][0], outline="black")
    
    utils.write_text(d, (cx, cy-15), "POT", size=16, align="center", col="white", shadow=True)
    utils.write_text(d, (cx, cy+5), str(pot), size=20, align="center", col="#FFD700", shadow=True)
    return img

def draw_game_state(base_img, players):
    img = base_img.copy()
    d = ImageDraw.Draw(img)
    CELL = 40; OY = 80
    colors = ["#FF4444", "#44FF44", "#FFFF44", "#4444FF"]
    
    # Group tokens to handle overlap
    cell_occupants = {}
    for i, p in enumerate(players):
        if not p or p['pos'] == -1 or p['eliminated']: continue
        gx, gy = get_coordinates(p['pos'], i)
        if (gx, gy) not in cell_occupants: cell_occupants[(gx,gy)] = []
        cell_occupants[(gx,gy)].append(i)
        
    for (gx, gy), p_idxs in cell_occupants.items():
        base_x = gx * CELL + CELL//2
        base_y = gy * CELL + CELL//2 + OY
        
        for idx, p_idx in enumerate(p_idxs):
            # Shift if overlapping
            shift = (idx - (len(p_idxs)-1)/2) * 10
            tx, ty = base_x + shift, base_y - shift
            p = players[p_idx]
            
            # 1. Token Circle
            d.ellipse([tx-16, ty-16, tx+16, ty+16], fill=colors[p_idx], outline="white", width=2)
            
            # 2. Avatar Inside
            if p.get('av_img'):
                try: 
                    mini = p['av_img'].resize((24, 24))
                    img.paste(mini, (int(tx-12), int(ty-12)), mini)
                except: pass
                
            # 3. Name Tag (Small text above token)
            utils.write_text(d, (tx, ty-25), p['name'][:4], size=14, align="center", col="black", shadow=False)

    # Header Status
    turn_p = next((p for p in players if p and p['turn']), None)
    if turn_p:
        utils.write_text(d, (img.width//2, 40), f"Turn: @{turn_p['name']} (45s)", size=30, align="center", col="white", shadow=True)

    return img

# ==========================================
# ⚙️ LOGIC
# ==========================================

class LudoGame:
    def __init__(self, room_id, bet):
        self.room_id = room_id
        self.bet = bet
        self.pot = 0
        self.players = [None] * 4
        self.state = 'waiting'
        self.turn_idx = 0
        self.last_interaction = time.time()
        self.turn_start_time = 0 # For timeout
        self.base_board_cache = None
        
    def add_player(self, uid, name, av_url):
        for i in range(4):
            if self.players[i] is None:
                # Pre-download Avatar
                av_img = utils.get_circle_avatar(av_url, size=150)
                self.players[i] = {
                    'id': i, 'uid': uid, 'name': name, 'av_img': av_img,
                    'pos': -1, 'turn': False, 'eliminated': False
                }
                self.pot += self.bet
                return i
        return -1

    def start_game(self):
        self.state = 'playing'
        self.players[0]['turn'] = True
        self.turn_start_time = time.time() # Start timer
        self.base_board_cache = create_static_board(self.players, self.pot)

    def next_turn(self):
        start = self.turn_idx
        while True:
            self.turn_idx = (self.turn_idx + 1) % 4
            p = self.players[self.turn_idx]
            # Skip if empty or eliminated
            if p and not p['eliminated']:
                for pl in self.players: 
                    if pl: pl['turn'] = False
                p['turn'] = True
                self.turn_start_time = time.time() # Reset Timer
                return p
            if self.turn_idx == start: return None

    def move_token(self, p_idx, dice):
        p = self.players[p_idx]
        if p['pos'] == -1:
            if dice == 6: p['pos'] = 0; return "open"
            return "stuck"
        new_pos = p['pos'] + dice
        if new_pos == 56: p['pos'] = 56; return "win"
        if new_pos > 56: return "bounce"
        
        # Kill Logic
        my_gx, my_gy = get_coordinates(new_pos, p_idx)
        killed = None
        if new_pos not in SAFE_SPOTS:
            for i, enemy in enumerate(self.players):
                if enemy and i != p_idx and enemy['pos'] > -1 and enemy['pos'] < 51 and not enemy['eliminated']:
                    en_gx, en_gy = get_coordinates(enemy['pos'], i)
                    if my_gx == en_gx and my_gy == en_gy:
                        enemy['pos'] = -1; killed = enemy['name']
        p['pos'] = new_pos
        return f"kill {killed}" if killed else "move"

def handle_command(bot, command, room_id, user, args, data):
    uid = data.get('userid', user)
    av_url = f"https://cdn.howdies.app/avatar?image={data.get('avatar')}" if data.get('avatar') else None
    cmd = command.lower().strip()
    
    # 1. CREATE
    if cmd == "ludo":
        bet = int(args[0]) if args and args[0].isdigit() else 0
        with game_lock:
            if room_id in games: return True
            g = LudoGame(room_id, bet)
            g.add_player(uid, user, av_url)
            if bet > 0: add_game_result(uid, user, "ludo", -bet, False)
            games[room_id] = g
        bot.send_message(room_id, f"🎲 **Ludo!** Bet: {bet}\nWaiting for players... `!join`")
        return True

    # 2. JOIN
    if cmd == "join":
        with game_lock:
            g = games.get(room_id)
            if not g or g.state != 'waiting': return False
            if any(p and str(p['uid']) == str(uid) for p in g.players): return True
            idx = g.add_player(uid, user, av_url)
            if idx != -1:
                if g.bet > 0: add_game_result(uid, user, "ludo", -g.bet, False)
                bot.send_message(room_id, f"✅ **{user}** Joined!")
        return True

    # 3. START
    if cmd == "start":
        with game_lock:
            g = games.get(room_id)
            if not g or g.state != 'waiting': return False
            if sum(1 for p in g.players if p) < 2:
                bot.send_message(room_id, "⚠️ Need 2 players.")
                return True
            g.start_game()
            
            # Cache Illusion GIF once
            global CACHED_GIF_LINK
            if not CACHED_GIF_LINK:
                # Mock upload or use direct URL if supported (Assuming Utils handles URL or Bytes)
                # Since utils.upload expects bytes, we can skip if using direct URL.
                # If bot supports direct URL in JSON, we use DICE_GIF_URL.
                pass

            link = utils.upload(bot, draw_game_state(g.base_board_cache, g.players))
            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Start"})
            bot.send_message(room_id, f"🚦 Go! @{g.players[0]['name']} `!roll`")
        return True

    # 4. ROLL
    if cmd == "roll":
        with game_lock:
            g = games.get(room_id)
            if not g or g.state != 'playing': return True
            curr = g.players[g.turn_idx]
            if str(curr['uid']) != str(uid): return True
            
        utils.run_in_bg(process_turn, bot, room_id, uid)
        return True

    # 5. STOP
    if cmd == "stop":
        with game_lock:
            if room_id in games: del games[room_id]
            bot.send_message(room_id, "🛑 Stopped.")
        return True
    return False

def process_turn(bot, room_id, uid):
    # 1. Illusion GIF (No Dice Image, just GIF)
    bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": DICE_GIF_URL, "text": "Rolling"})
    time.sleep(2)
    
    dice = random.randint(1, 6)
    
    with game_lock:
        g = games.get(room_id)
        if not g: return
        g.last_interaction = time.time() # Update activity
        
        result = g.move_token(g.turn_idx, dice)
        
        # 2. Text Result (Dice Number)
        bot.send_message(room_id, f"🎲 **Rolled: {dice}**")
        
        if result == "win":
            w = g.players[g.turn_idx]['name']
            add_game_result(uid, w, "ludo", g.pot, True)
            bot.send_message(room_id, f"🏆 **{w} WINS!** +{g.pot} Coins")
            del games[room_id]
            return
            
        msg = ""
        if result == "open": msg = "🔓 Unlocked!"
        elif result.startswith("kill"): msg = f"⚔️ Killed {result.split()[1]}!"
        elif result == "stuck": 
            g.next_turn()
        elif result == "bounce":
            msg = "Bounce."
            g.next_turn()
        else:
            if dice != 6: g.next_turn()
            else: msg = "Roll again!"
            
        # 3. Board Update
        link = utils.upload(bot, draw_game_state(g.base_board_cache, g.players))
        bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Board"})
        
        if result != "win":
            nxt = g.players[g.turn_idx]['name']
            extra = f"\n{msg}" if msg else ""
            bot.send_message(room_id, f"👉 @{nxt}'s Turn {extra}")
