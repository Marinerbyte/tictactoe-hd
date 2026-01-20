import sys
import os
import textwrap
import random
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageOps

# --- IMPORTS ---
try: import utils
except ImportError: print("[Designer] Error: utils.py not found!")

# --- STATE ---
user_drafts = {}

def setup(bot):
    print("[Designer] Premium Aesthetics Engine Loaded.")

# ==========================================
# 🧠 SMART ASSETS (Better Avatars & Icons)
# ==========================================

class AssetLib:
    @staticmethod
    def get_premium_avatar(username, vibe):
        """
        Chooses the best avatar style based on Vibe.
        No more boring/bald avatars.
        """
        # Random seed modifier to ensure uniqueness every time
        seed = f"{username}_{random.randint(1, 9999)}"
        
        if vibe == "love" or vibe == "cute":
            # Cute 3D or Anime style
            style = random.choice(["fun-emoji", "lorelei"])
        elif vibe == "angry" or vibe == "sad":
            # Expressive faces
            style = "notionists" # Sketch style captures emotion well
        elif vibe == "cool" or vibe == "fun":
            # Stylish humans
            style = random.choice(["avataaars", "micah", "open-peeps"])
        else:
            # Default stylish
            style = "notionists"

        return f"https://api.dicebear.com/9.x/{style}/png?seed={seed}&size=1024&backgroundColor=transparent"

    @staticmethod
    def get_vibe_icon(vibe):
        """Returns High-Res 3D Icons based on vibe"""
        icons = {
            "love": ["heart-with-arrow", "love-letter", "diamond-heart", "kiss"],
            "cool": ["cool", "sunglasses", "dj", "rock-music"],
            "angry": ["angry-face", "explosion", "bomb", "fire-element"],
            "sad": ["crying", "rain-cloud", "broken-heart", "sad-cloud"],
            "fun": ["lol", "party-popper", "confetti", "joker"],
            "birthday": ["birthday-cake", "gift", "party-hat", "candle"]
        }
        # Fallback to Star if vibe not found
        selection = icons.get(vibe, ["star", "flash-on", "diamond"])
        icon_name = random.choice(selection)
        return f"https://img.icons8.com/fluency/512/{icon_name}.png"

# ==========================================
# 🎨 GRAPHICS ENGINE (The Artist)
# ==========================================

def create_aesthetic_bg(W, H, vibe):
    """
    Creates a modern, grainy, gradient background.
    """
    # 1. Palette Selection
    palettes = {
        "love": ["#FF9A9E", "#FECFEF"],
        "cool": ["#a18cd1", "#fbc2eb"], # Purple gradient
        "angry": ["#ff9a9e", "#fecfef"], # Reddish
        "fun": ["#84fab0", "#8fd3f4"],   # Teal/Blue
        "sad": ["#cfd9df", "#e2ebf0"],   # Greyish
        "birthday": ["#f6d365", "#fda085"] # Gold/Orange
    }
    colors = palettes.get(vibe, ["#667eea", "#764ba2"]) # Default Deep Purple
    
    # 2. Base Gradient
    img = utils.get_gradient(W, H, colors[0], colors[1])
    
    # 3. Add Abstract Shapes (Orbs)
    overlay = Image.new("RGBA", (W, H), (0,0,0,0))
    d = ImageDraw.Draw(overlay)
    
    for _ in range(6):
        x = random.randint(-100, W)
        y = random.randint(-100, H)
        size = random.randint(200, 600)
        d.ellipse([x, y, x+size, y+size], fill=(255, 255, 255, 30))
    
    # Blur the shapes for "Bokeh" look
    overlay = overlay.filter(ImageFilter.GaussianBlur(50))
    img.paste(overlay, (0,0), overlay)
    
    # 4. Add Noise (Grain Effect) - Makes it look premium
    noise = Image.effect_noise((W, H), 15).convert("L")
    noise = ImageOps.colorize(noise, black="black", white="white").convert("RGBA")
    noise.putalpha(15) # Subtle grain
    img.paste(noise, (0,0), noise)
    
    return img

