import sys
import os
import random
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageOps, ImageChops

# --- IMPORTS ---
try: import utils
except ImportError: print("[CharMaker] Error: utils.py not found!")

# --- STATE ---
char_drafts = {}

def setup(bot):
    print("[CharMaker] Infinite Style Engine Loaded.")

# ==========================================
# 🧠 SMART ASSET INTELLIGENCE
# ==========================================

def analyze_style(description):
    """
    Description se Vibe, Palette aur Avatar Style nikalta hai.
    """
    desc = description.lower()
    
    # Defaults
    style = "adventurer"
    bg_mode = "splatter"
    palette = ["#FFD700", "#FF4500", "#1E90FF"] # Standard Gold/Red/Blue
    
    # 1. TECH / SCI-FI
    if any(x in desc for x in ["robot", "bot", "mech", "cyborg", "tech", "ai", "future", "cyber"]):
        style = "bottts"
        bg_mode = "cyber"
        palette = ["#00FFFF", "#FF00FF", "#00FF00"] # Neon
        
    # 2. CUTE / ANIME
    elif any(x in desc for x in ["cute", "kawaii", "baby", "kid", "chibi", "soft", "love"]):
        style = "fun-emoji"
        bg_mode = "pastel"
        palette = ["#FFB6C1", "#87CEEB", "#E6E6FA"] # Pink/Blue/Lavender
        
    # 3. HORROR / DARK
    elif any(x in desc for x in ["ghost", "zombie", "dead", "scary", "horror", "monster", "demon", "evil"]):
        style = "thumbs" # Weird shapes
        if "zombie" in desc: style = "avataaars" # Can config for zombie skin later
        bg_mode = "horror"
        palette = ["#8B0000", "#2F4F4F", "#000000"] # Blood Red/Dark
        
    # 4. ARTISTIC / SKETCH
    elif any(x in desc for x in ["art", "sketch", "draw", "paint", "pencil", "paper"]):
        style = "notionists"
        bg_mode = "paper"
        palette = ["#000000", "#555555", "#FFFFFF"] # Grayscale
        
    # 5. RETRO / GAMER
    elif any(x in desc for x in ["pixel", "game", "retro", "8bit", "arcade"]):
        style = "pixel-art"
        bg_mode = "pixel"
        palette = ["#FF0000", "#0000FF", "#FFFF00"] # Primary
        
    # 6. FEMALE / BEAUTY
    elif any(x in desc for x in ["girl", "woman", "lady", "queen", "princess", "beauty"]):
        style = "lorelei"
        bg_mode = "splatter"
        palette = ["#FF1493", "#9400D3", "#FFD700"]
        
    # 7. MALE / COOL
    elif any(x in desc for x in ["boy", "man", "king", "cool", "hero", "guy"]):
        style = "adventurer"
        bg_mode = "galaxy"
        palette = ["#FFD700", "#191970", "#4B0082"]

    return style, bg_mode, palette

def get_avatar_url(seed, style):
    # DiceBear API v9
    return f"https://api.dicebear.com/9.x/{style}/png?seed={seed}&backgroundColor=transparent&size=1024"

# ==========================================
# 🎨 BACKGROUND GENERATORS
# ==========================================

