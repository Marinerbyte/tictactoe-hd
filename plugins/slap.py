import sys
import os
import random
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageOps

# --- IMPORTS ---
try: import utils
except ImportError: print("[Slap] Error: utils.py not found!")

def setup(bot):
    print("[Fun] Slap Manga Engine Loaded.")

# ==========================================
# 🎨 MANGA FX ENGINE
# ==========================================

def create_speed_lines(W, H):
    """Anime style action background lines"""
    # Create white canvas
    img = Image.new("RGBA", (W, H), "white")
    d = ImageDraw.Draw(img)
    
    # Draw center focus lines
    cx, cy = W//2, H//2
    for i in range(0, 360, 5):
        if random.random() > 0.5: continue # Random skip
        
        angle = math.radians(i)
        # Inner radius (Safe zone)
        r1 = random.randint(100, 200)
        # Outer radius
        r2 = 600
        
        x1 = cx + r1 * math.cos(angle)
        y1 = cy + r1 * math.sin(angle)
        x2 = cx + r2 * math.cos(angle)
        y2 = cy + r2 * math.sin(angle)
        
        # Width varies
        w = random.randint(1, 5)
        d.line([x1, y1, x2, y2], fill="black", width=w)
        
    return img

def get_avatar(username, vibe="normal"):
    """Smart Avatar Fetcher"""
    seed = f"{username}_{random.randint(1,999)}"
    style = "adventurer"
    if vibe == "angry": style = "notionists" # Angry sketch look
    if vibe == "dizzy": style = "fun-emoji" # Funny face
    
    url = f"https://api.dicebear.com/9.x/{style}/png?seed={seed}&size=512&backgroundColor=transparent"
    return utils.get_image(url)

# ==========================================
# 🖼️ SLAP CARD GENERATOR
# ==========================================

def draw_slap_card(slapper, victim, style="m"):
    W, H = 800, 450 # Cinematic Aspect Ratio
    
    # 1. Background (Manga Speed Lines)
    # Background color based on intensity
    bg_color = (255, 255, 255) # White
    if style == "x": bg_color = (255, 50, 50) # Red for Extreme
    
    img = Image.new("RGBA", (W, H), bg_color)
    speed_lines = create_speed_lines(W, H)
    
    # Blend lines
    img = Image.alpha_composite(img, speed_lines)
    d = ImageDraw.Draw(img)

    # 2. THE SLAPPER (Left Side)
    # Avatar fetch
    av_slapper = get_avatar(slapper, "angry")
    if av_slapper:
        av_slapper = av_slapper.resize((350, 350))
        # Add "Angry" tint
        if style == "x":
            av_slapper = ImageOps.colorize(av_slapper.convert("L"), (0,0,0), (255,0,0)).convert("RGBA")
        
        # Place on Left
        img.paste(av_slapper, (-20, 50), av_slapper)

    # 3. THE VICTIM (Right Side - Getting Hit)
    av_victim = get_avatar(victim, "dizzy")
    if av_victim:
        av_victim = av_victim.resize((300, 300))
        
        # EFFECT: Rotate & Blur to show IMPACT
        av_victim = av_victim.rotate(-30, expand=True) # Teda ho gaya
        
        # Motion Blur (Manual simulation)
        # Paste multiple times with low opacity
        for i in range(3):
            offset = (i+1) * 15
            ghost = av_victim.copy()
            ghost.putalpha(100 - (i*30))
            img.paste(ghost, (450 + offset, 80 - offset), ghost)
            
        # Main Victim Head
        img.paste(av_victim, (450, 80), av_victim)

    # 4. IMPACT EFFECT (Sticker)
    impact_url = "https://img.icons8.com/fluency/512/explosion.png"
    if style == "f": impact_url = "https://img.icons8.com/3d-fluency/512/anger.png"
    
    impact = utils.get_image(impact_url)
    if impact:
        impact = impact.resize((200, 200))
        # Center Impact
        img.paste(impact, (300, 100), impact)

    # 5. TEXT (Comic Style)
    # "POW!" Text
    pow_text = "SLAP!"
    if style == "x": pow_text = "K.O.!"
    if style == "f": pow_text = "SMACK!"
    
    # Big Shadow Text
    utils.write_text(d, (W//2+5, 30+5), pow_text, size=80, align="center", col="black")
    # Big Main Text
    text_col = "#FFD700" if style != "x" else "#FFFF00"
    utils.write_text(d, (W//2, 30), pow_text, size=80, align="center", col=text_col)

    # 6. CAPTION
    caption = f"@{slapper}  🤜  @{victim}"
    
    # Bottom Strip
    d.rectangle([0, 400, W, H], fill="black")
    utils.write_text(d, (W//2, 410), caption, size=30, align="center", col="white", shadow=False)

    return img

# ==========================================
# ⚙️ HANDLER
# ==========================================

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
        
        # Self Slap
        if target.lower() == user.lower():
            bot.send_message(room_id, "⚠️ Khud ko kyu maar rahe ho bhai?")
            return True

        bot.send_message(room_id, f"💢 **{user}** is winding up a slap...")
        
        # Background Worker (Safe Upload)
        utils.run_in_bg(process_slap, bot, room_id, user, target, style)
        
        return True

    return False

def process_slap(bot, room_id, user, target, style):
    try:
        # Generate Comic Card
        img = draw_slap_card(user, target, style)
        link = utils.upload(bot, img)
        
        if link:
            # Random Funny Text
            comments = [
                f"Ouch! @{target} needs some ice! 🧊",
                f"Damn! @{user} has no chill! 🔥",
                f"@{target} just left the chat mentally. 😵",
                "That sounded expensive! 💸"
            ]
            msg = random.choice(comments)
            
            bot.send_json({
                "handler": "chatroommessage", 
                "roomid": room_id, 
                "type": "image", 
                "url": link, 
                "text": "Slap"
            })
            bot.send_message(room_id, msg)
        else:
            bot.send_message(room_id, "❌ Slap missed (Upload Error).")
            
    except Exception as e:
        print(f"Slap Error: {e}")
