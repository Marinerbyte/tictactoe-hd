import time
import random
import threading
import sys
import os
from PIL import ImageDraw

# --- UTILS IMPORT (Graphics & Network) ---
try:
    import utils
except ImportError:
    print("[Mines] Error: utils.py not found!")

# --- DB IMPORT (Economy) ---
try:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from db import add_game_result
except Exception as e:
    print(f"DB Import Error: {e}")

# --- GLOBAL VARIABLES ---
games = {}           # Active Games in Rooms
setup_pending = {}   # Users jo abhi DM me bomb set kar rahe hain {user_id: room_id}
game_lock = threading.Lock()
BOT_INSTANCE = None

def setup(bot_ref):
    global BOT_INSTANCE
    BOT_INSTANCE = bot_ref
    print("[CookieMines] Loaded successfully.")

# --- 🎨 VISUAL ENGINE (The Artist) ---

def draw_mine_board(board_config, revealed_list, lives_p1, lives_p2, current_turn_name, is_game_over=False):
    """
    12-Grid Board banata hai.
    board_config: Kahan bomb hai (True/False list)
    revealed_list: Kahan click kiya gaya (True/False list)
    """
    W, H = 500, 600
    
    # 1. Background (Dark Casino Style)
    img = utils.get_gradient(W, H, (30, 30, 40), (10, 10, 15))
    d = ImageDraw.Draw(img)

    # 2. Header (Lives & Turn)
    # P1 Lives (Left)
    hearts_p1 = "❤️" * lives_p1 + "💀" * (3 - lives_p1)
    utils.write_text(d, (20, 20), f"P1: {hearts_p1}", size=20, align="left")
    
    # P2 Lives (Right)
    hearts_p2 = "❤️" * lives_p2 + "💀" * (3 - lives_p2)
    utils.write_text(d, (480, 20), f"P2: {hearts_p2}", size=20, align="right")

    # Turn Info
    status_text = f"Turn: @{current_turn_name}" if not is_game_over else "GAME OVER"
    status_col = "#FFD700" if not is_game_over else "#FF4444"
    utils.write_text(d, (W//2, 60), status_text, size=30, align="center", col=status_col, shadow=True)

    # 3. The Grid (3 Rows x 4 Columns)
    # Assets load karo (Cache se fast aayenge)
    cookie_img = utils.get_emoji("🍪", size=90)
    bomb_img = utils.get_emoji("💥", size=90)
    crumb_img = utils.get_emoji("🟤", size=40) # Crumbs for safe spot
    
    start_x, start_y = 50, 120
    box_w, box_h = 100, 100
    gap = 20

    for i in range(12):
        row = i // 4
        col = i % 4
        
        x = start_x + (col * (box_w + gap))
        y = start_y + (row * (box_h + gap))
        
        # Box Background
        utils.draw_rounded_card(box_w, box_h, 15, (50, 50, 60)).paste(img, (x, y)) # Blend logic simulation
        # Simple Rect fallback for speed
        d.rounded_rectangle([x, y, x+box_w, y+box_h], radius=15, fill=(50, 50, 60), outline=(80,80,90), width=2)

        # Number Label (Always visible nicely)
        utils.write_text(d, (x+10, y+5), str(i+1), size=18, col="#AAAAAA")

        # LOGIC: Kya dikhana hai?
        if not revealed_list[i]:
            # Hidden hai -> Cookie dikhao
            if cookie_img: img.paste(cookie_img, (x+5, y+5), cookie_img)
        else:
            # Reveal ho chuka hai
            if board_config[i] == 1: # BOMB THA!
                d.rounded_rectangle([x, y, x+box_w, y+box_h], radius=15, fill=(100, 30, 30)) # Red bg
                if bomb_img: img.paste(bomb_img, (x+5, y+5), bomb_img)
            else: # SAFE THA
                d.rounded_rectangle([x, y, x+box_w, y+box_h], radius=15, fill=(30, 80, 30)) # Green bg
                utils.write_text(d, (x+50, y+50), "YUM!", size=20, align="center", col="#88FF88")

    return img

def draw_setup_board():
    """Sirf DM ke liye reference board"""
    W, H = 500, 400
    img = utils.get_gradient(W, H, (20,20,30), (10,10,10))
    d = ImageDraw.Draw(img)
    utils.write_text(d, (W//2, 30), "Hide 3 Bombs", size=30, align="center", col="#FFD700")
    utils.write_text(d, (W//2, 70), "Reply e.g.: '2 5 9'", size=20, align="center", col="white")
    
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

# --- GAME LOGIC ---

class MinesGame:
    def __init__(self, room_id, p1_id, p1_name):
        self.room_id = room_id
        self.p1_id = p1_id; self.p1_name = p1_name
        self.p2_id = None; self.p2_name = None
        
        # State: 'waiting_join', 'setup_phase', 'playing'
        self.state = 'waiting_join'
        self.bet = 0
        
        # Boards (12 slots: 0=Safe, 1=Bomb)
        self.board_p1 = [0] * 12  # P1 ka board (Jisme P1 ne bomb chupaye)
        self.board_p2 = [0] * 12  # P2 ka board
        
        # Revealed Status (Track clicks)
        self.revealed_p1 = [False] * 12 # P2 ne P1 ke board pe kya khola
        self.revealed_p2 = [False] * 12 # P1 ne P2 ke board pe kya khola
        
        # Lives
        self.lives_p1 = 3
        self.lives_p2 = 3
        
        # Setup Tracking
        self.p1_ready = False
        self.p2_ready = False
        
        self.turn = 'P1' # P1 starts eating
        self.last_interaction = time.time()

    def touch(self): self.last_interaction = time.time()

# --- COMMAND HANDLER ---

def handle_command(bot, command, room_id, user, args, data):
    global games, setup_pending
    
    user_id = data.get('userid', user)
    cmd = command.lower().strip()
    
    # --- 1. GAME START & JOIN (Room Commands) ---
    
    if cmd == "mines":
        # Check args for bet
        bet_amount = 0
        if args and args[0].isdigit():
            bet_amount = int(args[0])

        with game_lock:
            if room_id in games:
                bot.send_message(room_id, "⚠️ Game chal raha hai!")
                return True
            
            game = MinesGame(room_id, user_id, user)
            game.bet = bet_amount
            
            # Deduct Bet P1
            if bet_amount > 0:
                add_game_result(user_id, user, "mines", -bet_amount, is_win=False)

            games[room_id] = game
        
        bot.send_message(room_id, f"💣 **Cookie Mines Created!**\nBet: {bet_amount}\nWaiting for Player 2 to type `!join`")
        return True

    if cmd == "join":
        with game_lock:
            game = games.get(room_id)
            if not game or game.state != 'waiting_join': return False
            if str(game.p1_id) == str(user_id): return True # Self join check

            # P2 Join Logic
            game.p2_id = user_id
            game.p2_name = user
            
            # Deduct Bet P2
            if game.bet > 0:
                add_game_result(user_id, user, "mines", -game.bet, is_win=False)

            game.state = 'setup_phase'
            
            # Add to Pending Setup Map (Taaki DM pehchan sake)
            setup_pending[str(game.p1_id)] = room_id
            setup_pending[str(game.p2_id)] = room_id
            
        # Send DMs
        bot.send_message(room_id, "✅ **Match Found!** Check your DMs to set bombs. 🤫")
        
        # Generate Reference Board
        img = draw_setup_board()
        link = utils.upload(bot, img)
        
        dm_msg = "🤫 **Shhh! Setup Phase**\nReply with 3 numbers (1-12) to hide bombs.\nExample: `2 5 9`"
        bot.send_dm_image(game.p1_name, link, dm_msg)
        bot.send_dm_image(game.p2_name, link, dm_msg)
        return True

    # --- 2. DM HANDLING (Hidden Setup) ---
    
    # Hum check karenge agar message DM hai aur user setup_pending list me hai
    # Note: Howdies plugin system me usually DM ka 'room_id' alag hota hai ya handler 'privatemessage' hota hai.
    # Agar ye normal chat handler se aa raha hai to hum check karenge:
    
    is_setup_msg = str(user_id) in setup_pending
    
    if is_setup_msg:
        # User is in setup mode. Try to parse numbers.
        # Sirf tab jab message me digits hon (Chat me bhi commands aa sakti hain)
        # Hum assume kar rahe hain ki Setup ke waqt user sirf numbers bhejega.
        
        potential_nums = [int(s) for s in command.split() if s.isdigit()]
        if len(potential_nums) == 0 and args:
             potential_nums = [int(s) for s in args if s.isdigit()]

        if len(potential_nums) == 3:
            # Validate Range (1-12)
            if all(1 <= n <= 12 for n in potential_nums) and len(set(potential_nums)) == 3:
                # Valid Setup!
                target_room = setup_pending[str(user_id)]
                with game_lock:
                    if target_room in games:
                        game = games[target_room]
                        
                        # Indices fix (0-11)
                        mine_indices = [n-1 for n in potential_nums]
                        
                        if str(user_id) == str(game.p1_id):
                            for idx in mine_indices: game.board_p1[idx] = 1 # Set P1 Bombs
                            game.p1_ready = True
                            bot.send_dm(user, "✅ Bombs set! Waiting for opponent...")
                        
                        elif str(user_id) == str(game.p2_id):
                            for idx in mine_indices: game.board_p2[idx] = 1 # Set P2 Bombs
                            game.p2_ready = True
                            bot.send_dm(user, "✅ Bombs set! Waiting for opponent...")

                        # Check if Both Ready
                        if game.p1_ready and game.p2_ready:
                            game.state = 'playing'
                            # Remove from pending
                            if str(game.p1_id) in setup_pending: del setup_pending[str(game.p1_id)]
                            if str(game.p2_id) in setup_pending: del setup_pending[str(game.p2_id)]
                            
                            # Announce Start in Room
                            bot.send_message(target_room, "🔥 **Game Started!** Bombs are hidden.")
                            
                            # Show P1's Turn (P1 has to eat from P2's board)
                            # Draw P2's board (Hidden)
                            img = draw_mine_board(game.board_p2, game.revealed_p2, game.lives_p1, game.lives_p2, game.p1_name)
                            link = utils.upload(bot, img)
                            bot.send_json({"handler": "chatroommessage", "roomid": target_room, "type": "image", "url": link, "text": "Turn P1"})
                            bot.send_message(target_room, f"@{game.p1_name}, Pick a cookie (1-12)!")
                
                return True # Command handled
            else:
                bot.send_dm(user, "❌ Invalid! Send 3 unique numbers between 1-12. (e.g., 1 2 3)")
                return True

    # --- 3. GAMEPLAY (Room Moves) ---
    
    with game_lock:
        game = games.get(room_id)
        if not game or game.state != 'playing': return False

        # Only process numbers 1-12
        if cmd.isdigit() and 1 <= int(cmd) <= 12:
            choice = int(cmd) - 1
            game.touch()

            # Identify Player & Logic
            is_p1_turn = (game.turn == 'P1')
            
            if is_p1_turn and str(user_id) != str(game.p1_id): return False
            if not is_p1_turn and str(user_id) != str(game.p2_id): return False

            # Select correct board arrays
            # P1 khayega P2 ke board se
            target_board = game.board_p2 if is_p1_turn else game.board_p1
            revealed_status = game.revealed_p2 if is_p1_turn else game.revealed_p1
            
            # Check if already clicked
            if revealed_status[choice]:
                bot.send_message(room_id, "🚫 Already eaten! Pick another.")
                return True

            # REVEAL LOGIC
            revealed_status[choice] = True
            hit_bomb = (target_board[choice] == 1)
            
            msg_extra = ""
            
            if hit_bomb:
                msg_extra = "💥 **BOOM!** Found a bomb!"
                if is_p1_turn: game.lives_p1 -= 1
                else: game.lives_p2 -= 1
            else:
                msg_extra = "😋 **Safe!** Yummy cookie."

            # CHECK GAME OVER
            winner = None
            if game.lives_p1 == 0: winner = game.p2_name; winner_id = game.p2_id
            elif game.lives_p2 == 0: winner = game.p1_name; winner_id = game.p1_id

            if winner:
                # Game Over Image
                # Final state dikhao
                img = draw_mine_board(target_board, revealed_status, game.lives_p1, game.lives_p2, winner, is_game_over=True)
                link = utils.upload(bot, img)
                bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "GameOver"})
                
                # Payout
                reward = game.bet * 2 if game.bet > 0 else 0
                if reward > 0:
                    add_game_result(winner_id, winner, "mines", reward, is_win=True)
                    bot.send_message(room_id, f"🏆 **{winner} WINS!** Won {reward} Coins.")
                else:
                    add_game_result(winner_id, winner, "mines", 0, is_win=True)
                    bot.send_message(room_id, f"🏆 **{winner} WINS!**")
                
                # Cleanup
                del games[room_id]
                return True
            
            # SWITCH TURN
            game.turn = 'P2' if is_p1_turn else 'P1'
            next_player = game.p2_name if is_p1_turn else game.p1_name
            
            # Draw Next State (Opponent's board dikhana hai ab)
            # Agar ab P2 ki baari hai, to P1 ka board dikhao (game.board_p1)
            next_target_board = game.board_p1 if is_p1_turn else game.board_p2
            next_revealed = game.revealed_p1 if is_p1_turn else game.revealed_p2
            
            img = draw_mine_board(next_target_board, next_revealed, game.lives_p1, game.lives_p2, next_player)
            link = utils.upload(bot, img)
            
            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "NextTurn"})
            bot.send_message(room_id, f"{msg_extra}\n@{next_player}, Your turn! (1-12)")
            return True

    return False
