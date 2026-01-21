import sys
import os
import random
import time
import threading
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

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
DICE_GIF = "https://media.tenor.com/2sWp_FhG2P4AAAAi/dice-roll.gif" # Rolling animation
DICE_FACES = {
    1: "https://img.icons8.com/3d-fluency/512/1-circle.png",
    2: "https://img.icons8.com/3d-fluency/512/2-circle.png",
    3: "https://img.icons8.com/3d-fluency/512/3-circle.png",
    4: "https://img.icons8.com/3d-fluency/512/4-circle.png",
    5: "https://img.icons8.com/3d-fluency/512/5-circle.png",
    6: "https://img.icons8.com/3d-fluency/512/6-circle.png"
}

# Config
SAFE_SPOTS = [0, 8, 13, 21, 26, 34, 39, 47] # Star positions (Global Index)
TOTAL_STEPS = 51
HOME_STRETCH = 5 # Steps inside home

def setup(bot):
    global BOT_INSTANCE
    BOT_INSTANCE = bot
    print("[Ludo] One-Token Engine Loaded.")

# --- CLEANUP ---
def game_cleanup_loop():
    while True:
        time.sleep(10); now = time.time(); to_remove = []
        with game_lock:
            for rid, g in games.items():
                if now - g.last_interaction > 300: to_remove.append(rid) # 5 Mins timeout
        for rid in to_remove:
            if BOT_INSTANCE:
                try: BOT_INSTANCE.send_message(rid, "⌛ Ludo Timeout! Game closed.")
                except: pass
            with game_lock:
                if rid in games: del games[rid]

if threading.active_count() < 10: threading.Thread(target=game_cleanup_loop, daemon=True).start()

# ==========================================
# 🗺️ MAPPING ENGINE (The Brain of Board)
# ==========================================

# Standard Ludo Path Coordinates (15x15 Grid)
# 0,0 is Top-Left. Units are blocks.
def get_coordinates(global_step, color_idx):
    """
    Converts logical step (0-56) to (x, y) grid coordinates (0-14).
    """
    # Base Path (Red's Perspective - Starts at 1,6)
    # This is a hardcoded path for a standard Ludo board
    # Path sequence for Red (0 to 50)
    # 0 is the start point.
    path_map = [
        (1,6), (2,6), (3,6), (4,6), (5,6), # 0-4
        (6,5), (6,4), (6,3), (6,2), (6,1), (6,0), # 5-10
        (7,0), # 11 (Middle turn)
        (8,0), (8,1), (8,2), (8,3), (8,4), (8,5), # 12-17
        (9,6), (10,6), (11,6), (12,6), (13,6), (14,6), # 18-23
        (14,7), # 24 (Middle bottom)
        (14,8), (13,8), (12,8), (11,8), (10,8), (9,8), # 25-30
        (8,9), (8,10), (8,11), (8,12), (8,13), (8,14), # 31-36
        (7,14), # 37 (Middle right)
        (6,14), (6,13), (6,12), (6,11), (6,10), (6,9), # 38-43
        (5,8), (4,8), (3,8), (2,8), (1,8), (0,8), # 44-49
        (0,7) # 50 (Before Home)
    ]
    
    # Offsets for other colors (Rotation)
    # Red(0)=0, Green(1)=13, Yellow(2)=26, Blue(3)=39
    offset = color_idx * 13
    
    # Calculate actual index on the shared path
    if global_step < 51:
        # Standard Path
        actual_idx = (global_step + offset) % 52
        return path_map[actual_idx]
    else:
        # Home Stretch (Inside)
        home_steps = global_step - 50
        if color_idx == 0: return (home_steps, 7) # Red goes Right
        if color_idx == 1: return (7, home_steps) # Green goes Down
        if color_idx == 2: return (14-home_steps, 7) # Yellow goes Left
        if color_idx == 3: return (7, 14-home_steps) # Blue goes Up
    
    return (7,7) # Center (Winner)

