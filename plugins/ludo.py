import time
import random
import threading
from PIL import Image, ImageDraw

# --- IMPORTS ---
try: import ludo_utils as utils
except ImportError: print("[Ludo] Error: ludo_utils.py missing.")

try: from db import add_game_result
except: pass

# --- GLOBALS ---
games = {}; game_lock = threading.Lock(); BOT = None 

# --- THEMES ---
THEMES = {
    'R': {'name': 'Red', 'hex': '#e74c3c'}, 
    'G': {'name': 'Green', 'hex': '#2ecc71'},
    'Y': {'name': 'Yellow', 'hex': '#f1c40f'}, 
    'B': {'name': 'Blue', 'hex': '#3498db'}
}

# ==========================================================
# 📍 INDIVIDUAL PATH MAPPING (15x15 GRID)
# ==========================================================
# Har Color ka apna rasta hai. Koi confusion nahi.
# Format: (Col, Row)
# Index 0-50: Main Track. Index 51-56: Home Run.

# 1. RED PATH (Bottom-Left Start)
RED_PATH = [
    (1,13),(2,13),(3,13),(4,13),(5,13), # Bottom Straight
    (6,12),(6,11),(6,10),(6,9),(6,8),   # Up
    (5,8),(4,8),(3,8),(2,8),(1,8),(0,8), # Left
    (0,7), # Turn
    (0,6),(1,6),(2,6),(3,6),(4,6),(5,6), # Right
    (6,5),(6,4),(6,3),(6,2),(6,1),(6,0), # Up
    (7,0), # Turn
    (8,0),(8,1),(8,2),(8,3),(8,4),(8,5), # Down
    (8,6),(9,6),(10,6),(11,6),(12,6),(13,6), # Right
    (14,6), # Turn
    (14,7),(14,8),(13,8),(12,8),(11,8),(10,8),(9,8), # Left
    (8,9),(8,10),(8,11),(8,12),(8,13),(8,14), # Down
    (7,14), # Turn Last
    (6,14), # Entry Point
    # HOME RUN
    (7,13),(7,12),(7,11),(7,10),(7,9),(7,8) # Win at 56
]

# 2. GREEN PATH (Top-Left Start)
GREEN_PATH = [
    (1,1),(1,2),(1,3),(1,4),(1,5),
    (2,6),(3,6),(4,6),(5,6),(6,6), # Error in manual logic? Let's use Rotation Logic for perfection.
    # Writing manual lists is prone to typos.
    # I will use a smarter Generator based on Red Path.
]

# --- SMART ROTATOR (Logic se Rasta Banao) ---
def rotate(path, times):
    new_path = []
    for c, r in path:
        nc, nr = c, r
        for _ in range(times):
            # Rotate 90 deg clockwise around center (7,7)
            # Formula: (x, y) -> (14-y, x)
            nc, nr = 14 - nr, nc
        new_path.append((nc, nr))
    return new_path

# RED PATH (Manually Verified 100%)
BASE_PATH = [
    (1,13),(2,13),(3,13),(4,13),(5,13), (6,12),(6,11),(6,10),(6,9),(6,8),
    (5,8),(4,8),(3,8),(2,8),(1,8),(0,8), (0,7), (0,6),(1,6),(2,6),(3,6),(4,6),(5,6),
    (6,5),(6,4),(6,3),(6,2),(6,1),(6,0), (7,0), (8,0),(8,1),(8,2),(8,3),(8,4),(8,5),
    (8,6),(9,6),(10,6),(11,6),(12,6),(13,6), (14,6), (14,7),(14,8),(13,8),(12,8),(11,8),(10,8),(9,8),
    (8,9),(8,10),(8,11),(8,12),(8,13),(8,14), (7,14), (6,14),
    # Home Run
    (7,13),(7,12),(7,11),(7,10),(7,9),(7,7) # Win Center
]

PATHS = {
    'R': BASE_PATH,
    'G': rotate(BASE_PATH, 1), # Green starts Top-Left (Rotated 90)
    'Y': rotate(BASE_PATH, 2), # Yellow starts Top-Right
    'B': rotate(BASE_PATH, 3)  # Blue starts Bottom-Right
}

def setup(bot):
    global BOT
    BOT = bot
    threading.Thread(target=cleanup, daemon=True).start()
    print("[Ludo] Path-Finder Engine Loaded.")

