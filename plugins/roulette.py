import time
import random
import requests
import io
import sys
import os
import uuid
import threading
import math
from PIL import Image, ImageDraw, ImageFont

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

def upload_image(bot, image):
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    url = "https://api.howdies.app/api/upload"
    try:
        uid = bot.user_id if bot.user_id else 0
        files = {'file': ('roulette.png', img_byte_arr, 'image/png')}
        data = {'token': bot.token, 'uploadType': 'image', 'UserID': uid}
        r = requests.post(url, files=files, data=data, timeout=10)
        res = r.json()
        return res.get('url') or res.get('data', {}).get('url')
    except: return None

# --- NEW VISUALS ENGINE ---
def draw_roulette_visual(state, username, bullets=1, result_angle=0):
    W, H = 500, 500
    
    # Define colors
    bg_color = (20, 25, 30) # Dark Blue/Gray
    metal_light = (180, 180, 180)
    metal_dark = (100, 100, 100)
    wood_color = (139, 69, 19)

    img = Image.new('RGB', (W, H), color=bg_color)
    d = ImageDraw.Draw(img)
    cx, cy = W//2, H//2

    # --- STATE 1: SPINNING CYLINDER ---
    if state == "SPIN":
        # Draw Gun Barrel side view
        d.rectangle([20, cy-30, 100, cy+30], fill=metal_dark)
        # Revolver Cylinder
        radius = 120
        for i in range(6):
            angle = math.radians(i * 60 + 45) # Rotate for dynamic look
            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle)
            d.ellipse([(x-30, y-30), (x+30, y+30)], fill=metal_light, outline=metal_dark)
        # Blurred overlay for motion effect
        blur = Image.new('RGBA', (W, H), (0,0,0,0))
        blur_draw = ImageDraw.Draw(blur)
        blur_draw.ellipse([(cx-radius, cy-radius), (cx+radius, cy+radius)], fill=(255,255,255,50))
        img.paste(blur, (0,0), blur)
        
        d.text((cx, cy), "Spinning...", fill="yellow", font=get_font(40), anchor="mm")

    # --- STATE 2: BANG! ---
    elif state == "BANG":
        # Bullet Hole in center
        d.ellipse([(cx-20, cy-20), (cx+20, cy+20)], fill="black")
        # Cracks
        for i in range(8):
            angle = math.radians(random.randint(0, 360))
            length = random.randint(40, 100)
            end_x = cx + length * math.cos(angle)
            end_y = cy + length * math.sin(angle)
            d.line([(cx, cy), (end_x, end_y)], fill=(150,150,150), width=2)
        
        d.text((cx, H - 80), f"@{username}", fill="white", font=get_font(40), anchor="mm")
        d.text((cx, H - 40), "You Died (-500)", fill="#ff4757", font=get_font(30), anchor="mm")

    # --- STATE 3: SAFE! (LUCKY CARD) ---
    elif state == "SAFE":
        # Card background
        card_w, card_h = 300, 400
        d.rectangle([(cx-card_w//2, cy-card_h//2), (cx+card_w//2, cy+card_h//2)], fill=(250, 250, 240), outline="gold", width=5)
        
        # Lucky Clover / Horseshoe Icon
        d.text((cx, 150), "🍀", font=get_font(100), anchor="mm")
        
        # Text
        d.text((cx, 250), "LUCKY YOU!", fill="#27ae60", font=get_font(40), anchor="mm")
        d.text((cx, 300), f"@{username}", fill="black", font=get_font(30), anchor="mm")
        d.text((cx, 350), "You Survived", fill="gray", font=get_font(20), anchor="mm")
        
    return img

# --- GAME THREAD ---
def play_roulette_thread(bot, room_id, user, user_id, is_hard):
    try:
        # 1. SPIN VISUAL
        spin_img = draw_roulette_visual("SPIN", user)
        spin_link = upload_image(bot, spin_img)
        
        if spin_link:
            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": spin_link, "text": "Spinning the cylinder...", "id": uuid.uuid4().hex})
        else:
            bot.send_message(room_id, "🔫 Spinning...")
        
        time.sleep(3) # More suspense

        # 2. LOGIC
        bullets = 3 if is_hard else 1
        reward = 1500 if is_hard else 500
        chamber = random.randint(1, 6)
        
        dead = (chamber <= bullets)

        if dead:
            # LOSE
            add_game_result(user_id, user, "roulette", -500, is_win=False)
            
            img = draw_roulette_visual("BANG", user)
            link = upload_image(bot, img)
            
            if link: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Bang!", "id": uuid.uuid4().hex})
            bot.send_message(room_id, f"💥 **BOOM!** @{user} lost 500 Coins!")
            
            # Kick Logic
            if user_id:
                time.sleep(1)
                bot.send_json({"handler": "kickuser", "id": uuid.uuid4().hex, "roomid": room_id, "to": user_id})
        
        else:
            # WIN
            add_game_result(user_id, user, "roulette", reward, is_win=True)
            
            img = draw_roulette_visual("SAFE", user)
            link = upload_image(bot, img)
            
            if link: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Safe!", "id": uuid.uuid4().hex})
            bot.send_message(room_id, f"😅 **Phew! Safe!** @{user} won {reward} Coins.")

    except Exception as e:
        print(f"Roulette Error: {e}")

# --- COMMAND HANDLER ---
def handle_command(bot, command, room_id, user, args, data):
    cmd_clean = command.lower().strip()

    if cmd_clean == "shoot":
        user_id_from_data = data.get('userid')
        if not user_id_from_data:
            bot.send_message(room_id, "Error: Your User ID is not available.")
            return True
        
        is_hard = (len(args) > 0 and args[0].lower() == "hard")
        
        # Prevent spamming by checking if a game is already running (simple check)
        # (A more robust check would use a global dict like in Ludo)
        
        threading.Thread(target=play_roulette_thread, args=(bot, room_id, user, user_id_from_data, is_hard)).start()
        return True

    return False
