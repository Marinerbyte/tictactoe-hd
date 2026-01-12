# file: games/tic_tac_toe_polish.py

import io
import random
import time
import threading
from PIL import Image, ImageDraw, ImageFont

TRIGGER = "!tic"

# --- Helper Functions ---

def create_base_assets():
    assets = {}
    size = 200
    # X
    img_x = Image.new('RGBA', (size, size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img_x)
    draw.line((40, 40, 160, 160), fill="red", width=20)
    draw.line((160, 40, 40, 160), fill="red", width=20)
    assets['X'] = img_x
    # O
    img_o = Image.new('RGBA', (size, size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img_o)
    draw.ellipse((40, 40, 160, 160), outline="blue", width=20)
    assets['O'] = img_o
    # Numbers 1-9
    font = ImageFont.load_default()
    for i in range(1, 10):
        img = Image.new('RGBA', (size, size), (255, 255, 255, 0))
        d = ImageDraw.Draw(img)
        text = str(i)
        w, h = d.textsize(text, font=font)
        d.text(((size-w)/2, (size-h)/2), text, fill="gray", font=font)
        assets[str(i)] = img
    return assets

def generate_board_image(board):
    width, height = 600, 600
    img = Image.new('RGB', (width, height), "white")
    draw = ImageDraw.Draw(img)
    for i in [200, 400]:
        draw.line((i,0,i,600), fill="black", width=10)
        draw.line((0,i,600,i), fill="black", width=10)
    assets = create_base_assets()
    for idx, cell in enumerate(board):
        row, col = idx//3, idx%3
        x, y = col*200, row*200
        if cell in ['X','O']:
            img.paste(assets[cell], (x,y), assets[cell])
        else:
            img.paste(assets[str(idx+1)], (x,y), assets[str(idx+1)])
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf

def check_winner(board):
    wins = [
        (0,1,2),(3,4,5),(6,7,8),
        (0,3,6),(1,4,7),(2,5,8),
        (0,4,8),(2,4,6)
    ]
    for a,b,c in wins:
        if board[a]==board[b]==board[c] and board[a]!=' ':
            return board[a]
    if ' ' not in board:
        return 'Draw'
    return None

# --- Timeout Thread ---

def start_timeout_thread(game, send_text, economy_api):
    def check_timeout():
        while game['active']:
            if game['started_at'] and time.time()-game['started_at']>90:
                players_list = [v for v in game['players'].values() if v]
                send_text(f"⏰ Game Timeout! Tic Tac Toe between {', '.join(players_list)} ended.")
                if game['bet']>0:
                    for p in players_list:
                        if p != 'BOT':
                            economy_api.add_currency(p, game['bet'])
                game['active'] = False
                break
            time.sleep(5)
    t = threading.Thread(target=check_timeout)
    t.daemon = True
    t.start()

# --- Main Handler ---

def handle(user, msg, room_id, state, send_text, send_raw, db_api, economy_api, media_api, add_log):
    if 'tic_game' not in state:
        state['tic_game'] = {
            'active': False,
            'step':0,
            'players':{},
            'turn':'X',
            'board':[' ']*9,
            'bet':0,
            'mode':1,
            'started_at': None
        }

    game = state['tic_game']
    clean_msg = msg.strip()

    # --- START GAME ---
    if clean_msg.lower().startswith("!tic"):
        if game['active']:
            send_text("⚠️ Game already running! Wait or play your move.")
            return
        game['board']=[' ']*9
        game['turn']='X'
        game['players']={'X':user,'O':None}
        game['active']=True
        game['step']=1
        game['started_at']=time.time()
        send_text("🎮 Tic Tac Toe 🎮\nSelect Mode:\n1️⃣ Single Player\n2️⃣ Multiplayer")
        start_timeout_thread(game, send_text, economy_api)
        return

    # --- MODE SELECTION ---
    if game['active'] and game['step']==1 and user==game['players']['X']:
        if clean_msg=="1":
            game['mode']=1
            game['players']['O']='BOT'
            game['step']=2
            send_text("Single Player selected.\nBet amount? (0 for no bet)")
        elif clean_msg=="2":
            game['mode']=2
            game['step']=2
            send_text("Multiplayer selected.\nBet amount? (0 for no bet)")
        else:
            send_text("⚠️ Type 1 or 2 only")
        return

    # --- BET SELECTION ---
    if game['active'] and game['step']==2 and user==game['players']['X']:
        try:
            amount=int(clean_msg)
            if amount<0: raise ValueError
            game['bet']=amount
            if amount>0:
                economy_api.add_currency(user,-amount)
            game['step']=3
            intro=f"Game started! Bet: {amount}\n"
            if game['mode']==2:
                intro+="Waiting for Player O to join..."
            send_text(intro+"Type 1-9 to play.")
            media_api.send_image(room_id, generate_board_image(game['board']), caption="TicTacToe Board")
        except:
            send_text("⚠️ Invalid amount")
        return

    # --- GAMEPLAY ---
    if game['active'] and game['step']==3:
        if not clean_msg.isdigit(): return
        pos=int(clean_msg)-1
        if pos<0 or pos>8: return

        current_turn=game['turn']

        # Multiplayer: assign O if not joined
        if game['mode']==2 and game['players']['O'] is None and user!=game['players']['X']:
            game['players']['O']=user
            if game['bet']>0:
                economy_api.add_currency(user,-game['bet'])
            send_text(f"{user} joined as Player O!")

        expected_user=game['players'][current_turn]
        if expected_user!='BOT' and user!=expected_user:
            send_text(f"⚠️ {user}, wait for {expected_user}")
            return
        if game['board'][pos]!=' ':
            send_text("⚠️ Position filled")
            return

        # Make move
        game['board'][pos]=current_turn
        game['started_at']=time.time()  # reset timeout after move

        winner=check_winner(game['board'])
        media_api.send_image(room_id, generate_board_image(game['board']), caption=f"Turn: {game['turn']}")

        if winner:
            players_list=[v for v in game['players'].values() if v]
            if winner=='Draw':
                send_text("🤝 Draw! Bets refunded.")
                if game['bet']>0:
                    for p in players_list:
                        if p!='BOT':
                            economy_api.add_currency(p,game['bet'])
            elif winner=='X':
                win_user=game['players']['X']
                prize = game['bet']*2
                msg=f"🏆 {win_user} wins! 🎉 Won {prize} coins! 💰" if game['mode']==1 else f"🏆 {win_user} wins!"
                send_text(msg)
                if game['bet']>0:
                    economy_api.add_currency(win_user, prize)
            elif winner=='O':
                if game['mode']==1:
                    send_text("😢 BOT wins! Better luck next time.")
                else:
                    win_user=game['players']['O']
                    prize = game['bet']*2
                    msg=f"🏆 {win_user} wins!"
                    send_text(msg)
                    if game['bet']>0:
                        economy_api.add_currency(win_user, prize)
            game['active']=False
            return

        # Switch turn
        game['turn']='O' if current_turn=='X' else 'X'

        # BOT move for Single Player
        if game['mode']==1 and game['turn']=='O':
            empty=[i for i,x in enumerate(game['board']) if x==' ']
            if empty:
                bot_move=random.choice(empty)
                game['board'][bot_move]='O'
                game['started_at']=time.time()  # reset timeout after BOT move
                winner_bot=check_winner(game['board'])
                media_api.send_image(room_id, generate_board_image(game['board']), caption="🤖 BOT moved")
                
                if winner_bot:
                    if winner_bot=='Draw':
                        send_text("🤝 Draw! Your bet has been refunded.")
                        if game['bet']>0:
                            economy_api.add_currency(game['players']['X'], game['bet'])
                    elif winner_bot=='O':
                        send_text("😢 BOT wins! Better luck next time.")
                    else:
                        prize = game['bet']*2
                        send_text(f"🏆 You win! 🎉 Won {prize} coins! 💰")
                        if game['bet']>0:
                            economy_api.add_currency(game['players']['X'], prize)
                    game['active'] = False
                    return
                game['turn']='X'
