import threading
import time
import requests
import re
import urllib.parse
import music_utils

# --- GLOBALS ---
BOT_INSTANCE = None

def setup(bot):
    global BOT_INSTANCE
    BOT_INSTANCE = bot
    print("[Music] Multi-Route DJ Engine Ready.")

def music_processor(bot, room_id, query):
    try:
        # 1. Search (Render pe hamesha chalega)
        search_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res_text = requests.get(search_url, headers=headers, timeout=10).text
        
        vid = re.search(r"watch\?v=(\S{11})", res_text).group(1)
        title = re.search(r'\"title\":\{\"runs\":\[\{\"text\":\"(.*?)\"\}', res_text).group(1)
        
        # 2. Download (3 backup sources)
        bot.send_message(room_id, f"📥 Preparing: **{title}**...")
        audio_content = music_utils.get_audio_bytes(vid)
        
        if not audio_content:
            bot.send_message(room_id, "❌ All download servers are busy. Try later.")
            return

        # 3. Native Upload (Howdies Server)
        bot.send_message(room_id, "📤 Uploading to Howdies...")
        howdies_url = music_utils.upload_to_howdies(bot, audio_content, f"{vid}.mp3")
        
        if not howdies_url:
            bot.send_message(room_id, "❌ Howdies server rejected the song.")
            return

        # 4. Final Broadcast
        rid = int(room_id)
        msg_id = int(time.time() * 1000)
        
        # Thumbnail
        bot.send_json({
            "handler": "chatroommessage", "id": msg_id, "type": "image", "roomid": rid,
            "url": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg", "text": f"🎶 {title}"
        })
        time.sleep(1.5)
        # Audio Player
        bot.send_json({
            "handler": "chatroommessage", "id": msg_id + 1, "type": "audio", "roomid": rid,
            "url": howdies_url, "length": "300"
        })
    except Exception as e:
        print(f"[Music Error]: {e}")

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    if cmd in ["p", "play"]:
        if not args: return True
        query = " ".join(args)
        bot.send_message(room_id, f"🔎 Searching: **{query}**...")
        threading.Thread(target=music_processor, args=(bot, room_id, query), daemon=True).start()
        return True
    return False
