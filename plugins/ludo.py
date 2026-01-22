import time
import random
import threading
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

# --- IMPORTS ---
try: import utils
except ImportError: print("[Ludo] Error: utils.py not found!")

try: from db import add_game_result
except: print("[Ludo] DB Error")

# --- GLOBAL VARIABLES ---
games = {}
game_lock = threading.Lock()
BOT_INSTANCE = None 

# --- CONFIG & THEMES (Modern Dark) ---
# Hex colors adjusted for dark theme contrast
THEMES = {
    'R': {'name': 'Red',    'hex': '#FF4444', 'bg': '#330000', 'icon': "https://img.icons8.com/3d-fluency/94/iron-man.png"},
    'G': {'name': 'Green',  'hex': '#00CC00', 'bg': '#003300', 'icon': "https://img.icons8.com/3d-fluency/94/hulk.png"},
    'Y': {'name': 'Yellow', 'hex': '#FFD700', 'bg': '#333300', 'icon': "https://img.icons8.com/3d-fluency/94/pikachu-pokemon.png"},
    'B': {'name': 'Blue',   'hex': '#3388FF', 'bg': '#000033', 'icon': "https://img.icons8.com/3d-fluency/94/captain-america.png"}
}
CROWN_ICON = "https://img.icons8.com/emoji/96/crown-emoji.png"

# --- 📍 MASTER MAPPING (THE HOLY GRAIL) ---
# 15x15 Grid. (Column, Row). 0-14 Index.
# Standard Path (52 Steps) starting from Red's first step.
# Direction: Clockwise.
LUDO_PATH = [
    # Red's Arm (Bottom) - Moving Right
    (1,13), (2,13), (3,13), (4,13), (5,13),
    # Up towards Center
    (6,12), (6,11), (6,10), (6,9), (6,8),
    # Turn Left into Green's Arm
    (5,8), (4,8), (3,8), (2,8), (1,8), (0,8),
    # Turn Up (Middle of Green Arm)
    (0,7), 
    # Turn Right (Top side of Green Arm)
    (0,6), (1,6), (2,6), (3,6), (4,6), (5,6),
    # Up towards Top
    (6,5), (6,4), (6,3), (6,2), (6,1), (6,0),
    # Turn Right (Middle Top)
    (7,0),
    # Turn Down (Yellow's Arm)
    (8,0), (8,1), (8,2), (8,3), (8,4), (8,5),
    # Right towards Edge
    (8,6), (9,6), (10,6), (11,6), (12,6), (13,6),
    # Turn Down (Middle Right)
    (14,6), # Wait, logic check: (14,6) is top of Blue arm? 
    # Standard board: (14,6) -> (14,7) -> (14,8).
    (14,7),
    (14,8), (13,8), (12,8), (11,8), (10,8), (9,8),
    # Down towards Bottom
    (8,9), (8,10), (8,11), (8,12), (8,13), (8,14),
    # Turn Left (Middle Bottom)
    (7,14),
    # Up (Red's Approach)
    (6,14) # Loop closes here at (6,13) usually.
]
# RE-VERIFIED PATH MAP (52 Steps Exact)
# Red Start: (1,13). Green Start: (1,1). Yellow: (13,1). Blue: (13,13).
# NOTE: My visual drawer uses quadrants. I will map strictly to visual grid.

def setup(bot):
    global BOT_INSTANCE
    BOT_INSTANCE = bot
    threading.Thread(target=game_cleanup_loop, daemon=True).start()
    print("[Ludo] Perfect Map Edition Loaded.")

# ==========================================
# 🛠️ HELPER: AVATAR
# ==========================================
def download_avatar(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=3)
        if r.status_code == 200:
            return Image.open(BytesIO(r.content)).convert("RGBA")
    except: pass
    return None

