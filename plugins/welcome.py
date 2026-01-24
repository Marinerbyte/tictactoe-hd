import io
import random
import requests
import threading
from PIL import Image, ImageDraw, ImageFont, ImageFilter

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

# CUTE EMOJI API (3D Style)
AVATAR_API = "https://api.dicebear.com/9.x/fun-emoji/png?seed={}&backgroundColor=transparent&size=600"

# DECENT MESSAGES
GREETINGS = [
    "Welcome to the Community!",
    "Glad you are here!",
    "Hello & Welcome!",
    "Welcome to the Family!",
    "Nice to meet you!",
    "Welcome Aboard!",
    "New Member Joined!",
    "Enjoy your stay!"
]

# CLEAN & FRESH PALETTES
PALETTES = [
    ("#4facfe", "#00f2fe", "#ffffff"), # Blue Sky
    ("#43e97b", "#38f9d7", "#ffffff"), # Mint Green
    ("#fa709a", "#fee140", "#ffffff"), # Soft Pink/Yellow
    ("#667eea", "#764ba2", "#ffffff"), # Deep Purple
    ("#ff0844", "#ffb199", "#ffffff"), # Red Fade
    ("#000000", "#434343", "#FFD700"), # Black Gold
    ("#209cff", "#68e0cf", "#ffffff")  # Ocean
]

def setup(bot):
    print("[Welcome] Clean & Cute Edition Loaded.")

# ==========================================
# 🎨 GRAPHICS ENGINE
# ==========================================

def get_font(size):
    """Finds the best available font"""
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", # Render Default
        "arialbd.ttf", "arial.ttf"
    ]
    for path in font_paths:
        try: return ImageFont.truetype(path, size)
        except: continue
    return ImageFont.load_default()

def get_avatar(username):
    """Fetches Cute 3D Emoji"""
    try:
        seed = f"{username}-{random.randint(1,999)}"
        url = AVATAR_API.format(seed)
        r = requests.get(url, timeout=4)
        if r.status_code == 200:
            return Image.open(io.BytesIO(r.content)).convert("RGBA")
    except: pass
    return None

def make_rounded(img, radius):
    """Makes the image actually round (Transparent Corners)"""
    mask = Image.new('L', img.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), img.size], radius=radius, fill=255)
    img.putalpha(mask)
    return img

def draw_auto_text(draw, text, y_pos, max_width, max_font_size, color, center_x):
    """Auto-scales text to fit perfectly"""
    size = max_font_size
    font = get_font(size)
    
    # Resize loop
    while size > 20:
        try: w = font.getlength(text)
        except: w = len(text) * size * 0.6
        if w < max_width: break
        size -= 5
        font = get_font(size)
        
    try: w = font.getlength(text)
    except: w = len(text) * size * 0.6
    
    # Shadow for readability
    draw.text((center_x - w/2 + 2, y_pos + 2), text, font=font, fill=(0,0,0, 80))
    # Main Text
    draw.text((center_x - w/2, y_pos), text, font=font, fill=color)

# ==========================================
# 🖼️ MASTER RENDERER
# ==========================================

def render_card(username, room_name):
    W, H = CARD_SIZE, CARD_SIZE
    
    # 1. Setup Theme
    c1, c2, txt_col = random.choice(PALETTES)
    greeting = random.choice(GREETINGS)
    
    # 2. Gradient Background
    base = Image.new('RGB', (W, H), c1)
    top = Image.new('RGB', (W, H), c2)
    mask = Image.new('L', (W, H))
    m_data = []
    for y in range(H): m_data.extend([int(255 * (y / H))] * W)
    mask.putdata(m_data)
    base.paste(top, (0, 0), mask)
    img = base.convert("RGBA")
    
    d = ImageDraw.Draw(img)
    
    # 3. Inner White Frame (Neat Look)
    margin = 40
    d.rounded_rectangle(
        [margin, margin, W-margin, H-margin], 
        radius=60, 
        fill=(255, 255, 255, 30), # Very light glass
        outline=(255, 255, 255, 100), 
        width=4
    )

    # 4. Cute Avatar
    av = get_avatar(username)
    if av:
        av = av.resize((450, 450), Image.Resampling.LANCZOS)
        cx, cy = W // 2, 380
        
        # Soft Shadow under avatar
        d.ellipse([cx-180, cy+180, cx+180, cy+210], fill=(0,0,0, 60))
        
        # Place Avatar
        img.paste(av, (cx - 225, cy - 225), av)

    # 5. Text Layout
    cx = W // 2
    
    # Greeting (Small & Top)
    draw_auto_text(d, greeting, 620, W-100, 50, "#EEEEEE", cx)
    
    # Username (Big & Bold)
    draw_auto_text(d, username, 690, W-100, 110, "white", cx)
    
    # Room Name (Bottom)
    draw_auto_text(d, f"Joined: {room_name}", 850, W-150, 45, "#DDDDDD", cx)

    # 6. Apply Real Round Corners
    img = make_rounded(img, 80)
    
    return img

# ==========================================
# ⚡ HANDLERS
# ==========================================

def process_welcome(bot, room_id, username, room_name):
    try:
        img = render_card(username, room_name)
        
        # Use utils to upload (it handles PNG conversion)
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
        
        # Don't welcome self
        if u == bot.user_data.get('username'): return
        
        # Safe Room Name
        rname = bot.room_id_to_name_map.get(rid)
        if not rname: rname = data.get("title") or "The Chat"
            
        utils.run_in_bg(process_welcome, bot, rid, u, rname)

def handle_command(bot, command, room_id, user, args, data):
    global WELCOME_ENABLED
    cmd = command.lower().strip()
    
    if cmd == "welcome":
        if not args:
            st = "ON" if WELCOME_ENABLED else "OFF"
            bot.send_message(room_id, f"Welcome Plugin: **{st}**")
            return True
            
        arg = args[0].lower()
        if arg == "on": WELCOME_ENABLED = True; bot.send_message(room_id, "✅ Enabled")
        elif arg == "off": WELCOME_ENABLED = False; bot.send_message(room_id, "❌ Disabled")
        elif arg == "test":
            rname = bot.room_id_to_name_map.get(room_id, "Test Room")
            utils.run_in_bg(process_welcome, bot, room_id, user, rname)
            
        return True
    return False
