import sys
import os
import random
import requests
import textwrap
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageOps

# --- IMPORTS ---
try: import utils
except ImportError: print("[CharPro] Error: utils.py not found!")

# --- STATE ---
char_drafts = {}

def setup(bot):
    print("[CharPro] Infinite Generation Engine Loaded.")

# ==========================================
# 🧠 INTELLIGENT ASSET FETCHING (Multi-Source)
# ==========================================

class AssetFactory:
    @staticmethod
    def get_smart_image(prompt, username):
        """
        Prompt ko samajh kar sahi API se image lata hai.
        Har baar naya seed use karta hai taaki image repeat na ho.
        """
        prompt = prompt.lower()
        
        # RANDOM SEED GENERATOR (Ye loop problem fix karega)
        # Hum username + prompt + random number mila kar seed banayenge
        seed = f"{username}_{prompt}_{random.randint(1, 999999)}"
        
        # SOURCE 1: SUPERHEROES & WARRIORS (Detailed Humans)
        if any(x in prompt for x in ["hero", "super", "wonder", "man", "woman", "spider", "bat", "iron", "captain"]):
            # DiceBear 'Lorelei' ya 'Adventurer' best hai humans ke liye
            style = "lorelei" if any(x in prompt for x in ["woman", "girl", "wonder", "widow"]) else "adventurer"
            return f"https://api.dicebear.com/9.x/{style}/png?seed={seed}&backgroundColor=transparent&size=1024"

        # SOURCE 2: MONSTERS & VILLAINS (RoboHash Set 2)
        elif any(x in prompt for x in ["monster", "hulk", "zombie", "alien", "thanos", "villain", "ghost"]):
            # RoboHash Set 2 is Monsters
            return f"https://robohash.org/{seed}.png?set=set2&size=600x600"

        # SOURCE 3: ROBOTS & CYBORGS (RoboHash Set 1 / DiceBear Bottts)
        elif any(x in prompt for x in ["robot", "cyborg", "mech", "android", "tech", "ai"]):
            # Mix of sources for variety
            if random.random() > 0.5:
                return f"https://robohash.org/{seed}.png?set=set1&size=600x600"
            else:
                return f"https://api.dicebear.com/9.x/bottts-neutral/png?seed={seed}&size=1024"

        # SOURCE 4: CATS & CUTE ANIMALS (RoboHash Set 4)
        elif any(x in prompt for x in ["cat", "kitty", "cute", "animal", "pet"]):
            return f"https://robohash.org/{seed}.png?set=set4&size=600x600"

        # SOURCE 5: ART & SKETCH (Notion Style)
        elif any(x in prompt for x in ["art", "sketch", "draw", "paint", "paper"]):
            return f"https://api.dicebear.com/9.x/notionists/png?seed={seed}&size=1024"

        # SOURCE 6: 3D AVATARS (Default)
        # Agar kuch samajh na aaye to 3D Fun Emoji ya Avataaars use karo
        styles = ["fun-emoji", "avataaars", "big-smile", "open-peeps"]
        chosen = random.choice(styles)
        return f"https://api.dicebear.com/9.x/{chosen}/png?seed={seed}&size=1024"

# ==========================================
# 🎨 BACKGROUND & FX ENGINE
# ==========================================

def create_ultra_bg(W, H, prompt):
    """
    Prompt ke mood ke hisaab se background generate karta hai.
    """
    prompt = prompt.lower()
    
    # 1. THEME SELECTION
    if any(x in prompt for x in ["fire", "anger", "hot", "devil", "red"]):
        colors = ["#8B0000", "#FF4500", "#000000"] # Magma
    elif any(x in prompt for x in ["ice", "cool", "water", "blue", "sky"]):
        colors = ["#00BFFF", "#1E90FF", "#F0F8FF"] # Ice
    elif any(x in prompt for x in ["joker", "toxic", "poison", "green", "hulk"]):
        colors = ["#00FF00", "#4B0082", "#2F4F4F"] # Toxic
    elif any(x in prompt for x in ["girl", "love", "pink", "cute", "wonder"]):
        colors = ["#FF69B4", "#FF1493", "#FFD700"] # Barbie/Wonder
    else:
        # Random Neon
        colors = [random.choice(["#FF00FF", "#00FFFF", "#FFFF00"]), "#111111", "#222233"]

    # 2. BASE GRADIENT
    img = Image.new("RGBA", (W, H), colors[1])
    d = ImageDraw.Draw(img)
    
    # 3. PROCEDURAL PARTICLES (Chinte)
    for _ in range(30):
        x = random.randint(-100, W)
        y = random.randint(-100, H)
        s = random.randint(20, 400)
        col = random.choice([colors[0], colors[2]])
        
        # Transparent Shape
        shape = Image.new("RGBA", (W, H), (0,0,0,0))
        sd = ImageDraw.Draw(shape)
        
        if random.random() > 0.5:
            sd.ellipse([x, y, x+s, y+s], fill=col)
        else:
            # Draw Splatter Lines
            sd.line([x, y, x+random.randint(-100,100), y+random.randint(-100,100)], fill=col, width=random.randint(5, 20))
            
        # Heavy Blur for "Glow" effect
        shape = shape.filter(ImageFilter.GaussianBlur(random.randint(10, 50)))
        img.paste(shape, (0,0), shape)

    # 4. OVERLAY TEXTURE (Noise)
    noise = Image.effect_noise((W, H), 5).convert("L")
    noise = ImageOps.colorize(noise, black="black", white="white").convert("RGBA")
    noise.putalpha(20) # 20% opacity
    img.paste(noise, (0,0), noise)
    
    return img

