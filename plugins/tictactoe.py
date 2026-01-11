import time
import random
import requests
import io
import sys
import os
from PIL import Image, ImageDraw, ImageFont

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import db

games = {} 

# --- Helper: Fonts ---
def get_font(size):
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "arial.ttf"
    ]
    for path in font_paths:
        try:
            return ImageFont.truetype(path, size)
        except: continue
    return ImageFont.load_default()

# --- Helper: DB ---
def update_coins(user_id, amount):
    conn = db.get_connection()
    if not conn: return
    cur = conn.cursor()
    try:
        try:
            cur.execute("INSERT INTO users (user_id, username, global_score) VALUES (%s, %s, 0) ON CONFLICT (user_id) DO NOTHING", (user_id, user_id))
        except:
            cur.execute("INSERT OR IGNORE INTO users (user_id, username, global_score) VALUES (?, ?, 0)", (user_id, user_id))
        
        query = "UPDATE users SET global_score = global_score + %s WHERE user_id = %s"
        if not db.DATABASE_URL.startswith("postgres"):
            query = "UPDATE users SET global_score = global_score + ? WHERE user_id = ?"
        cur.execute(query, (amount, user_id))
        conn.commit()
    except: pass
    finally: conn.close()

# --- Helper: Upload ---
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
    except Exception as e:
        print(f"Upload Fail: {e}")
        return None

# --- NEW: Download & Process Avatar ---
def get_avatar_img(url):
    try:
        if not url: return None
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            img = Image.open(io.BytesIO(res.content)).convert("RGBA")
            # Resize
            img = img.resize((120, 120))
            
            # Make Circle
            mask = Image.new('L', (120, 120), 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, 120, 120), fill=255)
            
            output = Image.new('RGBA', (120, 120), (0,0,0,0))
            output.paste(img, (0,0), mask)
            return output
    except Exception as e:
        print(f"Avatar Fetch Error: {e}")
    return None

# --- Draw Winner Card (With Real DP) ---
def draw_winner_card(username, winner_symbol, avatar_url=None):
    W, H = 400, 400
    bg = (25, 10, 10) if winner_symbol == 'X' else (10, 10, 25)
    img = Image.new('RGB', (W, H), color=bg)
    d = ImageDraw.Draw(img)
    
    col = (255, 60, 60) if winner_symbol == 'X' else (60, 100, 255)
    d.rectangle([(10, 10), (W-10, H-10)], outline=col, width=6)

    # 1. Try Real Avatar
    real_avatar = get_avatar_img(avatar_url)
    cx, cy = W//2, 130
    
    if real_avatar:
        # Paste Real Avatar (Centered)
        img.paste(real_avatar, (cx - 60, cy - 60), real_avatar)
        d.ellipse([(cx-60, cy-60), (cx+60, cy+60)], outline="white", width=4)
    else:
        # Fallback: Initials
        rad = 60
        d.ellipse([(cx-rad, cy-rad), (cx+rad, cy+rad)], fill=(60, 60, 60), outline="white", width=4)
        initial = username[0].upper()
        fnt_av = get_font(70)
        bbox = d.textbbox((0, 0), initial, font=fnt_av)
        d.text((cx - (bbox[2]-bbox[0])/2, cy - (bbox[3]-bbox[1])/1.2), initial, fill="white", font=fnt_av)

    # Text Info
    fnt_name = get_font(45)
    bbox = d.textbbox((0, 0), f"@{username}", font=fnt_name)
    d.text(((W - (bbox[2]-bbox[0]))/2, 220), f"@{username}", fill="white", font=fnt_name)

    fnt_title = get_font(30)
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
        self.p1_avatar = creator_avatar # Store Avatar
        self.p2_name = None
        self.p2_avatar = None
        self.board = [None]*9
        self.turn = 'X'
        self.state = 'setup_mode'
        self.mode = None
        self.bet = 0
        self.last_interaction = time.time()
    def check_win(self):
        wins = [(0,1,2), (3,4,5), (6,7,8), (0,3,6), (1,4,7), (2,5,8), (0,4,8), (2,4,6)]
        for a, b, c in wins:
            if self.board[a] and self.board[a] == self.board[b] == self.board[c]: return self.board[a]
        if None not in self.board: return 'draw'
        return None
    def bot_move(self):
        empty = [i for i, x in enumerate(self.board) if x is None]
        return random.choice(empty) if empty else None

