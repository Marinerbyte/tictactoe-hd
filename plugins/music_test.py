import threading
import time
import requests
import uuid

# --- GLOBALS ---
BOT_INSTANCE = None

def setup(bot):
    global BOT_INSTANCE
    BOT_INSTANCE = bot
    print("[MusicTest] Catbox Link Tester Loaded.")

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()

    # COMMAND: !testcat
    # Ye seedha catbox ka link audio player me bhejega
    if cmd == "testcat":
        try:
            # 1. Catbox MP3 Link
            catbox_url = "https://files.catbox.moe/kftu8t.mp3"
            
            # 2. Room ID (Must be Integer)
            rid = int(room_id)
            
            # 3. Message ID (16-digit timestamp style)
            msg_id = int(time.time() * 1000000)

            # 4. THUMBNAIL PEHLE (Important sequence)
            bot.send_json({
                "handler": "chatroommessage",
                "id": msg_id,
                "type": "image",
                "roomid": rid,
                "url": "https://i.ytimg.com/vi/7wtfhZwyrcc/hqdefault.jpg",
                "text": "🎵 Testing Catbox Audio Player..."
            })

            # Chota delay spam se bachne ke liye
            time.sleep(1.5)

            # 5. ASLI AUDIO PLAYER (With Catbox URL)
            # Hum isse upload nahi kar rahe, seedha link bhej rahe hain
            audio_payload = {
                "handler": "chatroommessage",
                "id": msg_id + 1,
                "type": "audio",
                "roomid": rid,
                "url": catbox_url,
                "length": "240" # Appx length
            }
            
            bot.send_json(audio_payload)
            bot.send_message(room_id, "🚀 Bhej diya! Agar player dikh gaya aur bot nahi nikla, toh domain ka chakkar nahi hai.")
            
            print(f"[MusicTest] Catbox payload sent to room {rid}")
            return True

        except Exception as e:
            bot.send_message(room_id, f"⚠️ Error: {str(e)}")
            return True

    return False
