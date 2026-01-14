import time
import random
import requests
import io
import sys
import os
import uuid
import threading
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# --- DB IMPORT ---
try:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from db import add_game_result
except Exception as e:
    print(f"DB Import Error: {e}")

# --- CONFIGURATION ---
BANG_IMAGE_URLS = [
    "https://www.dropbox.com/scl/fi/178rt7ol45n4ew3026ide/file_00000000ac847206b5d652e61f8445a7.png?rlkey=4pwus4m4brs1jk8t4xea5ierr&st=t2ad3zma&dl=1",
    "https://www.dropbox.com/scl/fi/w1rt0ohnycguyv8gujvda/file_00000000e5d8720685c235c1138550a4.png?rlkey=rj7gbft7dn1hflyf04yvtqqw2&st=cf9wie5m&dl=1"
]
ASSET_CACHE = {}

# --- NEW SCORE RULES ---
WIN_REWARD = 50
LOSE_PENALTY = -50

# --- HELPER FUNCTIONS ---
def get_font(size):
    try: return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except: return ImageFont.load_default()

def upload_media(bot, media_bytes, is_gif=False):
    # ... (same upload logic)
    file_format = 'gif' if is_gif else 'png'; mime_type = 'image/gif' if is_gif else 'image/png'
    url = "https://api.howdies.app/api/upload"
    try:
        uid = bot.user_id or 0
        files = {'file': (f'roulette.{file_format}', media_bytes, mime_type)}
        data = {'token': bot.token, 'uploadType': 'image', 'UserID': uid}
        r = requests.post(url, files=files, data=data, timeout=15)
        return r.json().get('url') or r.json().get('data', {}).get('url')
    except: return None

def get_asset_image(url):
    if url in ASSET_CACHE: return ASSET_CACHE[url]
    try:
        resp = requests.get(url, timeout=10)
        img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
        ASSET_CACHE[url] = img
        return img
    except: return None

# --- VISUALS ENGINE (NEW SAFE CARD) ---
def draw_roulette_visual(state, username):
    W, H = 500, 500
    cx, cy = W//2, H//2

    if state == "SPIN":
        # ... (same Anime GIF generation logic)
        frames = []
        for deg in range(0, 360, 15):
            img = Image.new("RGBA", (W, H), (0,0,0,0)); draw = ImageDraw.Draw(img)
            radius = 180
            for r in range(radius, 0, -2):
                ratio = r / radius; red = int(255-80*ratio); green = int(80+175*ratio); blue = int(0+60*ratio)
                draw.ellipse((cx-r, cy-int(r*0.7), cx+r, cy+int(r*0.7)), fill=(red,green,blue))
            draw.ellipse((cx-radius, cy-int(radius*0.7), cx+radius, cy+int(radius*0.7)), outline="black", width=18)
            hole_radius = 35
            for c in range(6):
                angle = math.radians(c*60+deg); x = cx+radius*0.68*math.cos(angle); y = cy+radius*0.65*math.sin(angle)
                draw.ellipse((x-hole_radius, y-hole_radius*0.9, x+hole_radius, y+hole_radius*0.9), fill="black")
            frames.append(img.filter(ImageFilter.GaussianBlur(1.5)))
        gif_bytes = io.BytesIO()
        frames[0].save(gif_bytes, format='GIF', save_all=True, append_images=frames[1:], duration=40, loop=0, disposal=2, optimize=True)
        gif_bytes.seek(0)
        return gif_bytes

    img = Image.new('RGB', (W, H), (20,25,30))
    d = ImageDraw.Draw(img)
    
    if state == "BANG":
        random_url = random.choice(BANG_IMAGE_URLS)
        bang_image = get_asset_image(random_url)
        if bang_image: img.paste(bang_image.resize((400,400)), (50, 50), bang_image.resize((400,400)))
        d.text((cx, H - 50), f"@{username} GOT SHOT!", fill="#ff4757", font=get_font(30), anchor="mm")
        
    elif state == "SAFE":
        # --- NEW MINIMALIST SAFE CARD ---
        bg_color = (30, 40, 50)
        img.paste(bg_color, (0,0,W,H))
        
        # Shield Icon (Using Text Emoji for simplicity and reliability)
        shield_font = get_font(120)
        d.text((cx, 180), "🛡️", fill="#2ecc71", font=shield_font, anchor="mm")
        
        # Text
        main_font = get_font(50)
        user_font = get_font(30)
        d.text((cx, 300), "SAFE", fill="white", font=main_font, anchor="mm")
        d.text((cx, 360), f"@{username}", fill="#bdc3c7", font=user_font, anchor="mm")
        
        # Subtle border
        d.rectangle([20,20, W-20, H-20], outline=(50,60,70), width=5)

    png_bytes = io.BytesIO(); img.save(png_bytes, format='PNG'); png_bytes.seek(0)
    return png_bytes

# --- GAME THREAD (Updated with new scores) ---
def play_roulette_thread(bot, room_id, user, user_id):
    try:
        spin_media = draw_roulette_visual("SPIN", user)
        if not spin_media: return

        spin_link = upload_media(bot, spin_media, is_gif=True)
        if spin_link:
            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": spin_link, "text": "Spinning...", "id": uuid.uuid4().hex})
        else: bot.send_message(room_id, "🔫 Spinning...")
        time.sleep(3)

        dead = (random.randint(1, 6) == 1)

        if dead:
            # LOSE
            add_game_result(user_id, user, "roulette", LOSE_PENALTY, is_win=False)
            img_bytes = draw_roulette_visual("BANG", user)
            link = upload_media(bot, img_bytes)
            
            if link: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Bang!", "id": uuid.uuid4().hex})
            bot.send_message(room_id, f"💥 **BOOM!** @{user} lost {abs(LOSE_PENALTY)} Coins!")
            
            if user_id: time.sleep(1); bot.send_json({"handler": "kickuser", "id": uuid.uuid4().hex, "roomid": room_id, "to": user_id})
        else:
            # WIN
            add_game_result(user_id, user, "roulette", WIN_REWARD, is_win=True)
            img_bytes = draw_roulette_visual("SAFE", user)
            link = upload_media(bot, img_bytes)
            
            if link: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Safe!", "id": uuid.uuid4().hex})
            bot.send_message(room_id, f"😅 **Safe!** @{user} won {WIN_REWARD} Coins.")

    except Exception as e:
        print(f"Roulette Error: {e}")

# --- HANDLER (No changes needed) ---
def handle_command(bot, command, room_id, user, args, data):
    if command.lower().strip() == "shoot":
        user_id = data.get('userid') or data.get('userID')
        if not user_id:
            bot.send_message(room_id, "⚠️ Your user ID could not be found.")
            return True
        threading.Thread(target=play_roulette_thread, args=(bot, room_id, user, user_id)).start()
        return True
    return False
