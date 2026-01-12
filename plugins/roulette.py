import time
import random
import requests
import io
import sys
import os
import uuid
import math
import threading
from PIL import Image, ImageDraw, ImageFont

# Import DB
try:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    import db
except Exception as e:
    print(f"DB Import Error: {e}")

# --- HELPER FUNCTIONS ---
def update_coins(user_id, amount):
    conn = db.get_connection()
    if not conn: return
    cur = conn.cursor()
    try:
        try: cur.execute("INSERT INTO users (user_id, username, global_score, wins) VALUES (%s, %s, 0, 0) ON CONFLICT (user_id) DO NOTHING", (user_id, user_id))
        except: cur.execute("INSERT OR IGNORE INTO users (user_id, username, global_score, wins) VALUES (?, ?, 0, 0)", (user_id, user_id))
        query = "UPDATE users SET global_score = global_score + %s WHERE user_id = %s"
        if not db.DATABASE_URL.startswith("postgres"): query = "UPDATE users SET global_score = global_score + ? WHERE user_id = ?"
        cur.execute(query, (amount, user_id))
        conn.commit()
    except: pass
    finally: conn.close()

def upload_image(bot, image):
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    url = "https://api.howdies.app/api/upload"
    try:
        uid = bot.user_id if bot.user_id else 0
        files = {'file': ('roulette.png', img_byte_arr, 'image/png')}
        data = {'token': bot.token, 'uploadType': 'image', 'UserID': uid}
        r = requests.post(url, files=files, data=data)
        res = r.json()
        return res.get('url') or res.get('data', {}).get('url')
    except: return None

# --- NEW: EMOJI & SPIN VISUALS ---
def draw_roulette_visual(state, username):
    W, H = 400, 400
    
    # Colors
    if state == "SPIN": bg_color = (30, 30, 35) # Dark Gray
    elif state == "BANG": bg_color = (60, 10, 10) # Dark Red
    else: bg_color = (10, 60, 20) # Dark Green
    
    img = Image.new('RGB', (W, H), color=bg_color)
    d = ImageDraw.Draw(img)
    
    cx, cy = W//2, H//2
    
    # Fonts
    try: font_emoji = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 100)
    except: font_emoji = ImageFont.load_default()
    
    try: font_text = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30)
    except: font_text = ImageFont.load_default()

    # --- STATE 1: SPINNING ILLUSION ---
    if state == "SPIN":
        # Draw blurred concentric circles to look like motion
        for r in range(120, 20, -10):
            color = (80 + r, 80 + r, 80 + r) # Gradient Gray
            d.ellipse([(cx-r, cy-r), (cx+r, cy+r)], outline=color, width=4)
        
        # Draw Motion Lines (Arcs)
        for i in range(0, 360, 45):
            start = i
            end = i + 30
            d.arc([(cx-100, cy-100), (cx+100, cy+100)], start=start, end=end, fill="white", width=2)
        
        # Center Text
        txt = "Tk.. Tk.."
        bbox = d.textbbox((0, 0), txt, font=font_text)
        d.text(((W-(bbox[2]-bbox[0]))/2, cy-15), txt, fill="yellow", font=font_text)
        
        # Bottom Text
        d.text((80, 350), "Spinning...", fill="gray", font=font_text)

    # --- STATE 2: BANG (LOSE) ---
    elif state == "BANG":
        # Jagged Burst Background
        d.ellipse([(cx-130, cy-130), (cx+130, cy+130)], fill=(100, 0, 0))
        
        # Big Emoji
        emoji = "💥"
        # Note: Linux fonts might render emoji as B/W glyphs. 
        # Drawing a simple Boom star shape just in case emoji fails visually
        d.regular_polygon((cx, cy, 100), 12, rotation=0, fill="orange", outline="yellow")
        
        # Text Overlay
        bbox = d.textbbox((0, 0), "BOOM!", font=font_text)
        d.text(((W-(bbox[2]-bbox[0]))/2, cy-20), "BOOM!", fill="black", font=font_text)
        
        # Info
        msg = "-500 Coins"
        bbox = d.textbbox((0, 0), msg, font=font_text)
        d.text(((W-(bbox[2]-bbox[0]))/2, 320), msg, fill="yellow", font=font_text)

    # --- STATE 3: SAFE (WIN) ---
    elif state == "SAFE":
        # Green Circle
        d.ellipse([(cx-120, cy-120), (cx+120, cy+120)], fill=(34, 139, 34), outline="white", width=5)
        
        # Draw Smile (Manual drawing to be safe if emoji fails)
        # Face
        d.ellipse([(cx-80, cy-80), (cx+80, cy+80)], fill="yellow")
        # Eyes
        d.arc([(cx-50, cy-40), (cx-20, cy-20)], start=0, end=180, fill="black", width=3)
        d.arc([(cx+20, cy-40), (cx+50, cy-20)], start=0, end=180, fill="black", width=3)
        # Sweat
        d.ellipse([(cx+50, cy-60), (cx+65, cy-40)], fill="cyan")
        # Smile
        d.arc([(cx-40, cy), (cx+40, cy+40)], start=0, end=180, fill="black", width=4)

        # Info
        msg = "Safe!"
        bbox = d.textbbox((0, 0), msg, font=font_text)
        d.text(((W-(bbox[2]-bbox[0]))/2, 320), msg, fill="white", font=font_text)

    return img

# --- GAME LOGIC THREAD ---
def play_roulette_thread(bot, room_id, user, user_id, is_hard):
    try:
        # 1. VISUAL: SPINNING
        spin_img = draw_roulette_visual("SPIN", user)
        spin_link = upload_image(bot, spin_img)
        
        if spin_link:
            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": spin_link, "text": "Spin", "id": uuid.uuid4().hex})
        
        time.sleep(2) # Illusion Time

        # 2. CALCULATION
        bullets = 3 if is_hard else 1
        reward = 1500 if is_hard else 500
        roll = random.randint(1, 6)
        
        dead = False
        if roll <= bullets: dead = True

        if dead:
            # --- BANG ---
            update_coins(user, -500) # Penalty
            
            img = draw_roulette_visual("BANG", user)
            link = upload_image(bot, img)
            
            bot.send_message(room_id, f"💥 **BOOM!** @{user} lost 500 Coins!")
            if link: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Bang", "id": uuid.uuid4().hex})
            
            # Kick Logic
            if user_id:
                time.sleep(1)
                bot.send_json({"handler": "kickuser", "id": uuid.uuid4().hex, "roomid": room_id, "to": user_id})
        
        else:
            # --- SAFE ---
            update_coins(user, reward)
            
            img = draw_roulette_visual("SAFE", user)
            link = upload_image(bot, img)
            
            bot.send_message(room_id, f"😅 **Safe!** @{user} won {reward} Coins.")
            if link: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Safe", "id": uuid.uuid4().hex})

    except Exception as e:
        print(f"Roulette Error: {e}")

# --- COMMAND HANDLER ---
def handle_command(bot, command, room_id, user, args, data):
    cmd_clean = command.lower().strip()

    if cmd_clean == "shoot":
        target_user_id = data.get('userid') or data.get('id')
        is_hard = (args and args[0].lower() == "hard")
        
        threading.Thread(target=play_roulette_thread, args=(bot, room_id, user, target_user_id, is_hard)).start()
        return True

    return False
