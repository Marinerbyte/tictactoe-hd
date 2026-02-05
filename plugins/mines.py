import time, random, threading, sys, os, uuid, requests, io
from PIL import Image, ImageDraw, ImageOps

# --- IMPORTS ---
try:
    import utils
except ImportError:
    print("[Mines] utils.py not found!")

try:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from db import add_game_result
except Exception as e:
    print(f"[Mines] DB error: {e}")

# ==========================================
# 🌍 GLOBALS
# ==========================================

games = {}
setup_pending = {}   # { user_id : room_id }
game_lock = threading.Lock()
BOT_INSTANCE = None

def setup(bot_ref):
    global BOT_INSTANCE
    BOT_INSTANCE = bot_ref
    print("[Mines] FINAL Production Engine Loaded")

# ==========================================
# 🔤 SMALL CAPS
# ==========================================

def to_small_caps(text):
    normal = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    small  = "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ"
    return text.translate(str.maketrans(normal, small))

# ==========================================
# 🖼️ AVATAR ENGINE (ROBUST)
# ==========================================

AVATAR_CACHE = {}

def get_robust_avatar(avatar_url, username):
    if avatar_url and avatar_url in AVATAR_CACHE:
        return AVATAR_CACHE[avatar_url].copy()

    try:
        if avatar_url:
            r = requests.get(avatar_url, timeout=5)
            if r.status_code == 200:
                img = Image.open(io.BytesIO(r.content)).convert("RGBA")
                AVATAR_CACHE[avatar_url] = img
                return img.copy()
    except:
        pass

    # fallback (DO NOT CACHE)
    try:
        fb = f"https://api.dicebear.com/9.x/adventurer/png?seed={username}&backgroundColor=transparent"
        r = requests.get(fb, timeout=5)
        return Image.open(io.BytesIO(r.content)).convert("RGBA")
    except:
        return Image.new("RGBA", (100, 100), (60, 60, 60))

