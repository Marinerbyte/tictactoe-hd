import time
import random
import requests
import io
import sys
import os
from PIL import Image, ImageDraw

# Root directory se db.py import karne ke liye path setup
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import db

# --- Global Game State ---
games = {} # room_id -> GameInstance

# --- Helper: Database Money Management ---
def update_coins(user_id, amount):
    """Coins add (+) ya remove (-) karta hai"""
    conn = db.get_connection()
    if not conn: return
    cur = conn.cursor()
    try:
        # Ensure user exists
        try:
            cur.execute("INSERT INTO users (user_id, username, global_score) VALUES (%s, %s, 0) ON CONFLICT (user_id) DO NOTHING", (user_id, user_id))
        except:
            cur.execute("INSERT OR IGNORE INTO users (user_id, username, global_score) VALUES (?, ?, 0)", (user_id, user_id))
        
        # Update Score
        query = "UPDATE users SET global_score = global_score + %s WHERE user_id = %s"
        # SQLite fallback
        if not db.DATABASE_URL.startswith("postgres"):
            query = "UPDATE users SET global_score = global_score + ? WHERE user_id = ?"
            
        cur.execute(query, (amount, user_id))
        conn.commit()
    except Exception as e:
        print(f"DB Error: {e}")
    finally:
        conn.close()

# --- Helper: Upload Image to Howdies ---
def upload_image(bot, image):
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    
    url = "https://api.howdies.app/api/upload"
    try:
        # UserID is crucial for Howdies API
        files = {'file': ('tic.png', img_byte_arr, 'image/png')}
        data = {
            'token': bot.token,
            'uploadType': 'image',
            'UserID': bot.user_data.get('username', 'bot') # Fix: Sending UserID
        }
        
        r = requests.post(url, files=files, data=data)
        res = r.json()
        
        # Extract URL logic
        link = res.get('url') 
        if not link:
            link = res.get('data', {}).get('url')
            
        if not link:
            print(f"[Upload Fail] Response: {r.text}")
            
        return link
    except Exception as e:
        print(f"[Upload Error] {e}")
        return None

# --- Helper: Draw Board ---
def draw_board(board_state):
    # Canvas
    size = 400
    cell = size // 3
    img = Image.new('RGB', (size, size), color=(20, 20, 20)) # Dark Background
    d = ImageDraw.Draw(img)

    # Grid Lines (White)
    for i in range(1, 3):
        d.line([(cell * i, 10), (cell * i, size - 10)], fill=(255, 255, 255), width=5)
        d.line([(10, cell * i), (size - 10, cell * i)], fill=(255, 255, 255), width=5)

    # Draw Cells
    for i in range(9):
        row = i // 3
        col = i % 3
        x = col * cell
        y = row * cell
        
        # Center coordinates
        cx = x + cell // 2
        cy = y + cell // 2
        
        val = board_state[i]

        if val is None:
            # Empty Box: Draw Faint Number (Halka Color)
            # Default font used to avoid file dependency
            d.text((cx - 5, cy - 10), str(i+1), fill=(60, 60, 60)) 
        elif val == 'X':
            # Sharp RED Cross
            offset = 35
            d.line([(x + offset, y + offset), (x + cell - offset, y + cell - offset)], fill=(255, 40, 40), width=12)
            d.line([(x + cell - offset, y + offset), (x + offset, y + cell - offset)], fill=(255, 40, 40), width=12)
        elif val == 'O':
            # Sharp BLUE Circle
            offset = 35
            d.ellipse([(x + offset, y + offset), (x + cell - offset, y + cell - offset)], outline=(40, 100, 255), width=12)

    return img

# --- Helper: Draw Winner Card ---
def draw_winner_card(username, winner_symbol):
    W, H = 500, 250
    # Background depends on winner
    bg_color = (30, 10, 10) if winner_symbol == 'X' else (10, 10, 30)
    img = Image.new('RGB', (W, H), color=bg_color)
    d = ImageDraw.Draw(img)
    
    # Border
    color = (255, 50, 50) if winner_symbol == 'X' else (50, 100, 255)
    d.rectangle([(10, 10), (W-10, H-10)], outline=color, width=5)

    # Fake Avatar (Circle with Initial)
    d.ellipse([(40, 50), (160, 170)], fill=(50, 50, 50), outline="white", width=3)
    d.text((85, 95), username[:2].upper(), fill="white") # Initials

    # Winner Text
    d.text((200, 80), "👑 WINNER 👑", fill="yellow")
    d.text((200, 110), f"@{username}", fill="white")
    
    # Symbol Graphic
    if winner_symbol == 'X':
        d.text((380, 80), "X", fill="red")
    else:
        d.text((380, 80), "O", fill="blue")

    return img

# --- Game Class ---
class TicTacToe:
    def __init__(self, room_id, creator_id):
        self.room_id = room_id
        self.p1_name = creator_id
        self.p2_name = None
        self.board = [None] * 9
        self.turn = 'X'
        self.state = 'setup_mode' # setup_mode -> setup_bet -> waiting_join -> playing
        self.mode = None # 1=Bot, 2=Multi
        self.bet = 0
        self.last_interaction = time.time()

    def check_win(self):
        wins = [(0,1,2), (3,4,5), (6,7,8), (0,3,6), (1,4,7), (2,5,8), (0,4,8), (2,4,6)]
        for a, b, c in wins:
            if self.board[a] and self.board[a] == self.board[b] == self.board[c]:
                return self.board[a]
        if None not in self.board: return 'draw'
        return None

    def bot_move(self):
        # 1. Try to win
        # 2. Block opponent
        # 3. Random
        empty = [i for i, x in enumerate(self.board) if x is None]
        if not empty: return None
        return random.choice(empty)

