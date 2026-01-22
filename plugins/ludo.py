import time
import random
import threading
from PIL import Image, ImageDraw

# --- IMPORTS ---
try: import utils
except ImportError: print("[Ludo] Error: utils.py not found!")

try: from db import add_game_result
except: print("[Ludo] DB Error")

# --- GLOBAL VARIABLES ---
games = {}
game_lock = threading.Lock()
BOT_INSTANCE = None # To send messages from background thread

# --- CONSTANTS ---
THEMES = {
    'R': {'name': 'Red', 'hex': '#FF3333', 'icon': "https://img.icons8.com/3d-fluency/94/iron-man.png"},
    'G': {'name': 'Green', 'hex': '#33FF33', 'icon': "https://img.icons8.com/3d-fluency/94/hulk.png"},
    'Y': {'name': 'Yellow', 'hex': '#FFD700', 'icon': "https://img.icons8.com/3d-fluency/94/pikachu-pokemon.png"},
    'B': {'name': 'Blue', 'hex': '#3388FF', 'icon': "https://img.icons8.com/3d-fluency/94/captain-america.png"}
}

def setup(bot):
    global BOT_INSTANCE
    BOT_INSTANCE = bot
    # Start Cleanup Thread
    threading.Thread(target=game_cleanup_loop, daemon=True).start()
    print("[Ludo] Pro Edition (Auto-Mod) Loaded.")

# ==========================================
# 🕒 AUTOMATIC CLEANUP & TIMEOUT SYSTEM
# ==========================================

def game_cleanup_loop():
    while True:
        time.sleep(5) # Check every 5 seconds
        if not games: continue
        
        now = time.time()
        to_delete = []
        
        with game_lock:
            for rid, g in games.items():
                if g.state == 'lobby':
                    # Lobby Timeout (2 mins)
                    if now - g.created_at > 120:
                        if BOT_INSTANCE: BOT_INSTANCE.send_message(rid, "⏳ **Lobby Expired.**")
                        to_delete.append(rid)
                    continue

                # 1. Game Inactivity (90s)
                if now - g.last_interaction > 90:
                    if BOT_INSTANCE: BOT_INSTANCE.send_message(rid, "💤 **Game Dead!** Closed due to inactivity.")
                    # Host Penalty logic can be added here
                    to_delete.append(rid)
                    continue
                
                # 2. Player Timeout (45s)
                curr_uid, curr_p = g.get_current_player()
                if curr_uid and (now - g.turn_start_time > 45):
                    # KICK PLAYER
                    p_name = curr_p['name']
                    if BOT_INSTANCE: BOT_INSTANCE.send_message(rid, f"⏱️ **@{p_name}** slept! Eliminated (-200 Coins).")
                    
                    # Penalty
                    add_game_result(curr_uid, p_name, "ludo_penalty", -200, False)
                    
                    # Remove from turn list
                    g.turn_list.remove(curr_uid)
                    
                    # Check if game ends (Only 1 player left)
                    if len(g.turn_list) < 2:
                        winner_uid = g.turn_list[0]
                        winner_name = g.players[winner_uid]['name']
                        reward = g.bet * len(g.players)
                        add_game_result(winner_uid, winner_name, "ludo", reward, True)
                        if BOT_INSTANCE: BOT_INSTANCE.send_message(rid, f"🏆 **@{winner_name} Wins** by default!")
                        to_delete.append(rid)
                    else:
                        # Next Turn
                        if g.turn_index >= len(g.turn_list): g.turn_index = 0
                        g.turn_start_time = time.time()
                        g.last_interaction = time.time()
                        
                        # Notify next player
                        n_uid, n_p = g.get_current_player()
                        if BOT_INSTANCE: BOT_INSTANCE.send_message(rid, f"👉 **@{n_p['name']}'s** Turn")

        for rid in to_delete:
            if rid in games: del games[rid]

# ==========================================
# 🎨 GRAPHICS ENGINE (AVATAR SUPPORT)
# ==========================================

