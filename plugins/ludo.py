import time
import random
import threading
from PIL import Image, ImageDraw, ImageFont

# --- IMPORTS ---
try: import utils
except ImportError: print("[Ludo] Error: utils.py not found!")

try: from db import add_game_result
except: print("[Ludo] DB Error")

# --- GLOBAL VARIABLES ---
games = {}
game_lock = threading.Lock()
BOT_INSTANCE = None 

# --- ASSETS & CONFIG ---
THEMES = {
    'R': {'name': 'Red', 'hex': '#FF3333', 'bg': '#FFEEEE', 'icon': "https://img.icons8.com/3d-fluency/94/iron-man.png"},
    'G': {'name': 'Green', 'hex': '#33FF33', 'bg': '#EEFFEE', 'icon': "https://img.icons8.com/3d-fluency/94/hulk.png"},
    'Y': {'name': 'Yellow', 'hex': '#FFD700', 'bg': '#FFFFEE', 'icon': "https://img.icons8.com/3d-fluency/94/pikachu-pokemon.png"},
    'B': {'name': 'Blue', 'hex': '#3388FF', 'bg': '#EEEEFF', 'icon': "https://img.icons8.com/3d-fluency/94/captain-america.png"}
}
CROWN_ICON = "https://img.icons8.com/emoji/96/crown-emoji.png"

def setup(bot):
    global BOT_INSTANCE
    BOT_INSTANCE = bot
    threading.Thread(target=game_cleanup_loop, daemon=True).start()
    print("[Ludo] Ultimate Avatar Edition Loaded.")

