import time
import random
import threading
from PIL import Image, ImageDraw, ImageFont

# --- IMPORTS ---
try: import utils
except ImportError: print("[Ludo] Error: utils.py not found!")

try: from db import add_game_result
except: print("[Ludo] DB Error")

# --- GLOBAL VARIABLES ---
games = {}
game_lock = threading.Lock()

# --- ASSETS (CUTE TOKENS) ---
# Hum online cute 3D icons use karenge har color ke liye
TOKENS = {
    'R': "https://img.icons8.com/3d-fluency/94/mario.png",       # Red
    'G': "https://img.icons8.com/3d-fluency/94/luigi.png",       # Green
    'Y': "https://img.icons8.com/3d-fluency/94/yoshi.png",       # Yellow
    'B': "https://img.icons8.com/3d-fluency/94/sonic.png"        # Blue (Sonic/Blue char)
}
# Fallback local colors
COLORS = {
    'R': '#FF4444', 'G': '#44FF44', 'Y': '#FFD700', 'B': '#4444FF'
}

# --- LUDO PATH MAPPING (The Hardest Part) ---
# Ye function 0-51 steps ko X,Y coordinates me convert karta hai (15x15 Grid)
# 1 Cell = 40px. Board Size = 600x600.
CELL_SIZE = 40
OFFSET = 20 # Padding

def get_grid_pos(path_index, color):
    """
    Standard Ludo Path Logic.
    Index 0-50: Common Path
    Index 51-56: Home Run (Inside Color)
    Index 57: WIN (Center)
    """
    # Global Path definition (Standard Ludo Snake Path)
    # Starts from Red Start Position (Bottom Left)
    # List of (Row, Col) for the outer loop (0 to 51)
    
    # Isko manually map karna padega for perfection
    # Hum relative movement use karenge.
    
    # Start (Red's 1st Step) is at (13, 6) in a 15x15 grid (0-indexed)
    # But let's simplify: Standard Ludo has a fixed path.
    
    # Generic Path for ONE quadrant (13 steps), then rotate logic.
    pass

# Hum ek pre-calculated path list use karenge taaki calculation fast ho.
# Ye coordinates (Col, Row) hain 15x15 grid ke liye.
MAIN_PATH = [
    (1,13), (2,13), (3,13), (4,13), (5,13), # Red Strip Up
    (6,12), (6,11), (6,10), (6,9), (6,8), (6,7), # Top Left Horizontal
    (5,7), (4,7), (3,7), (2,7), (1,7), (0,7), # Top Left Up
    (0,8), # Top Middle (Turning point)
    (0,9), (1,9), (2,9), (3,9), (4,9), (5,9), # Top Right Down
    (6,9), (6,10), (6,11), (6,12), (6,13), (6,14), # Right Horizontal
    (7,14), # Right Middle
    (8,14), (8,13), (8,12), (8,11), (8,10), (8,9), # Bottom Right Horizontal
    (9,9), (10,9), (11,9), (12,9), (13,9), (14,9), # Bottom Right Down
    (14,8), # Bottom Middle
    (14,7), (13,7), (12,7), (11,7), (10,7), (9,7), # Bottom Left Up
    (8,7), (8,6), (8,5), (8,4), (8,3), (8,2), # Left Horizontal
    (7,0), # Left Middle
    (6,0), (6,1), (6,2), (6,3), (6,4), (6,5) # Left Horizontal In
]
# Wait, standard Ludo path logic is tricky to hardcode array.
# Let's use coordinate geometry.

