import io
import random
import uuid
import requests
import time
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps, ImageChops

# --- IMPORTS ---
# We use the existing utils for threading and uploading to keep the bot stable
try: 
    import utils 
except ImportError: 
    print("[Welcome] Warning: utils.py not found. Uploads will fail.")

# ==========================================
# ⚙️ CONFIGURATION & TOGGLE
# ==========================================

# GLOBAL TOGGLE (Controlled via !welcome command)
WELCOME_CARD_ENABLED = True 

# DESIGN SETTINGS
CARD_SIZE = 1024  # 1:1 Aspect Ratio
AVATAR_API = "https://api.dicebear.com/9.x/adventurer/png?seed={}&backgroundColor=transparent&size=512"

# MODERN COLOR PALETTES (Bg1, Bg2, Accent, TextColor)
PALETTES = [
    ("#2E3192", "#1BFFFF", "#FFFFFF", "white"), # Midnight City
    ("#D4145A", "#FBB03B", "#FFD700", "white"), # Sunset Vibe
    ("#009245", "#FCEE21", "#004d00", "white"), # Fresh Lime
    ("#662D8C", "#ED1E79", "#E0E0E0", "white"), # Deep Berry
    ("#12c2e9", "#c471ed", "#ffffff", "white"), # Unicorn
    ("#000000", "#434343", "#F1C40F", "white"), # Luxury Dark
    ("#FF416C", "#FF4B2B", "#FFCBCB", "white"), # Cherry
]

def setup(bot):
    print("[Welcome] Plugin Loaded. Auto-Greeter is Active.")

# ==========================================
# 🎨 GRAPHICS ENGINE
# ==========================================

class DesignEngine:
    
    @staticmethod
    def get_gradient(w, h, c1, c2):
        """Generates a high-quality linear gradient"""
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
    def add_noise(img, factor=0.05):
        """Adds subtle grain for a premium texture look"""
        w, h = img.size
        # Generate noise
        noise = Image.effect_noise((w, h), 20).convert('L')
        noise = ImageOps.colorize(noise, black="black", white="white").convert('RGBA')
        noise.putalpha(int(255 * factor))
        
        # Blend
        return Image.alpha_composite(img.convert('RGBA'), noise)

    @staticmethod
    def get_avatar(username):
        """Fetches a unique cartoon avatar based on UUID seed"""
        try:
            # Create a unique seed using username + random uuid
            unique_seed = f"{username}-{uuid.uuid4().hex[:8]}"
            url = AVATAR_API.format(unique_seed)
            
            headers = {'User-Agent': 'Mozilla/5.0'}
            r = requests.get(url, headers=headers, timeout=5)
            if r.status_code == 200:
                return Image.open(io.BytesIO(r.content)).convert("RGBA")
        except Exception as e:
            print(f"[Welcome] Avatar Error: {e}")
        return None

    @staticmethod
    def draw_glass_panel(draw, x, y, w, h):
        """Draws a modern frosted glass container"""
        # Semi-transparent dark background
        draw.rounded_rectangle([x, y, x+w, y+h], radius=40, fill=(0, 0, 0, 80))
        # Subtle white border
        draw.rounded_rectangle([x, y, x+w, y+h], radius=40, outline=(255, 255, 255, 50), width=2)

    @staticmethod
    def draw_decorations(draw, w, h, color):
        """Adds random geometric shapes for uniqueness"""
        style = random.choice(['circles', 'lines', 'crosses'])
        
        # Draw subtle shapes in background
        for _ in range(8):
            x = random.randint(0, w)
            y = random.randint(0, h)
            size = random.randint(50, 300)
            
            fill_color = (255, 255, 255, 15) # Very transparent white
            
            if style == 'circles':
                draw.ellipse([x, y, x+size, y+size], fill=fill_color)
            elif style == 'lines':
                x2 = x + random.randint(-200, 200)
                y2 = y + random.randint(-200, 200)
                draw.line([x, y, x2, y2], fill=fill_color, width=5)

# ==========================================
# 🖼️ CARD GENERATOR
# ==========================================

