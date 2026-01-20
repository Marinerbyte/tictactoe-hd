import sys
import os
import random
import requests
import textwrap
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageOps, ImageChops

# --- IMPORTS ---
try: import utils
except ImportError: print("[CharPro] Error: utils.py not found!")

# --- STATE ---
# Drafts save karne ke liye taaki share kar sakein
char_drafts = {}

def setup(bot):
    print("[CharPro] God-Mode Graphic Engine Loaded.")

# ==========================================
# 🧠 ASSET INTELLIGENCE (The Source)
# ==========================================

class AssetEngine:
    """
    Yeh class alag-alag API se best character dhund kar lati hai.
    Supports: Robots, Humans, Anime, Sketch, Monsters, Aliens.
    """
    @staticmethod
    def get_avatar_url(seed, tags):
        tags = tags.lower()
        
        # 1. 🤖 ROBOTS / SCI-FI
        if any(x in tags for x in ["robot", "mech", "bot", "android", "future"]):
            if "old" in tags: return f"https://robohash.org/{seed}.png?set=set1&size=500x500" # Classic Robot
            return f"https://api.dicebear.com/9.x/bottts/png?seed={seed}&size=1024" # Modern Bot

        # 2. 👹 MONSTERS / ALIENS
        if any(x in tags for x in ["monster", "alien", "ghost", "zombie", "demon", "scary"]):
            if "alien" in tags: return f"https://robohash.org/{seed}.png?set=set2&size=500x500" # Alien
            if "head" in tags: return f"https://robohash.org/{seed}.png?set=set3&size=500x500" # Robot Head
            return f"https://api.dicebear.com/9.x/thumbs/png?seed={seed}&size=1024" # Weird Shape

        # 3. 👩 WOMAN / GIRL
        if any(x in tags for x in ["girl", "woman", "lady", "queen", "princess", "she"]):
            style = random.choice(["lorelei", "personalities", "micah"])
            return f"https://api.dicebear.com/9.x/{style}/png?seed={seed}&size=1024"

        # 4. 👨 MAN / BOY
        if any(x in tags for x in ["boy", "man", "king", "guy", "he", "hero"]):
            style = random.choice(["adventurer", "avataaars", "micah"])
            return f"https://api.dicebear.com/9.x/{style}/png?seed={seed}&size=1024"

        # 5. ✏️ ART / SKETCH
        if any(x in tags for x in ["art", "sketch", "draw", "paint", "paper"]):
            return f"https://api.dicebear.com/9.x/notionists/png?seed={seed}&size=1024"

        # 6. 😺 CUTE / ANIME
        if any(x in tags for x in ["cute", "cat", "animal", "kawaii", "chibi"]):
            return f"https://api.dicebear.com/9.x/fun-emoji/png?seed={seed}&size=1024"

        # 7. 👾 RETRO / PIXEL
        if any(x in tags for x in ["pixel", "retro", "game", "8bit"]):
            return f"https://api.dicebear.com/9.x/pixel-art/png?seed={seed}&size=1024"

        # DEFAULT RANDOMIZER (Agar kuch match na ho to surprise do)
        styles = ["adventurer", "avataaars", "bottts", "fun-emoji", "lorelei", "notionists", "open-peeps"]
        return f"https://api.dicebear.com/9.x/{random.choice(styles)}/png?seed={seed}&size=1024"

# ==========================================
# 🖌️ PILLOW FX ENGINE (Visual Magic)
# ==========================================

