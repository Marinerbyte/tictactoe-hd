import io
import random
import uuid
import requests
import time
import threading
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

# --- IMPORTS ---
try: 
    import utils 
except ImportError: 
    print("[Welcome] Warning: utils.py not found. Uploads will fail.")

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================

# Toggles
WELCOME_ENABLED = True 
TRANSPARENT_MODE = False # Default OFF

CARD_SIZE = 1024

# Avatar API (DiceBear Adventurer - Best for Chatrooms)
AVATAR_API = "https://api.dicebear.com/9.x/adventurer/png?seed={}&backgroundColor=transparent&size=512"

# Dynamic Greetings with Emojis 🌟
GREETINGS = [
    "Look who's here! 👀",
    "Welcome Aboard! 🚀",
    "A wild user appeared! 🦁",
    "Glad you made it! ✨",
    "Welcome to the party! 🥳",
    "Hop on in! 🐰",
    "Good to see you! 👋",
    "Say Hello to... 🎤",
    "Just landed! 🛬",
    "Welcome, Legend! 👑",
    "New Challenger! ⚔️",
    "The VIP arrived! 💎"
]

# Color Palettes (Backgrounds & Accents)
PALETTES = [
    ("#0f0c29", "#302b63", "#00d2ff"), # Cyberpunk
    ("#11998e", "#38ef7d", "#ffffff"), # Fresh Nature
    ("#FF416C", "#FF4B2B", "#FFD700"), # Sunset Fire
    ("#000000", "#434343", "#F1C40F"), # Luxury Gold
    ("#8E2DE2", "#4A00E0", "#E0C3FC"), # Electric Purple
    ("#200122", "#6f0000", "#c70039"), # Dark Red
    ("#000428", "#004e92", "#ffffff"), # Deep Ocean
]

def setup(bot):
    print("[Welcome] Transparent & Emoji Edition Loaded.")

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
    def add_abstract_art(img, accent):
        """Adds random circles/lines for premium look"""
        d = ImageDraw.Draw(img, 'RGBA')
        W, H = img.size
        for _ in range(6):
            x = random.randint(-100, W)
            y = random.randint(-100, H)
            s = random.randint(100, 500)
            fill = (255, 255, 255, 10) # Very faint white
            d.ellipse([x, y, x+s, y+s], fill=fill)
        return img

    @staticmethod
    def get_avatar(username):
        try:
            # Unique seed ensures unique avatar per user
            seed = f"{username}-{random.randint(1,9999)}"
            url = AVATAR_API.format(seed)
            headers = {'User-Agent': 'Mozilla/5.0'}
            r = requests.get(url, headers=headers, timeout=4)
            if r.status_code == 200:
                return Image.open(io.BytesIO(r.content)).convert("RGBA")
        except: pass
        return None

# ==========================================
# 🖼️ CARD RENDERER
# ==========================================

