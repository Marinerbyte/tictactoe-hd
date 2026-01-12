# file: games/tic_tac_toe_polish_safe.py

import io
import random
import time
from PIL import Image, ImageDraw, ImageFont
import threading

TRIGGER = "!tic"
LEADER_COMMAND = "!ticleader"

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
    try:
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
    except Exception as e:
        print("DEBUG: Board image error:", e)
        return None

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
def start_timeout(game, send_text, economy_api):
    def monitor():
        while game.get('active'):
            try:
                if game.get('started_at') and time.time()-game['started_at'] > 90:
                    players_list = [v for v in game.get('players', {}).values() if v]
                    try:
                        send_text(f"⏰ Game Timeout! Tic Tac Toe between {', '.join(players_list)} ended.")
                    except: pass
                    if game.get('bet',0)>0:
                        for p in players_list:
                            if p!='BOT':
                                try:
                                    economy_api.add_currency(p, game['bet'])
                                except: pass
                    game['active'] = False
                    break
            except Exception as e:
                print("DEBUG: Timeout thread error:", e)
            time.sleep(1)
    t = threading.Thread(target=monitor)
    t.daemon = True
    t.start()

# --- Leaderboard ---
def update_score(state, winner, players, bet):
    try:
        if 'tic_scores' not in state:
            state['tic_scores'] = {}
        for p in players.values():
            if p=='BOT': continue
            if p not in state['tic_scores']:
                state['tic_scores'][p] = {'wins':0,'losses':0,'draws':0,'coins':0}

        if winner=='Draw':
            for p in players.values():
                if p!='BOT':
                    state['tic_scores'][p]['draws'] +=1
                    state['tic_scores'][p]['coins'] += bet
        elif winner in ['X','O']:
            win_p = players[winner]
            lose_p = [v for k,v in players.items() if v and v!=win_p and v!='BOT']
            if win_p!='BOT':
                state['tic_scores'][win_p]['wins'] +=1
                state['tic_scores'][win_p]['coins'] += bet*2
            for lp in lose_p:
                state['tic_scores'][lp]['losses'] +=1
    except Exception as e:
        print("DEBUG: update_score error:", e)

def show_leaderboard(state):
    try:
        scores = state.get('tic_scores', {})
        if not scores:
            return "Leaderboard is empty!"
        sorted_scores = sorted(scores.items(), key=lambda x:x[1]['coins'], reverse=True)
        msg = "🏆 Tic Tac Toe Leaderboard 🏆\n"
        for i, (p,data) in enumerate(sorted_scores[:5],1):
            msg += f"{i}. {p}: Wins:{data['wins']} Losses:{data['losses']} Draws:{data['draws']} Coins:{data['coins']}\n"
        return msg.strip()
    except Exception as e:
        print("DEBUG: show_leaderboard error:", e)
        return "Leaderboard error!"