# --- Main Handler ---
def handle_command(bot, command, room_id, user, args):
    global games
    current_game = games.get(room_id)

    # --- START GAME ---
    if command == "tic":
        if current_game:
            bot.send_message(room_id, "⚠️ Game already running! Type 'stop' to end.")
            return True
        
        games[room_id] = TicTacToe(room_id, user)
        bot.send_message(room_id, f"🎮 **Tic-Tac-Toe**\n@{user}, Choose Mode:\n1️⃣ Single Player (vs Bot)\n2️⃣ Multiplayer (vs Human)")
        return True

    # --- STOP GAME ---
    if command == "stop" and current_game:
        # Refund coins if game stops mid-way (Optional logic)
        del games[room_id]
        bot.send_message(room_id, "🛑 Game stopped.")
        return True

    # --- GAME INPUTS ---
    if current_game:
        game = current_game
        
        # 1. SETUP MODE
        if game.state == 'setup_mode' and user == game.p1_name:
            if command == "1":
                game.mode = 1
                game.p2_name = "Bot"
                game.state = 'setup_bet'
                game.last_interaction = time.time() # ✅ Valid Input
                bot.send_message(room_id, "💰 Bet Amount?\n1️⃣ Fun (0 Coins)\n2️⃣ 100 Coins")
                return True
            elif command == "2":
                game.mode = 2
                game.state = 'setup_bet'
                game.last_interaction = time.time() # ✅ Valid Input
                bot.send_message(room_id, "💰 Bet Amount?\n1️⃣ Fun (0 Coins)\n2️⃣ 100 Coins")
                return True

        # 2. SETUP BET
        elif game.state == 'setup_bet' and user == game.p1_name:
            if command in ["1", "2"]:
                game.bet = 0 if command == "1" else 100
                game.last_interaction = time.time() # ✅ Valid Input

                # Deduct P1 Coins
                if game.bet > 0:
                    update_coins(game.p1_name, -game.bet)

                if game.mode == 1:
                    game.state = 'playing'
                    img = draw_board(game.board)
                    link = upload_image(bot, img)
                    bot.send_message(room_id, f"🔥 Started (Vs Bot)\nBet: {game.bet}\nType **1-9** to play.")
                    if link: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Board", "id": "gm_s"})
                else:
                    game.state = 'waiting_join'
                    bot.send_message(room_id, f"⚔️ Multiplayer (Bet: {game.bet})\nWaiting for player...\nType **'j'** to join!")
                return True

        # 3. JOINING
        elif game.state == 'waiting_join':
            if command == "j" and user != game.p1_name:
                game.p2_name = user
                game.last_interaction = time.time() # ✅ Valid Input
                
                # Deduct P2 Coins
                if game.bet > 0:
                    update_coins(game.p2_name, -game.bet)

                game.state = 'playing'
                img = draw_board(game.board)
                link = upload_image(bot, img)
                bot.send_message(room_id, f"🥊 Match On!\n@{game.p1_name} (X) vs @{game.p2_name} (O)\n@{game.p1_name} turn!")
                if link: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Board", "id": "gm_s"})
                return True

        # 4. PLAYING
        elif game.state == 'playing':
            if command.isdigit() and 1 <= int(command) <= 9:
                idx = int(command) - 1
                
                # Turn Logic
                current_player = game.p1_name if game.turn == 'X' else game.p2_name
                if user != current_player: return False # Not your turn
                if game.board[idx] is not None: 
                    bot.send_message(room_id, "🚫 Taken!")
                    return True

                # Move Executed
                game.last_interaction = time.time() # ✅ Valid Input
                game.board[idx] = game.turn
                
                # Check Win
                winner = game.check_win()
                if winner:
                    # Final Image
                    img = draw_board(game.board)
                    link = upload_image(bot, img)
                    if link: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "End", "id": "gm_e"})

                    if winner == 'draw':
                        bot.send_message(room_id, "🤝 Draw! Coins refunded.")
                        if game.bet > 0:
                            update_coins(game.p1_name, game.bet)
                            if game.mode == 2: update_coins(game.p2_name, game.bet)
                    else:
                        win_user = game.p1_name if winner == 'X' else game.p2_name
                        total_pot = game.bet * 2 if game.mode == 2 else game.bet * 2 # Simple doubling logic
                        
                        # Generate Winner Card
                        card = draw_winner_card(win_user, winner)
                        clink = upload_image(bot, card)
                        if clink: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": clink, "text": "Win", "id": "gm_w"})
                        
                        bot.send_message(room_id, f"🎉 @{win_user} Won {total_pot} coins!")
                        if game.bet > 0:
                            update_coins(win_user, total_pot)

                    del games[room_id]
                    return True

                # Swap Turn
                game.turn = 'O' if game.turn == 'X' else 'X'
                
                # Bot Logic (If Single Player)
                if game.mode == 1 and game.turn == 'O':
                    bot_idx = game.bot_move()
                    if bot_idx is not None:
                        game.board[bot_idx] = 'O'
                        # Check Bot Win
                        winner = game.check_win()
                        if winner:
                            img = draw_board(game.board)
                            link = upload_image(bot, img)
                            if link: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "BotWin", "id": "gm_be"})
                            
                            if winner == 'draw': bot.send_message(room_id, "Draw!")
                            else: bot.send_message(room_id, "🤖 Bot Wins! You lost coins.")
                            del games[room_id]
                            return True
                        
                        game.turn = 'X' # Back to player

                # Update Board Image
                img = draw_board(game.board)
                link = upload_image(bot, img)
                next_p = game.p1_name if game.turn == 'X' else game.p2_name
                if link: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": f"Turn: {next_p}", "id": "gm_u"})
                return True

    return False
