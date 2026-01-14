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
BANG_IMAGE_URL = "https://www.dropbox.com/scl/fi/178rt7ol45n4ew3026ide/file_00000000ac847206b5d652e61f8445a7.png?rlkey=4pwus4m4brs1jk8t4xea5ierr&st=t2ad3zma&dl=1"
BANG_IMAGE_CACHE = None # Cache for the downloaded image

# --- HELPER FUNCTIONS ---
def get_font(size):
    try: return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except: return ImageFont.load_default()

def upload_media(bot, media_bytes, is_gif=False):
    file_format = 'gif' if is_gif else 'png'
    mime_type = 'image/gif' if is_gif else 'image/png'
    
    url = "https://api.howdies.app/api/upload"
    try:
        uid = bot.user_id if bot.user_id else 0
        files = {'file': (f'roulette.{file_format}', media_bytes, mime_type)}
        data = {'token': bot.token, 'uploadType': 'image', 'UserID': uid}
        r = requests.post(url, files=files, data=data, timeout=10)
        res = r.json()
        return res.get('url') or res.get('data', {}).get('url')
    except: return None

# --- NEW VISUALS ENGINE ---
def draw_roulette_visual(state, username):
    W, H = 500, 500
    bg_color = (20, 25, 30)
    cx, cy = W//2, H//2

    # --- STATE 1: COLORFUL SPINNING GIF ---
    if state == "SPIN":
        frames = []
        num_frames = 15
        
        for frame_num in range(num_frames):
            img = Image.new('RGB', (W, H), color=bg_color)
            d = ImageDraw.Draw(img)
            
            base_angle = frame_num * 24
            
            for i in range(6):
                angle_deg = base_angle + (i * 60)
                angle_rad = math.radians(angle_deg)
                
                x = cx + 120 * math.cos(angle_rad)
                y = cy + 120 * math.sin(angle_rad)
                
                # Alternating Red and Yellow colors
                chamber_color = "#ffc312" if i % 2 == 0 else "#c23616" # Yellow / Red
                outline_color = "#e1b12c" if i % 2 == 0 else "#8c270f"

                # 3D Effect
                d.ellipse([(x-37, y-37), (x+37, y+37)], fill=(20,20,20)) # Shadow
                d.ellipse([(x-35, y-35), (x+35, y+35)], fill=chamber_color, outline=outline_color, width=4)

            # Motion blur
            blurred_frame = img.filter(ImageFilter.GaussianBlur(radius=2))
            frames.append(blurred_frame)

        gif_bytes = io.BytesIO()
        frames[0].save(gif_bytes, format='GIF', save_all=True, append_images=frames[1:], duration=50, loop=0)
        gif_bytes.seek(0)
        return gif_bytes

    # --- STATE 2: CUSTOM BANG IMAGE ---
    elif state == "BANG":
        global BANG_IMAGE_CACHE
        if BANG_IMAGE_CACHE is None:
            try:
                print("Downloading BANG image for the first time...")
                resp = requests.get(BANG_IMAGE_URL, timeout=10)
                BANG_IMAGE_CACHE = Image.open(io.BytesIO(resp.content)).convert("RGBA")
            except Exception as e:
                print(f"Failed to load BANG image: {e}")
                # Fallback to simple text
                img = Image.new('RGB', (W,H), (60,10,10)); d = ImageDraw.Draw(img)
                d.text((cx,cy), "BOOM!", font=get_font(60), anchor="mm");
                png_bytes = io.BytesIO(); img.save(png_bytes, format='PNG'); png_bytes.seek(0)
                return png_bytes
        
        # Create a background and paste the cached image onto it
        img = Image.new('RGB', (W, H), color=bg_color)
        
        # Resize BANG image to fit
        bang_resized = BANG_IMAGE_CACHE.resize((400, 400))
        img.paste(bang_resized, (W//2 - 200, H//2 - 200), bang_resized)
        
        # Add text over the image
        d = ImageDraw.Draw(img)
        d.text((cx, H - 50), f"@{username} GOT SHOT!", fill="#ff4757", font=get_font(30), anchor="mm")
        
        png_bytes = io.BytesIO(); img.save(png_bytes, format='PNG'); png_bytes.seek(0)
        return png_bytes

    # --- STATE 3: SAFE CARD ---
    elif state == "SAFE":
        img = Image.new('RGB', (W, H), color=bg_color)
        d = ImageDraw.Draw(img)
        card_w, card_h = 300, 400
        d.rectangle([(cx-card_w//2, cy-card_h//2), (cx+card_w//2, cy+card_h//2)], fill=(250, 250, 240), outline="gold", width=5)
        d.text((cx, 150), "🍀", font=get_font(100), anchor="mm")
        d.text((cx, 250), "LUCKY YOU!", fill="#27ae60", font=get_font(40), anchor="mm")
        d.text((cx, 300), f"@{username}", fill="black", font=get_font(30), anchor="mm")
        d.text((cx, 350), "You Survived", fill="gray", font=get_font(20), anchor="mm")
        png_bytes = io.BytesIO(); img.save(png_bytes, format='PNG'); png_bytes.seek(0)
        return png_bytes
        
    return None

# --- GAME THREAD ---
def play_roulette_thread(bot, room_id, user, user_id, is_hard):
    try:
        # 1. SPIN (Generates a GIF)
        spin_gif_bytes = draw_roulette_visual("SPIN", user)
        spin_link = upload_media(bot, spin_gif_bytes, is_gif=True)
        
        if spin_link:
            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": spin_link, "text": "Spinning...", "id": uuid.uuid4().hex})
        else:
            bot.send_message(room_id, "🔫 Spinning...")
        
        time.sleep(3)

        # 2. LOGIC
        bullets = 3 if is_hard else 1; reward = 1500 if is_hard else 500
        chamber = random.randint(1, 6)
        dead = (chamber <= bullets)

        if dead:
            # LOSE
            add_game_result(user_id, user, "roulette", -500, is_win=False)
            img_bytes = draw_roulette_visual("BANG", user)
            link = upload_media(bot, img_bytes)
            
            if link: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Bang!", "id": uuid.uuid4().hex})
            else: bot.send_message(room_id, f"💥 **BOOM!** @{user} lost 500 Coins!")
            
            if user_id: time.sleep(1); bot.send_json({"handler": "kickuser", "id": uuid.uuid4().hex, "roomid": room_id, "to": user_id})
        
        else:
            # WIN
            add_game_result(user_id, user, "roulette", reward, is_win=True)
            img_bytes = draw_roulette_visual("SAFE", user)
            link = upload_media(bot, img_bytes)
            
            if link: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Safe!", "id": uuid.uuid4().hex})
            else: bot.send_message(room_id, f"😅 **Safe!** @{user} won {reward} Coins.")

    except Exception as e:
        print(f"Roulette Error: {e}")

# --- HANDLER ---
def handle_command(bot, command, room_id, user, args, data):
    cmd_clean = command.lower().strip()
    if cmd_clean == "shoot":
        user_id_from_data = data.get('userid')
        if not user_id_from_data: return True
        
        is_hard = (args and args[0].lower() == "hard")
        threading.Thread(target=play_roulette_thread, args=(bot, room_id, user, user_id_from_data, is_hard)).start()
        return True
    return False