def get_pixel_coords(step, color, cell_size, margin_x, margin_y):
    # Same simplified mapping as before for 15x15 grid
    # 0-indexed from Red Start (1, 13)
    COORDS_52 = [
        (1,13),(2,13),(3,13),(4,13),(5,13), (6,12),(6,11),(6,10),(6,9),(6,8), (6,7), # 0-10
        (5,7),(4,7),(3,7),(2,7),(1,7),(0,7), (0,6),(0,5), # 11-18 (Turn TopLeft)
        (1,5),(2,5),(3,5),(4,5),(5,5), (6,5), (6,4),(6,3),(6,2),(6,1),(6,0), # 19-29
        (7,0),(8,0), # 30-31 (Turn TopRight)
        (8,1),(8,2),(8,3),(8,4),(8,5), (8,6), (9,6),(10,6),(11,6),(12,6),(13,6),(14,6), # 32-43
        (14,7),(14,8), # 44-45 (Turn BottomRight)
        (13,8),(12,8),(11,8),(10,8),(9,8), (8,8), (8,9),(8,10),(8,11),(8,12),(8,13) # 46-51
    ]
    
    offset = 0
    if color == 'G': offset = 13
    elif color == 'Y': offset = 26
    elif color == 'B': offset = 39
    
    if step == -1: # Home Base
        if color == 'R': return margin_x + 2.5*cell_size, margin_y + 11.5*cell_size
        if color == 'G': return margin_x + 2.5*cell_size, margin_y + 2.5*cell_size
        if color == 'Y': return margin_x + 11.5*cell_size, margin_y + 2.5*cell_size
        if color == 'B': return margin_x + 11.5*cell_size, margin_y + 11.5*cell_size
        
    if step < 51:
        idx = (step + offset) % 52
        c, r = COORDS_52[idx] if idx < len(COORDS_52) else (7,7)
    else:
        # Home Run
        dist = step - 51
        if color == 'R': c, r = 7, 13 - dist
        elif color == 'G': c, r = 1 + dist, 7
        elif color == 'Y': c, r = 7, 1 + dist
        elif color == 'B': c, r = 13 - dist, 7
        if step >= 56: c, r = 7, 7 # Center
        
    x = margin_x + (c * cell_size) + (cell_size // 2)
    y = margin_y + (r * cell_size) + (cell_size // 2)
    return x, y

def draw_ludo_board_hd(players, dice_val=None, rolling=False):
    SZ = 50; W, H = SZ * 15 + 40, SZ * 15 + 40
    img = utils.create_canvas(W, H, "#F5F5F5")
    d = ImageDraw.Draw(img)
    mx, my = 20, 20
    
    # 1. DRAW BOARD BASE (Simplified for brevity, same as before)
    # Homes
    d.rectangle([mx, my, mx+6*SZ, my+6*SZ], fill=THEMES['G']['hex'], outline="black", width=2) # Green
    d.rectangle([mx+9*SZ, my, mx+15*SZ, my+6*SZ], fill=THEMES['Y']['hex'], outline="black", width=2) # Yellow
    d.rectangle([mx, my+9*SZ, mx+6*SZ, my+15*SZ], fill=THEMES['R']['hex'], outline="black", width=2) # Red
    d.rectangle([mx+9*SZ, my+9*SZ, mx+15*SZ, my+15*SZ], fill=THEMES['B']['hex'], outline="black", width=2) # Blue
    # Inner Whites
    d.rectangle([mx+SZ, my+SZ, mx+5*SZ, my+5*SZ], fill="white", outline="black")
    d.rectangle([mx+10*SZ, my+SZ, mx+14*SZ, my+5*SZ], fill="white", outline="black")
    d.rectangle([mx+SZ, my+10*SZ, mx+5*SZ, my+14*SZ], fill="white", outline="black")
    d.rectangle([mx+10*SZ, my+10*SZ, mx+14*SZ, my+14*SZ], fill="white", outline="black")

    # Tracks
    for r in range(15):
        for c in range(15):
            is_track = False
            fill = "white"
            if (6 <= r <= 8) or (6 <= c <= 8): is_track = True
            if (6 <= r <= 8) and (6 <= c <= 8): is_track = False # Center exclusion for now
            
            if is_track:
                x, y = mx + c*SZ, my + r*SZ
                # Colored Paths
                if r==7 and 1<=c<=5: fill=THEMES['G']['hex']
                if r==7 and 9<=c<=13: fill=THEMES['B']['hex']
                if c==7 and 1<=r<=5: fill=THEMES['Y']['hex']
                if c==7 and 9<=r<=13: fill=THEMES['R']['hex']
                d.rectangle([x, y, x+SZ, y+SZ], fill=fill, outline="black", width=1)
                
    # Center
    cx, cy = mx + 7.5*SZ, my + 7.5*SZ
    d.polygon([(mx+6*SZ, my+6*SZ), (mx+9*SZ, my+6*SZ), (cx, cy)], fill=THEMES['Y']['hex'], outline="black")
    d.polygon([(mx+9*SZ, my+6*SZ), (mx+9*SZ, my+9*SZ), (cx, cy)], fill=THEMES['B']['hex'], outline="black")
    d.polygon([(mx+9*SZ, my+9*SZ), (mx+6*SZ, my+9*SZ), (cx, cy)], fill=THEMES['R']['hex'], outline="black")
    d.polygon([(mx+6*SZ, my+9*SZ), (mx+6*SZ, my+6*SZ), (cx, cy)], fill=THEMES['G']['hex'], outline="black")

    # 2. DRAW TOKENS (WITH AVATAR)
    for uid, p in players.items():
        step = p['step']
        color = p['color']
        px, py = get_pixel_coords(step, color, SZ, mx, my)
        
        # Shadow
        d.ellipse([px-18, py+12, px+18, py+20], fill=(0,0,0,50))
        
        # Priority: Avatar > Cartoon
        av_img = None
        if p.get('avatar_url'):
            av_img = utils.get_circle_avatar(p['avatar_url'], size=44)
        
        if av_img:
            # Add Colored Border to Avatar
            border_col = THEMES[color]['hex']
            bg = Image.new('RGBA', (48, 48), (0,0,0,0))
            bd = ImageDraw.Draw(bg)
            bd.ellipse([0, 0, 48, 48], fill=border_col)
            bg.paste(av_img, (2, 2), av_img)
            img.paste(bg, (int(px-24), int(py-24)), bg)
        else:
            # Fallback Cartoon
            icon_url = THEMES[color]['icon']
            icon_img = utils.get_image(icon_url)
            if icon_img:
                icon_img = icon_img.resize((44, 44))
                img.paste(icon_img, (int(px-22), int(py-22)), icon_img)
            else:
                d.ellipse([px-20, py-20, px+20, py+20], fill=THEMES[color]['hex'], outline="black", width=2)
                
        # Name Tag Bubble
        name_txt = p['name'][:6]
        bx, by = px, py - 38
        d.rounded_rectangle([bx-30, by-12, bx+30, by+8], radius=6, fill="white", outline="black", width=1)
        utils.write_text(d, (bx, by-2), name_txt, size=13, align="center", col="black", shadow=False)

    # 3. DICE OVERLAY
    if rolling:
        ov = Image.new('RGBA', (W, H), (0,0,0,80))
        img.paste(ov, (0,0), ov)
        utils.write_text(d, (W//2, H//2), "🎲 ROLLING...", size=60, align="center", col="white", shadow=True)
    elif dice_val:
        # Result Card
        d.rounded_rectangle([W//2-40, H//2-40, W//2+40, H//2+40], radius=10, fill="white", outline="#FFD700", width=4)
        dice_url = f"https://img.icons8.com/3d-fluency/94/{dice_val}-circle.png"
        dimg = utils.get_image(dice_url)
        if dimg:
            dimg = dimg.resize((70, 70))
            img.paste(dimg, (int(W//2-35), int(H//2-35)), dimg)
        else:
            utils.write_text(d, (W//2, H//2), str(dice_val), size=40, align="center", col="black")

    return img

# ==========================================
# ⚙️ LOGIC
# ==========================================

class LudoGame:
    def __init__(self, room_id, bet, creator_id):
        self.room_id = room_id
        self.bet = bet
        self.creator_id = creator_id
        self.players = {}
        self.state = 'lobby'
        self.colors = ['R', 'G', 'Y', 'B']
        self.turn_list = []
        self.turn_index = 0
        
        # Timestamps for Auto-Mod
        self.created_at = time.time()
        self.last_interaction = time.time()
        self.turn_start_time = time.time()

    def add_player(self, uid, name, avatar_url=None):
        if not self.colors: return False
        col = self.colors.pop(0)
        self.players[str(uid)] = {
            'name': name, 'color': col, 'step': -1, 'avatar_url': avatar_url
        }
        self.last_interaction = time.time()
        return True

    def get_current_player(self):
        if not self.turn_list: return None, None
        uid = self.turn_list[self.turn_index]
        return uid, self.players[uid]

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    uid = data.get('userid', user)
    
    # 🛑 BOT SELF-JOIN PREVENTION
    if str(uid) == str(bot.user_id): return False
    
    global games
    
    # 1. CREATE
    if cmd == "ludo":
        bet = 0
        if args and args[0].isdigit(): bet = int(args[0])
        
        with game_lock:
            if room_id in games: return True
            g = LudoGame(room_id, bet, uid)
            
            # Fetch Avatar from Data
            av_file = data.get("avatar")
            av_url = f"https://cdn.howdies.app/avatar?image={av_file}" if av_file else None
            
            g.add_player(uid, user, av_url)
            if bet > 0: add_game_result(uid, user, "ludo", -bet, False)
            games[room_id] = g
            
        img = draw_ludo_board_hd(g.players)
        link = utils.upload(bot, img)
        bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Lobby"})
        bot.send_message(room_id, f"🎲 **Ludo Lobby!** Bet: {bet}\nType `!join`")
        return True

    # 2. JOIN
    if cmd == "join":
        with game_lock:
            g = games.get(room_id)
            if not g or g.state != 'lobby': return False
            if str(uid) in g.players: return True
            
            av_file = data.get("avatar")
            av_url = f"https://cdn.howdies.app/avatar?image={av_file}" if av_file else None
            
            if g.add_player(uid, user, av_url):
                if g.bet > 0: add_game_result(uid, user, "ludo", -g.bet, False)
                bot.send_message(room_id, f"✅ **{user}** joined!")
                img = draw_ludo_board_hd(g.players)
                link = utils.upload(bot, img)
                bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Join"})
            else:
                bot.send_message(room_id, "Full!")
        return True

    # 3. START
    if cmd == "start":
        with game_lock:
            g = games.get(room_id)
            if not g: return False
            if len(g.players) < 2:
                bot.send_message(room_id, "Need 2+ Players.")
                return True
            g.state = 'playing'
            g.turn_list = list(g.players.keys())
            g.turn_start_time = time.time()
            bot.send_message(room_id, "🔥 **Game Started!**")
        return True

    # 4. ROLL
    if cmd == "roll":
        with game_lock:
            g = games.get(room_id)
            if not g or g.state != 'playing': return False
            
            curr_uid, curr_p = g.get_current_player()
            if str(uid) != str(curr_uid): return True
            
            # Update Timestamps
            g.last_interaction = time.time()
            
            # Rolling FX
            roll_img = draw_ludo_board_hd(g.players, rolling=True)
            r_link = utils.upload(bot, roll_img)
            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": r_link, "text": "Roll"})
            
            time.sleep(1.5)
            
            dice = random.randint(1, 6)
            
            # Move Logic
            p = g.players[str(uid)]
            is_win = False
            msg = ""
            
            if p['step'] == -1:
                p['step'] = 0 # Start
                msg = "Entered Board!"
            else:
                new_step = p['step'] + dice
                if new_step >= 56:
                    p['step'] = 57
                    is_win = True
                    msg = "🏆 REACHED HOME!"
                elif new_step < 51:
                    # Cut Logic
                    for oid, op in g.players.items():
                        if oid != str(uid) and op['step'] == new_step:
                            op['step'] = -1
                            msg = f"\n⚔️ **KILLED {op['name']}!**"
                    p['step'] = new_step
                else:
                    p['step'] = new_step
            
            # Final Image
            final_img = draw_ludo_board_hd(g.players, dice_val=dice)
            f_link = utils.upload(bot, final_img)
            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": f_link, "text": f"Dice {dice}"})
            bot.send_message(room_id, f"🎲 **{curr_p['name']}** rolled {dice}! {msg}")
            
            if is_win:
                reward = g.bet * len(g.players)
                add_game_result(uid, user, "ludo", reward, True)
                bot.send_message(room_id, f"🎉 **{user} WINS!** +{reward} Coins")
                del games[room_id]
                return True
            
            if dice != 6:
                g.turn_index = (g.turn_index + 1) % len(g.turn_list)
            else:
                bot.send_message(room_id, "🎉 **Bonus Turn!**")
            
            g.turn_start_time = time.time() # Reset Turn Timer
            n_uid, n_p = g.get_current_player()
            bot.send_message(room_id, f"👉 **@{n_p['name']}'s** Turn")
            
        return True

    # 5. STOP (!stop) - Only Creator/Admin
    if cmd == "stop":
        with game_lock:
            g = games.get(room_id)
            if not g: return False
            if str(uid) == str(g.creator_id) or str(uid) in ["ADMIN_ID_HERE"]: # Add Admin ID if needed
                del games[room_id]
                bot.send_message(room_id, "🛑 Game Force Stopped.")
            else:
                bot.send_message(room_id, "❌ Only Host can stop.")
        return True

    return False
