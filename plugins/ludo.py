import time
import random
import threading
import requests
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
AVATAR_CACHE = {} # Memory Cache for Speed

# --- CONFIG ---
THEMES = {
    'R': {'name': 'Red', 'hex': '#FF4444', 'icon': "https://img.icons8.com/3d-fluency/94/iron-man.png"},
    'G': {'name': 'Green', 'hex': '#00CC00', 'icon': "https://img.icons8.com/3d-fluency/94/hulk.png"},
    'Y': {'name': 'Yellow', 'hex': '#FFD700', 'icon': "https://img.icons8.com/3d-fluency/94/pikachu-pokemon.png"},
    'B': {'name': 'Blue', 'hex': '#3388FF', 'icon': "https://img.icons8.com/3d-fluency/94/captain-america.png"}
}

def setup(bot):
    global BOT_INSTANCE
    BOT_INSTANCE = bot
    threading.Thread(target=game_cleanup_loop, daemon=True).start()
    print("[Ludo] Avatar Fail-Proof Edition Loaded.")

# ==========================================
# 🚀 ASYNC WORKERS
# ==========================================
def run_async(target, *args):
    t = threading.Thread(target=target, args=args)
    t.daemon = True
    t.start()

# ==========================================
# 🛠️ HELPER: SMART AVATAR DOWNLOADER (PLAN A + PLAN B)
# ==========================================
def get_avatar_image(uid, url, username):
    """
    1. Cache Check
    2. Try Real URL (Howdies CDN)
    3. Fallback to DiceBear (Cartoon Generator)
    """
    # 1. Check RAM Cache
    if uid in AVATAR_CACHE:
        return AVATAR_CACHE[uid]
    
    # 2. Try Real Photo
    if url:
        try:
            # Browser headers to avoid blocking
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8'
            }
            r = requests.get(url, headers=headers, timeout=2) # 2 sec wait
            if r.status_code == 200:
                img = Image.open(BytesIO(r.content)).convert("RGBA")
                AVATAR_CACHE[uid] = img
                print(f"[Ludo] Downloaded Real Avatar: {username}")
                return img
            else:
                print(f"[Ludo] Real Avatar Failed ({r.status_code}): {url}")
        except Exception as e:
            print(f"[Ludo] Avatar Error: {e}")

    # 3. PLAN B: DiceBear (Guaranteed Avatar)
    try:
        # 'adventurer' style looks very like Ludo tokens
        seed = username.replace(" ", "")
        fallback_url = f"https://api.dicebear.com/9.x/adventurer/png?seed={seed}&backgroundColor=b6e3f4"
        r = requests.get(fallback_url, timeout=3)
        if r.status_code == 200:
            img = Image.open(BytesIO(r.content)).convert("RGBA")
            AVATAR_CACHE[uid] = img
            print(f"[Ludo] Generated DiceBear Avatar: {username}")
            return img
    except:
        pass
    
    return None