def bg_cyber_grid(W, H, palette):
    """Tron Style Neon Grid"""
    img = Image.new("RGBA", (W, H), (10, 5, 20)) # Dark Purple base
    d = ImageDraw.Draw(img)
    
    # Grid
    step = 50
    grid_col = palette[0]
    
    # Perspective Grid effect (Basic)
    for i in range(0, W, step):
        d.line([(i, 0), (i, H)], fill=grid_col, width=1)
    for i in range(0, H, step):
        d.line([(0, i), (W, i)], fill=grid_col, width=1)
        
    # Glow Overlay
    glow = Image.new("RGBA", (W, H), (0,0,0,0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([100, 100, W-100, H-100], fill=palette[1]+"40") # Hex + Alpha
    glow = glow.filter(ImageFilter.GaussianBlur(80))
    
    img.paste(glow, (0,0), glow)
    return img

def bg_horror_fog(W, H, palette):
    """Scary Dark Fog"""
    img = Image.new("RGBA", (W, H), (5, 0, 0)) # Pitch Black
    
    # Red/Grey Fog
    fog = Image.new("RGBA", (W, H), (0,0,0,0))
    d = ImageDraw.Draw(fog)
    
    for _ in range(15):
        x = random.randint(-100, W)
        y = random.randint(-100, H)
        s = random.randint(200, 500)
        col = random.choice([palette[0], "#333333"])
        d.ellipse([x, y, x+s, y+s], fill=col)
        
    fog = fog.filter(ImageFilter.GaussianBlur(60))
    img.paste(fog, (0,0), fog)
    
    # Scratches
    d = ImageDraw.Draw(img)
    for _ in range(50):
        x1 = random.randint(0, W); y1 = random.randint(0, H)
        d.line([x1, y1, x1+random.randint(-20, 20), y1+random.randint(-20,20)], fill=(100,100,100,100), width=1)
        
    return img

def bg_splatter_art(W, H, palette):
    """Original Splatter Art"""
    img = Image.new("RGBA", (W, H), (20, 20, 25))
    
    for _ in range(25):
        x = random.randint(-100, W)
        y = random.randint(-100, H)
        s = random.randint(50, 300)
        col = random.choice(palette)
        
        splash = Image.new("RGBA", (W, H), (0,0,0,0))
        d = ImageDraw.Draw(splash)
        
        shape = random.choice(["circle", "rect", "tri"])
        if shape == "circle": d.ellipse([x,y,x+s,y+s], fill=col)
        elif shape == "rect": d.rectangle([x,y,x+s,y+s/2], fill=col)
        else: d.polygon([(x,y), (x+s,y+s), (x-s,y+s)], fill=col)
            
        splash = splash.filter(ImageFilter.GaussianBlur(35))
        img.paste(splash, (0,0), splash)
        
    return img

def bg_pastel_dream(W, H, palette):
    """Soft Clouds"""
    img = utils.get_gradient(W, H, (255, 230, 230), (230, 230, 255))
    
    clouds = Image.new("RGBA", (W, H), (0,0,0,0))
    d = ImageDraw.Draw(clouds)
    
    for _ in range(10):
        x = random.randint(0, W)
        y = random.randint(0, H)
        s = random.randint(200, 400)
        d.ellipse([x,y,x+s,y+s], fill="white")
        
    clouds = clouds.filter(ImageFilter.GaussianBlur(50))
    img.paste(clouds, (0,0), clouds)
    return img

def generate_background(W, H, mode, palette):
    if mode == "cyber": return bg_cyber_grid(W, H, palette)
    if mode == "horror": return bg_horror_fog(W, H, palette)
    if mode == "pastel": return bg_pastel_dream(W, H, palette)
    return bg_splatter_art(W, H, palette)

# ==========================================
# 🖼️ MASTER CARD CREATOR
# ==========================================

def draw_character_card(username, description):
    W, H = 600, 800
    
    # 1. Analyze & Prepare
    style, bg_mode, palette = analyze_style(description)
    accent_col = palette[0]
    
    # 2. Generate Background
    img = generate_background(W, H, bg_mode, palette)
    d = ImageDraw.Draw(img)
    
    # 3. Avatar Fetching
    avatar_url = get_avatar_url(username, style)
    avatar = utils.get_image(avatar_url)
    
    if avatar:
        avatar = avatar.resize((550, 550))
        # Back Glow
        glow = Image.new("RGBA", (W, H), (0,0,0,0))
        gd = ImageDraw.Draw(glow)
        gd.ellipse([50, 100, 550, 600], fill=palette[1]+"60") # Hex + Alpha
        glow = glow.filter(ImageFilter.GaussianBlur(50))
        img.paste(glow, (0,0), glow)
        
        # Paste Avatar
        img.paste(avatar, (25, 80), avatar)

    # 4. UI Elements (The Frame)
    m = 20
    # Cyber Frame
    if bg_mode == "cyber":
        d.rectangle([m, m, W-m, H-m], outline=accent_col, width=3)
        d.line([m, m+100, m, m], fill=accent_col, width=8) # Corner
        d.line([m, m, m+100, m], fill=accent_col, width=8)
    # Elegant Frame
    else:
        d.rounded_rectangle([m, m, W-m, H-m], radius=0, outline="white", width=2)
        d.line([W-m, H-m-100, W-m, H-m], fill=accent_col, width=8)
        d.line([W-m-100, H-m, W-m, H-m], fill=accent_col, width=8)

    # 5. Name Plate
    # Slanted background for text
    poly = [(0, 600), (W, 560), (W, H), (0, H)]
    d.polygon(poly, fill=(10, 10, 15, 220))
    d.line([(0, 600), (W, 560)], fill=accent_col, width=4)
    
    # Username
    utils.write_text(d, (W//2, 630), username.upper(), size=50, align="center", col="white", shadow=True)
    
    # Stats / Tags
    # Rarity Logic
    rarity = "COMMON"
    rar_col = "#AAAAAA"
    if "king" in description or "god" in description: rarity = "LEGENDARY"; rar_col = "#FFD700"
    elif "robot" in description or "pro" in description: rarity = "EPIC"; rar_col = "#9400D3"
    
    utils.write_text(d, (W//2, 690), f"♦ {rarity} ♦", size=24, align="center", col=rar_col)
    
    # Attributes
    tags = description.split()[:3]
    tag_str = " | ".join(t.upper() for t in tags)
    utils.write_text(d, (W//2, 730), tag_str, size=18, align="center", col="#CCCCCC")

    return img

# ==========================================
# ⚙️ COMMAND HANDLER
# ==========================================

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    user_id = data.get('userid', user)
    
    # 1. CREATE
    if cmd == "char":
        if len(args) < 2:
            bot.send_message(room_id, "Usage: `!char <username> <style>`\nStyles: Robot, Cute, Sketch, Horror, Cool...")
            return True
            
        target = args[0].replace("@", "")
        desc = " ".join(args[1:])
        
        bot.send_message(room_id, f"🎨 **Summoning:** {target} ({desc})...")
        
        try:
            img = draw_character_card(target, desc)
            link = utils.upload(bot, img)
            
            if link:
                char_drafts[user_id] = link
                bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Character"})
                bot.send_message(room_id, f"✨ Created! Type `!share @user` to gift.")
            else:
                bot.send_message(room_id, "❌ Render failed.")
        except Exception as e:
            print(f"Char Error: {e}")
            bot.send_message(room_id, "⚠️ Art Engine Error.")
            
        return True

    # 2. SHARE
    if cmd == "share":
        # Check Char Drafts First
        if user_id in char_drafts:
            if not args:
                bot.send_message(room_id, "Usage: `!share @username`")
                return True
                
            target = args[0].replace("@", "")
            link = char_drafts[user_id]
            
            bot.send_dm_image(target, link, f"🃏 **Legendary Card from @{user}**")
            bot.send_message(room_id, f"✅ Card gifted to @{target}!")
            return True
            
        return False # Fallback to other plugins

    return False