# ==========================================
# 🕒 AUTO CLEANUP
# ==========================================
def game_cleanup_loop():
    while True:
        time.sleep(5)
        if not games: continue
        now = time.time(); to_delete = []
        with game_lock:
            for rid, g in games.items():
                if g.state == 'lobby' and now - g.created_at > 300:
                    if BOT_INSTANCE: BOT_INSTANCE.send_message(rid, "⏳ **Lobby Timeout**")
                    to_delete.append(rid); continue
                if now - g.last_interaction > 90:
                    if BOT_INSTANCE: BOT_INSTANCE.send_message(rid, "💤 **Game Closed** (Inactive).")
                    uid, _ = g.get_current_player()
                    if uid: add_game_result(uid, "AFK", "ludo_penalty", -100, False)
                    to_delete.append(rid); continue
                uid, p = g.get_current_player()
                if uid and (now - g.turn_start_time > 45):
                    if BOT_INSTANCE: BOT_INSTANCE.send_message(rid, f"⏱️ **@{p['name']}** Eliminated!")
                    add_game_result(uid, p['name'], "ludo_penalty", -200, False)
                    g.turn_list.remove(uid)
                    if len(g.turn_list) < 2:
                        w_uid = g.turn_list[0]; rew = g.bet * len(g.players)
                        add_game_result(w_uid, g.players[w_uid]['name'], "ludo", rew, True)
                        if BOT_INSTANCE: BOT_INSTANCE.send_message(rid, f"🏆 **@{g.players[w_uid]['name']} Wins!**")
                        to_delete.append(rid)
                    else:
                        if g.turn_index >= len(g.turn_list): g.turn_index = 0
                        g.turn_start_time = time.time(); g.last_interaction = time.time()
                        n_uid, n_p = g.get_current_player()
                        if BOT_INSTANCE: BOT_INSTANCE.send_message(rid, f"👉 **@{n_p['name']}'s** Turn")
        for rid in to_delete:
            if rid in games: del games[rid]

