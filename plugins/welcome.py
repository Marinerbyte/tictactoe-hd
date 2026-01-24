import io
import random
import uuid
import math
import requests
import threading
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

# --- IMPORTS ---
try: import utils
except: pass

# --- CONFIG ---
WELCOME_ENABLED = True
GIF_ENABLED = False # Default Off rakha hai, command se ON kar lena (!welcome gif on)

# Themes (Clean Gradients)
THEMES = [
    ("#0f0c29", "#302b63", "#00d2ff"), # Cyberpunk
    ("#11998e", "#38ef7d", "#ffffff"), # Nature
    ("#FF416C", "#FF4B2B", "#FFD700"), # Sunset
    ("#000000", "#434343", "#F1C40F"), # Luxury Gold
    ("#2C3E50", "#4CA1AF", "#FFFFFF"), # Corporate
]

def setup(bot):
    print("[Welcome] Stable Engine Loaded.")

# ==========================================
# 🎨 GRAPHICS ENGINE (Clean & Premium)
# ==========================================

def get_avatar(username):
    """Fetch Avatar with Retry"""
    try:
        seed = f"{username}{random.randint(1,999)}"
        url = f"https://api.dicebear.com/9.x/adventurer/png?seed={seed}&size=512&backgroundColor=transparent"
        r = requests.get(url, timeout=3)
        if r.status_code == 200:
            return Image.open(io.BytesIO(r.content)).convert("RGBA")
    except: pass
    return None

def create_base_card(username, room_name, theme):
    """Creates the base image without animation"""
    W, H = 800, 800
    c1, c2, accent = theme
    
    # 1. Gradient Background
    base = Image.new('RGB', (W, H), c1)
    top = Image.new('RGB', (W, H), c2)
    mask = Image.new('L', (W, H))
    mask_data = []
    for y in range(H): mask_data.extend([int(255 * (y / H))] * W)
    mask.putdata(mask_data)
    base.paste(top, (0, 0), mask)
    img = base.convert("RGBA")
    
    # 2. Glass Panel (Bottom)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([50, 450, 750, 750], radius=30, fill=(0,0,0, 100))
    d.rounded_rectangle([50, 450, 750, 750], radius=30, outline=accent, width=2)
    
    # 3. Avatar Placeholder
    av = get_avatar(username)
    if av:
        av = av.resize((350, 350))
        # Shadow
        d.ellipse([225+10, 80+10, 225+350+10, 80+350+10], fill=(0,0,0,80))
        # Avatar
        img.paste(av, (225, 80), av)
        # Border
        d.ellipse([225, 80, 225+350, 80+350], outline=accent, width=5)
        
    # 4. Text
    try: font_lg = ImageFont.truetype("arial.ttf", 60)
    except: font_lg = ImageFont.load_default()
    try: font_sm = ImageFont.truetype("arial.ttf", 30)
    except: font_sm = ImageFont.load_default()
    
    # Helper for center text
    def draw_text(text, y, font, color):
        try: w = font.getlength(text)
        except: w = len(text) * 15
        d.text(((W-w)/2, y), text, font=font, fill=color)

    draw_text("WELCOME", 500, font_sm, "#CCC")
    draw_text(username.upper(), 560, font_lg, "white")
    draw_text(f"to {room_name}", 660, font_sm, accent)
    
    return img

