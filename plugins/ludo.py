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

# --- CONFIG ---
ROLLING_GIF_URL = "https://media.tenor.com/26gthl7qCzkAAAAi/dice-roll.gif"  # <-- Yahan fix kar diya

THEMES = {
    'R': {'name': 'Red', 'hex': '#FF3333', 'bg': '#2b0000'},
    'G': {'name': 'Green', 'hex': '#00FF00', 'bg': '#002b00'},
    'Y': {'name': 'Yellow', 'hex': '#FFFF00', 'bg': '#2b2b00'},
    'B': {'name': 'Blue', 'hex': '#0099FF', 'bg': '#00002b'}
}

# ==========================================================
# 📍 THE MASTER TRACK (52 Boxes Logic)
# ==========================================================
# Index 0 = Red Start.
TRACK = [
    # Red Area (0-12)
    (1,13),(2,13),(3,13),(4,13),(5,13), (6,12),(6,11),(6,10),(6,9),(6,8), (6,7), (5,8), 
    # Green Area (13-25)
    (4,8),(3,8),(2,8),(1,8),(0,8), (0,7), (0,6), (1,6),(2,6),(3,6),(4,6),(5,6), (6,5),
    # Yellow Area (26-38)
    (6,4),(6,3),(6,2),(6,1),(6,0), (7,0), (8,0), (8,1),(8,2),(8,3),(8,4),(8,5), (8,6),
    # Blue Area (39-51)
    (9,6),(10,6),(11,6),(12,6),(13,6),(14,6), (14,7), (14,8), (13,8),(12,8),(11,8),(10,8),(9,8), (8,9),
    # Close Loop
    (8,10),(8,11),(8,12),(8,13),(8,14), (7,14), (6,14), (6,13)
]

HOME_RUNS = {
    'R': [(7,13),(7,12),(7,11),(7,10),(7,9),(7,8)],
    'G': [(1,7),(2,7),(3,7),(4,7),(5,7),(6,7)],
    'Y': [(7,1),(7,2),(7,3),(7,4),(7,5),(7,6)],
    'B': [(13,7),(12,7),(11,7),(10,7),(9,7),(8,7)]
}

def setup(bot):
    global BOT_INSTANCE
    BOT_INSTANCE = bot
    threading.Thread(target=cleanup, daemon=True).start()
    print("[Ludo] Final Fixed Loaded.")

# ==========================================
# 📍 COORDINATE ENGINE
# ==========================================
def get_xy(step, color, sz, mx, my):
    # Step -1: Base
    if step == -1:
        if color == 'R': return mx + 2.5*sz, my + 11.5*sz
        if color == 'G': return mx + 2.5*sz, my + 2.5*sz
        if color == 'Y': return mx + 11.5*sz, my + 2.5*sz
        if color == 'B': return mx + 11.5*sz, my + 11.5*sz
    
    # Step 57: Center Win
    if step >= 57:
        return mx + 7.5*sz, my + 7.5*sz

    # Home Run (51-56)
    if step >= 51:
        idx = step - 51
        if idx < 6:
            c, r = HOME_RUNS[color][idx]
            return mx + c*sz + sz//2, my + r*sz + sz//2
        return mx + 7.5*sz, my + 7.5*sz

    # Main Track (0-50)
    offset = 0
    if color == 'G': offset = 13
    elif color == 'Y': offset = 26
    elif color == 'B': offset = 39
    
    track_idx = (step + offset) % len(TRACK)
    if track_idx < len(TRACK):
        c, r = TRACK[track_idx]
        return mx + c*sz + sz//2, my + r*sz + sz//2
    
    return mx + 7.5*sz, my + 7.5*sz

