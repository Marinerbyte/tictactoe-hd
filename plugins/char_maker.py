import sys
import os
import random
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageOps

# --- IMPORTS ---
try: import utils
except ImportError: print("[CharMaker] Error: utils.py not found!")

def setup(bot):
    print("[CharMaker] Character Engine Loaded.")

# ==========================================
# 🧠 SMART STYLE SELECTOR
# ==========================================

def get_smart_avatar_url(seed, description):
    """
    Description ke hisaab se best Avatar Style chunta hai.
    """
    desc = description.lower()
    
    # Style Mapping
    if any(x in desc for x in ["robot", "bot", "cyborg", "tech", "mech"]):
        style = "bottts" # Robots
    elif any(x in desc for x in ["cute", "kid", "baby", "chibi", "kawaii"]):
        style = "fun-emoji" # Cute round faces
    elif any(x in desc for x in ["women", "girl", "lady", "female", "beauty"]):
        style = "lorelei" # Beautiful artistic style
    elif any(x in desc for x in ["sketch", "art", "drawing", "black", "white"]):
        style = "notionists" # Notion style sketch
    elif any(x in desc for x in ["monster", "ghost", "alien", "scary", "creepy"]):
        style = "thumbs" # Funny/Weird creatures
    else:
        # Default Cool Style
        style = "adventurer" 

    return f"https://api.dicebear.com/9.x/{style}/png?seed={seed}&backgroundColor=transparent&size=1024"

# ==========================================
# 🎨 PAINT SPLATTER & EFFECTS ENGINE
# ==========================================

def create_splatter_background(W, H):
    """
    Random Colour Ke Chinte (Paint Splatter) Effect banata hai.
    """
    # 1. Dark Base
    base_color = random.choice([(20, 20, 30), (30, 10, 10), (10, 30, 20), (15, 15, 20)])
    img = Image.new("RGBA", (W, H), base_color)
    d = ImageDraw.Draw(img)
    
    # 2. Random Neon Splatters
    palettes = [
        ["#FF00FF", "#00FFFF", "#FFFF00"], # Cyberpunk
        ["#FF4500", "#FFD700", "#FF69B4"], # Sunset
        ["#00FF00", "#ADFF2F", "#00FA9A"], # Toxic
        ["#1E90FF", "#00BFFF", "#87CEEB"]  # Ocean
    ]
    colors = random.choice(palettes)
    
    # Draw random abstract shapes
    for _ in range(20):
        x = random.randint(-100, W+100)
        y = random.randint(-100, H+100)
        size = random.randint(50, 300)
        color = random.choice(colors)
        
        shape_type = random.choice(["circle", "rect", "line"])
        
        # Create a separate layer for each splash to control transparency
        splash = Image.new("RGBA", (W, H), (0,0,0,0))
        ds = ImageDraw.Draw(splash)
        
        fill_col = color + "40" # Hex + Alpha (Low opacity)
        
        if shape_type == "circle":
            ds.ellipse([x, y, x+size, y+size], fill=color)
        elif shape_type == "rect":
            ds.rectangle([x, y, x+size, y+size/2], fill=color)
            
        # Blur the splash for "Glow" effect
        splash = splash.filter(ImageFilter.GaussianBlur(30))
        img.paste(splash, (0,0), splash)

    # 3. Noise Texture (Grain)
    noise = Image.effect_noise((W, H), 10).convert("RGBA")
    noise.putalpha(30) # Very subtle
    img.paste(noise, (0,0), noise)
    
    return img

def apply_glitch_effect(img, shift=5):
    """Thoda sa 3D Glitch effect deta hai"""
    r, g, b, a = img.split()
    r = ImageOps.colorize(r.convert("L"), (0,0,0), (255,0,0)).convert("RGBA")
    b = ImageOps.colorize(b.convert("L"), (0,0,0), (0,0,255)).convert("RGBA")
    
    # Shift channels
    final = Image.new("RGBA", img.size)
    final.paste(r, (shift, 0), r)
    final.paste(b, (-shift, 0), b)
    
    # Original green/alpha on top
    final = Image.alpha_composite(final, img)
    return final

# ==========================================
# 🖼️ CARD GENERATOR
# ==========================================

def draw_character_card(username, description):
    W, H = 600, 800 # Portrait Poster Style
    
    # 1. Background (Splatter Effect)
    img = create_splatter_background(W, H)
    d = ImageDraw.Draw(img)
    
    # 2. Border (Stylish Frame)
    m = 20
    d.rectangle([m, m, W-m, H-m], outline="white", width=2)
    # Corner Accents
    line_len = 60
    d.line([m, m, m+line_len, m], fill="#FFD700", width=6) # Top Left
    d.line([m, m, m, m+line_len], fill="#FFD700", width=6)
    d.line([W-m, H-m, W-m-line_len, H-m], fill="#FFD700", width=6) # Bottom Right
    d.line([W-m, H-m, W-m, H-m-line_len], fill="#FFD700", width=6)

    # 3. Avatar Generation
    avatar_url = get_smart_avatar_url(username, description)
    avatar = utils.get_image(avatar_url)
    
    if avatar:
        avatar = avatar.resize((500, 500))
        
        # Back Glow behind Avatar
        glow = Image.new("RGBA", (500, 500), (0,0,0,0))
        gd = ImageDraw.Draw(glow)
        gd.ellipse([50, 50, 450, 450], fill=(255, 255, 255, 80))
        glow = glow.filter(ImageFilter.GaussianBlur(60))
        img.paste(glow, (50, 100), glow)
        
        # Place Avatar
        img.paste(avatar, (50, 120), avatar)

    # 4. Text Overlay
    # Name Plate Background
    d.polygon([(0, 600), (W, 550), (W, H), (0, H)], fill=(0, 0, 0, 200))
    
    # Username (Big & Bold)
    utils.write_text(d, (W//2, 630), username.upper(), size=50, align="center", col="#00FFFF", shadow=True)
    
    # Description / Role
    tags = description.split()[:3] # First 3 words as tags
    tag_text = "  |  ".join([t.upper() for t in tags])
    utils.write_text(d, (W//2, 690), f"⚡ {tag_text} ⚡", size=25, align="center", col="#FFD700")
    
    # Footer
    utils.write_text(d, (W//2, 750), "GENERATED CHARACTER", size=16, align="center", col="#888")

    return img

# ==========================================
# ⚙️ HANDLER
# ==========================================

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    
    if cmd == "char":
        if len(args) < 2:
            bot.send_message(room_id, "Usage: `!char <username> <description>`\nExample: `!char yasin cute robot`")
            return True
            
        target_name = args[0].replace("@", "")
        description = " ".join(args[1:])
        
        bot.send_message(room_id, f"🎨 **Painting Character:** {target_name} ({description})...")
        
        try:
            # Generate Art
            img = draw_character_card(target_name, description)
            link = utils.upload(bot, img)
            
            if link:
                bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Character"})
                bot.send_message(room_id, f"🔥 Here is **{target_name}'s** Avatar!")
            else:
                bot.send_message(room_id, "❌ Creation failed.")
                
        except Exception as e:
            print(f"Char Error: {e}")
            bot.send_message(room_id, "⚠️ Error in art engine.")
            
        return True

    return False
