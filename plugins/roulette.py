import time
import random
import requests
import io
import sys
import os
import uuid
import threading # Zaroori hai taaki Bot hang na ho
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
        files = {'file': ('gun.png', img_byte_arr, 'image/png')}
        data = {'token': bot.token, 'uploadType': 'image', 'UserID': uid}
        r = requests.post(url, files=files, data=data)
        res = r.json()
        return res.get('url') or res.get('data', {}).get('url')
    except: return None

def draw_gun_result(status, username, bullets_count=1):
    W, H = 400, 300
    color = (20, 20, 20)
    if status == "BANG": color = (50, 10, 10)
    img = Image.new('RGB', (W, H), color=color)
    d = ImageDraw.Draw(img)
    cx, cy = W//2, H//2
    rad = 80
    d.ellipse([(cx-rad, cy-rad), (cx+rad, cy+rad)], outline="gray", width=5)
    
    import math
    for i in range(6):
        angle = math.radians(i * 60)
        ox = cx + int(50 * math.cos(angle))
        oy = cy + int(50 * math.sin(angle))
        fill = "gray"
        if status == "BANG" and i == 0: fill = "red" 
        if bullets_count > 1 and i < bullets_count and status == "SAFE": fill = "darkgray" 
        d.ellipse([(ox-15, oy-15), (ox+15, oy+15)], fill=fill)

    try: font = ImageFont.truetype("arial.ttf", 40)
    except: font = ImageFont.load_default()
    text = "CLICK..." if status == "SAFE" else "BANG!!!"
    text_col = "green" if status == "SAFE" else "red"
    bbox = d.textbbox((0, 0), text, font=font)
    d.text(((W-(bbox[2]-bbox[0]))/2, 20), text, fill=text_col, font=font)
    msg = f"@{username} survived!" if status == "SAFE" else f"@{username} died!"
    try: font_s = ImageFont.truetype("arial.ttf", 20)
    except: font_s = ImageFont.load_default()
    bbox = d.textbbox((0, 0), msg, font=font_s)
    d.text(((W-(bbox[2]-bbox[0]))/2, 250), msg, fill="white", font=font_s)
    return img

# --- GAME LOGIC (RUNS IN BACKGROUND) ---
def play_roulette_thread(bot, room_id, user, user_id, is_hard):
    try:
        # 1. THE ILLUSION (Spinning)
        bot.send_message(room_id, f"🔄 @{user} spins the cylinder... *(Tkk.. Tkk.. Tkk..)*")
        time.sleep(2) # 2 Seconds delay for sound effect illusion

        # 2. THE TENSION (Holding Breath)
        bot.send_message(room_id, "😨 *Pointing at head... Holding breath...*")
        time.sleep(1.5) # 1.5 Seconds delay for tension

        # 3. THE RESULT
        bullets = 3 if is_hard else 1
        reward = 1500 if is_hard else 500
        roll = random.randint(1, 6)
        
        dead = False
        if is_hard:
            if roll <= 3: dead = True
        else:
            if roll == 6: dead = True
            
        if dead:
            # BANG!
            status = "BANG"
            img = draw_gun_result(status, user, bullets)
            link = upload_image(bot, img)
            
            bot.send_message(room_id, f"💥 **BANG!** @{user} dropped dead!")
            if link: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "BANG", "id": uuid.uuid4().hex})
            
            if user_id:
                time.sleep(1)
                bot.send_message(room_id, "😈 *Bot drags the body out...* (Kicking)")
                time.sleep(1)
                kick_payload = {"handler": "kickuser", "id": uuid.uuid4().hex, "roomid": room_id, "to": user_id}
                bot.send_json(kick_payload)
        else:
            # SAFE
            status = "SAFE"
            update_coins(user, reward)
            img = draw_gun_result(status, user, bullets)
            link = upload_image(bot, img)
            
            mode_text = "(Hard Mode)" if is_hard else ""
            bot.send_message(room_id, f"😅 **CLICK...** Empty Chamber! {mode_text}\n@{user} wins **{reward} Coins** for bravery.")
            if link: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Safe", "id": uuid.uuid4().hex})

    except Exception as e:
        print(f"Roulette Error: {e}")

# --- MAIN COMMAND HANDLER ---
def handle_command(bot, command, room_id, user, args, data):
    
    cmd_clean = command.lower().strip()

    if cmd_clean == "shoot":
        target_user_id = data.get('userid') or data.get('id')
        
        is_hard = False
        if args and args[0].lower() == "hard":
            is_hard = True
        
        # Start Game in Background Thread (Taaki bot hang na ho)
        t = threading.Thread(target=play_roulette_thread, args=(bot, room_id, user, target_user_id, is_hard))
        t.start()
            
        return True

    return False
