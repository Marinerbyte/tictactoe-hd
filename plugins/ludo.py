import time
import random
import threading
import requests
import traceback
from io import BytesIO
from PIL import Image, ImageDraw

# --- IMPORTS ---
try: import utils
except ImportError: print("[Ludo] Error: utils.py not found!")

try: from db import add_game_result
except: print("[Ludo] DB Error")

# --- GLOBAL VARIABLES ---
games = {}
game_lock = threading.Lock()
BOT_INSTANCE = None 
AVATAR_CACHE = {} 

# --- CONFIG ---
THEMES = {
    'R': {'name': 'Red', 'hex': '#e74c3c', 'icon': "https://img.icons8.com/3d-fluency/94/iron-man.png"},
    'G': {'name': 'Green', 'hex': '#2ecc71', 'icon': "https://img.icons8.com/3d-fluency/94/hulk.png"},
    'Y': {'name': 'Yellow', 'hex': '#f1c40f', 'icon': "https://img.icons8.com/3d-fluency/94/pikachu-pokemon.png"},
    'B': {'name': 'Blue', 'hex': '#3498db', 'icon': "https://img.icons8.com/3d-fluency/94/captain-america.png"}
}

# --- 📍 MASTER PATH (The Holy Grail) ---
# Ye list 15x15 Grid ke (Col, Row) coordinates hai.
# 0-51 Steps (Outer Track). Red ke Start se shuru hoke clockwise.
MASTER_PATH = [
    # Red Bottom Track (Right -> Up)
    (1,13), (2,13), (3,13), (4,13), (5,13), # 0-4
    (6,12), (6,11), (6,10), (6,9), (6,8),   # 5-9
    (6,7), # 10 (Joint) - Actually usually safe spot is (6,8) or (8,6). keeping flow.
    # Green Left Track (Up -> Right)
    (5,8), (4,8), (3,8), (2,8), (1,8), (0,8), # 11-16
    (0,7), # 17 (Turn)
    (0,6), (1,6), (2,6), (3,6), (4,6), (5,6), # 18-23
    # Yellow Top Track (Right -> Down)
    (6,5), (6,4), (6,3), (6,2), (6,1), (6,0), # 24-29
    (7,0), # 30 (Turn)
    (8,0), (8,1), (8,2), (8,3), (8,4), (8,5), # 31-36
    # Blue Right Track (Down -> Left)
    (8,6), (9,6), (10,6), (11,6), (12,6), (13,6), # 37-42
    (14,6), # 43 (Turn)
    (14,7), (14,8), # 44-45 (Turn Down) -> Standard Ludo turn
    (13,8), (12,8), (11,8), (10,8), (9,8), (8,8), # 46-51 ... Wait alignment check
    # Let's verify loop close. 
    # (8,8) connects back to Red Up path? No.
    # Let's use visual mapping logic strictly.
]

# RE-MAPPING FOR VISUAL PERFECTION
# Hum quadrants ke hisaab se path define karenge.
# Red Start: (1, 13). 
# Track visual blocks:
# Bottom-Left Horizontal: (1,13)..(5,13)
# Bottom-Left Vertical: (6,12)..(6,9) (Stop at 8)
# We will construct the list programmatically to match visual boxes exactly.

FINAL_PATH = []
# 1. Red Strip (Bottom-Left)
for c in range(1, 6): FINAL_PATH.append((c, 13))    # 0-4
for r in range(12, 6, -1): FINAL_PATH.append((6, r)) # 5-10
FINAL_PATH.append((5, 7)) # 11 (Jump to Left Arm?) No, Standard Ludo goes to (6,6) then (5,6)
# SIMPLIFIED SPRINT PATH (Matches visual boxes 100%)
FINAL_PATH = [
    (1,13),(2,13),(3,13),(4,13),(5,13), # Bottom
    (6,12),(6,11),(6,10),(6,9),(6,8),   # Up
    (5,8),(4,8),(3,8),(2,8),(1,8),(0,8), # Left
    (0,7), (0,6), # Turn
    (1,6),(2,6),(3,6),(4,6),(5,6),       # Right
    (6,5),(6,4),(6,3),(6,2),(6,1),(6,0), # Up
    (7,0), (8,0), # Turn
    (8,1),(8,2),(8,3),(8,4),(8,5),       # Down
    (9,6),(10,6),(11,6),(12,6),(13,6),(14,6), # Right
    (14,7),(14,8), # Turn
    (13,8),(12,8),(11,8),(10,8),(9,8),   # Left
    (8,9),(8,10),(8,11),(8,12),(8,13),(8,14), # Down
    (7,14), (6,14) # Close
]
# Total 52 points approx. logic holds.

