import os
import io
import time
import requests
import json
import threading
import traceback
from PIL import Image, ImageDraw, ImageSequence, ImageFont, ImageFilter
import utils
import db

# --- CONFIGURATION ---
TENOR_KEY = "LIVDSRZULELA"  # Public Demo Key
GIFT_PRICE = 2000
CLEANUP_TIME = 120  # 2 Minutes
MAX_FRAMES = 40     # Optimization

# --- STATE & LOCKS ---
pending_gifts = {}
gift_lock = threading.Lock()

def setup(bot):
    # Start Background Cleanup Thread
    threading.Thread(target=auto_cleanup_task, daemon=True).start()
    print("[GiftShop] Professional GIF Engine & Memory Manager Loaded.")

# ==========================================
# 🧠 MEMORY MANAGEMENT
# ==========================================

def auto_cleanup_task():
    """RAM bachane ke liye purane generated GIFs ko delete karta hai."""
    while True:
        time.sleep(30)
        now = time.time()
        with gift_lock:
            expired_users = [
                uid for uid, data in pending_gifts.items() 
                if now - data['timestamp'] > CLEANUP_TIME
            ]
            for uid in expired_users:
                del pending_gifts[uid]

# ==========================================
# 🎨 GIF PROCESSING ENGINE
# ==========================================

def create_personalized_gif(gif_url, target_name):
    try:
        # 1. Download
        resp = requests.get(gif_url, timeout=10)
        if resp.status_code != 200: return None
        
        im = Image.open(io.BytesIO(resp.content))
        
        frames = []
        size = (300, 300) 
        
        try:
            font = ImageFont.truetype("arialbd.ttf", 22)
        except:
            font = ImageFont.load_default()

        # 2. Frame Processing Loop
        i = 0
        for frame in ImageSequence.Iterator(im):
            i += 1
            if i > MAX_FRAMES: break 
            
            frame = frame.convert("RGBA").resize(size, Image.Resampling.LANCZOS)
            
            # Mask
            mask = Image.new('L', size, 0)
            draw_mask = ImageDraw.Draw(mask)
            draw_mask.ellipse((0, 0) + size, fill=255)
            
            output = Image.new("RGBA", size, (0,0,0,0))
            output.paste(frame, (0, 0), mask)
            
            d = ImageDraw.Draw(output)
            
            # Gold Border
            d.ellipse([2, 2, 298, 298], outline="#FFD700", width=5)
            d.ellipse([7, 7, 293, 293], outline=(255, 255, 255, 120), width=2)

            # Text Badge
            text = f"For {target_name.title()}"
            
            # Text Size Calculation
            # Pillow version compatibility fix
            try:
                bbox = d.textbbox((0, 0), text, font=font)
                text_w = bbox[2] - bbox[0]
            except:
                text_w = len(text) * 10 # Fallback estimation

            badge_w = text_w + 40
            bx1 = (300 - badge_w) // 2
            by1 = 240
            bx2 = bx1 + badge_w
            by2 = 240 + 35
            
            d.rounded_rectangle([bx1, by1, bx2, by2], radius=15, fill=(0,0,0,200), outline="#FFD700", width=2)
            
            # Draw Text
            d.text((150+1, 258+1), text, font=font, fill="black", anchor="mm")
            d.text((150, 258), text, font=font, fill="#FFD700", anchor="mm")

            frames.append(output)

        if not frames: return None
        
        output_io = io.BytesIO()
        frames[0].save(
            output_io, 
            format='GIF', 
            save_all=True, 
            append_images=frames[1:], 
            duration=im.info.get('duration', 100), 
            loop=0, 
            disposal=2,
            transparency=0,
            optimize=True
        )
        return output_io.getvalue()

    except Exception as e:
        print(f"[GiftEngine Error] {e}")
        traceback.print_exc()
        return None