# ==========================================
# 🕒 AUTO MOD
# ==========================================
def game_cleanup_loop():
    while True:
        time.sleep(5)
        if not games: continue
        now = time.time()
        to_delete = []
        with game_lock:
            for rid, g in games.items():
                if g.state == 'lobby' and now - g.created_at > 180:
                    if BOT_INSTANCE: BOT_INSTANCE.send_message(rid, "⏳ **Lobby Timeout!**")
                    to_delete.append(rid); continue
                if now - g.last_interaction > 90:
                    if BOT_INSTANCE: BOT_INSTANCE.send_message(rid, "💤 **Game Dead!** (-100 Penalty)")
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
# 📍 PERFECT COORDINATE MAPPING (15x15)
# ==========================================
def get_coordinates(step, color, sz, mx, my):
    # 52 Steps Loop (0-Indexed from Red Start (1,13))
    # Corrected Manual Map for 15x15 Grid
    P = [
        (1,13),(2,13),(3,13),(4,13),(5,13), # 0-4 (Red Straight)
        (6,12),(6,11),(6,10),(6,9),(6,8),   # 5-9 (Up)
        (6,7),                              # 10 (Towards Center - Stop) -> Actually Standard Ludo goes to (5,8) next
        # FIX: Standard path: (6,8) -> (5,8) -> (4,8)...
    ]
    # Let's use the verified relative calculation
    # Red Start (1, 13)
    
    # 0-50 Path (52 steps)
    PATH_52 = [
        (1,13),(2,13),(3,13),(4,13),(5,13), (6,12),(6,11),(6,10),(6,9),(6,8), (6,7), # 0-10
        (5,7),(4,7),(3,7),(2,7),(1,7),(0,7), (0,6),(0,5), # 11-18
        (1,5),(2,5),(3,5),(4,5),(5,5), (6,5), (6,4),(6,3),(6,2),(6,1),(6,0), # 19-29
        (7,0),(8,0), # 30-31
        (8,1),(8,2),(8,3),(8,4),(8,5), (8,6), (9,6),(10,6),(11,6),(12,6),(13,6),(14,6), # 32-43
        (14,7),(14,8), # 44-45
        (13,8),(12,8),(11,8),(10,8),(9,8), (8,8), (8,9),(8,10),(8,11) # 46-51
    ]
    
    offset = 0
    if color == 'G': offset = 13
    elif color == 'Y': offset = 26
    elif color == 'B': offset = 39
    
    c, r = 0, 0
    
    if step == -1: # Home Base Center
        if color == 'R': c, r = 2.5, 11.5 # Adjusted for visuals (Not exact grid)
        if color == 'G': c, r = 2.5, 2.5
        if color == 'Y': c, r = 11.5, 2.5
        if color == 'B': c, r = 11.5, 11.5
        # Return exact pixels for Home
        return mx + c*sz + sz//2, my + r*sz + sz//2

    elif step >= 51: # Home Run
        dist = step - 51
        if color == 'R': c, r = 1 + dist, 7
        elif color == 'G': c, r = 7, 1 + dist
        elif color == 'Y': c, r = 13 - dist, 7
        elif color == 'B': c, r = 7, 13 - dist
        if step >= 56: c, r = 7, 7 # Center
    else:
        # Normal Track
        idx = (step + offset) % 52
        if idx < len(PATH_52):
            c, r = PATH_52[idx]
        else:
            c, r = 7, 7 # Fallback

    # Pixel conversion (Center of the cell)
    x = mx + (c * sz) + (sz // 2)
    y = my + (r * sz) + (sz // 2)
    return x, y

# ==========================================
# 🎨 GRAPHICS ENGINE (AVATARS + LEADER)
# ==========================================

def draw_ludo_board_hd(players, dice_val=None, rolling=False):
    SZ = 50
    W, H = SZ * 15 + 40, SZ * 15 + 40
    img = utils.create_canvas(W, H, "#E0E0E0")
    d = ImageDraw.Draw(img)
    mx, my = 20, 20
    
    # --- 1. DRAW HOMES (WITH BIG AVATAR) ---
    homes = [
        ('G', 0, 0, 6, 6), ('Y', 9, 0, 15, 6),
        ('R', 0, 9, 6, 15), ('B', 9, 9, 15, 15)
    ]
    
    for code, c1, r1, c2, r2 in homes:
        # Outer Box
        x1, y1 = mx+c1*SZ, my+r1*SZ
        x2, y2 = mx+c2*SZ, my+r2*SZ
        d.rectangle([x1, y1, x2, y2], fill=THEMES[code]['hex'], outline="black", width=2)
        # Inner White
        d.rectangle([x1+SZ, y1+SZ, x2-SZ, y2-SZ], fill="white", outline="black")
        
        # FIND PLAYER OWNER
        owner_p = None
        for p in players.values():
            if p['color'] == code: owner_p = p; break
            
        # DRAW BIG AVATAR IN HOME
        center_hx, center_hy = (x1+x2)//2, (y1+y2)//2
        if owner_p and owner_p.get('avatar_url'):
            big_av = utils.get_circle_avatar(owner_p['avatar_url'], size=120)
            if big_av:
                # Add Glow
                bg = Image.new('RGBA', (130, 130), (0,0,0,0))
                ImageDraw.Draw(bg).ellipse([0,0,130,130], fill=THEMES[code]['hex'])
                bg.paste(big_av, (5,5), big_av)
                img.paste(bg, (int(center_hx-65), int(center_hy-65)), bg)
                
                # Username Label
                d.rounded_rectangle([center_hx-60, center_hy+60, center_hx+60, center_hy+85], radius=10, fill="black")
                utils.write_text(d, (center_hx, center_hy+62), owner_p['name'][:10], size=16, align="center", col="white")
        else:
            # Fallback Icon
            icon_img = utils.get_image(THEMES[code]['icon'])
            if icon_img:
                icon_img = icon_img.resize((100, 100))
                img.paste(icon_img, (int(center_hx-50), int(center_hy-50)), icon_img)

    # --- 2. DRAW TRACKS ---
    for r in range(15):
        for c in range(15):
            if not ((6 <= r <= 8) or (6 <= c <= 8)): continue # Skip non-track
            if (6 <= r <= 8) and (6 <= c <= 8): continue # Skip Center
            
            x, y = mx+c*SZ, my+r*SZ
            fill = "white"
            # Colored Home Runs
            if r==7 and 1<=c<=5: fill=THEMES['R']['hex']
            if r==7 and 9<=c<=13: fill=THEMES['Y']['hex']
            if c==7 and 1<=r<=5: fill=THEMES['G']['hex']
            if c==7 and 9<=r<=13: fill=THEMES['B']['hex']
            # Safe Spots (Grey)
            if (c,r) in [(1,13),(6,2),(13,1),(8,12), (2,6),(6,12),(12,8),(8,2)]: fill = "#DDDDDD" 
            if fill != "white" and fill != "#DDDDDD": pass # Keep colored
            
            d.rectangle([x, y, x+SZ, y+SZ], fill=fill, outline="#555", width=1)

    # Center Win Zone
    cx, cy = mx + 7.5*SZ, my + 7.5*SZ
    d.polygon([(mx+6*SZ, my+6*SZ), (mx+9*SZ, my+6*SZ), (cx, cy)], fill=THEMES['G']['hex'], outline="black")
    d.polygon([(mx+9*SZ, my+6*SZ), (mx+9*SZ, my+9*SZ), (cx, cy)], fill=THEMES['Y']['hex'], outline="black")
    d.polygon([(mx+9*SZ, my+9*SZ), (mx+6*SZ, my+9*SZ), (cx, cy)], fill=THEMES['B']['hex'], outline="black")
    d.polygon([(mx+6*SZ, my+9*SZ), (mx+6*SZ, my+6*SZ), (cx, cy)], fill=THEMES['R']['hex'], outline="black")

    # --- 3. CALCULATE LEADER ---
    max_step = -1
    leader_uid = None
    for uid, p in players.items():
        if p['step'] > max_step and p['step'] > 0: # Only if left base
            max_step = p['step']
            leader_uid = uid
    # Handle Draw (No leader if multiple same max)
    same_count = 0
    for p in players.values():
        if p['step'] == max_step: same_count += 1
    if same_count > 1: leader_uid = None

    # --- 4. DRAW TOKENS ---
    for uid, p in players.items():
        step = p['step']
        # If at home base (-1), we already drew the big avatar. 
        # But user requested "bids par" (lobby) and board. 
        # During game, if step is -1, usually we show token in start box.
        # But since we drew Big Avatar, let's skip drawing Small Token at -1 
        # UNLESS it's the only representation. 
        # Let's draw Small Token ALWAYS for clarity, inside the Start Spot (Colored Box).
        
        px, py = get_coordinates(step, p['color'], SZ, mx, my)
        
        # Token Size
        tsz = 44
        
        # Shadow
        d.ellipse([px-18, py+12, px+18, py+20], fill=(0,0,0,60))
        
        # Avatar
        av_img = None
        if p.get('avatar_url'):
            av_img = utils.get_circle_avatar(p['avatar_url'], size=tsz)
        
        if av_img:
            # Border
            bg = Image.new('RGBA', (tsz+4, tsz+4), (0,0,0,0))
            ImageDraw.Draw(bg).ellipse([0,0,tsz+4,tsz+4], fill=THEMES[p['color']]['hex'])
            bg.paste(av_img, (2,2), av_img)
            img.paste(bg, (int(px-tsz/2-2), int(py-tsz/2-2)), bg)
        else:
            # Cartoon Fallback
            icon = utils.get_image(THEMES[p['color']]['icon'])
            if icon:
                icon = icon.resize((tsz, tsz))
                img.paste(icon, (int(px-tsz/2), int(py-tsz/2)), icon)
        
        # Name Bubble (Tiny)
        d.rounded_rectangle([px-20, py-32, px+20, py-18], radius=4, fill="white", outline="black")
        utils.write_text(d, (px, py-27), p['name'][:4], size=10, align="center", col="black")

        # --- LEADER EFFECT (#1 CROWN) ---
        if str(uid) == str(leader_uid):
            # Draw Crown
            crown = utils.get_image(CROWN_ICON)
            if crown:
                crown = crown.resize((30, 30))
                # Float above name
                img.paste(crown, (int(px-15), int(py-60)), crown)
            
            # #1 Badge
            d.ellipse([px+10, py+10, px+26, py+26], fill="#FFD700", outline="black", width=1)
            utils.write_text(d, (px+18, py+12), "1", size=12, align="center", col="black", shadow=False)

    # --- 5. DICE ---
    if rolling:
        ov = Image.new('RGBA', (W, H), (0,0,0,90))
        img.paste(ov, (0,0), ov)
        utils.write_text(d, (W//2, H//2), "🎲 ROLLING...", size=60, align="center", col="white", shadow=True)
    elif dice_val:
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
# ⚙️ GAME LOGIC
# ==========================================
class LudoGame:
    def __init__(self, room_id, bet, creator_id):
        self.room_id = room_id; self.bet = bet; self.creator_id = creator_id
        self.players = {}; self.state = 'lobby'; self.colors = ['R', 'G', 'Y', 'B']
        self.turn_list = []; self.turn_index = 0
        self.created_at = time.time(); self.last_interaction = time.time()
        self.turn_start_time = time.time()

    def add_player(self, uid, name, avatar_url):
        if not self.colors: return False
        col = self.colors.pop(0)
        self.players[str(uid)] = {'name': name, 'color': col, 'step': -1, 'avatar_url': avatar_url}
        self.last_interaction = time.time()
        return True

    def get_current_player(self):
        if not self.turn_list: return None, None
        uid = self.turn_list[self.turn_index]
        return uid, self.players[uid]

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    uid = data.get('userid', user)
    if str(uid) == str(bot.user_id): return False
    global games
    
    # FETCH AVATAR
    av_file = data.get("avatar")
    av_url = f"https://cdn.howdies.app/avatar?image={av_file}" if av_file else None

    # 1. LUDO
    if cmd == "ludo":
        bet = 0
        if args and args[0].isdigit(): bet = int(args[0])
        with game_lock:
            if room_id in games: return True
            g = LudoGame(room_id, bet, uid)
            g.add_player(uid, user, av_url)
            if bet > 0: add_game_result(uid, user, "ludo", -bet, False)
            games[room_id] = g
        img = draw_ludo_board_hd(g.players)
        link = utils.upload(bot, img)
        bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Lobby"})
        bot.send_message(room_id, f"🎲 **Ludo!** Bet: {bet}\nType `!join`")
        return True

    # 2. JOIN
    if cmd == "join":
        with game_lock:
            g = games.get(room_id)
            if not g or g.state != 'lobby': return False
            if str(uid) in g.players: return True
            if g.add_player(uid, user, av_url):
                if g.bet > 0: add_game_result(uid, user, "ludo", -g.bet, False)
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
            bot.send_message(room_id, "🔥 **Started!** First player `!roll`")
        return True

    # 4. ROLL
    if cmd == "roll":
        with game_lock:
            g = games.get(room_id)
            if not g or g.state != 'playing': return False
            c_uid, c_p = g.get_current_player()
            if str(uid) != str(c_uid): return True
            g.last_interaction = time.time()
            
            # Roll Visual
            r_img = draw_ludo_board_hd(g.players, rolling=True)
            r_link = utils.upload(bot, r_img)
            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": r_link, "text": "..."})
            time.sleep(1.5)
            
            dice = random.randint(1, 6)
            msg = ""; is_win = False
            p = g.players[str(uid)]
            
            if p['step'] == -1:
                p['step'] = 0; msg = "Go!"
            else:
                ns = p['step'] + dice
                if ns >= 56: p['step'] = 57; is_win = True
                elif ns < 51:
                    for oid, op in g.players.items():
                        if oid != str(uid) and op['step'] == ns:
                            op['step'] = -1; msg = f"⚔️ **Cut {op['name']}!**"
                    p['step'] = ns
                else: p['step'] = ns
                
            f_img = draw_ludo_board_hd(g.players, dice_val=dice)
            f_link = utils.upload(bot, f_img)
            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": f_link, "text": f"{dice}"})
            bot.send_message(room_id, f"🎲 **{c_p['name']}** rolled {dice}! {msg}")
            
            if is_win:
                rew = g.bet * len(g.players); add_game_result(uid, user, "ludo", rew, True)
                bot.send_message(room_id, f"🎉 **{user} WINS!**"); del games[room_id]; return True
            
            if dice != 6: g.turn_index = (g.turn_index + 1) % len(g.turn_list)
            g.turn_start_time = time.time()
            n_uid, n_p = g.get_current_player()
            bot.send_message(room_id, f"👉 **@{n_p['name']}'s** Turn")
        return True

    # 5. STOP
    if cmd == "stop":
        with game_lock:
            g = games.get(room_id)
            if g and str(uid) == str(g.creator_id):
                del games[room_id]; bot.send_message(room_id, "🛑 Stopped.")
        return True
    return False
