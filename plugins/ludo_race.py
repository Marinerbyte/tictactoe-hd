import time
import random
import requests
import io
import sys
import os
import threading
import traceback
import uuid
from PIL import Image, ImageDraw, ImageFont

# --- DB IMPORT ---
try:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    import db
except Exception as e:
    print(f"DB Import Error: {e}")

# --- GLOBAL VARIABLES ---
games = {} 
games_lock = threading.Lock()
BOT_INSTANCE = None 
CACHED_IMAGES = {}
BASE_BOARD_CACHE = None

# --- CONFIG ---
MAX_PLAYERS = 4 
FINISH_LINE = 39 
WIN_REWARD = 100

HORSES_CONFIG = [
    {"name": "Bijli ⚡",   "url": "https://www.dropbox.com/scl/fi/5mxn0hancsdixl8o8qxv9/file_000000006d7871fdaee7d2e8f89d10ac.png?rlkey=tit3yzcn0dobpjy2p7g1hhr0z&st=7xyenect&dl=1"},
    {"name": "Toofan 🌪️",  "url": "https://www.dropbox.com/scl/fi/xrkby1kkak8ckxx75iixg/file_0000000086c871f8905c8f0de54f17dc.png?rlkey=nx91tgxbd3zcf60xtk7l6yqvj&st=2gj0n5lf&dl=1"},
    {"name": "Chetak 🐎",  "url": "https://www.dropbox.com/scl/fi/hvzez76rm1db5c0efxvt8/file_0000000027e47230b3f8471ac00250a3.png?rlkey=d8hu6l9movcicvr4irrqtdxnt&st=zicoegnf&dl=1"},
    {"name": "Badal ☁️",   "url": "https://www.dropbox.com/scl/fi/ge578p3tcdavurikbe3pm/8a281edf86f04365bb8308a73fd5b2a3_0_1768291766_9901.png?rlkey=2jr0oy6h40gp5yqck49djo9wh&st=awnz4exs&dl=1"},
    {"name": "Raftar 🚀",  "url": "https://www.dropbox.com/scl/fi/4at6eq4nxvgrp1exbilm5/e2b3f94bdbdd489c8d013d9bb259d4c4_0_1768292038_1500.png?rlkey=3m080rz9psgpx0ik4v10vfeqy&st=rdoo5aav&dl=1"},
    {"name": "Sultan 👑",  "url": "https://www.dropbox.com/scl/fi/ce2yjpv915e5t67vmq9bj/LS20260113135259.png?rlkey=rwy1sqp4jowpir8svpl89ew3g&st=n6wfjn7z&dl=1"}
]

# --- SETUP ---
def setup(bot_ref):
    global BOT_INSTANCE
    BOT_INSTANCE = bot_ref
    print("[LudoRace] Logic Loaded.")

# --- CLEANER ---
def game_cleanup_loop():
    while True:
        time.sleep(10)
        now = time.time()
        to_remove = []
        with games_lock:
            for room_id, game in games.items():
                if now - game.last_interaction > 120:
                    to_remove.append(room_id)
        for room_id in to_remove:
            if BOT_INSTANCE:
                try: BOT_INSTANCE.send_message(room_id, "⌛ Race cancelled (Timeout).")
                except: pass
            with games_lock:
                if room_id in games: del games[room_id]

if threading.active_count() < 10: 
    threading.Thread(target=game_cleanup_loop, daemon=True).start()

# --- UTILS ---
def get_font(size):
    try: return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except: return ImageFont.load_default()

def update_stats(user_id, username):
    if user_id == "BOT": return
    conn = db.get_connection()
    if not conn: return
    cur = conn.cursor()
    try:
        try: cur.execute("INSERT INTO users (user_id, username, global_score, wins) VALUES (%s, %s, 0, 0) ON CONFLICT (user_id) DO NOTHING", (user_id, username))
        except: cur.execute("INSERT OR IGNORE INTO users (user_id, username, global_score, wins) VALUES (?, ?, 0, 0)", (user_id, username))
        q1 = "UPDATE users SET global_score = global_score + %s, wins = wins + 1 WHERE user_id = %s"
        if not db.DATABASE_URL.startswith("postgres"): q1 = "UPDATE users SET global_score = global_score + ?, wins = wins + 1 WHERE user_id = ?"
        cur.execute(q1, (WIN_REWARD, user_id))
        
        try: cur.execute("INSERT INTO game_stats (user_id, game_name, wins, earnings) VALUES (%s, 'ludo', 0, 0) ON CONFLICT (user_id, game_name) DO NOTHING", (user_id,))
        except: cur.execute("INSERT OR IGNORE INTO game_stats (user_id, game_name, wins, earnings) VALUES (?, 'ludo', 0, 0)", (user_id,))
        q2 = "UPDATE game_stats SET wins = wins + 1, earnings = earnings + %s WHERE user_id = %s AND game_name = 'ludo'"
        if not db.DATABASE_URL.startswith("postgres"): q2 = "UPDATE game_stats SET wins = wins + 1, earnings = earnings + ? WHERE user_id = ? AND game_name = 'ludo'"
        cur.execute(q2, (WIN_REWARD, user_id))
        conn.commit()
    except Exception as e:
        print(f"DB Error: {e}")
    finally: conn.close()

