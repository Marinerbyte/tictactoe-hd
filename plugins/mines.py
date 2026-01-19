import time
import random
import threading
import sys
import os
from PIL import ImageDraw

# --- UTILS IMPORT ---
try:
    import utils
except ImportError:
    print("[Mines] Error: utils.py not found!")

# --- DB IMPORT ---
try:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from db import add_game_result
except Exception as e:
    print(f"DB Import Error: {e}")

# --- GLOBAL VARIABLES ---
games = {}
setup_pending = {}
game_lock = threading.Lock()
BOT_INSTANCE = None

def setup(bot_ref):
    global BOT_INSTANCE
    BOT_INSTANCE = bot_ref
    print("[CookieMines] Ultimate Version Loaded.")

# --- AUTOMATIC CLEANUP (90 Seconds) ---
def game_cleanup_loop():
    while True:
        time.sleep(10)
        now = time.time()
        to_remove = []
        with game_lock:
            for room_id, game in games.items():
                if now - game.last_interaction > 90: # 90 Seconds Check
                    to_remove.append(room_id)
        
        for room_id in to_remove:
            if BOT_INSTANCE:
                try: BOT_INSTANCE.send_message(room_id, "⌛ **Game Timeout!** Room cleaned.")
                except: pass
            with game_lock:
                if room_id in games: 
                    # Clean pending setups too if any
                    g = games[room_id]
                    if str(g.p1_id) in setup_pending: del setup_pending[str(g.p1_id)]
                    if g.p2_id and str(g.p2_id) in setup_pending: del setup_pending[str(g.p2_id)]
                    del games[room_id]

if threading.active_count() < 10: 
    threading.Thread(target=game_cleanup_loop, daemon=True).start()

# ==========================================
# 🎨 ARTIST SECTION (Premium Visuals)
# ==========================================