def render_card(username, room_name):
    W, H = CARD_SIZE, CARD_SIZE
    
    # 1. Choose Random Theme & Greeting
    theme = random.choice(PALETTES)
    greeting = random.choice(GREETINGS)
    c1, c2, accent = theme
    
    # 2. Setup Background (Transparent or Gradient)
    if TRANSPARENT_MODE:
        # Fully Transparent Base
        img = Image.new('RGBA', (W, H), (0,0,0,0))
    else:
        # Gradient Base
        img = DesignEngine.get_gradient(W, H, c1, c2).convert("RGBA")
        img = DesignEngine.add_abstract_art(img, accent)
    
    d = ImageDraw.Draw(img, 'RGBA')
    
    # 3. Glass Panel (Bottom Area)
    panel_y = 500
    
    # Logic: Transparent mode me panel thoda zyada dark rakhenge
    # taaki light theme wale apps me bhi text dikhe
    panel_opacity = 200 if TRANSPARENT_MODE else 140
    
    d.rounded_rectangle([50, panel_y, W-50, H-50], radius=40, fill=(0,0,0, panel_opacity))
    d.rounded_rectangle([50, panel_y, W-50, H-50], radius=40, outline=accent, width=3)
    
    # 4. Avatar (Top Center, Floating)
    av = DesignEngine.get_avatar(username)
    av_size = 400
    
    # Center Coordinates
    cx = W // 2
    cy = panel_y # Avatar sits exactly on the panel edge
    
    if av:
        av = av.resize((av_size, av_size), Image.Resampling.LANCZOS)
        
        # Shadow behind avatar
        d.ellipse([cx-180, cy-180+20, cx+180, cy+180+20], fill=(0,0,0,100))
        
        # Paste Avatar
        img.paste(av, (cx - av_size//2, cy - av_size//2 - 50), av)
        
    # 5. Typography (Smart Scaling)
    try: font_main = ImageFont.truetype("arial.ttf", 80)
    except: font_main = ImageFont.load_default()
    try: font_sub = ImageFont.truetype("arial.ttf", 40)
    except: font_sub = ImageFont.load_default()
    try: font_emoji = ImageFont.truetype("seguiemj.ttf", 40) # Try emoji font
    except: font_emoji = font_sub
    
    # Helper to draw centered text
    def draw_centered(text, y, font, col):
        try: w = font.getlength(text)
        except: w = len(text) * 20
        d.text(((W-w)/2, y), text, font=font, fill=col)

    # Greeting (With Emoji Support logic handled by font fallback usually)
    draw_centered(greeting, panel_y + 160, font_sub, "#CCCCCC")
    
    # Username (Big & Bold)
    draw_centered(username, panel_y + 230, font_main, "white")
    
    # Room Name (Bottom)
    room_text = f"to {room_name}"
    draw_centered(room_text, panel_y + 350, font_sub, accent)

    return img

# ==========================================
# ⚡ HANDLERS
# ==========================================

def process_welcome(bot, room_id, username, room_name):
    try:
        # Generate
        img = render_card(username, room_name)
        
        # Upload (Uses utils.upload which handles requests/timeouts)
        # Note: utils.upload automatically saves as PNG if we pass image object
        link = utils.upload(bot, img)
        
        if link:
            bot.send_json({
                "handler": "chatroommessage",
                "roomid": room_id,
                "type": "image",
                "url": link,
                "text": f"Welcome {username}! 👋"
            })
    except Exception as e:
        print(f"[Welcome] Error: {e}")

def handle_system_message(bot, data):
    """Triggered on User Join"""
    if not WELCOME_ENABLED: return
    
    handler = data.get("handler")
    if handler == "userjoin":
        username = data.get("username")
        room_id = data.get("roomid")
        
        # Don't welcome self
        if username == bot.user_data.get('username'): return
        
        # ROOM NAME FETCHING LOGIC
        # 1. Try bot's room map
        room_name = bot.room_id_to_name_map.get(room_id)
        
        # 2. Try getting from data if available
        if not room_name:
            room_name = data.get("title") or data.get("room_name")
            
        # 3. Fallback
        if not room_name:
            room_name = "The Chat"
            
        print(f"[Welcome] Greeting {username} in {room_name}")
        
        # Run in Background (No Lag)
        utils.run_in_bg(process_welcome, bot, room_id, username, room_name)

def handle_command(bot, command, room_id, user, args, data):
    """ !welcome on/off/test/transparent """
    global WELCOME_ENABLED, TRANSPARENT_MODE
    cmd = command.lower().strip()
    
    if cmd == "welcome":
        if not args:
            status = "ON" if WELCOME_ENABLED else "OFF"
            t_mode = "ON" if TRANSPARENT_MODE else "OFF"
            bot.send_message(room_id, f"👋 **Settings:**\nPlugin: {status}\nTransparent: {t_mode}")
            return True
            
        arg = args[0].lower()
        
        # Main Toggle
        if arg == "on":
            WELCOME_ENABLED = True
            bot.send_message(room_id, "✅ Welcome Plugin Enabled")
        elif arg == "off":
            WELCOME_ENABLED = False
            bot.send_message(room_id, "❌ Welcome Plugin Disabled")
            
        # Transparent Mode Toggle
        elif arg == "transparent":
            if len(args) > 1 and args[1] == "on":
                TRANSPARENT_MODE = True
                bot.send_message(room_id, "✨ Transparent Mode: **ON**")
            elif len(args) > 1 and args[1] == "off":
                TRANSPARENT_MODE = False
                bot.send_message(room_id, "🎨 Gradient Mode: **ON**")
            else:
                state = "ON" if TRANSPARENT_MODE else "OFF"
                bot.send_message(room_id, f"ℹ️ Transparent Mode is **{state}**")

        # Test Command
        elif arg == "test":
            rname = bot.room_id_to_name_map.get(room_id, "Test Room")
            bot.send_message(room_id, "🎨 Creating Test Card...")
            utils.run_in_bg(process_welcome, bot, room_id, user, rname)
            
        return True
    return False
