import io
import random
import uuid
import requests
import time
import threading
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps, ImageChops

# --- IMPORTS ---
try: 
    import utils 
except ImportError: 
    print("[Welcome] Warning: utils.py not found. Uploads will fail.")

# ==========================================
# ⚙️ CONFIGURATION & PERSISTENCE
# ==========================================

# Room-specific settings (In-memory)
# Format: { room_id: True/False }
ROOM_SETTINGS = {}

# DESIGN SETTINGS
CARD_SIZE = 1024  
FALLBACK_AVATAR = "https://api.dicebear.com/9.x/adventurer/png?seed={}&backgroundColor=transparent"

# MODERN COLOR PALETTES
PALETTES = [
    ("#2E3192", "#1BFFFF", "#FFFFFF", "white"), # Midnight
    ("#D4145A", "#FBB03B", "#FFD700", "white"), # Sunset
    ("#009245", "#FCEE21", "#004d00", "white"), # Fresh
    ("#662D8C", "#ED1E79", "#E0E0E0", "white"), # Berry
    ("#000000", "#434343", "#F1C40F", "white"), # Gold
]

def setup(bot):
    print("[Welcome] Real DP Plugin Loaded. Room-specific toggles active.")

# ==========================================
# 🎨 GRAPHICS ENGINE
# ==========================================

class DesignEngine:
    
    @staticmethod
    def get_gradient(w, h, c1, c2):
        base = Image.new('RGB', (w, h), c1)
        top = Image.new('RGB', (w, h), c2)
        mask = Image.new('L', (w, h))
        mask_data = []
        for y in range(h):
            mask_data.extend([int(255 * (y / h))] * w)
        mask.putdata(mask_data)
        base.paste(top, (0, 0), mask)
        return base

    @staticmethod
    def get_user_dp(url, username):
        """Downloads user DP or gets fallback avatar"""
        try:
            if url:
                r = requests.get(url, timeout=5)
                if r.status_code == 200:
                    return Image.open(io.BytesIO(r.content)).convert("RGBA")
        except:
            pass
        
        # Fallback to DiceBear if DP fetch fails
        try:
            fb_url = FALLBACK_AVATAR.format(username + str(time.time()))
            r = requests.get(fb_url, timeout=5)
            return Image.open(io.BytesIO(r.content)).convert("RGBA")
        except:
            return None

    @staticmethod
    def draw_glass_panel(draw, x, y, w, h):
        draw.rounded_rectangle([x, y, x+w, y+h], radius=40, fill=(0, 0, 0, 100))
        draw.rounded_rectangle([x, y, x+w, y+h], radius=40, outline=(255, 255, 255, 60), width=2)

# ==========================================
# 🖼️ CARD GENERATOR
# ==========================================

def render_card(username, room_name, avatar_url):
    W, H = CARD_SIZE, CARD_SIZE
    theme = random.choice(PALETTES)
    c1, c2, accent, txt_col = theme
    
    # 1. Background
    img = DesignEngine.get_gradient(W, H, c1, c2)
    d = ImageDraw.Draw(img, 'RGBA')
    
    # 2. Random Decor
    for _ in range(10):
        size = random.randint(50, 300)
        x, y = random.randint(0, W), random.randint(0, H)
        d.ellipse([x, y, x+size, y+size], fill=(255, 255, 255, 20))
    
    # 3. Glass Panel
    panel_h = 450
    panel_y = H - panel_h - 60
    DesignEngine.draw_glass_panel(d, 60, panel_y, W-120, panel_h)
    
    # 4. DP Processing (Real DP)
    av_size = 420
    avatar = DesignEngine.get_user_dp(avatar_url, username)
    
    if avatar:
        avatar = avatar.resize((av_size, av_size), Image.Resampling.LANCZOS)
        
        # Circle Mask for DP
        mask = Image.new('L', (av_size, av_size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, av_size, av_size), fill=255)
        
        av_x, av_y = (W - av_size) // 2, panel_y - (av_size // 2) + 30
        
        # Shadow for DP
        shadow = Image.new('RGBA', (av_size, av_size), (0,0,0,0))
        ImageDraw.Draw(shadow).ellipse((10, 10, av_size-10, av_size-10), fill=(0,0,0,80))
        shadow = shadow.filter(ImageFilter.GaussianBlur(15))
        img.paste(shadow, (av_x, av_y+10), shadow)
        
        # Paste DP
        img.paste(avatar, (av_x, av_y), mask)
        d.ellipse([av_x, av_y, av_x+av_size, av_y+av_size], outline=accent, width=10)

    # 5. Text
    cx = W // 2
    utils.write_text(d, (cx, panel_y + 230), "WELCOME", size=50, align="center", col="#CCCCCC")
    utils.write_text(d, (cx, panel_y + 300), username.upper(), size=90, align="center", col="white", shadow=True)
    utils.write_text(d, (cx, panel_y + 400), f"to {room_name}", size=45, align="center", col=accent)

    # 6. Smooth Round Corners
    final_mask = Image.new('L', (W, H), 0)
    ImageDraw.Draw(final_mask).rounded_rectangle([0, 0, W, H], radius=60, fill=255)
    final = Image.new('RGBA', (W, H), (0,0,0,0))
    final.paste(img, (0,0), final_mask)
    
    return final

# ==========================================
# ⚡ EVENT HANDLERS
# ==========================================

def background_process(bot, room_id, username, room_name, avatar_url):
    try:
        img = render_card(username, room_name, avatar_url)
        url = utils.upload(bot, img)
        if url:
            bot.send_json({
                "handler": "chatroommessage",
                "roomid": room_id,
                "type": "image",
                "url": url,
                "text": f"Welcome @{username}! 💛"
            })
    except Exception as e:
        print(f"[Welcome] Error: {e}")

def handle_system_message(bot, data):
    handler = data.get("handler")
    if handler == "userjoin":
        room_id = data.get("roomid")
        
        # Check Room Toggle (Default: Enabled)
        if not ROOM_SETTINGS.get(room_id, True):
            return

        username = data.get("username")
        avatar_url = data.get("avatar") # Fetching real DP from Join Payload

        if username == bot.user_data.get('username'): return
        room_name = bot.room_id_to_name_map.get(room_id, "The Chat")
        
        utils.run_in_bg(background_process, bot, room_id, username, room_name, avatar_url)

def handle_command(bot, command, room_id, user, args, data):
    global ROOM_SETTINGS
    cmd = command.lower().strip()
    
    if cmd == "welcome":
        if not args:
            status = "ENABLED" if ROOM_SETTINGS.get(room_id, True) else "DISABLED"
            bot.send_message(room_id, f"👋 Welcome cards for this room: **{status}**")
            return True
            
        action = args[0].lower()
        if action == "on":
            ROOM_SETTINGS[room_id] = True
            bot.send_message(room_id, "✅ Welcome cards turned **ON** for this room.")
        elif action == "off":
            ROOM_SETTINGS[room_id] = False
            bot.send_message(room_id, "🔕 Welcome cards turned **OFF** for this room.")
        return True
        
    return False