def draw_enhanced_board(board_config, revealed_list, lives_p1, lives_p2, current_turn_name, p1_name, p2_name, is_game_over=False):
    """
    Premium 3D-Style Board with VS Badge and Status
    """
    W, H = 500, 680
    
    # 1. Premium Background (Gradient + Noise Texture feel)
    img = utils.get_gradient(W, H, (40, 35, 60), (15, 10, 20))
    d = ImageDraw.Draw(img)
    
    # Decorative Corners
    star = utils.get_emoji("✨", size=30)
    if star:
        img.paste(star, (10, 10), star)
        img.paste(star, (W-40, 10), star)

    # 2. Header Area (VS Mode)
    # P1 Box (Active Turn Highlight)
    p1_bg = (60, 100, 60) if current_turn_name == p1_name and not is_game_over else (50, 40, 60)
    d.rounded_rectangle([20, 50, 200, 110], radius=15, fill=p1_bg, outline="#55AAFF", width=2)
    utils.write_text(d, (110, 70), f"@{p1_name[:8]}", size=18, align="center", col="#88CCFF", shadow=True)
    utils.write_text(d, (110, 95), "❤️" * lives_p1, size=16, align="center")

    # P2 Box
    p2_bg = (60, 100, 60) if current_turn_name == p2_name and not is_game_over else (50, 40, 60)
    d.rounded_rectangle([300, 50, 480, 110], radius=15, fill=p2_bg, outline="#FF5555", width=2)
    utils.write_text(d, (390, 70), f"@{p2_name[:8]}", size=18, align="center", col="#FF8888", shadow=True)
    utils.write_text(d, (390, 95), "❤️" * lives_p2, size=16, align="center")

    # VS Badge in Center
    d.ellipse([220, 55, 280, 115], fill="#FFD700", outline="white", width=3)
    utils.write_text(d, (250, 85), "VS", size=24, align="center", col="black", shadow=False)

    # 3. Status Text
    if is_game_over:
        status = "GAME OVER"
        col = "#FF4444"
    else:
        status = f"Waiting for @{current_turn_name}..."
        col = "#FFFF00"
    
    utils.write_text(d, (W//2, 140), status, size=20, align="center", col=col, shadow=True)

    # 4. The Grid
    start_x, start_y = 50, 170
    box_w, box_h = 90, 90
    gap = 15
    
    # Assets
    cookie_icon = utils.get_emoji("🍪", size=65)
    bomb_icon = utils.get_sticker("fire", size=70) or utils.get_emoji("💥", size=70)
    lock_icon = utils.get_emoji("📦", size=50)

    for i in range(12):
        row = i // 4; col = i % 4
        x = start_x + (col * (box_w + gap))
        y = start_y + (row * (box_h + gap))
        
        is_revealed = revealed_list[i]
        is_bomb = (board_config[i] == 1)
        
        if not is_revealed:
            # 3D Button Style (Locked)
            # Darker bottom for 3D effect
            d.rounded_rectangle([x, y+5, x+box_w, y+box_h+5], radius=15, fill=(40, 30, 50)) 
            # Main Face
            d.rounded_rectangle([x, y, x+box_w, y+box_h], radius=15, fill=(70, 60, 90), outline="#9988AA", width=2)
            
            if lock_icon: img.paste(lock_icon, (x+20, y+15), lock_icon)
            utils.write_text(d, (x+45, y+70), str(i+1), size=16, col="#DDD", align="center")
            
        else:
            # Revealed State
            if is_bomb:
                d.rounded_rectangle([x, y, x+box_w, y+box_h], radius=15, fill=(180, 50, 50), outline="red", width=3)
                if bomb_icon: img.paste(bomb_icon, (x+10, y+10), bomb_icon)
            else:
                d.rounded_rectangle([x, y, x+box_w, y+box_h], radius=15, fill=(50, 150, 80), outline="#00FF00", width=3)
                if cookie_icon: img.paste(cookie_icon, (x+12, y+12), cookie_icon)

    # Footer
    utils.write_text(d, (W//2, 640), "Avoid the Bombs! Find the Cookies!", size=16, col="#888", align="center")
    
    return img

def draw_blast_card(victim_name, lives_left, avatar_url=None):
    W, H = 500, 400
    img = utils.get_gradient(W, H, (100, 0, 0), (30, 0, 0))
    d = ImageDraw.Draw(img)
    
    # Blast Sticker
    blast = utils.get_emoji("💥", size=180)
    if blast: img.paste(blast, (W//2 - 90, 40), blast)

    if avatar_url:
        av = utils.get_circle_avatar(avatar_url, size=100)
        if av: img.paste(av, (W//2 - 50, 140), av)

    utils.write_text(d, (W//2, 280), "BOOM!", size=50, align="center", col="yellow", shadow=True)
    utils.write_text(d, (W//2, 340), f"@{victim_name} lost a life!", size=24, align="center", col="white")
    utils.write_text(d, (W//2, 370), f"Lives Remaining: {lives_left}", size=20, align="center", col="#FFAAAA")
    return img

def draw_mines_winner(winner_name, reward, avatar_url=None):
    W, H = 500, 600
    img = utils.get_gradient(W, H, (255, 215, 0), (200, 150, 0)) # Gold Gradient
    d = ImageDraw.Draw(img)
    
    # Pattern
    pat = utils.get_emoji("🍪", size=40)
    if pat:
        for _ in range(10):
            img.paste(pat, (random.randint(0, 450), random.randint(0, 550)), pat)

    # Trophy
    trophy = utils.get_sticker("win", size=160) or utils.get_emoji("🏆", size=160)
    if trophy: img.paste(trophy, (W//2 - 80, 60), trophy)

    if avatar_url:
        av = utils.get_circle_avatar(avatar_url, size=130)
        if av: 
            img.paste(av, (W//2 - 65, 240), av)
            d.ellipse([W//2-70, 235, W//2+70, 375], outline="white", width=5)

    utils.write_text(d, (W//2, 420), "VICTORY!", size=50, align="center", col="white", shadow=True)
    utils.write_text(d, (W//2, 490), f"@{winner_name}", size=35, align="center", col="#333")
    if reward > 0:
        utils.write_text(d, (W//2, 550), f"+{reward} Coins", size=30, align="center", col="#006400")

    return img

def draw_setup_board():
    W, H = 500, 300
    img = utils.get_gradient(W, H, (30,30,40), (10,10,10))
    d = ImageDraw.Draw(img)
    utils.write_text(d, (W//2, 40), "SECRET SETUP", size=35, align="center", col="#FFD700", shadow=True)
    utils.write_text(d, (W//2, 100), "Reply with 3 numbers", size=25, align="center", col="white")
    utils.write_text(d, (W//2, 140), "Example: 1 5 9", size=20, align="center", col="#AAA")
    
    # Decorative boxes below
    for i in range(5):
        d.rounded_rectangle([50 + i*90, 200, 120 + i*90, 270], radius=10, fill=(60,60,70))
        utils.write_text(d, (85 + i*90, 235), "?", size=30, align="center")
    
    return img

# ==========================================
# ⚙️ LOGIC
# ==========================================

class MinesGame:
    def __init__(self, room_id, p1_id, p1_name):
        self.room_id = room_id
        self.p1_id = p1_id; self.p1_name = p1_name
        self.p2_id = None; self.p2_name = None
        self.p1_avatar = None; self.p2_avatar = None
        self.state = 'waiting_join'
        self.bet = 0
        self.board_p1 = [0] * 12
        self.board_p2 = [0] * 12
        self.revealed_p1 = [False] * 12
        self.revealed_p2 = [False] * 12
        self.lives_p1 = 3
        self.lives_p2 = 3
        self.p1_ready = False
        self.p2_ready = False
        self.turn = 'P1'
        self.last_interaction = time.time()

    def touch(self): self.last_interaction = time.time()

def handle_command(bot, command, room_id, user, args, data):
    global games, setup_pending
    user_id = data.get('userid', user)
    avatar_file = data.get("avatar")
    avatar_url = f"https://cdn.howdies.app/avatar?image={avatar_file}" if avatar_file else None
    cmd = command.lower().strip()
    
    # 1. CREATE GAME
    if cmd == "mines":
        bet_amount = int(args[0]) if args and args[0].isdigit() else 0
        with game_lock:
            if room_id in games: 
                bot.send_message(room_id, "⚠️ Game running! Type `!stop` to cancel.")
                return True
            game = MinesGame(room_id, user_id, user)
            game.bet = bet_amount
            game.p1_avatar = avatar_url
            if bet_amount > 0: add_game_result(user_id, user, "mines", -bet_amount, False)
            games[room_id] = game
        
        bot.send_message(room_id, f"💣 **Cookie Mines!**\nEntry Fee: {bet_amount}\nPlayer 2: Type `!join` to start.")
        return True

    # 2. STOP GAME (Added !stop logic)
    if cmd == "stop":
        with game_lock:
            if room_id in games:
                game = games[room_id]
                # Only P1, P2 or Admin can stop
                if str(user_id) in [str(game.p1_id), str(game.p2_id)] or user == bot.user_data.get('username'):
                    # Refund Logic if game didn't finish properly? 
                    # For simplicity, we assume stop means cancel (refund usually done manually or logic can be added)
                    bot.send_message(room_id, "🛑 **Game Stopped by player.**")
                    if str(game.p1_id) in setup_pending: del setup_pending[str(game.p1_id)]
                    if game.p2_id and str(game.p2_id) in setup_pending: del setup_pending[str(game.p2_id)]
                    del games[room_id]
                else:
                    bot.send_message(room_id, "⚠️ Only players can stop the game.")
            else:
                bot.send_message(room_id, "⚠️ No active game.")
        return True

    # 3. JOIN GAME
    if cmd == "join":
        with game_lock:
            game = games.get(room_id)
            if not game or game.state != 'waiting_join': return False
            if str(game.p1_id) == str(user_id): return True

            game.p2_id = user_id
            game.p2_name = user
            game.p2_avatar = avatar_url
            
            if game.bet > 0: add_game_result(user_id, user, "mines", -game.bet, False)
            game.state = 'setup_phase'
            setup_pending[str(game.p1_id)] = room_id
            setup_pending[str(game.p2_id)] = room_id
            
        bot.send_message(room_id, "✅ **Match Found!** check your **DMs** now! 🤫")
        
        # DM Setup with Clear Instructions
        img = draw_setup_board()
        link = utils.upload(bot, img)
        
        guide_text = (
            "💣 **Cookie Mines Setup** 💣\n\n"
            "You need to hide 3 bombs on your board.\n"
            "**How to do it:**\n"
            "Type 3 unique numbers between 1 and 12 separated by space.\n\n"
            "👉 **Example:** `2 7 11`\n\n"
            "Reply here with your numbers now!"
        )
        
        bot.send_dm_image(game.p1_name, link, guide_text)
        bot.send_dm_image(game.p2_name, link, guide_text)
        return True

    # 4. DM SETUP HANDLER
    if str(user_id) in setup_pending:
        nums = [int(s) for s in command.split() if s.isdigit()]
        if len(nums) == 0 and args: nums = [int(s) for s in args if s.isdigit()]

        if len(nums) == 3 and all(1 <= n <= 12 for n in nums) and len(set(nums)) == 3:
            rid = setup_pending[str(user_id)]
            with game_lock:
                if rid in games:
                    g = games[rid]
                    indices = [n-1 for n in nums]
                    
                    if str(user_id) == str(g.p1_id):
                        for i in indices: g.board_p1[i] = 1
                        g.p1_ready = True
                        bot.send_dm(user, "✅ **Bombs Set!** Waiting for opponent...")
                    elif str(user_id) == str(g.p2_id):
                        for i in indices: g.board_p2[i] = 1
                        g.p2_ready = True
                        bot.send_dm(user, "✅ **Bombs Set!** Waiting for opponent...")

                    if g.p1_ready and g.p2_ready:
                        g.state = 'playing'
                        del setup_pending[str(g.p1_id)]
                        del setup_pending[str(g.p2_id)]
                        
                        bot.send_message(rid, "🔥 **All Set! Game Started!**")
                        
                        img = draw_enhanced_board(g.board_p2, g.revealed_p2, g.lives_p1, g.lives_p2, g.p1_name, g.p1_name, g.p2_name)
                        link = utils.upload(bot, img)
                        bot.send_json({"handler": "chatroommessage", "roomid": rid, "type": "image", "url": link, "text": "Start"})
                        bot.send_message(rid, f"@{g.p1_name}, Pick a number (1-12) to Eat!")
            return True
        else:
            # Error Message in DM if format wrong
            bot.send_dm(user, "❌ **Incorrect Format!**\nPlease type exactly 3 unique numbers.\nExample: `1 5 12`")
            return True

    # 5. GAMEPLAY
    with game_lock:
        game = games.get(room_id)
        if not game or game.state != 'playing': return False

        if cmd.isdigit() and 1 <= int(cmd) <= 12:
            choice = int(cmd) - 1
            game.touch()

            is_p1 = (game.turn == 'P1')
            if is_p1 and str(user_id) != str(game.p1_id): return False
            if not is_p1 and str(user_id) != str(game.p2_id): return False

            tgt_board = game.board_p2 if is_p1 else game.board_p1
            tgt_reveal = game.revealed_p2 if is_p1 else game.revealed_p1
            
            if tgt_reveal[choice]: 
                bot.send_message(room_id, "🚫 **Already Eaten!** Pick another box.")
                return True

            tgt_reveal[choice] = True
            hit_bomb = (tgt_board[choice] == 1)
            
            curr_name = game.p1_name if is_p1 else game.p2_name
            curr_av = game.p1_avatar if is_p1 else game.p2_avatar
            
            if hit_bomb:
                if is_p1: game.lives_p1 -= 1
                else: game.lives_p2 -= 1
                lives = game.lives_p1 if is_p1 else game.lives_p2
                
                blast_img = draw_blast_card(curr_name, lives, curr_av)
                link = utils.upload(bot, blast_img)
                bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "BOOM"})

            winner, win_id, win_av = None, None, None
            if game.lives_p1 == 0: 
                winner = game.p2_name; win_id = game.p2_id; win_av = game.p2_avatar
            elif game.lives_p2 == 0: 
                winner = game.p1_name; win_id = game.p1_id; win_av = game.p1_avatar

            if winner:
                reward = game.bet * 2 if game.bet > 0 else 0
                add_game_result(win_id, winner, "mines", reward, True)
                
                win_img = draw_mines_winner(winner, reward, win_av)
                link = utils.upload(bot, win_img)
                bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Winner"})
                bot.send_message(room_id, f"🎉 **GAME OVER!** {winner} wins!")
                del games[room_id]
                return True

            game.turn = 'P2' if is_p1 else 'P1'
            next_p = game.p2_name if is_p1 else game.p1_name
            
            next_tgt_board = game.board_p1 if is_p1 else game.board_p2
            next_tgt_reveal = game.revealed_p1 if is_p1 else game.revealed_p2
            
            img = draw_enhanced_board(next_tgt_board, next_tgt_reveal, game.lives_p1, game.lives_p2, next_p, game.p1_name, game.p2_name)
            link = utils.upload(bot, img)
            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Turn"})
            return True

    return False