def create_gif_frames(base_img, theme):
    """Adds lightweight particle effect"""
    frames = []
    W, H = base_img.size
    accent_hex = theme[2]
    # Hex to RGB
    accent = tuple(int(accent_hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
    
    particles = []
    # Create random particles
    for _ in range(30):
        particles.append({
            'x': 400, 'y': 250, # Center of avatar
            'vx': random.uniform(-10, 10),
            'vy': random.uniform(-10, 10),
            'life': 255,
            'size': random.randint(4, 10)
        })
        
    # Generate 12 Frames (Short & Fast)
    for _ in range(12):
        frame = base_img.copy()
        d = ImageDraw.Draw(frame)
        
        for p in particles:
            p['x'] += p['vx']
            p['y'] += p['vy']
            p['life'] -= 20
            
            if p['life'] > 0:
                fill = accent + (int(p['life']),)
                d.ellipse([p['x'], p['y'], p['x']+p['size'], p['y']+p['size']], fill=fill)
        
        frames.append(frame)
        
    return frames

# ==========================================
# ⚡ UPLOAD ENGINE
# ==========================================

def upload_media(bot, data_bytes, ext):
    try:
        url = "https://api.howdies.app/api/upload"
        mime = 'image/gif' if ext == 'gif' else 'image/png'
        files = {'file': (f'welcome.{ext}', data_bytes, mime)}
        form_data = {'token': bot.token, 'uploadType': 'image', 'UserID': bot.user_id or 0}
        
        r = requests.post(url, files=files, data=form_data, timeout=60)
        if r.status_code == 200:
            return r.json().get('url') or r.json().get('data', {}).get('url')
    except Exception as e:
        print(f"[Welcome] Upload Error: {e}")
    return None

def process_card(bot, room_id, username, room_name):
    try:
        theme = random.choice(THEMES)
        img = create_base_card(username, room_name, theme)
        
        final_bytes = None
        ext = "png"
        
        # Try GIF if enabled
        if GIF_ENABLED:
            try:
                frames = create_gif_frames(img, theme)
                out = io.BytesIO()
                frames[0].save(out, format='GIF', save_all=True, append_images=frames[1:], duration=80, loop=0, transparency=0, disposal=2)
                final_bytes = out.getvalue()
                ext = "gif"
            except:
                print("[Welcome] GIF Generation Failed. Falling back to PNG.")
                ext = "png"
        
        # Fallback / Static Mode
        if ext == "png":
            out = io.BytesIO()
            img.save(out, format='PNG')
            final_bytes = out.getvalue()
            
        # Upload
        link = upload_media(bot, final_bytes, ext)
        
        if link:
            bot.send_json({
                "handler": "chatroommessage",
                "roomid": room_id,
                "type": "image",
                "url": link,
                "text": f"Welcome @{username}"
            })
            
    except Exception as e:
        print(f"[Welcome] Critical Error: {e}")

# ==========================================
# 📨 HANDLERS
# ==========================================

def handle_system_message(bot, data):
    if not WELCOME_ENABLED: return
    if data.get("handler") == "userjoin":
        u = data.get("username")
        rid = data.get("roomid")
        if u == bot.user_data.get('username'): return
        rname = bot.room_id_to_name_map.get(rid, "Room")
        
        # Background Run
        threading.Thread(target=process_card, args=(bot, rid, u, rname), daemon=True).start()

def handle_command(bot, command, room_id, user, args, data):
    global WELCOME_ENABLED, GIF_ENABLED
    cmd = command.lower().strip()
    
    if cmd == "welcome":
        if not args:
            bot.send_message(room_id, f"Cards: {WELCOME_ENABLED} | GIF: {GIF_ENABLED}")
            return True
            
        arg = args[0].lower()
        if arg == "on":
            WELCOME_ENABLED = True
            bot.send_message(room_id, "✅ Welcome Cards ON")
        elif arg == "off":
            WELCOME_ENABLED = False
            bot.send_message(room_id, "❌ Welcome Cards OFF")
        elif arg == "gif":
            if len(args) > 1 and args[1] == "on":
                GIF_ENABLED = True
                bot.send_message(room_id, "✨ GIF Mode ON")
            else:
                GIF_ENABLED = False
                bot.send_message(room_id, "🖼️ Static Mode ON")
        elif arg == "test":
            bot.send_message(room_id, "🎨 Generating Test Card...")
            threading.Thread(target=process_card, args=(bot, room_id, user, "Test Room"), daemon=True).start()
            
        return True
    return False
