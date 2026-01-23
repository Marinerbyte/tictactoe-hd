import time
import random
import threading
from PIL import Image, ImageDraw

# --- IMPORTS ---
try: import ludo_utils as utils
except ImportError: print("CRITICAL: ludo_utils.py missing")

try: from db import add_game_result
except: pass

# --- GLOBALS ---
games = {}
game_lock = threading.Lock()
BOT_INSTANCE = None 

# --- CONFIG ---
THEMES = {
    'R': {'hex': '#e74c3c'}, 'G': {'hex': '#2ecc71'},
    'Y': {'hex': '#f1c40f'}, 'B': {'hex': '#3498db'}
}

# ==========================================================
# 📍 THE HOLY GRAIL MAPPING (15x15 GRID)
# ==========================================================
# Format: (Column, Row). 0 is Left/Top. 14 is Right/Bottom.
# Ye list 100% verified hai. Isko mat छेड़na.
MAIN_TRACK = [
    # Red Arm (Bottom-Left)
    (1,13),(2,13),(3,13),(4,13),(5,13), # 0-4
    (6,12),(6,11),(6,10),(6,9),(6,8),   # 5-9
    (6,7),                              # 10 (Safe Spot)
    # Green Arm (Top-Left)
    (5,8),(4,8),(3,8),(2,8),(1,8),(0,8), # 11-16
    (0,7),                               # 17 (Turn)
    (0,6),(1,6),(2,6),(3,6),(4,6),(5,6), # 18-23
    # Yellow Arm (Top-Right)
    (6,5),(6,4),(6,3),(6,2),(6,1),(6,0), # 24-29
    (7,0),                               # 30 (Turn)
    (8,0),(8,1),(8,2),(8,3),(8,4),(8,5), # 31-36
    # Blue Arm (Bottom-Right)
    (8,6),(9,6),(10,6),(11,6),(12,6),(13,6), # 37-42
    (14,6),                                  # 43 (Turn)
    (14,7),(14,8),                           # 44-45 (Turn Down Fix)
    (13,8),(12,8),(11,8),(10,8),(9,8),(8,8), # 46-51
    # Close Loop
    (8,9),(8,10),(8,11),(8,12),(8,13),(8,14),
    (7,14),(6,14)
]
# NOTE: Standard Ludo is 52 steps. The list above covers the visual path.
# We will use modulo logic.

def setup(bot):
    global BOT_INSTANCE
    BOT_INSTANCE = bot
    threading.Thread(target=cleanup, daemon=True).start()
    print("[Ludo] Grid-Lock Edition Loaded.")

# ==========================================
# 📍 COORDINATE ENGINE
# ==========================================
def get_xy(step, color, sz, mx, my):
    # Base Offset
    off = 0
    if color == 'G': off = 13
    elif color == 'Y': off = 26
    elif color == 'B': off = 39
    
    c, r = 7, 7
    
    if step == -1: # Home Base Center
        if color == 'R': c, r = 2.5, 11.5
        if color == 'G': c, r = 2.5, 2.5
        if color == 'Y': c, r = 11.5, 2.5
        if color == 'B': c, r = 11.5, 11.5
        return mx + int(c*sz), my + int(r*sz)
        
    elif step >= 51: # Home Run
        d = step - 51
        if color == 'R': c, r = 7, 13-d
        elif color == 'G': c, r = 1+d, 7
        elif color == 'Y': c, r = 7, 1+d
        elif color == 'B': c, r = 13-d, 7
        if step >= 56: c, r = 7, 7
        
    else: # Main Track
        idx = (step + off) % len(MAIN_TRACK)
        c, r = MAIN_TRACK[idx]
        
    return mx + c*sz + sz//2, my + r*sz + sz//2