# ==========================================
# 🎨 GRAPHICS
# ==========================================
def draw_board(players, dice=None, rolling=False):
    SZ = 40; MX, MY = 20, 20
    W, H = SZ*15 + 40, SZ*15 + 40
    img = utils.create_canvas(W, H, "#1a1a1a")
    d = ImageDraw.Draw(img)
    
    # 1. Boxes
    for c, r in TRACK:
        x, y = MX+c*SZ, MY+r*SZ
        d.rectangle([x, y, x+SZ, y+SZ], fill="white", outline="#333")
    for code, coords in HOME_RUNS.items():
        col = THEMES[code]['hex']
        for c, r in coords:
            x, y = MX+c*SZ, MY+r*SZ
            d.rectangle([x, y, x+SZ, y+SZ], fill=col, outline="#222")

    # 2. Bases
    homes = [('G',0,0,6,6),('Y',9,0,15,6),('R',0,9,6,15),('B',9,9,15,15)]
    for c,x1,y1,x2,y2 in homes:
        d.rectangle([MX+x1*SZ, MY+y1*SZ, MX+x2*SZ, MY+y2*SZ], fill=THEMES[c]['hex'], outline="black", width=2)
        d.rectangle([MX+(x1+1)*SZ, MY+(y1+1)*SZ, MX+(x2-1)*SZ, MY+(y2-1)*SZ], fill="#fff", outline="black")
        
        owner = next((p for p in players.values() if p['color']==c), None)
        cx, cy = MX+((x1+x2)*SZ)//2, MY+((y1+y2)*SZ)//2
        if owner:
            av = utils.get_image(owner.get('av'))
            if av:
                av = utils.circle_crop(av, 110)
                img.paste(av, (cx-55, cy-55), av)
            utils.write_text(d, (cx, cy+50), owner['name'][:8], 14, "black", "center")

    # Center
    cx, cy = MX + 7.5*SZ, MY + 7.5*SZ
    utils.write_text(d, (cx, cy), "🏆", 30, "white", "center")

    # 3. Tokens (Stacked)
    pos_map = {}
    for uid, p in players.items():
        px, py = get_xy(p['step'], p['color'], SZ, MX, MY)
        k = (int(px), int(py))
        if k not in pos_map: pos_map[k] = []
        pos_map[k].append(p)

    for (px, py), p_list in pos_map.items():
        offset_x = -10 if len(p_list) > 1 else 0
        for i, p in enumerate(p_list):
            dx = px + offset_x + (i * 20)
            dy = py
            av = utils.get_image(p.get('av'))
            if av:
                av = utils.circle_crop(av, 34)
                bg = Image.new('RGBA', (38,38), (0,0,0,0))
                ImageDraw.Draw(bg).ellipse([0,0,38,38], fill=THEMES[p['color']]['hex'])
                bg.paste(av, (2,2), av)
                img.paste(bg, (int(dx-19), int(dy-19)), bg)
            else:
                d.ellipse([dx-15, dy-15, dx+15, dy+15], fill=THEMES[p['color']]['hex'], outline="white", width=2)
            # Name
            d.rounded_rectangle([dx-20, dy-30, dx+20, dy-20], 3, "white", "black")
            utils.write_text(d, (dx, dy-25), p['name'][:4], 10, "black", "center")

    # 4. Dice
    if rolling:
        utils.write_text(d, (W//2, H//2), "ROLLING", 40, "white", "center", True)
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

def task_update(bot, rid, g, text="Update"):
    try:
        img = draw_board(g.players)
        link = utils.upload(bot, img)
        if link: bot.send_json({"handler": "chatroommessage", "roomid": rid, "type": "image", "url": link, "text": text})
    except: pass

def task_roll(bot, rid, g, uid, name, dice):
    # 1. Illusion
    try:
        bot.send_json({"handler": "chatroommessage", "roomid": rid, "type": "image", "url": ROLLING_GIF_URL, "text": "..."})
        time.sleep(2)
        
        with game_lock:
            p = g.players[str(uid)]
            msg = ""; win = False
            
            # Logic: 1 or 6 to open
            if p['step'] == -1:
                if dice == 1 or dice == 6:
                    p['step'] = 0; msg = "🔓 Open!"
                else:
                    msg = "🔒 Locked"
            else:
                ns = p['step'] + dice
                if ns == 57: p['step']=57; win=True
                elif ns > 57: msg = "Wait!"
                else:
                    # Cut Logic
                    my_xy = get_xy(ns, p['color'], 40, 20, 20)
                    for oid, op in g.players.items():
                        if oid!=str(uid) and op['step']>=0 and op['step']<51:
                            opp_xy = get_xy(op['step'], op['color'], 40, 20, 20)
                            if abs(my_xy[0]-opp_xy[0]) < 5 and abs(my_xy[1]-opp_xy[1]) < 5:
                                op['step'] = -1; msg = f"⚔️ Cut {op['name']}!"
                    p['step'] = ns
            
            next_t = False
            if not win and dice != 6:
                g.idx = (g.idx + 1) % len(g.turn)
                next_t = True
                
            g.turn_ts = time.time(); g.ts = time.time()
            nxt = g.players[g.turn[g.idx]]['name']

        # 2. Result
        f_img = draw_board(g.players, dice)
        f_link = utils.upload(bot, f_img)
        
        if f_link:
            bot.send_json({"handler": "chatroommessage", "roomid": rid, "type": "image", "url": f_link, "text": str(dice)})
        
        bot.send_message(rid, f"🎲 **{name}** rolled {dice} {msg}")
        
        if win:
            rew = g.bet * len(g.players); add_game_result(uid, name, "ludo", rew, True)
            bot.send_message(rid, f"🏆 **{name} WINS!**"); del games[rid]; return
            
        if next_t: bot.send_message(rid, f"👉 **@{nxt}** Turn")
        else: bot.send_message(rid, "🎉 **Bonus!** Roll Again")
        
    except Exception as e:
        traceback.print_exc()
        bot.send_message(rid, f"⚠️ Error: {e}")

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
        with game_lock:
            g = games.get(rid)
            if not g or g.state != 'playing': return False
            if str(uid) != g.turn[g.idx]: 
                bot.send_message(rid, "⏳ Not your turn!")
                return True
            dice = 6 if random.random() < 0.3 else random.randint(1, 5) # Boosted 6
            
        utils.run_in_bg(task_roll, bot, rid, g, uid, user, dice)
        return True
        
    if c == "stop":
        with game_lock:
            if rid in games and str(uid) == str(games[rid].creator):
                del games[rid]; bot.send_message(rid, "Stopped")
        return True
    return False
