import os
import threading
import time
import requests
import traceback

# --- CONFIG ---
DOWNLOAD_DIR = "music_cache"
MAX_QUEUE_SIZE = 15
COOKIE_FILE = "cookies.txt" # Agar aap GitHub par upload karenge

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
# 🎵 MUSIC ENGINE (Fixed for Bot Detection)
# ==========================================

def search_and_download(query):
    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(DOWNLOAD_DIR, '%(id)s.%(ext)s'),
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '128'}],
            'default_search': 'ytsearch1',
            'noplaylist': True,
            'quiet': True,
            'no_check_certificate': True,
            'add_header': [
                'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language: en-US,en;q=0.5',
            ]
        }

        # AGAR COOKIES FILE HAI TOH USE KARO
        if os.path.exists(COOKIE_FILE):
            print("[Music] Using cookies.txt to bypass bot detection.")
            ydl_opts['cookiefile'] = COOKIE_FILE
        else:
            print("[Music] Warning: cookies.txt not found. Attempting bypass headers...")

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
        # Chat mein error bhejta hai taaki aapko pata chale
        if "confirm you’re not a bot" in str(e):
            print("[Music] YouTube blocked us. Needs cookies.txt")
        print(f"[Music Error]: {e}")
    return None

# --- UPLOAD & PLAYER LOGIC (Same as before) ---

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
                BOT_INSTANCE.send_message(room_id, "⏹️ Queue finished.")
                break
            song = state['queue'].pop(0)

        BOT_INSTANCE.send_message(room_id, f"📥 Uploading gaana...")
        url = upload_audio(song['filepath'])
        
        try:
            if os.path.exists(song['filepath']): os.remove(song['filepath'])
        except: pass
        
        if url:
            html = f"<audio src='{url}' controls autoplay></audio>"
            BOT_INSTANCE.send_message(room_id, f"🎶 Playing: **{song['title']}**\n{html}")
            dur = song.get('duration', 180)
            for _ in range(int(dur)):
                time.sleep(1)
                with lock:
                    if not state['is_playing']: break
            if not state['is_playing']: break
        else:
            BOT_INSTANCE.send_message(room_id, "❌ Upload Failed.")

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    if cmd in ["p", "play"]:
        if not args: return True
        query = " ".join(args)
        bot.send_message(room_id, f"🔎 Searching: **{query}**...")
        song = search_and_download(query)
        if not song:
            bot.send_message(room_id, "❌ YouTube ne block kar diya hai. Admin ko cookies.txt update karni hogi.")
            return True
        with lock:
            if room_id not in music_state: music_state[room_id] = {'queue': [], 'is_playing': False}
            state = music_state[room_id]
            state['queue'].append(song)
            bot.send_message(room_id, f"✅ Queued: {song['title']}")
            if not state['is_playing']:
                threading.Thread(target=player_thread, args=(room_id,), daemon=True).start()
        return True
    if cmd == "stop":
        with lock:
            if room_id in music_state:
                music_state[room_id]['queue'] = []
                music_state[room_id]['is_playing'] = False
        bot.send_message(room_id, "⏹️ Stopped.")
        return True
    return False
