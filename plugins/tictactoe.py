import time
import random
import requests
import io
import sys
import os
import threading
import traceback
from PIL import Image, ImageDraw, ImageFont

# --- DB IMPORT (Master Function) ---
try:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from db import add_game_result
except Exception as e:
    print(f"DB Import Error: {e}")

# --- GLOBAL STATE ---
games = {} 
games_lock = threading.Lock()
BOT_INSTANCE = None 

# --- SETUP ---
def setup(bot_ref):
    global BOT_INSTANCE
    BOT_INSTANCE = bot_ref
    print("[TicTacToe] Logic Loaded.")

# --- CLEANER THREAD ---
def game_cleanup_loop():
    while True:
        time.sleep(10)
        now = time.time()
        to_remove = []
        with games_lock:
            for room_id, game in games.items():
                if now - game.last_interaction > 90:
                    to_remove.append(room_id)
        for room_id in to_remove:
            if BOT_INSTANCE:
                try: BOT_INSTANCE.send_message(room_id, "⌛ Game closed due to inactivity.")
                except: pass
            with games_lock:
                if room_id in games: del games[room_id]

if threading.active_count() < 10: 
    threading.Thread(target=game_cleanup_loop, daemon=True).start()

# --- HELPER FUNCTIONS ---
def get_font(size):
    # Try multiple fonts for compatibility
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "arial.ttf"
    ]
    for path in font_paths:
        try: return ImageFont.truetype(path, size)
        except: continue
    return ImageFont.load_default()

def upload_image(bot, image):
    """Uploads in-memory image to Howdies API"""
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    url = "https://api.howdies.app/api/upload"
    try:
        uid = bot.user_id if bot.user_id else 0
        files = {'file': ('tic.png', img_byte_arr, 'image/png')}
        data = {'token': bot.token, 'uploadType': 'image', 'UserID': uid}
        r = requests.post(url, files=files, data=data, timeout=10)
        res = r.json()
        return res.get('url') or res.get('data', {}).get('url')
    except: return None

# --- VISUALS ---
def get_avatar_img(url):
    try:
        if not url: return None
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            img = Image.open(io.BytesIO(res.content)).convert("RGBA")
            img = img.resize((120, 120))
            mask = Image.new('L', (120, 120), 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, 120, 120), fill=255)
            output = Image.new('RGBA', (120, 120), (0,0,0,0))
            output.paste(img, (0,0), mask)
            return output
    except: return None