def get_coords_for_step(step, color_code):
    """
    Step: 0 to 56 (57 is Win)
    Color: R, G, Y, B
    Returns: (pixel_x, pixel_y)
    """
    # Base offsets for colors (Start indices in global loop)
    # Red Starts at index 0 of our defined loop? No.
    # Let's define the 52-step loop starting from Red's first step.
    
    # Standard Ludo Grid (15x15):
    # R Start: (6, 13) -> No, (1, 13) is Red start in standard logic?
    # Let's assume Red is Bottom-Left Player.
    # Start Position: Grid (1, 13) [Col 1, Row 13] -> (Step 0)
    
    # List of (Col, Row) for the 52 common steps starting from Red
    common_route = [
        (1,13), (2,13), (3,13), (4,13), (5,13),         # 0-4
        (6,12), (6,11), (6,10), (6,9), (6,8), (6,7),    # 5-10
        (5,6), (4,6), (3,6), (2,6), (1,6), (0,6),       # 11-16 (Green Approach)
        (0,7), (0,8),                                   # 17-18 (Top Turn)
        (1,8), (2,8), (3,8), (4,8), (5,8), (6,8),       # 19-24 (Yellow Approach)
        (7,9), (7,10), (7,11), (7,12), (7,13), (7,14),  # 25-30 WRONG MAPPING
    ]
    
    # --- SIMPLIFIED COORDINATE MAPPER ---
    # Behtareen tareeka: Har quadrant ka logic same hai, bas rotate ho raha hai.
    # Hum Red ka path define karte hain, baaki colors ke liye rotate kar denge.
    
    # Red Path (Bottom-Left Home):
    # Starts at Bottom-Left white strip.
    # Coordinates relative to Center (0,0) might be easier, but let's stick to 15x15 grid.
    
    # RED PATH (Steps 0-56)
    # 0-50: Main board
    # 51-56: Home Run
    
    # Hardcoded Loop for absolute precision (Col, Row)
    # 0,0 is Top-Left.
    
    loop = [
        (1,13), (2,13), (3,13), (4,13), (5,13), # 0-4
        (6,12), (6,11), (6,10), (6,9), (6,8),   # 5-9
        (6,7), (5,7), (4,7), (3,7), (2,7), (1,7), # 10-15 (Towards Green)
        (0,7), (0,8),                             # 16-17 (Top Turn)
        (1,8), (2,8), (3,8), (4,8), (5,8), (6,8), # 18-23
        (7,9), (7,10), (7,11), (7,12), (7,13),    # 24-28 (Towards Yellow) Is logic wrong?
    ]
    # Okay, manual mapping is error prone without visual aid.
    # Let's use the Visual Grid approach (Start from Red: Bottom-Left box, first cell above it).
    
    # RED (Starts at 1,13), GREEN (Starts 1,1), YELLOW (Starts 13,1), BLUE (Starts 13,13)
    # Note: Standard Ludo has 52 outer cells.
    
    # --- FINAL RELIABLE PATH MAPPING ---
    # Path of Red:
    P = []
    # 1. Up (Bottom Left)
    for r in range(13, 8, -1): P.append((6, r)) # 6 is col index? No. 
    # Let's assume standard board layout.
    # Board is 15x15.
    
    # Red Path:
    # 1. (1, 13) -> (2,13) -> (3,13) -> (4,13) -> (5,13) 
    # Wait, Red usually goes UP. Let's fix Red at Bottom Left.
    # Starts at (6, 13) [Col 6, Row 13] -> moves Up to (6, 9)
    # Then moves Left to (1, 9) ??? No.
    
    # Let's fix the visual first.
    # Home Bases: Red(Bottom-Left), Blue(Bottom-Right), Yellow(Top-Right), Green(Top-Left).
    pass

# ==========================================
# 🎨 GRAPHICS ENGINE (REALISTIC)
# ==========================================

