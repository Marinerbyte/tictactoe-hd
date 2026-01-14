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

# --- HELPER FUNCTIONS ---
def get_font(size):
    try: return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except: return ImageFont.load_default()

def upload_media(bot, media_bytes, is_gif=False):
    """Handles both PNG and GIF uploads"""
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

# --- NEW VISUALS ENGINE (WITH GIF) ---
def draw_roulette_visual(state, username):
    W, H = 500, 500
    bg_color = (20, 25, 30)

    # --- STATE 1: SPINNING GIF ---
    if state == "SPIN":
        frames = []
        num_frames = 15 # No. of frames in GIF
        
        for frame_num in range(num_frames):
            img = Image.new('RGB', (W, H), color=bg_color)
            d = ImageDraw.Draw(img)
            cx, cy = W//2, H//2

            # Gun barrel on the left
            d.rectangle([30, cy-30, 120, cy+30], fill=(50,50,50), outline=(80,80,80))
            
            # Draw Cylinder
            main_radius = 120
            chamber_radius = 35
            
            # Rotation angle changes each frame
            base_angle = (frame_num * 24) # 360 / 15 frames = 24 degrees per frame
            
            # Draw each of the 6 chambers
            for i in range(6):
                angle_deg = base_angle + (i * 60)
                angle_rad = math.radians(angle_deg)
                
                x = cx + main_radius * math.cos(angle_rad)
                y = cy + main_radius * math.sin(angle_rad)
                
                # 3D Effect: Shadow first, then the hole
                d.ellipse([(x-chamber_radius+2, y-chamber_radius+2), (x+chamber_radius+2, y+chamber_radius+2)], fill=(30,30,30))
                d.ellipse([(x-chamber_radius, y-chamber_radius), (x+chamber_radius, y+chamber_radius)], fill=(50,50,50), outline=(80,80,80))

            # Add motion blur to the whole image for a faster feel
            blurred_frame = img.filter(ImageFilter.GaussianBlur(radius=2))
            frames.append(blurred_frame)

        # Save GIF to memory
        gif_bytes = io.BytesIO()
        frames[0].save(gif_bytes, format='GIF', save_all=True, append_images=frames[1:], duration=50, loop=0)
        gif_bytes.seek(0)
        return gif_bytes

    # --- STATIC IMAGES (BANG / SAFE) ---
    img = Image.new('RGB', (W, H), color=bg_color)
    d = ImageDraw.Draw(img)
    cx, cy = W//2, H//2
    
    if state == "BANG":
        bg_color = (60, 10, 10)
        img.paste(bg_color, (0,0,W,H))
        
        d.ellipse([(cx-20, cy-20), (cx+20, cy+20)], fill="black")
        for i in range(8):
            angle = math.radians(random.randint(0, 360))
            length = random.randint(40, 100)
            end_x = cx + length * math.cos(angle)
            end_y = cy + length * math.sin(angle)
            d.line([(cx, cy), (end_x, end_y)], fill=(150,150,150), width=2)
        d.text((cx, H - 80), f"@{username}", fill="white", font=get_font(40), anchor="mm")
        d.text((cx, H - 40), "You Died (-500)", fill="#ff4757", font=get_font(30), anchor="mm")
        
    elif state == "SAFE":
        card_w, card_h = 300, 400
        d.rectangle([(cx-card_w//2, cy-card_h//2), (cx+card_w//2, cy+card_h//2)], fill=(250, 250, 240), outline="gold", width=5)
        d.text((cx, 150), "🍀", font=get_font(100), anchor="mm")
        d.text((cx, 250), "LUCKY YOU!", fill="#27ae60", font=get_font(40), anchor="mm")
        d.text((cx, 300), f"@{username}", fill="black", font=get_font(30), anchor="mm")
        d.text((cx, 350), "You Survived", fill="gray", font=get_font(20), anchor="mm")

    # Save PNG to memory
    png_bytes = io.BytesIO()
    img.save(png_bytes, format='PNG')
    png_bytes.seek(0)
    return png_bytes

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
            bot.send_message(room_id, f"💥 **BOOM!** @{user} lost 500 Coins!")
            
            if user_id: time.sleep(1); bot.send_json({"handler": "kickuser", "id": uuid.uuid4().hex, "roomid": room_id, "to": user_id})
        
        else:
            # WIN
            add_game_result(user_id, user, "roulette", reward, is_win=True)
            img_bytes = draw_roulette_visual("SAFE", user)
            link = upload_media(bot, img_bytes)
            
            if link: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Safe!", "id": uuid.uuid4().hex})
            bot.send_message(room_id, f"😅 **Safe!** @{user} won {reward} Coins.")

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
