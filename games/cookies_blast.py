import time
import random
import threading
import requests
import io
from PIL import Image, ImageDraw, ImageFont

# --- IMPORTS ---
try: 
    import utils 
except ImportError: 
    print("[CookieBlast] Warning: utils.py not found.")

try: 
    from db import add_game_result
except: 
    pass

# --- CONFIGURATION ---
GAME_NAME = "Cookie Blast 3D"
GRID_SIZE = 6 # 6x6
BOX_SIZE = 130 
GAP = 15
CANVAS_W = 1024
CANVAS_H = 1250 # Thoda aur bada kiya header ke liye

# COLORS
BG_COLOR = "#1e272e" 
BOX_CLOSED = "#3498db"
BOX_SHADOW = "#2980b9"
BOX_COOKIE = "#f1c40f"
BOX_BOMB = "#e74c3c"
TEXT_COLOR = "#ecf0f1"

# --- GLOBALS ---
games = {}
game_lock = threading.Lock()
BOT_INSTANCE = None 

def setup(bot):
    global BOT_INSTANCE
    BOT_INSTANCE = bot
    threading.Thread(target=game_monitor_loop, daemon=True).start()
    print(f"[{GAME_NAME}] Hardcore Mode Loaded.")

# ==========================================
# 🎨 ASSET & FONT HELPERS
# ==========================================

def get_font(size):
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "arialbd.ttf", "arial.ttf"
    ]
    for path in font_paths:
        try: return ImageFont.truetype(path, size)
        except: continue
    return ImageFont.load_default()

def get_avatar(username):
    try:
        seed = f"{username}-{random.randint(1,999)}"
        url = f"https://api.dicebear.com/9.x/fun-emoji/png?seed={seed}&backgroundColor=transparent&size=512"
        r = requests.get(url, timeout=3)
        if r.status_code == 200:
            return Image.open(io.BytesIO(r.content)).convert("RGBA")
    except: pass
    return None

def centered_text(draw, x, y, text, size, color, shadow=True):
    font = get_font(size)
    try: w = font.getlength(text)
    except: w = len(text) * (size*0.6)
    
    nx = x - (w / 2)
    ny = y - (size / 2)
    
    if shadow:
        draw.text((nx+3, ny+3), text, font=font, fill=(0,0,0,100))
    draw.text((nx, ny), text, font=font, fill=color)

# ==========================================
# 🖼️ BOARD RENDERER (Enhanced Header)
# ==========================================

