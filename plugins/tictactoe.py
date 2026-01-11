import time
import random
import requests
import io
import threading
from PIL import Image, ImageDraw, ImageFont

# --- Global Game State ---
games = {} # room_id -> GameInstance

# --- Helper: Upload Image to Howdies ---
def upload_image(bot, image):
    """Image ko memory se direct Howdies par upload karta hai"""
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    
    url = "https://api.howdies.app/api/upload"
    try:
        files = {'file': ('tic.png', img_byte_arr, 'image/png')}
        data = {'token': bot.token, 'uploadType': 'image'}
        r = requests.post(url, files=files, data=data)
        res = r.json()
        
        # URL nikalna (structure vary kar sakta hai)
        link = res.get('url') or res.get('data', {}).get('url')
        return link
    except Exception as e:
        print(f"Upload Error: {e}")
        return None

# --- Helper: Draw Graphics (No External Fonts) ---
def draw_board(board_state):
    """
    Board banata hai.
    1-9: Faint (Halke)
    X/O: Sharp (Tez)
    """
    # Canvas (Black Background)
    size = 400
    cell = size // 3
    img = Image.new('RGB', (size, size), color=(20, 20, 20))
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
        center_x = x + cell // 2
        center_y = y + cell // 2
        
        val = board_state[i]

        if val is None:
            # Empty Box: Draw Faint Number (Halka Number)
            # Drawing generic shape for number to avoid font dependency issues or using default
            d.text((center_x - 5, center_y - 10), str(i+1), fill=(80, 80, 80)) # Very faint gray
            
            # Note: Agar aapke server pe font nahi hai, to default font bahut chhota hota hai.
            # Isliye hum yahan chhote circles draw karke hint de sakte hain ya default use karein.
            # Better Visual: Halka sa number draw karna default font se.

        elif val == 'X':
            # Sharp RED Cross
            offset = 30
            d.line([(x + offset, y + offset), (x + cell - offset, y + cell - offset)], fill=(255, 50, 50), width=15)
            d.line([(x + cell - offset, y + offset), (x + offset, y + cell - offset)], fill=(255, 50, 50), width=15)
            
        elif val == 'O':
            # Sharp BLUE Circle
            offset = 30
            d.ellipse([(x + offset, y + offset), (x + cell - offset, y + cell - offset)], outline=(50, 100, 255), width=12)

    return img

def draw_winner_card(username, winner_symbol, user_id=None):
    """Winner ka Card banata hai DP ke sath"""
    W, H = 500, 250
    img = Image.new('RGB', (W, H), color=(10, 10, 30))
    d = ImageDraw.Draw(img)
    
    # Background pattern
    d.rectangle([(10, 10), (W-10, H-10)], outline=(winner_symbol == 'X' and (255,50,50) or (50,100,255)), width=5)

    # Try Fetching DP (Placeholder logic - Howdies avatar usually follows a pattern or API)
    # Yahan hum ek dummy avatar bana rahe hain agar real fetch na ho paye
    # Real app mein: requests.get(avatar_url) karke paste karein
    try:
        # Example Avatar Fetch (Generic Placeholder)
        avatar_url = f"https://api.howdies.app/api/avatar/{user_id}" # Hypothetical
        # Agar real API pata ho to wahan se layein. Abhi hum Generate karenge.
        
        # Avatar Circle
        d.ellipse([(30, 50), (180, 200)], fill=(50, 50, 50), outline="white", width=3)
        d.text((80, 110), username[:2].upper(), fill="white") # Initials
        
    except:
        pass

    # Winner Text
    d.text((220, 80), "WINNER!", fill="yellow")
    d.text((220, 120), username, fill="white")
    
    # Symbol
    if winner_symbol == 'X':
        d.line([(400, 50), (450, 100)], fill="red", width=10)
        d.line([(450, 50), (400, 100)], fill="red", width=10)
    else:
        d.ellipse([(400, 50), (450, 100)], outline="blue", width=10)

    return img

# --- Game Logic Class ---
class TicTacToe:
    def __init__(self, room_id, creator_id, creator_name):
        self.room_id = room_id
        self.p1_id = creator_id
        self.p1_name = creator_name
        self.p2_id = None
        self.p2_name = None
        
        self.board = [None] * 9
        self.turn = 'X' # X always starts
        self.state = 'setup_mode' # setup_mode, setup_bet, waiting_join, playing
        self.mode = None # 1=Single, 2=Multi
        self.bet = 0
        self.last_interaction = time.time()

    def check_win(self):
        wins = [(0,1,2), (3,4,5), (6,7,8), (0,3,6), (1,4,7), (2,5,8), (0,4,8), (2,4,6)]
        for a, b, c in wins:
            if self.board[a] and self.board[a] == self.board[b] == self.board[c]:
                return self.board[a]
        if None not in self.board:
            return 'draw'
        return None

    def bot_move(self):
        # Simple AI: Random empty spot
        empty = [i for i, x in enumerate(self.board) if x is None]
        if empty:
            return random.choice(empty)
        return None

