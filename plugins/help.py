import sys
import os
import textwrap
from PIL import ImageDraw

# --- IMPORTS ---
try: import utils
except ImportError: print("[Help] Error: utils.py not found!")

try:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from db import save_guide, get_guide, get_all_guide_names, get_all_admins
except Exception as e: print(f"DB Import Error: {e}")

def setup(bot):
    print("[Help System] Guide Plugin Loaded.")

# ==========================================
# 🎨 ARTIST SECTION
# ==========================================

def draw_help_card(game_name, description):
    """Specific Game ki Guide Card banata hai"""
    W, H = 500, 450
    # Blueprint / Tech Style Background
    img = utils.create_canvas(W, H, (25, 30, 40))
    d = ImageDraw.Draw(img)
    
    # Header
    d.rectangle([0, 0, W, 80], fill=(40, 50, 60))
    utils.write_text(d, (W//2, 40), f"GUIDE: {game_name.upper()}", size=30, align="center", col="#FFD700", shadow=True)
    
    # Body Text (Auto Wrap)
    # 35 characters per line tak text todega
    lines = textwrap.wrap(description, width=35)
    
    start_y = 110
    for line in lines:
        if start_y > H - 60: break # Agar jagah khatam ho jaye
        utils.write_text(d, (W//2, start_y), line, size=24, align="center", col="white")
        start_y += 35
        
    # Footer
    utils.write_text(d, (W//2, H-30), "Howdies Game Bot Help", size=16, align="center", col="#888")
    return img

def draw_list_card(games_list):
    """Available Games ki List Card"""
    W, H = 500, 400
    img = utils.create_canvas(W, H, (20, 20, 25))
    d = ImageDraw.Draw(img)
    
    utils.write_text(d, (W//2, 50), "📚 GAME GUIDES", size=35, align="center", col="#44FF44", shadow=True)
    utils.write_text(d, (W//2, 90), "Type !help <gamename>", size=20, align="center", col="#AAA")
    
    y = 140
    for game in games_list:
        # Button Style
        d.rounded_rectangle([100, y, 400, y+40], radius=10, fill=(50, 50, 60), outline="#777", width=1)
        utils.write_text(d, (W//2, y+20), game.upper(), size=22, align="center", col="white")
        y += 55
        
    return img

# ==========================================
# ⚙️ LOGIC
# ==========================================

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    user_id = data.get('userid', user)

    # 1. GET HELP (!help or !help mines)
    if cmd == "help":
        if not args:
            # --- Show List ---
            games = get_all_guide_names()
            if not games:
                bot.send_message(room_id, "❌ Koi guides available nahi hain.\nAdmin `!guide` use karke add karein.")
                return True
            
            link = utils.upload(bot, draw_list_card(games))
            bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Help List"})
            return True
        else:
            # --- Show Specific Game Guide ---
            game_name = args[0].lower()
            desc = get_guide(game_name)
            
            if desc:
                link = utils.upload(bot, draw_help_card(game_name, desc))
                bot.send_json({"handler": "chatroommessage", "roomid": room_id, "type": "image", "url": link, "text": "Guide"})
            else:
                bot.send_message(room_id, f"❌ '{game_name}' ki guide nahi mili.\nCheck `!help` list.")
            return True

    # 2. ADD GUIDE (!guide name description) - ADMIN ONLY
    if cmd == "guide":
        # Security Check: Bot Owner OR Database Admin
        admins = get_all_guide_names() # Just to init DB logic if needed
        db_admins = get_all_admins()
        
        is_owner = (user == bot.user_data.get('username'))
        is_admin = (str(user_id) in db_admins)
        
        if not (is_owner or is_admin):
            bot.send_message(room_id, "🚫 **Access Denied!** Sirf Admins guide add kar sakte hain.")
            return True
            
        if len(args) < 2:
            bot.send_message(room_id, "📝 **Usage:** `!guide <game> <description>`\nExample: `!guide mines Bomb se bacho aur cookies khao!`")
            return True
            
        game_name = args[0].lower()
        description = " ".join(args[1:])
        
        if save_guide(game_name, description):
            bot.send_message(room_id, f"✅ Guide saved for **{game_name}**!")
        else:
            bot.send_message(room_id, "❌ Database Error.")
            
        return True

    return False