class FX:
    """Special Effects for Images"""
    
    @staticmethod
    def apply_glitch(img, offset=10):
        """RGB Channel Split Glitch"""
        r, g, b, a = img.split()
        r = ImageOps.colorize(r.convert("L"), (0,0,0), (255,0,0)).convert("RGBA")
        b = ImageOps.colorize(b.convert("L"), (0,0,0), (0,255,255)).convert("RGBA")
        
        # Shift channels
        final = Image.new("RGBA", img.size)
        final.paste(r, (offset, 0), r)
        final.paste(b, (-offset, 0), b)
        
        # Blend original alpha
        final.putalpha(a)
        return final

    @staticmethod
    def add_cinematic_lighting(img, color_hex):
        """Adds a gradient overlay"""
        overlay = Image.new("RGBA", img.size, (0,0,0,0))
        d = ImageDraw.Draw(overlay)
        W, H = img.size
        # Vignette
        for i in range(100):
            alpha = int(255 * (i/100))
            margin = i * 2
            d.rectangle([0,0,W,H], outline=(0,0,0,alpha), width=1)
        
        # Color Tint
        tint = Image.new("RGBA", img.size, color_hex)
        tint.putalpha(50)
        
        img = Image.alpha_composite(img, tint)
        return img

    @staticmethod
    def create_dynamic_bg(W, H, theme="dark"):
        if theme == "neon":
            colors = ["#FF00FF", "#00FFFF", "#FFFF00", "#FF4500"]
            base = (10, 5, 20)
        elif theme == "gold":
            colors = ["#FFD700", "#FFA500", "#FFFFFF"]
            base = (30, 20, 5)
        elif theme == "blood":
            colors = ["#800000", "#FF0000", "#000000"]
            base = (10, 0, 0)
        else: # Random
            colors = ["#1E90FF", "#00FA9A", "#FF69B4"]
            base = (20, 20, 25)

        img = Image.new("RGBA", (W, H), base)
        d = ImageDraw.Draw(img)
        
        # Random Splatters
        for _ in range(30):
            x = random.randint(-100, W)
            y = random.randint(-100, H)
            s = random.randint(50, 400)
            col = random.choice(colors)
            
            layer = Image.new("RGBA", (W, H), (0,0,0,0))
            ld = ImageDraw.Draw(layer)
            
            type = random.choice(["circle", "rect", "line"])
            if type == "circle": ld.ellipse([x, y, x+s, y+s], fill=col)
            elif type == "rect": ld.rectangle([x, y, x+s, y+s/2], fill=col)
            else: ld.line([x, y, x+s, y+s], fill=col, width=10)
            
            # Blur & Paste
            layer = layer.filter(ImageFilter.GaussianBlur(random.randint(20, 60)))
            # Random Opacity
            r,g,b,a = layer.split()
            a = a.point(lambda i: i * 0.3)
            layer.putalpha(a)
            
            img.paste(layer, (0,0), layer)
            
        return img

# ==========================================
# 🖼️ GENERATORS (The 4 Command Modes)
# ==========================================