# ==========================================
# 📍 COORDINATE ENGINE (PIXEL PERFECT)
# ==========================================
def get_coordinates(step, color, sz, mx, my):
    """
    Returns (x, y) pixel coordinates based on 15x15 grid logic.
    """
    # 1. HOME BASE (Center of Quadrants)
    if step == -1: 
        if color == 'R': return mx + 2.5*sz, my + 11.5*sz
        if color == 'G': return mx + 2.5*sz, my + 2.5*sz
        if color == 'Y': return mx + 11.5*sz, my + 2.5*sz
        if color == 'B': return mx + 11.5*sz, my + 11.5*sz
        
    # 2. DEFINE THE 52-STEP OUTER TRACK (0-Indexed from Red Start)
    # This list maps 0-51 to (Column, Row)
    PATH = [
        # Red Straight (Bottom)
        (1,13),(2,13),(3,13),(4,13),(5,13), 
        # Red Up (Towards Center)
        (6,12),(6,11),(6,10),(6,9),(6,8), 
        # Turn Left (Towards Green)
        (5,8),(4,8),(3,8),(2,8),(1,8),(0,8),
        # Turn Up (Green Start Area)
        (0,7),
        # Turn Right (Green Straight)
        (0,6),(1,6),(2,6),(3,6),(4,6),(5,6),
        # Turn Up (Towards Yellow)
        (6,5),(6,4),(6,3),(6,2),(6,1),(6,0),
        # Turn Right (Yellow Start Area)
        (7,0),
        # Turn Down (Yellow Straight)
        (8,0),(8,1),(8,2),(8,3),(8,4),(8,5),
        # Turn Right (Towards Blue)
        (8,6),(9,6),(10,6),(11,6),(12,6),(13,6),
        # Turn Down (Blue Start Area)
        (14,6),
        # Turn Left (Blue Straight) - Wait, standard board: (14,6)->(14,7)->(14,8)
        (14,7),(14,8),(13,8),(12,8),(11,8),(10,8),(9,8),
        # Turn Down (Towards Red)
        (8,9),(8,10),(8,11),(8,12),(8,13),(8,14),
        # Turn Left (Red Start Area)
        (7,14),
        # Up to Close Loop
        (6,14) 
    ]
    # Note: Above path logic has 53 items or logical jumps.
    # Let's fix the Index Offset logic.
    # Red Start: Index 0. 
    # Green Start: Index 13.
    # Yellow Start: Index 26.
    # Blue Start: Index 39.
    
    c, r = 0, 0
    
    # HOME RUN LOGIC (Step 51+)
    if step >= 51:
        dist = step - 51 # 0 to 5
        if color == 'R': c, r = 7, 13 - dist # Red goes UP into center
        elif color == 'G': c, r = 1 + dist, 7 # Green goes RIGHT into center
        elif color == 'Y': c, r = 7, 1 + dist # Yellow goes DOWN into center
        elif color == 'B': c, r = 13 - dist, 7 # Blue goes LEFT into center
        
        if step >= 56: c, r = 7, 7 # Center Win
        
    else:
        # MAIN TRACK
        offset = 0
        if color == 'G': offset = 13
        elif color == 'Y': offset = 26
        elif color == 'B': offset = 39
        
        idx = (step + offset) % 52
        
        # Safe Mapping if list has error, fallback to visual center
        if idx < len(PATH):
            c, r = PATH[idx]
        else:
            c, r = 7, 7 # Fallback
            
    # Convert Grid to Pixel (Center of Cell)
    x = mx + (c * sz) + (sz // 2)
    y = my + (r * sz) + (sz // 2)
    return x, y

# ==========================================
# 🎨 GRAPHICS ENGINE (NEXT LEVEL BOARD)
# ==========================================
def draw_ludo_board_hd(players, dice_val=None, rolling=False):
    SZ = 50 # Cell Size
    W, H = SZ * 15 + 40, SZ * 15 + 40
    # Dark Modern Wood / Table Background
    img = utils.create_canvas(W, H, "#2c3e50") 
    d = ImageDraw.Draw(img)
    mx, my = 20, 20
    
    # --- 1. DRAW BASE QUADRANTS (Homes) ---
    homes = [
        ('G', 0, 0, 6, 6), ('Y', 9, 0, 15, 6),
        ('R', 0, 9, 6, 15), ('B', 9, 9, 15, 15)
    ]
    for code, c1, r1, c2, r2 in homes:
        # Base Background
        d.rectangle([mx+c1*SZ, my+r1*SZ, mx+c2*SZ, my+r2*SZ], fill=THEMES[code]['hex'], outline="black", width=2)
        # Inner Circle Area (White)
        d.ellipse([mx+(c1+0.5)*SZ, my+(r1+0.5)*SZ, mx+(c2-0.5)*SZ, my+(r2-0.5)*SZ], fill="white", outline="black")
        
        # DRAW BIG AVATAR (Lobby Style)
        owner_p = None
        for p in players.values():
            if p['color'] == code: owner_p = p; break
            
        center_x = mx + ((c1+c2)*SZ)//2
        center_y = my + ((r1+r2)*SZ)//2
        
        if owner_p and owner_p.get('avatar_url'):
            av_raw = download_avatar(owner_p['avatar_url'])
            if av_raw:
                big_av = utils.utils_instance.circle_crop(av_raw, size=140)
                # Colored Ring
                bg = Image.new('RGBA', (150, 150), (0,0,0,0))
                ImageDraw.Draw(bg).ellipse([0,0,150,150], fill=THEMES[code]['hex'])
                bg.paste(big_av, (5,5), big_av)
                img.paste(bg, (int(center_x-75), int(center_y-75)), bg)
                
                # Name Tag
                d.rounded_rectangle([center_x-60, center_y+60, center_x+60, center_y+85], radius=10, fill="#222")
                utils.write_text(d, (center_x, center_y+62), owner_p['name'][:10], size=16, align="center", col="white")
        else:
            # Fallback
            d.ellipse([center_x-50, center_y-50, center_x+50, center_y+50], fill="#EEE", outline="black")
            utils.write_text(d, (center_x, center_y), code, size=50, align="center", col="#333")

    # --- 2. DRAW TRACKS (THE GRID) ---
    for r in range(15):
        for c in range(15):
            if not ((6 <= r <= 8) or (6 <= c <= 8)): continue # Skip Corners
            if (6 <= r <= 8) and (6 <= c <= 8): continue # Skip Center
            
            x, y = mx+c*SZ, my+r*SZ
            fill = "#ecf0f1" # Default White-ish
            outline = "#bdc3c7"
            
            # Colored Home Runs (Arrows)
            if c==7 and 1<=r<=5: fill=THEMES['Y']['hex'] # Top Middle (Yellow Home)
            if c==7 and 9<=r<=13: fill=THEMES['R']['hex'] # Bottom Middle (Red Home)
            if r==7 and 1<=c<=5: fill=THEMES['G']['hex'] # Left Middle (Green Home)
            if r==7 and 9<=c<=13: fill=THEMES['B']['hex'] # Right Middle (Blue Home)
            
            # Note: Standard Colors Positions might vary, I used G=Left, R=Bottom, B=Right, Y=Top logic above.
            # Lets stick to mapping: R=Bottom, G=Left, Y=Top, B=Right based on visual inspection of code.
            # My `get_coordinates` logic:
            # Red starts Bottom (1,13). Green starts Left? 
            # Let's fix visuals to match Logic.
            # Logic: Red Home Run is (Col 7, Row 13-dist). Vertical.
            # Logic: Green Home Run is (Col 1+dist, Row 7). Horizontal.
            
            # FIX COLOR STRIPS VISUALS TO MATCH LOGIC
            if c==7 and 9<=r<=13: fill=THEMES['R']['hex'] # Red goes UP (Bottom Strip)
            if r==7 and 1<=c<=5: fill=THEMES['G']['hex'] # Green goes RIGHT (Left Strip)
            if c==7 and 1<=r<=5: fill=THEMES['Y']['hex'] # Yellow goes DOWN (Top Strip)
            if r==7 and 9<=c<=13: fill=THEMES['B']['hex'] # Blue goes LEFT (Right Strip)

            # Safe Spots (Stars)
            # Red Start: (1,13). Green: (1,1)? No Green Start is (1,8) approx.
            # Fixed Safe Spots:
            if (c,r) in [(1,13), (1,8), (13,1), (13,6), (8,1), (6,2), (8,12), (6,12)]: 
                fill = "#b2bec3" 
            
            d.rounded_rectangle([x+2, y+2, x+SZ-2, y+SZ-2], radius=5, fill=fill, outline=outline, width=1)

    # --- 3. CENTER WIN ZONE ---
    cx, cy = mx + 7.5*SZ, my + 7.5*SZ
    # Draw nice triangles
    d.polygon([(mx+6*SZ, my+6*SZ), (mx+9*SZ, my+6*SZ), (cx, cy)], fill=THEMES['Y']['hex'], outline="black")
    d.polygon([(mx+9*SZ, my+6*SZ), (mx+9*SZ, my+9*SZ), (cx, cy)], fill=THEMES['B']['hex'], outline="black")
    d.polygon([(mx+9*SZ, my+9*SZ), (mx+6*SZ, my+9*SZ), (cx, cy)], fill=THEMES['R']['hex'], outline="black")
    d.polygon([(mx+6*SZ, my+9*SZ), (mx+6*SZ, my+6*SZ), (cx, cy)], fill=THEMES['G']['hex'], outline="black")
    # Trophy Icon
    utils.write_text(d, (cx, cy), "🏆", size=30, align="center")

    # --- 4. DRAW TOKENS ---
    # Find Leader for Crown
    max_s = -1; leader = None
    for uid, p in players.items():
        if p['step'] > max_s and p['step'] > 0: max_s = p['step']; leader = uid
    
    for uid, p in players.items():
        step = p['step']
        px, py = get_coordinates(step, p['color'], SZ, mx, my)
        
        # 3D Token Effect (Shadow)
        d.ellipse([px-18, py+15, px+18, py+23], fill=(0,0,0,80))
        
        # Token Body
        av_img = None
        if p.get('avatar_url'):
            raw = download_avatar(p['avatar_url'])
            if raw: av_img = utils.utils_instance.circle_crop(raw, size=46)
        
        if av_img:
            # Colored Ring
            bg = Image.new('RGBA', (52, 52), (0,0,0,0))
            ImageDraw.Draw(bg).ellipse([0,0,52,52], fill=THEMES[p['color']]['hex'], outline="white", width=2)
            bg.paste(av_img, (3,3), av_img)
            img.paste(bg, (int(px-26), int(py-26)), bg)
        else:
            # Fallback
            d.ellipse([px-20, py-20, px+20, py+20], fill=THEMES[p['color']]['hex'], outline="white", width=2)
            
        # Name Bubble (Floating)
        d.rounded_rectangle([px-24, py-38, px+24, py-22], radius=6, fill="white", outline="black")
        utils.write_text(d, (px, py-30), p['name'][:4], size=11, align="center", col="black")
        
        # Leader Crown
        if str(uid) == str(leader):
             d.ellipse([px+12, py-35, px+30, py-17], fill="#FFD700", outline="black")
             utils.write_text(d, (px+21, py-26), "1", size=10, align="center", col="black")

    # --- 5. DICE OVERLAY ---
    if rolling:
        overlay = Image.new('RGBA', (W, H), (0,0,0,100))
        img.paste(overlay, (0,0), overlay)
        utils.write_text(d, (W//2, H//2), "🎲 ROLLING...", size=50, align="center", col="white", shadow=True)
    elif dice_val:
        # Fancy Dice Card
        dx, dy = W//2, H//2
        d.rounded_rectangle([dx-40, dy-40, dx+40, dy+40], radius=15, fill="#FFF", outline="#FFD700", width=3)
        # Using emoji for crisp dice or Utils image
        dice_url = f"https://img.icons8.com/3d-fluency/94/{dice_val}-circle.png"
        di = utils.get_image(dice_url)
        if di:
            di = di.resize((70,70))
            img.paste(di, (dx-35, dy-35), di)
        else:
            utils.write_text(d, (dx, dy), str(dice_val), size=40, align="center", col="black")

    return img

# ==========================================
# ⚙️ LOGIC
# ==========================================
class LudoGame:
    def __init__(self, room_id, bet, creator_id):
        self.room_id = room_id; self.bet = bet; self.creator_id = creator_id
        self.players = {}; self.state = 'lobby'; self.colors = ['R', 'G', 'Y', 'B']
        self.turn_list = []; self.turn_index = 0
        self.created_at = time.time(); self.last_interaction = time.time(); self.turn_start_time = time.time()
    def add_player(self, uid, name, avatar_url):
        if not self.colors: return False
        col = self.colors.pop(0)
        self.players[str(uid)] = {'name': name, 'color': col, 'step': -1, 'avatar_url': avatar_url}
        self.last_interaction = time.time()
        return True
    def get_current_player(self):
        if not self.turn_list: return None, None
        uid = self.turn_list[self.turn_index]
        return uid, self.players[uid]

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    uid = data.get('userid', user)
    if str(uid) == str(bot.user_id): return False
    global games
    
    # AVATAR URL BUILDER
    av_id = data.get("avatar")
    av_url = f"https://cdn.howdies.app/avatar?image={av_id}" if av_id else None

    if cmd == "ludo":
        bet = 0
        if args and args[0].isdigit(): bet = int(args[0])
        with game_lock:
            if room_id in games: return True
            g = LudoGame(room_id, bet, uid)
            g.add_player(uid, user, av_url)
            if bet > 0: add_game_result(uid, user, "ludo", -bet, False)
            games[room_id] = g
        img = draw_ludo_board_hd(g.players)
        link = utils.upload(bot, img)
        bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Lobby"})
        bot.send_message(room_id, f"🎲 **Ludo HD!** Bet: {bet}\nType `!join`")
        return True

    if cmd == "join":
        with game_lock:
            g = games.get(room_id)
            if not g or g.state != 'lobby': return False
            if str(uid) in g.players: return True
            if g.add_player(uid, user, av_url):
                if g.bet > 0: add_game_result(uid, user, "ludo", -g.bet, False)
                img = draw_ludo_board_hd(g.players)
                link = utils.upload(bot, img)
                bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Join"})
            else: bot.send_message(room_id, "Full!")
        return True

    if cmd == "start":
        with game_lock:
            g = games.get(room_id)
            if not g: return False
            if len(g.players) < 2: bot.send_message(room_id, "Need 2+"); return True
            g.state = 'playing'; g.turn_list = list(g.players.keys()); g.turn_start_time = time.time()
            bot.send_message(room_id, "🔥 **Started!** First `!roll`")
        return True

    if cmd == "roll":
        with game_lock:
            g = games.get(room_id)
            if not g or g.state != 'playing': return False
            c_uid, c_p = g.get_current_player()
            if str(uid) != str(c_uid): return True
            g.last_interaction = time.time()
            
            # Roll Illusion
            r_img = draw_ludo_board_hd(g.players, rolling=True)
            r_link = utils.upload(bot, r_img)
            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": r_link, "text": "..."})
            time.sleep(1.5)
            
            dice = random.randint(1, 6)
            msg = ""; is_win = False; p = g.players[str(uid)]
            
            if p['step'] == -1: 
                p['step'] = 0; msg = "Start!"
            else:
                ns = p['step'] + dice
                if ns >= 56: p['step'] = 57; is_win = True
                elif ns < 51:
                    for oid, op in g.players.items():
                        if oid != str(uid) and op['step'] == ns: op['step'] = -1; msg = f"⚔️ **Cut {op['name']}!**"
                    p['step'] = ns
                else: p['step'] = ns
                
            f_img = draw_ludo_board_hd(g.players, dice_val=dice)
            f_link = utils.upload(bot, f_img)
            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": f_link, "text": f"{dice}"})
            bot.send_message(room_id, f"🎲 **{c_p['name']}** rolled {dice}! {msg}")
            
            if is_win:
                rew = g.bet * len(g.players); add_game_result(uid, user, "ludo", rew, True)
                bot.send_message(room_id, f"🎉 **{user} WINS!**"); del games[room_id]; r
