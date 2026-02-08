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
        # Draw background with slightly more opacity for cleaner look
        draw.rounded_rectangle([x, y, x+w, y+h], radius=40, fill=(0, 0, 0, 120))
        # Add a subtle inner glow/highlight at the top for 3D glass effect
        draw.rounded_rectangle([x, y, x+w, y+h], radius=40, outline=(255, 255, 255, 80), width=2)
        
    @staticmethod
    def add_soft_shadow(image, radius=20, offset=(0,0), opacity=100):
        """Adds a soft shadow to an image"""
        shadow = Image.new('RGBA', image.size, (0,0,0,0))
        # Create shadow mask from image alpha channel
        if image.mode == 'RGBA':
            alpha = image.split()[3]
            shadow.paste((0,0,0,opacity), (0,0), mask=alpha)
        else:
            shadow.paste((0,0,0,opacity), (0,0))
            
        shadow = shadow.filter(ImageFilter.GaussianBlur(radius))
        
        # Create a larger canvas to hold shadow + offset
        w, h = image.size
        canvas = Image.new('RGBA', (w + abs(offset[0]) + radius*2, h + abs(offset[1]) + radius*2), (0,0,0,0))
        
        # Paste shadow with offset
        canvas.paste(shadow, (radius + offset[0], radius + offset[1]))
        return canvas

# ==========================================
# 🖼️ CARD GENERATOR
# ==========================================

def render_card(username, room_name, avatar_url):
    W, H = CARD_SIZE, CARD_SIZE
    theme = random.choice(PALETTES)
    c1, c2, accent, txt_col = theme
    
    # 1. Background (High Quality Gradient)
    img = DesignEngine.get_gradient(W, H, c1, c2)
    d = ImageDraw.Draw(img, 'RGBA')
    
    # 2. Random Decor (Softer, more premium look)
    for _ in range(8):
        size = random.randint(80, 400)
        x, y = random.randint(-50, W+50), random.randint(-50, H+50)
        # Use elliptical gradient or soft shape
        overlay = Image.new('RGBA', (size, size), (0,0,0,0))
        draw_overlay = ImageDraw.Draw(overlay)
        draw_overlay.ellipse([0, 0, size, size], fill=(255, 255, 255, 15))
        # Blur the decor for depth
        overlay = overlay.filter(ImageFilter.GaussianBlur(20))
        img.paste(overlay, (x, y), overlay)
    
    # 3. Glass Panel (Modernized)
    panel_h = 420
    panel_y = H - panel_h - 80
    DesignEngine.draw_glass_panel(d, 60, panel_y, W-120, panel_h)
    
    # 4. DP Processing (Enhanced 3D Avatar)
    # Increased size significantly for visual dominance
    av_size = 580 
    avatar = DesignEngine.get_user_dp(avatar_url, username)
    
    if avatar:
        # High quality resize
        avatar = avatar.resize((av_size, av_size), Image.Resampling.LANCZOS)
        
        # Sharpen facial details
        avatar = avatar.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
        
        # Circle Mask for DP
        mask = Image.new('L', (av_size, av_size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, av_size, av_size), fill=255)
        
        # Calculate Position (Center, overlapping top of panel slightly)
        av_x = (W - av_size) // 2
        # Move up to create overlap/pop-out effect
        av_y = panel_y - (av_size // 2) + 60 
        
        # Multi-layered shadow for 3D depth
        # Layer 1: Sharp, close shadow (Ambient Occlusion)
        shadow1 = Image.new('RGBA', (av_size, av_size), (0,0,0,0))
        ImageDraw.Draw(shadow1).ellipse((10, 10, av_size-10, av_size-10), fill=(0,0,0,120))
        shadow1 = shadow1.filter(ImageFilter.GaussianBlur(10))
        img.paste(shadow1, (av_x, av_y+5), shadow1)
        
        # Layer 2: Soft, wide drop shadow
        shadow2 = Image.new('RGBA', (av_size, av_size), (0,0,0,0))
        ImageDraw.Draw(shadow2).ellipse((20, 20, av_size-20, av_size-20), fill=(0,0,0,60))
        shadow2 = shadow2.filter(ImageFilter.GaussianBlur(30))
        img.paste(shadow2, (av_x, av_y+15), shadow2)
        
        # Paste DP
        img.paste(avatar, (av_x, av_y), mask)
        
        # Add a subtle rim light/glow border
        ring = Image.new('RGBA', (av_size, av_size), (0,0,0,0))
        ring_draw = ImageDraw.Draw(ring)
        ring_draw.ellipse([0, 0, av_size, av_size], outline=accent, width=8)
        # Blur ring slightly for "glow" effect
        ring = ring.filter(ImageFilter.GaussianBlur(1))
        img.paste(ring, (av_x, av_y), ring)

    # 5. Text (Balanced Layout)
    cx = W // 2
    # "WELCOME" - Clean, spaced out
    utils.write_text(d, (cx, panel_y + 200), "WELCOME", size=45, align="center", col="#DDDDDD", font_path=None) # Assume default font or add param if available
    
    # USERNAME - Large, bold, with drop shadow
    username_y = panel_y + 270
    # Text shadow
    utils.write_text(d, (cx+3, username_y+3), username.upper(), size=85, align="center", col="#000000AA")
    # Main text
    utils.write_text(d, (cx, username_y), username.upper(), size=85, align="center", col="white")
    
    # "to Room Name" - Accent color
    utils.write_text(d, (cx, panel_y + 370), f"to {room_name}", size=40, align="center", col=accent)

    # 6. Smooth Round Corners & Vignette
    # Add subtle vignette for focus
    vignette = Image.new('RGBA', (W, H), (0,0,0,0))
    # Simple radial gradient simulation for vignette could go here, skipping for performance/simplicity
    
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
            
