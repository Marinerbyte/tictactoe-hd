import io
import random
import requests
import threading
from PIL import Image, ImageDraw, ImageOps, ImageFilter

# --- IMPORTS ---
try: 
    import utils 
except ImportError: 
    pass

# --- CONFIG ---
MEME_API = "https://meme-api.com/gimme" # Sab type ke memes ke liye

def to_small_caps(text):
    normal = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    small  = "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ"
    trans = str.maketrans(normal, small)
    return text.translate(trans)

def setup(bot):
    print("[Meme Engine] Frames & No-Filter Mode Ready.")

# ==========================================
# 🖌️ PILLOW FRAME ENGINE (The Artist)
# ==========================================

def apply_premium_frame(img_bytes):
    """Meme ko Round Corners aur Neon Frame deta hai"""
    img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    
    # 1. Resize logic (Small optimization)
    img.thumbnail((800, 800))
    W, H = img.size
    
    # 2. Rounded Corners Mask
    radius = 50
    mask = Image.new('L', (W, H), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, W, H), radius=radius, fill=255)
    
    # Apply rounded corners
    img = ImageOps.fit(img, (W, H), centering=(0.5, 0.5))
    img.putalpha(mask)
    
    # 3. Create Canvas with Padding for Frame
    border_size = 15
    canvas_w, canvas_h = W + (border_size * 2), H + (border_size * 2)
    
    # Random Neon Color for border
    neon_colors = ["#FF00FF", "#00FFFF", "#FFFF00", "#FF0000", "#00FF00", "#FF4500"]
    frame_color = random.choice(neon_colors)
    
    # Draw Background (Frame)
    final_img = Image.new('RGBA', (canvas_w, canvas_h), (0,0,0,0))
    d_final = ImageDraw.Draw(final_img)
    
    # Draw Shadow/Glow behind
    d_final.rounded_rectangle((5, 5, canvas_w-5, canvas_h-5), radius=radius+5, fill=frame_color)
    
    # Paste Meme on Frame
    final_img.paste(img, (border_size, border_size), img)
    
    # Convert back to bytes for upload
    output = io.BytesIO()
    final_img.save(output, format='PNG')
    return output.getvalue()

# ==========================================
# ⚡ BACKGROUND WORKER
# ==========================================

def process_meme_task(bot, room_id, user):
    try:
        # 1. Fetch Meme Info (No NSFW filter as requested)
        r = requests.get(MEME_API, timeout=10).json()
        meme_url = r.get("url")
        meme_title = r.get("title", "ʟᴍᴀᴏ")
        subreddit = r.get("subreddit", "ᴍᴇᴍᴇs")

        if not meme_url: return

        # 2. Download Meme Image
        img_data = requests.get(meme_url, timeout=10).content
        
        # 3. Apply Professional Edit (Pillow)
        edited_meme = apply_premium_frame(img_data)
        
        # 4. Convert to PIL for utils.upload compatibility
        pil_to_upload = Image.open(io.BytesIO(edited_meme))
        
        # 5. Upload via bot utils
        link = utils.upload(bot, pil_to_upload)
        
        if link:
            # Send to room
            bot.send_json({
                "handler": "chatroommessage",
                "type": "image",
                "roomid": room_id,
                "url": link,
                "text": to_small_caps(f"😂 {meme_title} (ᴠɪᴀ ʀ/{subreddit})")
            })

    except Exception as e:
        print(f"[Meme Error] {e}")

# ==========================================
# 📨 COMMAND HANDLER
# ==========================================

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()

    # Command: !meme
    if cmd == "meme":
        # Seedha background thread chalao, no "searching" text
        threading.Thread(target=process_meme_task, args=(bot, room_id, user), daemon=True).start()
        return True

    return False
