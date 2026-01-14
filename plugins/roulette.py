import time
import random
import requests
import io
import sys
import os
import uuid
import threading
from PIL import Image, ImageDraw, ImageFont

# --- DB IMPORT (Master Function) ---
try:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from db import add_game_result
except Exception as e:
    print(f"DB Import Error: {e}")

# --- CONFIGURATION ---
SPIN_GIF_URL = "https://www.dropbox.com/scl/fi/fdc3cw487lsxd9hkgyv2v/anime_red_yellow_cylinder_rotate.gif?rlkey=d46acayd693mz444w2b7ozr0b&st=28lejgd3&dl=1"
BANG_IMAGE_URLS = [
    "https://www.dropbox.com/scl/fi/178rt7ol45n4ew3026ide/file_00000000ac847206b5d652e61f8445a7.png?rlkey=4pwus4m4brs1jk8t4xea5ierr&st=t2ad3zma&dl=1",
    "https://www.dropbox.com/scl/fi/w1rt0ohnycguyv8gujvda/file_00000000e5d8720685c235c1138550a4.png?rlkey=rj7gbft7dn1hflyf04yvtqqw2&st=cf9wie5m&dl=1"
]
ASSET_CACHE = {}

# Score Rules
WIN_REWARD = 50
LOSE_PENALTY = -50

# --- HELPER FUNCTIONS ---
def get_font(size):
    try: return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except: return ImageFont.load_default()

def upload_image(bot, image_bytes):
    url = "https://api.howdies.app/api/upload"
    try:
        uid = bot.user_id or 0
        files = {'file': ('roulette.png', image_bytes, 'image/png')}
        data = {'token': bot.token, 'uploadType': 'image', 'UserID': uid}
        r = requests.post(url, files=files, data=data, timeout=10)
        res = r.json()
        return res.get('url') or res.get('data', {}).get('url')
    except: return None

def get_asset_image(url, size=None):
    if url in ASSET_CACHE: return ASSET_CACHE[url]
    try:
        resp = requests.get(url, timeout=10)
        img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
        if size: img = img.resize(size)
        ASSET_CACHE[url] = img
        return img
    except: return None

# --- VISUALS ENGINE ---
def draw_roulette_visual(state, username):
    W, H = 500, 500
    bg_color = (20, 25, 30)
    cx, cy = W//2, H//2
    img = Image.new('RGB', (W, H), color=bg_color)
    d = ImageDraw.Draw(img)
    
    if state == "BANG":
        random_url = random.choice(BANG_IMAGE_URLS)
        bang_image = get_asset_image(random_url)
        if bang_image:
            bang_resized = bang_image.resize((400, 400))
            img.paste(bang_resized, (cx - 200, cy - 200), bang_resized)
        d.text((cx, H - 50), f"@{username} GOT SHOT!", fill="#ff4757", font=get_font(30), anchor="mm")
        
    elif state == "SAFE":
        d.rectangle([(cx-150, cy-200), (cx+150, cy+200)], fill=(250, 250, 240), outline="gold", width=5)
        d.text((cx, 150), "🍀", font=get_font(100), anchor="mm")
        d.text((cx, 250), "SURVIVED!", fill="#27ae60", font=get_font(40), anchor="mm")
        d.text((cx, 300), f"@{username}", fill="black", font=get_font(30), anchor="mm")

    png_bytes = io.BytesIO(); img.save(png_bytes, format='PNG'); png_bytes.seek(0)
    return png_bytes

# --- GAME THREAD ---
def play_roulette_thread(bot, room_id, user, user_id):
    try:
        # 1. SPIN (Use direct GIF URL)
        bot.send_json({
            "handler": "chatroommessage", "roomid": room_id, "type": "image",
            "url": SPIN_GIF_URL, "text": "Spinning... 1 bullet is loaded.",
            "id": uuid.uuid4().hex
        })
        time.sleep(3)

        # 2. LOGIC
        dead = (random.randint(1, 6) == 1) # 1 in 6 chance

        if dead:
            # LOSE
            add_game_result(user_id, user, "roulette", LOSE_PENALTY, is_win=False)
            img_bytes = draw_roulette_visual("BANG", user)
            link = upload_image(bot, img_bytes)
            
            if link: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Bang!", "id": uuid.uuid4().hex})
            else: bot.send_message(room_id, f"💥 **BOOM!** @{user} lost {abs(LOSE_PENALTY)} Coins!")
            
            # KICK PAYLOAD
            time.sleep(1)
            bot.send_json({"handler": "kickuser", "id": uuid.uuid4().hex, "roomid": room_id, "to": user_id})
        
        else:
            # WIN
            add_game_result(user_id, user, "roulette", WIN_REWARD, is_win=True)
            img_bytes = draw_roulette_visual("SAFE", user)
            link = upload_image(bot, img_bytes)
            
            if link: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Safe!", "id": uuid.uuid4().hex})
            else: bot.send_message(room_id, f"😅 **Safe!** @{user} won {WIN_REWARD} Coins.")
    except Exception as e:
        print(f"Roulette Error: {e}")

# --- HANDLER (FIXED) ---
def handle_command(bot, command, room_id, user, args, data):
    cmd_clean = command.lower().strip()
    if cmd_clean == "shoot":
        
        # --- THIS IS THE FIX ---
        user_id = data.get('userid') or data.get('userID')
        
        if not user_id:
            bot.send_message(room_id, "⚠️ Your user ID could not be found to play. Please try rejoining the room.")
            return True # Command handled
        
        # Start game in new thread
        threading.Thread(target=play_roulette_thread, args=(bot, room_id, user, user_id)).start()
        
        return True
    return False
