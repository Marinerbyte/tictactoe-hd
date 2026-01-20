import sys
import os
import random
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

# --- IMPORTS ---
try: import utils
except ImportError: print("[SceneMaker] Error: utils.py not found!")

def setup(bot):
    print("[SceneMaker] Tiny World Engine Loaded.")

# ==========================================
# 🧠 ASSET INTELLIGENCE (The "No-Box" Logic)
# ==========================================

class WorldAssets:
    @staticmethod
    def get_twemoji(char, size=100):
        """
        Emoji Character (e.g. 🌻) ko PNG Image banata hai.
        Isse 'Box' banne ki problem 100% khatam ho jati hai.
        """
        try:
            # Emoji ko Unicode Hex me convert karo (e.g. 🌻 -> 1f33b)
            code = "-".join(f"{ord(c):x}" for c in char)
            url = f"https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/{code}.png"
            
            # Utils ka downloader use karo (Caching ke sath)
            img = utils.get_image(url)
            if img:
                return img.resize((size, size), Image.Resampling.LANCZOS)
        except:
            pass
        return None

    @staticmethod
    def get_full_body_avatar(username, pose="standing"):
        """
        Open Peeps style (Full Body Character)
        """
        seed = f"{username}_{random.randint(1,999)}"
        # Poses: standing, sitting, bust
        url = f"https://api.dicebear.com/9.x/open-peeps/png?seed={seed}&pose={pose}&clothingColor=FFD700,FF4500,1E90FF&size=1000"
        return utils.get_image(url)

# ==========================================
# 🌍 WORLD BUILDER (Graphics Engine)
# ==========================================

def create_tiny_world(username, emojis_input):
    W, H = 800, 800
    
    # 1. Detect Biome (Theme) based on Emojis
    # Default: Grassland
    ground_col = "#4CAF50" # Green
    sky_col = ["#87CEEB", "#E0F7FA"] # Blue Sky
    
    input_str = "".join(emojis_input)
    if any(x in input_str for x in ["🌵", "🐪", "🔥", "☀️"]):
        ground_col = "#F4A460" # Sand
        sky_col = ["#FFD700", "#FF8C00"] # Sunset
    elif any(x in input_str for x in ["❄️", "⛄", "🧊", "🎄"]):
        ground_col = "#E0FFFF" # Ice
        sky_col = ["#B0C4DE", "#FFFFFF"] # Snowy
    elif any(x in input_str for x in ["🌊", "🐟", "🐬", "🚢"]):
        ground_col = "#F4A460" # Sand (Beach)
        sky_col = ["#00BFFF", "#1E90FF"] # Deep Ocean
    elif any(x in input_str for x in ["🌑", "✨", "🚀", "👽"]):
        ground_col = "#2F4F4F" # Moon Rock
        sky_col = ["#000000", "#483D8B"] # Space

    # 2. Draw Sky Background
    img = utils.get_gradient(W, H, sky_col[0], sky_col[1])
    d = ImageDraw.Draw(img)
    
    # Add Clouds/Stars (Subtle)
    for _ in range(5):
        x = random.randint(0, W)
        y = random.randint(0, 300)
        d.ellipse([x, y, x+100, y+60], fill=(255,255,255,50))

    # 3. Draw The 3D Island (Ground)
    # Isometric Circle feel
    cx, cy = W//2, 650
    rw, rh = 350, 150 # Radius Width/Height
    
    # Shadow/Dirt Layer (Darker)
    d.ellipse([cx-rw, cy-rh+20, cx+rw, cy+rh+20], fill="#3E2723") 
    # Main Grass/Ground Layer
    d.ellipse([cx-rw, cy-rh, cx+rw, cy+rh], fill=ground_col)
    
    # 4. Process Emojis (The Props)
    # Hum emojis ko 2 list me baatenge: Background (Peeche) aur Foreground (Aage)
    props = []
    for char in emojis_input:
        # Filter: Only process actual emojis/symbols (ignore text mostly)
        if ord(char) > 200: 
            png = WorldAssets.get_twemoji(char, size=120)
            if png: props.append(png)
            
    # Shuffle for randomness
    random.shuffle(props)
    
    # Layer 1: Background Props (Behind Avatar)
    # Trees, Houses, Sun etc usually go here
    for i in range(len(props) // 2):
        prop = props[i]
        # Position: Top half of the island
        px = random.randint(150, 600)
        py = random.randint(500, 600)
        img.paste(prop, (px, py), prop)

    # 5. Place User Avatar (Center Stage)
    avatar = WorldAssets.get_full_body_avatar(username, "standing")
    if avatar:
        avatar = avatar.resize((500, 500))
        # Shadow for Avatar
        sh = Image.new("RGBA", (500, 500), (0,0,0,0))
        ImageDraw.Draw(sh).ellipse([150, 420, 350, 450], fill=(0,0,0,50))
        sh = sh.filter(ImageFilter.GaussianBlur(10))
        img.paste(sh, (150, 250), sh)
        
        # Paste Avatar
        img.paste(avatar, (150, 200), avatar)

    # 6. Layer 2: Foreground Props (In front of Avatar)
    # Flowers, Pets, Gifts, Food
    remaining_props = props[len(props)//2:]
    for prop in remaining_props:
        # Resize small for foreground items
        prop = prop.resize((80, 80))
        # Position: Bottom half of the island (Near feet)
        px = random.randint(250, 550)
        py = random.randint(620, 700)
        img.paste(prop, (px, py), prop)

    # 7. Name Tag (Floating)
    tag_bg = (0, 0, 0, 150)
    utils.write_text(d, (W//2, 100), f"@{username}'s World", size=40, align="center", col="white", shadow=True)
    
    return img

# ==========================================
# ⚙️ HANDLER
# ==========================================

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    user_id = data.get('userid', user)
    
    # Command: !world @user 🌻🌲🏡
    if cmd == "world":
        if not args:
            bot.send_message(room_id, "Usage: `!world @user <emojis>`\nExample: `!world @yasin 🌳🏠🚗`")
            return True
            
        target = args[0].replace("@", "")
        
        # Emojis ko extract karna (baki text ignore)
        raw_input = "".join(args[1:])
        emojis_list = [c for c in raw_input if ord(c) > 200] # Simple emoji filter
        
        if not emojis_list:
            # Default agar user ne emoji nahi diya
            emojis_list = ["🌳", "🌼", "🏠", "☁️"]
            
        bot.send_message(room_id, f"🌍 **Building World for:** {target}...")
        
        try:
            img = create_tiny_world(target, emojis_list)
            link = utils.upload(bot, img)
            
            if link:
                bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "TinyWorld"})
                bot.send_message(room_id, f"✨ Welcome to **{target}'s** Universe!")
            else:
                bot.send_message(room_id, "❌ Creation failed.")
                
        except Exception as e:
            print(f"World Error: {e}")
            bot.send_message(room_id, "⚠️ Error building world.")
            
        return True

    return False
