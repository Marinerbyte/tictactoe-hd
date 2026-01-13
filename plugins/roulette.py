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

# --- NEW: UNIFIED DB STATS UPDATE ---
def update_stats(user_id, username, amount, is_win=False):
    """Updates Global & Roulette Specific Stats"""
    if not user_id or user_id == "BOT": return
    
    conn = db.get_connection()
    if not conn: return
    cur = conn.cursor()
    
    try:
        win_count = 1 if is_win else 0
        
        # 1. Global Stats
        try: cur.execute("INSERT INTO users (user_id, username, global_score, wins) VALUES (%s, %s, 0, 0) ON CONFLICT (user_id) DO NOTHING", (user_id, username))
        except: cur.execute("INSERT OR IGNORE INTO users (user_id, username, global_score, wins) VALUES (?, ?, 0, 0)", (user_id, username))
        
        q1 = "UPDATE users SET global_score = global_score + %s, wins = wins + %s WHERE user_id = %s"
        if not db.DATABASE_URL.startswith("postgres"): q1 = "UPDATE users SET global_score = global_score + ?, wins = wins + ? WHERE user_id = ?"
        cur.execute(q1, (amount, win_count, user_id))
        
        # 2. Roulette Stats
        try: cur.execute("INSERT INTO game_stats (user_id, game_name, wins, earnings) VALUES (%s, 'roulette', 0, 0) ON CONFLICT (user_id, game_name) DO NOTHING", (user_id,))
        except: cur.execute("INSERT OR IGNORE INTO game_stats (user_id, game_name, wins, earnings) VALUES (?, 'roulette', 0, 0)", (user_id,))
        
        q2 = "UPDATE game_stats SET earnings = earnings + %s, wins = wins + %s WHERE user_id = %s AND game_name = 'roulette'"
        if not db.DATABASE_URL.startswith("postgres"): q2 = "UPDATE game_stats SET earnings = earnings + ?, wins = wins + ? WHERE user_id = ? AND game_name = 'roulette'"
        cur.execute(q2, (amount, win_count, user_id))
        
        conn.commit()
    except Exception as e:
        print(f"DB Error: {e}")
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

# --- VISUALS ---
def draw_roulette_visual(state, username):
    W, H = 400, 400
    if state == "SPIN": bg_color = (30, 30, 35)
    elif state == "BANG": bg_color = (60, 10, 10)
    else: bg_color = (10, 60, 20)
    
    img = Image.new('RGB', (W, H), color=bg_color)
    d = ImageDraw.Draw(img)
    cx, cy = W//2, H//2
    
    # Fonts
    try: font_emoji = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 100)
    except: font_emoji = ImageFont.load_default()
    try: font_text = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30)
    except: font_text = ImageFont.load_default()

    if state == "SPIN":
        for r in range(120, 20, -10):
            color = (80 + r, 80 + r, 80 + r)
            d.ellipse([(cx-r, cy-r), (cx+r, cy+r)], outline=color, width=4)
        txt = "Tk.. Tk.."
        bbox = d.textbbox((0, 0), txt, font=font_text)
        d.text(((W-(bbox[2]-bbox[0]))/2, cy-15), txt, fill="yellow", font=font_text)
        d.text((80, 350), "Spinning...", fill="gray", font=font_text)

    elif state == "BANG":
        d.ellipse([(cx-130, cy-130), (cx+130, cy+130)], fill=(100, 0, 0))
        d.regular_polygon((cx, cy, 100), 12, rotation=0, fill="orange", outline="yellow")
        bbox = d.textbbox((0, 0), "BOOM!", font=font_text)
        d.text(((W-(bbox[2]-bbox[0]))/2, cy-20), "BOOM!", fill="black", font=font_text)
        msg = "-500 Coins"
        bbox = d.textbbox((0, 0), msg, font=font_text)
        d.text(((W-(bbox[2]-bbox[0]))/2, 320), msg, fill="yellow", font=font_text)

    elif state == "SAFE":
        d.ellipse([(cx-120, cy-120), (cx+120, cy+120)], fill=(34, 139, 34), outline="white", width=5)
        # Face
        d.ellipse([(cx-80, cy-80), (cx+80, cy+80)], fill="yellow")
        # Eyes
        d.arc([(cx-50, cy-40), (cx-20, cy-20)], start=0, end=180, fill="black", width=3)
        d.arc([(cx+20, cy-40), (cx+50, cy-20)], start=0, end=180, fill="black", width=3)
        # Sweat
        d.ellipse([(cx+50, cy-60), (cx+65, cy-40)], fill="cyan")
        # Smile
        d.arc([(cx-40, cy), (cx+40, cy+40)], start=0, end=180, fill="black", width=4)
        msg = "Safe!"
        bbox = d.textbbox((0, 0), msg, font=font_text)
        d.text(((W-(bbox[2]-bbox[0]))/2, 320), msg, fill="white", font=font_text)

    return img

# --- GAME THREAD ---
def play_roulette_thread(bot, room_id, user, user_id, is_hard):
    try:
        # 1. SPIN
        spin_img = draw_roulette_visual("SPIN", user)
        spin_link = upload_image(bot, spin_img)
        if spin_link:
            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": spin_link, "text": "Spin", "id": uuid.uuid4().hex})
        
        time.sleep(2)

        # 2. CALCULATION
        bullets = 3 if is_hard else 1
        reward = 1500 if is_hard else 500
        roll = random.randint(1, 6)
        
        dead = False
        if roll <= bullets: dead = True

        if dead:
            # LOSE
            update_stats(user_id, user, -500, is_win=False) # Deduct 500
            
            img = draw_roulette_visual("BANG", user)
            link = upload_image(bot, img)
            
            bot.send_message(room_id, f"💥 **BOOM!** @{user} lost 500 Coins!")
            if link: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Bang", "id": uuid.uuid4().hex})
            
            # Kick (Optional)
            if user_id:
                time.sleep(1)
                bot.send_json({"handler": "kickuser", "id": uuid.uuid4().hex, "roomid": room_id, "to": user_id})
        
        else:
            # WIN
            update_stats(user_id, user, reward, is_win=True) # Add Reward
            
            img = draw_roulette_visual("SAFE", user)
            link = upload_image(bot, img)
            
            bot.send_message(room_id, f"😅 **Safe!** @{user} won {reward} Coins.")
            if link: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Safe", "id": uuid.uuid4().hex})

    except Exception as e:
        print(f"Roulette Error: {e}")

# --- HANDLER ---
def handle_command(bot, command, room_id, user, args, data):
    cmd_clean = command.lower().strip()

    if cmd_clean == "shoot":
        target_user_id = data.get('userid') or data.get('id')
        is_hard = (len(args) > 0 and args[0].lower() == "hard")
        
        if not target_user_id:
            bot.send_message(room_id, "Error: User ID not found.")
            return True

        threading.Thread(target=play_roulette_thread, args=(bot, room_id, user, target_user_id, is_hard)).start()
        return True

    return False
    if cmd_clean == "shoot":
        target_user_id = data.get('userid') or data.get('id')
        is_hard = (args and args[0].lower() == "hard")
        
        threading.Thread(target=play_roulette_thread, args=(bot, room_id, user, target_user_id, is_hard)).start()
        return True

    return False
