import os
import threading
import time
import requests
import re
import urllib.parse
import uuid
import sys

# Naye music_utils ko import karne ke liye path set karte hain
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    import music_utils
except ImportError:
    print("[Music] music_utils.py not found in root!")

# --- GLOBALS ---
BOT_INSTANCE = None

def setup(bot):
    global BOT_INSTANCE
    BOT_INSTANCE = bot
    print("[Music] Native Engine with dedicated Utils ready.")

# ==========================================
# ⚡ BACKGROUND MUSIC PROCESSOR
# ==========================================

def process_music_task(bot, room_id, song):
    """
    Ye function alag thread me chalta hai taaki bot disconnect na ho
    """
    try:
        video_id = song['id']
        
        # 1. Gaane ke bytes mangwao
        audio_content = music_utils.get_direct_mp3_content(video_id)
        if not audio_content:
            bot.send_message(room_id, "❌ Maafi, audio server busy hai. Baad me try karein.")
            return

        # 2. Howdies par upload karo
        howdies_url = music_utils.upload_audio_to_howdies(bot, audio_content, f"{video_id}.mp3")
        if not howdies_url:
            bot.send_message(room_id, "❌ Howdies server ne gaana reject kar diya.")
            return

        # 3. Chat mein Player bhejo (Exact Mirror of successful bot)
        rid = int(room_id)
        # 16-digit ID mimic karne ke liye timestamp use karte hain
        msg_id = int(time.time() * 1000000)

        # A. Pehle Image/Thumbnail
        bot.send_json({
            "handler": "chatroommessage",
            "id": msg_id,
            "type": "image",
            "roomid": rid,
            "url": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
            "text": f"🎶 Now Playing: {song['title']}"
        })
        
        # Chota delay taaki server spam na samjhe
        time.sleep(2.0)

        # B. Phir Asli Audio Player
        bot.send_json({
            "handler": "chatroommessage",
            "id": msg_id + 1,
            "type": "audio",
            "roomid": rid,
            "url": howdies_url,
            "length": "300" # Standard length
        })
        
        print(f"[Music] Successfully played {song['title']} via native link.")

    except Exception as e:
        print(f"[Music Task Error]: {e}")

# ==========================================
# 📨 HANDLER & SEARCH
# ==========================================

def get_youtube_info(query):
    try:
        search_query = urllib.parse.quote(query)
        url = f"https://www.youtube.com/results?search_query={search_query}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=10).text
        
        v_id = re.search(r"watch\?v=(\S{11})", response)
        t_match = re.search(r'\"title\":\{\"runs\":\[\{\"text\":\"(.*?)\"\}', response)
        
        if v_id and t_match:
            return {"id": v_id.group(1), "title": t_match.group(1)}
    except: pass
    return None

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    
    if cmd in ["p", "play"]:
        if not args:
            bot.send_message(room_id, "❌ Usage: `!p song name`")
            return True
            
        query = " ".join(args)
        bot.send_message(room_id, f"🔎 Searching & Processing: **{query}**...")
        
        song = get_youtube_info(query)
        if not song:
            bot.send_message(room_id, "❌ Gaana nahi mila.")
            return True

        # Process everything in a background thread to prevent "WS Closure"
        threading.Thread(
            target=process_music_task, 
            args=(bot, room_id, song),
            daemon=True
        ).start()
        
        return True
    return False
