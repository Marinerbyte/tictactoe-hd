import sys
import os
import textwrap
import random
import re
from PIL import ImageDraw, ImageFont, ImageFilter

# --- IMPORTS ---
try: import utils
except ImportError: print("[Designer] Error: utils.py not found!")

# --- STATE MANAGEMENT ---
# Store pending designs: {user_id: "Text content"}
user_drafts = {}

def setup(bot):
    print("[Designer] 3D Vibe Engine Loaded.")

# ==========================================
# 🧠 VIBE ENGINE (AI Logic)
# ==========================================

VIBE_CONFIG = {
    "love": {
        "gradient": [(255, 20, 147), (50, 0, 20)], # Deep Pink to Dark
        "border": "#FF69B4", "glow": (255, 105, 180, 100),
        "sticker": "love", "emoji_fallback": "❤️"
    },
    "birthday": {
        "gradient": [(255, 215, 0), (255, 69, 0)], # Gold to Orange
        "border": "#FFFF00", "glow": (255, 255, 0, 100),
        "sticker": "win", "emoji_fallback": "🎂"
    },
    "cool": {
        "gradient": [(0, 0, 0), (0, 191, 255)], # Black to Cyan
        "border": "#00FFFF", "glow": (0, 255, 255, 100),
        "sticker": "cool", "emoji_fallback": "😎"
    },
    "sad": {
        "gradient": [(40, 62, 81), (10, 35, 66)], # Rainy Blue
        "border": "#87CEEB", "glow": (135, 206, 235, 80),
        "sticker": "sad", "emoji_fallback": "😢"
    },
    "angry": {
        "gradient": [(139, 0, 0), (0, 0, 0)], # Dark Red to Black
        "border": "#FF0000", "glow": (255, 0, 0, 120),
        "sticker": "fire", "emoji_fallback": "😡"
    },
    "fun": {
        "gradient": [(255, 0, 255), (0, 255, 255)], # Cyberpunk
        "border": "#FFFFFF", "glow": (255, 255, 255, 100),
        "sticker": "laugh", "emoji_fallback": "😂"
    }
}

def detect_vibe(text):
    """Text aur Emojis analyze karke Theme decide karta hai"""
    text = text.lower()
    
    # Keyword & Emoji Matching
    if any(x in text for x in ["love", "miss", "jaan", "babu", "❤️", "😘", "😍", "💋", "rose"]): return "love"
    if any(x in text for x in ["hbd", "birthday", "party", "cake", "🎂", "🎈", "🎉"]): return "birthday"
    if any(x in text for x in ["sad", "cry", "sorry", "hurt", "😢", "😭", "💔"]): return "sad"
    if any(x in text for x in ["angry", "hate", "fuck", "bsdk", "😡", "🤬", "fire"]): return "angry"
    if any(x in text for x in ["lol", "lmao", "haha", "😂", "🤣", "😜"]): return "fun"
    
    # Default Vibe (Cool/Attitude)
    return "cool"

# ==========================================
# 🎨 3D CARD GENERATOR
# ==========================================

def draw_3d_card(text, sender_name, vibe_key):
    # 1. Canvas Setup
    W, H = 800, 500
    config = VIBE_CONFIG[vibe_key]
    
    # Background Gradient
    img = utils.get_gradient(W, H, config["gradient"][0], config["gradient"][1])
    d = ImageDraw.Draw(img)
    
    # 2. Background Decor (Floating Emojis)
    # Background me halke opacity wale emojis
    bg_emoji = utils.get_emoji(config["emoji_fallback"], size=100)
    if bg_emoji:
        # Transparent layer
        bg_layer = utils.create_canvas(W, H, (0,0,0,0))
        for _ in range(6):
            x, y = random.randint(-50, W), random.randint(-50, H)
            # Rotate random
            rotated = bg_emoji.rotate(random.randint(0, 360), expand=True)
            # Paste with low alpha
            mask = rotated.split()[3].point(lambda i: i * 0.15) # 15% Opacity
            bg_layer.paste(rotated, (x, y), mask)
        img.paste(bg_layer, (0,0), bg_layer)

    # 3. Glassmorphism Card (Center)
    card_w, card_h = 600, 300
    cx, cy = (W - card_w) // 2, (H - card_h) // 2
    
    # Glass Layer (White transparent)
    d.rounded_rectangle([cx, cy, cx+card_w, cy+card_h], radius=30, fill=(255, 255, 255, 30))
    
    # 3D Border Effect
    # Outer Glow
    d.rounded_rectangle([cx-2, cy-2, cx+card_w+2, cy+card_h+2], radius=30, outline=config["glow"], width=4)
    # Solid Border
    d.rounded_rectangle([cx, cy, cx+card_w, cy+card_h], radius=30, outline=config["border"], width=2)
    
    # 4. Main Sticker (Pop-out effect)
    # Sticker ko card ke upar aur thoda bahar nikalte hue lagayenge
    sticker_name = config["sticker"]
    sticker = utils.get_sticker(sticker_name, size=180)
    
    # Agar sticker nahi mila to emoji use karo
    if not sticker: 
        sticker = utils.get_emoji(config["emoji_fallback"], size=180)
    
    if sticker:
        # Place at top-right or bottom-right
        img.paste(sticker, (cx + card_w - 120, cy - 60), sticker)

    # 5. Text Rendering (Auto-Fit)
    # Text ko wrap karo taaki card se bahar na jaye
    wrapper = textwrap.TextWrapper(width=30) 
    lines = wrapper.wrap(text)
    
    # Dynamic Font Size logic
    font_size = 50
    if len(text) > 50: font_size = 40
    if len(text) > 100: font_size = 30
    
    start_y = cy + 60
    for line in lines:
        if start_y > cy + card_h - 60: break # Safety cutoff
        # Text Shadow (3D Effect)
        utils.write_text(d, (cx + 50 + 3, start_y + 3), line, size=font_size, col=(0,0,0,150))
        # Main Text
        utils.write_text(d, (cx + 50, start_y), line, size=font_size, col="white", shadow=False)
        start_y += (font_size + 10)

    # 6. Signature / Footer
    utils.write_text(d, (cx + 30, cy + card_h - 40), f"From: @{sender_name}", size=20, col=config["border"])
    utils.write_text(d, (cx + card_w - 150, cy + card_h - 40), "✨ 3D Design", size=16, col="#AAA", align="center")

    return img