# --- Main Command Handler ---
def handle_command(bot, command, room_id, user, args):
    
    global games
    current_game = games.get(room_id)

    # 1. New Game Command
    if command == "tic":
        if current_game:
            bot.send_message(room_id, "⚠️ Game already running! Type 'stop' to end it.")
            return True
        
        # Create Game
        games[room_id] = TicTacToe(room_id, user, user)
        bot.send_message(room_id, f"🎮 **Tic-Tac-Toe**\n@{user}, Choose Mode:\n1️⃣ Single Player (vs Bot)\n2️⃣ Multiplayer (vs Human)")
        return True

    # 2. Stop Command
    if command == "stop" and current_game:
        # Only players or admin can stop
        if user in [current_game.p1_name, current_game.p2_name] or user == bot.user_data.get('username'):
            del games[room_id]
            bot.send_message(room_id, "🛑 Game stopped.")
        return True

    # 3. Handle Inputs based on State
    if current_game:
        game = current_game
        game.last_interaction = time.time()

        # --- SETUP: Choose Mode ---
        if game.state == 'setup_mode' and user == game.p1_name:
            if command == "1":
                game.mode = 1
                game.p2_name = "Bot"
                game.p2_id = "bot"
                game.state = 'setup_bet'
                bot.send_message(room_id, "💰 Choose Bet:\n1️⃣ No Bet (Fun)\n2️⃣ 100 Coins")
                return True
            elif command == "2":
                game.mode = 2
                game.state = 'setup_bet'
                bot.send_message(room_id, "💰 Choose Bet:\n1️⃣ No Bet (Fun)\n2️⃣ 100 Coins")
                return True

        # --- SETUP: Choose Bet ---
        elif game.state == 'setup_bet' and user == game.p1_name:
            if command == "1": game.bet = 0
            elif command == "2": game.bet = 100
            
            if game.mode == 1:
                game.state = 'playing'
                # Start Game (Bot)
                img = draw_board(game.board)
                link = upload_image(bot, img)
                bot.send_message(room_id, f"🔥 Game Started! (Vs Bot)\n@{game.p1_name} (X) vs Bot (O)\nType **1-9** to play.")
                if link:
                    bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Board", "id": "gm_start"})
            else:
                game.state = 'waiting_join'
                bot.send_message(room_id, f"⚔️ Multiplayer Mode!\nWaiting for player...\nType **'j'** to join @{game.p1_name}!")
            return True

        # --- SETUP: Join Multiplayer ---
        elif game.state == 'waiting_join':
            if command == "j" and user != game.p1_name:
                game.p2_name = user
                game.p2_id = user # Save ID logic here if available
                game.state = 'playing'
                
                img = draw_board(game.board)
                link = upload_image(bot, img)
                bot.send_message(room_id, f"🥊 Match On!\n@{game.p1_name} (X) vs @{game.p2_name} (O)\n@{game.p1_name}, your turn!")
                if link:
                    bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Board", "id": "gm_start"})
                return True

        # --- PLAYING STATE (Input 1-9) ---
        elif game.state == 'playing':
            # Check if input is a valid number 1-9
            if command.isdigit() and 1 <= int(command) <= 9:
                idx = int(command) - 1
                
                # Identify Player
                current_player_symbol = game.turn
                current_player_name = game.p1_name if game.turn == 'X' else game.p2_name
                
                # Check Turn
                if user != current_player_name:
                    return False # Not their turn
                
                # Check if cell empty
                if game.board[idx] is not None:
                    bot.send_message(room_id, f"🚫 Spot taken @{user}!")
                    return True
                
                # EXECUTE MOVE
                game.board[idx] = current_player_symbol
                
                # Check Win/Draw
                winner = game.check_win()
                
                if winner:
                    # Game Over
                    img = draw_board(game.board)
                    link = upload_image(bot, img)
                    if link:
                        bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Final", "id": "gm_end"})
                    
                    if winner == 'draw':
                        bot.send_message(room_id, "🤝 It's a DRAW!")
                    else:
                        # Draw Winner Card
                        card = draw_winner_card(user, winner)
                        card_link = upload_image(bot, card)
                        if card_link:
                            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": card_link, "text": "Winner", "id": "gm_win"})
                        bot.send_message(room_id, f"🎉 WINNER: @{user} wins {game.bet if game.bet > 0 else ''}!")
                        
                        # TODO: Update DB here if bet > 0
                        
                    del games[room_id]
                    return True
                
                # Swap Turn
                game.turn = 'O' if game.turn == 'X' else 'X'
                next_player = game.p1_name if game.turn == 'X' else game.p2_name
                
                # IF SINGLE PLAYER & NEXT IS BOT
                if game.mode == 1 and next_player == "Bot":
                    # Bot moves immediately
                    bot_idx = game.bot_move()
                    if bot_idx is not None:
                        game.board[bot_idx] = 'O'
                        
                        # Check Win for Bot
                        winner = game.check_win()
                        if winner:
                            img = draw_board(game.board)
                            link = upload_image(bot, img)
                            if link:
                                bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Bot Wins", "id": "gm_botwin"})
                            if winner == 'draw':
                                bot.send_message(room_id, "Draw!")
                            else:
                                bot.send_message(room_id, "🤖 Bot Wins! Better luck next time.")
                            del games[room_id]
                            return True
                            
                        # Swap back to Player
                        game.turn = 'X'
                
                # Update Board Image for Next Turn
                img = draw_board(game.board)
                link = upload_image(bot, img)
                if link:
                    next_p = game.p1_name if game.turn == 'X' else game.p2_name
                    bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": f"Turn: {next_p}", "id": "gm_upd"})

                return True

    return False