# ==========================================
# 🎨 GRAPHICS ENGINE (The Artist)
# ==========================================

def draw_ludo_board(players):
    """
    Generates a High-Definition Realistic Ludo Board.
    """
    # Canvas Size
    CELL = 50
    W, H = CELL * 15, CELL * 15 + 100 # +100 for Header
    BOARD_SIZE = CELL * 15
    
    img = utils.create_canvas(W, H, (30, 30, 35))
    d = ImageDraw.Draw(img)
    
    # 1. BOARD BASE (Wood/Plastic Texture)
    board_rect = [0, 100, BOARD_SIZE, 100 + BOARD_SIZE]
    d.rectangle(board_rect, fill="white", outline="black", width=2)
    
    # 2. DRAW BASES (The 4 Corners)
    colors = {
        0: ("#FF4500", "#FFD700"), # Red
        1: ("#32CD32", "#ADFF2F"), # Green
        2: ("#FFD700", "#FFFFE0"), # Yellow
        3: ("#1E90FF", "#87CEFA")  # Blue
    }
    
    bases = [
        (0,0, "Red"), (9,0, "Green"), (9,9, "Yellow"), (0,9, "Blue")
    ]
    
    # Offset for top header
    OY = 100 
    
    for i, (bx, by, name) in enumerate(bases):
        x = bx * CELL
        y = by * CELL + OY
        size = 6 * CELL
        col_main = colors[i][0]
        col_light = colors[i][1]
        
        # Base Box
        d.rectangle([x, y, x+size, y+size], fill=col_main, outline="black", width=2)
        # Inner White Box
        d.rectangle([x+CELL, y+CELL, x+size-CELL, y+size-CELL], fill="white", outline="black", width=2)
        
        # Player Info inside Base
        p = players[i]
        if p:
            # Stamp Username
            utils.write_text(d, (x + size//2, y + size - 30), f"@{p['name'][:8]}", size=20, align="center", col="black", shadow=False)
            # Avatar (Big)
            if p['av']:
                av = utils.get_circle_avatar(p['av'], size=100)
                if av: img.paste(av, (x + size//2 - 50, y + size//2 - 50), av)
        else:
            utils.write_text(d, (x + size//2, y + size//2), "Empty", size=30, align="center", col="#AAA")

    # 3. DRAW GRID & PATHS
    # Grid lines
    for i in range(15):
        for j in range(15):
            # Only draw if not in base area
            in_base = (i<6 and j<6) or (i>8 and j<6) or (i>8 and j>8) or (i<6 and j>8)
            if not in_base:
                px, py = i*CELL, j*CELL + OY
                d.rectangle([px, py, px+CELL, py+CELL], outline="black", width=1)
                
                # Color Home Stretch
                # Red Home
                if j==7 and 0 < i < 6: d.rectangle([px, py, px+CELL, py+CELL], fill=colors[0][0], outline="black")
                # Green Home
                if i==7 and 0 < j < 6: d.rectangle([px, py, px+CELL, py+CELL], fill=colors[1][0], outline="black")
                # Yellow Home
                if j==7 and 8 < i < 14: d.rectangle([px, py, px+CELL, py+CELL], fill=colors[2][0], outline="black")
                # Blue Home
                if i==7 and 8 < j < 14: d.rectangle([px, py, px+CELL, py+CELL], fill=colors[3][0], outline="black")

    # 4. START POINTS & SAFE SPOTS (Stars)
    # Red Start: (1,6), Green: (8,1), Yellow: (13,8), Blue: (6,13)
    starts = [(1,6,0), (8,1,1), (13,8,2), (6,13,3)]
    for sx, sy, c_idx in starts:
        px, py = sx*CELL, sy*CELL + OY
        d.rectangle([px, py, px+CELL, py+CELL], fill=colors[c_idx][0], outline="black")
        # Draw Star
        utils.write_text(d, (px+25, py+25), "⭐", size=30, align="center", shadow=False)

    # Other Safe Spots (Grey Star)
    safe_glob = [8, 21, 34, 47] # Global indices
    # We need to map global indices to coordinates
    # Let's manual map for simplicity since get_coordinates depends on color
    # (6,2), (12,6), (8,12), (2,8) are the other safe spots visually
    manual_safes = [(6,2), (12,6), (8,12), (2,8)]
    for mx, my in manual_safes:
        px, py = mx*CELL, my*CELL + OY
        utils.write_text(d, (px+25, py+25), "⭐", size=30, align="center", col="#888", shadow=False)

    # 5. CENTER HOME (Winner's Triangle)
    center_box = [6*CELL, 6*CELL + OY, 9*CELL, 9*CELL + OY]
    d.polygon([(6*CELL, 6*CELL+OY), (9*CELL, 6*CELL+OY), (7.5*CELL, 7.5*CELL+OY)], fill=colors[1][0], outline="black") # Top
    d.polygon([(9*CELL, 6*CELL+OY), (9*CELL, 9*CELL+OY), (7.5*CELL, 7.5*CELL+OY)], fill=colors[2][0], outline="black") # Right
    d.polygon([(9*CELL, 9*CELL+OY), (6*CELL, 9*CELL+OY), (7.5*CELL, 7.5*CELL+OY)], fill=colors[3][0], outline="black") # Bottom
    d.polygon([(6*CELL, 9*CELL+OY), (6*CELL, 6*CELL+OY), (7.5*CELL, 7.5*CELL+OY)], fill=colors[0][0], outline="black") # Left
    utils.write_text(d, (7.5*CELL, 7.5*CELL + OY), "HOME", size=25, align="center", col="white", shadow=True)

    # 6. DRAW TOKENS (The Players)
    # Group players by position to handle overlaps
    pos_map = {}
    for i, p in enumerate(players):
        if not p: continue
        
        # If position is -1, token is in base (Draw in base center)
        if p['pos'] == -1:
            # We already drew big avatar in base, maybe draw a small token pin
            continue
            
        # Calculate Grid Coords
        gx, gy = get_coordinates(p['pos'], i)
        key = (gx, gy)
        if key not in pos_map: pos_map[key] = []
        pos_map[key].append(i)

    # Render Tokens
    for (gx, gy), p_idxs in pos_map.items():
        cx = gx * CELL + CELL//2
        cy = gy * CELL + CELL//2 + OY
        
        # If multiple players on same spot, shift slightly
        count = len(p_idxs)
        shift = 10 if count > 1 else 0
        
        for idx, p_idx in enumerate(p_idxs):
            # Calculate offset
            off_x = (idx - (count-1)/2) * shift
            
            p = players[p_idx]
            token_col = colors[p_idx][0]
            
            # Draw Token Body (Pin)
            d.ellipse([cx-18+off_x, cy-18, cx+18+off_x, cy+18], fill=token_col, outline="white", width=2)
            
            # Draw Tiny Avatar inside
            if p['av']:
                av = utils.get_circle_avatar(p['av'], size=30)
                if av: img.paste(av, (int(cx-15+off_x), int(cy-15)), av)

    # 7. HEADER INFO
    utils.write_text(d, (W//2, 30), "🎲 LUDO: ONE TOKEN", size=40, align="center", col="#FFD700", shadow=True)
    turn_p = next((p for p in players if p and p['turn']), None)
    if turn_p:
        status = f"Turn: @{turn_p['name']} ({colors[turn_p['id']][0]})"
        utils.write_text(d, (W//2, 70), status, size=25, align="center", col="white")

    return img

def draw_dice_result(val):
    """Draws just the dice for the result message"""
    url = DICE_FACES.get(val)
    if not url: return None
    return utils.get_image(url) # Returns PIL image

# ==========================================
# ⚙️ GAME LOGIC
# ==========================================

class LudoGame:
    def __init__(self, room_id, bet):
        self.room_id = room_id
        self.bet = bet
        self.players = [None] * 4 # Max 4 slots (0=Red, 1=Green, 2=Yel, 3=Blue)
        self.state = 'waiting' # waiting, playing
        self.turn_idx = 0
        self.last_interaction = time.time()
        
    def add_player(self, uid, name, av):
        for i in range(4):
            if self.players[i] is None:
                self.players[i] = {
                    'id': i, 'uid': uid, 'name': name, 'av': av,
                    'pos': -1, # -1 = Base, 0 = Start, 56 = Win
                    'turn': False
                }
                return i
        return -1

    def next_turn(self):
        start = self.turn_idx
        while True:
            self.turn_idx = (self.turn_idx + 1) % 4
            p = self.players[self.turn_idx]
            if p:
                # Reset turn flags
                for pl in self.players: 
                    if pl: pl['turn'] = False
                p['turn'] = True
                return p
            if self.turn_idx == start: return None # Should not happen

    def move_token(self, p_idx, dice):
        p = self.players[p_idx]
        if p['pos'] == -1:
            if dice == 6: 
                p['pos'] = 0 # Unlock
                return "open"
            return "stuck"
        
        new_pos = p['pos'] + dice
        
        if new_pos > 56: return "bounce" # Cannot move
        if new_pos == 56: 
            p['pos'] = 56
            return "win"
            
        # Check Kill
        # Convert new_pos to Global Coords to check collision
        # Wait, simple logic:
        # We need to check if new_pos lands on someone else's token.
        # This requires converting everyone's pos to a common coordinate system or checking path overlaps.
        # Simplified: We will trust the grid logic.
        
        # Kill Logic:
        # We need to know the 'Global Cell Index' for collision.
        # Red(0): 0-50. Green(1) starts at 13.
        # Let's implement a 'get_global_index(p_idx, steps)' helper conceptually.
        
        # For this version, let's keep it simple:
        # If user lands on a spot, we calculate collision visually? No, logic first.
        
        # Advanced Collision Logic:
        my_global = (new_pos + (p_idx * 13)) % 52
        if new_pos > 50: my_global = -100 # Safe zone inside home, no kill
        
        killed = None
        if my_global not in SAFE_SPOTS and my_global != -100:
            for i, enemy in enumerate(self.players):
                if enemy and i != p_idx and enemy['pos'] != -1 and enemy['pos'] <= 50:
                    enemy_global = (enemy['pos'] + (i * 13)) % 52
                    if enemy_global == my_global:
                        # KILL!
                        enemy['pos'] = -1 # Send to base
                        killed = enemy['name']
        
        p['pos'] = new_pos
        return f"kill {killed}" if killed else "move"

# ==========================================
# ⚙️ HANDLER
# ==========================================

def handle_command(bot, command, room_id, user, args, data):
    uid = data.get('userid', user)
    av_file = data.get("avatar")
    av = f"https://cdn.howdies.app/avatar?image={av_file}" if av_file else None
    
    cmd = command.lower().strip()
    
    # 1. CREATE GAME
    if cmd == "ludo":
        bet = int(args[0]) if args and args[0].isdigit() else 0
        with game_lock:
            if room_id in games:
                bot.send_message(room_id, "⚠️ Game running! Type `!join` or `!stop`.")
                return True
            g = LudoGame(room_id, bet)
            g.add_player(uid, user, av)
            if bet>0: add_game_result(uid, user, "ludo", -bet, False)
            games[room_id] = g
        
        bot.send_message(room_id, f"🎲 **Ludo 1T Created!**\nBet: {bet}\nWaiting for players... (`!join`)")
        return True

    # 2. JOIN
    if cmd == "join":
        with game_lock:
            g = games.get(room_id)
            if not g or g.state != 'waiting': return False
            
            # Check exist
            if any(p and str(p['uid']) == str(uid) for p in g.players):
                bot.send_message(room_id, "⚠️ You already joined.")
                return True
                
            idx = g.add_player(uid, user, av)
            if idx == -1:
                bot.send_message(room_id, "❌ Room Full!")
                return True
                
            if g.bet>0: add_game_result(uid, user, "ludo", -g.bet, False)
            bot.send_message(room_id, f"✅ **{user}** joined as Player {idx+1}!")
            
            # Auto Start if 4 (Optional, let's keep manual start or auto start at 2?)
            # Let's add !start command logic
        return True

    # 3. START
    if cmd == "start":
        with game_lock:
            g = games.get(room_id)
            if not g or g.state != 'waiting': return False
            # Check Count
            count = sum(1 for p in g.players if p)
            if count < 2:
                bot.send_message(room_id, "⚠️ Need at least 2 players.")
                return True
            
            g.state = 'playing'
            g.players[0]['turn'] = True # P1 Starts
            
            # Draw Board
            img = draw_ludo_board(g.players)
            link = utils.upload(bot, img)
            
            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Start"})
            bot.send_message(room_id, f"🚦 **Game Started!**\n@{g.players[0]['name']}'s Turn. Type `!roll`")
        return True

    # 4. ROLL (The Main Action)
    if cmd == "roll":
        # Note: Roll should be async to show animation
        utils.run_in_bg(process_turn, bot, room_id, uid)
        return True

    # 5. STOP
    if cmd == "stop":
        with game_lock:
            if room_id in games:
                del games[room_id]
                bot.send_message(room_id, "🛑 Game Stopped.")
        return True

    return False

# --- ASYNC TURN PROCESSOR ---
def process_turn(bot, room_id, uid):
    with game_lock:
        g = games.get(room_id)
        if not g: return
        
        curr_p = g.players[g.turn_idx]
        if str(curr_p['uid']) != str(uid): return # Not your turn
        
    # 1. Show Rolling GIF
    bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": DICE_GIF, "text": "Rolling..."})
    time.sleep(2.5) # Suspense
    
    # 2. Calculate
    dice = random.randint(1, 6)
    res_msg = ""
    
    with game_lock:
        # Re-fetch safely
        g = games.get(room_id)
        if not g: return
        
        # Logic
        result = g.move_token(g.turn_idx, dice)
        
        # Generate Result Image (Dice Face)
        dice_img = utils.get_image(DICE_FACES[dice])
        # We can overlay this on board or send separately. Sending separately is cleaner for chat flow.
        dice_link = utils.upload(bot, dice_img)
        
        bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": dice_link, "text": f"Dice: {dice}"})
        
        if result == "win":
            # WINNER!
            rew = g.bet * sum(1 for p in g.players if p)
            add_game_result(uid, curr_p['name'], "ludo", rew, True)
            bot.send_message(room_id, f"🏆 **{curr_p['name']} WINS!**\nWon {rew} Coins!")
            del games[room_id]
            return
            
        elif result.startswith("kill"):
            victim = result.split()[1]
            res_msg = f"⚔️ **KILL!** Sent {victim} home!"
            # Extra turn? Usually yes in Ludo.
            # Let's keep turn with current player
            pass
            
        elif result == "open":
            res_msg = "🔓 **Unlocked!** Token is out."
            # 6 gets extra turn
            pass
            
        elif result == "stuck":
            res_msg = "🔒 Need 6 to open."
            g.next_turn()
            
        elif result == "bounce":
            res_msg = "🚫 Too high! Wait."
            g.next_turn()
            
        else: # Normal move
            res_msg = f"✅ Moved {dice} steps."
            if dice != 6: g.next_turn()
            else: res_msg += " (Roll again!)"

        # 3. Update Board
        img = draw_ludo_board(g.players)
        link = utils.upload(bot, img)
        
        next_name = g.players[g.turn_idx]['name']
        
        bot.send_message(room_id, f"{res_msg}")
        bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Board"})
        
        if "Roll again" not in res_msg and result != "win":
             bot.send_message(room_id, f"👉 @{next_name}'s Turn")