def apply_cinematic_effects(img):
    """
    Image ko 3D pop aur Contrast deta hai.
    """
    # 1. Enhance Color
    enhancer = ImageEnhance.Color(img)
    img = enhancer.enhance(1.3)
    
    # 2. Enhance Sharpness
    enhancer = ImageEnhance.Sharpness(img)
    img = enhancer.enhance(1.2)
    
    # 3. Vignette (Dark Corners)
    W, H = img.size
    overlay = Image.new("RGBA", (W, H), (0,0,0,0))
    d = ImageDraw.Draw(overlay)
    
    # Draw transparent radial gradient manually
    # Simple workaround: Draw thick borders with blur
    d.rectangle([0,0,W,H], outline="black", width=20)
    overlay = overlay.filter(ImageFilter.GaussianBlur(50))
    img.paste(overlay, (0,0), overlay)
    
    return img

# ==========================================
# 🖼️ MASTER CARD BUILDER
# ==========================================

def draw_character_card(username, prompt):
    W, H = 600, 800
    
    # 1. Generate Dynamic Background
    img = create_ultra_bg(W, H, prompt)
    d = ImageDraw.Draw(img)
    
    # 2. Border Frame (Neon Style)
    m = 25
    border_col = "white"
    if "gold" in prompt or "king" in prompt: border_col = "#FFD700"
    elif "evil" in prompt or "red" in prompt: border_col = "#FF0000"
    
    d.rectangle([m, m, W-m, H-m], outline=border_col, width=3)
    # Corner Brackets
    L = 50
    d.line([m, m, m+L, m], fill=border_col, width=8)
    d.line([m, m, m, m+L], fill=border_col, width=8)
    d.line([W-m, H-m, W-m-L, H-m], fill=border_col, width=8)
    d.line([W-m, H-m, W-m, H-m-L], fill=border_col, width=8)

    # 3. Fetch & Process Avatar
    url = AssetFactory.get_smart_image(prompt, username)
    avatar = utils.get_image(url)
    
    if avatar:
        avatar = avatar.resize((550, 550))
        
        # Back Glow (Shadow behind character)
        glow = Image.new("RGBA", (W, H), (0,0,0,0))
        gd = ImageDraw.Draw(glow)
        gd.ellipse([50, 100, 550, 600], fill=(0,0,0, 100))
        glow = glow.filter(ImageFilter.GaussianBlur(40))
        img.paste(glow, (0,0), glow)
        
        # Place Main Character
        img.paste(avatar, (25, 80), avatar)

    # 4. Typography (Poster Style)
    # Slant Bar for Name
    d.polygon([(0, 620), (W, 580), (W, H), (0, H)], fill=(10, 10, 10, 230))
    d.line([(0, 620), (W, 580)], fill=border_col, width=3)
    
    # Name
    utils.write_text(d, (W//2, 650), username.upper(), size=55, align="center", col="white", shadow=True)
    
    # Subtitle / Role
    roles = prompt.split()[:4]
    role_text = " • ".join([r.upper() for r in roles])
    utils.write_text(d, (W//2, 710), f"✨ {role_text} ✨", size=22, align="center", col=border_col)
    
    # 5. Final Polish
    img = apply_cinematic_effects(img)
    
    return img

# ==========================================
# ⚙️ HANDLER
# ==========================================

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    user_id = data.get('userid', user)
    
    # 1. CREATE CHARACTER
    if cmd == "char":
        if len(args) < 1:
            bot.send_message(room_id, "⚠️ **Usage:** `!char <prompt>`\nExample: `!char wonder woman warrior`")
            return True
            
        # Agar user kisi aur ka char banana chahta hai (!char @user prompt)
        if args[0].startswith("@"):
            target_name = args[0].replace("@", "")
            prompt = " ".join(args[1:])
        else:
            target_name = user
            prompt = " ".join(args)
            
        if not prompt: prompt = "Legendary Hero"
        
        bot.send_message(room_id, f"🎨 **Generating:** {prompt}...")
        
        try:
            # Generate
            img = draw_character_card(target_name, prompt)
            link = utils.upload(bot, img)
            
            if link:
                char_drafts[user_id] = link
                bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Character"})
                bot.send_message(room_id, "🔥 **Done!** Type `!share @username` to gift this.")
            else:
                bot.send_message(room_id, "❌ Error: Upload failed.")
        except Exception as e:
            print(f"Char Error: {e}")
            bot.send_message(room_id, "⚠️ Art Engine Error.")
            
        return True

    # 2. SHARE
    if cmd == "share":
        if user_id in char_drafts:
            if not args:
                bot.send_message(room_id, "Usage: `!share @username`")
                return True
                
            target = args[0].replace("@", "")
            link = char_drafts[user_id]
            
            bot.send_dm_image(target, link, f"🦸‍♂️ **You have been summoned!**\nCharacter by @{user}")
            bot.send_message(room_id, f"✅ Character sent to @{target}")
            return True
        return False

    return False
