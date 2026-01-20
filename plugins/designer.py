import sys
import os
import textwrap
import random
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

# --- IMPORTS ---
try: import utils
except ImportError: print("[Designer] Error: utils.py not found!")

# --- STATE ---
user_drafts = {}

def setup(bot):
    print("[Designer] Ultra-Graphics Engine Loaded.")

# ==========================================
# 🌐 ASSETS MANAGER (More Variety)
# ==========================================

def get_dicebear_avatar(username, style="notionists"):
    """
    Styles: adventurer, fun-emoji, bottts, notionists (Sketch style), lorelei
    """
    # Using 'notionists' or 'lorelei' for a more artistic/premium look
    url = f"https://api.dicebear.com/9.x/{style}/png?seed={username}&backgroundColor=transparent&size=512"
    return utils.get_image(url)

def get_sticker_by_vibe(vibe):
    """
    Returns a random premium sticker based on vibe.
    """
    library = {
        "love": [
            "https://img.icons8.com/fluency/512/heart-with-arrow.png",
            "https://img.icons8.com/3d-fluency/512/love-letter.png",
            "https://img.icons8.com/fluency/512/diamond-heart.png"
        ],
        "birthday": [
            "https://img.icons8.com/fluency/512/birthday-cake.png",
            "https://img.icons8.com/3d-fluency/512/gift.png",
            "https://img.icons8.com/fluency/512/party-popper.png"
        ],
        "cool": [
            "https://img.icons8.com/fluency/512/cool.png",
            "https://img.icons8.com/3d-fluency/512/sunglasses.png",
            "https://img.icons8.com/fluency/512/dj.png"
        ],
        "angry": [
            "https://img.icons8.com/fluency/512/angry-face.png",
            "https://img.icons8.com/3d-fluency/512/fire-element.png",
            "https://img.icons8.com/fluency/512/bomb.png"
        ],
        "sad": [
            "https://img.icons8.com/fluency/512/crying.png",
            "https://img.icons8.com/3d-fluency/512/rain-cloud.png",
            "https://img.icons8.com/fluency/512/broken-heart.png"
        ],
        "fun": [
            "https://img.icons8.com/fluency/512/lol.png",
            "https://img.icons8.com/3d-fluency/512/joker.png",
            "https://img.icons8.com/fluency/512/confetti.png"
        ]
    }
    options = library.get(vibe, ["https://img.icons8.com/fluency/512/star.png"])
    return utils.get_image(random.choice(options))

# ==========================================
# 🧠 VIBE & THEME CONFIG
# ==========================================
VIBE_CONFIG = {
    "love": { "colors": ["#FF9A9E", "#FECFEF", "#FFD1FF"], "icon": "love" },
    "birthday": { "colors": ["#F6D365", "#FDA085", "#FFCC33"], "icon": "birthday" },
    "cool": { "colors": ["#84FAB0", "#8FD3F4", "#00F260"], "icon": "cool" },
    "angry": { "colors": ["#FF416C", "#FF4B2B", "#800000"], "icon": "angry" },
    "fun": { "colors": ["#FA709A", "#FEE140", "#96E6A1"], "icon": "fun" },
    "sad": { "colors": ["#E6E9F0", "#EEF1F5", "#BCC5CE"], "icon": "sad" }
}

def detect_vibe(text):
    t = text.lower()
    if any(x in t for x in ["love", "miss", "kiss", "❤️", "😍"]): return "love"
    if any(x in t for x in ["hbd", "birthday", "party", "🎂", "🎉"]): return "birthday"
    if any(x in t for x in ["angry", "hate", "fuck", "😡", "🤬"]): return "angry"
    if any(x in t for x in ["sad", "sorry", "cry", "😭", "💔"]): return "sad"
    if any(x in t for x in ["lol", "haha", "joy", "😂", "🤣"]): return "fun"
    return "cool"

# ==========================================
# 🎨 GENERATORS (Enhanced)
# ==========================================