# --- Handler with Avatar Support ---
def handle_command(bot, command, room_id, user, args, avatar_url=None):
    global games
    current_game = games.get(room_id)

    if command == "tic":
        if current_game:
            bot.send_message(room_id, "⚠️ Game running!")
            return True
        # Create game and save Creator's Avatar
        games[room_id] = TicTacToe(room_id, user, avatar_url)
        bot.send_message(room_id, f"🎮 **Tic-Tac-Toe**\n@{user}, Choose:\n1️⃣ Single\n2️⃣ Multi")
        return True

    if command == "stop" and current_game:
        del games[room_id]
        bot.send_message(room_id, "🛑 Stopped.")
        return True

    if current_game:
        game = current_game
        
        # Update Avatar if not set (Just in case they played a move and we caught it now)
        if user == game.p1_name and avatar_url and not game.p1_avatar:
            game.p1_avatar = avatar_url
        if user == game.p2_name and avatar_url and not game.p2_avatar:
            game.p2_avatar = avatar_url

        if game.state == 'setup_mode' and user == game.p1_name:
            if command == "1":
                game.mode = 1; game.p2_name = "Bot"; game.state = 'setup_bet'; game.last_interaction = time.time()
                bot.send_message(room_id, "💰 Bet?\n1️⃣ Fun (0)\n2️⃣ 100 Coins")
                return True
            elif command == "2":
                game.mode = 2; game.state = 'setup_bet'; game.last_interaction = time.time()
                bot.send_message(room_id, "💰 Bet?\n1️⃣ Fun (0)\n2️⃣ 100 Coins")
                return True
        
        elif game.state == 'setup_bet' and user == game.p1_name:
            if command in ["1", "2"]:
                game.bet = 0 if command == "1" else 100; game.last_interaction = time.time()
                if game.bet > 0: update_coins(game.p1_name, -game.bet)
                
                if game.mode == 1:
                    game.state = 'playing'
                    img = draw_board(game.board)
                    link = upload_image(bot, img, room_id)
                    bot.send_message(room_id, f"🔥 Started vs Bot\nType **1-9**")
                    if link: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Board", "id": "gm_s"})
                else:
                    game.state = 'waiting_join'
                    bot.send_message(room_id, f"⚔️ Waiting...\nType **'j'** to join!")
                return True
        
        elif game.state == 'waiting_join':
            if command == "j" and user != game.p1_name:
                game.p2_name = user
                game.p2_avatar = avatar_url # Save Player 2 Avatar
                game.last_interaction = time.time()
                if game.bet > 0: update_coins(game.p2_name, -game.bet)
                
                game.state = 'playing'
                img = draw_board(game.board)
                link = upload_image(bot, img, room_id)
                bot.send_message(room_id, f"🥊 @{game.p1_name} vs @{game.p2_name}\n@{game.p1_name} turn!")
                if link: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Board", "id": "gm_s"})
                return True
        
        elif game.state == 'playing':
            if command.isdigit() and 1 <= int(command) <= 9:
                idx = int(command) - 1
                curr_p = game.p1_name if game.turn == 'X' else game.p2_name
                if user != curr_p: return False
                if game.board[idx]: 
                    bot.send_message(room_id, "🚫 Taken!")
                    return True
                
                game.last_interaction = time.time()
                game.board[idx] = game.turn
                win = game.check_win()
                
                if win:
                    # Determine Winner Name & Avatar
                    w_user = game.p1_name if win=='X' else game.p2_name
                    w_avatar = game.p1_avatar if win=='X' else game.p2_avatar
                    
                    if win == 'draw':
                        bot.send_message(room_id, "🤝 Draw!")
                        if game.bet > 0:
                            update_coins(game.p1_name, game.bet)
                            if game.mode==2: update_coins(game.p2_name, game.bet)
                    else:
                        pot = game.bet * 2
                        # --- Winner Card with Real DP ---
                        card = draw_winner_card(w_user, win, w_avatar)
                        clink = upload_image(bot, card, room_id)
                        if clink: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": clink, "text": "Win", "id": "gm_w"})
                        bot.send_message(room_id, f"🎉 @{w_user} Won {pot} coins!")
                        if game.bet > 0: update_coins(w_user, pot)
                    
                    del games[room_id]
                    return True

                # Switch Turn Logic
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
                            del games[room_id]
                            return True
                        game.turn = 'X'
                
                img = draw_board(game.board)
                link = upload_image(bot, img, room_id)
                nxt = game.p1_name if game.turn=='X' else game.p2_name
                if link: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": f"Turn: {nxt}", "id": "gm_u"})
                return True
    return False