def render_card(username, room_name):
    """Main rendering pipeline"""
    W, H = CARD_SIZE, CARD_SIZE
    
    # 1. Select Theme
    theme = random.choice(PALETTES)
    c1, c2, accent, txt_col = theme
    
    # 2. Background
    img = DesignEngine.get_gradient(W, H, c1, c2)
    img = DesignEngine.add_noise(img) # Add Texture
    d = ImageDraw.Draw(img, 'RGBA')
    
    # 3. Random Decorations
    DesignEngine.draw_decorations(d, W, H, accent)
    
    # 4. Glass Panel (Bottom Half)
    # Holds the text
    panel_h = 450
    panel_y = H - panel_h - 50
    panel_x = 50
    panel_w = W - 100
    DesignEngine.draw_glass_panel(d, panel_x, panel_y, panel_w, panel_h)
    
    # 5. Avatar Processing
    av_size = 400
    avatar = DesignEngine.get_avatar(username)
    
    if avatar:
        avatar = avatar.resize((av_size, av_size), Image.Resampling.LANCZOS)
        
        # Circular Mask
        mask = Image.new('L', (av_size, av_size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, av_size, av_size), fill=255)
        
        # Center Position (Floating above panel)
        av_x = (W - av_size) // 2
        av_y = panel_y - (av_size // 2) + 40 
        
        # Drop Shadow for Avatar
        shadow = Image.new('RGBA', (av_size, av_size), (0,0,0,0))
        ImageDraw.Draw(shadow).ellipse((10, 10, av_size-10, av_size-10), fill=(0,0,0,60))
        shadow = shadow.filter(ImageFilter.GaussianBlur(15))
        img.paste(shadow, (av_x, av_y+10), shadow)
        
        # Paste Avatar
        img.paste(avatar, (av_x, av_y), mask)
        
        # Avatar Border Ring
        d.ellipse([av_x, av_y, av_x+av_size, av_y+av_size], outline=accent, width=8)

    # 6. Typography
    cx = W // 2
    
    # "Welcome" Label
    utils.write_text(d, (cx, panel_y + 220), "WELCOME", size=50, align="center", col="#CCCCCC")
    
    # Username (Big)
    # Using 'shadow=True' for depth
    utils.write_text(d, (cx, panel_y + 280), username.upper(), size=85, align="center", col="white", shadow=True)
    
    # Room Name
    clean_room = room_name.replace("-", " ").title()
    utils.write_text(d, (cx, panel_y + 390), f"to {clean_room}", size=40, align="center", col=accent)

    # 7. Final Polish (Rounded Corners for the whole card)
    # Create a mask for the main image
    mask = Image.new('L', (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, W, H], radius=60, fill=255)
    final = Image.new('RGBA', (W, H), (0,0,0,0))
    final.paste(img, (0,0), mask)
    
    return final

# ==========================================
# ⚡ EVENT HANDLERS
# ==========================================

def background_process(bot, room_id, username, room_name):
    """Runs in background thread to prevent lag"""
    try:
        # Generate
        img = render_card(username, room_name)
        
        # Upload
        # Uses utils.upload which handles the API interaction
        url = utils.upload(bot, img)
        
        if url:
            # Send to room
            bot.send_json({
                "handler": "chatroommessage",
                "roomid": room_id,
                "type": "image",
                "url": url,
                "text": f"Welcome @{username}!"
            })
        else:
            print("[Welcome] Upload failed.")
            
    except Exception as e:
        print(f"[Welcome] Generation Error: {e}")

# 1. USER JOIN LISTENER
def handle_system_message(bot, data):
    """Detects when a user joins"""
    
    # CHECK TOGGLE FIRST
    if not WELCOME_CARD_ENABLED:
        return

    try:
        handler = data.get("handler")
        
        if handler == "userjoin":
            username = data.get("username")
            room_id = data.get("roomid")
            
            # Ignore self
            if username == bot.user_data.get('username'): return
            
            # Resolve Room Name
            room_name = bot.room_id_to_name_map.get(room_id, "The Chat")
            
            print(f"[Welcome] User {username} joined. Generating card...")
            
            # Run in background (Non-blocking)
            utils.run_in_bg(background_process, bot, room_id, username, room_name)
            
    except Exception as e:
        print(f"[Welcome] Event Error: {e}")

# 2. COMMAND LISTENER (Toggle)
def handle_command(bot, command, room_id, user, args, data):
    """Allows admins to turn welcome cards on/off"""
    global WELCOME_CARD_ENABLED
    
    cmd = command.lower().strip()
    
    if cmd == "welcome":
        # Security: You might want to add Admin check here
        # if user not in admins: return
        
        if not args:
            status = "ON" if WELCOME_CARD_ENABLED else "OFF"
            bot.send_message(room_id, f"👋 Welcome Cards are currently **{status}**.")
            return True
            
        action = args[0].lower()
        
        if action == "on":
            WELCOME_CARD_ENABLED = True
            bot.send_message(room_id, "✅ **Welcome Cards Enabled!**")
        elif action == "off":
            WELCOME_CARD_ENABLED = False
            bot.send_message(room_id, "🔕 **Welcome Cards Disabled.**")
        
        return True
        
    return False