def render_board(game):
    W, H = CANVAS_W, CANVAS_H
    img = utils.create_canvas(W, H, BG_COLOR)
    d = ImageDraw.Draw(img)
    
    # 1. HEADER (Scoreboard & Usernames)
    # Background Panel
    d.rounded_rectangle([20, 20, 1004, 200], radius=20, fill="#2f3640", outline="#57606f", width=2)
    
    # Sort players by score
    players = sorted(game.players.values(), key=lambda x: x['score'], reverse=True)
    
    # Dynamic Width based on player count (Max 4)
    # Total width 960. 4 players = 240px each.
    col_w = 960 // 4
    
    for i, p in enumerate(players):
        px = 40 + (i * col_w)
        py = 40
        
        # Highlight active turn
        is_turn = (p['uid'] == game.turn_order[game.turn_index])
        
        # Box Colors
        bg_col = "#333"
        border_col = "#555"
        
        if is_turn: 
            bg_col = "#144225" # Dark Green
            border_col = "#2ecc71" # Bright Green
        
        if p['eliminated']:
            bg_col = "#4a1010" # Dark Red
            border_col = "#e74c3c" # Red
            
        # Draw Player Card
        d.rounded_rectangle([px, py, px+col_w-20, py+140], radius=15, fill=bg_col, outline=border_col, width=3)
        
        # Name (Big & Clear)
        name = p['name'][:8]
        centered_text(d, px + (col_w-20)//2, py + 35, name, 35, "white")
        
        # Score & Status
        if p['eliminated']:
            status_txt = "💀 OUT"
            status_col = "#e74c3c"
        else:
            status_txt = f"🍪 {p['score']}"
            status_col = "#f1c40f"
            
        centered_text(d, px + (col_w-20)//2, py + 100, status_txt, 45, status_col)

    # 2. THE GRID (3D Buttons)
    grid_start_y = 240
    grid_w = (BOX_SIZE * 6) + (GAP * 5)
    margin_x = (W - grid_w) // 2
    
    for i in range(36):
        row = i // 6
        col = i % 6
        
        x = margin_x + (col * (BOX_SIZE + GAP))
        y = grid_start_y + (row * (BOX_SIZE + GAP))
        
        # Draw Box Base
        is_open = game.opened[i]
        
        if not is_open:
            # CLOSED STATE (3D Blue Button)
            d.rounded_rectangle([x, y+10, x+BOX_SIZE, y+BOX_SIZE+10], radius=15, fill=BOX_SHADOW)
            d.rounded_rectangle([x, y, x+BOX_SIZE, y+BOX_SIZE], radius=15, fill=BOX_CLOSED)
            d.rounded_rectangle([x+5, y+5, x+BOX_SIZE-5, y+BOX_SIZE//2], radius=15, fill=(255,255,255,40))
            centered_text(d, x + BOX_SIZE//2, y + BOX_SIZE//2, str(i+1), 50, "white")
            
        else:
            # OPENED STATE (Flat)
            content = game.board[i] # 0=Cookie, 1=Bomb
            opener_name = game.opened_by[i]
            
            fill = BOX_COOKIE if content == 0 else BOX_BOMB
            icon = "🍪" if content == 0 else "💥"
            
            # Pressed Box
            d.rounded_rectangle([x, y+10, x+BOX_SIZE, y+BOX_SIZE+10], radius=15, fill=fill)
            
            # Icon
            centered_text(d, x + BOX_SIZE//2, y + BOX_SIZE//2 - 15, icon, 60, "black", False)
            
            # Username Tag (Bottom of box)
            d.rounded_rectangle([x+5, y+BOX_SIZE-35, x+BOX_SIZE-5, y+BOX_SIZE+5], radius=8, fill=(0,0,0,140))
            centered_text(d, x + BOX_SIZE//2, y + BOX_SIZE-15, opener_name[:7], 20, "white", False)

    return img

# ==========================================
# 💣 BLAST CARD RENDERER
# ==========================================

def render_blast(username):
    W, H = 1024, 600
    img = utils.create_canvas(W, H, "#2c0000")
    d = ImageDraw.Draw(img)
    
    # Chaos Background
    for _ in range(30):
        x = random.randint(0, W); y = random.randint(0, H)
        s = random.randint(20, 200)
        col = random.choice(["#ff4500", "#ff8c00", "#000000"])
        d.ellipse([x, y, x+s, y+s], fill=col + "40") # Hex + Alpha workaround if supported, else distinct colors
    
    # Avatar
    av = get_avatar(username)
    if av:
        av = av.resize((350, 350))
        img.paste(av, (100, 125), av)
        
    # Text
    centered_text(d, 700, 200, "BOOM!", 140, "#FFD700")
    centered_text(d, 700, 350, f"@{username}", 60, "white")
    centered_text(d, 700, 450, "Lost 1 Cookie!", 40, "#FF4444")
    
    return img

# ==========================================
# 🏆 WINNER CARD RENDERER
# ==========================================

def render_winner(username, score):
    W, H = 1024, 600
    img = utils.create_canvas(W, H, "#2d3436")
    d = ImageDraw.Draw(img)
    
    cx, cy = W//2, H//2
    # Rays
    for i in range(0, 360, 15):
        import math
        r = 800
        x = cx + r * math.cos(math.radians(i))
        y = cy + r * math.sin(math.radians(i))
        d.line([cx, cy, x, y], fill="#f1c40f", width=5)
        
    av = get_avatar(username)
    if av:
        av = av.resize((250, 250))
        img.paste(av, (W//2 - 125, 50), av)
        
    centered_text(d, W//2, 350, "CHAMPION!", 90, "#f1c40f")
    centered_text(d, W//2, 450, f"@{username}", 60, "white")
    centered_text(d, W//2, 530, f"Score: {score}", 50, "#2ecc71")
    
    return img

# ==========================================
# ⚙️ GAME LOGIC (Hardcore Shuffle)
# ==========================================

class CookieGame:
    def __init__(self, room_id, host_id, host_name):
        self.id = room_id; self.host_id = host_id
        self.players = {}; self.state = 'lobby'; self.board = []
        self.opened = [False] * 36; self.opened_by = [""] * 36
        self.turn_order = []; self.turn_index = 0
        self.last_move_time = time.time(); self.turn_start_time = 0
        self.add_player(host_id, host_name)

    def add_player(self, uid, name):
        if len(self.players) >= 4: return False
        self.players[str(uid)] = {'uid': str(uid), 'name': name, 'score': 0, 'eliminated': False, 'strikes': 0}
        self.last_move_time = time.time()
        return True

    def start_game(self):
        count = len(self.players)
        if count < 2: return False
        
        # --- HARDCORE DIFFICULTY ---
        # 2 Players -> 8 Bombs
        # 3 Players -> 10 Bombs
        # 4 Players -> 12 Bombs
        bombs = 8 if count == 2 else 10 if count == 3 else 12
        cookies = 36 - bombs
        
        arr = [1]*bombs + [0]*cookies
        
        # --- TRUE SHUFFLE ---
        # Random seed based on time to ensure no pattern repeats
        random.seed(time.time()) 
        random.shuffle(arr)
        # Double shuffle for luck
        random.shuffle(arr)
        
        self.board = arr
        self.turn_order = list(self.players.keys())
        random.shuffle(self.turn_order)
        self.state = 'playing'
        self.turn_start_time = time.time()
        return True

    def next_turn(self):
        for _ in range(len(self.turn_order)):
            self.turn_index = (self.turn_index + 1) % len(self.turn_order)
            uid = self.turn_order[self.turn_index]
            if not self.players[uid]['eliminated']:
                self.turn_start_time = time.time()
                return uid
        return None

    def check_end_condition(self):
        active = [p for p in self.players.values() if not p['eliminated']]
        if len(active) <= 1: return True
        
        cookies_left = 0
        for i in range(36):
            if not self.opened[i] and self.board[i] == 0:
                cookies_left += 1
        return cookies_left == 0

# ==========================================
# ⚡ TASKS
# ==========================================

def task_update(bot, rid, g, text="Update"):
    try:
        img = render_board(g)
        link = utils.upload(bot, img)
        if link: bot.send_json({"handler": "chatroommessage", "roomid": rid, "type": "image", "url": link, "text": text})
    except: pass

def task_blast(bot, rid, g, user):
    try:
        img = render_blast(user)
        link = utils.upload(bot, img)
        if link: bot.send_json({"handler": "chatroommessage", "roomid": rid, "type": "image", "url": link, "text": "BOOM!"})
        time.sleep(2)
        task_update(bot, rid, g, "Board Updated")
    except: pass

def task_win(bot, rid, name, score):
    try:
        img = render_winner(name, score)
        link = utils.upload(bot, img)
        if link: bot.send_json({"handler": "chatroommessage", "roomid": rid, "type": "image", "url": link, "text": "WINNER"})
    except: pass

def game_monitor_loop():
    while True:
        time.sleep(5)
        if not games: continue
        now = time.time(); to_del = []
        with game_lock:
            for rid, g in games.items():
                if g.state == 'lobby' and now - g.last_move_time > 300:
                    if BOT_INSTANCE: BOT_INSTANCE.send_message(rid, "⏳ Lobby Expired"); to_del.append(rid); continue
                if g.state == 'playing' and now - g.last_move_time > 90:
                    if BOT_INSTANCE: BOT_INSTANCE.send_message(rid, "💤 Game Closed (90s Inactivity)"); to_del.append(rid); continue
                
                if g.state == 'playing':
                    curr = g.turn_order[g.turn_index]
                    p = g.players[curr]
                    if not p['eliminated'] and now - g.turn_start_time > 45:
                        p['eliminated'] = True
                        if BOT_INSTANCE: BOT_INSTANCE.send_message(rid, f"💀 **@{p['name']}** Timeout!")
                        if g.check_end_condition():
                            act = [x for x in g.players.values() if not x['eliminated']]
                            if act:
                                w = max(act, key=lambda x:x['score'])
                                task_win(BOT_INSTANCE, rid, w['name'], w['score'])
                                add_game_result(w['uid'], w['name'], "cookie_blast", 500, True)
                            to_del.append(rid)
                        else:
                            g.next_turn()
                            nxt = g.players[g.turn_order[g.turn_index]]['name']
                            if BOT_INSTANCE: BOT_INSTANCE.send_message(rid, f"👉 **@{nxt}** Turn")
        for r in to_del: 
            if r in games: del games[r]

# ==========================================
# 📨 HANDLER
# ==========================================

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    uid = data.get('userid', user)
    
    if cmd == "cookie":
        with game_lock:
            if room_id in games: return True
            games[room_id] = CookieGame(room_id, uid, user)
        bot.send_message(room_id, f"🍪 **Hardcore Blast!**\nHost: @{user}\nType `!join`")
        return True

    if cmd == "join":
        with game_lock:
            g = games.get(room_id)
            if not g or g.state != 'lobby': return False
            if str(uid) in g.players: return True
            if g.add_player(uid, user): bot.send_message(room_id, f"✅ **{user}** joined!")
            else: bot.send_message(room_id, "Full!")
        return True

    if cmd == "start":
        with game_lock:
            g = games.get(room_id)
            if not g or str(uid) != str(g.host_id): return False
            if g.start_game():
                utils.run_in_bg(task_update, bot, room_id, g, "Started")
                p1 = g.players[g.turn_order[0]]['name']
                bot.send_message(room_id, f"🔥 **Start!** Turn: @{p1}")
            else: bot.send_message(room_id, "Need 2+ Players")
        return True

    if cmd.isdigit():
        bn = int(cmd)
        if bn < 1 or bn > 36: return False
        with game_lock:
            g = games.get(room_id)
            if not g or g.state != 'playing': return False
            curr = g.turn_order[g.turn_index]
            if str(uid) != str(curr): return False
            
            idx = bn - 1
            if g.opened[idx]: 
                bot.send_message(room_id, "🚫 Opened!")
                return True
                
            g.opened[idx] = True; g.opened_by[idx] = user
            is_bomb = (g.board[idx] == 1)
            p = g.players[str(uid)]
            g.last_move_time = time.time()
            p['strikes'] = 0
            
            if is_bomb:
                p['score'] = max(0, p['score'] - 1)
                bot.send_message(room_id, f"💥 **BOOM!** @{user}")
                utils.run_in_bg(task_blast, bot, room_id, g, user)
            else:
                p['score'] += 1
                bot.send_message(room_id, f"🍪 **Yum!** @{user}")
                utils.run_in_bg(task_update, bot, room_id, g, "Move")
            
            if g.check_end_condition():
                act = [x for x in g.players.values() if not x['eliminated']]
                if act:
                    w = max(act, key=lambda x:x['score'])
                    add_game_result(w['uid'], w['name'], "cookie_blast", 500, True)
                    utils.run_in_bg(task_win, bot, room_id, w['name'], w['score'])
                    bot.send_message(room_id, f"🏆 **Winner:** @{w['name']}")
                del games[room_id]; return True
                
            g.next_turn()
            nxt = g.players[g.turn_order[g.turn_index]]['name']
            bot.send_message(room_id, f"👉 **@{nxt}** Turn")
        return True

    if cmd == "stop":
        with game_lock:
            g = games.get(room_id)
            if g and str(uid) == str(g.host_id):
                del games[room_id]; bot.send_message(room_id, "🛑 Stopped")
        return True
    return False