def fetch_tenor_gif(query):
    try:
        url = f"https://g.tenor.com/v1/search?q={query}&key={TENOR_KEY}&limit=1&contentfilter=medium"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = json.loads(r.content)
            if data['results']:
                return data['results'][0]['media'][0]['mediumgif']['url']
    except: pass
    return None

# ==========================================
# ⚙️ COMMAND HANDLER
# ==========================================

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    uid = str(data.get('userid', user))
    
    # 1. GENERATE PREVIEW (!gif name query)
    if cmd in ["gif", "gf"]:
        if len(args) < 2:
            bot.send_message(room_id, "🎁 Usage: `!gif <Name> <Query>`\nExample: `!gif Yasin Rose`")
            return True
            
        target_name = args[0]
        search_query = " ".join(args[1:])
        
        bot.send_message(room_id, f"🎨 Creating custom gift for **{target_name}**... (Please wait)")
        
        def generate_task():
            try:
                # A. Find GIF
                raw_url = fetch_tenor_gif(search_query)
                if not raw_url:
                    bot.send_message(room_id, "❌ GIF not found.")
                    return

                # B. Process GIF
                processed_bytes = create_personalized_gif(raw_url, target_name)
                if not processed_bytes:
                    bot.send_message(room_id, "⚠️ Rendering failed.")
                    return

                # C. Upload (FIXED LINE)
                # Hum utils.upload use kar rahe hain jo internally sahi function call karega
                # ext='gif' batana zaroori hai taaki server sahi mime type samjhe
                upl_url = utils.upload(bot, io.BytesIO(processed_bytes), ext='gif')

                if upl_url:
                    # D. Save to State
                    with gift_lock:
                        pending_gifts[uid] = {
                            'url': upl_url,
                            'target_name': target_name,
                            'timestamp': time.time()
                        }
                    
                    # E. Send Preview
                    bot.send_json({
                        "handler": "chatroommessage",
                        "roomid": room_id,
                        "type": "image",
                        "url": upl_url,
                        "text": f"PREVIEW FOR {target_name.upper()}"
                    })
                    bot.send_message(room_id, f"💎 **Cost: {GIFT_PRICE:,} Chips**\nType `!share` to send this to {target_name}!")
                else:
                    bot.send_message(room_id, "❌ Upload server error.")
            
            except Exception as e:
                print(f"Task Error: {e}")
                traceback.print_exc() # Print full error to logs
                bot.send_message(room_id, "❌ System error occurred.")

        utils.run_in_bg(generate_task)
        return True

    # 2. SHARE & PAY (!share)
    if cmd == "share":
        gift_data = None
        with gift_lock:
            if uid in pending_gifts:
                gift_data = pending_gifts.pop(uid)
        
        if not gift_data:
            bot.send_message(room_id, "⚠️ No gift ready! Use `!gif <Name> <Topic>` first.")
            return True
            
        final_target = args[0].replace("@", "") if args else gift_data['target_name']
        
        # Economy Check
        conn = db.get_connection()
        cur = conn.cursor()
        ph = "%s" if db.DATABASE_URL.startswith("postgres") else "?"
        cur.execute(f"SELECT global_score FROM users WHERE user_id = {ph}", (uid,))
        row = cur.fetchone()
        balance = row[0] if row else 0
        conn.close()
        
        if balance < GIFT_PRICE:
            bot.send_message(room_id, f"❌ Insufficient Funds! Need **{GIFT_PRICE:,} Chips**.")
            return True
            
        # Transaction
        db.add_game_result(uid, user, "gift_sent", -GIFT_PRICE, False)
        
        # Delivery (DM)
        bot.send_dm_image(final_target, gift_data['url'], f"🎁 **SURPRISE!**\n@{user} sent you a Premium Gift!")
        
        # Room Confirmation
        bot.send_message(room_id, f"✅ **Gift Delivered!**\nSent to: {final_target}\nCost: {GIFT_PRICE:,} Chips")
        return True

    return False