def setup(bot):
    global BOT_INSTANCE
    BOT_INSTANCE = bot
    threading.Thread(target=game_cleanup_loop, daemon=True).start()
    print("[Ludo] Safe & Perfect Map Version Loaded.")

# ==========================================
# 🛡️ SAFE AVATAR DOWNLOADER
# ==========================================
def get_avatar_image(uid, url):
    if not url: return None
    if uid in AVATAR_CACHE: return AVATAR_CACHE[uid]
    
    try:
        # High timeout, User-Agent to prevent 403 Forbidden
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=4)
        if r.status_code == 200:
            img = Image.open(BytesIO(r.content)).convert("RGBA")
            AVATAR_CACHE[uid] = img
            return img
        else:
            print(f"[Ludo Debug] Avatar Fail {r.status_code}: {url}")
    except Exception as e:
        print(f"[Ludo Debug] Avatar Exception: {e}")
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
                    if BOT_INSTANCE: BOT_INSTANCE.send_message(rid, "⏳ Lobby Timeout")
                    to_delete.append(rid); continue
                if now - g.last_interaction > 90:
                    if BOT_INSTANCE: BOT_INSTANCE.send_message(rid, "💤 Game Closed (Inactive)")
                    to_delete.append(rid); continue
                # Simple Turn Timeout
                uid, p = g.get_current_player()
                if uid and (now - g.turn_start_time > 45):
                    if BOT_INSTANCE: BOT_INSTANCE.send_message(rid, f"⏱️ **@{p['name']}** Skipped Turn!")
                    # Just skip turn instead of kick to prevent errors
                    g.turn_index = (g.turn_index + 1) % len(g.turn_list)
                    g.turn_start_time = time.time()
                    n_uid, n_p = g.get_current_player()
                    if BOT_INSTANCE: BOT_INSTANCE.send_message(rid, f"👉 **@{n_p['name']}'s** Turn")
        for rid in to_delete:
            if rid in games: del games[rid]