def circle_crop(img, size):
    img = img.resize((size, size), Image.Resampling.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    out = Image.new("RGBA", (size, size))
    out.paste(img, (0, 0), mask)
    return out

# ==========================================
# 🎨 RENDERING
# ==========================================

def draw_3d_box(d, x, y, size, text):
    d.rounded_rectangle([x, y+6, x+size, y+size+6], 15, fill=(20,30,50))
    d.rounded_rectangle([x, y, x+size, y+size], 15, fill=(60,90,160), outline="#8899AA", width=2)
    utils.write_text(d, (x+size//2, y+size//2), text, size=30, align="center", shadow=True)

def draw_board(game):
    is_p1 = game.turn == "P1"

    # opponent board only
    board   = game.board_p1 if is_p1 else game.board_p2
    reveal  = game.revealed_p1 if is_p1 else game.revealed_p2

    opp_name = game.p2_name if is_p1 else game.p1_name
    opp_av   = game.p2_av   if is_p1 else game.p1_av
    opp_life = game.lives_p2 if is_p1 else game.lives_p1

    img = utils.create_canvas(500, 650, (15,15,20))
    d = ImageDraw.Draw(img)

    d.rounded_rectangle([20,20,480,130], 25, fill=(45,55,85), outline="#00FFFF", width=3)

    dp = circle_crop(get_robust_avatar(opp_av, opp_name), 90)
    img.paste(dp, (40,30), dp)

    utils.write_text(d, (150,50), to_small_caps(f"Opponent: {opp_name}"), size=26, align="left")
    utils.write_text(d, (150,85), f"Lives: {'❤️'*opp_life}", size=20, align="left")

    sx, sy, bs, gap = 55, 170, 85, 15
    for i in range(12):
        x = sx + (i%4)*(bs+gap)
        y = sy + (i//4)*(bs+gap)

        if not reveal[i]:
            draw_3d_box(d, x, y, bs, str(i+1))
        else:
            bomb = board[i] == 1
            col = (180,50,50) if bomb else (50,180,80)
            d.rounded_rectangle([x,y,x+bs,y+bs],15,fill=col,outline="white",width=2)

            icon = utils.get_emoji("💣" if bomb else "🍪", size=50)
            img.paste(icon, (x+17,y+10), icon)

    return img

def draw_blast(name, av):
    img = utils.create_canvas(500,500,(30,0,0))
    d = ImageDraw.Draw(img)
    boom = utils.get_emoji("💥",300)
    img.paste(boom,(100,40),boom)

    dp = circle_crop(get_robust_avatar(av,name),200)
    dp = ImageOps.grayscale(dp)
    img.paste(dp,(150,150),dp)

    utils.write_text(d,(250,430),to_small_caps(f"{name} HIT A BOMB"),40,"center","red")
    return img

def draw_winner(name,av):
    img = utils.create_canvas(500,500,(10,30,10))
    d = ImageDraw.Draw(img)

    trophy = utils.get_sticker("win",250)
    img.paste(trophy,(125,30),trophy)

    dp = circle_crop(get_robust_avatar(av,name),180)
    img.paste(dp,(160,200),dp)

    utils.write_text(d,(250,430),to_small_caps(f"WINNER: {name}"),40,"center","gold")
    return img

def draw_setup_board():
    img = utils.create_canvas(500,500,(25,30,45))
    d = ImageDraw.Draw(img)
    utils.write_text(d,(250,50),"BOMB SETUP (1–12)",35,"center","gold")

    sx, sy, bw, bh, g = 55,110,85,65,15
    for i in range(12):
        x = sx+(i%4)*(bw+g)
        y = sy+(i//4)*(bh+g)
        d.rounded_rectangle([x,y,x+bw,y+bh],10,fill=(50,60,90),outline="#DDD")
        utils.write_text(d,(x+bw//2,y+bh//2),str(i+1),24,"center","white")
    return img

# ==========================================
# 🧠 GAME CLASS
# ==========================================

class MinesGame:
    def __init__(self, room, uid, name, av):
        self.room_id = room
        self.p1_id, self.p1_name, self.p1_av = uid, name, av
        self.p2_id = self.p2_name = self.p2_av = None

        self.board_p1 = [0]*12
        self.board_p2 = [0]*12
        self.revealed_p1 = [False]*12
        self.revealed_p2 = [False]*12

        self.lives_p1 = self.lives_p2 = 3
        self.turn = "P1"
        self.state = "waiting"
        self.bet = 0

# ==========================================
# 🎮 COMMAND HANDLER
# ==========================================

def handle_command(bot, command, room_id, user, args, data):
    uid = str(data.get("userid", user))
    avatar = data.get("avatar")
    cmd = command.lower().strip()

    # ---------- DM SETUP ----------
    if uid in setup_pending and not room_id:
        nums = list(set(int(n) for n in command.replace(","," ").split() if n.isdigit()))
        if len(nums)!=4 or not all(1<=n<=12 for n in nums):
            bot.send_dm(user,"❌ Send exactly 4 unique numbers (1–12).")
            return True

        rid = setup_pending.pop(uid)
        g = games.get(rid)
        if not g: return True

        target = g.board_p2 if uid==g.p1_id else g.board_p1
        for n in nums: target[n-1]=1

        bot.send_dm(user,"✅ Bombs placed.")

        if g.state!="playing" and sum(g.board_p1)==4 and sum(g.board_p2)==4:
            g.state="playing"
            bot.send_message(rid,to_small_caps("🔥 GAME STARTED"))
            img = draw_board(g)
            bot.send_json({"handler":"chatroommessage","roomid":rid,"type":"image","url":utils.upload(bot,img)})
        return True

    # ---------- START ----------
    if cmd=="mines":
        bet = int(args[0]) if args and args[0].isdigit() else 500
        games[room_id] = MinesGame(room_id,uid,user,avatar)
        games[room_id].bet = bet
        bot.send_message(room_id,to_small_caps(f"💣 MINES started by @{user}. Type !join"))
        return True

    if cmd=="join":
        g = games.get(room_id)
        if not g or g.state!="waiting": return False
        g.p2_id,g.p2_name,g.p2_av = uid,user,avatar
        g.state="setup"
        setup_pending[g.p1_id]=room_id
        setup_pending[g.p2_id]=room_id

        img = utils.upload(bot,draw_setup_board())
        bot.send_dm_image(g.p1_name,img,f"Place bombs for @{g.p2_name}")
        bot.send_dm_image(g.p2_name,img,f"Place bombs for @{g.p1_name}")
        return True

    # ---------- GAME ----------
    if cmd.isdigit() and room_id:
        idx=int(cmd)-1
        g=games.get(room_id)
        if not g or g.state!="playing" or not 0<=idx<12: return False

        is_p1 = g.turn=="P1"
        if (is_p1 and uid!=g.p1_id) or (not is_p1 and uid!=g.p2_id): return False

        reveal = g.revealed_p1 if is_p1 else g.revealed_p2
        board  = g.board_p1 if is_p1 else g.board_p2

        if reveal[idx]:
            bot.send_message(room_id,"❌ Tile already opened.")
            return True

        reveal[idx]=True

        if board[idx]==1:
            if is_p1: g.lives_p1-=1
            else: g.lives_p2-=1

            name = g.p1_name if is_p1 else g.p2_name
            av   = g.p1_av if is_p1 else g.p2_av
            bot.send_json({"handler":"chatroommessage","roomid":room_id,"type":"image",
                           "url":utils.upload(bot,draw_blast(name,av))})

            if (is_p1 and g.lives_p1<=0) or (not is_p1 and g.lives_p2<=0):
                win_id   = g.p2_id if is_p1 else g.p1_id
                win_name = g.p2_name if is_p1 else g.p1_name
                win_av   = g.p2_av if is_p1 else g.p1_av

                add_game_result(win_id,win_name,"mines",g.bet*2,True)
                bot.send_json({"handler":"chatroommessage","roomid":room_id,"type":"image",
                               "url":utils.upload(bot,draw_winner(win_name,win_av))})

                def end():
                    time.sleep(3)
                    bot.send_json({"handler":"kickuser","roomid":int(room_id),"to":int(uid)})
                    games.pop(room_id,None)
                threading.Thread(target=end).start()
                return True
        else:
            bot.send_message(room_id,f"🍪 @{user} found a cookie!")

        g.turn = "P2" if is_p1 else "P1"
        bot.send_json({"handler":"chatroommessage","roomid":room_id,"type":"image",
                       "url":utils.upload(bot,draw_board(g))})
        return True

    return False
