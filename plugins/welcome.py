import io
import random
import uuid
import requests
import time
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps, ImageChuckles

# --- IMPORTS ---
try: 
    import utils 
except ImportError: 
    print("[Welcome] Warning: utils.py not found. Uploads will fail.")

# ==========================================
# ⚙️ CONFIGURATION & TOGGLE
# ==========================================

WELCOME_CARD_ENABLED = True 

CARD_SIZE = 1024
FALLBACK_AVATAR = "https://api.dicebear.com/9.x/adventurer/png?seed={}&backgroundColor=transparent&size=512"

# MODERN COLOR PALETTES (Bg1, Bg2, Accent, TextColor)
PALETTES = [
    ("#2E3192", "#1BFFFF", "#FFFFFF", "white"),
    ("#D4145A", "#FBB03B", "#FFD700", "white"),
    ("#009245", "#FCEE21", "#004d00", "white"),
    ("#662D8C", "#ED1E79", "#E0E0E0", "white"),
    ("#12c2e9", "#c471ed", "#ffffff", "white"),
    ("#000000", "#434343", "#F1C40F", "white"),
    ("#FF416C", "#FF4B2B", "#FFCBCB", "white"),
]

def setup(bot):
    print("[Welcome] Plugin Loaded → Using real user avatars")

# ==========================================
# 🎨 GRAPHICS ENGINE
# ==========================================

class DesignEngine:
    
    @staticmethod
    def get_gradient(w, h, c1, c2):
        base = Image.new('RGB', (w, h), c1)
        top = Image.new('RGB', (w, h), c2)
        mask = Image.new('L', (w, h))
        mask_data = [int(255 * (y / h)) for y in range(h) for _ in range(w)]
        mask.putdata(mask_data)
        base.paste(top, (0, 0), mask)
        return base

    @staticmethod
    def add_noise(img, factor=0.04):
        w, h = img.size
        noise = Image.effect_noise((w, h), 18).convert('L')
        noise = ImageOps.colorize(noise, black="black", white="white").convert('RGBA')
        noise.putalpha(int(255 * factor))
        return Image.alpha_composite(img.convert('RGBA'), noise)

    @staticmethod
    def get_user_avatar(username, active_users_dict):
        """
        Try to get real avatar from active_users_dict
        Format expected: active_users_dict[username.lower()] = {"avatar": "https://..."}
        """
        if not active_users_dict:
            return None
            
        key = username.lower()
        if key in active_users_dict:
            info = active_users_dict[key]
            if isinstance(info, dict) and "avatar" in info and info["avatar"]:
                url = info["avatar"]
                try:
                    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
                    r = requests.get(url, headers=headers, timeout=6)
                    if r.status_code == 200:
                        return Image.open(io.BytesIO(r.content)).convert("RGBA")
                except Exception as e:
                    print(f"[Welcome] Avatar download failed for {username}: {e}")
        return None

    @staticmethod
    def get_fallback_avatar(username):
        try:
            url = FALLBACK_AVATAR.format(username)
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                return Image.open(io.BytesIO(r.content)).convert("RGBA")
        except:
            pass
        # Ultimate fallback: blank circle
        img = Image.new("RGBA", (512, 512), (0,0,0,0))
        d = ImageDraw.Draw(img)
        d.ellipse((0,0,512,512), fill=(80,80,80,180))
        return img

    @staticmethod
    def draw_glass_panel(draw, x, y, w, h):
        draw.rounded_rectangle([x, y, x+w, y+h], radius=48, fill=(0, 0, 0, 85))
        draw.rounded_rectangle([x, y, x+w, y+h], radius=48, outline=(255,255,255,60), width=3)

    @staticmethod
    def draw_decorations(draw, w, h, accent):
        for _ in range(10):
            x = random.randint(0, w)
            y = random.randint(0, h)
            size = random.randint(40, 280)
            alpha = random.randint(8, 25)
            draw.ellipse([x, y, x+size, y+size], fill=(*ImageColor.getrgb(accent)[:3], alpha))

# ==========================================
# 🖼️ CARD GENERATOR
# ==========================================