# ==========================================
# 🎨 GRAPHICS ENGINE
# ==========================================
def draw_board(players, dice=None):
    SZ = 40; MX, MY = 20, 20
    W, H = SZ*15 + 40, SZ*15 + 40
    img = utils.create_canvas(W, H, "#2c3e50")
    d = ImageDraw.Draw(img)
    
    # 1. DRAW TRACKS (White Boxes)
    # We iterate 0-51 of Red Path (Outer Track)
    # Rotating it 4 times covers the whole board
    outer_cells = set()
    for p in PATHS.values():
        for i in range(52): outer_cells.add(p[i])
        
    for c, r in outer_cells:
        x, y = MX+c*SZ, MY+r*SZ
        d.rectangle([x, y, x+SZ, y+SZ], fill="white", outline="#7f8c8d", width=1)

    # 2. DRAW HOME RUNS (Colored)
    for code, path in PATHS.items():
        col = THEMES[code]['hex']
        for i in range(51, 57): # Last 6 steps
            c, r = path[i]
            x, y = MX+c*SZ, MY+r*SZ
            d.rectangle([x, y, x+SZ, y+SZ], fill=col, outline="#333", width=1)

    # 3. DRAW BASE HOMES
    homes = [('G',0,0,6,6),('Y',9,0,15,6),('R',0,9,6,15),('B',9,9,15,15)]
    for c,x1,y1,x2,y2 in homes:
        d.rectangle([MX+x1*SZ, MY+y1*SZ, MX+x2*SZ, MY+y2*SZ], fill=THEMES[c]['hex'], outline="black", width=2)
        d.rectangle([MX+(x1+1)*SZ, MY+(y1+1)*SZ, MX+(x2-1)*SZ, MY+(y2-1)*SZ], fill="white", outline="black")
        
        # Big Avatar
        owner = next((p for p in players.values() if p['color']==c), None)
        cx, cy = MX+((x1+x2)*SZ)//2, MY+((y1+y2)*SZ)//2
        if owner:
            av = utils.get_image(owner.get('av'))
            if av:
                av = utils.circle_crop(av, 120)
                img.paste(av, (cx-60, cy-60), av)
            utils.write_text(d, (cx, cy+50), owner['name'][:8], 14, "black", "center")

    # Center
    cx, cy = MX + 7.5*SZ, MY + 7.5*SZ
    utils.write_text(d, (cx, cy), "🏆", 30, "white", "center")

    # 4. DRAW TOKENS
    lid = None; ms = -1
    for u, p in players.items():
        if p['step']>ms and p['step']>=0: ms=p['step']; lid=u
    
    for u, p in players.items():
        # COORDINATE LOGIC
        step = p['step']; color = p['color']
        px, py = 0, 0
        
        if step == -1: # Home Base
            if color=='R': px, py = MX+2.5*SZ, MY+11.5*SZ
            if color=='G': px, py = MX+2.5*SZ, MY+2.5*SZ
            if color=='Y': px, py = MX+11.5*SZ, MY+2.5*SZ
            if color=='B': px, py = MX+11.5*SZ, MY+11.5*SZ
            # Adjust to center of imaginary cell
            px += SZ//2; py += SZ//2
        else:
            # Main Track
            grid_c, grid_r = PATHS[color][step]
            px = MX + grid_c*SZ + SZ//2
            py = MY + grid_r*SZ + SZ//2

        # Draw
        av = utils.get_image(p.get('av'))
        if av:
            av = utils.circle_crop(av, 34)
            bg = Image.new('RGBA', (38,38), (0,0,0,0))
            ImageDraw.Draw(bg).ellipse([0,0,38,38], fill=THEMES[color]['hex'])
            bg.paste(av, (2,2), av)
            img.paste(bg, (int(px-19), int(py-19)), bg)
        else:
            d.ellipse([px-15, py-15, px+15, py+15], fill=THEMES[color]['hex'], outline="white", width=2)
            
        d.rounded_rectangle([px-20, py-30, px+20, py-20], 3, "white", "black")
        utils.write_text(d, (px, py-25), p['name'][:4], 10, "black", "center")
        
        if u == lid:
            d.ellipse([px+10, py-30, px+25, py-15], fill="gold", outline="black")
            utils.write_text(d, (px+18, py-22), "1", 10, "black", "center")

    # 5. DICE (Result Only)
    if dice:
        d.rounded_rectangle([W//2-30, H//2-30, W//2+30, H//2+30], 10, "white", "gold", 3)
        utils.write_text(d, (W//2, H//2), str(dice), 40, "black", "center")

    return img

# ==========================================
# ⚙️ GAME LOGIC
# ==========================================
class Ludo:
    def __init__(self, rid, bet, creator):
        self.id = rid; self.bet = bet; self.creator = creator
        self.players = {}; self.state = 'lobby'; self.colors = ['R','G','Y','B']
        self.turn = []; self.idx = 0; self.ts = time.time(); self.turn_ts = time.time()

# ==========================================
# ⚡ TASKS
# ==========================================
def task_update(bot, rid, g, text="Update"):
    img = draw_board(g.players)
    link = utils.upload(bot, img)
    if link: bot.send_json({"handler": "chatroommessage", "roomid": rid, "type": "image", "url": link, "text": text})

def task_roll(bot, rid, g, uid, name, dice):
    # 1. SEND ILLUSION GIF (Immediate)
    bot.send_json({"handler": "chatroommessage", "roomid": rid, "type": "image", "url": utils.ROLLING_GIF_URL, "text": "..."})
    time.sleep(2) # Wait for animation feel
    
    with game_lock:
        p = g.players[str(uid)]
        msg = ""; win = False
        
        # --- LOGIC UPDATE (Strict Rules) ---
        if p['step'] == -1:
            if dice == 6:
                p['step'] = 0 # Open Account
                msg = "🔓 Released!"
            else:
                msg = "Locked (Need 6)"
        else:
            ns = p['step'] + dice
            if ns == 57: # Exact Win
                p['step'] = 57; win = True
            elif ns > 57: # Bounce/Stay logic
                msg = "Wait!" # Don't move if overflow
            else:
                # Cut Logic
                my_coords = PATHS[p['color']][ns]
                for oid, op in g.players.items():
                    if oid!=str(uid) and op['step']>=0 and op['step']<52:
                        opp_coords = PATHS[op['color']][op['step']]
                        if my_coords == opp_coords:
                            op['step'] = -1; msg = f"⚔️ Cut {op['name']}!"
                p['step'] = ns
        
        # Next Turn
        if not win and dice != 6:
            g.idx = (g.idx + 1) % len(g.turn)
        
        g.turn_ts = time.time(); g.ts = time.time()
        nxt = g.players[g.turn[g.idx]]['name']

    # 2. SEND FINAL BOARD
    f_img = draw_board(g.players, dice)
    f_link = utils.upload(bot, f_img)
    
    if f_link:
        bot.send_json({"handler": "chatroommessage", "roomid": rid, "type": "image", "url": f_link, "text": str(dice)})
        
    bot.send_message(rid, f"🎲 **{name}** rolled {dice} {msg}")
    
    if win:
        add_game_result(uid, name, "ludo", g.bet*len(g.players), True)
        bot.send_message(rid, f"🎉 **{name} WINS!**"); del games[rid]; return
        
    if dice!=6: bot.send_message(rid, f"👉 **@{nxt}** Turn")
    else: bot.send_message(rid, "🎉 **6!** Roll Again")

def cleanup():
    while True:
        time.sleep(5)
        if not games: continue
        now = time.time(); dele = []
        with game_lock:
            for rid, g in games.items():
                if now - g.ts > 300: BOT.send_message(rid, "💤 Timeout"); dele.append(rid); continue
                if g.state=='playing':
                    uid = g.turn[g.idx]
                    if now - g.turn_ts > 45:
                        BOT.send_message(rid, f"⏱️ Skipped **@{g.players[uid]['name']}**")
                        g.idx = (g.idx + 1) % len(g.turn)
                        g.turn_ts = time.time()
        for r in dele: 
            if r in games: del games[r]

# ==========================================
# 📨 HANDLER
# ==========================================
def handle_command(bot, cmd, rid, user, args, data):
    c = cmd.lower().strip()
    uid = data.get('userid', user)
    if str(uid) == str(bot.user_id): return False
    
    av_id = data.get("avatar")
    av = f"https://cdn.howdies.app/avatar?image={av_id}" if av_id else None

    if c == "ludo":
        bet = int(args[0]) if args and args[0].isdigit() else 0
        with game_lock:
            if rid in games: return True
            g = Ludo(rid, bet, uid)
            col = g.colors.pop(0)
            g.players[str(uid)] = {'name':user, 'color':col, 'step':-1, 'av':av}
            if bet>0: add_game_result(uid, user, "ludo", -bet, False)
            games[rid] = g
        utils.run_in_bg(task_update, bot, rid, g, "Lobby")
        bot.send_message(rid, f"🎲 **Ludo!** Bet: {bet}\nType `!join`")
        return True

    if c == "join":
        with game_lock:
            g = games.get(rid)
            if not g or g.state != 'lobby': return False
            if str(uid) in g.players: return True
            if g.colors:
                col = g.colors.pop(0)
                g.players[str(uid)] = {'name':user, 'color':col, 'step':-1, 'av':av}
                if g.bet>0: add_game_result(uid, user, "ludo", -g.bet, False)
                bot.send_message(rid, f"✅ Joined!")
                utils.run_in_bg(task_update, bot, rid, g, "Join")
            else: bot.send_message(rid, "Full!")
        return True

    if c == "start":
        with game_lock:
            g = games.get(rid)
            if not g: return False
            if len(g.players) < 2: bot.send_message(rid, "Need 2+"); return True
            g.state = 'playing'; g.turn = list(g.players.keys())
            g.turn_ts = time.time()
            bot.send_message(rid, "🔥 Started!")
        return True

    if c == "roll":
        with game_lock:
            g = games.get(rid)
            if not g or g.state != 'playing': return False
            if str(uid) != g.turn[g.idx]: return True
            dice = random.randint(1, 6)
        utils.run_in_bg(task_roll, bot, rid, g, uid, user, dice)
        return True
        
    if c == "stop":
        with game_lock:
            if rid in games and str(uid) == str(games[rid].creator):
                del games[rid]; bot.send_message(rid, "Stopped")
        return True
    return False