def draw_real_board(players, dice_val=None, rolling=False):
    W, H = 640, 640 # Multiple of 15 (approx 42.6px per cell, let's use 600 for 40px)
    W, H = 600, 600
    SZ = 40 # Cell Size
    
    img = utils.create_canvas(W, H, "white")
    d = ImageDraw.Draw(img)
    
    # 1. DRAW BASE QUADRANTS (Homes)
    # Top-Left (Green)
    d.rectangle([0, 0, 6*SZ, 6*SZ], fill=COLORS['G'], outline="black")
    d.rectangle([SZ, SZ, 5*SZ, 5*SZ], fill="white") # Inner white
    
    # Top-Right (Yellow)
    d.rectangle([9*SZ, 0, 15*SZ, 6*SZ], fill=COLORS['Y'], outline="black")
    d.rectangle([10*SZ, SZ, 14*SZ, 5*SZ], fill="white")
    
    # Bottom-Left (Red)
    d.rectangle([0, 9*SZ, 6*SZ, 15*SZ], fill=COLORS['R'], outline="black")
    d.rectangle([SZ, 10*SZ, 5*SZ, 14*SZ], fill="white")
    
    # Bottom-Right (Blue)
    d.rectangle([9*SZ, 9*SZ, 15*SZ, 15*SZ], fill=COLORS['B'], outline="black")
    d.rectangle([10*SZ, 10*SZ, 14*SZ, 14*SZ], fill="white")
    
    # 2. DRAW GRID LINES (The Cross)
    # Vertical Strips
    for c in range(6, 10): # Cols 6,7,8 (Index 6,7,8 is 9th col?) Range is exclusive
        # We need cols 6, 7, 8 (0-indexed)
        x = c * SZ
        d.line([x, 0, x, 15*SZ], fill="black", width=1)
        
    # Horizontal Strips
    for r in range(6, 10): # Rows 6, 7, 8
        y = r * SZ
        d.line([0, y, 15*SZ, y], fill="black", width=1)

    # 3. DRAW COLORED HOME RUNS & START SPOTS
    # Green Strip (Top, Middle Col)
    d.rectangle([7*SZ, SZ, 8*SZ, 6*SZ], fill=COLORS['G']) # Home Run
    d.rectangle([8*SZ, SZ, 9*SZ, 2*SZ], fill=COLORS['G']) # Start Spot
    
    # Yellow Strip (Right, Middle Row)
    d.rectangle([9*SZ, 7*SZ, 14*SZ, 8*SZ], fill=COLORS['Y']) # Home Run
    d.rectangle([13*SZ, 8*SZ, 14*SZ, 9*SZ], fill=COLORS['Y']) # Start Spot
    
    # Blue Strip (Bottom, Middle Col)
    d.rectangle([7*SZ, 9*SZ, 8*SZ, 14*SZ], fill=COLORS['B']) # Home Run
    d.rectangle([6*SZ, 13*SZ, 7*SZ, 14*SZ], fill=COLORS['B']) # Start Spot
    
    # Red Strip (Left, Middle Row)
    d.rectangle([SZ, 7*SZ, 6*SZ, 8*SZ], fill=COLORS['R']) # Home Run
    d.rectangle([SZ, 6*SZ, 2*SZ, 7*SZ], fill=COLORS['R']) # Start Spot
    
    # Center Triangle
    d.polygon([(6*SZ, 6*SZ), (9*SZ, 6*SZ), (7.5*SZ, 7.5*SZ)], fill=COLORS['G'], outline='black')
    d.polygon([(9*SZ, 6*SZ), (9*SZ, 9*SZ), (7.5*SZ, 7.5*SZ)], fill=COLORS['Y'], outline='black')
    d.polygon([(9*SZ, 9*SZ), (6*SZ, 9*SZ), (7.5*SZ, 7.5*SZ)], fill=COLORS['B'], outline='black')
    d.polygon([(6*SZ, 9*SZ), (6*SZ, 6*SZ), (7.5*SZ, 7.5*SZ)], fill=COLORS['R'], outline='black')
    
    # 4. DRAW TOKENS (The Logic of Movement)
    for uid, p in players.items():
        step = p['step'] # 0 to 57
        col_code = p['color']
        
        # Calculate X, Y based on step and color
        cx, cy = calculate_pixel_pos(step, col_code, SZ)
        
        # Get Cute Avatar
        token_img = utils.get_image(TOKENS[col_code])
        if token_img:
            token_img = token_img.resize((SZ-2, SZ-2))
            img.paste(token_img, (cx+1, cy+1), token_img)
        else:
            # Fallback
            d.ellipse([cx+5, cy+5, cx+SZ-5, cy+SZ-5], fill=COLORS[col_code], outline="black", width=2)
            
        # Name Tag (Small)
        utils.write_text(d, (cx+SZ//2, cy-10), p['name'][:4], size=14, align="center", col="black", shadow=False)

    # 5. DRAW DICE ILLUSION / RESULT
    center_x, center_y = 300, 300
    
    if rolling:
        # Blur Box
        d.rounded_rectangle([250, 250, 350, 350], radius=15, fill=(0,0,0,180))
        utils.write_text(d, (center_x, center_y), "🎲", size=60, align="center")
    elif dice_val:
        # 3D Dice Graphic
        dice_url = f"https://img.icons8.com/3d-fluency/94/{dice_val}-circle.png"
        dice_img = utils.get_image(dice_url)
        if dice_img:
            dice_img = dice_img.resize((100, 100))
            img.paste(dice_img, (250, 250), dice_img)
        else:
            d.rounded_rectangle([260, 260, 340, 340], radius=10, fill="white", outline="black")
            utils.write_text(d, (center_x, center_y), str(dice_val), size=50, align="center", col="black")

    return img

def calculate_pixel_pos(step, color, sz):
    """
    Mapping logic based on 15x15 Grid.
    Returns Top-Left Pixel (x, y) of the cell.
    """
    # Define the Spiral Path (0-51) starting from Red's Start (1, 6)
    # wait, Red Start is usually cell (1, 6). (Col 1, Row 6) relative to grid?
    # No, Let's define one Quadrant path relative to center or fixed list.
    
    # FIXED LIST OF 52 STEPS (0-indexed on 15x15 grid)
    # Starting from Red's Safe Spot and moving Clockwise
    
    # Coordinates (Col, Row)
    path_map = [
        (1,6), (2,6), (3,6), (4,6), (5,6), # Red Straight
        (6,5), (6,4), (6,3), (6,2), (6,1), (6,0), # Up
        (7,0), # Top Middle
        (8,0), (8,1), (8,2), (8,3), (8,4), (8,5), # Down
        (9,6), (10,6), (11,6), (12,6), (13,6), (14,6), # Right
        (14,7), # Right Middle
        (14,8), (13,8), (12,8), (11,8), (10,8), (9,8), # Left
        (8,9), (8,10), (8,11), (8,12), (8,13), (8,14), # Down
        (7,14), # Bottom Middle
        (6,14), (6,13), (6,12), (6,11), (6,10), (6,9), # Up
        (5,8), (4,8), (3,8), (2,8), (1,8), (0,8), # Left
        (0,7) # Left Middle (End of loop)
    ]
    
    # Offsets in the path list based on Color
    # Red starts at 0. Green at 13. Yellow at 26. Blue at 39.
    start_idx = 0
    if color == 'R': start_idx = 0
    elif color == 'G': start_idx = 13
    elif color == 'Y': start_idx = 26
    elif color == 'B': start_idx = 39
    
    if step == -1: # At Home Base
        if color == 'R': return (2*sz, 11*sz) # Center of Red Home
        if color == 'G': return (2*sz, 2*sz)
        if color == 'Y': return (11*sz, 2*sz)
        if color == 'B': return (11*sz, 11*sz)
        
    if step < 51:
        # Normal Path
        actual_idx = (start_idx + step) % 52
        c, r = path_map[actual_idx]
        return (c*sz, r*sz)
    else:
        # Home Run (Inside)
        home_step = step - 51 # 0 to 5
        # Coordinates depend on color
        if color == 'R': return ((1+home_step)*sz, 7*sz)
        if color == 'G': return (7*sz, (1+home_step)*sz) # Wait, Green goes Down? No Green is Top.
        # Fix Green Home Run
        if color == 'G': return (7*sz, (5-home_step)*sz) # Goes Down? No Green Home run is (7, 1) to (7, 5) ?
        # Actually Green starts at top (6,0) -> moves down.
        # Green Home run is column 7, rows 1 to 5.
        if color == 'G': return (7*sz, (1+home_step)*sz) 
        
        if color == 'Y': return ((13-home_step)*sz, 7*sz)
        if color == 'B': return (7*sz, (13-home_step)*sz)
        
        # Center Win
        if step >= 56: return (7*sz, 7*sz)

    return (0,0)

# ==========================================
# ⚙️ LOGIC
# ==========================================

class RealLudo:
    def __init__(self, room_id, bet):
        self.room_id = room_id
        self.bet = bet
        self.players = {} # {uid: {name, color, step}}
        self.turn_order = [] # ['R', 'G', 'Y', 'B'] present in game
        self.current_idx = 0
        self.state = 'lobby'
        self.colors = ['R', 'G', 'Y', 'B']

    def add_player(self, uid, name):
        if not self.colors: return False
        col = self.colors.pop(0)
        self.players[str(uid)] = {
            'name': name,
            'color': col,
            'step': -1 # -1 is Home Base (Need 6 to start? No, let's keep it Sprint style: Start at 0)
            # Sprint Ludo: Start at 0 immediately to make it fast.
        }
        self.players[str(uid)]['step'] = 0 
        return True

    def get_current_uid(self):
        # Find uid with current color
        curr_col = self.turn_order[self.current_idx]
        for uid, p in self.players.items():
            if p['color'] == curr_col: return uid
        return None

    def move(self, uid, dice):
        p = self.players[str(uid)]
        new_step = p['step'] + dice
        
        msg = f"🎲 **{dice}**!"
        
        # Check Win
        if new_step >= 56: # Reached Center
            p['step'] = 57
            return True, f"{msg} 🏆 Reached Home!"
            
        # Cutting Logic
        # Calculate actual Grid Position of new step
        # If matches another player's grid pos (and not safe zone), Kill.
        # Safe Zones: 0, 8, 13, 21, 26, 34, 39, 47 (Indices in Path Map)
        
        p['step'] = new_step
        return False, msg

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    uid = data.get('userid', user)
    global games
    
    # 1. NEW GAME
    if cmd == "ludo":
        bet = 0
        if args and args[0].isdigit(): bet = int(args[0])
        
        with game_lock:
            if room_id in games: return True
            game = RealLudo(room_id, bet)
            game.add_player(uid, user)
            if bet > 0: add_game_result(uid, user, "ludo", -bet, False)
            games[room_id] = game
            
        # Initial Board (Lobby)
        img = draw_real_board(game.players)
        link = utils.upload(bot, img)
        bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Lobby"})
        bot.send_message(room_id, f"🎲 **Real Ludo Created!** Bet: {bet}\nType `!join`")
        return True

    # 2. JOIN
    if cmd == "join":
        with game_lock:
            g = games.get(room_id)
            if not g or g.state != 'lobby': return False
            if g.add_player(uid, user):
                if g.bet > 0: add_game_result(uid, user, "ludo", -g.bet, False)
                
                img = draw_real_board(g.players)
                link = utils.upload(bot, img)
                bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Join"})
            else:
                bot.send_message(room_id, "Full!")
        return True

    # 3. START
    if cmd == "start":
        with game_lock:
            g = games.get(room_id)
            if not g: return False
            g.state = 'playing'
            # Sort turn order R, G, Y, B
            g.turn_order = sorted([p['color'] for p in g.players.values()], key=lambda x: ['R','G','Y','B'].index(x))
            
            bot.send_message(room_id, "🔥 **Game Started!** Red goes first.")
        return True

    # 4. ROLL (THE ILLUSION)
    if cmd == "roll":
        with game_lock:
            g = games.get(room_id)
            if not g or g.state != 'playing': return False
            
            curr_uid = g.get_current_uid()
            if str(uid) != str(curr_uid): return True # Not turn
            
            # --- ILLUSION PART ---
            # Send Rolling Image First
            roll_img = draw_real_board(g.players, rolling=True)
            roll_link = utils.upload(bot, roll_img)
            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": roll_link, "text": "Rolling..."})
            
            # Sleep 1.5s for suspense (Thread blocking is bad, but short sleep is ok here or use timer)
            time.sleep(1.5)
            
            # Real Result
            dice = random.randint(1, 6)
            is_win, msg = g.move(uid, dice)
            
            # Send Final Image
            final_img = draw_real_board(g.players, dice_val=dice)
            final_link = utils.upload(bot, final_img)
            
            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": final_link, "text": f"Dice {dice}"})
            bot.send_message(room_id, f"@{user} {msg}")
            
            if is_win:
                reward = g.bet * len(g.players)
                add_game_result(uid, user, "ludo", reward, True)
                bot.send_message(room_id, f"🎉 **VICTORY!** @{user} wins {reward} coins!")
                del games[room_id]
                return True
                
            # Next Turn
            if dice != 6:
                g.current_idx = (g.current_idx + 1) % len(g.turn_order)
            
            nxt_uid = g.get_current_uid()
            nxt_name = g.players[nxt_uid]['name']
            bot.send_message(room_id, f"👉 **@{nxt_name}'s** Turn")
            
        return True
    
    # 5. END
    if cmd == "end":
        with game_lock:
            if room_id in games: del games[room_id]
            bot.send_message(room_id, "Stopped.")
        return True

    return False
