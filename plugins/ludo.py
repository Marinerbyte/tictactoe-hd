import time
import random
import threading
from PIL import Image, ImageDraw

# --- IMPORTS ---
# Hum naya banaya hua 'ludo_utils' use karenge best performance ke liye
try: 
    import ludo_utils as utils
except ImportError: 
    print("[Ludo] CRITICAL ERROR: 'ludo_utils.py' not found. Please create it.")

try: 
    from db import add_game_result
except: 
    print("[Ludo] DB Error")

# --- GLOBAL VARIABLES ---
games = {}
game_lock = threading.Lock()
BOT_INSTANCE = None 

# --- THEMES & ASSETS ---
THEMES = {
    'R': {'name': 'Red', 'hex': '#e74c3c', 'icon': "https://img.icons8.com/3d-fluency/94/iron-man.png"},
    'G': {'name': 'Green', 'hex': '#2ecc71', 'icon': "https://img.icons8.com/3d-fluency/94/hulk.png"},
    'Y': {'name': 'Yellow', 'hex': '#f1c40f', 'icon': "https://img.icons8.com/3d-fluency/94/pikachu-pokemon.png"},
    'B': {'name': 'Blue', 'hex': '#3498db', 'icon': "https://img.icons8.com/3d-fluency/94/captain-america.png"}
}
CROWN_ICON = "https://img.icons8.com/emoji/96/crown-emoji.png"

# --- 📍 MASTER PATH MAPPING (15x15 GRID) ---
# Ye 52 coordinates hain jahan se safed dabbe (white boxes) draw honge.
# Token bhi bilkul inhi coordinates par chalega.
FINAL_PATH = [
    (1,13),(2,13),(3,13),(4,13),(5,13), # Bottom Left -> Right
    (6,12),(6,11),(6,10),(6,9),(6,8),   # Bottom Middle -> Up
    (5,8),(4,8),(3,8),(2,8),(1,8),(0,8), # Left Middle -> Left
    (0,7), (0,6), # Turn Up
    (1,6),(2,6),(3,6),(4,6),(5,6),       # Left Top -> Right
    (6,5),(6,4),(6,3),(6,2),(6,1),(6,0), # Top Middle -> Up
    (7,0), (8,0), # Turn Right
    (8,1),(8,2),(8,3),(8,4),(8,5),       # Top Right -> Down
    (9,6),(10,6),(11,6),(12,6),(13,6),(14,6), # Right Top -> Right
    (14,7), (14,8), # Turn Down
    (13,8),(12,8),(11,8),(10,8),(9,8),   # Right Bottom -> Left
    (8,9),(8,10),(8,11),(8,12),(8,13),(8,14), # Bottom Right -> Down
    (7,14), (6,14) # Close Loop
]

def setup(bot):
    global BOT_INSTANCE
    BOT_INSTANCE = bot
    threading.Thread(target=game_cleanup_loop, daemon=True).start()
    print("[Ludo] Complete Avatar Edition Loaded.")

# ==========================================
# 🕒 AUTO CLEANUP (90s / 45s Rule)
# ==========================================
def game_cleanup_loop():
    while True:
        time.sleep(5)
        if not games: continue
        now = time.time(); to_delete = []
        
        with game_lock:
            for rid, g in games.items():
                # Lobby Timeout (5 mins)
                if g.state == 'lobby' and now - g.created_at > 300:
                    if BOT_INSTANCE: BOT_INSTANCE.send_message(rid, "⏳ **Lobby Expired**")
                    to_delete.append(rid); continue
                
                # Game Dead (90s)
                if now - g.last_interaction > 90:
                    if BOT_INSTANCE: BOT_INSTANCE.send_message(rid, "💤 **Game Closed** (Inactive)")
                    to_delete.append(rid); continue
                
                # Player Move Timeout (45s)
                uid, p = g.get_current_player()
                if uid and (now - g.turn_start_time > 45):
                    if BOT_INSTANCE: BOT_INSTANCE.send_message(rid, f"⏱️ **@{p['name']}** Skipped Turn!")
                    
                    # Skip logic
                    g.turn_index = (g.turn_index + 1) % len(g.turn_list)
                    g.turn_start_time = time.time()
                    n_uid, n_p = g.get_current_player()
                    if BOT_INSTANCE: BOT_INSTANCE.send_message(rid, f"👉 **@{n_p['name']}'s** Turn")
                    
        for rid in to_delete:
            if rid in games: del games[rid]

