import time
import random
import threading
import math
from PIL import Image, ImageDraw

# --- IMPORTS ---
try: import utils
except ImportError: print("[Ludo] Error: utils.py not found!")

try: from db import add_game_result
except: print("[Ludo] DB Error")

# --- GLOBAL STATE ---
games = {}
game_lock = threading.Lock()

# --- CONSTANTS ---
COLORS = {
    'R': {'name': 'Red',    'hex': '#FF4444', 'path_start': 0},
    'G': {'name': 'Green',  'hex': '#44FF44', 'path_start': 7},
    'Y': {'name': 'Yellow', 'hex': '#FFFF44', 'path_start': 14},
    'B': {'name': 'Blue',   'hex': '#4444FF', 'path_start': 21}
}
TURN_ORDER = ['R', 'G', 'Y', 'B']
TOTAL_STEPS = 28 # Chhota board for fast game

def setup(bot):
    print("[Ludo] Sprint Edition Loaded.")

# ==========================================
# 🎨 GRAPHICS ENGINE (The Artist)
# ==========================================

def get_coordinates(step_index):
    """
    Ye function batata hai ki board par kahan circle banana hai.
    Hum ek Square Loop bana rahe hain (0-27 steps).
    """
    # Board Size 600x600. Center is 300,300.
    # Hum ek rounded square path define kar rahe hain.
    
    # Corners
    margin = 80
    size = 440 # Track width
    
    # Coordinates mapping logic (Simplified Square Track)
    # Total 28 steps: 7 steps per side.
    
    side_len = size // 7
    x, y = 0, 0
    start_x, start_y = margin, margin
    
    if 0 <= step_index <= 6:   # Top Row (Left to Right)
        x = start_x + (step_index * side_len)
        y = start_y
    elif 7 <= step_index <= 13: # Right Col (Top to Bottom)
        x = start_x + size
        y = start_y + ((step_index - 7) * side_len)
    elif 14 <= step_index <= 20: # Bottom Row (Right to Left)
        x = start_x + size - ((step_index - 14) * side_len)
        y = start_y + size
    elif 21 <= step_index <= 27: # Left Col (Bottom to Top)
        x = start_x
        y = start_y + size - ((step_index - 21) * side_len)
        
    return int(x), int(y)