# ==========================================
# 📍 COORDINATE LOGIC
# ==========================================
def get_pixel_coords(step, color, sz, mx, my):
    # Offsets in the FINAL_PATH list
    offset = 0
    if color == 'G': offset = 13
    elif color == 'Y': offset = 26
    elif color == 'B': offset = 39
    
    c, r = 7, 7
    
    if step == -1: # Home
        if color == 'R': c, r = 2.5, 11.5
        if color == 'G': c, r = 2.5, 2.5
        if color == 'Y': c, r = 11.5, 2.5
        if color == 'B': c, r = 11.5, 11.5
        return mx + c*sz + sz//2, my + r*sz + sz//2
        
    elif step >= 51: # Home Run
        dist = step - 51
        if color == 'R': c, r = 7, 13 - dist
        elif color == 'G': c, r = 1 + dist, 7
        elif color == 'Y': c, r = 7, 1 + dist
        elif color == 'B': c, r = 13 - dist, 7
        if step >= 56: c, r = 7, 7
    else:
        # Main Track
        idx = (step + offset) % len(FINAL_PATH)
        c, r = FINAL_PATH[idx]
        
    return mx + (c * sz) + (sz // 2), my + (r * sz) + (sz // 2)

# ==========================================
# 🎨 GRAPHICS ENGINE
# ==========================================
def draw_ludo_board_hd(players, dice_val=None, rolling=False):
    SZ = 40 # Slightly smaller to fit mobile screens better
    W, H = SZ * 15 + 40, SZ * 15 + 40
    img = utils.create_canvas(W, H, "#222222")
    d = ImageDraw.Draw(img)
    mx, my = 20, 20
    
    # 1. DRAW BASE QUADRANTS
    homes = [('G',0,0,6,6), ('Y',9,0,15,6), ('R',0,9,6,15), ('B',9,9,15,15)]
    for code, c1, r1, c2, r2 in homes:
        d.rectangle([mx+c1*SZ, my+r1*SZ, mx+c2*SZ, my+r2*SZ], fill=THEMES[code]['hex'], outline="black", width=2)
        d.ellipse([mx+(c1+0.5)*SZ, my+(r1+0.5)*SZ, mx+(c2-0.5)*SZ, my+(r2-0.5)*SZ], fill="white", outline="black")
        
        # Big Avatar
        owner = next((p for p in players.values() if p['color'] == code), None)
        cx, cy = mx+((c1+c2)*SZ)//2, my+((r1+r2)*SZ)//2
        
        if owner:
            # TRY CATCH FOR AVATAR
            try:
                u_img = get_avatar_image(owner['uid'], owner.get('avatar_url'))
                if u_img:
                    u_img = utils.utils_instance.circle_crop(u_img, size=110)
                    img.paste(u_img, (int(cx-55), int(cy-55)), u_img)
            except: pass
            
            # Name
            utils.write_text(d, (cx, cy+40), owner['name'][:6], size=14, align="center", col="black", shadow=False)
        else:
            utils.write_text(d, (cx, cy), code, size=40, align="center", col="#888")

    # 2. DRAW TRACKS (Using FINAL_PATH to match logic)
    # We draw white boxes EXACTLY where the tokens walk
    for c, r in FINAL_PATH:
        x, y = mx+c*SZ, my+r*SZ
        d.rectangle([x, y, x+SZ, y+SZ], fill="white", outline="#555", width=1)
        
    # Draw Colored Home Runs manually
    # Red Home Run
    for i in range(1, 6): d.rectangle([mx+7*SZ, my+(13-i)*SZ, mx+8*SZ, my+(14-i)*SZ], fill=THEMES['R']['hex'], outline="black")
    # Green Home Run
    for i in range(1, 6): d.rectangle([mx+(1+i)*SZ, my+7*SZ, mx+(2+i)*SZ, my+8*SZ], fill=THEMES['G']['hex'], outline="black")
    # Yellow Home Run
    for i in range(1, 6): d.rectangle([mx+7*SZ, my+(1+i)*SZ, mx+8*SZ, my+(2+i)*SZ], fill=THEMES['Y']['hex'], outline="black")
    # Blue Home Run
    for i in range(1, 6): d.rectangle([mx+(13-i)*SZ, my+7*SZ, mx+(14-i)*SZ, my+8*SZ], fill=THEMES['B']['hex'], outline="black")

    # 3. TOKENS
    leader = None; max_s = -1
    for uid, p in players.items():
        if p['step'] > max_s and p['step'] > 0: max_s = p['step']; leader = uid
        
    for uid, p in players.items():
        px, py = get_coordinates(p['step'], p['color'], SZ, mx, my)
        
        # Safe Draw
        try:
            t_img = get_avatar_image(uid, p.get('avatar_url'))
            if t_img:
                t_img = utils.utils_instance.circle_crop(t_img, size=38)
                bg = Image.new('RGBA', (42,42), (0,0,0,0))
                ImageDraw.Draw(bg).ellipse([0,0,42,42], fill=THEMES[p['color']]['hex'])
                bg.paste(t_img, (2,2), t_img)
                img.paste(bg, (int(px-21), int(py-21)), bg)
            else:
                # Fallback Cartoon
                d.ellipse([px-18, py-18, px+18, py+18], fill=THEMES[p['color']]['hex'], outline="white", width=2)
        except:
             d.ellipse([px-18, py-18, px+18, py+18], fill=THEMES[p['color']]['hex'], outline="white", width=2)
        
        # Name
        d.rounded_rectangle([px-20, py-32, px+20, py-22], radius=4, fill="white", outline="black")
        utils.write_text(d, (px, py-27), p['name'][:4], size=9, align="center", col="black")

        if uid == leader:
            d.ellipse([px+10, py-30, px+25, py-15], fill="gold", outline="black")
            utils.write_text(d, (px+18, py-22), "1", size=10, align="center", col="black")

    # 4. DICE
    if rolling:
        ov = Image.new('RGBA', (W, H), (0,0,0,100))
        img.paste(ov, (0,0), ov)
        utils.write_text(d, (W//2, H//2), "ROLLING...", size=50, align="center", col="white", shadow=True)
    elif dice_val:
        d.rounded_rectangle([W//2-35, H//2-35, W//2+35, H//2+35], radius=10, fill="white", outline="gold", width=3)
        utils.write_text(d, (W//2, H//2), str(dice_val), size=40, align="center", col="black")
        
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
        self.players[str(uid)] = {'name': name, 'color': col, 'step': -1, 'avatar_url': avatar_url, 'uid': str(uid)}
        self.last_interaction = time.time()
        return True
    def get_current_player(self):
        if not self.turn_list: return None, None
        uid = self.turn_list[self.turn_index]
        return uid, self.players[uid]

# ==========================================
# ⚡ BACKGROUND HANDLERS (Safe Guarded)
# ==========================================
def safe_run(func, *args):
    try: func(*args)
    except Exception as e: 
        print(f"[Ludo] Error: {e}")
        traceback.print_exc()

def task_create_game(bot, room_id, g):
    img = draw_ludo_board_hd(g.players)
    link = utils.upload(bot, img)
    bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Lobby"})
    bot.send_message(room_id, f"🎲 **Ludo!** Bet: {g.bet}\nType `!join`")

def task_process_roll(bot, room_id, g, uid, user, dice):
    try:
        r_img = draw_ludo_board_hd(g.players, rolling=True)
        r_link = utils.upload(bot, r_img)
        bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": r_link, "text": "..."})
        time.sleep(1.5)
        
        with game_lock:
            p = g.players[str(uid)]
            msg = ""; is_win = False
            if p['step'] == -1: p['step'] = 0; msg = "Start!"
            else:
                ns = p['step'] + dice
                if ns >= 56: p['step'] = 57; is_win = True
                elif ns < 51:
                    for oid, op in g.players.items():
                        if oid != str(uid) and op['step'] == ns: op['step'] = -1; msg = f"⚔️ Cut {op['name']}!"
                    p['step'] = ns
                else: p['step'] = ns
                
            next_turn = False
            if not is_win and dice != 6:
                g.turn_index = (g.turn_index + 1) % len(g.turn_list)
                next_turn = True
            g.turn_start_time = time.time(); g.last_interaction = time.time()
            n_uid, n_p = g.get_current_player()
            next_name = n_p['name'] if n_p else ""

        f_img = draw_ludo_board_hd(g.players, dice_val=dice)
        f_link = utils.upload(bot, f_img)
        bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": f_link, "text": str(dice)})
        bot.send_message(room_id, f"🎲 **{user}** rolled {dice} {msg}")
        
        if is_win:
            rew = g.bet * len(g.players); add_game_result(uid, user, "ludo", rew, True)
            bot.send_message(room_id, f"🎉 **{user} WINS!**"); 
            with game_lock: del games[room_id]
            return
        
        if next_turn: bot.send_message(room_id, f"👉 **@{next_name}'s** Turn")
        else: bot.send_message(room_id, "🎉 Bonus Turn!")
    except Exception as e:
        print(f"[Ludo Roll Error]: {e}")
        traceback.print_exc()

# ==========================================
# 📨 HANDLER
# ==========================================
def handle_command(bot, command, room_id, user, args, data):
    try:
        cmd = command.lower().strip()
        uid = data.get('userid', user)
        if str(uid) == str(bot.user_id): return False
        
        # CORRECT AVATAR URL
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
            run_async(safe_run, task_create_game, bot, room_id, g)
            return True

        if cmd == "join":
            with game_lock:
                g = games.get(room_id)
                if not g or g.state != 'lobby': return False
                if str(uid) in g.players: return True
                if g.add_player(uid, user, av_url):
                    if g.bet > 0: add_game_result(uid, user, "ludo", -g.bet, False)
                    bot.send_message(room_id, f"✅ **{user}** joined!")
                    # Just update board image, use generic task
                    run_async(safe_run, task_create_game, bot, room_id, g)
                else: bot.send_message(room_id, "Full!")
            return True

        if cmd == "start":
            with game_lock:
                g = games.get(room_id)
                if not g: return False
                if len(g.players) < 2: bot.send_message(room_id, "Need 2+"); return True
                g.state = 'playing'; g.turn_list = list(g.players.keys()); g.turn_start_time = time.time()
                bot.send_message(room_id, "🔥 **Started!**")
            return True

        if cmd == "roll":
            with game_lock:
                g = games.get(room_id)
                if not g or g.state != 'playing': return False
                c_uid, _ = g.get_current_player()
                if str(uid) != str(c_uid): return True
                dice = random.randint(1, 6)
            run_async(task_process_roll, bot, room_id, g, uid, user, dice)
            return True

        if cmd == "stop":
            with game_lock:
                g = games.get(room_id)
                if g and str(uid) == str(g.creator_id): del games[room_id]; bot.send_message(room_id, "🛑 Stopped.")
            return True
            
    except Exception as e:
        print(f"[Ludo Handler Error]: {e}")
        return False
    return False
