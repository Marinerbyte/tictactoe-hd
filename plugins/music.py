import os
import threading
import time
import requests
import uuid

# --- GLOBALS ---
BOT_INSTANCE = None

def setup(bot):
    global BOT_INSTANCE
    BOT_INSTANCE = bot
    print("[Music] Low-Size optimized engine loaded.")

# ==========================================
# 🎵 MUSIC SEARCH (JioSaavn Vercel API)
# ==========================================

def fetch_song_saavn(query):
    """
    Saavn se gaana search karke uska sabse chota MP3 link nikalta hai.
    """
    try:
        # Stable Vercel Mirror
        api_url = f"https://jiosaavn-api-v3.vercel.app/search/songs?query={query}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        
        response = requests.get(api_url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                song = data[0] # Pehla result
                
                # DEVELOPER TIP: 'Size zyada hoga'
                # downloadUrl[0] -> 12kbps (Extremely Small)
                # downloadUrl[1] -> 48kbps (Very Small)
                # downloadUrl[2] -> 96kbps (Small & Good Quality) <- We use this
                
                return {
                    "title": song.get('title', 'Unknown Song'),
                    "url": song['downloadUrl'][2]['url'], # 96kbps for stability
                    "duration": song.get('duration', '300'),
                    "image": song.get('image', [{}])[0].get('url', '')
                }
    except Exception as e:
        print(f"[Music API Error]: {e}")
    return None

# ==========================================
# ⚡ ASYNC SENDER (To prevent disconnects)
# ==========================================

def send_music_player(bot, room_id, song):
    try:
        rid = int(room_id)
        msg_id = int(time.time() * 1000)

        # 1. SEND THUMBNAIL (As per successful bot logs)
        if song['image']:
            bot.send_json({
                "handler": "chatroommessage",
                "id": msg_id,
                "type": "image",
                "roomid": rid,
                "url": song['image'],
                "text": f"🎶 {song['title']}"
            })
            time.sleep(1.2) # Small gap

        # 2. SEND NATIVE PLAYER (With Low-Size URL)
        audio_payload = {
            "handler": "chatroommessage",
            "id": msg_id + 1,
            "type": "audio",
            "roomid": rid,
            "url": song['url'],
            "length": str(song['duration'])
        }
        
        bot.send_json(audio_payload)
        print(f"[Music] Low-size player sent: {song['title']}")

    except Exception as e:
        print(f"[Music Error]: {e}")

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
        bot.send_message(room_id, f"🔎 Searching for **{query}**...")
        
        # Background thread me processing taaki bot freeze na ho
        def run():
            song = fetch_song_saavn(query)
            if song:
                send_music_player(bot, room_id, song)
            else:
                bot.send_message(room_id, "❌ Maafi, gaana nahi mil saka.")

        threading.Thread(target=run, daemon=True).start()
        return True

    # TEST COMMAND FOR TINY FILE
    if cmd == "tinytouch":
        tiny_url = "https://www.soundjay.com/buttons/beep-01a.mp3"
        bot.send_json({
            "handler": "chatroommessage",
            "id": int(time.time()*1000),
            "type": "audio",
            "roomid": int(room_id),
            "url": tiny_url,
            "length": "2"
        })
        bot.send_message(room_id, "Bheja! Agar bot nahi nikla toh size ka hi chakkar tha.")
        return True

    return False