# ==========================================
# ⚙️ HANDLER
# ==========================================

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    
    # MODE 1: Store Design (!design text...)
    if cmd == "design":
        if not args:
            bot.send_message(room_id, "❌ Usage: `!design Happy Birthday Bro!`")
            return True
        
        text = " ".join(args)
        user_id = data.get('userid', user)
        
        user_drafts[user_id] = text
        
        # Analyze Vibe for preview message
        vibe = detect_vibe(text)
        icons = {"love":"❤️", "birthday":"🎂", "cool":"😎", "sad":"😢", "angry":"😡", "fun":"😂"}
        
        bot.send_message(room_id, f"🎨 **Design Saved!**\nVibe Detected: {vibe.upper()} {icons[vibe]}\nType `!share @username` to send.")
        return True

    # MODE 1: Share Design (!share @user)
    if cmd == "share":
        user_id = data.get('userid', user)
        
        if user_id not in user_drafts:
            bot.send_message(room_id, "⚠️ No design found. Use `!design <text>` first.")
            return True
            
        if not args:
            bot.send_message(room_id, "❌ Usage: `!share @username`")
            return True
            
        target_name = args[0].replace("@", "")
        # Find ID
        target_id = None
        if room_id in bot.room_details:
             target_id = bot.room_details[room_id]['id_map'].get(target_name.lower())
        
        if not target_id:
            bot.send_message(room_id, f"❌ User @{target_name} not found in this room.")
            return True
            
        # Generate
        text = user_drafts[user_id]
        vibe = detect_vibe(text)
        
        bot.send_message(room_id, "🎨 **Rendering 3D Card...**")
        
        img = draw_3d_card(text, user, vibe)
        link = utils.upload(bot, img)
        
        if link:
            bot.send_dm_image(target_id, link, f"📨 **New Card from @{user}**")
            bot.send_message(room_id, f"✅ Card successfully sent to @{target_name}!")
            # Clear draft
            del user_drafts[user_id]
        else:
            bot.send_message(room_id, "❌ Render failed.")
            
        return True

    # MODE 2: Instant PMS (!pms @user text...)
    if cmd == "pms":
        if len(args) < 2:
            bot.send_message(room_id, "❌ Usage: `!pms @username Your Message Here...`")
            return True
            
        target_name = args[0].replace("@", "")
        text = " ".join(args[1:])
        
        # Find ID
        target_id = None
        if room_id in bot.room_details:
             target_id = bot.room_details[room_id]['id_map'].get(target_name.lower())
             
        if not target_id:
            bot.send_message(room_id, f"❌ User @{target_name} not found in room.")
            return True
            
        # Analyze & Generate
        vibe = detect_vibe(text)
        bot.send_message(room_id, f"🎨 Sending **{vibe.upper()}** style card to @{target_name}...")
        
        img = draw_3d_card(text, user, vibe)
        link = utils.upload(bot, img)
        
        if link:
            bot.send_dm_image(target_id, link, f"📨 **You got a Card!**")
            bot.send_message(room_id, "✅ **Delivered!**")
        else:
            bot.send_message(room_id, "❌ Error uploading card.")
            
        return True

    return False
