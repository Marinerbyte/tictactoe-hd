import time
import random
import requests
import io
import sys
import os
import threading
import traceback
from PIL import Image, ImageDraw, ImageFont

# Import DB safely
try:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    import db
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
    print("[TicTacToe] Setup Complete.")

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
    font_paths = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "arial.ttf"]
    for path in font_paths:
        try: return ImageFont.truetype(path, size)
        except: continue
    return ImageFont.load_default()

def update_coins(user_id, amount):
    """Coins update karta hai"""
    conn = db.get_connection()
    if not conn: return
    cur = conn.cursor()
    try:
        try: cur.execute("INSERT INTO users (user_id, username, global_score, wins) VALUES (%s, %s, 0, 0) ON CONFLICT (user_id) DO NOTHING", (user_id, user_id))
        except: cur.execute("INSERT OR IGNORE INTO users (user_id, username, global_score, wins) VALUES (?, ?, 0, 0)", (user_id, user_id))
        
        query = "UPDATE users SET global_score = global_score + %s WHERE user_id = %s"
        if not db.DATABASE_URL.startswith("postgres"): query = "UPDATE users SET global_score = global_score + ? WHERE user_id = ?"
        cur.execute(query, (amount, user_id))
        conn.commit()
    except: pass
    finally: conn.close()

def add_win(user_id):
    """Wins counter badhata hai (+1)"""
    conn = db.get_connection()
    if not conn: return
    cur = conn.cursor()
    try:
        try: cur.execute("INSERT INTO users (user_id, username, global_score, wins) VALUES (%s, %s, 0, 0) ON CONFLICT (user_id) DO NOTHING", (user_id, user_id))
        except: cur.execute("INSERT OR IGNORE INTO users (user_id, username, global_score, wins) VALUES (?, ?, 0, 0)", (user_id, user_id))
        
        query = "UPDATE users SET wins = wins + 1 WHERE user_id = %s"
        if not db.DATABASE_URL.startswith("postgres"): query = "UPDATE users SET wins = wins + 1 WHERE user_id = ?"
        cur.execute(query, (user_id,))
        conn.commit()
    except: pass
    finally: conn.close()

