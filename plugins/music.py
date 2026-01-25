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
    print("[Music] Ultra-Stable Mirror Engine Loaded.")

# ==========================================
# 🎵 THE SCRAPER ENGINE (Improved)
# ==========================================

def get_youtube_info(query):
    try:
        search_query = urllib.parse.quote(query)
        url = f"https://www.youtube.com/results?search_query={search_query}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10).text
        
        v_id = re.search(r"watch\?v=(\S{11})", response)
        t_match = re.search(r'\"title\":\{\"runs\":\[\{\"text\":\"(.*?)\"\}', response)
        
        if v_id and t_match:
            return {"id": v_id.group(1), "title": t_match.group(1)}
    except: pass
    return None

# ==========================================
# ⚡ ASYNC PACKET SENDER (Server-Safe)
# ==========================================

def send_audio_packet(bot, room_id, room_name, song):
    try:
        video_id = song['id']
        
        # 1. DIRECT MP3 LINK (Bypass Vevioz Page)
        # Ye link direct MP3 stream deta hai jo Howdies ke player me chalega
        direct_mp3_url = f"https://api.vkrtool.in/youtube/v1/get?id={video_id}"
        thumbnail_url = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
        
        # 2. ROOM ID FIX: Must be pure Integer
        rid = int(room_id)
        
        # 3. ID SEQUENCE: Mimicking the log exactly
        # Log me ID 16 digits ka integer hai. Hum timestamp use karenge.
        client_msg_id = int(time.time() * 1000000)

        # STEP A: Thumbnail Message
        thumb_payload = {
            "handler": "chatroommessage",
            "id": client_msg_id,
            "type": "image",
            "roomid": rid,
            "url": thumbnail_url,
            "text": f"🎵 {song['title']}"
        }
        bot.send_json(thumb_payload)
        
        # Anti-Spam Wait (Very important)
        time.sleep(2.0)

        # STEP B: Asli Audio Message
        # Payload structure is now exactly like the successful bot
        audio_payload = {
            "handler": "chatroommessage",
            "id": client_msg_id + 1,
            "type": "audio",
            "roomid": rid,
            "url": direct_mp3_url,
            "length": "300" # Length as string per log
        }
        
        bot.send_json(audio_payload)
        print(f"[Music] Successfully broadcasted: {song['title']}")
        
    except Exception as e:
        print(f"[Music Error] Thread Crash: {e}")

# ==========================================
# 📨 COMMAND HANDLER
# ==========================================

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    
    if cmd in ["p", "play"]:
        if not args: return True
        
        query = " ".join(args)
        bot.send_message(room_id, f"🔎 Searching for **{query}**...")
        
        song = get_youtube_info(query)
        if not song:
            bot.send_message(room_id, "❌ Song not found.")
            return True

        # Room name fetch
        room_name = data.get('room') or bot.room_id_to_name_map.get(room_id, "Room")

        # Start Async Thread
        threading.Thread(
            target=send_audio_packet, 
            args=(bot, room_id, room_name, song),
            daemon=True
        ).start()
        
        return True

    return False
