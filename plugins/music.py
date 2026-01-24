import os
import threading
import time
import requests
import traceback
import tempfile

# --- CONFIG ---
DOWNLOAD_DIR = "music_cache"
MAX_QUEUE_SIZE = 15

try:
    import yt_dlp
    from pydub import AudioSegment
except ImportError:
    print("[Music] Error: yt-dlp or pydub missing.")

music_state = {}
lock = threading.Lock()
BOT_INSTANCE = None

def setup(bot):
    global BOT_INSTANCE
    BOT_INSTANCE = bot
    if not os.path.exists(DOWNLOAD_DIR): os.makedirs(DOWNLOAD_DIR)

# ==========================================
# 🛠️ COOKIE HELPER (Bypasses Bot Detection)
# ==========================================

def get_cookie_file():
    """Environment variable se cookies uthata hai aur temp file banata hai"""
    cookie_content = os.environ.get("YT_COOKIES")
    if cookie_content:
        # Ek temporary file banate hain jo delete nahi hogi jab tak bot chal raha hai
        tmp = tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.txt')
        tmp.write(cookie_content)
        tmp.close()
        return tmp.name
    return None

# ==========================================
# 🎵 MUSIC ENGINE
# ==========================================

def search_and_download(query):
    cookie_path = get_cookie_file()
    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(DOWNLOAD_DIR, '%(id)s.%(ext)s'),
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '128'}],
            'default_search': 'ytsearch1',
            'noplaylist': True,
            'quiet': True,
            'no_check_certificate': True,
        }

        if cookie_path:
            ydl_opts['cookiefile'] = cookie_path
            print("[Music] Using Cookies from Environment Variable.")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=True)
            if 'entries' in info and info['entries']:
                s = info['entries'][0]
                return {
                    "title": s.get('title', 'Unknown'),
                    "filepath": os.path.join(DOWNLOAD_DIR, f"{s.get('id')}.mp3"),
                    "duration": s.get('duration', 180)
                }
    except Exception as e:
        print(f"[Music Error]: {e}")
    finally:
        # Temp cookie file ko delete kar dete hain security ke liye
        if cookie_path and os.path.exists(cookie_path):
            try: os.remove(cookie_path)
            except: pass
    return None

# --- UPLOAD & PLAYER LOGIC ---

def upload_audio(filepath):
    try:
        url = "https://api.howdies.app/api/upload"
        with open(filepath, 'rb') as f:
            files = {'file': ('song.mp3', f.read(), 'audio/mpeg')}
        data = {'token': BOT_INSTANCE.token, 'uploadType': 'audio', 'UserID': BOT_INSTANCE.user_id or 0}
        r = requests.post(url, files=files, data=data, timeout=120)
        if r.status_code == 200:
            return r.json().get('url') or r.json().get('data', {}).get('url')
    except: pass
    return None

def player_thread(room_id):
    global music_state
    with lock:
        state = music_state.get(room_id)
        if not state: return
        state['is_playing'] = True

    while True:
        with lock:
            if not state['queue']:
                state['is_playing'] = False
                BOT_INSTANCE.send_message(room_id, "⏹️ Gaano ki list khatam.")
                break
            song = state['queue'].pop(0)

        BOT_INSTANCE.send_message(room_id, f"📥 Gaana taiyaar ho raha hai: **{song['title']}**...")
        url = upload_audio(song['filepath'])
        
        if os.path.exists(song['filepath']): 
            try: os.remove(song['filepath'])
            except: pass
        
        if url:
            html = f"<audio src='{url}' controls autoplay></audio>"
            BOT_INSTANCE.send_message(room_id, f"🎶 Baj raha hai: **{song['title']}**\n{html}")
            dur = song.get('duration', 180)
            for _ in range(int(dur)):
                time.sleep(1)
                with lock:
                    if not state['is_playing']: break
            if not state['is_playing']: break
        else:
            BOT_INSTANCE.send_message(room_id, "❌ Gaana upload nahi ho paya.")

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    if cmd in ["p", "play"]:
        if not args:
            bot.send_message(room_id, "Usage: `!p gaane ka naam`")
            return True
        query = " ".join(args)
        bot.send_message(room_id, f"🔎 Khoj raha hoon: **{query}**...")
        song = search_and_download(query)
        if not song:
            bot.send_message(room_id, "❌ YouTube ne block kar diya ya gaana nahi mila.")
            return True
        with lock:
            if room_id not in music_state: music_state[room_id] = {'queue': [], 'is_playing': False}
            state = music_state[room_id]
            state['queue'].append(song)
            bot.send_message(room_id, f"✅ List mein joda gaya: {song['title']}")
            if not state['is_playing']:
                threading.Thread(target=player_thread, args=(room_id,), daemon=True).start()
        return True
    if cmd == "stop":
        with lock:
            if room_id in music_state:
                music_state[room_id]['queue'] = []
                music_state[room_id]['is_playing'] = False
        bot.send_message(room_id, "⏹️ Music band kar diya.")
        return True
    return False