def create_bokeh_background(W, H, colors):
    """Creates a premium abstract background with glowing orbs"""
    # Base Gradient
    base_col = Image.new("RGB", (W, H), colors[0])
    
    # Create overlay for orbs
    overlay = Image.new("RGBA", (W, H), (0,0,0,0))
    d = ImageDraw.Draw(overlay)
    
    # Draw random glowing circles
    for _ in range(15):
        x = random.randint(-100, W)
        y = random.randint(-100, H)
        size = random.randint(100, 400)
        col_hex = random.choice(colors)
        
        # Draw ellipse with transparency
        # Pillow doesn't support direct hex with alpha in strings sometimes, so simple fill
        d.ellipse([x, y, x+size, y+size], fill=col_hex)
    
    # Heavy Blur for Bokeh effect
    overlay = overlay.filter(ImageFilter.GaussianBlur(40))
    
    # Composite
    base_col.paste(overlay, (0,0), overlay)
    return base_col

def create_square_design(username, text):
    W, H = 600, 600
    vibe = detect_vibe(text)
    cfg = VIBE_CONFIG[vibe]
    
    # 1. Advanced Background
    img = create_bokeh_background(W, H, cfg["colors"])
    d = ImageDraw.Draw(img)
    
    # 2. Glassmorphism Card
    m = 50
    # White Glass with low opacity
    d.rounded_rectangle([m, m, W-m, H-m], radius=40, fill=(255, 255, 255, 40))
    # Inner Stroke (Shine)
    d.rounded_rectangle([m+2, m+2, W-m-2, H-m-2], radius=38, outline=(255, 255, 255, 100), width=2)
    # Outer Glow/Shadow
    d.rounded_rectangle([m, m, W-m, H-m], radius=40, outline=(255, 255, 255, 150), width=4)

    # 3. Avatar (Artistic Style)
    # Using 'lorelei' for standard or 'adventurer'
    style = "lorelei" if vibe in ["love", "sad"] else "adventurer"
    avatar = get_dicebear_avatar(username, style)
    
    if avatar:
        avatar = avatar.resize((240, 240))
        # Drop Shadow for Avatar
        shadow = Image.new("RGBA", (240, 240), (0,0,0,0))
        ds = ImageDraw.Draw(shadow)
        ds.ellipse([20, 210, 220, 235], fill=(0,0,0,60))
        shadow = shadow.filter(ImageFilter.GaussianBlur(8))
        img.paste(shadow, (W//2 - 120, 100), shadow)
        # Paste Avatar
        img.paste(avatar, (W//2 - 120, 80), avatar)

    # 4. Text Typography (Pro)
    wrapper = textwrap.TextWrapper(width=22)
    lines = wrapper.wrap(text)
    
    # Dynamic Sizing
    font_size = 45 if len(text) < 40 else 32
    # Ensure text fits
    total_text_h = len(lines) * (font_size + 10)
    start_y = 350
    
    # Adjust Y if text is too long
    if start_y + total_text_h > H - 60:
        start_y = 330
        font_size -= 5

    for line in lines:
        # Stroke Effect (Black Outline)
        # Draw multiple times to create thickness
        for off in [(-2,-2), (-2,2), (2,-2), (2,2)]:
            utils.write_text(d, (W//2 + off[0], start_y + off[1]), line, size=font_size, align="center", col="black", shadow=False)
        
        # Main Text (White)
        utils.write_text(d, (W//2, start_y), line, size=font_size, align="center", col="white", shadow=False)
        start_y += (font_size + 8)

    # 5. Floating Sticker (Randomized)
    sticker_img = get_sticker_by_vibe(vibe)
    if sticker_img:
        sticker = sticker_img.resize((130, 130))
        # Rotate for fun
        sticker = sticker.rotate(random.randint(-15, 15), expand=True, resample=Image.BICUBIC)
        # Paste at top right
        img.paste(sticker, (W-160, 20), sticker)

    # Footer
    utils.write_text(d, (W//2, H-40), f"@{username}", size=18, align="center", col=(255,255,255,200))
    
    return img

def create_sticker_design(username, text):
    """Transparent Sticker with White Stroke"""
    W, H = 550, 320
    img = Image.new("RGBA", (W, H), (0,0,0,0))
    
    vibe = detect_vibe(text)
    cfg = VIBE_CONFIG[vibe]
    
    # Layer for content
    content = Image.new("RGBA", (W, H), (0,0,0,0))
    d = ImageDraw.Draw(content)
    
    # 1. Avatar (Fun Style)
    avatar = get_dicebear_avatar(username, "fun-emoji")
    if avatar:
        avatar = avatar.resize((160, 160))
        content.paste(avatar, (10, 70), avatar)
        
    # 2. Bubble Background
    # Draw a colorful rounded rect
    # We use the first color of the vibe palette
    bubble_col = cfg["colors"][0] 
    # Convert hex string to RGB tuple if needed, but PIL handles hex strings in fill
    
    d.rounded_rectangle([160, 40, 530, 260], radius=30, fill=bubble_col)
    
    # 3. Text
    wrapper = textwrap.TextWrapper(width=18)
    lines = wrapper.wrap(text)
    y = 70
    for line in lines:
        if y > 240: break
        utils.write_text(d, (345, y), line, size=30, align="center", col="black")
        y += 35
        
    # 4. Icon Decor
    icon = get_sticker_by_vibe(vibe)
    if icon:
        icon = icon.resize((90, 90))
        content.paste(icon, (460, 200), icon)

    # 5. Create White Border (Sticker Cutout Effect)
    # Get alpha channel
    alpha = content.split()[3]
    # Expand it
    border = alpha.filter(ImageFilter.MaxFilter(9))
    
    bg = Image.new("RGBA", (W, H), (0,0,0,0))
    # Draw white silhouette
    white_layer = Image.new("RGBA", (W, H), (255,255,255,255))
    bg.paste(white_layer, (0,0), border)
    
    # Composite
    final = Image.alpha_composite(bg, content)
    
    # Add Drop Shadow
    # Create a larger canvas to hold shadow
    canvas = Image.new("RGBA", (W+20, H+20), (0,0,0,0))
    
    # Shadow layer
    shadow_mask = border.filter(ImageFilter.GaussianBlur(6))
    shadow_layer = Image.new("RGBA", (W, H), (0,0,0,100))
    canvas.paste(shadow_layer, (10, 10), shadow_mask)
    
    # Paste Main Image
    canvas.paste(final, (5, 5), final)
    
    return canvas

# ==========================================
# ⚙️ HANDLER
# ==========================================

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    user_id = data.get('userid', user)
    
    # 1. CREATE (!create text) - Show in Room
    if cmd == "create":
        if not args:
            bot.send_message(room_id, "Usage: `!create Hello World!`")
            return True
            
        text = " ".join(args)
        bot.send_message(room_id, "🎨 **Creating Masterpiece...**")
        
        img = create_square_design(user, text)
        link = utils.upload(bot, img)
        
        if link:
            user_drafts[user_id] = link # Save for sharing
            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Design"})
            bot.send_message(room_id, f"✨ Ready! Type `!share @username` to send.")
        else:
            bot.send_message(room_id, "❌ Error.")
        return True

    # 2. SHARE (!share @user)
    if cmd == "share":
        if user_id not in user_drafts:
            bot.send_message(room_id, "⚠️ Create a design first!")
            return True
        if not args:
            bot.send_message(room_id, "Usage: `!share @username`")
            return True
            
        target = args[0].replace("@", "")
        link = user_drafts[user_id]
        
        bot.send_dm_image(target, link, f"📨 **Special Card from @{user}**")
        bot.send_message(room_id, f"✅ Sent to @{target}")
        return True

    # 3. PMS (!pms @user text) - Instant Sticker
    if cmd == "pms":
        if len(args) < 2:
            bot.send_message(room_id, "Usage: `!pms @user Message...`")
            return True
            
        target = args[0].replace("@", "")
        text = " ".join(args[1:])
        
        bot.send_message(room_id, f"🎨 Sending Sticker to @{target}...")
        
        img = create_sticker_design(user, text)
        link = utils.upload(bot, img)
        
        if link:
            bot.send_dm_image(target, link, "You got a Sticker! ⭐")
            bot.send_message(room_id, "✅ **Delivered!**")
        else:
            bot.send_message(room_id, "❌ Error.")
        return True

    return False
