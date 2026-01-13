import threading
import random
import io
import requests
import time
from PIL import Image, ImageDraw, ImageFont

# --- CONFIGURATION ---
# Horse Data: Names mapped to specific URLs you provided
HORSES_CONFIG = [
    {"name": "Badal ☁️",   "url": "https://www.dropbox.com/scl/fi/ge578p3tcdavurikbe3pm/8a281edf86f04365bb8308a73fd5b2a3_0_1768291766_9901.png?rlkey=2jr0oy6h40gp5yqck49djo9wh&st=awnz4exs&dl=1"},
    {"name": "Raftar 🚀",  "url": "https://www.dropbox.com/scl/fi/4at6eq4nxvgrp1exbilm5/e2b3f94bdbdd489c8d013d9bb259d4c4_0_1768292038_1500.png?rlkey=3m080rz9psgpx0ik4v10vfeqy&st=rdoo5aav&dl=1"},
    {"name": "Bijli ⚡",   "url": "https://www.dropbox.com/scl/fi/5mxn0hancsdixl8o8qxv9/file_000000006d7871fdaee7d2e8f89d10ac.png?rlkey=tit3yzcn0dobpjy2p7g1hhr0z&st=7xyenect&dl=1"},
    {"name": "Chetak 🐎",  "url": "https://www.dropbox.com/scl/fi/hvzez76rm1db5c0efxvt8/file_0000000027e47230b3f8471ac00250a3.png?rlkey=d8hu6l9movcicvr4irrqtdxnt&st=zicoegnf&dl=1"},
    {"name": "Toofan 🌪️",  "url": "https://www.dropbox.com/scl/fi/xrkby1kkak8ckxx75iixg/file_0000000086c871f8905c8f0de54f17dc.png?rlkey=nx91tgxbd3zcf60xtk7l6yqvj&st=2gj0n5lf&dl=1"},
    {"name": "Sultan 👑",  "url": "https://www.dropbox.com/scl/fi/ce2yjpv915e5t67vmq9bj/LS20260113135259.png?rlkey=rwy1sqp4jowpir8svpl89ew3g&st=n6wfjn7z&dl=1"}
]

# Game Settings
FINISH_LINE = 40  # Total steps to win
GAME_LOCK = threading.Lock()
ACTIVE_GAMES = {} # {room_id: GameState}
CACHED_IMAGES = {} # Cache for downloaded horse PNGs

# --- UTILS: IMAGE LOADER ---
def get_horse_image(index):
    """Downloads and caches horse images from Dropbox"""
    url = HORSES_CONFIG[index]["url"]
    if url not in CACHED_IMAGES:
        try:
            # print(f"Downloading horse {index}...") # Debug
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
                img = img.resize((50, 50)) # Resize to fit board block
                CACHED_IMAGES[url] = img
            else:
                print(f"[Error] Failed to load horse {index}")
                return None
        except Exception as e:
            print(f"[Error] Image load exception: {e}")
            return None
    return CACHED_IMAGES.get(url)

# --- BOARD MAPPING (The Snake Path) ---
def get_coordinates(step):
    """
    Maps a step number (0-40) to (x, y) pixels on 800x500 canvas.
    Pattern: Snake (Zig-Zag)
    """
    start_x, start_y = 60, 80
    gap_x = 70 
    gap_y = 100
    
    # Row 1: Left -> Right (Steps 0-9)
    if step < 10:
        return (start_x + (step * gap_x), start_y)
    
    # Turn 1: Down
    elif step == 10:
        return (start_x + (9 * gap_x), start_y + (gap_y * 0.5))
        
    # Row 2: Right -> Left (Steps 11-19)
    elif step < 20:
        rel_step = step - 11
        return (start_x + (9 * gap_x) - (rel_step * gap_x), start_y + gap_y)
        
    # Turn 2: Down
    elif step == 20:
         return (start_x, start_y + (gap_y * 1.5))
         
    # Row 3: Left -> Right (Steps 21-29)
    elif step < 30:
        rel_step = step - 21
        return (start_x + (rel_step * gap_x), start_y + (2 * gap_y))
        
    # Turn 3: Down
    elif step == 30:
        return (start_x + (9 * gap_x), start_y + (gap_y * 2.5))
        
    # Row 4: Right -> Left (Steps 31-40)
    else:
        rel_step = step - 31
        return (start_x + (9 * gap_x) - (rel_step * gap_x), start_y + (3 * gap_y))

