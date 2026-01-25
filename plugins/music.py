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
    print("[Music] Mirror Engine Ready.")

# ==========================================
# 🎵 THE SCRAPER ENGINE
# ==========================================

def get_youtube_info(query):
    try:
        search_query = urllib.parse.quote(query)
        url = f"https://www.youtube.com/results?search_query={search_query}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10).text
        
        v_id = re.search(r"watch\?v=(\S{11})", response)
        t_id = re.search(r'\"title\":\{\"runs\":\[\{\"text\":\"(.*?)\"\}', response)
        
        if v_id and t_id:
            return {"id": v_id.group(1), "title": t_id.group(1)}
    except: pass
    return None

# ==========================================
# ⚡ ASYNC SENDING (Connection Bachane ke liye)
# ==========================================

def send_audio_packet(bot, room_id, room_name, song):
    try:
        video_id = song['id']
        stream_url = f"https://api.vevioz.com/@api/button/mp3/{video_id}"
        
        # 1. ROOM ID FIX: Ensure it is an Integer
        rid = int(room_id) if str(room_id).isdigit() else room_id
        
        # 2. DATA PACKET: Exactly like the successful bot log
        audio_payload = {
            "handler": "chatroommessage",
            "id": int(time.time() * 1000), # Timestamp ID
            "type": "audio",
            "roomid": rid,
            "room": str(room_name), # Adding room name
            "url": stream_url,
            "length": "300" # String length as per log
        }
        
        # 3. SEND Thumbnail first (Spam delay 1s)
        thumbnail_url = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
        bot.send_json({
            "handler": "chatroommessage",
            "id": int(time.time() * 1000) + 1,
            "type": "image",
            "roomid": rid,
            "url": thumbnail_url,
            "text": f"🎶 {song['title']}"
        })
        
        time.sleep(1.5)

        # 4. SEND ASLI AUDIO
        bot.send_json(audio_payload)
        
        print(f"[Music] Audio packet broadcasted for {song['title']}")
        
    except Exception as e:
        print(f"[Music Error] Async Fail: {e}")

# ==========================================
# 📨 HANDLER
# ==========================================

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    
    if cmd in ["p", "play"]:
        if not args: return True
        
        query = " ".join(args)
        bot.send_message(room_id, f"🔎 Searching for **{query}**...")
        
        song = get_youtube_info(query)
        if not song:
            bot.send_message(room_id, "❌ Not found.")
            return True

        # Room name fetch karna zaroori hai payload ke liye
        room_name = "Goodness" # Default fallback
        if room_id in bot.room_id_to_name_map:
            room_name = bot.room_id_to_name_map[room_id]
        elif 'room' in data:
            room_name = data['room']

        # Heavy work moves to background thread
        threading.Thread(
            target=send_audio_packet, 
            args=(bot, room_id, room_name, song),
            daemon=True
        ).start()
        
        return True

    return False