# ==========================================
# 📍 COORDINATE MAPPING
# ==========================================
def get_coordinates(step, color, sz, mx, my):
    # Perfect 52-step visual path for 15x15 grid
    PATH = [
        (1,13),(2,13),(3,13),(4,13),(5,13), (6,12),(6,11),(6,10),(6,9),(6,8), 
        (5,8),(4,8),(3,8),(2,8),(1,8),(0,8), (0,7), (0,6),(1,6),(2,6),(3,6),(4,6),(5,6),
        (6,5),(6,4),(6,3),(6,2),(6,1),(6,0), (7,0), (8,0),(8,1),(8,2),(8,3),(8,4),(8,5),
        (8,6),(9,6),(10,6),(11,6),(12,6),(13,6), (14,6), (14,7),(14,8),(13,8),(12,8),(11,8),(10,8),(9,8),
        (8,9),(8,10),(8,11),(8,12),(8,13),(8,14), (7,14), (6,14)
    ]
    offset = 0
    if color == 'G': offset = 13
    elif color == 'Y': offset = 26
    elif color == 'B': offset = 39
    
    c, r = 7, 7
    if step == -1: # Home Base
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
        idx = (step + offset) % 52
        if idx < len(PATH): c, r = PATH[idx]
            
    return mx + (c * sz) + (sz // 2), my + (r * sz) + (sz // 2)

# ==========================================
# 🎨 GRAPHICS ENGINE
# ==========================================
def draw_ludo_board_hd(players, dice_val=None, rolling=False):
    SZ = 50
    W, H = SZ * 15 + 40, SZ * 15 + 40
    img = utils.create_canvas(W, H, "#2c3e50")
    d = ImageDraw.Draw(img)
    mx, my = 20, 20
    
    # 1. BASE GRID
    homes = [('G',0,0,6,6), ('Y',9,0,15,6), ('R',0,9,6,15), ('B',9,9,15,15)]
    for code, c1, r1, c2, r2 in homes:
        d.rectangle([mx+c1*SZ, my+r1*SZ, mx+c2*SZ, my+r2*SZ], fill=THEMES[code]['hex'], outline="black", width=2)
        d.ellipse([mx+(c1+0.5)*SZ, my+(r1+0.5)*SZ, mx+(c2-0.5)*SZ, my+(r2-0.5)*SZ], fill="white", outline="black")
        
        # Big Avatar in Home
        owner = next((p for p in players.values() if p['color'] == code), None)
        cx, cy = mx+((c1+c2)*SZ)//2, my+((r1+r2)*SZ)//2
        
        if owner:
            # TRY DOWNLOADING AVATAR
            u_img = get_avatar_image(owner['uid'], owner.get('avatar_url'), owner['name'])
            
            if u_img:
                u_img = utils.utils_instance.circle_crop(u_img, size=140)
                img.paste(u_img, (int(cx-70), int(cy-70)), u_img)
                # Name Label
                d.rounded_rectangle([cx-60, cy+55, cx+60, cy+80], radius=10, fill="black")
                utils.write_text(d, (cx, cy+57), owner['name'][:10], size=14, align="center", col="white")
            else:
                # Still fallback if everything fails
                utils.write_text(d, (cx, cy), owner['name'][0], size=50, align="center", col="#333")

    # 2. TRACKS
    for r in range(15):
        for c in range(15):
            if not ((6<=r<=8) or (6<=c<=8)): continue
            if (6<=r<=8) and (6<=c<=8): continue
            
            x, y = mx+c*SZ, my+r*SZ
            fill = "#ecf0f1"
            if r==7 and 1<=c<=5: fill=THEMES['G']['hex']
            if r==7 and 9<=c<=13: fill=THEMES['B']['hex']
            if c==7 and 1<=r<=5: fill=THEMES['Y']['hex']
            if c==7 and 9<=r<=13: fill=THEMES['R']['hex']
            if (c,r) in [(1,13),(6,2),(13,1),(8,12),(2,6),(6,12),(12,8),(8,2)]: fill="#bdc3c7"
            
            d.rounded_rectangle([x+1, y+1, x+SZ-1, y+SZ-1], radius=4, fill=fill, outline="#7f8c8d")

    # Center
    cx, cy = mx + 7.5*SZ, my + 7.5*SZ
    pts = [(mx+6*SZ, my+6*SZ), (mx+9*SZ, my+6*SZ), (mx+9*SZ, my+9*SZ), (mx+6*SZ, my+9*SZ)]
    cols = [THEMES['Y']['hex'], THEMES['B']['hex'], THEMES['R']['hex'], THEMES['G']['hex']]
    for i in range(4):
        d.polygon([pts[i], pts[(i+1)%4], (cx,cy)], fill=cols[i], outline="black")
    utils.write_text(d, (cx, cy), "🏆", size=30, align="center")

    # 3. TOKENS
    max_s = -1; leader = None
    for uid, p in players.items():
        if p['step'] > max_s and p['step'] > 0: max_s = p['step']; leader = uid

    for uid, p in players.items():
        px, py = get_coordinates(p['step'], p['color'], SZ, mx, my)
        
        # Shadow
        d.ellipse([px-20, py+15, px+20, py+25], fill=(0,0,0,50))
        
        # Token Avatar
        t_img = get_avatar_image(uid, p.get('avatar_url'), p['name'])
        
        if t_img:
            t_img = utils.utils_instance.circle_crop(t_img, size=46)
            # Border
            bg = Image.new('RGBA', (52,52), (0,0,0,0))
            ImageDraw.Draw(bg).ellipse([0,0,52,52], fill=THEMES[p['color']]['hex'])
            bg.paste(t_img, (3,3), t_img)
            img.paste(bg, (int(px-26), int(py-26)), bg)
        else:
            d.ellipse([px-20, py-20, px+20, py+20], fill=THEMES[p['color']]['hex'], outline="white", width=2)

        # Name Bubble
        d.rounded_rectangle([px-22, py-38, px+22, py-24], radius=4, fill="white", outline="black")
        utils.write_text(d, (px, py-34), p['name'][:4], size=10, align="center", col="black")

        if uid == leader:
            d.ellipse([px+10, py-35, px+28, py-17], fill="#FFD700", outline="black")
            utils.write_text(d, (px+19, py-26), "1", size=10, align="center", col="black")

    # 4. DICE
    if rolling:
        ov = Image.new('RGBA', (W, H), (0,0,0,100))
        img.paste(ov, (0,0), ov)
        utils.write_text(d, (W//2, H//2), "🎲 ROLLING...", size=60, align="center", col="white", shadow=True)
    elif dice_val:
        d.rounded_rectangle([W//2-40, H//2-40, W//2+40, H//2+40], radius=10, fill="white", outline="#f1c40f", width=4)
        dice_url = f"https://img.icons8.com/3d-fluency/94/{dice_val}-circle.png"
        di = utils.get_image(dice_url)
        if di:
            di = di.resize((70,70))
            img.paste(di, (int(W//2-35), int(H//2-35)), di)
        else:
            utils.write_text(d, (W//2, H//2), str(dice_val), size=40, align="center", col="black")

    return img

# ==========================================
# ⚙️ GAME LOGIC
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
# ⚡ BACKGROUND TASK HANDLERS
# ==========================================
def task_create_game(bot, room_id, g):
    img = draw_ludo_board_hd(g.players)
    link = utils.upload(bot, img)
    bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Lobby"})
    bot.send_message(room_id, f"🎲 **Ludo HD!** Bet: {g.bet}\nType `!join` to play.")

def task_join_game(bot, room_id, g):
    img = draw_ludo_board_hd(g.players)
    link = utils.upload(bot, img)
    bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Join"})

def task_process_roll(bot, room_id, g, uid, user, dice):
    r_img = draw_ludo_board_hd(g.players, rolling=True)
    r_link = utils.upload(bot, r_img)
    bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": r_link, "text": "..."})
    
    time.sleep(1.5)
    
    with game_lock:
        p = g.players[str(uid)]
        msg = ""; is_win = False
        if p['step'] == -1: 
            p['step'] = 0; msg = "Start!"
        else:
            ns = p['step'] + dice
            if ns >= 56: p['step'] = 57; is_win = True
            elif ns < 51:
                for oid, op in g.players.items():
                    if oid != str(uid) and op['step'] == ns: 
                        op['step'] = -1; msg = f"⚔️ **Cut {op['name']}!**"
                p['step'] = ns
            else: p['step'] = ns

        c_p_name = p['name']
        next_turn = False
        if not is_win and dice != 6:
            g.turn_index = (g.turn_index + 1) % len(g.turn_list)
            next_turn = True
        g.turn_start_time = time.time(); g.last_interaction = time.time()
        n_uid, n_p = g.get_current_player()
        next_name = n_p['name'] if n_p else ""

    f_img = draw_ludo_board_hd(g.players, dice_val=dice)
    f_link = utils.upload(bot, f_img)
    
    bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": f_link, "text": f"{dice}"})
    bot.send_message(room_id, f"🎲 **{c_p_name}** rolled {dice}! {msg}")
    
    if is_win:
        rew = g.bet * len(g.players)
        add_game_result(uid, user, "ludo", rew, True)
        bot.send_message(room_id, f"🎉 **{user} WINS!** +{rew} Coins")
        with game_lock: 
            if room_id in games: del games[room_id]
        return
        
    if dice == 6: bot.send_message(room_id, "🎉 **Bonus Turn!**")
    if next_turn: bot.send_message(room_id, f"👉 **@{next_name}'s** Turn")

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
                    if BOT_INSTANCE: BOT_INSTANCE.send_message(rid, "⏳ **Lobby Expired**")
                    to_delete.append(rid); continue
                if now - g.last_interaction > 90:
                    if BOT_INSTANCE: BOT_INSTANCE.send_message(rid, "💤 **Game Closed**")
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
# 📨 HANDLER
# ==========================================
def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    uid = data.get('userid', user)
    if str(uid) == str(bot.user_id): return False
    
    # EXACT URL CONSTRUCTION
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
        run_async(task_create_game, bot, room_id, g)
        return True

    if cmd == "join":
        with game_lock:
            g = games.get(room_id)
            if not g or g.state != 'lobby': return False
            if str(uid) in g.players: return True
            if g.add_player(uid, user, av_url):
                if g.bet > 0: add_game_result(uid, user, "ludo", -g.bet, False)
                bot.send_message(room_id, f"✅ **{user}** joined!")
                run_async(task_join_game, bot, room_id, g)
            else: bot.send_message(room_id, "Lobby Full!")
        return True

    if cmd == "start":
        with game_lock:
            g = games.get(room_id)
            if not g: return False
            if len(g.players) < 2: bot.send_message(room_id, "Need 2+ Players."); return True
            g.state = 'playing'; g.turn_list = list(g.players.keys()); g.turn_start_time = time.time()
            bot.send_message(room_id, "🔥 **Started!** First `!roll`")
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
    return False