# ==========================================
# 📍 COORDINATE CALCULATOR
# ==========================================
def get_coordinates(step, color, sz, mx, my):
    # Offsets based on Color (Red=0, Green=13, etc)
    offset = 0
    if color == 'G': offset = 13
    elif color == 'Y': offset = 26
    elif color == 'B': offset = 39
    
    c, r = 7, 7 # Default Center
    
    if step == -1: # Home Base Positions
        if color == 'R': c, r = 2.5, 11.5
        if color == 'G': c, r = 2.5, 2.5
        if color == 'Y': c, r = 11.5, 2.5
        if color == 'B': c, r = 11.5, 11.5
        return mx + c*sz + sz//2, my + r*sz + sz//2
        
    elif step >= 51: # Home Run (Entering Center)
        dist = step - 51
        if color == 'R': c, r = 7, 13 - dist
        elif color == 'G': c, r = 1 + dist, 7
        elif color == 'Y': c, r = 7, 1 + dist
        elif color == 'B': c, r = 13 - dist, 7
        if step >= 56: c, r = 7, 7
        
    else: # Main Track
        idx = (step + offset) % 52
        if idx < len(FINAL_PATH): c, r = FINAL_PATH[idx]
            
    # Convert Grid (0-14) to Pixels
    return mx + (c * sz) + (sz // 2), my + (r * sz) + (sz // 2)

# ==========================================
# 🎨 GRAPHICS ENGINE (HD + AVATARS)
# ==========================================
def draw_ludo_board_hd(players, dice_val=None, rolling=False):
    SZ = 40 # Cell Size
    W, H = SZ * 15 + 40, SZ * 15 + 40
    img = utils.create_canvas(W, H, "#2c3e50") # Dark Background
    d = ImageDraw.Draw(img)
    mx, my = 20, 20
    
    # 1. DRAW HOMES (With Big Avatar)
    homes = [('G',0,0,6,6), ('Y',9,0,15,6), ('R',0,9,6,15), ('B',9,9,15,15)]
    for code, c1, r1, c2, r2 in homes:
        # Base Box
        d.rectangle([mx+c1*SZ, my+r1*SZ, mx+c2*SZ, my+r2*SZ], fill=THEMES[code]['hex'], outline="black", width=2)
        # Inner Circle
        d.ellipse([mx+(c1+0.5)*SZ, my+(r1+0.5)*SZ, mx+(c2-0.5)*SZ, my+(r2-0.5)*SZ], fill="white", outline="black")
        
        # FIND OWNER
        owner = next((p for p in players.values() if p['color'] == code), None)
        cx, cy = mx+((c1+c2)*SZ)//2, my+((r1+r2)*SZ)//2
        
        if owner:
            # Download Avatar (using ludo_utils robust downloader)
            u_img = utils.get_image(owner.get('avatar_url'))
            
            if u_img:
                u_img = utils.circle_crop(u_img, size=110)
                if u_img:
                    img.paste(u_img, (int(cx-55), int(cy-55)), u_img)
            
            # Name Tag
            name = owner['name'][:8]
            d.rounded_rectangle([cx-40, cy+35, cx+40, cy+55], radius=5, fill="black")
            utils.write_text(d, (cx, cy+38), name, size=12, align="center", col="white")
        else:
            utils.write_text(d, (cx, cy), code, size=40, align="center", col="#888")

    # 2. DRAW TRACKS (White Boxes)
    # Using the FINAL_PATH list ensures visuals match logic 100%
    for c, r in FINAL_PATH:
        x, y = mx+c*SZ, my+r*SZ
        d.rectangle([x, y, x+SZ, y+SZ], fill="white", outline="#555", width=1)
        
    # Colored Home Runs
    for i in range(1, 6): d.rectangle([mx+7*SZ, my+(13-i)*SZ, mx+8*SZ, my+(14-i)*SZ], fill=THEMES['R']['hex'], outline="black")
    for i in range(1, 6): d.rectangle([mx+(1+i)*SZ, my+7*SZ, mx+(2+i)*SZ, my+8*SZ], fill=THEMES['G']['hex'], outline="black")
    for i in range(1, 6): d.rectangle([mx+7*SZ, my+(1+i)*SZ, mx+8*SZ, my+(2+i)*SZ], fill=THEMES['Y']['hex'], outline="black")
    for i in range(1, 6): d.rectangle([mx+(13-i)*SZ, my+7*SZ, mx+(14-i)*SZ, my+8*SZ], fill=THEMES['B']['hex'], outline="black")

    # 3. DRAW TOKENS (Small Avatars)
    # Find Leader for Crown
    max_s = -1; leader = None
    for uid, p in players.items():
        if p['step'] > max_s and p['step'] > 0: max_s = p['step']; leader = uid
        
    for uid, p in players.items():
        px, py = get_coordinates(p['step'], p['color'], SZ, mx, my)
        
        # Token Avatar
        t_img = utils.get_image(p.get('avatar_url'))
        
        if t_img:
            t_img = utils.circle_crop(t_img, size=38)
            # Border
            bg = Image.new('RGBA', (42,42), (0,0,0,0))
            ImageDraw.Draw(bg).ellipse([0,0,42,42], fill=THEMES[p['color']]['hex'])
            if t_img: bg.paste(t_img, (2,2), t_img)
            img.paste(bg, (int(px-21), int(py-21)), bg)
        else:
            # Fallback Dot
            d.ellipse([px-18, py-18, px+18, py+18], fill=THEMES[p['color']]['hex'], outline="white", width=2)
        
        # Name Bubble
        d.rounded_rectangle([px-22, py-32, px+22, py-22], radius=4, fill="white", outline="black")
        utils.write_text(d, (px, py-27), p['name'][:4], size=9, align="center", col="black")

        # Crown Logic
        if uid == leader:
            d.ellipse([px+10, py-30, px+25, py-15], fill="gold", outline="black")
            utils.write_text(d, (px+18, py-22), "1", size=10, align="center", col="black")

    # 4. DICE
    if rolling:
        utils.write_text(d, (W//2, H//2), "ROLLING...", size=40, align="center", col="white", shadow=True)
    elif dice_val:
        d.rounded_rectangle([W//2-35, H//2-35, W//2+35, H//2+35], radius=10, fill="white", outline="gold", width=3)
        utils.write_text(d, (W//2, H//2), str(dice_val), size=40, align="center", col="black")

    return img

# ==========================================
# ⚙️ GAME LOGIC CLASS
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

# ==========================================
# ⚡ BACKGROUND TASK HANDLERS
# ==========================================
def task_create(bot, room_id, g):
    img = draw_ludo_board_hd(g.players)
    link = utils.upload(bot, img)
    if link:
        bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Lobby"})
        bot.send_message(room_id, f"🎲 **Ludo!** Bet: {g.bet}\nType `!join` to enter.")
    else:
        bot.send_message(room_id, "⚠️ Upload Failed. Check Console.")

def task_roll(bot, room_id, g, uid, user, dice):
    # Illusion
    r_img = draw_ludo_board_hd(g.players, rolling=True)
    r_link = utils.upload(bot, r_img)
    if r_link: 
        bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": r_link, "text": "..."})
    
    time.sleep(1.5)
    
    # Logic Update
    with game_lock:
        p = g.players[str(uid)]
        msg = ""; is_win = False
        
        if p['step'] == -1: 
            p['step'] = 0; msg = "Start!"
        else:
            ns = p['step'] + dice
            if ns >= 56: p['step'] = 57; is_win = True
            elif ns < 51:
                # Cut Logic
                for oid, op in g.players.items():
                    if oid != str(uid) and op['step'] == ns: 
                        op['step'] = -1; msg = f"⚔️ Cut {op['name']}!"
                p['step'] = ns
            else: p['step'] = ns
        
        # Turn Management
        if not is_win and dice != 6:
            g.turn_index = (g.turn_index + 1) % len(g.turn_list)
        
        g.turn_start_time = time.time(); g.last_interaction = time.time()
        n_uid, n_p = g.get_current_player()

    # Final Image
    f_img = draw_ludo_board_hd(g.players, dice_val=dice)
    f_link = utils.upload(bot, f_img)
    
    if f_link:
        bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": f_link, "text": str(dice)})
    
    bot.send_message(room_id, f"🎲 **{user}** rolled {dice}! {msg}")
    
    if is_win:
        rew = g.bet * len(g.players); add_game_result(uid, user, "ludo", rew, True)
        bot.send_message(room_id, f"🎉 **{user} WINS!** +{rew} Coins")
        with game_lock: del games[room_id]
        return
        
    if dice != 6: bot.send_message(room_id, f"👉 **@{n_p['name']}'s** Turn")
    else: bot.send_message(room_id, "🎉 Bonus Turn!")

# ==========================================
# 📨 MAIN COMMAND HANDLER
# ==========================================
def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    uid = data.get('userid', user)
    
    # 🛑 BOT PREVENTION
    if str(uid) == str(bot.user_id): return False
    
    # ✅ EXTRACT AVATAR URL CORRECTLY
    av_id = data.get("avatar")
    av_url = f"https://cdn.howdies.app/avatar?image={av_id}" if av_id else None

    # !ludo
    if cmd == "ludo":
        bet = 0
        if args and args[0].isdigit(): bet = int(args[0])
        with game_lock:
            if room_id in games: return True
            g = LudoGame(room_id, bet, uid)
            g.add_player(uid, user, av_url)
            if bet > 0: add_game_result(uid, user, "ludo", -bet, False)
            games[room_id] = g
        utils.run_in_bg(task_create, bot, room_id, g)
        return True

    # !join
    if cmd == "join":
        with game_lock:
            g = games.get(room_id)
            if not g or g.state != 'lobby': return False
            if str(uid) in g.players: return True
            if g.add_player(uid, user, av_url):
                if g.bet > 0: add_game_result(uid, user, "ludo", -g.bet, False)
                bot.send_message(room_id, f"✅ Joined!")
                utils.run_in_bg(task_create, bot, room_id, g) # Update board
            else: bot.send_message(room_id, "Full!")
        return True

    # !start
    if cmd == "start":
        with game_lock:
            g = games.get(room_id)
            if not g: return False
            if len(g.players) < 2: bot.send_message(room_id, "Need 2+ Players."); return True
            g.state = 'playing'; g.turn_list = list(g.players.keys()); g.turn_start_time = time.time()
            bot.send_message(room_id, "🔥 **Started!** First `!roll`")
        return True

    # !roll
    if cmd == "roll":
        with game_lock:
            g = games.get(room_id)
            if not g or g.state != 'playing': return False
            c_uid, _ = g.get_current_player()
            if str(uid) != str(c_uid): return True
            dice = random.randint(1, 6)
        utils.run_in_bg(task_roll, bot, room_id, g, uid, user, dice)
        return True

    # !stop
    if cmd == "stop":
        with game_lock:
            g = games.get(room_id)
            if g and str(uid) == str(g.creator_id):
                del games[room_id]; bot.send_message(room_id, "🛑 Stopped.")
        return True

    return False
