import threading
import time
import requests
import uuid

# --- GLOBALS ---
BOT_INSTANCE = None

def setup(bot):
    global BOT_INSTANCE
    BOT_INSTANCE = bot
    print("[MusicTest] Dropbox Direct Tester Loaded.")

def upload_to_howdies(bot, audio_bytes, filename="dropbox_test.mp3"):
    """
    Howdies API Documentation ke hisaab se upload logic
    """
    try:
        url = "https://api.howdies.app/api/upload"
        # Documentation: UserID, token, uploadType
        files = {'file': (filename, audio_bytes, 'audio/mpeg')}
        data = {
            'token': bot.token,
            'uploadType': 'audio', 
            'UserID': bot.user_id # Capital U, I, D as per docs
        }
        
        print(f"[Test] Uploading {len(audio_bytes)} bytes to Howdies...")
        # 60s timeout for large files
        r = requests.post(url, files=files, data=data, timeout=60)
        
        if r.status_code == 200:
            res = r.json()
            return res.get('url') or res.get('data', {}).get('url')
        return f"ERROR: Status {r.status_code} - {r.text}"
    except Exception as e:
        return f"ERROR: {str(e)}"

def dropbox_processor(bot, room_id, url):
    try:
        bot.send_message(room_id, "🚀 **Starting Dropbox Test...**")
        
        # 1. Download from Dropbox
        bot.send_message(room_id, "📥 Downloading from Dropbox...")
        resp = requests.get(url, timeout=60)
        
        if resp.status_code != 200:
            bot.send_message(room_id, f"❌ Dropbox link failed! Status: {resp.status_code}")
            return
            
        audio_content = resp.content
        bot.send_message(room_id, f"✅ Downloaded {len(audio_content)} bytes.")

        # 2. Upload to Howdies
        bot.send_message(room_id, "📤 Uploading to Howdies native server...")
        upload_result = upload_to_howdies(bot, audio_content)
        
        if not upload_result or "ERROR" in str(upload_result):
            bot.send_message(room_id, f"❌ Howdies Upload Failed: {upload_result}")
            return

        bot.send_message(room_id, "✅ Native Link Generated!")

        # 3. Broadcast to Chat (Audio Player)
        rid = int(room_id)
        msg_id = int(time.time() * 1000000) # 16-digit style

        bot.send_json({
            "handler": "chatroommessage",
            "id": msg_id,
            "type": "audio",
            "roomid": rid,
            "url": upload_result,
            "length": "300"
        })
        
        bot.send_message(room_id, f"🎵 **SUCCESS!** Player should appear above.\nLink: {upload_result}")

    except Exception as e:
        bot.send_message(room_id, f"⚠️ Fatal Test Error: {str(e)}")

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    
    # Command: !testup <paste_your_dropbox_link>
    if cmd == "testup":
        target_url = args[0] if args else ""
        if not target_url or "dropbox.com" not in target_url:
            bot.send_message(room_id, "❌ Usage: `!testup <dropbox_link>`")
            return True
            
        threading.Thread(target=dropbox_processor, args=(bot, room_id, target_url), daemon=True).start()
        return True
        
    return False
