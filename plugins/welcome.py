import io
import random
import uuid
import requests
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

WELCOME_ENABLED = True 
CARD_SIZE = 1024

# 🔥 POWERFUL STICKER API (3D Fun Emojis)
# Ye style sabse best hai stickers ke liye
AVATAR_API = "https://api.dicebear.com/9.x/fun-emoji/png?seed={}&backgroundColor=transparent&size=600"

# 🌟 PREMIUM GREETINGS (With Emojis)
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
    "The VIP arrived! 💎",
    "Knock Knock! 🚪",
    "Player Joined! 🎮"
]

# 🎨 VIBRANT PALETTES (Backgrounds)
PALETTES = [
    ("#4158D0", "#C850C0", "#FFCC70"), # Peach Purple
    ("#0093E9", "#80D0C7", "#FFFFFF"), # Aqua Blue
    ("#8EC5FC", "#E0C3FC", "#FFFFFF"), # Soft Lavender
    ("#D9AFD9", "#97D9E1", "#FFFFFF"), # Sky Pink
    ("#FBAB7E", "#F7CE68", "#FFFFFF"), # Warm Gold
    ("#FF3CAC", "#784BA0", "#2B86C5"), # Deep Neon
    ("#21D4FD", "#B721FF", "#FFFFFF"), # Electric Purple
]

def setup(bot):
    print("[Welcome] Ultra-Sticker Edition Loaded.")

# ==========================================
# 🎨 GRAPHICS ENGINE
# ==========================================

class DesignEngine:
    
    @staticmethod
    def get_font(size):
        """Finds the best font available on the system"""
        font_paths = [
            "arialbd.ttf", "arial.ttf", # Windows
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", # Linux (Render)
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"
        ]
        for path in font_paths:
            try: return ImageFont.truetype(path, size)
            except: continue
        return ImageFont.load_default()

    @staticmethod
    def create_background(w, h, c1, c2):
        """Creates a high-quality gradient with Noise Texture"""
        # 1. Gradient
        base = Image.new('RGB', (w, h), c1)
        top = Image.new('RGB', (w, h), c2)
        mask = Image.new('L', (w, h))
        mask_data = []
        for y in range(h): mask_data.extend([int(255 * (y / h))] * w)
        mask.putdata(mask_data)
        base.paste(top, (0, 0), mask)
        
        # 2. Add Noise (Grain Effect for realism)
        noise = Image.effect_noise((w, h), 10).convert('L')
        noise = ImageOps.colorize(noise, black="black", white="white").convert('RGBA')
        noise.putalpha(25) # Subtle grain
        
        img = base.convert("RGBA")
        img.paste(noise, (0,0), noise)
        return img

    @staticmethod
    def add_shapes(img):
        """Adds floating bubbles/shapes"""
        d = ImageDraw.Draw(img, 'RGBA')
        W, H = img.size
        for _ in range(8):
            x = random.randint(-100, W)
            y = random.randint(-100, H)
            s = random.randint(50, 400)
            fill = (255, 255, 255, 20) # Transparent White
            d.ellipse([x, y, x+s, y+s], fill=fill)
        return img

    @staticmethod
    def get_sticker(username):
        """Downloads the 3D Emoji Sticker"""
        try:
            seed = f"{username}-{random.randint(1,9999)}"
            url = AVATAR_API.format(seed)
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
    
    # 1. Setup Theme
    theme = random.choice(PALETTES)
    greeting = random.choice(GREETINGS)
    c1, c2, accent = theme
    
    # 2. Create Art Background
    bg = DesignEngine.create_background(W, H, c1, c2)
    bg = DesignEngine.add_shapes(bg)
    
    # 3. Create the "Card Body" (Floating Glass)
    # Isse hum round corners denge
    card_margin = 60
    card_w = W - (card_margin * 2)
    card_h = H - (card_margin * 2)
    
    # Create Mask for Round Corners
    mask = Image.new('L', (W, H), 0)
    d_mask = ImageDraw.Draw(mask)
    d_mask.rounded_rectangle(
        [card_margin, card_margin, W-card_margin, H-card_margin], 
        radius=60, fill=255
    )
    
    # Apply Mask to Background (This makes the outer area transparent or clean)
    # Actually, let's keep full background but draw a white panel
    
    # Draw White Glass Panel
    panel = Image.new("RGBA", (W, H), (0,0,0,0))
    d_panel = ImageDraw.Draw(panel)
    d_panel.rounded_rectangle(
        [card_margin, card_margin, W-card_margin, H-card_margin],
        radius=60, fill=(255, 255, 255, 40) # Glassy White
    )
    d_panel.rounded_rectangle(
        [card_margin, card_margin, W-card_margin, H-card_margin],
        radius=60, outline=(255, 255, 255, 100), width=4 # Sharp White Border
    )
    bg.paste(panel, (0,0), panel)

    # 4. Avatar (The Sticker)
    av = DesignEngine.get_sticker(username)
    av_size = 450
    cx = W // 2
    cy = 400 # Top half
    
    if av:
        av = av.resize((av_size, av_size), Image.Resampling.LANCZOS)
        
        # Sticker Shadow (Floating Effect)
        shadow = av.copy()
        shadow = ImageOps.colorize(shadow.convert('L'), black=(0,0,0), white=(0,0,0))
        shadow.putalpha(60)
        shadow = shadow.filter(ImageFilter.GaussianBlur(20))
        
        # Paste Shadow then Avatar
        bg.paste(shadow, (cx - av_size//2, cy - av_size//2 + 20), shadow)
        bg.paste(av, (cx - av_size//2, cy - av_size//2), av)

    # 5. Text (Auto-Scaling)
    d = ImageDraw.Draw(bg)
    
    def draw_auto_text(text, y_pos, max_font, color):
        size = max_font
        font = DesignEngine.get_font(size)
        
        # Shrink to fit width
        max_width = card_w - 40
        while size > 20:
            try: w = font.getlength(text)
            except: w = len(text) * (size * 0.6)
            if w < max_width: break
            size -= 5
            font = DesignEngine.get_font(size)
            
        # Draw Center
        try: w = font.getlength(text)
        except: w = len(text) * (size * 0.6)
        x = (W - w) // 2
        
        # Text Shadow
        d.text((x+3, y_pos+3), text, font=font, fill=(0,0,0,50))
        d.text((x, y_pos), text, font=font, fill=color)

    # Greeting (Small)
    draw_auto_text(greeting, 650, 50, "white")
    
    # Username (Huge)
    draw_auto_text(username.upper(), 720, 110, "white")
    
    # Room Name (Medium)
    draw_auto_text(f"joined {room_name}", 850, 45, "#EEEEEE")

    return bg

# ==========================================
# ⚡ HANDLERS
# ==========================================

def process_welcome(bot, room_id, username, room_name):
    try:
        img = render_card(username, room_name)
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
            status = "ON" if WELCOME_ENABLED else "OFF"
            bot.send_message(room_id, f"👋 Status: **{status}**")
            return True
            
        arg = args[0].lower()
        if arg == "on":
            WELCOME_ENABLED = True
            bot.send_message(room_id, "✅ Enabled")
        elif arg == "off":
            WELCOME_ENABLED = False
            bot.send_message(room_id, "❌ Disabled")
        elif arg == "test":
            rname = bot.room_id_to_name_map.get(room_id, "Test Room")
            utils.run_in_bg(process_welcome, bot, room_id, user, rname)
            
        return True
    return False
