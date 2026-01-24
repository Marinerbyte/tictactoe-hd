import io
import os
import random
import uuid
import math
import requests
import threading
import traceback
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

# --- IMPORTS ---
try: 
    import utils 
except ImportError: 
    print("[WelcomePro] Utils not found. Uploads might fail.")

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================

# Toggles (Can be changed via !welcomepro command)
CONFIG = {
    "ENABLED": True,
    "GIF_MODE": False,  # Default OFF to save data/speed. Turn ON via command.
    "THEME_COLOR": "random" # Can be set to specific hex if needed
}

# Settings
CARD_SIZE = 1024
FONT_PATH = "arial.ttf" # Ensure this exists or fallback to default
AVATAR_API = "https://api.dicebear.com/9.x/fun-emoji/png?seed={}&size=512&backgroundColor=transparent"

# Modern Palettes (Bg1, Bg2, Accent)
PALETTES = [
    ("#141E30", "#243B55", "#00d2ff"), # Deep Sea
    ("#200122", "#6f0000", "#c70039"), # Red Velvet
    ("#000000", "#434343", "#F1C40F"), # Gold Rush
    ("#1A2980", "#26D0CE", "#26D0CE"), # Aqua
    ("#FF416C", "#FF4B2B", "#FFFFFF"), # Sunset
    ("#403B4A", "#E7E9BB", "#E7E9BB"), # Cinematic
]

def setup(bot):
    print("[WelcomePro] Premium Card Engine Loaded.")

# ==========================================
# 🎨 GRAPHICS ENGINE
# ==========================================

class CardRenderer:
    
    @staticmethod
    def get_font(size):
        try: return ImageFont.truetype(FONT_PATH, size)
        except: return ImageFont.load_default()

    @staticmethod
    def fit_text(draw, text, max_width, initial_size, color, y_pos, shadow=True):
        """Auto-scales text to fit within width"""
        size = initial_size
        font = CardRenderer.get_font(size)
        
        # Shrink until fits
        while size > 20:
            try:
                length = font.getlength(text)
            except: 
                length = len(text) * (size * 0.6) # Fallback estimation
                
            if length < max_width: break
            size -= 5
            font = CardRenderer.get_font(size)
            
        # Draw centered
        W = CARD_SIZE
        try: w = font.getlength(text)
        except: w = length
        x = (W - w) // 2
        
        if shadow:
            draw.text((x+4, y_pos+4), text, font=font, fill=(0,0,0,180))
        draw.text((x, y_pos), text, font=font, fill=color)

    @staticmethod
    def generate_background(w, h, palette):
        c1, c2, accent = palette
        
        # 1. Gradient
        base = Image.new('RGB', (w, h), c1)
        top = Image.new('RGB', (w, h), c2)
        mask = Image.new('L', (w, h))
        mask_data = []
        for y in range(h): mask_data.extend([int(255 * (y/h))] * w)
        mask.putdata(mask_data)
        base.paste(top, (0,0), mask)
        
        # 2. Abstract Patterns
        d = ImageDraw.Draw(base, 'RGBA')
        for _ in range(10):
            shape_type = random.choice(['circle', 'rect', 'line'])
            alpha_col = (255, 255, 255, 10) # Faint overlay
            
            if shape_type == 'circle':
                r = random.randint(50, 400)
                cx, cy = random.randint(0, w), random.randint(0, h)
                d.ellipse([cx-r, cy-r, cx+r, cy+r], fill=alpha_col)
            elif shape_type == 'line':
                x1, y1 = random.randint(0, w), random.randint(0, h)
                x2, y2 = random.randint(0, w), random.randint(0, h)
                d.line([x1, y1, x2, y2], fill=alpha_col, width=5)
                
        return base

    @staticmethod
    def get_avatar(username):
        try:
            # Unique seed per join
            seed = f"{username}-{uuid.uuid4().hex[:6]}"
            r = requests.get(AVATAR_API.format(seed), timeout=4)
            if r.status_code == 200:
                return Image.open(io.BytesIO(r.content)).convert("RGBA")
        except: pass
        return None

# ==========================================
# ✨ PARTICLE SYSTEM (BURST GIF)
# ==========================================

class Particle:
    def __init__(self, cx, cy, color):
        self.x, self.y = cx, cy
        angle = random.uniform(0, 6.28)
        speed = random.uniform(10, 25)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.size = random.randint(5, 15)
        self.color = color
        self.life = 1.0 # 100% opacity
        self.decay = random.uniform(0.05, 0.1)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.life -= self.decay
        self.size *= 0.95 # Shrink

    def draw(self, draw):
        if self.life > 0:
            alpha = int(255 * self.life)
            fill = self.color + (alpha,)
            draw.ellipse([self.x, self.y, self.x+self.size, self.y+self.size], fill=fill)