def draw_winner_card(username, winner_symbol, avatar_url=None):
    W, H = 400, 400
    bg = (25, 10, 10) if winner_symbol == 'X' else (10, 10, 25)
    img = Image.new('RGB', (W, H), color=bg)
    d = ImageDraw.Draw(img)
    col = (255, 60, 60) if winner_symbol == 'X' else (60, 100, 255)
    d.rectangle([(10, 10), (W-10, H-10)], outline=col, width=6)

    real_avatar = get_avatar_img(avatar_url)
    cx, cy = W//2, 130
    if real_avatar:
        img.paste(real_avatar, (cx - 60, cy - 60), real_avatar)
        d.ellipse([(cx-60, cy-60), (cx+60, cy+60)], outline="white", width=4)
    else:
        d.ellipse([(cx-60, cy-60), (cx+60, cy+60)], fill=(60, 60, 60), outline="white", width=4)
        initial = username[0].upper()
        fnt_av = get_font(70)
        d.text((cx, cy-10), initial, fill="white", font=fnt_av, anchor="mm")

    fnt_name = get_font(40)
    d.text((W//2, 230), f"@{username}", fill="white", font=fnt_name, anchor="mm")
    fnt_title = get_font(30)
    d.text((W//2, 290), "🏆 WINNER 🏆", fill="yellow", font=fnt_title, anchor="mm")
    
    return img

def draw_board(board_state):
    size = 400
    cell = size // 3
    img = Image.new('RGB', (size, size), color=(20, 20, 25)) 
    d = ImageDraw.Draw(img)
    fnt_num = get_font(60)
    
    # Grid
    for i in range(1, 3):
        d.line([(cell * i, 15), (cell * i, size - 15)], fill=(100, 100, 100), width=4)
        d.line([(15, cell * i), (size - 15, cell * i)], fill=(100, 100, 100), width=4)
    
    # Symbols
    for i in range(9):
        row, col = i // 3, i % 3
        x, y = col * cell, row * cell
        cx, cy = x + cell // 2, y + cell // 2
        val = board_state[i]
        
        if val is None:
            d.text((cx, cy), str(i+1), font=fnt_num, fill=(50, 50, 60), anchor="mm") 
        elif val == 'X':
            offset = 30
            d.line([(x+offset, y+offset), (x+cell-offset, y+cell-offset)], fill=(255, 50, 50), width=15)
            d.line([(x+cell-offset, y+offset), (x+offset, y+cell-offset)], fill=(255, 50, 50), width=15)
        elif val == 'O':
            offset = 30
            d.ellipse([(x+offset, y+offset), (x+cell-offset, y+cell-offset)], outline=(50, 150, 255), width=15)
    return img

# --- GAME LOGIC ---
class TicTacToe:
    def __init__(self, room_id, creator_id, creator_name, creator_avatar=None):
        self.room_id = room_id
        # Store IDs separately for DB tracking
        self.p1_id = creator_id
        self.p1_name = creator_name
        self.p1_avatar = creator_avatar
        
        self.p2_id = None
        self.p2_name = None
        self.p2_avatar = None
        
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
        # Try to win
        for m in empty:
            self.board[m] = 'O'
            if self.check_win() == 'O': self.board[m] = None; return m
            self.board[m] = None
        # Block X
        for m in empty:
            self.board[m] = 'X'
            if self.check_win() == 'X': self.board[m] = None; return m
            self.board[m] = None
        if 4 in empty: return 4
        return random.choice(empty)

# --- MAIN HANDLER ---
def handle_command(bot, command, room_id, user, args, data):
    try:
        global games, BOT_INSTANCE
        if BOT_INSTANCE is None: BOT_INSTANCE = bot
        
        # EXTRACT ID Correctly
        user_id = data.get('userid', user)
        
        avatar_file = data.get("avatar")
        avatar_url = f"https://cdn.howdies.app/avatar?image={avatar_file}" if avatar_file else None
        cmd_clean = command.lower().strip()

        with games_lock: current_game = games.get(room_id)

        # 1. NEW GAME
        if cmd_clean == "tic":
            if current_game:
                bot.send_message(room_id, "⚠️ Game running! Type 'stop'.")
                return True
            with games_lock: games[room_id] = TicTacToe(room_id, user_id, user, avatar_url)
            bot.send_message(room_id, f"🎮 **Tic-Tac-Toe**\n@{user}, Choose:\n1️⃣ Single\n2️⃣ Multi")
            return True

        # 2. STOP
        if cmd_clean == "stop" and current_game:
            with games_lock: del games[room_id]
            bot.send_message(room_id, "🛑 Stopped.")
            return True

        # 3. GAMEPLAY
        if current_game:
            game = current_game
            # Identify Player
            is_p1 = str(user_id) == str(game.p1_id)
            
            # SETUP
            if game.state == 'setup_mode' and is_p1:
                if cmd_clean == "1":
                    game.mode = 1; game.p2_name = "Bot"; game.p2_id = "BOT"; game.state = 'setup_bet'; game.touch()
                    bot.send_message(room_id, "💰 Reward Mode?\n1️⃣ Free Play (Win 500)\n2️⃣ Bet 100 (Win 700)")
                    return True
                elif cmd_clean == "2":
                    game.mode = 2; game.state = 'setup_bet'; game.touch()
                    bot.send_message(room_id, "💰 Bet Amount?\n1️⃣ Fun (No Reward)\n2️⃣ Bet 100 Coins")
                    return True
            
            # BET
            elif game.state == 'setup_bet' and is_p1:
                if cmd_clean in ["1", "2"]:
                    game.bet = 0 if cmd_clean == "1" else 100; game.touch()
                    
                    # Deduct Entry Fee using MASTER FUNCTION
                    if game.bet > 0: 
                        add_game_result(game.p1_id, game.p1_name, "tictactoe", -game.bet, is_win=False)
                    
                    if game.mode == 1:
                        game.state = 'playing'
                        img = draw_board(game.board)
                        link = upload_image(bot, img)
                        bot.send_message(room_id, f"🔥 vs Pro Bot 🤖\nType **1-9**")
                        if link: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Board", "id": "g_s"})
                    else:
                        game.state = 'waiting_join'
                        bot.send_message(room_id, f"⚔️ Waiting...\nType **'j'** to join!")
                    return True
            
            # JOIN
            elif game.state == 'waiting_join':
                if cmd_clean in ["j", "join"]:
                    if is_p1: return True # Cannot join own game
                    
                    # Register Player 2
                    game.p2_id = user_id
                    game.p2_name = user
                    game.p2_avatar = avatar_url
                    game.touch()
                    
                    # Deduct Entry Fee P2
                    if game.bet > 0: 
                        add_game_result(game.p2_id, game.p2_name, "tictactoe", -game.bet, is_win=False)
                    
                    game.state = 'playing'
                    img = draw_board(game.board)
                    link = upload_image(bot, img)
                    bot.send_message(room_id, f"🥊 @{game.p1_name} vs @{game.p2_name}\n@{game.p1_name} turn!")
                    if link: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Board", "id": "g_j"})
                    return True
            
            # PLAY
            elif game.state == 'playing':
                if cmd_clean.isdigit() and 1 <= int(cmd_clean) <= 9:
                    idx = int(cmd_clean) - 1
                    
                    # Check Turn
                    curr_id = game.p1_id if game.turn == 'X' else game.p2_id
                    if str(user_id) != str(curr_id): return False
                    if game.board[idx]: 
                        bot.send_message(room_id, "🚫 Taken!")
                        return True
                    
                    game.touch()
                    game.board[idx] = game.turn
                    win = game.check_win()
                    
                    # WIN LOGIC
                    if win:
                        w_id = game.p1_id if win=='X' else game.p2_id
                        w_nm = game.p1_name if win=='X' else game.p2_name
                        w_av = game.p1_avatar if win=='X' else game.p2_avatar
                        
                        if win == 'draw':
                            bot.send_message(room_id, "🤝 Draw! Coins Refunded.")
                            if game.bet > 0:
                                add_game_result(game.p1_id, game.p1_name, "tictactoe", game.bet, False)
                                if game.mode == 2: 
                                    add_game_result(game.p2_id, game.p2_name, "tictactoe", game.bet, False)
                        else:
                            # Calculate Reward
                            reward = 0
                            if game.mode == 1: 
                                reward = 500 if game.bet == 0 else 700
                            else:
                                reward = game.bet * 2 if game.bet > 0 else 0
                            
                            # SAVE WIN (Master Function)
                            if reward > 0:
                                add_game_result(w_id, w_nm, "tictactoe", reward, is_win=True)
                            else:
                                # Just log the win count, 0 coins
                                add_game_result(w_id, w_nm, "tictactoe", 0, is_win=True)
                            
                            msg_text = f"🎉 @{w_nm} Won {reward} Coins!" if reward > 0 else f"🎉 @{w_nm} Won!"
                            
                            card = draw_winner_card(w_nm, win, w_av)
                            clink = upload_image(bot, card)
                            if clink: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": clink, "text": "Win", "id": "g_w"})
                            bot.send_message(room_id, msg_text)

                        with games_lock: del games[room_id]
                        return True

                    game.turn = 'O' if game.turn == 'X' else 'X'
                    
                    # BOT AUTO MOVE
                    if game.mode == 1 and game.turn == 'O':
                        b_idx = game.bot_move()
                        if b_idx is not None:
                            game.board[b_idx] = 'O'
                            if game.check_win() == 'O':
                                img = draw_board(game.board)
                                link = upload_image(bot, img)
                                if link: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "BotWin", "id": "g_be"})
                                bot.send_message(room_id, "🤖 Pro Bot Wins!")
                                with games_lock: del games[room_id]
                                return True
                            game.turn = 'X'
                    
                    img = draw_board(game.board)
                    link = upload_image(bot, img)
                    nxt = game.p1_name if game.turn=='X' else game.p2_name
                    if link: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": f"Turn: {nxt}", "id": "g_u"})
                    return True
        return False
    except Exception as e:
        bot.send_message(room_id, f"⚠️ Error: {str(e)}")
        traceback.print_exc()
        return False
