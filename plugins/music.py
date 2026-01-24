import os
import threading
import time
import requests
import re
import urllib.parse

# --- GLOBALS ---
music_state = {}
lock = threading.Lock()
BOT_INSTANCE = None

def setup(bot):
    global BOT_INSTANCE
    BOT_INSTANCE = bot
    print("[Music] Anti-Block Engine Loaded.")

# ==========================================
# 🎵 THE SCRAPER ENGINE (Direct Search)
# ==========================================

def get_youtube_data(query):
    """YouTube se Video ID aur Title nikaalta hai bina block hue"""
    try:
        search_query = urllib.parse.quote(query)
        url = f"https://www.youtube.com/results?search_query={search_query}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        
        response = requests.get(url, headers=headers, timeout=10).text
        
        # Regex se Video ID nikaalna
        video_ids = re.findall(r"watch\?v=(\S{11})", response)
        # Regex se Title nikaalna
        titles = re.findall(r'"title":\{"runs":\[\{"text":"(.*?)"\}', response)
        
        if video_ids and titles:
            return {
                "id": video_ids[0],
                "title": titles[0]
            }
    except Exception as e:
        print(f"[Music] Search Error: {e}")
    return None

# ==========================================
# 📨 HANDLER (Instant Streaming)
# ==========================================

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    
    if cmd in ["p", "play"]:
        if not args:
            bot.send_message(room_id, "Usage: !p gaane ka naam")
            return True
            
        query = " ".join(args)
        bot.send_message(room_id, f"🔎 Searching for: **{query}**...")
        
        song = get_youtube_data(query)
        
        if not song:
            bot.send_message(room_id, "❌ Gaana nahi mila ya server busy hai.")
            return True

        # --- THE MAGIC LINK (Third Party Converter) ---
        # Hum gaana download nahi karenge, hum converter ka link as an audio source bhejenge
        # Isse Render ka net use nahi hoga aur gaana 1 second me bajega
        video_id = song['id']
        stream_url = f"https://api.vevioz.com/@api/button/mp3/{video_id}"
        
        # Howdies Audio Player HTML
        # Style tag use kiya hai taaki player poora dikhe
        player_html = f"<audio src='{stream_url}' controls autoplay style='width:100%; border-radius:10px;'></audio>"
        
        bot.send_message(room_id, f"🎶 **{song['title']}**\n{player_html}")
        return True

    if cmd == "stop":
        bot.send_message(room_id, "⏹️ Music cleared.")
        return True
        
    return False
