import time
import random
import requests
import io
import sys
import os
from PIL import Image, ImageDraw

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import db

games = {} 

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

# --- FIXED UPLOAD FUNCTION WITH ERROR REPORTING ---
def upload_image(bot, image, room_id):
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    
    url = "https://api.howdies.app/api/upload"
    try:
        # Use Numeric User ID if available, else fallback to 0
        uid = bot.user_id if bot.user_id else 0
        
        files = {'file': ('tic.png', img_byte_arr, 'image/png')}
        data = {
            'token': bot.token,
            'uploadType': 'image',
            'UserID': uid 
        }
        
        r = requests.post(url, files=files, data=data)
        
        # Log response for debugging
        print(f"Upload Status: {r.status_code}, Response: {r.text}")

        res = r.json()
        link = res.get('url') or res.get('data', {}).get('url')
            
        if not link:
            # Agar upload fail ho, to chat me error bhejo (Sirf debugging ke liye)
            bot.send_message(room_id, f"⚠️ Upload Error: API returned {r.status_code}")
            
        return link
    except Exception as e:
        bot.send_message(room_id, f"⚠️ Upload Failed: {str(e)}")
        return None

def draw_board(board_state):
    size = 400
    cell = size // 3
    img = Image.new('RGB', (size, size), color=(20, 20, 20)) 
    d = ImageDraw.Draw(img)
    for i in range(1, 3):
        d.line([(cell * i, 10), (cell * i, size - 10)], fill=(255, 255, 255), width=5)
        d.line([(10, cell * i), (size - 10, cell * i)], fill=(255, 255, 255), width=5)
    for i in range(9):
        row, col = i // 3, i % 3
        x, y = col * cell, row * cell
        cx, cy = x + cell // 2, y + cell // 2
        val = board_state[i]
        if val is None:
            d.text((cx - 5, cy - 10), str(i+1), fill=(60, 60, 60)) 
        elif val == 'X':
            offset = 35
            d.line([(x+offset, y+offset), (x+cell-offset, y+cell-offset)], fill=(255, 40, 40), width=12)
            d.line([(x+cell-offset, y+offset), (x+offset, y+cell-offset)], fill=(255, 40, 40), width=12)
        elif val == 'O':
            offset = 35
            d.ellipse([(x+offset, y+offset), (x+cell-offset, y+cell-offset)], outline=(40, 100, 255), width=12)
    return img

def draw_winner_card(username, winner_symbol):
    W, H = 500, 250
    bg = (30, 10, 10) if winner_symbol == 'X' else (10, 10, 30)
    img = Image.new('RGB', (W, H), color=bg)
    d = ImageDraw.Draw(img)
    col = (255, 50, 50) if winner_symbol == 'X' else (50, 100, 255)
    d.rectangle([(10, 10), (W-10, H-10)], outline=col, width=5)
    d.ellipse([(40, 50), (160, 170)], fill=(50, 50, 50), outline="white", width=3)
    d.text((85, 95), username[:2].upper(), fill="white")
    d.text((200, 80), "👑 WINNER 👑", fill="yellow")
    d.text((200, 110), f"@{username}", fill="white")
    d.text((380, 80), "X" if winner_symbol=='X' else "O", fill=col)
    return img

class TicTacToe:
    def __init__(self, room_id, creator_id):
        self.room_id, self.p1_name = room_id, creator_id
        self.p2_name, self.board, self.turn = None, [None]*9, 'X'
        self.state, self.mode, self.bet = 'setup_mode', None, 0
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

def handle_command(bot, command, room_id, user, args):
    global games
    current_game = games.get(room_id)

    if command == "tic":
        if current_game:
            bot.send_message(room_id, "⚠️ Game running! Type 'stop'.")
            return True
        games[room_id] = TicTacToe(room_id, user)
        bot.send_message(room_id, f"🎮 **Tic-Tac-Toe**\n@{user}, Choose Mode:\n1️⃣ Single\n2️⃣ Multi")
        return True

    if command == "stop" and current_game:
        del games[room_id]
        bot.send_message(room_id, "🛑 Stopped.")
        return True

    if current_game:
        game = current_game
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
                    bot.send_message(room_id, f"🔥 Started vs Bot (Bet: {game.bet})\nType **1-9**")
                    if link: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Board", "id": "gm_s"})
                else:
                    game.state = 'waiting_join'
                    bot.send_message(room_id, f"⚔️ Waiting (Bet: {game.bet})\nType **'j'** to join!")
                return True
        elif game.state == 'waiting_join':
            if command == "j" and user != game.p1_name:
                game.p2_name = user; game.last_interaction = time.time()
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
                    img = draw_board(game.board)
                    link = upload_image(bot, img, room_id)
                    if link: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "End", "id": "gm_e"})
                    if win == 'draw':
                        bot.send_message(room_id, "🤝 Draw! Refunded.")
                        if game.bet > 0:
                            update_coins(game.p1_name, game.bet)
                            if game.mode==2: update_coins(game.p2_name, game.bet)
                    else:
                        w_user = game.p1_name if win=='X' else game.p2_name
                        pot = game.bet * 2
                        card = draw_winner_card(w_user, win)
                        clink = upload_image(bot, card, room_id)
                        if clink: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": clink, "text": "Win", "id": "gm_w"})
                        bot.send_message(room_id, f"🎉 @{w_user} Won {pot} coins!")
                        if game.bet > 0: update_coins(w_user, pot)
                    del games[room_id]
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
                            del games[room_id]
                            return True
                        game.turn = 'X'
                img = draw_board(game.board)
                link = upload_image(bot, img, room_id)
                nxt = game.p1_name if game.turn=='X' else game.p2_name
                if link: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": f"Turn: {nxt}", "id": "gm_u"})
                return True
    return False
