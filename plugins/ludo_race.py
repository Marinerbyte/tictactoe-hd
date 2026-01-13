import threading
import random
import io
import requests
import time
import os
from PIL import Image, ImageDraw, ImageFont
from db import get_connection, db_lock

# --- CONFIGURATION ---
MAX_PLAYERS = 4 
FINISH_LINE = 39 
TIMEOUT_SECONDS = 90
WIN_REWARD = 100

# Agar Render/Heroku par ho, to apna URL yahan daalo
# Example: MY_DOMAIN = "https://your-app-name.onrender.com"
MY_DOMAIN = "" 

HORSES_CONFIG = [
    {"name": "Bijli ⚡",   "url": "https://www.dropbox.com/scl/fi/5mxn0hancsdixl8o8qxv9/file_000000006d7871fdaee7d2e8f89d10ac.png?rlkey=tit3yzcn0dobpjy2p7g1hhr0z&st=7xyenect&dl=1"},
    {"name": "Toofan 🌪️",  "url": "https://www.dropbox.com/scl/fi/xrkby1kkak8ckxx75iixg/file_0000000086c871f8905c8f0de54f17dc.png?rlkey=nx91tgxbd3zcf60xtk7l6yqvj&st=2gj0n5lf&dl=1"},
    {"name": "Chetak 🐎",  "url": "https://www.dropbox.com/scl/fi/hvzez76rm1db5c0efxvt8/file_0000000027e47230b3f8471ac00250a3.png?rlkey=d8hu6l9movcicvr4irrqtdxnt&st=zicoegnf&dl=1"},
    {"name": "Badal ☁️",   "url": "https://www.dropbox.com/scl/fi/ge578p3tcdavurikbe3pm/8a281edf86f04365bb8308a73fd5b2a3_0_1768291766_9901.png?rlkey=2jr0oy6h40gp5yqck49djo9wh&st=awnz4exs&dl=1"},
    {"name": "Raftar 🚀",  "url": "https://www.dropbox.com/scl/fi/4at6eq4nxvgrp1exbilm5/e2b3f94bdbdd489c8d013d9bb259d4c4_0_1768292038_1500.png?rlkey=3m080rz9psgpx0ik4v10vfeqy&st=rdoo5aav&dl=1"},
    {"name": "Sultan 👑",  "url": "https://www.dropbox.com/scl/fi/ce2yjpv915e5t67vmq9bj/LS20260113135259.png?rlkey=rwy1sqp4jowpir8svpl89ew3g&st=n6wfjn7z&dl=1"}
]

GAME_LOCK = threading.Lock()
ACTIVE_GAMES = {} 
CACHED_IMAGES = {}
BASE_BOARD_CACHE = None 

