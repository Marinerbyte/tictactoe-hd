import time
import random
import threading
import traceback
import sys
import os
from PIL import ImageDraw

# --- UTILS IMPORT (The Artist & Network Manager) ---
try:
    import utils
except ImportError:
    print("[TicTacToe] Error: utils.py not found!")

# --- DB IMPORT (Economy) ---
try:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from db import add_game_result
except Exception as e:
    print(f"DB Import Error: {e}")

# --- GLOBAL STATE ---
games = {} 
games_lock = threading.Lock()
BOT_INSTANCE = None 

def setup(bot_ref):
    global BOT_INSTANCE
    BOT_INSTANCE = bot_ref
    print("[TicTacToe] Pro Version Loaded.")

# --- CLEANUP THREAD (Background Garbage Collector) ---
def game_cleanup_loop():
    while True:
        time.sleep(10)
        now = time.time()
        to_remove = []
        
        # Check for inactive games
        with games_lock:
            for room_id, game in games.items():
                if now - game.last_interaction > 90:
                    to_remove.append(room_id)
        
        # Remove and Notify
        for room_id in to_remove:
            if BOT_INSTANCE:
                try: BOT_INSTANCE.send_message(room_id, "⌛ Game Timeout! Cleaning up...")
                except: pass
            with games_lock:
                if room_id in games: del games[room_id]

if threading.active_count() < 10: 
    threading.Thread(target=game_cleanup_loop, daemon=True).start()

# --- 🎨 VISUALS (Powered by UTILS) ---