# ==========================================
# 🎨 GRAPHICS ENGINE
# ==========================================
def draw_board(players, dice=None, rolling=False):
    SZ = 40 # Box Size
    W, H = SZ*15 + 40, SZ*15 + 40
    img = utils.create_canvas(W, H, "#2c3e50")
    d = ImageDraw.Draw(img)
    mx, my = 20, 20
    
    # 1. DRAW BASE HOMES
    homes = [('G',0,0,6,6),('Y',9,0,15,6),('R',0,9,6,15),('B',9,9,15,15)]
    for code,x1,y1,x2,y2 in homes:
        d.rectangle([mx+x1*SZ, my+y1*SZ, mx+x2*SZ, my+y2*SZ], fill=THEMES[code]['hex'], outline="black", width=2)
        d.rectangle([mx+(x1+1)*SZ, my+(y1+1)*SZ, mx+(x2-1)*SZ, my+(y2-1)*SZ], fill="white", outline="black")
        
        # Big Avatar in Home
        owner = next((p for p in players.values() if p['color']==code), None)
        cx, cy = mx+((x1+x2)*SZ)//2, my+((y1+y2)*SZ)//2
        if owner:
            av = utils.get_image(owner.get('av'))
            if av:
                av = utils.circle_crop(av, 120)
                img.paste(av, (cx-60, cy-60), av)
            # Name
            utils.write_text(d, (cx, cy+50), owner['name'][:8], 14, "black", "center")

    # 2. DRAW TRACKS (CRITICAL: Using MASTER_PATH)
    # Jahan ye box banega, wahi token aayega.
    for c, r in MAIN_TRACK:
        x, y = mx+c*SZ, my+r*SZ
        d.rectangle([x, y, x+SZ, y+SZ], fill="white", outline="#7f8c8d", width=1)
        
    # Colored Home Runs
    for i in range(1,6): d.rectangle([mx+7*SZ, my+(14-i)*SZ, mx+8*SZ, my+(15-i)*SZ], fill=THEMES['R']['hex'], outline="black")
    for i in range(1,6): d.rectangle([mx+(0+i)*SZ, my+7*SZ, mx+(1+i)*SZ, my+8*SZ], fill=THEMES['G']['hex'], outline="black")
    for i in range(1,6): d.rectangle([mx+7*SZ, my+(0+i)*SZ, mx+8*SZ, my+(1+i)*SZ], fill=THEMES['Y']['hex'], outline="black")
    for i in range(1,6): d.rectangle([mx+(14-i)*SZ, my+7*SZ, mx+(15-i)*SZ, my+8*SZ], fill=THEMES['B']['hex'], outline="black")

    # Center
    cx, cy = mx + 7.5*SZ, my + 7.5*SZ
    d.polygon([(mx+6*SZ, my+6*SZ), (mx+9*SZ, my+6*SZ), (cx, cy)], fill=THEMES['Y']['hex'], outline="black")
    d.polygon([(mx+9*SZ, my+6*SZ), (mx+9*SZ, my+9*SZ), (cx, cy)], fill=THEMES['B']['hex'], outline="black")
    d.polygon([(mx+9*SZ, my+9*SZ), (mx+6*SZ, my+9*SZ), (cx, cy)], fill=THEMES['R']['hex'], outline="black")
    d.polygon([(mx+6*SZ, my+9*SZ), (mx+6*SZ, my+6*SZ), (cx, cy)], fill=THEMES['G']['hex'], outline="black")

    # 3. DRAW TOKENS
    # Leader Logic
    ms = -1; lid = None
    for u, p in players.items():
        if p['step']>ms and p['step']>0: ms=p['step']; lid=u
    
    for u, p in players.items():
        px, py = get_xy(p['step'], p['color'], SZ, mx, my)
        
        # Shadow
        d.ellipse([px-18, py+12, px+18, py+20], fill=(0,0,0,60))
        
        # Avatar Token
        av = utils.get_image(p.get('av'))
        if av:
            av = utils.circle_crop(av, 36)
            # Border
            bg = Image.new('RGBA', (40,40), (0,0,0,0))
            ImageDraw.Draw(bg).ellipse([0,0,40,40], fill=THEMES[p['color']]['hex'])
            bg.paste(av, (2,2), av)
            img.paste(bg, (int(px-20), int(py-20)), bg)
        else:
            d.ellipse([px-18, py-18, px+18, py+18], fill=THEMES[p['color']]['hex'], outline="white", width=2)
            
        # Name
        d.rounded_rectangle([px-20, py-32, px+20, py-22], 4, "white", "black")
        utils.write_text(d, (px, py-27), p['name'][:4], 10, "black", "center")
        
        if u == lid:
            d.ellipse([px+10, py-30, px+25, py-15], fill="gold", outline="black")
            utils.write_text(d, (px+18, py-22), "1", 10, "black", "center")

    # 4. DICE
    if rolling:
        utils.write_text(d, (W//2, H//2), "ROLLING...", 40, "white", "center", True)
    elif dice:
        d.rounded_rectangle([W//2-30, H//2-30, W//2+30, H//2+30], 10, "white", "gold", 3)
        utils.write_text(d, (W//2, H//2), str(dice), 40, "black", "center")

    return img

# ==========================================
# ⚙️ LOGIC & TASKS
# ==========================================
class Ludo:
    def __init__(self, rid, bet, creator):
        self.id = rid; self.bet = bet; self.creator = creator
        self.players = {}; self.state = 'lobby'; self.colors = ['R','G','Y','B']
        self.turn = []; self.idx = 0; self.ts = time.time(); self.turn_ts = time.time()

def task_draw(bot, rid, g, text="Update"):
    try:
        img = draw_board(g.players)
        link = utils.upload(bot, img)
        if link:
            bot.send_json({"handler": "chatroommessage", "roomid": rid, "type": "image", "url": link, "text": text})
        else:
            bot.send_message(rid, "⚠️ Upload Failed (Check Logs)")
    except Exception as e: print(e)

def task_roll(bot, rid, g, uid, name, dice):
    # Illusion
    img = draw_board(g.players, rolling=True)
    lnk = utils.upload(bot, img)
    if lnk: bot.send_json({"handler": "chatroommessage", "roomid": rid, "type": "image", "url": lnk, "text": "..."})
    time.sleep(1.5)
    
    with game_lock:
        p = g.players[str(uid)]
        msg = ""; win = False
        
        if p['step'] == -1: p['step'] = 0; msg = "Start!"
        else:
            ns = p['step'] + dice
            if ns >= 56: p['step']=57; win=True
            elif ns < 51:
                # Cut
                for oid, op in g.players.items():
                    if oid!=str(uid) and op['step']==ns: op['step']=-1; msg="⚔️ Cut!"
                p['step'] = ns
            else: p['step'] = ns
            
        g.turn_ts = time.time()
        if not win and dice != 6:
            g.idx = (g.idx + 1) % len(g.turn)
        nxt = g.players[g.turn[g.idx]]['name']

    # Final
    task_draw(bot, rid, g, str(dice))
    bot.send_message(rid, f"🎲 **{name}** rolled {dice} {msg}")
    
    if win:
        add_game_result(uid, name, "ludo", g.bet*len(g.players), True)
        bot.send_message(rid, f"🎉 **{name} WINS!**"); del games[rid]; return
        
    if dice!=6: bot.send_message(rid, f"👉 **@{nxt}** Turn")
    else: bot.send_message(rid, "🎉 Bonus Turn!")

def cleanup():
    while True:
        time.sleep(5)
        if not games: continue
        now = time.time(); dele = []
        with game_lock:
            for rid, g in games.items():
                if now - g.ts > 300: BOT_INSTANCE.send_message(rid, "⏳ Timeout"); dele.append(rid); continue
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
    
    # AVATAR URL
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
        utils.run_in_bg(task_draw, bot, rid, g, "Lobby")
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
                bot.send_message(rid, "✅ Joined!")
                utils.run_in_bg(task_draw, bot, rid, g, "Join")
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
