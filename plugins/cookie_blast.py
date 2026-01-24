import time
import random
import threading
import traceback
from PIL import Image, ImageDraw, ImageFont

# --- IMPORTS ---
try: 
    import utils 
except ImportError: 
    print("[CookieBlast] Warning: utils.py not found. Uploads will fail.")

try: 
    from db import add_game_result
except: 
    pass

# --- CONFIGURATION ---
GAME_NAME = "Cookie Blast Royale"
GRID_SIZE = 6 # 6x6 = 36 boxes
BOX_SIZE = 100
GAP = 15
BG_COLOR = "#2d3436" # Dark Slate
BUTTON_COLOR = "#6c5ce7" # Purple
BUTTON_SHADOW = "#4834d4" # Dark Purple
COOKIE_COLOR = "#fdcb6e" # Gold
BOMB_COLOR = "#d63031" # Red

# --- GLOBALS ---
games = {}
game_lock = threading.Lock()
BOT_INSTANCE = None 

def setup(bot):
    global BOT_INSTANCE
    BOT_INSTANCE = bot
    # Background thread for timeouts
    threading.Thread(target=game_monitor_loop, daemon=True).start()
    print(f"[{GAME_NAME}] Plugin Loaded.")

# ==========================================
# 🎨 GRAPHICS ENGINE
# ==========================================

def get_font(size):
    try: return ImageFont.truetype("arialbd.ttf", size)
    except: return ImageFont.load_default()