def draw_pro_board(board_state, p1_name, p2_name, turn):
    """
    Creates a High-Quality Game Board using Utils Gradient & Text Engine.
    """
    W, H = 400, 500  # Extra height for status
    
    # 1. Background (Dark Blue-Purple Gradient)
    img = utils.get_gradient(W, H, (20, 20, 30), (10, 10, 15))
    d = ImageDraw.Draw(img)
    
    # 2. Header (Status)
    current_player = p1_name if turn == 'X' else p2_name
    utils.write_text(d, (W//2, 30), f"Turn: {current_player}", size=24, align="center", col="#FFD700", shadow=True)
    utils.write_text(d, (W//2, 470), "Type 1-9 to play", size=16, align="center", col="#8888AA", shadow=False)

    # 3. The Grid
    start_y = 70
    size = 360 # Grid size
    cell = size // 3
    margin = (W - size) // 2
    
    line_col = (100, 100, 120)
    for i in range(1, 3):
        # Vertical
        d.line([(margin + cell*i, start_y), (margin + cell*i, start_y + size)], fill=line_col, width=5)
        # Horizontal
        d.line([(margin, start_y + cell*i), (margin + size, start_y + cell*i)], fill=line_col, width=5)

    # 4. Draw X and O
    for i in range(9):
        row, col = i // 3, i % 3
        x = margin + col * cell
        y = start_y + row * cell
        cx, cy = x + cell // 2, y + cell // 2
        val = board_state[i]

        if val is None:
            # Subtle number hint
            utils.write_text(d, (cx, cy), str(i+1), size=40, col=(50, 50, 60), align="center", shadow=False)
        elif val == 'X':
            # Draw Red Cross
            off = 35
            d.line([(x+off, y+off), (x+cell-off, y+cell-off)], fill=(255, 60, 60), width=12)
            d.line([(x+cell-off, y+off), (x+off, y+cell-off)], fill=(255, 60, 60), width=12)
        elif val == 'O':
            # Draw Blue Circle
            off = 35
            d.ellipse([(x+off, y+off), (x+cell-off, y+cell-off)], outline=(60, 150, 255), width=12)

    return img

def draw_winner_card(winner_name, winner_symbol, avatar_url=None):
    """
    Creates a Professional Winner Card using Utils Assets.
    """
    W, H = 500, 300
    
    # 1. Background (Victory Gradient)
    if winner_symbol == 'X':
        bg = utils.get_gradient(W, H, (60, 10, 10), (20, 5, 5)) # Red tint
    elif winner_symbol == 'O':
        bg = utils.get_gradient(W, H, (10, 10, 60), (5, 5, 20)) # Blue tint
    else:
        bg = utils.get_gradient(W, H, (40, 40, 40), (20, 20, 20)) # Grey (Draw)

    d = ImageDraw.Draw(bg)

    # 2. Add Sticker (Trophy or Bot)
    sticker = utils.get_sticker("win", size=100)
    if sticker:
        bg.paste(sticker, (380, 20), sticker)

    # 3. Avatar (Circular)
    cx, cy = 100, 150
    if avatar_url:
        av = utils.get_circle_avatar(avatar_url, size=140)
        if av:
            bg.paste(av, (cx-70, cy-70), av)
            # Gold Ring border
            d.ellipse([(cx-70, cy-70), (cx+70, cy+70)], outline="#FFD700", width=4)
    else:
        # Fallback Avatar
        d.ellipse([(cx-70, cy-70), (cx+70, cy+70)], fill=(50,50,50), outline="white", width=3)
        initial = winner_name[0].upper()
        utils.write_text(d, (cx, cy), initial, size=80, align="center")

    # 4. Text Info
    utils.write_text(d, (200, 80), "WINNER!", size=50, col="#FFD700", shadow=True)
    utils.write_text(d, (200, 150), f"@{winner_name}", size=35, col="white", shadow=True)
    
    if winner_symbol == 'X':
        utils.write_text(d, (200, 220), "Team Red (X)", size=20, col="#ff6b6b")
    else:
        utils.write_text(d, (200, 220), "Team Blue (O)", size=20, col="#4facfe")

    return bg

# --- GAME LOGIC ---
class TicTacToe:
    def __init__(self, room_id, creator_id, creator_name, creator_avatar=None):
        self.room_id = room_id
        # Tracking IDs & Avatars
        self.p1_id = creator_id; self.p1_name = creator_name; self.p1_avatar = creator_avatar
        self.p2_id = None; self.p2_name = None; self.p2_avatar = None
        
        self.board = [None]*9
        self.turn = 'X'
        self.state = 'setup_mode'
        self.mode = None
        self.bet = 0
        self.last_interaction = time.time()
        
    def touch(self): self.last_interaction = time.time()
    
    def check_win(self):
        wins = [(0,1,2), (3,4,5), (6,7,8), (0,3,6), (1,4,7), (2,5,8), (0,4,8), (2,4,6)]
        for a, b, c in wins:
            if self.board[a] and self.board[a] == self.board[b] == self.board[c]:
                return self.board[a]
        if None not in self.board: return 'draw'
        return None
    
    def bot_move(self):
        empty = [i for i, x in enumerate(self.board) if x is None]
        if not empty: return None
        # Win or Block Logic
        for m in empty:
            self.board[m] = 'O'; 
            if self.check_win() == 'O': self.board[m] = None; return m
            self.board[m] = None
        for m in empty:
            self.board[m] = 'X'; 
            if self.check_win() == 'X': self.board[m] = None; return m
            self.board[m] = None
        if 4 in empty: return 4
        return random.choice(empty)

# --- COMMAND HANDLER ---
def handle_command(bot, command, room_id, user, args, data):
    try:
        global games, BOT_INSTANCE
        if BOT_INSTANCE is None: BOT_INSTANCE = bot
        
        # User Data Extraction
        user_id = data.get('userid', user)
        avatar_file = data.get("avatar")
        # Howdies Avatar URL format
        avatar_url = f"https://cdn.howdies.app/avatar?image={avatar_file}" if avatar_file else None
        
        cmd_clean = command.lower().strip()

        # THREAD-SAFE ACCESS
        with games_lock: 
            current_game = games.get(room_id)

        # 1. START NEW GAME
        if cmd_clean == "tic":
            if current_game:
                bot.send_message(room_id, "⚠️ Game running! Type 'stop' to end.")
                return True
            
            with games_lock: 
                games[room_id] = TicTacToe(room_id, user_id, user, avatar_url)
            
            bot.send_message(room_id, f"🎮 **Tic-Tac-Toe Pro**\n@{user}, Choose Mode:\n1️⃣ Single Player (vs Bot)\n2️⃣ Multiplayer (1v1)")
            return True

        # 2. STOP COMMAND
        if cmd_clean == "stop" and current_game:
            with games_lock: del games[room_id]
            bot.send_message(room_id, "🛑 Game Stopped.")
            return True

        # 3. GAMEPLAY LOGIC
        if current_game:
            game = current_game
            is_p1 = str(user_id) == str(game.p1_id)
            
            # PHASE 1: MODE SELECTION
            if game.state == 'setup_mode' and is_p1:
                if cmd_clean == "1":
                    game.mode = 1; game.p2_name = "Bot"; game.p2_id = "BOT"; game.state = 'setup_bet'; game.touch()
                    bot.send_message(room_id, "💰 Choose Bet:\n1️⃣ Free (Win 500 XP)\n2️⃣ Bet 100 Coins (Win 700)")
                    return True
                elif cmd_clean == "2":
                    game.mode = 2; game.state = 'setup_bet'; game.touch()
                    bot.send_message(room_id, "💰 Choose Bet:\n1️⃣ Friendly (No Coins)\n2️⃣ Bet 100 Coins")
                    return True
            
            # PHASE 2: BETTING
            elif game.state == 'setup_bet' and is_p1:
                if cmd_clean in ["1", "2"]:
                    game.bet = 0 if cmd_clean == "1" else 100; game.touch()
                    
                    # Deduct Entry Fee (P1)
                    if game.bet > 0: 
                        add_game_result(game.p1_id, game.p1_name, "tictactoe", -game.bet, is_win=False)
                    
                    if game.mode == 1:
                        game.state = 'playing'
                        # Use UTILS for fast upload
                        img = draw_pro_board(game.board, game.p1_name, "Bot", game.turn)
                        link = utils.upload(bot, img)
                        
                        # Note: DM removed as requested
                        bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Game Start"})
                    else:
                        game.state = 'waiting_join'
                        bot.send_message(room_id, f"⚔️ **Lobby Open!**\nEntry: {game.bet} Coins\nType **'join'** to play vs @{game.p1_name}")
                    return True
            
            # PHASE 3: JOINING
            elif game.state == 'waiting_join':
                if cmd_clean in ["j", "join"]:
                    if is_p1: return True # Self join prevention
                    
                    game.p2_id = user_id; game.p2_name = user; game.p2_avatar = avatar_url
                    game.touch()
                    
                    # Deduct Entry Fee (P2)
                    if game.bet > 0: 
                        add_game_result(game.p2_id, game.p2_name, "tictactoe", -game.bet, is_win=False)
                    
                    game.state = 'playing'
                    img = draw_pro_board(game.board, game.p1_name, game.p2_name, game.turn)
                    link = utils.upload(bot, img)
                    
                    if link: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "VS"})
                    return True
            
            # PHASE 4: MOVING (1-9)
            elif game.state == 'playing':
                if cmd_clean.isdigit() and 1 <= int(cmd_clean) <= 9:
                    idx = int(cmd_clean) - 1
                    
                    # Turn Validation
                    curr_id = game.p1_id if game.turn == 'X' else game.p2_id
                    if str(user_id) != str(curr_id): return False # Not your turn
                    
                    if game.board[idx]: 
                        bot.send_message(room_id, "🚫 Space Occupied!")
                        return True
                    
                    game.touch()
                    game.board[idx] = game.turn
                    win_result = game.check_win()
                    
                    # --- WIN/DRAW HANDLER ---
                    if win_result:
                        # Determine Winner Data
                        if win_result == 'draw':
                            bot.send_message(room_id, "🤝 **Draw Game!** Money Refunded.")
                            if game.bet > 0:
                                add_game_result(game.p1_id, game.p1_name, "tictactoe", game.bet, False)
                                if game.mode == 2: 
                                    add_game_result(game.p2_id, game.p2_name, "tictactoe", game.bet, False)
                        else:
                            # Winner ID/Name mapping
                            w_id = game.p1_id if win_result=='X' else game.p2_id
                            w_nm = game.p1_name if win_result=='X' else game.p2_name
                            w_av = game.p1_avatar if win_result=='X' else game.p2_avatar
                            
                            # Reward Logic
                            reward = 0
                            if game.mode == 1: reward = 500 if game.bet == 0 else 700
                            else: reward = game.bet * 2 if game.bet > 0 else 0
                            
                            # DB Update
                            if reward > 0: add_game_result(w_id, w_nm, "tictactoe", reward, is_win=True)
                            else: add_game_result(w_id, w_nm, "tictactoe", 0, is_win=True)
                            
                            # GENERATE PRO WINNER CARD (Using Utils)
                            card = draw_winner_card(w_nm, win_result, w_av)
                            clink = utils.upload(bot, card)
                            
                            if clink: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": clink, "text": "Win"})
                            bot.send_message(room_id, f"🏆 **Victory!** @{w_nm} takes the crown!")

                        # CLEANUP
                        with games_lock: del games[room_id]
                        return True

                    # --- NEXT TURN ---
                    game.turn = 'O' if game.turn == 'X' else 'X'
                    
                    # BOT AI MOVE
                    if game.mode == 1 and game.turn == 'O':
                        time.sleep(1) # Fake thinking
                        b_idx = game.bot_move()
                        if b_idx is not None:
                            game.board[b_idx] = 'O'
                            if game.check_win() == 'O':
                                # Bot Wins
                                img = draw_pro_board(game.board, game.p1_name, "Bot", 'O')
                                link = utils.upload(bot, img)
                                if link: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "BotWin"})
                                bot.send_message(room_id, "🤖 **Bot Wins!** Better luck next time.")
                                with games_lock: del games[room_id]
                                return True
                            game.turn = 'X'
                    
                    # Redraw Board for Next Turn
                    p2_disp = "Bot" if game.mode == 1 else game.p2_name
                    img = draw_pro_board(game.board, game.p1_name, p2_disp, game.turn)
                    link = utils.upload(bot, img)
                    if link: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Turn"})
                    return True
        return False
    except Exception as e:
        bot.send_message(room_id, f"⚠️ Fatal Error: {str(e)}")
        traceback.print_exc()
        return False
