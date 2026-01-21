import sys
import os
import random
import time
import threading
import math
from io import BytesIO
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

# Assets
DICE_GIF = "https://media.tenor.com/2sWp_FhG2P4AAAAi/dice-roll.gif"

# Configuration
SAFE_SPOTS = [0, 8, 13, 21, 26, 34, 39, 47] # Global Step Indices
PATH_LENGTH = 52

def setup(bot):
    global BOT_INSTANCE
    BOT_INSTANCE = bot
    print("[Ludo] Pro Engine Loaded.")

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
# 🗺️ MAPPING ENGINE (Coordinate System)
# ==========================================

def get_coordinates(global_step, p_idx):
    """
    Returns (Column, Row) for 15x15 Grid.
    0,0 is Top-Left.
    """
    # Standard Ludo Path (Red Start Perspective)
    # This path assumes Red starts at index 0 (coords 1,6)
    # The path loops clockwise around the center.
    main_path = [
        (1,6), (2,6), (3,6), (4,6), (5,6), # 0-4
        (6,5), (6,4), (6,3), (6,2), (6,1), (6,0), # 5-10
        (7,0), (8,0), # 11-12
        (8,1), (8,2), (8,3), (8,4), (8,5), (8,6), # 13-18
        (9,6), (10,6), (11,6), (12,6), (13,6), (14,6), # 19-24
        (14,7), (14,8), # 25-26
        (13,8), (12,8), (11,8), (10,8), (9,8), (8,8), # 27-32
        (8,9), (8,10), (8,11), (8,12), (8,13), (8,14), # 33-38
        (7,14), (6,14), # 39-40
        (6,13), (6,12), (6,11), (6,10), (6,9), (6,8), # 41-46
        (5,8), (4,8), (3,8), (2,8), (1,8), (0,8), # 47-52
        (0,7) # 51 (Last step before home turn)
    ]
    
    # Offsets: Red=0, Green=13, Yellow=26, Blue=39
    offset = p_idx * 13
    
    if global_step < 51:
        # Main Track
        actual_idx = (global_step + offset) % 52
        return main_path[actual_idx]
    else:
        # Home Stretch (Inside)
        home_step = global_step - 50 # 1 to 6
        if p_idx == 0: return (home_step, 7) # Red (Right)
        if p_idx == 1: return (7, home_step) # Green (Down)
        if p_idx == 2: return (14-home_step, 7) # Yellow (Left)
        if p_idx == 3: return (7, 14-home_step) # Blue (Up)
        
    return (7,7) # Winner Center

# ==========================================
# 🎨 GRAPHICS ENGINE
# ==========================================

def draw_dice(number):
    """Draws a 3D looking dice"""
    size = 150
    img = Image.new("RGBA", (size, size), (0,0,0,0))
    d = ImageDraw.Draw(img)
    
    # 3D Box
    d.rounded_rectangle([10, 10, 140, 140], radius=20, fill="#FFF", outline="#888", width=2)
    # Bevel/Shadow
    d.rounded_rectangle([15, 120, 135, 140], radius=10, fill="#CCC") 
    
    dots = []
    c = size // 2
    l = size // 3.5
    r = size - l
    
    if number == 1: dots = [(c, c)]
    elif number == 2: dots = [(l, l), (r, r)]
    elif number == 3: dots = [(l, l), (c, c), (r, r)]
    elif number == 4: dots = [(l, l), (r, l), (l, r), (r, r)]
    elif number == 5: dots = [(l, l), (r, l), (c, c), (l, r), (r, r)]
    elif number == 6: dots = [(l, l), (r, l), (l, c), (r, c), (l, r), (r, r)]
    
    for x, y in dots:
        d.ellipse([x-12, y-12, x+12, y+12], fill="black")
        
    return img

