import sys
import os
import textwrap
import random
import re
from PIL import ImageDraw, ImageFont, ImageFilter

# --- IMPORTS ---
try: import utils
except ImportError: print("[Designer] Error: utils.py not found!")

# --- STATE ---
user_drafts = {}

def setup(bot):
    print("[Designer] 3D Vibe Engine Loaded.")

# ==========================================
# 🧠 VIBE ENGINE
# ==========================================
VIBE_CONFIG = {
    "love": { "gradient": [(255, 20, 147), (50, 0, 20)], "border": "#FF69B4", "glow": (255, 105, 180, 100), "sticker": "love", "emoji_fallback": "❤️" },
    "birthday": { "gradient": [(255, 215, 0), (255, 69, 0)], "border": "#FFFF00", "glow": (255, 255, 0, 100), "sticker": "win", "emoji_fallback": "🎂" },
    "cool": { "gradient": [(0, 0, 0), (0, 191, 255)], "border": "#00FFFF", "glow": (0, 255, 255, 100), "sticker": "cool", "emoji_fallback": "😎" },
    "sad": { "gradient": [(40, 62, 81), (10, 35, 66)], "border": "#87CEEB", "glow": (135, 206, 235, 80), "sticker": "sad", "emoji_fallback": "😢" },
    "angry": { "gradient": [(139, 0, 0), (0, 0, 0)], "border": "#FF0000", "glow": (255, 0, 0, 120), "sticker": "fire", "emoji_fallback": "😡" },
    "fun": { "gradient": [(255, 0, 255), (0, 255, 255)], "border": "#FFFFFF", "glow": (255, 255, 255, 100), "sticker": "laugh", "emoji_fallback": "😂" }
}

def detect_vibe(text):
    text = text.lower()
    if any(x in text for x in ["love", "miss", "jaan", "babu", "❤️", "😘", "😍", "💋"]): return "love"
    if any(x in text for x in ["hbd", "birthday", "party", "cake", "🎂", "🎈"]): return "birthday"
    if any(x in text for x in ["sad", "cry", "sorry", "hurt", "😢", "😭", "💔"]): return "sad"
    if any(x in text for x in ["angry", "hate", "fuck", "bsdk", "😡", "🤬", "fire"]): return "angry"
    if any(x in text for x in ["lol", "lmao", "haha", "😂", "🤣", "😜"]): return "fun"
    return "cool"

# ==========================================
# 🎨 3D CARD GENERATOR
# ==========================================
def draw_3d_card(text, sender_name, vibe_key):
    W, H = 800, 500
    config = VIBE_CONFIG[vibe_key]
    
    img = utils.get_gradient(W, H, config["gradient"][0], config["gradient"][1])
    d = ImageDraw.Draw(img)
    
    bg_emoji = utils.get_emoji(config["emoji_fallback"], size=100)
    if bg_emoji:
        bg_layer = utils.create_canvas(W, H, (0,0,0,0))
        for _ in range(6):
            x, y = random.randint(-50, W), random.randint(-50, H)
            rotated = bg_emoji.rotate(random.randint(0, 360), expand=True)
            mask = rotated.split()[3].point(lambda i: i * 0.15)
            bg_layer.paste(rotated, (x, y), mask)
        img.paste(bg_layer, (0,0), bg_layer)

    card_w, card_h = 600, 300
    cx, cy = (W - card_w) // 2, (H - card_h) // 2
    
    d.rounded_rectangle([cx, cy, cx+card_w, cy+card_h], radius=30, fill=(255, 255, 255, 30))
    d.rounded_rectangle([cx-2, cy-2, cx+card_w+2, cy+card_h+2], radius=30, outline=config["glow"], width=4)
    d.rounded_rectangle([cx, cy, cx+card_w, cy+card_h], radius=30, outline=config["border"], width=2)
    
    sticker_name = config["sticker"]
    sticker = utils.get_sticker(sticker_name, size=180)
    if not sticker: sticker = utils.get_emoji(config["emoji_fallback"], size=180)
    
    if sticker: img.paste(sticker, (cx + card_w - 120, cy - 60), sticker)

    wrapper = textwrap.TextWrapper(width=30) 
    lines = wrapper.wrap(text)
    
    font_size = 50
    if len(text) > 50: font_size = 40
    if len(text) > 100: font_size = 30
    
    start_y = cy + 60
    for line in lines:
        if start_y > cy + card_h - 60: break
        utils.write_text(d, (cx + 50 + 3, start_y + 3), line, size=font_size, col=(0,0,0,150))
        utils.write_text(d, (cx + 50, start_y), line, size=font_size, col="white", shadow=False)
        start_y += (font_size + 10)

    utils.write_text(d, (cx + 30, cy + card_h - 40), f"From: @{sender_name}", size=20, col=config["border"])
    utils.write_text(d, (cx + card_w - 150, cy + card_h - 40), "✨ 3D Design", size=16, col="#AAA", align="center")
    return img

# ==========================================
# ⚙️ HANDLER (NO CHECKS VERSION)
# ==========================================

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    user_id = data.get('userid', user)
    
    # MODE 1: Store
    if cmd == "design":
        if not args:
            bot.send_message(room_id, "Usage: `!design <text>`")
            return True
        
        text = " ".join(args)
        user_drafts[user_id] = text
        vibe = detect_vibe(text)
        bot.send_message(room_id, f"🎨 **Saved!** Theme: {vibe.upper()}\nUse `!share @username`")
        return True

    # MODE 1: Share (Removed ID Checks)
    if cmd == "share":
        if user_id not in user_drafts:
            bot.send_message(room_id, "⚠️ No draft. Use `!design` first.")
            return True
        if not args:
            bot.send_message(room_id, "Usage: `!share @username`")
            return True
            
        target_name = args[0].replace("@", "")
        text = user_drafts[user_id]
        vibe = detect_vibe(text)
        
        bot.send_message(room_id, "🎨 **Sending...**")
        
        # --- NO ID LOOKUP: DIRECT SEND ---
        img = draw_3d_card(text, user, vibe)
        link = utils.upload(bot, img)
        
        if link:
            # Seedha Username use kar rahe hain
            bot.send_dm_image(target_name, link, f"📨 **Card from @{user}**")
            bot.send_message(room_id, f"✅ Sent to @{target_name}")
            del user_drafts[user_id]
        else:
            bot.send_message(room_id, "❌ Upload Failed.")
        return True

    # MODE 2: Instant PMS (Removed ID Checks)
    if cmd == "pms":
        if len(args) < 2:
            bot.send_message(room_id, "Usage: `!pms @username Message...`")
            return True
            
        target_name = args[0].replace("@", "")
        text = " ".join(args[1:])
        
        vibe = detect_vibe(text)
        bot.send_message(room_id, f"🎨 Sending **{vibe.upper()}** card...")
        
        # --- NO ID LOOKUP: DIRECT SEND ---
        img = draw_3d_card(text, user, vibe)
        link = utils.upload(bot, img)
        
        if link:
            # Seedha Username use kar rahe hain
            bot.send_dm_image(target_name, link, f"📨 **You got a Card!**")
            bot.send_message(room_id, "✅ **Delivered!**")
        else:
            bot.send_message(room_id, "❌ Error uploading.")
            
        return True

    return False