def generate_board_image(players, game_msg=""):
    """Draws the race track and places horses."""
    width, height = 800, 500
    
    # 1. Create Green Board (Grass)
    bg = Image.new('RGB', (width, height), (34, 100, 34))
    draw = ImageDraw.Draw(bg)
    
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30)
    except:
        font = ImageFont.load_default()
        title_font = ImageFont.load_default()

    # 2. Draw Track Boxes
    for i in range(FINISH_LINE + 1):
        x, y = get_coordinates(i)
        # Draw Tile
        color = "white" if i % 2 == 0 else "#ddd"
        if i == 0: color = "#FFFF00" # Start Yellow
        if i == FINISH_LINE: color = "#FF0000" # End Red
        
        draw.rectangle([x-25, y-25, x+25, y+25], fill=color, outline="black")
        
        # Number
        draw.text((x-5, y-5), str(i), fill="black", font=font if i%5==0 else None)

    # 3. Place Horses (Stacking logic included)
    # We group horses by step to handle overlapping
    step_map = {}
    for p in players:
        s = p['pos']
        if s not in step_map: step_map[s] = []
        step_map[s].append(p)

    for step, p_list in step_map.items():
        base_x, base_y = get_coordinates(step)
        
        # If multiple horses on same block, offset them slightly
        count = 0
        for p in p_list:
            h_img = get_horse_image(p['horse_idx'])
            if h_img:
                # Slight offset based on count to prevent total hiding
                off_x = (count % 2) * 10 - 5
                off_y = (count // 2) * 10 - 5
                
                paste_pos = (int(base_x - 25 + off_x), int(base_y - 25 + off_y))
                bg.paste(h_img, paste_pos, h_img)
                count += 1

    # 4. Draw Header
    draw.text((400, 30), "🐎 HOWDIES GRAND PRIX 🐎", fill="yellow", font=title_font, anchor="mm")
    if game_msg:
        draw.text((400, 470), game_msg, fill="white", font=font, anchor="mm")

    # 5. Output
    output = io.BytesIO()
    bg.save(output, format='PNG')
    output.seek(0)
    return output

# --- GAME LOGIC CLASS ---
class LudoGame:
    def __init__(self, host_id, mode):
        self.host_id = host_id
        self.mode = mode # '1' (Single) or '2' (Multi)
        self.state = 'waiting' # waiting, playing
        self.players = [] 
        self.turn_idx = 0
        # Available horse indices [0,1,2,3,4,5] shuffled
        self.deck = list(range(6))
        random.shuffle(self.deck)

    def add_player(self, uid, name):
        if not self.deck: return None
        h_idx = self.deck.pop(0)
        self.players.append({
            "uid": uid, "name": name, "horse_idx": h_idx, "pos": 0
        })
        return h_idx

    def get_current_player(self):
        return self.players[self.turn_idx]

    def next_turn(self):
        self.turn_idx = (self.turn_idx + 1) % len(self.players)
        return self.players[self.turn_idx]

# --- COMMAND HANDLER ---
def handle_command(bot, command, room_id, user, args, data):
    user_id = data.get('userid', user)

    # --- 1. START NEW GAME ---
    if command == "race":
        mode = args[0] if args else "1"
        
        with GAME_LOCK:
            if room_id in ACTIVE_GAMES:
                bot.send_message(room_id, "⚠️ Race already running here!")
                return True
            
            game = LudoGame(user_id, mode)
            
            # Add Host
            h = game.add_player(user_id, user)
            h_name = HORSES_CONFIG[h]["name"]
            
            if mode == "1":
                # Single Player vs Bot
                game.add_player("BOT", "Computer 🤖")
                game.state = 'playing'
                ACTIVE_GAMES[room_id] = game
                
                bot.send_message(room_id, f"⚔️ **1v1 Race Started!**\n@{user} ({h_name}) VS Computer.\nTarget: {FINISH_LINE} steps.\n\n👉 Type `!roll` to move!")
            else:
                # Multiplayer Lobby
                ACTIVE_GAMES[room_id] = game
                bot.send_message(room_id, f"🏆 **Lobby Open!**\nHost: @{user} ({h_name})\n\nOthers type `!join`\nHost type `!start` when ready.")
        return True

    # --- 2. JOIN GAME ---
    if command == "join":
        with GAME_LOCK:
            game = ACTIVE_GAMES.get(room_id)
            if not game or game.mode != "2" or game.state != "waiting":
                bot.send_message(room_id, "No open lobby.")
                return True
            
            # Check dupes
            if any(p['uid'] == user_id for p in game.players):
                bot.send_message(room_id, "You already joined.")
                return True
            
            if len(game.players) >= 6:
                bot.send_message(room_id, "Lobby Full (6/6).")
                return True

            h = game.add_player(user_id, user)
            h_name = HORSES_CONFIG[h]["name"]
            bot.send_message(room_id, f"✅ @{user} joined with **{h_name}**")
        return True

    # --- 3. START MULTIPLAYER ---
    if command == "start":
        with GAME_LOCK:
            game = ACTIVE_GAMES.get(room_id)
            if not game or game.state != "waiting": return True
            if game.host_id != user_id:
                bot.send_message(room_id, "Only Host can start.")
                return True
            if len(game.players) < 2:
                bot.send_message(room_id, "Need 2+ players.")
                return True
            
            game.state = 'playing'
            p1 = game.get_current_player()
            bot.send_message(room_id, f"🚦 **RACE STARTED!** 🚦\nFirst Turn: @{p1['name']}\nType `!roll`")
        return True

    # --- 4. ROLL DICE ---
    if command == "roll":
        # Pre-check without lock to save resources
        if room_id not in ACTIVE_GAMES: return False

        with GAME_LOCK:
            game = ACTIVE_GAMES[room_id]
            if game.state != 'playing': return True
            
            curr = game.get_current_player()
            
            # Turn Validation
            if curr['uid'] == "BOT" and user_id != "BOT":
                # Ignore user input during bot turn
                return True
            
            if curr['uid'] != user_id and curr['uid'] != "BOT":
                bot.send_message(room_id, f"Wait! It's @{curr['name']}'s turn.")
                return True

            # -- Execute Logic --
            dice = random.randint(1, 6)
            old_pos = curr['pos']
            new_pos = old_pos + dice
            curr['pos'] = new_pos
            
            msg_text = f"🎲 @{curr['name']} rolled **{dice}**! (Step {new_pos})"
            
            # Check Win
            if new_pos >= FINISH_LINE:
                curr['pos'] = FINISH_LINE # Cap visuals
                win_msg = f"🎉🏆 **{curr['name']} WINS THE RACE!** 🏆🎉"
                bot.send_message(room_id, win_msg)
                
                # Final Board
                # NOTE: Replace with actual upload logic if available
                # img_bytes = generate_board_image(game.players, f"WINNER: {curr['name']}")
                # bot.upload_and_send(img_bytes) 
                
                del ACTIVE_GAMES[room_id]
                return True

            # Send Update
            bot.send_message(room_id, msg_text)
            
            # --- NEXT TURN ---
            next_p = game.next_turn()
            
            # IF Next is BOT, Trigger Auto-Roll
            if next_p['uid'] == "BOT":
                bot.send_message(room_id, "🤖 Bot is rolling...")
                # Run in separate thread to not block
                def bot_move():
                    time.sleep(2) # Thinking time
                    handle_command(bot, "roll", room_id, "BOT", [], {})
                
                threading.Thread(target=bot_move).start()
            else:
                bot.send_message(room_id, f"👉 @{next_p['name']}'s turn. Type `!roll`")
                
        return True

    return False