def draw_board(players, pot):
    CELL = 40
    W, H = CELL * 15, CELL * 15 + 80 # Extra space for header
    OY = 80 # Offset Y
    
    img = utils.create_canvas(W, H, (35, 40, 45))
    d = ImageDraw.Draw(img)
    
    # 1. Base Colors
    colors = {
        0: ("#FF4444", "#880000"), # Red
        1: ("#44FF44", "#008800"), # Green
        2: ("#FFFF44", "#888800"), # Yellow
        3: ("#4444FF", "#000088")  # Blue
    }
    
    # 2. Draw 4 Bases
    # TL, TR, BR, BL
    base_positions = [(0,0,0), (9,0,1), (9,9,2), (0,9,3)]
    for bx, by, pid in base_positions:
        x, y = bx*CELL, by*CELL + OY
        size = 6*CELL
        d.rectangle([x, y, x+size, y+size], fill=colors[pid][0], outline="black")
        d.rectangle([x+30, y+30, x+size-30, y+size-30], fill="white")
        
        # Draw Big Avatar if player in base
        p = players[pid]
        if p:
            if p['pos'] == -1: # In Base
                if p['av']:
                    av = utils.get_circle_avatar(p['av'], size=100)
                    if av: img.paste(av, (x+70, y+70), av)
            utils.write_text(d, (x+size//2, y+size-25), f"@{p['name'][:8]}", size=18, align="center", col="black")
        else:
            utils.write_text(d, (x+size//2, y+size//2), "EMPTY", size=20, align="center", col="#AAA")

    # 3. Draw Paths (The Cross)
    # Vertical Strip
    d.rectangle([6*CELL, OY, 9*CELL, 15*CELL+OY], fill="white")
    # Horizontal Strip
    d.rectangle([0, 6*CELL+OY, 15*CELL, 9*CELL+OY], fill="white")
    
    # Colored Home Paths
    # Red (Left)
    d.rectangle([CELL, 7*CELL+OY, 6*CELL, 8*CELL+OY], fill=colors[0][0])
    # Green (Top)
    d.rectangle([7*CELL, CELL+OY, 8*CELL, 6*CELL+OY], fill=colors[1][0])
    # Yellow (Right)
    d.rectangle([9*CELL, 7*CELL+OY, 14*CELL, 8*CELL+OY], fill=colors[2][0])
    # Blue (Bottom)
    d.rectangle([7*CELL, 9*CELL+OY, 8*CELL, 14*CELL+OY], fill=colors[3][0])
    
    # Grid Lines
    for i in range(16):
        # Vertical lines
        d.line([i*CELL, OY, i*CELL, 15*CELL+OY], fill="black", width=1)
        # Horizontal lines
        d.line([0, i*CELL+OY, 15*CELL, i*CELL+OY], fill="black", width=1)

    # 4. Center Home (Triangles)
    cx, cy = 7.5*CELL, 7.5*CELL + OY
    d.polygon([(6*CELL, 6*CELL+OY), (9*CELL, 6*CELL+OY), (cx, cy)], fill=colors[1][0], outline="black")
    d.polygon([(9*CELL, 6*CELL+OY), (9*CELL, 9*CELL+OY), (cx, cy)], fill=colors[2][0], outline="black")
    d.polygon([(9*CELL, 9*CELL+OY), (6*CELL, 9*CELL+OY), (cx, cy)], fill=colors[3][0], outline="black")
    d.polygon([(6*CELL, 9*CELL+OY), (6*CELL, 6*CELL+OY), (cx, cy)], fill=colors[0][0], outline="black")
    
    # Pot Info
    utils.write_text(d, (cx, cy-15), "POT", size=16, align="center", col="white", shadow=True)
    utils.write_text(d, (cx, cy+5), str(pot), size=20, align="center", col="#FFD700", shadow=True)

    # 5. Tokens (The Important Part)
    # Calculate overlaps first
    cell_occupants = {}
    for i, p in enumerate(players):
        if not p or p['pos'] == -1: continue # Ignore base players
        
        gx, gy = get_coordinates(p['pos'], i)
        key = (gx, gy)
        if key not in cell_occupants: cell_occupants[key] = []
        cell_occupants[key].append(i)
        
    # Render Tokens
    for (gx, gy), p_idxs in cell_occupants.items():
        base_x = gx * CELL + CELL//2
        base_y = gy * CELL + CELL//2 + OY
        
        count = len(p_idxs)
        offset_step = 10
        
        for idx, p_idx in enumerate(p_idxs):
            # Calculate Shift for overlap
            shift = (idx - (count-1)/2) * offset_step
            tx = base_x + shift
            ty = base_y - shift # Diagonal shift
            
            p = players[p_idx]
            col = colors[p_idx][0]
            
            # Token Body (Pin Shape)
            d.ellipse([tx-16, ty-16, tx+16, ty+16], fill=col, outline="white", width=2)
            
            # Mini Avatar inside
            if p['av']:
                mini_av = utils.get_circle_avatar(p['av'], size=24)
                if mini_av: img.paste(mini_av, (int(tx-12), int(ty-12)), mini_av)

    # 6. Header Status
    utils.write_text(d, (W//2, 25), "🎲 LUDO: ONE TOKEN", size=30, align="center", col="#FFD700", shadow=True)
    
    turn_p = next((p for p in players if p and p['turn']), None)
    if turn_p:
        utils.write_text(d, (W//2, 55), f"Turn: @{turn_p['name']}", size=20, align="center", col="white")

    return img

# ==========================================
# ⚙️ GAME LOGIC
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
        
    def add_player(self, uid, name, av):
        for i in range(4):
            if self.players[i] is None:
                self.players[i] = {
                    'id': i, 'uid': uid, 'name': name, 'av': av,
                    'pos': -1, 'turn': False
                }
                self.pot += self.bet
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
        
        # Unlock logic
        if p['pos'] == -1:
            if dice == 6:
                p['pos'] = 0 # Start
                return "open"
            return "stuck"
            
        new_pos = p['pos'] + dice
        
        # Victory check
        if new_pos == 56: 
            p['pos'] = 56
            return "win"
        if new_pos > 56: return "bounce"
        
        # Kill Logic
        # Calculate my global grid index
        my_gx, my_gy = get_coordinates(new_pos, p_idx)
        
        killed = None
        # Check collision with others
        for i, enemy in enumerate(self.players):
            if enemy and i != p_idx and enemy['pos'] > -1 and enemy['pos'] < 51:
                en_gx, en_gy = get_coordinates(enemy['pos'], i)
                
                # If coords match
                if my_gx == en_gx and my_gy == en_gy:
                    # Check Safe Spot
                    # Is this coord a safe spot?
                    # Safe spots global indices for P0: 0, 8, 13...
                    # It's hard to map back. Let's simplify:
                    # If steps match safe indices relative to start.
                    # Standard safe indices from start: 0, 8, 13, 21...
                    
                    is_safe = False
                    # Safe spots relative to anyone's start
                    if new_pos in [0, 8, 13, 21, 26, 34, 39, 47]: is_safe = True
                    
                    if not is_safe:
                        enemy['pos'] = -1 # Send Home
                        killed = enemy['name']
        
        p['pos'] = new_pos
        return f"kill {killed}" if killed else "move"

def handle_command(bot, command, room_id, user, args, data):
    uid = data.get('userid', user)
    av_file = data.get("avatar")
    av = f"https://cdn.howdies.app/avatar?image={av_file}" if av_file else None
    cmd = command.lower().strip()
    
    # 1. CREATE
    if cmd == "ludo":
        bet = int(args[0]) if args and args[0].isdigit() else 0
        with game_lock:
            if room_id in games: return True
            g = LudoGame(room_id, bet)
            g.add_player(uid, user, av)
            if bet > 0: add_game_result(uid, user, "ludo", -bet, False)
            games[room_id] = g
        bot.send_message(room_id, f"🎲 **Ludo Created!** Bet: {bet}\nWaiting for players... `!join`")
        return True

    # 2. JOIN
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

    # 3. START
    if cmd == "start":
        with game_lock:
            g = games.get(room_id)
            if not g or g.state != 'waiting': return False
            if sum(1 for p in g.players if p) < 2:
                bot.send_message(room_id, "⚠️ Need 2 players.")
                return True
            g.state = 'playing'
            g.players[0]['turn'] = True
            
            link = utils.upload(bot, draw_board(g.players, g.pot))
            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Start"})
            bot.send_message(room_id, f"🚦 Go! @{g.players[0]['name']} `!roll`")
        return True

    # 4. ROLL
    if cmd == "roll":
        # Turn Check
        with game_lock:
            g = games.get(room_id)
            if not g or g.state != 'playing': return True
            if str(g.players[g.turn_idx]['uid']) != str(uid): return True
            
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
    # 1. Illusion (GIF)
    bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": DICE_GIF, "text": "Rolling"})
    time.sleep(2.5)
    
    dice = random.randint(1, 6)
    
    with game_lock:
        g = games.get(room_id)
        if not g: return
        
        # 2. Logic
        result = g.move_token(g.turn_idx, dice)
        
        # 3. Send Dice Image
        dice_img = draw_dice(dice)
        dice_link = utils.upload(bot, dice_img)
        bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": dice_link, "text": str(dice)})
        
        # Win Check
        if result == "win":
            winner = g.players[g.turn_idx]['name']
            add_game_result(uid, winner, "ludo", g.pot, True)
            bot.send_message(room_id, f"🏆 **{winner} WINS!** +{g.pot}")
            del games[room_id]
            return
            
        # Msg
        msg = f"Rolled {dice}. "
        if result == "open": msg += "🔓 Unlocked!"
        elif result.startswith("kill"): msg += f"⚔️ Killed {result.split()[1]}!"
        elif result == "stuck": 
            msg += "Locked."
            g.next_turn()
        elif result == "bounce":
            msg += "Too high."
            g.next_turn()
        else:
            if dice != 6: g.next_turn()
            else: msg += "Roll again!"
            
        # 4. Board Update
        link = utils.upload(bot, draw_board(g.players, g.pot))
        bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Board"})
        
        if result != "win":
            nxt = g.players[g.turn_idx]['name']
            bot.send_message(room_id, f"{msg}\n👉 @{nxt}")
