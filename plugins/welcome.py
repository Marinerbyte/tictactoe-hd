import io
import os
import random
import uuid
import requests
import threading
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

# --- IMPORTS ---
try: 
    import utils 
except ImportError: 
    print("[Welcome] Warning: utils.py not found.")

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================

WELCOME_ENABLED = True 
CARD_SIZE = 1024

# 🌟 PREMIUM AVATAR STYLES (Mix of the best human styles)
AVATAR_STYLES = [
    "notionists",   # Sketchy/Cool
    "adventurer",   # Detailed/RPG
    "lorelei",      # Artistic/Flat
    "avataaars",    # Classic Vector
    "micah"         # Modern Clean
]

GREETINGS = [
    "Look who's here!",
    "Welcome Aboard!",
    "A wild user appeared!",
    "Glad you made it!",
    "Welcome to the party!",
    "Hop on in!",
    "Good to see you!",
    "Just landed!",
    "The VIP arrived!",
    "New Challenger!"
]

# 🎨 DEEP GRADIENTS (Premium Look)
PALETTES = [
    ("#20002c", "#cbb4d4"), # Dark Purple -> Light
    ("#000046", "#1cb5e0"), # Deep Sea
    ("#0f2027", "#2c5364"), # Space
    ("#373b44", "#4286f4"), # Corporate Blue
    ("#8e2de2", "#4a00e0"), # Electric Violet
    ("#1a2a6c", "#b21f1f"), # America
    ("#000000", "#434343")  # Pure Luxury
]

def setup(bot):
    print("[Welcome] Human-Avatar Edition Loaded.")

# ==========================================
# 🎨 ASSET FETCHING
# ==========================================

def get_font(size):
    """Linux/Windows Safe Fonts"""
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "arialbd.ttf", "arial.ttf"
    ]
    for path in font_paths:
        try: return ImageFont.truetype(path, size)
        except: continue
    return ImageFont.load_default()

def get_avatar(username):
    """Fetches a RANDOM premium style every time"""
    try:
        # Pick a random style (Notion, Adventurer, etc.)
        style = random.choice(AVATAR_STYLES)
        
        # Seed ensures consistent look for same user + style
        seed = f"{username}-{random.randint(1,999)}"
        
        url = f"https://api.dicebear.com/9.x/{style}/png?seed={seed}&size=512&backgroundColor=transparent"
        
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=4)
        if r.status_code == 200:
            return Image.open(io.BytesIO(r.content)).convert("RGBA")
    except: pass
    return None

# ==========================================
# 🖼️ MASTER RENDERER
# ==========================================

def render_card(username, room_name):
    W, H = CARD_SIZE, CARD_SIZE
    
    # 1. Background Setup
    c1, c2 = random.choice(PALETTES)
    greeting = random.choice(GREETINGS)
    
    # Gradient
    base = Image.new('RGB', (W, H), c1)
    top = Image.new('RGB', (W, H), c2)
    mask = Image.new('L', (W, H))
    mask_data = []
    for y in range(H): mask_data.extend([int(255 * (y / H))] * W)
    mask.putdata(mask_data)
    base.paste(top, (0, 0), mask)
    img = base.convert("RGBA")
    
    d = ImageDraw.Draw(img)
    
    # 2. Abstract Shapes (Texture)
    for _ in range(5):
        x = random.randint(-200, W); y = random.randint(-200, H)
        s = random.randint(200, 800)
        d.ellipse([x, y, x+s, y+s], fill=(255, 255, 255, 10))

    # 3. Avatar (Center & Large)
    av = get_avatar(username)
    av_size = 420
    cx = W // 2
    cy = 400 # Position slightly up
    
    if av:
        av = av.resize((av_size, av_size), Image.Resampling.LANCZOS)
        
        # Circle Crop
        mask = Image.new('L', (av_size, av_size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, av_size, av_size), fill=255)
        
        # Glow/Shadow behind avatar
        d.ellipse([cx - av_size//2 - 20, cy - av_size//2 - 20, 
                   cx + av_size//2 + 20, cy + av_size//2 + 20], fill=(255, 255, 255, 30))
        
        # Paste Avatar
        bg_av = Image.new('RGBA', (av_size, av_size), (0,0,0,0))
        bg_av.paste(av, (0,0), mask)
        img.paste(bg_av, (cx - av_size//2, cy - av_size//2), bg_av)
        
        # White Border Ring
        d.ellipse([cx - av_size//2, cy - av_size//2, 
                   cx + av_size//2, cy + av_size//2], outline="white", width=8)

    # 4. Text Panel (Bottom Glass)
    panel_y = 650
    d.rounded_rectangle([50, panel_y, W-50, H-50], radius=40, fill=(0,0,0, 100)) # Dark Glass
    
    # Text Drawing Helper
    def draw_text(text, y, max_font, color):
        size = max_font
        font = get_font(size)
        max_w = W - 140
        
        # Auto Scale
        while size > 20:
            try: w = font.getlength(text)
            except: w = len(text) * size * 0.6
            if w < max_w: break
            size -= 5
            font = get_font(size)
            
        try: w = font.getlength(text)
        except: w = len(text) * size * 0.6
        
        d.text(((W-w)/2, y), text, font=font, fill=color)

    # Render Text
    draw_text(greeting.upper(), panel_y + 40, 45, "#CCCCCC")
    draw_text(username, panel_y + 110, 110, "white")
    draw_text(f"joined {room_name}", panel_y + 250, 50, "#00d2ff") # Blue accent

    return img

# ==========================================
# ⚡ HANDLERS
# ==========================================

def process_welcome(bot, room_id, username, room_name):
    try:
        img = render_card(username, room_name)
        
        # Upload
        link = utils.upload(bot, img)
        
        if link:
            bot.send_json({
                "handler": "chatroommessage",
                "roomid": room_id,
                "type": "image",
                "url": link,
                "text": f"Welcome {username}!"
            })
    except Exception as e:
        print(f"[Welcome] Error: {e}")

def handle_system_message(bot, data):
    if not WELCOME_ENABLED: return
    if data.get("handler") == "userjoin":
        u = data.get("username")
        rid = data.get("roomid")
        if u == bot.user_data.get('username'): return
        
        rname = bot.room_id_to_name_map.get(rid)
        if not rname: rname = data.get("title") or "The Chat"
            
        utils.run_in_bg(process_welcome, bot, rid, u, rname)

def handle_command(bot, command, room_id, user, args, data):
    global WELCOME_ENABLED
    cmd = command.lower().strip()
    
    if cmd == "welcome":
        if not args:
            st = "ON" if WELCOME_ENABLED else "OFF"
            bot.send_message(room_id, f"Status: {st}")
            return True
            
        arg = args[0].lower()
        if arg == "on": WELCOME_ENABLED = True; bot.send_message(room_id, "✅ ON")
        elif arg == "off": WELCOME_ENABLED = False; bot.send_message(room_id, "❌ OFF")
        elif arg == "test":
            rname = bot.room_id_to_name_map.get(room_id, "Test Room")
            utils.run_in_bg(process_welcome, bot, room_id, user, rname)
            
        return True
    return False
