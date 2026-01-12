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
        files = {'file': ('gun.png', img_byte_arr, 'image/png')}
        data = {'token': bot.token, 'uploadType': 'image', 'UserID': uid}
        r = requests.post(url, files=files, data=data)
        res = r.json()
        return res.get('url') or res.get('data', {}).get('url')
    except: return None

# --- NEW: ADVANCED GUN GRAPHICS ---
def draw_gun_visual(state, username):
    """
    state: 'SPIN' (Illusion), 'BANG' (Dead), 'SAFE' (Empty)
    """
    W, H = 400, 350
    
    # Background Color
    if state == "SPIN": bg = (30, 30, 30) # Dark Gray
    elif state == "BANG": bg = (50, 10, 10) # Blood Red tint
    else: bg = (10, 40, 10) # Green tint
    
    img = Image.new('RGB', (W, H), color=bg)
    d = ImageDraw.Draw(img)
    
    cx, cy = W//2, H//2 - 20
    radius = 100

    # 1. Main Cylinder Body
    d.ellipse([(cx-radius, cy-radius), (cx+radius, cy+radius)], outline=(150, 150, 150), width=8)
    d.ellipse([(cx-10, cy-10), (cx+10, cy+10)], fill=(100, 100, 100)) # Center Pivot

    # 2. CHAMBERS LOGIC
    if state == "SPIN":
        # ILLUSION: Draw blurry arcs instead of circles to look like it's moving fast
        for i in range(0, 360, 15):
            angle_start = math.radians(i)
            angle_end = math.radians(i + 10)
            
            # Inner blur
            r1 = 50
            x1 = cx + r1 * math.cos(angle_start)
            y1 = cy + r1 * math.sin(angle_start)
            x2 = cx + r1 * math.cos(angle_end)
            y2 = cy + r1 * math.sin(angle_end)
            d.line([(x1, y1), (x2, y2)], fill=(80, 80, 80), width=25)
            
        d.text((cx-60, cy-15), "SPINNING...", fill="yellow")

    else:
        # STATIC: Draw 6 clear chambers
        for i in range(6):
            angle = math.radians(i * 60 - 90) # -90 to start top
            dist = 60
            ox = cx + int(dist * math.cos(angle))
            oy = cy + int(dist * math.sin(angle))
            
            # Chamber Style
            fill_col = (10, 10, 10) # Empty (Black)
            outline_col = (100, 100, 100)
            
            # If BANG, the top chamber (index 0) has the bullet
            if state == "BANG" and i == 0:
                fill_col = (255, 215, 0) # Gold (Bullet Casing)
                outline_col = "red"
                
                # Draw Bullet Detail
                d.ellipse([(ox-23, oy-23), (ox+23, oy+23)], fill=fill_col, outline=outline_col, width=2)
                d.ellipse([(ox-10, oy-10), (ox+10, oy+10)], fill=(150, 100, 0)) # Primer
            else:
                # Empty Chamber
                d.ellipse([(ox-20, oy-20), (ox+20, oy+20)], fill=fill_col, outline=outline_col, width=3)

    # 3. TEXT & INFO
    try: font_main = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 35)
    except: font_main = ImageFont.load_default()
    
    try: font_sub = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
    except: font_sub = ImageFont.load_default()

    if state == "SPIN":
        txt = "ROLLING THE DICE..."
        col = "white"
    elif state == "BANG":
        txt = "💥 BANG!!! 💥"
        col = "red"
    else:
        txt = "😅 CLICK... SAFE"
        col = "#00FF00" # Lime Green

    # Draw Title
    bbox = d.textbbox((0, 0), txt, font=font_main)
    w = bbox[2]-bbox[0]
    d.text(((W-w)/2, H-60), txt, fill=col, font=font_main)

    # Draw Subtitle
    if state == "BANG":
        msg = f"@{username} lost 500 Coins & Died!"
    elif state == "SAFE":
        msg = f"@{username} won 500 Coins!"
    else:
        msg = f"@{username} is testing luck..."

    bbox = d.textbbox((0, 0), msg, font=font_sub)
    d.text(((W-w)/2 - 20, H-25), msg, fill="white", font=font_sub)

    return img

# --- GAME LOGIC THREAD ---
def play_roulette_thread(bot, room_id, user, user_id, is_hard):
    try:
        # 1. SEND SPINNING ILLUSION
        spin_img = draw_gun_visual("SPIN", user)
        spin_link = upload_image(bot, spin_img)
        
        if spin_link:
            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": spin_link, "text": "Spinning", "id": uuid.uuid4().hex})
        
        time.sleep(2.5) # Suspense time (Illusion dekhne ke liye)

        # 2. CALCULATE RESULT
        # Normal: 1/6 Chance. Hard: 3/6 Chance.
        bullets = 3 if is_hard else 1
        reward = 1500 if is_hard else 500
        
        # Logic: 1 se 6 number. Agar number <= bullets, to maut.
        # Example Normal: Bullet=1. Roll=1 -> Maut. Roll=2,3,4,5,6 -> Safe.
        roll = random.randint(1, 6)
        
        dead = False
        if roll <= bullets:
            dead = True

        if dead:
            # --- DEATH LOGIC ---
            # 1. Deduct Coins First
            update_coins(user, -500)
            
            # 2. Show BANG Image
            img = draw_gun_visual("BANG", user)
            link = upload_image(bot, img)
            
            bot.send_message(room_id, f"💥 **BANG!** @{user} took a bullet!\n💸 **-500 Coins** deducted.")
            if link: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "BANG", "id": uuid.uuid4().hex})
            
            # 3. KICK (If ID available)
            if user_id:
                time.sleep(1.5) # Thoda time taaki user apna loss dekh sake
                bot.send_message(room_id, "🚑 *Medics carry the body out...* (Kicking)")
                time.sleep(0.5)
                kick_payload = {"handler": "kickuser", "id": uuid.uuid4().hex, "roomid": room_id, "to": user_id}
                bot.send_json(kick_payload)
        
        else:
            # --- SAFE LOGIC ---
            update_coins(user, reward)
            
            img = draw_gun_visual("SAFE", user)
            link = upload_image(bot, img)
            
            mode_txt = "(Hard)" if is_hard else ""
            bot.send_message(room_id, f"😅 **Click...** Empty Chamber! {mode_txt}\n💰 **+{reward} Coins** added.")
            if link: bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Safe", "id": uuid.uuid4().hex})

    except Exception as e:
        print(f"Roulette Error: {e}")

# --- MAIN HANDLER ---
def handle_command(bot, command, room_id, user, args, data):
    cmd_clean = command.lower().strip()

    if cmd_clean == "shoot":
        target_user_id = data.get('userid') or data.get('id')
        
        is_hard = False
        if args and args[0].lower() == "hard":
            is_hard = True
        
        # Run in background to prevent bot lag
        t = threading.Thread(target=play_roulette_thread, args=(bot, room_id, user, target_user_id, is_hard))
        t.start()
            
        return True

    return False