def draw_3d_button(draw, x, y, size, text, color, shadow_col, is_open=False, content_type=None):
    """Draws a clickable 3D box or revealed content"""
    radius = 15
    
    if not is_open:
        # Shadow (Depth)
        draw.rounded_rectangle([x, y+5, x+size, y+size+5], radius, fill=shadow_col)
        # Main Button
        draw.rounded_rectangle([x, y, x+size, y+size], radius, fill=color)
        # Highlight (Top Shine)
        draw.rounded_rectangle([x+5, y+5, x+size-5, y+(size//2)], radius, fill=(255,255,255,30))
        # Number
        font = get_font(30)
        w = font.getlength(text) if hasattr(font, 'getlength') else len(text)*15
        draw.text((x + (size-w)/2, y + (size/2) - 15), text, font=font, fill="white")
    else:
        # Revealed State
        bg = "#222"
        icon = ""
        icon_col = "white"
        
        if content_type == 0: # Cookie
            bg = COOKIE_COLOR
            icon = "🍪"
            icon_col = "black"
        elif content_type == 1: # Bomb
            bg = BOMB_COLOR
            icon = "💣"
        
        draw.rounded_rectangle([x, y+5, x+size, y+size+5], radius, fill="#111") # Shadow
        draw.rounded_rectangle([x, y+5, x+size, y+size+5], radius, fill=bg) # Pressed down look
        
        font = get_font(50)
        # Center Icon
        try: w = font.getlength(icon)
        except: w = 30
        draw.text((x + (size-w)/2, y + (size/2) - 25), icon, font=font, fill=icon_col)

def render_board(game):
    """Generates the 6x6 Grid Image"""
    W = (BOX_SIZE * GRID_SIZE) + (GAP * (GRID_SIZE + 1))
    H = W + 150 # Extra space for score header
    
    img = utils.create_canvas(W, H, BG_COLOR)
    d = ImageDraw.Draw(img)
    
    # 1. Header (Scores)
    # Sort players by score
    sorted_players = sorted(game.players.values(), key=lambda x: x['score'], reverse=True)
    
    header_y = 20
    px = 20
    for p in sorted_players:
        name = p['name'][:6]
        score = p['score']
        active = "💀" if p['eliminated'] else "🍪"
        
        # Highlight current turn
        border_col = "#00b894" if p['uid'] == game.turn_order[game.turn_index] else "#636e72"
        
        d.rounded_rectangle([px, header_y, px+120, header_y+60], 10, fill="#333", outline=border_col, width=2)
        utils.write_text(d, (px+10, header_y+5), f"{name}", 14, "white")
        utils.write_text(d, (px+10, header_y+30), f"{active} {score}", 18, "#fdcb6e")
        px += 130

    # 2. Grid
    start_y = 120
    for i in range(36):
        row = i // 6
        col = i % 6
        
        x = GAP + (col * (BOX_SIZE + GAP))
        y = start_y + (row * (BOX_SIZE + GAP))
        
        is_open = game.opened[i]
        content = game.board[i] if is_open else None
        
        draw_3d_button(d, x, y, BOX_SIZE, str(i+1), BUTTON_COLOR, BUTTON_SHADOW, is_open, content)

    return img

def render_blast(username):
    """Dark card for Bomb Blast"""
    img = utils.create_canvas(600, 400, "#1a0505")
    d = ImageDraw.Draw(img)
    
    # Cracks
    for _ in range(10):
        x1 = random.randint(0, 600)
        y1 = random.randint(0, 400)
        x2 = x1 + random.randint(-100, 100)
        y2 = y1 + random.randint(-100, 100)
        d.line([x1, y1, x2, y2], fill="#4a0000", width=3)
        
    utils.write_text(d, (300, 150), "💣 BOOM! 💣", 60, "#ff4444", "center", True)
    utils.write_text(d, (300, 250), f"@{username} hit a mine!", 30, "white", "center")
    return img

def render_winner(username, score):
    """Bright card for Winner"""
    img = utils.create_canvas(600, 400, "#2d3436")
    d = ImageDraw.Draw(img)
    
    # Gold Rays
    cx, cy = 300, 200
    for i in range(0, 360, 20):
        # Simple rays
        import math
        r = 400
        x = cx + r * math.cos(math.radians(i))
        y = cy + r * math.sin(math.radians(i))
        d.line([cx, cy, x, y], fill="#fdcb6e", width=5)
    
    # Center Box
    d.rounded_rectangle([100, 100, 500, 300], 20, fill="#00b894", outline="white", width=4)
    
    utils.write_text(d, (300, 140), "VICTORY!", 50, "white", "center", True)
    utils.write_text(d, (300, 220), f"👑 @{username}", 35, "white", "center", True)
    utils.write_text(d, (300, 330), f"Total Cookies: {score}", 25, "#fdcb6e", "center")
    
    return img

# ==========================================
# ⚙️ GAME LOGIC
# ==========================================

class CookieGame:
    def __init__(self, room_id, host_id, host_name):
        self.id = room_id
        self.host_id = host_id
        self.players = {} # {uid: {name, score, eliminated, strikes, uid}}
        self.state = 'lobby'
        self.board = [] # 0=Cookie, 1=Bomb
        self.opened = [False] * 36
        self.turn_order = []
        self.turn_index = 0
        
        # Timers
        self.last_move_time = time.time()
        self.turn_start_time = 0
        
        # Add Host
        self.add_player(host_id, host_name)

    def add_player(self, uid, name):
        if len(self.players) >= 4: return False
        self.players[str(uid)] = {
            'uid': str(uid),
            'name': name,
            'score': 0,
            'eliminated': False,
            'strikes': 0
        }
        self.last_move_time = time.time()
        return True

    def start_game(self):
        count = len(self.players)
        if count < 2: return False
        
        # 1. Logic: Bombs based on players
        bombs = 6 if count == 2 else 7 if count == 3 else 8
        cookies = 36 - bombs
        
        # 2. Create Board
        arr = [1]*bombs + [0]*cookies
        random.shuffle(arr)
        self.board = arr
        
        # 3. Setup Turns
        self.turn_order = list(self.players.keys())
        random.shuffle(self.turn_order)
        self.turn_index = 0
        self.state = 'playing'
        self.turn_start_time = time.time()
        self.last_move_time = time.time()
        return True

    def next_turn(self):
        # Find next non-eliminated player
        original_idx = self.turn_index
        for _ in range(len(self.turn_order)):
            self.turn_index = (self.turn_index + 1) % len(self.turn_order)
            uid = self.turn_order[self.turn_index]
            if not self.players[uid]['eliminated']:
                self.turn_start_time = time.time()
                return uid
        return None # Should not happen unless all dead

    def check_end_condition(self):
        # 1. Only 1 player left
        active = [p for p in self.players.values() if not p['eliminated']]
        if len(active) <= 1: return True
        
        # 2. Only Bombs remaining (All cookies found)
        unopened_indices = [i for i, x in enumerate(self.opened) if not x]
        cookies_left = sum(1 for i in unopened_indices if self.board[i] == 0)
        
        if cookies_left == 0: return True
        
        return False

# ==========================================
# ⚡ BACKGROUND TASKS
# ==========================================

def task_update(bot, rid, game, text="Update"):
    try:
        img = render_board(game)
        link = utils.upload(bot, img)
        if link:
            bot.send_json({"handler": "chatroommessage", "roomid": rid, "type": "image", "url": link, "text": text})
    except: pass

def task_blast(bot, rid, game, username):
    # Show Blast Card first
    try:
        b_img = render_blast(username)
        b_link = utils.upload(bot, b_img)
        if b_link:
            bot.send_json({"handler": "chatroommessage", "roomid": rid, "type": "image", "url": b_link, "text": "BOOM!"})
    except: pass
    
    time.sleep(2) # Drama pause
    
    # Show updated board
    task_update(bot, rid, game, "Board Updated")

def task_win(bot, rid, game, winner_name, score):
    try:
        w_img = render_winner(winner_name, score)
        w_link = utils.upload(bot, w_img)
        if w_link:
            bot.send_json({"handler": "chatroommessage", "roomid": rid, "type": "image", "url": w_link, "text": "WINNER"})
    except: pass

def game_monitor_loop():
    """Handles timeouts and auto-kicks"""
    while True:
        time.sleep(5)
        if not games: continue
        
        now = time.time()
        to_delete = []
        
        with game_lock:
            for rid, g in games.items():
                # Lobby Timeout (3 mins)
                if g.state == 'lobby' and now - g.last_move_time > 180:
                    if BOT_INSTANCE: BOT_INSTANCE.send_message(rid, "⏳ Lobby Closed (Timeout)")
                    to_delete.append(rid)
                    continue
                
                # Global Game Timeout (90s inactivity)
                if g.state == 'playing' and now - g.last_move_time > 90:
                    if BOT_INSTANCE: BOT_INSTANCE.send_message(rid, "💤 Game Closed (90s Inactivity)")
                    to_delete.append(rid)
                    continue
                
                # Turn Timeout (45s)
                if g.state == 'playing':
                    curr_uid = g.turn_order[g.turn_index]
                    p = g.players[curr_uid]
                    
                    if not p['eliminated'] and now - g.turn_start_time > 45:
                        # STRIKE LOGIC
                        p['strikes'] += 1
                        if p['strikes'] >= 1: # Strict: 1 strike = out
                            p['eliminated'] = True
                            if BOT_INSTANCE: BOT_INSTANCE.send_message(rid, f"⏱️ **@{p['name']}** timed out! Eliminated.")
                            
                            # Check if game ends
                            if g.check_end_condition():
                                # End game logic handled in main loop usually, but here we force end
                                active = [pl for pl in g.players.values() if not pl['eliminated']]
                                if active:
                                    winner = max(active, key=lambda x:x['score'])
                                    task_win(BOT_INSTANCE, rid, g, winner['name'], winner['score'])
                                    # Add Economy
                                    add_game_result(winner['uid'], winner['name'], "cookie_blast", 500, True)
                                else:
                                    if BOT_INSTANCE: BOT_INSTANCE.send_message(rid, "💀 Everyone died.")
                                to_delete.append(rid)
                            else:
                                # Next Turn
                                g.next_turn()
                                g.turn_start_time = time.time()
                                next_uid = g.turn_order[g.turn_index]
                                next_name = g.players[next_uid]['name']
                                if BOT_INSTANCE: BOT_INSTANCE.send_message(rid, f"👉 **@{next_name}** It's your turn!")
                        else:
                            # Warning (Optional, logic above makes it instant)
                            pass

        for rid in to_delete:
            if rid in games: del games[rid]

# ==========================================
# 📨 HANDLER
# ==========================================

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    uid = data.get('userid', user)
    
    # 1. CREATE GAME
    if cmd == "cookie":
        with game_lock:
            if room_id in games: 
                bot.send_message(room_id, "⚠️ Game already active!")
                return True
            
            g = CookieGame(room_id, uid, user)
            games[room_id] = g
            
        bot.send_message(room_id, f"🍪 **Cookie Blast Royale!**\nHost: @{user}\nType `!join` to enter (Max 4).")
        return True

    # 2. JOIN
    if cmd == "join":
        with game_lock:
            g = games.get(room_id)
            if not g or g.state != 'lobby': return False
            
            if str(uid) in g.players:
                bot.send_message(room_id, "Already joined!")
                return True
                
            if g.add_player(uid, user):
                bot.send_message(room_id, f"✅ **{user}** joined! ({len(g.players)}/4)")
            else:
                bot.send_message(room_id, "Lobby Full!")
        return True

    # 3. START
    if cmd == "start":
        with game_lock:
            g = games.get(room_id)
            if not g: return False
            
            if str(uid) != str(g.host_id):
                bot.send_message(room_id, "❌ Only Host can start.")
                return True
                
            if g.start_game():
                p1 = g.turn_order[0]
                p1_name = g.players[p1]['name']
                utils.run_in_bg(task_update, bot, room_id, g, "Game Started")
                bot.send_message(room_id, f"🔥 **Game On!**\nGrid: 1-36\nTurn: @{p1_name}")
            else:
                bot.send_message(room_id, "Need at least 2 players!")
        return True

    # 4. GAMEPLAY (Number Input)
    if cmd.isdigit():
        box_num = int(cmd)
        if box_num < 1 or box_num > 36: return False # Ignore invalid nums
        
        with game_lock:
            g = games.get(room_id)
            if not g or g.state != 'playing': return False
            
            # Check Turn
            curr_uid = g.turn_order[g.turn_index]
            if str(uid) != str(curr_uid): return False # Silent ignore not turn
            
            idx = box_num - 1
            if g.opened[idx]:
                bot.send_message(room_id, "🚫 Box already opened!")
                return True
            
            # PROCESS MOVE
            g.opened[idx] = True
            is_bomb = (g.board[idx] == 1)
            player = g.players[str(uid)]
            
            g.last_move_time = time.time()
            
            if is_bomb:
                # Penalty
                player['score'] = max(0, player['score'] - 1)
                bot.send_message(room_id, f"💥 **BOOM!** @{user} hit a bomb! (-1 Score)")
                # Show Blast Card
                utils.run_in_bg(task_blast, bot, room_id, g, user)
            else:
                # Cookie
                player['score'] += 1
                bot.send_message(room_id, f"🍪 **Yum!** @{user} found a cookie! (+1 Score)")
                # Just update board
                utils.run_in_bg(task_update, bot, room_id, g, "Move")

            # Check End
            if g.check_end_condition():
                # Determine Winner
                active_players = [p for p in g.players.values() if not p['eliminated']]
                if not active_players:
                    bot.send_message(room_id, "🏳️ Draw (Everyone Eliminated)")
                else:
                    winner = max(active_players, key=lambda x: x['score'])
                    # Tie-Breaker? (Highest score wins, if tie, shared)
                    # Simple Max for now
                    
                    add_game_result(winner['uid'], winner['name'], "cookie_blast", 500, True)
                    utils.run_in_bg(task_win, bot, room_id, g, winner['name'], winner['score'])
                    bot.send_message(room_id, f"🏆 **GAME OVER!** Winner: @{winner['name']}")
                
                del games[room_id]
                return True
            
            # Next Turn
            g.next_turn()
            nxt_uid = g.turn_order[g.turn_index]
            nxt_name = g.players[nxt_uid]['name']
            bot.send_message(room_id, f"👉 **@{nxt_name}'s** Turn")
            
        return True

    # 5. STOP
    if cmd == "stop":
        with game_lock:
            g = games.get(room_id)
            if g and str(uid) == str(g.host_id):
                del games[room_id]
                bot.send_message(room_id, "🛑 Game Stopped.")
        return True

    return False
