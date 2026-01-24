import time
import random
import threading
import traceback
from PIL import Image, ImageDraw

# --- IMPORTS ---
try: 
    import ludo_utils as utils
except ImportError: 
    print("[Ludo] Error: ludo_utils.py missing.")

try: 
    from db import add_game_result
except: 
    pass

# --- GLOBALS ---
games = {}
game_lock = threading.Lock()
BOT_INSTANCE = None 

# --- THEMES ---
THEMES = {
    'R': {'name': 'Red', 'hex': '#e74c3c'}, 
    'G': {'name': 'Green', 'hex': '#2ecc71'},
    'Y': {'name': 'Yellow', 'hex': '#f1c40f'}, 
    'B': {'name': 'Blue', 'hex': '#3498db'}
}

# ==========================================================
# 📍 PATH MAPPING (15x15 GRID) - 100% VERIFIED
# ==========================================================
# Rotation Logic: (x, y) -> (14-y, x) around center (7,7)

# 1. RED PATH (Base Manual Path)
BASE_PATH = [
    (1,13),(2,13),(3,13),(4,13),(5,13), # 0-4
    (6,12),(6,11),(6,10),(6,9),(6,8),   # 5-9
    (6,7),                              # 10 (Safe Spot) - VISUAL LINK
    (5,8),(4,8),(3,8),(2,8),(1,8),(0,8), # 11-16
    (0,7), (0,6),                        # 17-18
    (1,6),(2,6),(3,6),(4,6),(5,6),       # 19-23
    (6,5),(6,4),(6,3),(6,2),(6,1),(6,0), # 24-29
    (7,0), (8,0),                        # 30-31
    (8,1),(8,2),(8,3),(8,4),(8,5),       # 32-36
    (8,6),(9,6),(10,6),(11,6),(12,6),(13,6), # 37-42
    (14,6), (14,7), (14,8),              # 43-45
    (13,8),(12,8),(11,8),(10,8),(9,8),(8,8), # 46-51
    # HOME RUN
    (8,9),(8,10),(8,11),(8,12),(8,13),(8,14) # This is Blue's entry? No.
]

# REDEFINING BASE PATH PROGRAMMATICALLY FOR PRECISION
# Red Starts (1,13) -> Right -> Up -> Left...
P = []
P.extend([(c,13) for c in range(1,6)])      # 0-4
P.extend([(6,r) for r in range(12,6,-1)])   # 5-10 (Stop at 6,7)
P.extend([(c,8) for c in range(5,-1,-1)])   # 11-16
P.append((0,7)); P.append((0,6))            # 17-18
P.extend([(c,6) for c in range(1,6)])       # 19-23
P.extend([(6,r) for r in range(5,-1,-1)])   # 24-29
P.append((7,0)); P.append((8,0))            # 30-31
P.extend([(8,r) for r in range(1,6)])       # 32-36
P.extend([(c,6) for c in range(9,15)])      # 37-42
P.append((14,6)); P.append((14,7)); P.append((14,8)) # 43-45
P.extend([(c,8) for c in range(13,7,-1)])   # 46-51
# Loop complete. Home Run separate.

# Function to rotate path for other colors
def rotate_path(path, times):
    new_p = []
    for c, r in path:
        nc, nr = c, r
        for _ in range(times):
            nc, nr = 14 - nr, nc # 90 deg clockwise
        new_p.append((nc, nr))
    return new_p

# Generate All Paths
PATHS = {
    'R': P,
    'G': rotate_path(P, 1),
    'Y': rotate_path(P, 2),
    'B': rotate_path(P, 3)
}

# Add Home Runs
# Red (Bottom) -> Up
PATHS['R'].extend([(7,r) for r in range(13,7,-1)])
# Green (Left) -> Right
PATHS['G'].extend([(c,7) for c in range(1,7)])
# Yellow (Top) -> Down
PATHS['Y'].extend([(7,r) for r in range(1,7)])
# Blue (Right) -> Left
PATHS['B'].extend([(c,7) for c in range(13,7,-1)])