def generate_gif(base_img, palette):
    frames = []
    particles = []
    
    # Accent color to RGB
    hex_col = palette[2].lstrip('#')
    accent_rgb = tuple(int(hex_col[i:i+2], 16) for i in (0, 2, 4))
    
    cx, cy = CARD_SIZE//2, 300 # Center of avatar
    
    # Spawn Particles
    for _ in range(50):
        particles.append(Particle(cx, cy, accent_rgb))
        
    # Generate 15 Frames (Short Burst)
    for _ in range(15):
        frame = base_img.copy()
        d = ImageDraw.Draw(frame, 'RGBA')
        
        alive = []
        for p in particles:
            p.update()
            p.draw(d)
            if p.life > 0: alive.append(p)
        particles = alive
        
        frames.append(frame)
        
    out = io.BytesIO()
    frames[0].save(out, format='GIF', save_all=True, append_images=frames[1:], duration=60, loop=0)
    return out.getvalue()

# ==========================================
# 🖼️ MAIN RENDERER
# ==========================================

def render_card(username, room_name):
    # 1. Setup
    palette = random.choice(PALETTES)
    img = CardRenderer.generate_background(CARD_SIZE, CARD_SIZE, palette)
    d = ImageDraw.Draw(img)
    
    # 2. Avatar
    av_size = 400
    av = CardRenderer.get_avatar(username)
    cx, cy = CARD_SIZE//2, 300
    
    if av:
        av = av.resize((av_size, av_size), Image.Resampling.LANCZOS)
        
        # Shadow
        d.ellipse([cx-av_size//2+10, cy-av_size//2+10, cx+av_size//2+10, cy+av_size//2+10], fill=(0,0,0,80))
        
        # Paste
        img.paste(av, (cx-av_size//2, cy-av_size//2), av)
        
        # Border Ring
        d.ellipse([cx-av_size//2, cy-av_size//2, cx+av_size//2, cy+av_size//2], outline=palette[2], width=8)

    # 3. Text Panel (Glass)
    panel_y = 550
    d.rounded_rectangle([100, panel_y, 924, 924], radius=30, fill=(0,0,0, 120))
    d.rounded_rectangle([100, panel_y, 924, 924], radius=30, outline=palette[2], width=2)
    
    # 4. Text Content
    CardRenderer.fit_text(d, "WELCOME", 700, 60, "#CCCCCC", panel_y + 50)
    CardRenderer.fit_text(d, username.upper(), 780, 100, "white", panel_y + 130)
    CardRenderer.fit_text(d, f"to {room_name}", 700, 50, palette[2], panel_y + 260)
    
    # 5. Output
    if CONFIG["GIF_MODE"]:
        return generate_gif(img, palette), 'gif'
    else:
        out = io.BytesIO()
        img.save(out, format='PNG')
        return out.getvalue(), 'png'

# ==========================================
# ⚡ HANDLERS
# ==========================================

def upload_and_send(bot, rid, data, ext, text):
    try:
        # Use simple requests to avoid dep issues
        url = "https://api.howdies.app/api/upload"
        mime = 'image/gif' if ext == 'gif' else 'image/png'
        files = {'file': (f'welcome.{ext}', data, mime)}
        form = {'token': bot.token, 'uploadType': 'image', 'UserID': bot.user_id}
        
        r = requests.post(url, files=files, data=form, timeout=60)
        if r.status_code == 200:
            link = r.json().get('url') or r.json().get('data', {}).get('url')
            if link:
                bot.send_json({
                    "handler": "chatroommessage",
                    "roomid": rid,
                    "type": "image",
                    "url": link,
                    "text": text
                })
    except Exception as e:
        print(f"[WelcomePro] Upload Error: {e}")

def process_job(bot, rid, user, rname):
    try:
        data, ext = render_card(user, rname)
        upload_and_send(bot, rid, data, ext, f"Welcome @{user}!")
    except Exception as e:
        print(f"[WelcomePro] Render Error: {e}")
        traceback.print_exc()

def handle_system_message(bot, data):
    if not CONFIG["ENABLED"]: return
    if data.get("handler") == "userjoin":
        u = data.get("username")
        if u == bot.user_data.get('username'): return
        
        rid = data.get("roomid")
        rname = bot.room_id_to_name_map.get(rid, "Room")
        
        # Run Background
        threading.Thread(target=process_job, args=(bot, rid, u, rname), daemon=True).start()

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    if cmd == "welcomepro":
        if not args:
            s = "ON" if CONFIG["ENABLED"] else "OFF"
            g = "ON" if CONFIG["GIF_MODE"] else "OFF"
            bot.send_message(room_id, f"⚙️ **Welcome Pro:**\nCard: {s}\nGIF Burst: {g}")
            return True
            
        arg = args[0].lower()
        if arg == "on":
            CONFIG["ENABLED"] = True
            bot.send_message(room_id, "✅ Welcome Pro ON")
        elif arg == "off":
            CONFIG["ENABLED"] = False
            bot.send_message(room_id, "❌ Welcome Pro OFF")
        elif arg == "gif":
            CONFIG["GIF_MODE"] = not CONFIG["GIF_MODE"]
            st = "ON" if CONFIG["GIF_MODE"] else "OFF"
            bot.send_message(room_id, f"✨ GIF Mode: {st}")
        elif arg == "test":
            bot.send_message(room_id, "🎨 Generating Test...")
            threading.Thread(target=process_job, args=(bot, room_id, user, "Test Room"), daemon=True).start()
            
        return True
    return False
