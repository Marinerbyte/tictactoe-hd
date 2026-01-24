import io
import random
import uuid
import math
import requests
import time
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps, ImageChops

# --- IMPORTS ---
try: 
    import utils 
except ImportError: 
    print("[Welcome] Warning: utils.py not found. Uploads will fail.")

# ==========================================
# ⚙️ CONFIGURATION & TOGGLES
# ==========================================

# GLOBAL TOGGLES (Controlled via !welcome command)
WELCOME_CARD_ENABLED = True 
BURST_ENABLED = False  # Set to True to enable GIF generation by default

# DESIGN SETTINGS
CARD_SIZE = 800  # 800x800 is best balance for GIF quality vs speed
AVATAR_API = "https://api.dicebear.com/9.x/adventurer/png?seed={}&backgroundColor=transparent&size=512"

# MODERN COLOR PALETTES (Bg1, Bg2, Accent, TextColor)
PALETTES = [
    ("#1A2980", "#26D0CE", "#00FFF0", "white"), # Aqua Splash
    ("#E55D87", "#5FC3E4", "#FFFFFF", "white"), # Rose Water
    ("#FF512F", "#DD2476", "#FFD700", "white"), # Bloody Mary
    ("#11998e", "#38ef7d", "#ccffcc", "white"), # Lush Green
    ("#0F2027", "#2C5364", "#00d2ff", "white"), # Space Night
    ("#8E2DE2", "#4A00E0", "#E0C3FC", "white"), # Electric Violet
    ("#F7971E", "#FFD200", "#FFF", "white"),    # Solar Power
]

def setup(bot):
    print("[Welcome] Plugin Loaded. GIF Engine Ready.")

# ==========================================
# ✨ PARTICLE SYSTEM (FOR GIFS)
# ==========================================

class Particle:
    def __init__(self, cx, cy, color):
        self.x = cx
        self.y = cy
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(2, 15)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.size = random.randint(3, 8)
        self.color = color
        self.life = 255  # Opacity
        self.decay = random.randint(15, 30)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.life -= self.decay
        self.size = max(0, self.size - 0.2) # Shrink slightly

    def draw(self, draw):
        if self.life > 0:
            fill = self.color + (int(self.life),) # Add Alpha
            draw.ellipse(
                [self.x, self.y, self.x+self.size, self.y+self.size], 
                fill=fill
            )

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
    def add_texture(img):
        w, h = img.size
        # Add subtle noise
        noise = Image.effect_noise((w, h), 15).convert('L')
        noise = ImageOps.colorize(noise, black="black", white="white").convert('RGBA')
        noise.putalpha(20)
        return Image.alpha_composite(img.convert('RGBA'), noise)

    @staticmethod
    def get_avatar(username):
        try:
            unique_seed = f"{username}-{uuid.uuid4().hex[:6]}"
            url = AVATAR_API.format(unique_seed)
            r = requests.get(url, timeout=4)
            if r.status_code == 200:
                return Image.open(io.BytesIO(r.content)).convert("RGBA")
        except: pass
        return None

    @staticmethod
    def draw_decorations(draw, w, h, color):
        style = random.choice(['rings', 'rays', 'dots'])
        fill_col = (255, 255, 255, 20)
        
        if style == 'rings':
            for _ in range(5):
                r = random.randint(100, 600)
                xy = (random.randint(-100, w), random.randint(-100, h))
                draw.ellipse([xy[0]-r, xy[1]-r, xy[0]+r, xy[1]+r], outline=fill_col, width=3)
        elif style == 'dots':
            for _ in range(30):
                x, y = random.randint(0, w), random.randint(0, h)
                s = random.randint(5, 20)
                draw.ellipse([x, y, x+s, y+s], fill=fill_color)

# ==========================================
# 🖼️ MASTER RENDERER
# ==========================================