# --- 1. STATIC FOLDER SETUP ---
# Ye folder images save karne ke liye banega
STATIC_DIR = os.path.join(os.getcwd(), "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)

# --- 2. DB HELPER ---
def add_win_stats(user_id, username):
    if user_id == "BOT": return
    with db_lock:
        try:
            conn = get_connection()
            cur = conn.cursor()
            # Global Score
            cur.execute("INSERT OR IGNORE INTO users (user_id, username, global_score, wins) VALUES (?, ?, 0, 0)", (str(user_id), username))
            cur.execute("UPDATE users SET global_score = global_score + ?, wins = wins + 1 WHERE user_id = ?", (WIN_REWARD, str(user_id)))
            # Game Specific Score
            cur.execute("INSERT OR IGNORE INTO game_stats (user_id, game_name, wins, earnings) VALUES (?, 'ludo', 0, 0)", (str(user_id),))
            cur.execute("UPDATE game_stats SET wins = wins + 1, earnings = earnings + ? WHERE user_id = ? AND game_name = 'ludo'", (WIN_REWARD, str(user_id)))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[DB Error] {e}")

# --- 3. INTERNAL BOARD GENERATION (Drawing Logic) ---
def get_horse_image(index):
    url = HORSES_CONFIG[index]["url"]
    if url not in CACHED_IMAGES:
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
                img = img.resize((45, 45))
                CACHED_IMAGES[url] = img
        except: return None
    return CACHED_IMAGES.get(url)

def get_coordinates(step):
    # Snake Logic: Calculate X, Y based on step number
    row = step // 10
    col = step % 10
    start_x, start_y = 50, 80
    box_w, box_h = 75, 90
    
    if row % 2 == 0: x = start_x + (col * box_w) # Left to Right
    else: x = start_x + ((9 - col) * box_w)      # Right to Left
    
    y = start_y + (row * box_h)
    return int(x), int(y)

def create_base_board():
    """Ye function Code se Board DRAW karta hai (No image file needed)"""
    width, height = 800, 500
    # 1. Green Grass Background
    bg = Image.new('RGB', (width, height), (34, 139, 34)) 
    draw = ImageDraw.Draw(bg)
    
    try: font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
    except: font = ImageFont.load_default()
    sm_font = font 
    
    # 2. Draw Connections (Brown Lines)
    for i in range(FINISH_LINE):
        x1, y1 = get_coordinates(i)
        x2, y2 = get_coordinates(i+1)
        draw.line([(x1 + 35, y1 + 35), (x2 + 35, y2 + 35)], fill=(101, 67, 33), width=10)

    # 3. Draw Boxes (Steps)
    for i in range(FINISH_LINE + 1):
        x, y = get_coordinates(i)
        fill_color = (210, 180, 140) # Mitti jaisa color
        if i == 0: fill_color = (255, 215, 0) # Start (Gold)
        if i == FINISH_LINE: fill_color = (255, 69, 0) # End (Red)
        
        draw.rectangle([x, y, x + 70, y + 70], fill=fill_color, outline="white", width=2)
        draw.text((x + 5, y + 5), str(i), fill="black", font=sm_font)
        
        if i == 0: draw.text((x + 10, y + 25), "START", fill="black", font=sm_font)
        if i == FINISH_LINE: draw.text((x + 10, y + 25), "WIN", fill="white", font=sm_font)

    draw.text((400, 30), "🐎 HOWDIES SPEEDWAY 🐎", fill="white", font=font, anchor="mm")
    return bg

# Generate Board Once on Startup
BASE_BOARD_CACHE = create_base_board()

def send_board_image(bot, room_id, players, msg=""):
    """Horses ko Board par paste karke bhejna"""
    try:
        # Clone base board
        img = BASE_BOARD_CACHE.copy()
        
        # Group players by position
        step_map = {}
        for p in players:
            s = p['pos']
            if s not in step_map: step_map[s] = []
            step_map[s].append(p)
            
        # Paste Horses
        for step, p_list in step_map.items():
            base_x, base_y = get_coordinates(step)
            count = 0
            for p in p_list:
                h_img = get_horse_image(p['horse_idx'])
                if h_img:
                    # Offset logic to show multiple horses
                    off_x = (count % 2) * 25
                    off_y = (count // 2) * 25
                    img.paste(h_img, (base_x + 12 + off_x, base_y + 12 + off_y), h_img)
                    count += 1

        # Add Message at Bottom
        if msg:
            draw = ImageDraw.Draw(img)
            draw.rectangle([0, 450, 800, 500], fill=(0,0,0))
            try: font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 25)
            except: font = ImageFont.load_default()
            draw.text((400, 475), msg, fill="yellow", font=font, anchor="mm")

        # Save to static folder
        filename = f"race_{room_id}_{int(time.time())}.png"
        filepath = os.path.join(STATIC_DIR, filename)
        img.save(filepath)

        # Create URL
        domain = MY_DOMAIN if MY_DOMAIN else "http://localhost:5000"
        image_url = f"{domain}/static/{filename}"
        
        # Send to Chat
        bot.send_message(room_id, f"{msg}\n{image_url}")
        
    except Exception as e:
        print(f"[Board Error] {e}")

# --- 4. GAME LOGIC ---
class LudoGame:
    def __init__(self, host_id, mode):
        self.host_id = host_id; self.mode = mode; self.state = 'waiting'
        self.players = []; self.turn_idx = 0; self.last_active = time.time()
        self.deck = list(range(len(HORSES_CONFIG))); random.shuffle(self.deck)
        self.deck = self.deck[:MAX_PLAYERS]

    def refresh(self): self.last_active = time.time()
    def add_player(self, uid, name):
        if not self.deck: return None
        h_idx = self.deck.pop(0)
        self.players.append({"uid": uid, "name": name, "horse_idx": h_idx, "pos": 0})
        self.refresh()
        return h_idx
    def get_current_player(self): return self.players[self.turn_idx]
    def next_turn(self): 
        self.turn_idx = (self.turn_idx + 1) % len(self.players)
        return self.players[self.turn_idx]

# --- 5. CLEANUP DAEMON ---
def setup(bot):
    t = threading.Thread(target=cleanup_loop, args=(bot,), daemon=True)
    t.start()

def cleanup_loop(bot):
    while True:
        time.sleep(15)
        now = time.time()
        # Clean images older than 5 mins
        try:
            if os.path.exists(STATIC_DIR):
                for f in os.listdir(STATIC_DIR):
                    fpath = os.path.join(STATIC_DIR, f)
                    if os.path.isfile(fpath) and now - os.path.getmtime(fpath) > 300:
                        os.remove(fpath)
        except: pass
        
        # Clean inactive games
        to_remove = []
        with GAME_LOCK:
            for room_id, game in ACTIVE_GAMES.items():
                if now - game.last_active > TIMEOUT_SECONDS: to_remove.append(room_id)
            for r in to_remove:
                del ACTIVE_GAMES[r]
                try: bot.send_message(r, "⏰ Game Timeout! Race cancelled.")
                except: pass

# --- 6. HANDLER ---
def handle_command(bot, command, room_id, user, args, data):
    user_id = data.get('userid', user)
    
    if command == "race":
        mode = args[0] if args else "1"
        with GAME_LOCK:
            if room_id in ACTIVE_GAMES:
                bot.send_message(room_id, "⚠️ Game already running!")
                return True
            game = LudoGame(user_id, mode)
            h = game.add_player(user_id, user)
            ACTIVE_GAMES[room_id] = game
            
            if mode == "1":
                game.add_player("BOT", "Computer 🤖")
                game.state = 'playing'
                send_board_image(bot, room_id, game.players, "1v1 STARTED! Type !roll")
            else:
                bot.send_message(room_id, f"🏆 Lobby Open! Host: @{user}\nType `!join` to enter.")
        return True

    if command == "join":
        with GAME_LOCK:
            game = ACTIVE_GAMES.get(room_id)
            if not game or game.mode != "2" or game.state != "waiting": return True
            if any(p['uid'] == user_id for p in game.players): return True
            if len(game.players) >= MAX_PLAYERS: 
                bot.send_message(room_id, "Lobby Full!"); return True
            h = game.add_player(user_id, user)
            bot.send_message(room_id, f"✅ @{user} joined!")
        return True

    if command == "start":
        with GAME_LOCK:
            game = ACTIVE_GAMES.get(room_id)
            if not game or game.host_id != user_id or len(game.players) < 2: return True
            game.state = 'playing'
            send_board_image(bot, room_id, game.players, "RACE STARTED!")
        return True

    if command == "roll":
        if room_id not in ACTIVE_GAMES: return False
        with GAME_LOCK:
            game = ACTIVE_GAMES[room_id]
            if game.state != 'playing': return True
            curr = game.get_current_player()
            if curr['uid'] == "BOT" and user_id != "BOT": return True
            if curr['uid'] != user_id and curr['uid'] != "BOT": 
                bot.send_message(room_id, f"Wait for @{curr['name']}")
                return True
            
            game.refresh()
            dice = random.randint(1, 6)
            curr['pos'] += dice
            msg = f"🎲 @{curr['name']} rolled {dice}!"
            
            if curr['pos'] >= FINISH_LINE:
                curr['pos'] = FINISH_LINE
                add_win_stats(curr['uid'], curr['name'])
                send_board_image(bot, room_id, game.players, f"WINNER: {curr['name']}!")
                del ACTIVE_GAMES[room_id]
                return True
            
            bot.send_message(room_id, msg)
            
            # Note: Har move par image bhejne se lag ho sakta hai.
            # Agar chahiye to niche wali line uncomment karein:
            # send_board_image(bot, room_id, game.players, msg)
            
            next_p = game.next_turn()
            if next_p['uid'] == "BOT":
                def bot_move():
                    time.sleep(2)
                    handle_command(bot, "roll", room_id, "BOT", [], {})
                threading.Thread(target=bot_move).start()
        return True
    return False