def draw_ludo_board(players, current_turn_color, dice_value=None, rolling=False):
    W, H = 600, 600
    bg_color = (20, 20, 30)
    
    img = utils.create_canvas(W, H, bg_color)
    d = ImageDraw.Draw(img)
    
    # 1. Draw Track (Connections)
    # Saare steps ke liye chote dots/lines
    for i in range(TOTAL_STEPS):
        x1, y1 = get_coordinates(i)
        next_step = (i + 1) % TOTAL_STEPS
        x2, y2 = get_coordinates(next_step)
        d.line([x1+25, y1+25, x2+25, y2+25], fill=(60, 60, 70), width=4)

    # 2. Draw Step Circles (Spots)
    for i in range(TOTAL_STEPS):
        x, y = get_coordinates(i)
        col = "#333344"
        # Corner spots ko highlight karo (Safe zones/Starts)
        if i % 7 == 0: col = "#555566"
        d.ellipse([x, y, x+50, y+50], fill=col, outline="#222", width=2)
        # Numbering (Optional, clutter bachane ke liye hata diya)

    # 3. Draw Center Info (Dice Area)
    center_x, center_y = W//2, H//2
    
    # Turn Indicator Glow
    curr_data = COLORS[current_turn_color]
    glow_col = curr_data['hex']
    d.ellipse([center_x-60, center_y-60, center_x+60, center_y+60], outline=glow_col, width=4)
    
    if rolling:
        utils.write_text(d, (center_x, center_y), "🎲...", size=50, align="center", col="white")
    elif dice_value:
        # Dice Box
        d.rounded_rectangle([center_x-40, center_y-40, center_x+40, center_y+40], radius=10, fill="white")
        # Dice Number
        dot_col = "black"
        # Draw Dots based on dice value (Simple representation)
        utils.write_text(d, (center_x, center_y), str(dice_value), size=50, align="center", col="black")
    else:
         utils.write_text(d, (center_x, center_y), "LUDO", size=30, align="center", col="#888")

    # 4. Draw Players (Tokens)
    # Important: Agar 2 players same jagah hain, to unhe thoda shift karna padega
    
    # Pehle grouping kar lete hain position ke hisaab se
    pos_map = {}
    for pid, pdata in players.items():
        pos = pdata['pos']
        if pos not in pos_map: pos_map[pos] = []
        pos_map[pos].append(pdata)

    for pos, p_list in pos_map.items():
        bx, by = get_coordinates(pos)
        
        # Agar ek se zyada token hain, to thoda offset denge
        offset_step = 0
        if len(p_list) > 1: offset_step = 10
        
        for idx, pdata in enumerate(p_list):
            cx = bx + (idx * offset_step)
            cy = by - (idx * offset_step)
            
            p_color = COLORS[pdata['color']]['hex']
            
            # Token Body
            d.ellipse([cx, cy, cx+50, cy+50], fill=p_color, outline="white", width=3)
            
            # Initial Name
            initial = pdata['name'][0].upper()
            utils.write_text(d, (cx+25, cy+25), initial, size=24, align="center", col="black")

    # 5. Player List Header
    y_off = 20
    for code in TURN_ORDER:
        found = False
        for pdata in players.values():
            if pdata['color'] == code:
                col = COLORS[code]['hex']
                name = pdata['name']
                # Highlight if current turn
                prefix = "👉 " if code == current_turn_color else ""
                utils.write_text(d, (W//2, y_off), f"{prefix}{name}", size=18, align="center", col=col, shadow=True)
                y_off += 25
                found = True
                break

    return img

def draw_rolling_gif_frame():
    """Illusion ke liye ek blurred frame"""
    W, H = 600, 600
    img = utils.create_canvas(W, H, (20, 20, 30))
    d = ImageDraw.Draw(img)
    utils.write_text(d, (300, 300), "🎲 ROLLING...", size=60, align="center", col="white", shadow=True)
    return img

# ==========================================
# ⚙️ GAME LOGIC
# ==========================================

class LudoGame:
    def __init__(self, room_id, bet):
        self.room_id = room_id
        self.bet = bet
        self.players = {} # {user_id: {name, color, pos}}
        self.state = 'lobby' # lobby, playing
        self.turn_idx = 0
        self.colors_avail = ['R', 'G', 'Y', 'B']

    def add_player(self, uid, name):
        if len(self.players) >= 4: return False
        color = self.colors_avail.pop(0)
        
        # Calculate Starting Position based on Color
        start_pos = COLORS[color]['path_start']
        
        self.players[str(uid)] = {
            'name': name,
            'color': color,
            'pos': start_pos, 
            'start_pos': start_pos, # Home base
            'finished': False
        }
        return True

    def get_current_player_id(self):
        # Ordered list of player IDs based on turn color
        active_colors = [p['color'] for p in self.players.values()]
        # Sort based on TURN_ORDER ['R', 'G', 'Y', 'B']
        # But we need the User ID.
        
        # Simple Logic: Hum TURN_ORDER iterate karenge.
        # Jo color current turn hai, uska player dhundenge.
        current_color = TURN_ORDER[self.turn_idx]
        
        for uid, p in self.players.items():
            if p['color'] == current_color:
                return uid
        return None
    
    def next_turn(self):
        # Cycle through R -> G -> Y -> B
        # Ensure next color actually exists in game
        while True:
            self.turn_idx = (self.turn_idx + 1) % 4
            next_col = TURN_ORDER[self.turn_idx]
            # Check if anyone has this color
            exists = any(p['color'] == next_col for p in self.players.values())
            if exists: break

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    user_id = data.get('userid', user)
    
    global games
    
    # 1. CREATE GAME (!ludo [bet])
    if cmd == "ludo":
        bet = 0
        if args and args[0].isdigit(): bet = int(args[0])
        
        with game_lock:
            if room_id in games:
                bot.send_message(room_id, "⚠️ Game already running! Type `!join`")
                return True
            
            game = LudoGame(room_id, bet)
            game.add_player(user_id, user)
            
            # Deduct Entry
            if bet > 0: add_game_result(user_id, user, "ludo", -bet, False)
            
            games[room_id] = game
            
        bot.send_message(room_id, f"🎲 **Ludo Lobby Created!**\nBet: {bet} Coins\nType `!join` to enter.\nHost type `!start` when ready.")
        return True

    # 2. JOIN GAME (!join)
    if cmd == "join":
        with game_lock:
            game = games.get(room_id)
            if not game or game.state != 'lobby': return False # Silent fail if playing
            
            if str(user_id) in game.players:
                bot.send_message(room_id, "⚠️ You are already in!")
                return True
                
            if game.add_player(user_id, user):
                if game.bet > 0: add_game_result(user_id, user, "ludo", -game.bet, False)
                bot.send_message(room_id, f"✅ **{user}** joined as {game.players[str(user_id)]['color']} Team!")
            else:
                bot.send_message(room_id, "❌ Lobby Full!")
        return True

    # 3. START GAME (!start)
    if cmd == "start":
        with game_lock:
            game = games.get(room_id)
            if not game or game.state != 'lobby': return False
            if len(game.players) < 2:
                bot.send_message(room_id, "⚠️ Need at least 2 players.")
                return True
            
            game.state = 'playing'
            # Figure out who starts (Red usually)
            # If Red not present, next available
            game.turn_idx = -1
            game.next_turn() 
            
            current_col = TURN_ORDER[game.turn_idx]
            
            # Upload Board
            img = draw_ludo_board(game.players, current_col)
            link = utils.upload(bot, img)
            
            bot.send_json({
                "handler": "chatroommessage", "roomid": room_id, 
                "type": "image", "url": link, "text": "Start"
            })
            
            p_id = game.get_current_player_id()
            p_name = game.players[p_id]['name']
            bot.send_message(room_id, f"🎲 Game Started! **@{p_name}'s** Turn. Type `!roll`")
        return True

    # 4. ROLL DICE (!roll / !r)
    if cmd in ["roll", "r"]:
        with game_lock:
            game = games.get(room_id)
            if not game or game.state != 'playing': return False
            
            curr_id = game.get_current_player_id()
            if str(user_id) != str(curr_id):
                bot.send_message(room_id, "⏳ Not your turn!")
                return True
            
            # --- THE ILLUSION ---
            # Pehle "Rolling..." image bhejo (optional, makes it slow but cool)
            # Fast experience ke liye hum seedha result dikhayenge par thoda delay lekar
            
            dice = random.randint(1, 6)
            p_data = game.players[str(user_id)]
            
            # Move Logic
            old_pos = p_data['pos']
            new_pos = (old_pos + dice) % TOTAL_STEPS
            
            msg_text = f"🎲 Rolled a **{dice}**!"
            
            # Killing Logic (Kaatna)
            killed_someone = False
            for target_uid, target_p in game.players.items():
                if target_uid != str(user_id) and target_p['pos'] == new_pos:
                    # KILL!
                    target_p['pos'] = target_p['start_pos'] # Reset to start
                    msg_text += f"\n⚔️ **BOOM!** Cut {target_p['name']}!"
                    killed_someone = True
            
            p_data['pos'] = new_pos
            
            # Check Win Logic
            # Humara chhota board circular hai. Win condition:
            # Agar wapas start position cross karke thoda aage gaya to win maane ya
            # bas ek loop complete hone par.
            
            # Simple Logic for Sprint Ludo: 
            # Total steps travel count karna padega. 
            # Abhi ke liye: Agar koi 'Kill' karta hai to +1 turn milta hai?
            # Ya bas race hai? Let's keep it simple infinite loop until someone quits?
            # NO, "Pahle gaya andar wo win".
            
            # Fix: Let's calculate 'distance travelled'.
            # Complex ho jayega. Easy fix: 
            # Random winning spot: Step 25 (agar 28 total hai).
            # Start positions: R=0, G=7, Y=14, B=21.
            # Red wins at 27. Green wins at 6 (wrapped). 
            # Let's simplify: First to complete 1 full round wins.
            
            # Calculate distance moved relative to start
            dist = (new_pos - p_data['start_pos']) % TOTAL_STEPS
            # Agar distance < dice (matlab wrap around hua hai)
            
            # Winning Condition:
            # Is logic me thoda math lagana padega. 
            # Best: First player to make 1 kill OR complete 30 steps wins.
            
            # Let's stick to "Kaatne wala king" logic or just simple race.
            # Simple Race: Check if current pos == start_pos - 1 (approx).
            
            # Visual Update
            current_col = p_data['color']
            
            img = draw_ludo_board(game.players, current_col, dice_value=dice)
            link = utils.upload(bot, img)
            
            bot.send_json({
                "handler": "chatroommessage", "roomid": room_id, 
                "type": "image", "url": link, "text": "Roll"
            })
            bot.send_message(room_id, msg_text)
            
            # Next Turn
            if dice != 6 and not killed_someone:
                game.next_turn()
            else:
                bot.send_message(room_id, "🎉 Bonus Turn!")

            # Inform next player
            next_id = game.get_current_player_id()
            next_name = game.players[next_id]['name']
            bot.send_message(room_id, f"👉 **@{next_name}'s** Turn.")

        return True

    # 5. STOP GAME (!end)
    if cmd == "end":
        with game_lock:
            if room_id in games:
                del games[room_id]
                bot.send_message(room_id, "🛑 Game Ended.")
        return True

    return False