def upload_image(bot, image, room_id):
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    url = "https://api.howdies.app/api/upload"
    try:
        uid = bot.user_id if bot.user_id else 0
        files = {'file': ('race.png', img_byte_arr, 'image/png')}
        data = {'token': bot.token, 'uploadType': 'image', 'UserID': uid}
        r = requests.post(url, files=files, data=data, timeout=10)
        res = r.json()
        return res.get('url') or res.get('data', {}).get('url')
    except: return None

# --- BOARD DRAWING ---
def get_horse_image(index):
    url = HORSES_CONFIG[index]["url"]
    if url not in CACHED_IMAGES:
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
                img = img.resize((40, 40))
                CACHED_IMAGES[url] = img
        except: return None
    return CACHED_IMAGES.get(url)

def get_coordinates(step):
    row = step // 10; col = step % 10
    start_x, start_y = 50, 80; box_w, box_h = 75, 90
    if row % 2 == 0: x = start_x + (col * box_w)
    else: x = start_x + ((9 - col) * box_w)
    y = start_y + (row * box_h)
    return int(x), int(y)

def create_base_board():
    width, height = 800, 500
    bg = Image.new('RGB', (width, height), (34, 139, 34)) 
    draw = ImageDraw.Draw(bg)
    font = get_font(20)
    sm_font = get_font(12)
    
    for i in range(FINISH_LINE):
        x1, y1 = get_coordinates(i); x2, y2 = get_coordinates(i+1)
        draw.line([(x1 + 35, y1 + 35), (x2 + 35, y2 + 35)], fill=(101, 67, 33), width=10)
    for i in range(FINISH_LINE + 1):
        x, y = get_coordinates(i); fill_color = (210, 180, 140)
        if i == 0: fill_color = (255, 215, 0)
        if i == FINISH_LINE: fill_color = (255, 69, 0)
        draw.rectangle([x, y, x + 70, y + 70], fill=fill_color, outline="white", width=2)
        draw.text((x + 5, y + 5), str(i), fill="black", font=sm_font)
        if i == 0: draw.text((x + 10, y + 25), "START", fill="black", font=sm_font)
        if i == FINISH_LINE: draw.text((x + 10, y + 25), "WIN", fill="white", font=sm_font)
    draw.text((400, 30), "🐎 HOWDIES SPEEDWAY 🐎", fill="white", font=font, anchor="mm")
    return bg

BASE_BOARD_CACHE = create_base_board()

def draw_game_state(players, msg=""):
    img = BASE_BOARD_CACHE.copy()
    step_map = {}
    for p in players:
        s = p['pos']
        if s not in step_map: step_map[s] = []
        step_map[s].append(p)
    
    for step, p_list in step_map.items():
        base_x, base_y = get_coordinates(step)
        count = 0
        for p in p_list:
            h_img = get_horse_image(p['horse_idx'])
            if h_img:
                off_x = (count % 2) * 20
                off_y = (count // 2) * 20
                img.paste(h_img, (base_x + 10 + off_x, base_y + 10 + off_y), h_img)
                count += 1
    
    if msg:
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 450, 800, 500], fill=(0,0,0))
        font = get_font(25)
        draw.text((400, 475), msg, fill="yellow", font=font, anchor="mm")
    
    return img

# --- GAME LOGIC ---
class LudoGame:
    def __init__(self, host_id, mode):
        self.host_id = host_id
        self.mode = mode
        self.state = 'waiting'
        self.players = [] 
        self.turn_idx = 0
        self.last_interaction = time.time()
        deck = list(range(len(HORSES_CONFIG)))
        random.shuffle(deck)
        self.deck = deck[:MAX_PLAYERS]

    def touch(self): self.last_interaction = time.time()
    def add_player(self, uid, name):
        if not self.deck: return None
        h_idx = self.deck.pop(0)
        self.players.append({"uid": uid, "name": name, "horse_idx": h_idx, "pos": 0})
        self.touch()
        return h_idx
    def get_current_player(self): return self.players[self.turn_idx]
    def next_turn(self): 
        self.turn_idx = (self.turn_idx + 1) % len(self.players)
        return self.players[self.turn_idx]