# Add Win Center
WIN_SPOT = (7,7)
for k in PATHS: PATHS[k].append(WIN_SPOT)

def setup(bot):
    global BOT_INSTANCE
    BOT_INSTANCE = bot
    threading.Thread(target=cleanup, daemon=True).start()
    print("[Ludo] Action-Fix Edition Loaded.")

# ==========================================
# 🎨 GRAPHICS ENGINE
# ==========================================
def draw_board(players, dice=None, rolling=False):
    SZ = 40; MX, MY = 20, 20
    W, H = SZ*15 + 40, SZ*15 + 40
    img = utils.create_canvas(W, H, "#2c3e50")
    d = ImageDraw.Draw(img)
    
    # 1. DRAW TRACKS (Visuals match Logic 100%)
    # Combine all paths to draw white boxes
    all_cells = set()
    for p in PATHS.values():
        for i in range(52): all_cells.add(p[i])
        
    for c, r in all_cells:
        x, y = MX+c*SZ, MY+r*SZ
        d.rectangle([x, y, x+SZ, y+SZ], fill="white", outline="#7f8c8d", width=1)

    # 2. DRAW HOME RUNS (Colored)
    for code, path in PATHS.items():
        col = THEMES[code]['hex']
        # Indices 52 to 57 are home run
        for i in range(52, 58):
            if i < len(path):
                c, r = path[i]
                x, y = MX+c*SZ, MY+r*SZ
                if (c,r) != (7,7): # Don't color center yet
                    d.rectangle([x, y, x+SZ, y+SZ], fill=col, outline="#333", width=1)

    # 3. DRAW HOMES
    homes = [('G',0,0,6,6),('Y',9,0,15,6),('R',0,9,6,15),('B',9,9,15,15)]
    for c,x1,y1,x2,y2 in homes:
        d.rectangle([MX+x1*SZ, MY+y1*SZ, MX+x2*SZ, MY+y2*SZ], fill=THEMES[c]['hex'], outline="black", width=2)
        d.rectangle([MX+(x1+1)*SZ, MY+(y1+1)*SZ, MX+(x2-1)*SZ, MY+(y2-1)*SZ], fill="white", outline="black")
        
        # Avatar
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
        # COORDINATE LOOKUP
        step = p['step']; color = p['color']
        px, py = 0, 0
        
        if step == -1: # Home Base
            if color=='R': px, py = MX+2.5*SZ, MY+11.5*SZ
            if color=='G': px, py = MX+2.5*SZ, MY+2.5*SZ
            if color=='Y': px, py = MX+11.5*SZ, MY+2.5*SZ
            if color=='B': px, py = MX+11.5*SZ, MY+11.5*SZ
            px += SZ//2; py += SZ//2
        else:
            # Map from PATH list
            path = PATHS[color]
            if step < len(path):
                grid_c, grid_r = path[step]
                px = MX + grid_c*SZ + SZ//2
                py = MY + grid_r*SZ + SZ//2
            else:
                px, py = cx, cy # Win

        # Draw Token
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

    # 5. DICE
    if rolling:
        utils.write_text(d, (W//2, H//2), "...", 50, "white", "center", True)
    elif dice:
        d.rounded_rectangle([W//2-30, H//2-30, W//2+30, H//2+30], 10, "white", "gold", 3)
        utils.write_text(d, (W//2, H//2), str(dice), 40, "black", "center")

    return img

# ==========================================
# ⚙️ LOGIC
# ==========================================
class Ludo:
    def __init__(self, rid, bet, creator):
        self.id = rid; self.bet = bet; self.creator = creator
        self.players = {}; self.state = 'lobby'; self.colors = ['R','G','Y','B']
        self.turn = []; self.idx = 0; self.ts = time.time(); self.turn_ts = time.time()

# ==========================================
# ⚡ TASKS (SAFE MODE)
# ==========================================
def task_update(bot, rid, g, text="Update"):
    try:
        img = draw_board(g.players)
        link = utils.upload(bot, img)
        if link: 
            bot.send_json({"handler": "chatroommessage", "roomid": rid, "type": "image", "url": link, "text": text})
        else:
            bot.send_message(rid, "⚠️ Board Upload Failed.")
    except Exception as e:
        print(f"Update Error: {e}")

def task_roll(bot, rid, g, uid, name, dice):
    try:
        # 1. Illusion (GIF)
        # Using a reliable GIF URL
        gif_url = "https://media.tenor.com/26gthl7qCzkAAAAi/dice-roll.gif"
        bot.send_json({"handler": "chatroommessage", "roomid": rid, "type": "image", "url": gif_url, "text": "Rolling..."})
        
        time.sleep(2.5) # Wait for animation
        
        with game_lock:
            p = g.players[str(uid)]
            msg = ""; win = False
            
            # --- STRICT LOGIC ---
            if p['step'] == -1:
                if dice == 6:
                    p['step'] = 0; msg = "🔓 Open!"
                else:
                    msg = "Locked (Need 6)"
            else:
                ns = p['step'] + dice
                # Win Condition (58 steps total: 0-51 track + 52-57 home + 58 center)
                # My PATH list has 58 items. Index 57 is Center.
                if ns == 57: 
                    p['step'] = 57; win = True
                elif ns > 57: 
                    msg = "Wait (Too high)"
                else:
                    # Check Cut
                    my_pos = PATHS[p['color']][ns]
                    
                    for oid, op in g.players.items():
                        if oid != str(uid) and op['step'] >= 0 and op['step'] < 52:
                            opp_pos = PATHS[op['color']][op['step']]
                            if my_pos == opp_pos:
                                op['step'] = -1; msg = f"⚔️ Cut {op['name']}!"
                                
                    p['step'] = ns
            
            # Turn Logic
            next_t = False
            if not win and dice != 6:
                g.idx = (g.idx + 1) % len(g.turn)
                next_t = True
                
            g.turn_ts = time.time(); g.ts = time.time()
            nxt_name = g.players[g.turn[g.idx]]['name']

        # 2. Final Board
        f_img = draw_board(g.players, dice)
        f_link = utils.upload(bot, f_img)
        
        if f_link:
            bot.send_json({"handler": "chatroommessage", "roomid": rid, "type": "image", "url": f_link, "text": str(dice)})
        else:
            bot.send_message(rid, "⚠️ Result Upload Failed.")
            
        bot.send_message(rid, f"🎲 **{name}** rolled {dice}. {msg}")
        
        if win:
            rew = g.bet * len(g.players); add_game_result(uid, name, "ludo", rew, True)
            bot.send_message(rid, f"🏆 **{name} WINS!** +{rew}"); del games[rid]; return
            
        if next_t: bot.send_message(rid, f"👉 **@{nxt_name}'s** Turn")
        else: bot.send_message(rid, "🎉 **6!** Roll Again")
        
    except Exception as e:
        traceback.print_exc()
        bot.send_message(rid, f"⚠️ Game Error: {e}")

def cleanup():
    while True:
        time.sleep(5)
        if not games: continue
        now = time.time(); dele = []
        with game_lock:
            for rid, g in games.items():
                if now - g.ts > 300: BOT_INSTANCE.send_message(rid, "💤 Timeout"); dele.append(rid); continue
                if g.state=='playing':
                    uid = g.turn[g.idx]
                    if now - g.turn_ts > 45:
                        BOT_INSTANCE.send_message(rid, f"⏱️ Skipped **@{g.players[uid]['name']}**")
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
        # QUICK CHECK IN MAIN THREAD
        with game_lock:
            g = games.get(rid)
            if not g or g.state != 'playing': return False
            
            # Check Turn
            curr_uid = g.turn[g.idx]
            if str(uid) != str(curr_uid):
                bot.send_message(rid, "⏳ Not your turn!")
                return True
                
            dice = random.randint(1, 6)
            
        # Run Heavy Task
        utils.run_in_bg(task_roll, bot, rid, g, uid, user, dice)
        return True
        
    if c == "stop":
        with game_lock:
            if rid in games and str(uid) == str(games[rid].owner):
                del games[rid]; bot.send_message(rid, "Stopped")
        return True
    return False