# --- Main Handler ---
def handle(user, msg, room_id, state, send_text, send_raw, db_api, economy_api, media_api, add_log):
    clean_msg = msg.strip()

    # Leaderboard
    if clean_msg.lower() == LEADER_COMMAND:
        try:
            send_text(show_leaderboard(state))
        except: pass
        return

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

    # Start Game
    if clean_msg.lower().startswith(TRIGGER):
        if game.get('active'):
            try: send_text("⚠️ Game already running!"); return
            except: pass
        game['board']=[' ']*9
        game['turn']='X'
        game['players']={'X':user,'O':None}
        game['active']=True
        game['step']=1
        game['started_at']=time.time()
        try: send_text("🎮 Tic Tac Toe 🎮\nSelect Mode:\n1️⃣ Single Player\n2️⃣ Multiplayer")
        except: pass
        start_timeout(game, send_text, economy_api)
        return

    # --- Mode Selection ---
    if game.get('active') and game['step']==1 and user==game['players']['X']:
        if clean_msg=="1":
            game['mode']=1
            game['players']['O']='BOT'
            game['step']=2
            try: send_text("Single Player selected.\nBet amount? (0 for no bet)"); return
            except: pass
        elif clean_msg=="2":
            game['mode']=2
            game['step']=2
            try: send_text("Multiplayer selected.\nBet amount? (0 for no bet)"); return
            except: pass
        else:
            try: send_text("⚠️ Type 1 or 2 only"); return
            except: pass

    # --- Bet Selection ---
    if game.get('active') and game['step']==2 and user==game['players']['X']:
        try:
            amount=int(clean_msg)
            if amount<0: raise ValueError
            game['bet']=amount
            if amount>0:
                try: economy_api.add_currency(user, -amount)
                except: pass
            game['step']=3
            intro=f"Game started! Bet: {amount}\n"
            if game['mode']==2:
                intro+="Waiting for Player O to join..."
            try:
                send_text(intro+"Type 1-9 to play.")
                media_api.send_image(room_id, generate_board_image(game['board']), caption="TicTacToe Board")
            except: pass
        except:
            try: send_text("⚠️ Invalid amount"); return
            except: pass
        return

    # --- Gameplay ---
    if game.get('active') and game['step']==3:
        if not clean_msg.isdigit(): return
        pos=int(clean_msg)-1
        if pos<0 or pos>8: return

        # Multiplayer join O
        if game['mode']==2 and game['players']['O'] is None and user!=game['players']['X']:
            game['players']['O']=user
            if game['bet']>0:
                try: economy_api.add_currency(user, -game['bet'])
                except: pass
            try: send_text(f"{user} joined as Player O!"); pass
            except: pass

        expected_user=game['players'][game['turn']]
        if expected_user!='BOT' and user!=expected_user:
            try: send_text(f"⚠️ {user}, wait for {expected_user}"); return
            except: pass
        if game['board'][pos]!=' ':
            try: send_text("⚠️ Position filled"); return
            except: pass

        # Make move
        game['board'][pos]=game['turn']
        game['started_at']=time.time()  # reset timeout
        try: media_api.send_image(room_id, generate_board_image(game['board']), caption=f"Turn: {game['turn']}")
        except: pass

        winner=check_winner(game['board'])
        if winner:
            players_list = {k:v for k,v in game['players'].items() if v}
            update_score(state, winner, players_list, game.get('bet',0))
            if winner=='Draw':
                try: send_text("🤝 Draw! Bets refunded."); pass
                except: pass
            elif winner=='X':
                if game['mode']==1:
                    try: send_text(f"🏆 You win! 🎉 Won {game['bet']*2} coins! 💰"); pass
                    except: pass
                else:
                    try: send_text(f"🏆 {game['players']['X']} wins!"); pass
                    except: pass
            elif winner=='O':
                if game['mode']==1:
                    try: send_text("😢 BOT wins! Better luck next time."); pass
                    except: pass
                else:
                    try: send_text(f"🏆 {game['players']['O']} wins!"); pass
                    except: pass
            game['active']=False
            return

        # Switch turn
        game['turn']='O' if game['turn']=='X' else 'X'

        # BOT move
        if game['mode']==1 and game['turn']=='O':
            empty=[i for i,x in enumerate(game['board']) if x==' ']
            if empty:
                bot_move=random.choice(empty)
                game['board'][bot_move]='O'
                game['started_at']=time.time()
                winner_bot=check_winner(game['board'])
                try: media_api.send_image(room_id, generate_board_image(game['board']), caption="🤖 BOT moved"); pass
                except: pass
                if winner_bot:
                    players_list = {k:v for k,v in game['players'].items() if v}
                    update_score(state, winner_bot, players_list, game.get('bet',0))
                    if winner_bot=='Draw':
                        try: send_text("🤝 Draw! Your bet refunded."); pass
                        except: pass
                    elif winner_bot=='O':
                        try: send_text("😢 BOT wins! Better luck next time."); pass
                        except: pass
                    else:
                        try: send_text(f"🏆 You win! 🎉 Won {game['bet']*2} coins! 💰"); pass
                        except: pass
                    game['active']=False
                    return
                game['turn']='X'