def render_card(username, room_name):
    """
    Generates the card. Returns either bytes (PNG) or bytes (GIF).
    """
    W, H = CARD_SIZE, CARD_SIZE
    
    # 1. Theme Setup
    theme = random.choice(PALETTES)
    c1, c2, accent_hex, txt_col = theme
    # Convert accent hex to RGB tuple for particles
    accent_rgb = tuple(int(accent_hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))

    # 2. Base Background
    bg = DesignEngine.get_gradient(W, H, c1, c2)
    bg = DesignEngine.add_texture(bg)
    d = ImageDraw.Draw(bg, 'RGBA')
    DesignEngine.draw_decorations(d, W, H, accent_rgb)

    # 3. Avatar Processing
    av_size = 350
    avatar = DesignEngine.get_avatar(username)
    
    if avatar:
        avatar = avatar.resize((av_size, av_size), Image.Resampling.LANCZOS)
        # Circular Mask
        mask = Image.new('L', (av_size, av_size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, av_size, av_size), fill=255)
        
        # Center Position
        cx, cy = W // 2, (H // 2) - 50
        av_x = cx - (av_size // 2)
        av_y = cy - (av_size // 2)
        
        # Shadow
        shadow = Image.new('RGBA', (av_size, av_size), (0,0,0,0))
        ImageDraw.Draw(shadow).ellipse((10, 10, av_size-10, av_size-10), fill=(0,0,0,80))
        shadow = shadow.filter(ImageFilter.GaussianBlur(20))
        bg.paste(shadow, (av_x, av_y+10), shadow)
        
        # Paste Avatar
        bg.paste(avatar, (av_x, av_y), mask)
        
        # Border Ring
        d.ellipse([av_x, av_y, av_x+av_size, av_y+av_size], outline=accent_rgb + (255,), width=6)

    # 4. Text Overlay
    # Use utils.write_text logic for consistency, but reimplemented here for custom placement
    try: font_main = ImageFont.truetype("arial.ttf", 70)
    except: font_main = ImageFont.load_default()
    try: font_sub = ImageFont.truetype("arial.ttf", 35)
    except: font_sub = ImageFont.load_default()

    # Calculate text width helper
    def draw_centered(text, y, font, color, shadow=False):
        try: w = font.getlength(text)
        except: w = len(text) * 20
        x = (W - w) // 2
        if shadow: d.text((x+3, y+3), text, font=font, fill=(0,0,0,100))
        d.text((x, y), text, font=font, fill=color)

    draw_centered("WELCOME", H - 280, font_sub, "#DDDDDD")
    draw_centered(username.upper(), H - 220, font_main, "white", shadow=True)
    draw_centered(f"to {room_name}", H - 120, font_sub, accent_hex)

    # --- GIF GENERATION BRANCH ---
    if BURST_ENABLED:
        frames = []
        particles = []
        center_x, center_y = W // 2, (H // 2) - 50
        
        # Initialize burst
        for _ in range(40):
            particles.append(Particle(center_x, center_y, accent_rgb))

        # Render Frames
        # Generate 20 frames for the GIF
        for _ in range(20):
            # Copy base image
            frame = bg.copy()
            fd = ImageDraw.Draw(frame, 'RGBA')
            
            # Update & Draw Particles
            alive_particles = []
            for p in particles:
                p.update()
                p.draw(fd)
                if p.life > 0: alive_particles.append(p)
            particles = alive_particles
            
            frames.append(frame)

        # Export GIF
        output = io.BytesIO()
        frames[0].save(
            output, 
            format='GIF', 
            save_all=True, 
            append_images=frames[1:], 
            optimize=False, 
            duration=60, 
            loop=0
        )
        return output.getvalue(), 'gif'

    # --- STATIC PNG BRANCH ---
    else:
        output = io.BytesIO()
        bg.save(output, format='PNG')
        return output.getvalue(), 'png'

# ==========================================
# ⚡ EVENT HANDLERS
# ==========================================

def background_process(bot, room_id, username, room_name):
    """Runs in background to keep bot responsive"""
    try:
        # Render (Returns Bytes, Extension)
        img_bytes, ext = render_card(username, room_name)
        
        # Convert bytes back to PIL for utils.upload (it expects PIL or we adjust)
        # Actually utils.upload expects PIL Image object generally. 
        # Let's handle it manually here to support GIF bytes directly.
        
        upload_url = None
        
        # Custom Upload Logic for GIF/PNG Bytes
        import requests
        url = "https://api.howdies.app/api/upload"
        mime = 'image/gif' if ext == 'gif' else 'image/png'
        files = {'file': (f'welcome.{ext}', img_bytes, mime)}
        data = {'token': bot.token, 'uploadType': 'image', 'UserID': bot.user_id or 0}
        
        r = requests.post(url, files=files, data=data, timeout=60)
        if r.status_code == 200:
            upload_url = r.json().get('url') or r.json().get('data', {}).get('url')

        if upload_url:
            msg_type = "image" # Both gif and png are treated as image type usually
            bot.send_json({
                "handler": "chatroommessage",
                "roomid": room_id,
                "type": msg_type,
                "url": upload_url,
                "text": f"Welcome @{username}!"
            })
            
    except Exception as e:
        print(f"[Welcome] Error: {e}")

def handle_system_message(bot, data):
    """Triggered on user join"""
    if not WELCOME_CARD_ENABLED: return

    if data.get("handler") == "userjoin":
        username = data.get("username")
        room_id = data.get("roomid")
        
        if username == bot.user_data.get('username'): return
        
        room_name = bot.room_id_to_name_map.get(room_id, "Room")
        
        # Run in Background
        utils.run_in_bg(background_process, bot, room_id, username, room_name)

def handle_command(bot, command, room_id, user, args, data):
    """
    !welcome on/off
    !welcome gif on/off
    """
    global WELCOME_CARD_ENABLED, BURST_ENABLED
    
    cmd = command.lower().strip()
    if cmd == "welcome":
        if not args:
            state = "ON" if WELCOME_CARD_ENABLED else "OFF"
            gif_state = "ON" if BURST_ENABLED else "OFF"
            bot.send_message(room_id, f"👋 **Welcome Settings:**\nCard: {state}\nGIF Burst: {gif_state}")
            return True
            
        arg1 = args[0].lower()
        
        # Toggle Main Feature
        if arg1 == "on":
            WELCOME_CARD_ENABLED = True
            bot.send_message(room_id, "✅ Welcome Cards: **Enabled**")
        elif arg1 == "off":
            WELCOME_CARD_ENABLED = False
            bot.send_message(room_id, "❌ Welcome Cards: **Disabled**")
            
        # Toggle GIF Feature
        elif arg1 == "gif" and len(args) > 1:
            if args[1].lower() == "on":
                BURST_ENABLED = True
                bot.send_message(room_id, "✨ GIF Burst: **Enabled**")
            elif args[1].lower() == "off":
                BURST_ENABLED = False
                bot.send_message(room_id, "🖼️ GIF Burst: **Disabled** (Static Mode)")
                
        return True
    return False
