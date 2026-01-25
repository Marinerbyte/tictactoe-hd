import os
import threading
import time
import requests
import re
import urllib.parse
import uuid

# --- GLOBALS ---
BOT_INSTANCE = None

def setup(bot):
    global BOT_INSTANCE
    BOT_INSTANCE = bot
    print("[Music] Audio-Type Engine Loaded.")

# ==========================================
# 🎵 THE SCRAPER ENGINE (YouTube Scraper)
# ==========================================

def get_youtube_info(query):
    try:
        search_query = urllib.parse.quote(query)
        url = f"https://www.youtube.com/results?search_query={search_query}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10).text
        
        video_id_match = re.search(r"watch\?v=(\S{11})", response)
        title_match = re.search(r'\"title\":\{\"runs\":\[\{\"text\":\"(.*?)\"\}', response)
        
        if video_id_match and title_match:
            return {
                "id": video_id_match.group(1),
                "title": title_match.group(1)
            }
    except Exception as e:
        print(f"[Music Search Error]: {e}")
    return None

# ==========================================
# 📨 COMMAND HANDLER
# ==========================================

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    
    if cmd in ["p", "play"]:
        if not args:
            bot.send_message(room_id, "❌ Usage: `!p song name`")
            return True
            
        query = " ".join(args)
        bot.send_message(room_id, f"🔎 Searching: **{query}**...")
        
        song = get_youtube_info(query)
        
        if not song:
            bot.send_message(room_id, "❌ Gaana nahi mila.")
            return True

        # --- THE MAGIC PAYLOAD (Logs ke hisaab se) ---
        video_id = song['id']
        # Hum streaming link use kar rahe hain
        stream_url = f"https://api.vevioz.com/@api/button/mp3/{video_id}"
        thumbnail_url = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

        # 1. Pehle Thumbnail bhejo (Jaise doosra bot bhejta hai)
        bot.send_json({
            "handler": "chatroommessage",
            "id": uuid.uuid4().hex,
            "type": "image",
            "roomid": room_id,
            "url": thumbnail_url,
            "text": f"🎶 {song['title']}"
        })

        # 2. Ab asli Audio Player bhejo
        # Type: audio, URL: stream link, Length: 300 (standard 5 mins)
        audio_payload = {
            "handler": "chatroommessage",
            "id": uuid.uuid4().hex,
            "type": "audio",
            "roomid": room_id,
            "url": stream_url,
            "length": "300",  # Duration in seconds
            "text": ""        # Audio type mein text khali rakhte hain
        }
        
        bot.send_json(audio_payload)
        
        # 3. Last mein details bhej do
        bot.send_message(room_id, f"✅ **Now Playing:** {song['title']}\n📤 Use `!stop` to end session.")
        
        print(f"[Music] Audio packet sent for: {song['title']}")
        return True

    if cmd == "stop":
        bot.send_message(room_id, "⏹️ Music stopped.")
        return True
        
    return False
