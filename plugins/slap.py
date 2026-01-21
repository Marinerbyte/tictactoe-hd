import sys
import os
import random
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageSequence, ImageOps

# --- IMPORTS ---
try: import utils
except ImportError: print("[Slap] Error: utils.py not found!")

def setup(bot):
    print("[Fun] Slap Engine (Async) Loaded.")

# ==========================================
# 📦 ASSETS
# ==========================================

GIFS = {
    "m": [
        "https://media.tenor.com/Ws6Dm1ZW_vMAAAAC/girl-slap.gif",
        "https://media.tenor.com/CvBTA0Jyh1kAAAAC/slap-hit.gif",
        "https://media.tenor.com/eU5H6GbVjrcAAAAC/slap-jjk.gif"
    ],
    "f": [
        "https://media.tenor.com/1-1M4PZpYcMAAAAC/slap-angry.gif",
        "https://media.tenor.com/HuP_R8Z0juAAAAAC/slap-woman.gif",
        "https://media.tenor.com/E3OqOorM80AAAAAC/slap-girl.gif"
    ],
    "x": [
        "https://media.tenor.com/XiYuU9h44-AAAAAC/anime-slap-mad.gif",
        "https://media.tenor.com/Sp7yE5UzqFMAAAAC/spank-slap.gif"
    ]
}

# ==========================================
# 🎬 GIF GENERATOR ENGINE
# ==========================================

def create_slap_gif(gif_url, text):
    try:
        # Download
        response = requests.get(gif_url, timeout=10)
        original_gif = Image.open(BytesIO(response.content))
        
        frames = []
        W, H = 400, 350 # Thoda size kam kiya taaki FAST ho (Upload fail na ho)
        gif_w, gif_h = 350, 250 
        
        # Base Background (Ek hi baar banayenge memory bachane ke liye)
        bg_base = utils.get_gradient(W, H, "#232526", "#414345")
        d = ImageDraw.Draw(bg_base)
        d.rectangle([25, 25, 375, 275], outline="white", width=2)
        
        # Text
        utils.write_text(d, (W//2, 310), text, size=22, align="center", col="#FFD700", shadow=True)
        
        # Process Frames (Limit to 15 frames max to prevent Timeout/Crash)
        i = 0
        for frame in ImageSequence.Iterator(original_gif):
            i += 1
            if i > 20: break # Safety limit
            
            frame = frame.convert("RGBA")
            frame = frame.resize((gif_w, gif_h), Image.Resampling.NEAREST) # Nearest is faster
            
            new_frame = bg_base.copy()
            new_frame.paste(frame, (25, 25), frame)
            frames.append(new_frame)

        if not frames: return None

        # Optimization: Quality kam aur Speed zyada
        output = BytesIO()
        frames[0].save(
            output, 
            format="GIF", 
            save_all=True, 
            append_images=frames[1:], 
            duration=original_gif.info.get('duration', 100),
            loop=0, 
            disposal=2,
            optimize=True # File size chhota karega
        )
        output.seek(0)
        return output

    except Exception as e:
        print(f"GIF Gen Error: {e}")
        return None

# ==========================================
# ⚙️ HANDLER (BACKGROUND THREAD)
# ==========================================

def process_slap_task(bot, room_id, style, text):
    """Ye function Background me chalega"""
    try:
        # 1. Select GIF
        gif_url = random.choice(GIFS.get(style, GIFS["m"]))
        
        # 2. Generate (Heavy Task)
        final_gif = create_slap_gif(gif_url, text)
        
        if final_gif:
            # 3. Upload
            link = utils.upload(bot, final_gif, ext="gif")
            if link:
                bot.send_json({
                    "handler": "chatroommessage", 
                    "roomid": room_id, 
                    "type": "image", 
                    "url": link, 
                    "text": "Slap"
                })
            else:
                bot.send_message(room_id, "❌ Slap miss ho gaya (Upload Failed).")
        else:
            bot.send_message(room_id, "❌ Camera kharab ho gaya (GIF Error).")
            
    except Exception as e:
        print(f"Background Task Error: {e}")

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    
    if cmd == "slap":
        if not args:
            bot.send_message(room_id, "Usage: `!slap <m/f> @user`")
            return True
            
        style = "m"
        target = args[0]
        
        if args[0].lower() in ["m", "f", "x"]:
            style = args[0].lower()
            if len(args) > 1: target = args[1]
        
        target = target.replace("@", "")
        
        # Revenge Logic
        my_name = bot.user_data.get('username', 'Bot')
        if target.lower() == my_name.lower():
            target = user; style = "x"; text = f"🤖 Bot ne @{user} ko dhoya!"
        else:
            text = f"👋 @{user} ne @{target} ko mara!"

        bot.send_message(room_id, f"🎥 **Recording Action...**")
        
        # 🔥 CRITICAL FIX: Run in Background
        # Ye bot ko block hone se rokega
        utils.run_in_bg(process_slap_task, bot, room_id, style, text)
        
        return True

    return False
