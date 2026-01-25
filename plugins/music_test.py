import threading
import time
import requests
import uuid

# --- GLOBALS ---
BOT_INSTANCE = None

def setup(bot):
    global BOT_INSTANCE
    BOT_INSTANCE = bot
    print("[MusicTest] Updated Robust Tester Loaded.")

def upload_to_howdies(bot, audio_bytes):
    """
    Howdies API 500 Error Fix:
    1. Short Filename
    2. String conversion for IDs
    3. Multiple parameter checks
    """
    try:
        url = "https://api.howdies.app/api/upload"
        
        # 1. Filename ko ekdam simple rakhte hain (Crash se bachne ke liye)
        short_name = f"track_{int(time.time())}.mp3"
        
        # 2. File Payload
        files = {'file': (short_name, audio_bytes, 'audio/mpeg')}
        
        # 3. Data Payload (Dhyan se: UserID docs me capital tha, wahi use kar rahe hain)
        # Hum ise string me convert kar rahe hain taaki server ko problem na ho
        payload = {
            'token': str(bot.token),
            'uploadType': 'audio', 
            'UserID': str(bot.user_id) 
        }
        
        print(f"[Test] Uploading to {url} | UserID: {bot.user_id}")
        
        # 60s timeout
        r = requests.post(url, files=files, data=payload, timeout=60)
        
        if r.status_code == 200:
            res = r.json()
            # Howdies URL fetch logic
            url_res = res.get('url') or res.get('data', {}).get('url')
            if url_res:
                return url_res
        
        return f"ERROR: Status {r.status_code} - {r.text}"
    except Exception as e:
        return f"ERROR: Exception - {str(e)}"

def dropbox_processor(bot, room_id, url):
    try:
        bot.send_message(room_id, "🔍 **Test Restarted...**")
        
        # 1. Download
        bot.send_message(room_id, "📥 Downloading from Dropbox...")
        # Direct URL conversion
        final_url = url.replace("dl=0", "dl=1")
        resp = requests.get(final_url, timeout=60)
        
        if resp.status_code != 200:
            bot.send_message(room_id, f"❌ Dropbox link error: {resp.status_code}")
            return
            
        audio_content = resp.content
        bot.send_message(room_id, f"✅ Downloaded {len(audio_content)} bytes.")

        # 2. Upload
        bot.send_message(room_id, "📤 Uploading to Howdies (Clean Mode)...")
        upload_result = upload_to_howdies(bot, audio_content)
        
        if "ERROR" in str(upload_result):
            bot.send_message(room_id, f"⚠️ **Server Error 500?**\nTrying lowercase 'userid' fallback...")
            
            # FALLBACK: Try with lowercase 'userid'
            files = {'file': ('test.mp3', audio_content, 'audio/mpeg')}
            payload_fallback = {
                'token': str(bot.token),
                'uploadType': 'audio',
                'userid': str(bot.user_id) # Lowercase
            }
            r2 = requests.post("https://api.howdies.app/api/upload", files=files, data=payload_fallback, timeout=60)
            
            if r2.status_code == 200:
                upload_result = r2.json().get('url') or r2.json().get('data', {}).get('url')
            else:
                bot.send_message(room_id, f"❌ Both attempts failed.\nResponse 1: {upload_result}\nResponse 2: {r2.text}")
                return

        bot.send_message(room_id, "✅ **Success!** Link generated.")

        # 3. Final Audio Packet
        rid = int(room_id)
        msg_id = int(time.time() * 1000000)

        bot.send_json({
            "handler": "chatroommessage",
            "id": msg_id,
            "type": "audio",
            "roomid": rid,
            "url": upload_result,
            "length": "240" # Fixed length for test
        })
        
        bot.send_message(room_id, f"🎵 Player sent!\nURL: {upload_result}")

    except Exception as e:
        bot.send_message(room_id, f"⚠️ Fatal Test Error: {str(e)}")

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    if cmd == "testup":
        target_url = args[0] if args else ""
        if not target_url:
            bot.send_message(room_id, "Usage: `!testup <link>`")
            return True
        threading.Thread(target=dropbox_processor, args=(bot, room_id, target_url), daemon=True).start()
        return True
    return False