# 1. STANDARD CARD (!char)
def gen_standard_card(username, desc):
    W, H = 600, 800
    img = FX.create_dynamic_bg(W, H)
    d = ImageDraw.Draw(img)
    
    # Avatar
    url = AssetEngine.get_avatar_url(username, desc)
    av = utils.get_image(url)
    if av:
        av = av.resize((550, 550))
        # Shadow
        sh = Image.new("RGBA", (550,550), (0,0,0,0))
        ImageDraw.Draw(sh).ellipse([50,450,500,500], fill=(0,0,0,100))
        sh = sh.filter(ImageFilter.GaussianBlur(20))
        img.paste(sh, (25,120), sh)
        img.paste(av, (25, 100), av)

    # Frame
    d.rectangle([20,20,W-20,H-20], outline="white", width=3)
    
    # Text Plate
    d.polygon([(0,650), (W,600), (W,H), (0,H)], fill=(0,0,0,220))
    utils.write_text(d, (W//2, 680), username.upper(), size=50, align="center", col="#00FFFF", shadow=True)
    utils.write_text(d, (W//2, 740), desc.upper()[:30], size=20, align="center", col="#FFD700")
    
    return img

# 2. WANTED POSTER (!wanted)
def gen_wanted_poster(username, reward):
    W, H = 600, 800
    # Sepia Paper Texture
    img = Image.new("RGB", (W, H), (210, 180, 140))
    d = ImageDraw.Draw(img)
    
    # Grunge noise
    noise = Image.effect_noise((W, H), 20).convert("L")
    img.paste(noise, (0,0), noise.point(lambda i: i*0.1))
    
    utils.write_text(d, (W//2, 80), "WANTED", size=90, align="center", col="#3E2723", shadow=False)
    utils.write_text(d, (W//2, 160), "DEAD OR ALIVE", size=30, align="center", col="#3E2723")
    
    # Avatar in Box
    d.rectangle([75, 200, 525, 600], outline="#3E2723", width=5)
    url = AssetEngine.get_avatar_url(username, "western") # Use generic or adventurous
    av = utils.get_image(url)
    if av:
        av = av.resize((440, 390))
        av = av.convert("L").convert("RGBA") # Black and white
        av = ImageOps.colorize(av.convert("L"), (50,30,10), (210,180,140)).convert("RGBA") # Sepia Tint
        img.paste(av, (80, 205), av)

    utils.write_text(d, (W//2, 650), username.upper(), size=50, align="center", col="#3E2723")
    utils.write_text(d, (W//2, 720), f"REWARD: ${reward}", size=40, align="center", col="#8B0000")
    
    return img

# 3. RPG CARD (!card)
def gen_rpg_card(username, role):
    W, H = 500, 700
    img = FX.create_dynamic_bg(W, H, "gold")
    d = ImageDraw.Draw(img)
    
    # Avatar
    url = AssetEngine.get_avatar_url(username, role)
    av = utils.get_image(url)
    if av:
        av = av.resize((400, 400))
        img.paste(av, (50, 100), av)
        
    # Stats Box
    d.rounded_rectangle([20, 500, 480, 680], radius=20, fill=(0,0,0,180), outline="gold", width=3)
    
    # Random Stats
    atk = random.randint(50, 99)
    defs = random.randint(40, 90)
    spd = random.randint(60, 100)
    
    utils.write_text(d, (W//2, 530), f"Class: {role.upper()}", size=30, align="center", col="gold")
    utils.write_text(d, (100, 600), f"⚔️ ATK: {atk}", size=24, align="left", col="#FF5555")
    utils.write_text(d, (300, 600), f"🛡️ DEF: {defs}", size=24, align="left", col="#5555FF")
    utils.write_text(d, (200, 640), f"⚡ SPD: {spd}", size=24, align="center", col="#55FF55")
    
    return img

# 4. GLITCH MODE (!glitch)
def gen_glitch_art(username):
    W, H = 500, 500
    img = Image.new("RGBA", (W, H), (10, 10, 10))
    
    # Matrix Text Effect
    d = ImageDraw.Draw(img)
    for _ in range(50):
        x, y = random.randint(0, W), random.randint(0, H)
        utils.write_text(d, (x, y), str(random.randint(0, 1)), size=20, col="#00FF00")
        
    url = AssetEngine.get_avatar_url(username, "bot")
    av = utils.get_image(url)
    if av:
        av = av.resize((400, 400))
        av = FX.apply_glitch(av, offset=15) # Apply Glitch FX
        img.paste(av, (50, 50), av)
        
    utils.write_text(d, (W//2, 450), "SYSTEM FAILURE", size=40, align="center", col="red", shadow=True)
    return img

# ==========================================
# ⚙️ HANDLER (4 Modes)
# ==========================================

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    user_id = data.get('userid', user)
    
    target = user
    desc = "Hero"
    if args: 
        target = args[0].replace("@", "")
        if len(args) > 1: desc = " ".join(args[1:])

    # 1. STANDARD (!char)
    if cmd == "char":
        bot.send_message(room_id, f"🎨 **Painting:** {target} ({desc})...")
        img = gen_standard_card(target, desc)
        link = utils.upload(bot, img)
        if link:
            char_drafts[user_id] = link
            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Char"})
            bot.send_message(room_id, "✨ Type `!share @user` to gift.")
        return True

    # 2. WANTED POSTER (!wanted)
    if cmd == "wanted":
        bounty = random.randint(1000, 999999)
        bot.send_message(room_id, f"🤠 **Printing Poster:** {target}...")
        img = gen_wanted_poster(target, f"{bounty:,}")
        link = utils.upload(bot, img)
        if link:
            char_drafts[user_id] = link
            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Wanted"})
        return True

    # 3. RPG CARD (!card)
    if cmd == "card":
        role = desc if args and len(args)>1 else "Warrior"
        bot.send_message(room_id, f"🃏 **Forging Card:** {target} ({role})...")
        img = gen_rpg_card(target, role)
        link = utils.upload(bot, img)
        if link:
            char_drafts[user_id] = link
            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "RPG"})
        return True

    # 4. GLITCH (!glitch)
    if cmd == "glitch":
        bot.send_message(room_id, f"👾 **Hacking System:** {target}...")
        img = gen_glitch_art(target)
        link = utils.upload(bot, img)
        if link:
            char_drafts[user_id] = link
            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Glitch"})
        return True

    # 5. SHARE (!share)
    if cmd == "share":
        if user_id in char_drafts:
            if not args: return False
            to_user = args[0].replace("@", "")
            link = char_drafts[user_id]
            bot.send_dm_image(to_user, link, f"🎁 **Special Gift from @{user}!**")
            bot.send_message(room_id, f"✅ Sent to @{to_user}!")
            return True
        return False

    return False