def create_square_design(username, text):
    W, H = 600, 600
    
    # Detect Vibe
    vibe = "cool"
    if any(x in text.lower() for x in ["love", "heart", "miss"]): vibe = "love"
    elif any(x in text.lower() for x in ["angry", "hate", "stupid"]): vibe = "angry"
    elif any(x in text.lower() for x in ["happy", "lol", "haha"]): vibe = "fun"
    elif any(x in text.lower() for x in ["hbd", "birthday"]): vibe = "birthday"
    elif any(x in text.lower() for x in ["sad", "cry"]): vibe = "sad"

    # 1. Background
    img = create_aesthetic_bg(W, H, vibe)
    d = ImageDraw.Draw(img)
    
    # 2. Glass Card (Center)
    m = 40
    d.rounded_rectangle([m, m, W-m, H-m], radius=40, fill=(255, 255, 255, 60)) # More opaque
    d.rounded_rectangle([m, m, W-m, H-m], radius=40, outline=(255, 255, 255, 150), width=4)

    # 3. Avatar (Premium)
    avatar_url = AssetLib.get_premium_avatar(username, vibe)
    avatar = utils.get_image(avatar_url)
    
    if avatar:
        avatar = avatar.resize((280, 280))
        # Shadow
        shadow = Image.new("RGBA", (280, 280), (0,0,0,0))
        ImageDraw.Draw(shadow).ellipse([20, 240, 260, 270], fill=(0,0,0,50))
        shadow = shadow.filter(ImageFilter.GaussianBlur(10))
        img.paste(shadow, (W//2 - 140, 90), shadow)
        # Main Avatar
        img.paste(avatar, (W//2 - 140, 70), avatar)

    # 4. Floating 3D Icon
    icon_url = AssetLib.get_vibe_icon(vibe)
    icon = utils.get_image(icon_url)
    if icon:
        icon = icon.resize((120, 120))
        # Rotate slightly
        icon = icon.rotate(random.randint(-20, 20), expand=True)
        img.paste(icon, (W - 160, 30), icon)

    # 5. Typography
    wrapper = textwrap.TextWrapper(width=22)
    lines = wrapper.wrap(text)
    
    font_size = 40
    start_y = 360
    
    for line in lines:
        if start_y > H - 80: break
        # Text Shadow
        utils.write_text(d, (W//2+2, start_y+2), line, size=font_size, align="center", col=(0,0,0,100))
        # Main Text
        utils.write_text(d, (W//2, start_y), line, size=font_size, align="center", col="white", shadow=False)
        start_y += (font_size + 10)

    # Footer
    utils.write_text(d, (W//2, H-50), f"@{username}", size=20, align="center", col=(50, 50, 50))
    
    return img

def create_sticker_design(username, text):
    """
    Creates a WhatsApp style sticker (Transparent BG).
    """
    W, H = 512, 512
    img = Image.new("RGBA", (W, H), (0,0,0,0))
    
    # Layer for Content
    content = Image.new("RGBA", (W, H), (0,0,0,0))
    d = ImageDraw.Draw(content)
    
    # 1. Avatar (Big Head)
    # Using 'fun-emoji' because it looks best as a sticker
    avatar_url = f"https://api.dicebear.com/9.x/fun-emoji/png?seed={username}_{random.randint(1,999)}&size=512"
    avatar = utils.get_image(avatar_url)
    
    if avatar:
        avatar = avatar.resize((300, 300))
        content.paste(avatar, (W//2 - 150, 50), avatar)
        
    # 2. Text Bubble
    # Draw text at bottom
    wrapper = textwrap.TextWrapper(width=15)
    lines = wrapper.wrap(text)
    
    # Bubble Background (White Pill)
    text_h = len(lines) * 50 + 40
    d.rounded_rectangle([50, 350, W-50, 350+text_h], radius=30, fill="white", outline="black", width=3)
    
    y = 370
    for line in lines:
        utils.write_text(d, (W//2, y), line, size=40, align="center", col="black")
        y += 45

    # 3. White Outline (Sticker Effect)
    # Extract Alpha
    alpha = content.split()[3]
    # Expand Alpha to create border
    border = alpha.filter(ImageFilter.MaxFilter(15)) # Thick border
    
    # Create White Background
    sticker_bg = Image.new("RGBA", (W, H), (0,0,0,0))
    white_fill = Image.new("RGBA", (W, H), (255,255,255,255))
    sticker_bg.paste(white_fill, (0,0), border)
    
    # Composite
    final = Image.alpha_composite(sticker_bg, content)
    
    # Add subtle shadow
    shadow = border.filter(ImageFilter.GaussianBlur(10))
    shadow_layer = Image.new("RGBA", (W, H), (0,0,0,100))
    
    # Final Combine
    canvas = Image.new("RGBA", (W, H), (0,0,0,0))
    canvas.paste(shadow_layer, (5, 5), shadow)
    canvas.paste(final, (0, 0), final)
    
    return canvas

# ==========================================
# ⚙️ HANDLER
# ==========================================

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    user_id = data.get('userid', user)
    
    # 1. !create text
    if cmd == "create":
        if not args:
            bot.send_message(room_id, "📝 Usage: `!create Your Message Here`")
            return True
            
        text = " ".join(args)
        bot.send_message(room_id, "🎨 **Designing Premium Card...**")
        
        img = create_square_design(user, text)
        link = utils.upload(bot, img)
        
        if link:
            user_drafts[user_id] = link
            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Design"})
            bot.send_message(room_id, "✨ Ready! Type `!share @username` to send.")
        else:
            bot.send_message(room_id, "❌ Error.")
        return True

    # 2. !share @user
    if cmd == "share":
        if user_id not in user_drafts:
            bot.send_message(room_id, "⚠️ First use `!create <text>`")
            return True
        if not args:
            bot.send_message(room_id, "Usage: `!share @username`")
            return True
            
        target = args[0].replace("@", "")
        link = user_drafts[user_id]
        
        bot.send_dm_image(target, link, f"📨 **Aesthetic Card from @{user}**")
        bot.send_message(room_id, f"✅ Sent to @{target}")
        return True

    # 3. !pms @user text
    if cmd == "pms":
        if len(args) < 2:
            bot.send_message(room_id, "Usage: `!pms @user Message...`")
            return True
            
        target = args[0].replace("@", "")
        text = " ".join(args[1:])
        
        bot.send_message(room_id, f"🎨 Creating Sticker for @{target}...")
        
        img = create_sticker_design(user, text)
        link = utils.upload(bot, img)
        
        if link:
            bot.send_dm_image(target, link, "You got a Sticker! ⭐")
            bot.send_message(room_id, "✅ Sticker Delivered!")
        else:
            bot.send_message(room_id, "❌ Error.")
        return True

    return False
