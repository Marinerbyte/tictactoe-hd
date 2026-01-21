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
    print("[Fun] Animated Slap Engine Loaded.")

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
    """
    Downloads a GIF, adds a background and text to EVERY frame,
    and re-assembles it.
    """
    try:
        # 1. Download Raw GIF
        response = requests.get(gif_url)
        original_gif = Image.open(BytesIO(response.content))
        
        frames = []
        
        # Canvas Settings
        W, H = 500, 450
        gif_w, gif_h = 450, 300 # Resize GIF to this
        
        # Pre-generate Background (Optimization: Ek hi baar banao)
        # Gradient Background
        bg_base = utils.get_gradient(W, H, "#232526", "#414345")
        
        # Add Border Frame to BG
        d = ImageDraw.Draw(bg_base)
        d.rectangle([20, 20, 480, 330], outline="white", width=3) # Frame for GIF
        
        # Write Text on BG (Optimization: Text har frame pe likhne se acha background me likh do)
        # Shadow
        utils.write_text(d, (W//2+2, 380+2), text, size=30, align="center", col="black")
        # Main Text
        utils.write_text(d, (W//2, 380), text, size=30, align="center", col="#FFD700") # Gold Text
        
        # 2. Process Each Frame
        for frame in ImageSequence.Iterator(original_gif):
            # Convert frame to RGBA to handle transparency/colors correctly
            frame = frame.convert("RGBA")
            
            # Resize frame to fit our box
            frame = frame.resize((gif_w, gif_h), Image.Resampling.LANCZOS)
            
            # Create a copy of our pre-made background
            new_frame = bg_base.copy()
            
            # Paste the GIF frame in the center
            # (25, 25) is the margin calculate based on (500-450)/2
            new_frame.paste(frame, (25, 25), frame)
            
            # We don't need to write text again, it's already on bg_base!
            
            frames.append(new_frame)

        # 3. Save as New GIF
        output = BytesIO()
        frames[0].save(
            output, 
            format="GIF", 
            save_all=True, 
            append_images=frames[1:], 
            duration=original_gif.info.get('duration', 100), # Original speed
            loop=0, 
            disposal=2
        )
        output.seek(0)
        return output

    except Exception as e:
        print(f"GIF Error: {e}")
        return None

# ==========================================
# ⚙️ HANDLER
# ==========================================

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    
    if cmd == "slap":
        if not args:
            bot.send_message(room_id, "Usage: `!slap <m/f> @user`")
            return True
            
        # Parse Arguments
        style = "m" # Default
        target = args[0]
        
        if args[0].lower() in ["m", "f", "x"]:
            style = args[0].lower()
            if len(args) > 1: target = args[1]
        
        target = target.replace("@", "")
        
        # Bot Revenge Logic
        my_name = bot.user_data.get('username', 'Bot')
        if target.lower() == my_name.lower():
            target = user # Target wapas user ban gaya
            style = "x"   # Extreme mode
            text = f"🤖 Bot SLAPPED @{user}!"
        else:
            text = f"👋 @{user} SLAPPED @{target}!"

        bot.send_message(room_id, f"🎥 **Recording Action...** (Processing GIF)")
        
        # Select GIF
        gif_url = random.choice(GIFS.get(style, GIFS["m"]))
        
        # Create Meme GIF
        final_gif = create_slap_gif(gif_url, text)
        
        if final_gif:
            # Upload (Using 'gif' extension is important)
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
                bot.send_message(room_id, "❌ Upload Failed.")
        else:
            bot.send_message(room_id, "❌ GIF Engine Error.")
            
        return True

    return False
