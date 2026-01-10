# file: games/tic_tac_toe_polish.py

import io
import random
import time
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
    # Numbers 1-9 centered
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
    # Grid
    for i in [200,400]:
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
            send_text("Game already running! Wait or play your move.")
            return
        game['board']=[' ']*9
        game['turn']='X'
        game['players']={'X':user,'O':None}
        game['active']=True
        game['step']=1
        game['started_at']=time.time()
        send_text("🎮 Tic Tac Toe 🎮\nSelect Mode:\n1️⃣ Single Player\n2️⃣ Multiplayer")
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
        # Timeout check
        if game['started_at'] and time.time()-game['started_at']>120:
            players_list = [v for v in game['players'].values() if v]
            send_text(f"⏰ Game Timeout! Tic Tac Toe between {', '.join(players_list)} ended.")
            # Refund bets
            if game['bet']>0:
                for p in players_list:
                    if p!='BOT':
                        economy_api.add_currency(p, game['bet'])
            game['active']=False
            return

        if not clean_msg.isdigit(): return
        pos=int(clean_msg)-1
        if pos<0 or pos>8: return

        current_turn=game['turn']
        expected_user=game['players'][current_turn]

        # Multiplayer assign O
        if game['mode']==2 and game['players']['O'] is None and user!=game['players']['X']:
            game['players']['O']=user
            expected_user=user
            if game['bet']>0:
                economy_api.add_currency(user,-game['bet'])
            send_text(f"{user} joined as Player O!")

        if expected_user!='BOT' and user!=expected_user:
            send_text(f"⚠️ {user}, wait for {expected_user}")
            return
        if game['board'][pos]!=' ':
            send_text("⚠️ Position filled")
            return

        game['board'][pos]=current_turn

        winner=check_winner(game['board'])
        img_bytes=generate_board_image(game['board'])
        media_api.send_image(room_id, img_bytes, caption=f"Turn: {game['turn']}")

        if winner:
            players_list=[v for v in game['players'].values() if v]
            if winner=='Draw':
                send_text("🤝 Draw! Bets refunded.")
                if game['bet']>0:
                    for p in players_list:
                        if p!='BOT':
                            economy_api.add_currency(p,game['bet'])
            else:
                win_user=game['players'][winner]
                prize=game['bet']*2
                msg=f"🏆 {win_user} wins!"
                if game['bet']>0 and win_user!='BOT':
                    economy_api.add_currency(win_user,prize)
                    msg+=f" Won {prize} coins!"
                send_text(msg)
            game['active']=False
            return

        # Switch turn
        game['turn']='O' if current_turn=='X' else 'X'

        # BOT move
        if game['mode']==1 and game['turn']=='O':
            empty=[i for i,x in enumerate(game['board']) if x==' ']
            if empty:
                bot_move=random.choice(empty)
                game['board'][bot_move]='O'
                winner_bot=check_winner(game['board'])
                img_bytes=generate_board_image(game['board'])
                media_api.send_image(room_id,img_bytes,caption="BOT moved")
                if winner_bot:
                    if winner_bot=='Draw':
                        send_text("🤝 Draw!")
                        if game['bet']>0:
                            economy_api.add_currency(game['players']['X'],game['bet'])
                    else:
                        send_text("🤖 Bot wins! Better luck next time.")
                    game['active']=False
                    return
                game['turn']='X'