# --- HANDLER ---
def handle_command(bot, command, room_id, user, args, data):
    try:
        global games, BOT_INSTANCE
        if BOT_INSTANCE is None: BOT_INSTANCE = bot
        user_id = data.get('userid', user)
        cmd_clean = command.lower().strip()

        with games_lock: current_game = games.get(room_id)

        # NEW GAME
        if cmd_clean == "race":
            if current_game:
                bot.send_message(room_id, "⚠️ Game running! Type 'stop'.")
                return True
            mode = args[0] if args else "1"
            with games_lock: 
                game = LudoGame(user_id, mode)
                h = game.add_player(user_id, user)
                games[room_id] = game
            
            h_name = HORSES_CONFIG[h]["name"]
            
            if mode == "1":
                game.add_player("BOT", "Bot 🤖")
                game.state = 'playing'
                img = draw_game_state(game.players, "1v1 STARTED! Type !roll")
                link = upload_image(bot, img, room_id)
                bot.send_message(room_id, f"⚔️ **1v1 Race!**\n@{user} ({h_name}) VS Bot.")
                if link: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Start", "id": uuid.uuid4().hex})
            else:
                bot.send_message(room_id, f"🏆 **Lobby Open! (Max 4)**\nHost: @{user} ({h_name})\nType `!join` to enter.")
            return True

        # STOP
        if cmd_clean == "stop" and current_game:
            with games_lock: del games[room_id]
            bot.send_message(room_id, "🛑 Race Stopped.")
            return True

        # JOIN & START (Same as before)
        if current_game:
            game = current_game
            
            if cmd_clean == "join" and game.state == 'waiting':
                if any(p['uid'] == user_id for p in game.players): return True
                if len(game.players) >= MAX_PLAYERS: bot.send_message(room_id, "Full!"); return True
                h = game.add_player(user_id, user)
                bot.send_message(room_id, f"✅ @{user} joined ({HORSES_CONFIG[h]['name']})")
                return True
            
            if cmd_clean == "start" and game.state == 'waiting':
                if game.host_id != user_id: return True
                if len(game.players) < 2: bot.send_message(room_id, "Need 2+ players."); return True
                game.state = 'playing'
                game.touch()
                img = draw_game_state(game.players, "RACE START! First Turn")
                link = upload_image(bot, img, room_id)
                p1 = game.get_current_player()
                bot.send_message(room_id, f"🚦 **GO!** @{p1['name']}'s turn (`!roll`)")
                if link: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Go", "id": uuid.uuid4().hex})
                return True

            # --- MODIFIED ROLL LOGIC (MERGED TURNS) ---
            if cmd_clean == "roll" and game.state == 'playing':
                curr = game.get_current_player()
                if curr['uid'] == "BOT": return True
                if curr['uid'] != user_id: return True
                
                game.touch()
                
                # 1. PLAYER MOVE
                p_dice = random.randint(1, 6)
                curr['pos'] += p_dice
                msg_text = f"You: {p_dice} (Pos {curr['pos']})"
                
                # Check Player Win
                if curr['pos'] >= FINISH_LINE:
                    curr['pos'] = FINISH_LINE
                    update_stats(curr['uid'], curr['name'])
                    img = draw_game_state(game.players, f"WINNER: {curr['name']}!")
                    link = upload_image(bot, img, room_id)
                    if link: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Win", "id": uuid.uuid4().hex})
                    bot.send_message(room_id, f"🎉🏆 **{curr['name']} WINS!** 🏆🎉")
                    with games_lock: del games[room_id]
                    return True
                
                # Advance Turn
                next_p = game.next_turn()
                
                # 2. IF NEXT IS BOT -> MOVE IMMEDIATELY & COMBINE IMAGE
                if next_p['uid'] == "BOT":
                    b_dice = random.randint(1, 6)
                    next_p['pos'] += b_dice
                    msg_text += f" | Bot: {b_dice} (Pos {next_p['pos']})"
                    
                    # Check Bot Win
                    if next_p['pos'] >= FINISH_LINE:
                        next_p['pos'] = FINISH_LINE
                        img = draw_game_state(game.players, "BOT WINS!")
                        link = upload_image(bot, img, room_id)
                        if link: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "BotWin", "id": uuid.uuid4().hex})
                        bot.send_message(room_id, "🤖 **Computer Wins!**")
                        with games_lock: del games[room_id]
                        return True
                    
                    # Turn back to Player
                    game.next_turn()
                
                # 3. SEND ONE COMBINED IMAGE
                img = draw_game_state(game.players, msg_text)
                link = upload_image(bot, img, room_id)
                
                if link:
                    bot.send_json({
                        "handler": "chatroommessage", 
                        "roomid": room_id, 
                        "type": "image", 
                        "url": link, 
                        "text": msg_text, 
                        "id": uuid.uuid4().hex
                    })
                else:
                    bot.send_message(room_id, msg_text)

                return True

        return False
    except Exception as e:
        traceback.print_exc()
        return False
