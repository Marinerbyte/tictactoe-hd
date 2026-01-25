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
    print("[Music] Stable Audio Engine Loaded.")

# ==========================================
# 🎵 THE SCRAPER ENGINE
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
            bot.send_message(room_id, "❌ Usage: `!p gaane ka naam`")
            return True
            
        query = " ".join(args)
        bot.send_message(room_id, f"🔎 Searching: **{query}**...")
        
        song = get_youtube_info(query)
        
        if not song:
            bot.send_message(room_id, "❌ Gaana nahi mila.")
            return True

        # --- THE STABLE PAYLOAD ---
        video_id = song['id']
        # Try a direct MP3 link format
        stream_url = f"https://api.vevioz.com/@api/button/mp3/{video_id}"
        thumbnail_url = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

        try:
            # 1. Sirf 1st Message: Thumbnail (Image)
            # Room ID ko integer me convert karna zaroori hai
            rid = int(room_id) if str(room_id).isdigit() else room_id
            
            bot.send_json({
                "handler": "chatroommessage",
                "id": uuid.uuid4().hex,
                "type": "image",
                "roomid": rid,
                "url": thumbnail_url,
                "text": f"🎶 Now Playing: {song['title']}"
            })

            # WAIT: Server ko saans lene do (Spam prevention)
            time.sleep(1.5)

            # 2. 2nd Message: Audio Player
            # Hum bilkul wahi format use karenge jo log me tha
            audio_payload = {
                "handler": "chatroommessage",
                "id": uuid.uuid4().hex,
                "type": "audio",
                "roomid": rid,
                "url": stream_url,
                "length": "300"
            }
            
            bot.send_json(audio_payload)
            print(f"[Music] Audio packet sent safely for: {song['title']}")

        except Exception as e:
            print(f"[Music Payload Error]: {e}")
            bot.send_message(room_id, "⚠️ Error sending player.")

        return True

    if cmd == "stop":
        bot.send_message(room_id, "⏹️ Session ended.")
        return True
        
    return False