def upload_image(bot, image, room_id):
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    url = "https://api.howdies.app/api/upload"
    try:
        uid = bot.user_id if bot.user_id else 0
        files = {'file': ('tic.png', img_byte_arr, 'image/png')}
        data = {'token': bot.token, 'uploadType': 'image', 'UserID': uid}
        r = requests.post(url, files=files, data=data)
        res = r.json()
        return res.get('url') or res.get('data', {}).get('url')
    except: return None

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
        rad = 60
        d.ellipse([(cx-rad, cy-rad), (cx+rad, cy+rad)], fill=(60, 60, 60), outline="white", width=4)
        initial = username[0].upper()
        fnt_av = get_font(70)
        bbox = d.textbbox((0, 0), initial, font=fnt_av)
        d.text((cx - (bbox[2]-bbox[0])/2, cy - (bbox[3]-bbox[1])/1.2), initial, fill="white", font=fnt_av)

    fnt_name, fnt_title = get_font(45), get_font(30)
    bbox = d.textbbox((0, 0), f"@{username}", font=fnt_name)
    d.text(((W - (bbox[2]-bbox[0]))/2, 220), f"@{username}", fill="white", font=fnt_name)
    bbox = d.textbbox((0, 0), "🏆 WINNER 🏆", font=fnt_title)
    d.text(((W - (bbox[2]-bbox[0]))/2, 290), "🏆 WINNER 🏆", fill="yellow", font=fnt_title)
    
    sym = "❌" if winner_symbol == 'X' else "⭕"
    d.text((W//2 - 15, 340), sym, fill="white", font=get_font(30))
    return img

def draw_board(board_state):
    size = 400
    cell = size // 3
    img = Image.new('RGB', (size, size), color=(20, 20, 25)) 
    d = ImageDraw.Draw(img)
    fnt_num = get_font(60)
    for i in range(1, 3):
        d.line([(cell * i, 15), (cell * i, size - 15)], fill=(100, 100, 100), width=4)
        d.line([(15, cell * i), (size - 15, cell * i)], fill=(100, 100, 100), width=4)
    for i in range(9):
        row, col = i // 3, i % 3
        x, y = col * cell, row * cell
        cx, cy = x + cell // 2, y + cell // 2
        val = board_state[i]
        if val is None:
            num_str = str(i+1)
            bbox = d.textbbox((0, 0), num_str, font=fnt_num)
            d.text((cx - (bbox[2]-bbox[0])/2, cy - (bbox[3]-bbox[1])/1.5), num_str, font=fnt_num, fill=(50, 50, 60)) 
        elif val == 'X':
            offset = 30
            d.line([(x+offset, y+offset), (x+cell-offset, y+cell-offset)], fill=(255, 50, 50), width=15)
            d.line([(x+cell-offset, y+offset), (x+offset, y+cell-offset)], fill=(255, 50, 50), width=15)
        elif val == 'O':
            offset = 30
            d.ellipse([(x+offset, y+offset), (x+cell-offset, y+cell-offset)], outline=(50, 150, 255), width=15)
    return img

class TicTacToe:
    def __init__(self, room_id, creator_id, creator_avatar=None):
        self.room_id = room_id
        self.p1_name = creator_id
        self.p1_avatar = creator_avatar
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
            if self.board[a] and self.board[a] == self.board[b] == self.board[c]: return self.board[a]
        if None not in self.board: return 'draw'
        return None
    def bot_move(self):
        empty = [i for i, x in enumerate(self.board) if x is None]
        return random.choice(empty) if empty else None

# --- MAIN HANDLER ---
def handle_command(bot, command, room_id, user, args, avatar_url=None, **kwargs):
    try:
        global games, BOT_INSTANCE
        if BOT_INSTANCE is None: BOT_INSTANCE = bot
        
        with games_lock: current_game = games.get(room_id)
        cmd_clean = command.lower().strip()

        if cmd_clean == "tic":
            if current_game:
                bot.send_message(room_id, "⚠️ Game running! Type 'stop'.")
                return True
            with games_lock: games[room_id] = TicTacToe(room_id, user, avatar_url)
            bot.send_message(room_id, f"🎮 **Tic-Tac-Toe**\n@{user}, Choose:\n1️⃣ Single\n2️⃣ Multi")
            return True

        if cmd_clean == "stop" and current_game:
            with games_lock: del games[room_id]
            bot.send_message(room_id, "🛑 Stopped.")
            return True

        if current_game:
            game = current_game
            if user == game.p1_name and avatar_url: game.p1_avatar = avatar_url
            if user == game.p2_name and avatar_url: game.p2_avatar = avatar_url

            # 1. SETUP - MODE SELECTION
            if game.state == 'setup_mode' and user == game.p1_name:
                if cmd_clean == "1":
                    game.mode = 1; game.p2_name = "Bot"; game.state = 'setup_bet'; game.touch()
                    # Updated Text for Single Player
                    bot.send_message(room_id, "💰 Reward Mode?\n1️⃣ Free Play (Win 500)\n2️⃣ Bet 100 (Win 700)")
                    return True
                elif cmd_clean == "2":
                    game.mode = 2; game.state = 'setup_bet'; game.touch()
                    # Updated Text for Multi Player
                    bot.send_message(room_id, "💰 Bet Amount?\n1️⃣ Fun (No Reward)\n2️⃣ Bet 100 Coins")
                    return True
            
            # 2. BET
            elif game.state == 'setup_bet' and user == game.p1_name:
                if cmd_clean in ["1", "2"]:
                    game.bet = 0 if cmd_clean == "1" else 100; game.touch()
                    if game.bet > 0: update_coins(game.p1_name, -game.bet)
                    
                    if game.mode == 1:
                        game.state = 'playing'
                        img = draw_board(game.board)
                        link = upload_image(bot, img, room_id)
                        bot.send_message(room_id, f"🔥 vs Bot\nType **1-9**")
                        if link: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Board", "id": "gm_s"})
                    else:
                        game.state = 'waiting_join'
                        bot.send_message(room_id, f"⚔️ Waiting...\nType **'j'** to join!")
                    return True
            
            # 3. JOIN
            elif game.state == 'waiting_join':
                if cmd_clean in ["j", "join"]:
                    if user == game.p1_name:
                        bot.send_message(room_id, "⚠️ Wait for opponent!")
                        return True
                    game.p2_name = user; game.p2_avatar = avatar_url; game.touch()
                    if game.bet > 0: update_coins(game.p2_name, -game.bet)
                    game.state = 'playing'
                    img = draw_board(game.board)
                    link = upload_image(bot, img, room_id)
                    bot.send_message(room_id, f"🥊 @{game.p1_name} vs @{game.p2_name}\n@{game.p1_name} turn!")
                    if link: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Board", "id": "gm_s"})
                    return True
            
            # 4. PLAYING
            elif game.state == 'playing':
                if cmd_clean.isdigit() and 1 <= int(cmd_clean) <= 9:
                    idx = int(cmd_clean) - 1
                    curr_p = game.p1_name if game.turn == 'X' else game.p2_name
                    if user != curr_p: return False
                    if game.board[idx]: 
                        bot.send_message(room_id, "🚫 Taken!")
                        return True
                    
                    game.touch()
                    game.board[idx] = game.turn
                    win = game.check_win()
                    
                    if win:
                        w_user = game.p1_name if win=='X' else game.p2_name
                        w_avatar = game.p1_avatar if win=='X' else game.p2_avatar
                        
                        # --- WIN LOGIC ---
                        if win == 'draw':
                            bot.send_message(room_id, "🤝 Draw!")
                            if game.bet > 0:
                                update_coins(game.p1_name, game.bet)
                                if game.mode==2: update_coins(game.p2_name, game.bet)
                        else:
                            # 1. Add Win to DB
                            add_win(w_user)

                            # 2. Calculate Reward
                            reward_msg = ""
                            if game.mode == 1:
                                # Single Player Reward
                                total = 500
                                if game.bet > 0: total = 700 # 500 Bonus + 200 Winnings
                                update_coins(w_user, total)
                                reward_msg = f"🎉 @{w_user} Won {total} coins!"
                            else:
                                # Multiplayer Reward
                                pot = game.bet * 2
                                if pot > 0:
                                    update_coins(w_user, pot)
                                    reward_msg = f"🎉 @{w_user} Won {pot} coins!"
                                else:
                                    reward_msg = f"🎉 @{w_user} Won! (No Bet)"

                            # 3. Draw Card & Send
                            card = draw_winner_card(w_user, win, w_avatar)
                            clink = upload_image(bot, card, room_id)
                            if clink: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": clink, "text": "Win", "id": "gm_w"})
                            bot.send_message(room_id, reward_msg)
                        
                        with games_lock: del games[room_id]
                        return True

                    game.turn = 'O' if game.turn == 'X' else 'X'
                    if game.mode == 1 and game.turn == 'O':
                        b_idx = game.bot_move()
                        if b_idx is not None:
                            game.board[b_idx] = 'O'
                            win = game.check_win()
                            if win:
                                img = draw_board(game.board)
                                link = upload_image(bot, img, room_id)
                                if link: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "BotWin", "id": "gm_be"})
                                bot.send_message(room_id, "🤖 Bot Wins!")
                                with games_lock: del games[room_id]
                                return True
                            game.turn = 'X'
                    
                    img = draw_board(game.board)
                    link = upload_image(bot, img, room_id)
                    nxt = game.p1_name if game.turn=='X' else game.p2_name
                    if link: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": f"Turn: {nxt}", "id": "gm_u"})
                    return True
        return False
    except Exception as e:
        bot.send_message(room_id, f"⚠️ Error: {str(e)}")
        traceback.print_exc()
        return False
