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

# --- CONFIG ---
BANG_IMAGE_URLS = [
    "https://www.dropbox.com/scl/fi/178rt7ol45n4ew3026ide/file_00000000ac847206b5d652e61f8445a7.png?rlkey=4pwus4m4brs1jk8t4xea5ierr&st=t2ad3zma&dl=1",
    "https://www.dropbox.com/scl/fi/w1rt0ohnycguyv8gujvda/file_00000000e5d8720685c235c1138550a4.png?rlkey=rj7gbft7dn1hflyf04yvtqqw2&st=cf9wie5m&dl=1"
]
BULLET_PNG_URL = "https://www.dropbox.com/scl/fi/gvp68when94fh40mwvb7f/file_00000000611c71fda680631eba29479e.png?rlkey=bxlwky1e5aavkz0ui2456d37d&st=gh45cydr&dl=1"
ASSET_CACHE = {}

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
        r = requests.post(url, files=files, data=data, timeout=10)
        return r.json().get('url') or r.json().get('data', {}).get('url')
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

# --- VISUALS ENGINE (WITH BULLET CYLINDER) ---
def draw_roulette_visual(state, username, bullets=1):
    W, H = 500, 500
    bg_color = (20, 25, 30)
    cx, cy = W//2, H//2

    # --- STATE 1: SPINNING BULLETS GIF ---
    if state == "SPIN":
        frames = []
        # Load the bullet PNG, resized to act as a chamber
        bullet_chamber_img = get_asset_image(BULLET_PNG_URL, size=(80, 80))
        if not bullet_chamber_img: # Fallback if image fails
            return None 

        for frame_num in range(15):
            img = Image.new('RGB', (W, H), color=bg_color)
            base_angle = frame_num * 24
            
            # Draw 6 bullets rotating in a circle
            for i in range(6):
                angle_deg = base_angle + (i * 60)
                angle_rad = math.radians(angle_deg)
                
                # Position of each bullet
                x = cx + 120 * math.cos(angle_rad)
                y = cy + 120 * math.sin(angle_rad)
                
                # Rotate the bullet image itself to point outwards
                rotated_bullet = bullet_chamber_img.rotate(-angle_deg - 90, expand=False)
                
                paste_pos = (int(x - rotated_bullet.width / 2), int(y - rotated_bullet.height / 2))
                img.paste(rotated_bullet, paste_pos, rotated_bullet)

            frames.append(img.filter(ImageFilter.GaussianBlur(radius=1)))

        gif_bytes = io.BytesIO()
        frames[0].save(gif_bytes, format='GIF', save_all=True, append_images=frames[1:], duration=50, loop=0)
        gif_bytes.seek(0)
        return gif_bytes

    # --- OTHER STATES (BANG / SAFE) ---
    img = Image.new('RGB', (W, H), color=bg_color)
    d = ImageDraw.Draw(img)
    
    if state == "BANG":
        random_url = random.choice(BANG_IMAGE_URLS)
        bang_image = get_asset_image(random_url)
        if bang_image:
            img.paste(bang_image.resize((400,400)), (50, 50), bang_image.resize((400,400)))
        d.text((cx, H - 50), f"@{username} GOT SHOT!", fill="#ff4757", font=get_font(30), anchor="mm")
        
    elif state == "SAFE":
        d.rectangle([(cx-150, cy-200), (cx+150, cy+200)], fill=(250, 250, 240), outline="gold", width=5)
        d.text((cx, 150), "🍀", font=get_font(100), anchor="mm")
        d.text((cx, 250), "LUCKY YOU!", fill="#27ae60", font=get_font(40), anchor="mm")
        d.text((cx, 300), f"@{username}", fill="black", font=get_font(30), anchor="mm")

    png_bytes = io.BytesIO(); img.save(png_bytes, format='PNG'); png_bytes.seek(0)
    return png_bytes

# --- GAME THREAD & HANDLER (Same as before) ---
def play_roulette_thread(bot, room_id, user, user_id, is_hard):
    try:
        bullets = 3 if is_hard else 1; reward = 1500 if is_hard else 500
        spin_media = draw_roulette_visual("SPIN", user, bullets=bullets)
        if not spin_media: bot.send_message(room_id, "Error generating spin visual."); return
            
        spin_link = upload_media(bot, spin_media, is_gif=True)
        if spin_link:
            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": spin_link, "text": f"Spinning with {bullets} bullet(s)...", "id": uuid.uuid4().hex})
        else: bot.send_message(room_id, "🔫 Spinning...")
        time.sleep(3)

        dead = (random.randint(1, 6) <= bullets)

        if dead:
            add_game_result(user_id, user, "roulette", -500, is_win=False)
            img_bytes = draw_roulette_visual("BANG", user)
            link = upload_media(bot, img_bytes)
            if link: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Bang!", "id": uuid.uuid4().hex})
            else: bot.send_message(room_id, f"💥 **BOOM!**")
            if user_id: time.sleep(1); bot.send_json({"handler": "kickuser", "id": uuid.uuid4().hex, "roomid": room_id, "to": user_id})
        else:
            add_game_result(user_id, user, "roulette", reward, is_win=True)
            img_bytes = draw_roulette_visual("SAFE", user)
            link = upload_media(bot, img_bytes)
            if link: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Safe!", "id": uuid.uuid4().hex})
            else: bot.send_message(room_id, f"😅 **Safe!**")
    except Exception as e:
        print(f"Roulette Error: {e}")

def handle_command(bot, command, room_id, user, args, data):
    if command.lower().strip() == "shoot":
        user_id = data.get('userid') or data.get('userID')
        if not user_id:
            bot.send_message(room_id, "⚠️ Your user ID could not be found.")
            return True
        is_hard = (args and args[0].lower() == "hard")
        threading.Thread(target=play_roulette_thread, args=(bot, room_id, user, user_id, is_hard)).start()
        return True
    return False
