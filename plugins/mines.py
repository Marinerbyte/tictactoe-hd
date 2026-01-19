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
    print("[CookieMines] Pro Visuals Loaded.")

# ==========================================
# 🎨 ARTIST SECTION (New Graphics)
# ==========================================

def draw_enhanced_board(board_config, revealed_list, lives_p1, lives_p2, current_turn_name, p1_name, p2_name, is_game_over=False):
    """
    Board with Cute Borders, Clear Status & Stickers
    """
    W, H = 500, 650
    
    # 1. Background (Deep Purple Casino Theme)
    img = utils.get_gradient(W, H, (40, 30, 60), (20, 15, 30))
    d = ImageDraw.Draw(img)
    
    # 2. Cute Border
    d.rectangle([5, 5, W-5, H-5], outline="#FFD700", width=4)
    d.rectangle([10, 10, W-10, H-10], outline="#FFA500", width=2)

    # 3. Header (Scoreboard)
    # Header Background
    utils.draw_rounded_card(W-40, 80, 20, (0, 0, 0, 100)).paste(img, (20, 20)) # Masking trick
    d.rounded_rectangle([20, 20, W-20, 100], radius=20, fill=(30, 20, 40), outline="#FF69B4", width=3)
    
    # P1 Info
    utils.write_text(d, (40, 35), f"@{p1_name[:10]}", size=18, col="#88CCFF")
    hearts_p1 = "❤️" * lives_p1 + "❌" * (3 - lives_p1)
    utils.write_text(d, (40, 60), hearts_p1, size=24)

    # P2 Info
    utils.write_text(d, (460, 35), f"@{p2_name[:10]}", size=18, col="#FF8888", align="right")
    hearts_p2 = "❤️" * lives_p2 + "❌" * (3 - lives_p2)
    utils.write_text(d, (460, 60), hearts_p2, size=24, align="right")

    # Center VS/Turn
    status_text = f"Turn:\n{current_turn_name}" if not is_game_over else "GAME\nOVER"
    utils.write_text(d, (W//2, 60), status_text, size=22, align="center", col="#FFF", shadow=True)

    # 4. The Grid
    start_x, start_y = 50, 130
    box_w, box_h = 90, 90
    gap = 15
    
    # Assets
    cookie_icon = utils.get_emoji("🍪", size=70)
    bomb_icon = utils.get_emoji("💣", size=70) # Or "💥"
    safe_icon = utils.get_emoji("😋", size=50)
    locked_icon = utils.get_emoji("❓", size=50)

    for i in range(12):
        row = i // 4
        col = i % 4
        x = start_x + (col * (box_w + gap))
        y = start_y + (row * (box_h + gap))
        
        # Determine Box Style
        is_revealed = revealed_list[i]
        is_bomb = (board_config[i] == 1)
        
        if not is_revealed:
            # LOCKED BOX
            d.rounded_rectangle([x, y, x+box_w, y+box_h], radius=15, fill=(60, 50, 80), outline="#9988AA", width=2)
            if locked_icon: img.paste(locked_icon, (x+20, y+20), locked_icon)
            # Number Overlay
            utils.write_text(d, (x+75, y+70), str(i+1), size=16, col="#DDD", align="center")
            
        else:
            # REVEALED
            if is_bomb:
                # BOMB HIT (Red)
                d.rounded_rectangle([x, y, x+box_w, y+box_h], radius=15, fill=(180, 50, 50), outline="red", width=3)
                if bomb_icon: img.paste(bomb_icon, (x+10, y+10), bomb_icon)
            else:
                # SAFE COOKIE (Green)
                d.rounded_rectangle([x, y, x+box_w, y+box_h], radius=15, fill=(50, 150, 80), outline="#00FF00", width=3)
                if cookie_icon: img.paste(cookie_icon, (x+10, y+10), cookie_icon)
                # Yum text
                utils.write_text(d, (x+45, y+70), "YUM", size=14, col="white", align="center", shadow=True)

    # Footer
    utils.write_text(d, (W//2, 620), "Choose a box (1-12) to Eat!", size=18, col="#888", align="center")
    
    return img

def draw_blast_card(victim_name, lives_left, avatar_url=None):
    """
    Funny Cartoon Blast Card when someone hits a bomb
    """
    W, H = 500, 400
    # 1. Background (Explosion Gradient)
    img = utils.get_gradient(W, H, (200, 50, 0), (50, 0, 0))
    d = ImageDraw.Draw(img)
    
    # Random pattern
    for _ in range(20):
        x, y = random.randint(0, W), random.randint(0, H)
        r = random.randint(5, 15)
        d.ellipse([x, y, x+r, y+r], fill=(255, 100, 0))

    # 2. Big Explosion Sticker
    blast = utils.get_sticker("fire", size=150) # Using fire or explosion emoji
    if not blast: blast = utils.get_emoji("💥", size=150)
    
    if blast:
        img.paste(blast, (W//2 - 75, 50), blast)

    # 3. Avatar Overlay (Burnt style)
    if avatar_url:
        av = utils.get_circle_avatar(avatar_url, size=100)
        if av:
            img.paste(av, (W//2 - 50, 150), av)
            # Draw X eyes on avatar if possible, or just a red cross
            d.line([W//2-30, 180, W//2+30, 220], fill="red", width=5)
            d.line([W//2+30, 180, W//2-30, 220], fill="red", width=5)

    # 4. Text
    utils.write_text(d, (W//2, 280), "BOOM! 💥", size=50, align="center", col="yellow", shadow=True)
    utils.write_text(d, (W//2, 340), f"@{victim_name} got roasted!", size=25, align="center", col="white", shadow=True)
    utils.write_text(d, (W//2, 370), f"Lives Left: {lives_left}", size=20, align="center", col="#FFCCCC")
    
    return img

def draw_mines_winner(winner_name, reward, avatar_url=None):
    """
    Celebration Card with Cookies & Trophies
    """
    W, H = 500, 600
    # 1. Background (Gold/Winner)
    img = utils.get_gradient(W, H, (60, 50, 10), (20, 20, 5))
    d = ImageDraw.Draw(img)
    
    # 2. Confetti / Cookies Background
    cookie = utils.get_emoji("🍪", size=40)
    if cookie:
        for _ in range(15):
            x, y = random.randint(0, W), random.randint(0, H)
            img.paste(cookie, (x, y), cookie)

    # 3. Trophy
    trophy = utils.get_sticker("win", size=180)
    if not trophy: trophy = utils.get_emoji("🏆", size=180)
    
    if trophy:
        img.paste(trophy, (W//2 - 90, 80), trophy)

    # 4. Avatar
    if avatar_url:
        av = utils.get_circle_avatar(avatar_url, size=120)
        if av:
            img.paste(av, (W//2 - 60, 250), av)
            d.ellipse([W//2-65, 245, W//2+65, 375], outline="#FFD700", width=5)

    # 5. Text Info
    utils.write_text(d, (W//2, 400), "WINNER!", size=60, align="center", col="#FFD700", shadow=True)
    utils.write_text(d, (W//2, 480), f"@{winner_name}", size=40, align="center", col="white", shadow=True)
    
    if reward > 0:
        utils.write_text(d, (W//2, 540), f"Won +{reward} Coins", size=30, align="center", col="#88FF88", shadow=True)
    
    return img

def draw_setup_board():
    """DM Setup Board"""
    W, H = 500, 400
    img = utils.get_gradient(W, H, (20,20,30), (10,10,10))
    d = ImageDraw.Draw(img)
    utils.write_text(d, (W//2, 30), "🤫 Hide 3 Bombs", size=30, align="center", col="#FFD700")
    
    start_x, start_y = 50, 100
    box_w, box_h = 90, 80
    gap = 15

    for i in range(12):
        row = i // 4; col = i % 4
        x = start_x + (col * (box_w + gap))
        y = start_y + (row * (box_h + gap))
        d.rounded_rectangle([x, y, x+box_w, y+box_h], radius=10, fill=(60, 60, 70))
        utils.write_text(d, (x+45, y+40), str(i+1), size=30, align="center", col="white")
    
    return img

# ==========================================
# ⚙️ GAME LOGIC
# ==========================================

class MinesGame:
    def __init__(self, room_id, p1_id, p1_name):
        self.room_id = room_id
        self.p1_id = p1_id; self.p1_name = p1_name
        self.p2_id = None; self.p2_name = None
        
        # New: Store Avatar URLs for cards
        self.p1_avatar = None
        self.p2_avatar = None

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
    # Extract Avatar
    avatar_file = data.get("avatar")
    avatar_url = f"https://cdn.howdies.app/avatar?image={avatar_file}" if avatar_file else None

    cmd = command.lower().strip()
    
    # 1. CREATE
    if cmd == "mines":
        bet_amount = int(args[0]) if args and args[0].isdigit() else 0
        with game_lock:
            if room_id in games: return True
            game = MinesGame(room_id, user_id, user)
            game.bet = bet_amount
            game.p1_avatar = avatar_url # Save Avatar
            if bet_amount > 0: add_game_result(user_id, user, "mines", -bet_amount, False)
            games[room_id] = game
        
        bot.send_message(room_id, f"💣 **Cookie Mines!** Bet: {bet_amount}\nWaiting for Player 2 (`!join`)")
        return True

    # 2. JOIN
    if cmd == "join":
        with game_lock:
            game = games.get(room_id)
            if not game or game.state != 'waiting_join': return False
            if str(game.p1_id) == str(user_id): return True

            game.p2_id = user_id
            game.p2_name = user
            game.p2_avatar = avatar_url # Save Avatar
            
            if game.bet > 0: add_game_result(user_id, user, "mines", -game.bet, False)
            game.state = 'setup_phase'
            setup_pending[str(game.p1_id)] = room_id
            setup_pending[str(game.p2_id)] = room_id
            
        bot.send_message(room_id, "✅ **Match Found!** Check DM to set bombs. 🤫")
        
        # DM Setup
        img = draw_setup_board()
        link = utils.upload(bot, img)
        bot.send_dm_image(game.p1_name, link, "Hide 3 Bombs! Reply: `1 5 9`")
        bot.send_dm_image(game.p2_name, link, "Hide 3 Bombs! Reply: `2 4 8`")
        return True

    # 3. DM SETUP
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
                        bot.send_dm(user, "✅ P1 Set!")
                    elif str(user_id) == str(g.p2_id):
                        for i in indices: g.board_p2[i] = 1
                        g.p2_ready = True
                        bot.send_dm(user, "✅ P2 Set!")

                    if g.p1_ready and g.p2_ready:
                        g.state = 'playing'
                        del setup_pending[str(g.p1_id)]
                        del setup_pending[str(g.p2_id)]
                        
                        bot.send_message(rid, "🔥 **Game Started!** Bombs hidden.")
                        
                        # Show Board (P1 Turn -> Show P2 Board)
                        img = draw_enhanced_board(g.board_p2, g.revealed_p2, g.lives_p1, g.lives_p2, g.p1_name, g.p1_name, g.p2_name)
                        link = utils.upload(bot, img)
                        bot.send_json({"handler": "chatroommessage", "roomid": rid, "type": "image", "url": link, "text": "Start"})
                        bot.send_message(rid, f"@{g.p1_name}, Pick a number (1-12)!")
            return True

    # 4. GAMEPLAY
    with game_lock:
        game = games.get(room_id)
        if not game or game.state != 'playing': return False

        if cmd.isdigit() and 1 <= int(cmd) <= 12:
            choice = int(cmd) - 1
            game.touch()

            is_p1 = (game.turn == 'P1')
            if is_p1 and str(user_id) != str(game.p1_id): return False
            if not is_p1 and str(user_id) != str(game.p2_id): return False

            # Determine Target Board
            tgt_board = game.board_p2 if is_p1 else game.board_p1
            tgt_reveal = game.revealed_p2 if is_p1 else game.revealed_p1
            
            if tgt_reveal[choice]: return True # Already clicked

            # Update State
            tgt_reveal[choice] = True
            hit_bomb = (tgt_board[choice] == 1)
            
            current_player_name = game.p1_name if is_p1 else game.p2_name
            current_player_av = game.p1_avatar if is_p1 else game.p2_avatar
            
            # --- ACTION: BOMB HIT ---
            if hit_bomb:
                if is_p1: game.lives_p1 -= 1
                else: game.lives_p2 -= 1
                
                lives_left = game.lives_p1 if is_p1 else game.lives_p2
                
                # 1. SEND FUNNY BLAST CARD
                blast_img = draw_blast_card(current_player_name, lives_left, current_player_av)
                blast_link = utils.upload(bot, blast_img)
                bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": blast_link, "text": "BOOM"})

            # CHECK WINNER
            winner, win_id, win_av = None, None, None
            if game.lives_p1 == 0: 
                winner = game.p2_name; win_id = game.p2_id; win_av = game.p2_avatar
            elif game.lives_p2 == 0: 
                winner = game.p1_name; win_id = game.p1_id; win_av = game.p1_avatar

            if winner:
                # REWARD
                reward = game.bet * 2 if game.bet > 0 else 0
                add_game_result(win_id, winner, "mines", reward, True)
                
                # WINNER CARD (Game Over)
                # Show final board first? No, show Winner Card directly
                win_img = draw_mines_winner(winner, reward, win_av)
                win_link = utils.upload(bot, win_img)
                
                bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": win_link, "text": "Winner"})
                bot.send_message(room_id, f"🎉 **GAME OVER!** {winner} wins!")
                
                del games[room_id]
                return True

            # NEXT TURN
            game.turn = 'P2' if is_p1 else 'P1'
            next_p = game.p2_name if is_p1 else game.p1_name
            
            # Draw Next State
            next_tgt_board = game.board_p1 if is_p1 else game.board_p2
            next_tgt_reveal = game.revealed_p1 if is_p1 else game.revealed_p2
            
            img = draw_enhanced_board(next_tgt_board, next_tgt_reveal, game.lives_p1, game.lives_p2, next_p, game.p1_name, game.p2_name)
            link = utils.upload(bot, img)
            
            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Turn"})
            bot.send_message(room_id, f"@{next_p}, Your turn! (1-12)")
            return True

    return False