def render_card(username, room_name, active_users=None):
    W, H = CARD_SIZE, CARD_SIZE
    
    theme = random.choice(PALETTES)
    c1, c2, accent, txt_col = theme
    
    img = DesignEngine.get_gradient(W, H, c1, c2)
    img = DesignEngine.add_noise(img)
    d = ImageDraw.Draw(img, 'RGBA')
    
    DesignEngine.draw_decorations(d, W, H, accent)
    
    # Glass panel
    panel_h = 480
    panel_y = H - panel_h - 40
    panel_x = 60
    panel_w = W - 120
    DesignEngine.draw_glass_panel(d, panel_x, panel_y, panel_w, panel_h)
    
    # ── Avatar ───────────────────────────────────────
    av_size = 420
    
    avatar = DesignEngine.get_user_avatar(username, active_users)
    
    if not avatar:
        avatar = DesignEngine.get_fallback_avatar(username)
    
    avatar = avatar.resize((av_size, av_size), Image.Resampling.LANCZOS)
    
    # Circular mask
    mask = Image.new('L', (av_size, av_size), 0)
    ImageDraw.Draw(mask).ellipse((0,0,av_size,av_size), fill=255)
    
    # Position
    av_x = (W - av_size) // 2
    av_y = panel_y - (av_size // 2) + 30
    
    # Shadow
    shadow = Image.new('RGBA', (av_size, av_size), (0,0,0,0))
    sd = ImageDraw.Draw(shadow)
    sd.ellipse((12,12,av_size-12,av_size-12), fill=(0,0,0,90))
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    img.paste(shadow, (av_x, av_y+12), shadow)
    
    # Paste avatar
    img.paste(avatar, (av_x, av_y), mask)
    
    # Glow / border ring
    d.ellipse([av_x-6, av_y-6, av_x+av_size+6, av_y+av_size+6], 
              outline=accent, width=10)
    
    # ── Text ─────────────────────────────────────────
    cx = W // 2
    
    utils.write_text(d, (cx, panel_y + 230), "WELCOME", size=54, align="center", col="#EEEEEE")
    utils.write_text(d, (cx, panel_y + 305), username.upper(), size=92, align="center", col="white", shadow=True)
    
    clean_room = room_name.replace("-", " ").title()
    utils.write_text(d, (cx, panel_y + 410), f"to {clean_room}", size=44, align="center", col=accent)

    # Rounded corners for whole card
    mask = Image.new('L', (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0,0,W,H], radius=64, fill=255)
    final = Image.new('RGBA', (W, H), (0,0,0,0))
    final.paste(img, (0,0), mask)
    
    return final

# ==========================================
# ⚡ EVENT HANDLERS
# ==========================================

def background_process(bot, room_id, username, room_name, active_users):
    try:
        img = render_card(username, room_name, active_users)
        url = utils.upload(bot, img)
        
        if url:
            bot.send_json({
                "handler": "chatroommessage",
                "roomid": room_id,
                "type": "image",
                "url": url,
                "text": f"Welcome @{username} 💛"
            })
        else:
            print("[Welcome] Upload failed")
            
    except Exception as e:
        print(f"[Welcome] Generation failed: {e}")

def handle_system_message(bot, data):
    if not WELCOME_CARD_ENABLED:
        return

    handler = data.get("handler")
    if handler != "userjoin":
        return

    username = data.get("username")
    room_id = data.get("roomid")
    
    # Ignore bot itself
    if username == bot.user_data.get('username'):
        return

    room_name = bot.room_id_to_name_map.get(room_id, "The Chat")
    
    print(f"[Welcome] Generating card for {username}")
    
    # Pass current active_users snapshot
    active_users_copy = getattr(bot, 'ACTIVE_USERS', {}).copy()
    
    utils.run_in_bg(background_process, bot, room_id, username, room_name, active_users_copy)

def handle_command(bot, command, room_id, user, args, data):
    global WELCOME_CARD_ENABLED
    
    cmd = command.lower().strip()
    
    if cmd == "welcome":
        if not args:
            status = "ON" if WELCOME_CARD_ENABLED else "OFF"
            bot.send_message(room_id, f"👋 Welcome Cards: **{status}**")
            return True
            
        action = args[0].lower()
        if action == "on":
            WELCOME_CARD_ENABLED = True
            bot.send_message(room_id, "✅ Welcome Cards **Enabled**")
        elif action == "off":
            WELCOME_CARD_ENABLED = False
            bot.send_message(room_id, "🔕 Welcome Cards **Disabled**")
        return True
        
    return False
