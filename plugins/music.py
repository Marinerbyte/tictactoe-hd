import os
import threading
import time
import yt_dlp
import requests
import traceback

# --- CONFIG ---
DOWNLOAD_DIR = "music_cache"
MAX_QUEUE_SIZE = 15

# --- GLOBALS ---
# { room_id: { queue: [], is_playing: bool, current_song: {} } }
music_state = {}
lock = threading.Lock()
BOT_INSTANCE = None

def setup(bot):
    global BOT_INSTANCE
    BOT_INSTANCE = bot
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)
    print("[Music] Upload & Play Engine Loaded.")

# ==========================================
# 🎵 MUSIC ENGINE
# ==========================================

def search_and_download(query):
    """Downloads a song from YouTube as MP3 and returns its info."""
    try:
        # Options for yt-dlp: search one, get best audio, convert to mp3
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(DOWNLOAD_DIR, '%(id)s.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192', # Good quality, small size
            }],
            'default_search': 'ytsearch1',
            'noplaylist': True,
            'quiet': True,
            'noprogress': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=True)
            if 'entries' in info and info['entries']:
                song_info = info['entries'][0]
                return {
                    "id": song_info.get('id'),
                    "title": song_info.get('title', 'Unknown Title'),
                    "duration": song_info.get('duration', 180), # Default 3 mins
                    "uploader": song_info.get('uploader', 'Unknown Artist'),
                    "filepath": os.path.join(DOWNLOAD_DIR, f"{song_info.get('id')}.mp3")
                }
    except Exception as e:
        print(f"[Music] Download Error: {e}")
    return None

def upload_audio(filepath):
    """Uploads the downloaded MP3 to Howdies server."""
    try:
        url = "https://api.howdies.app/api/upload"
        
        with open(filepath, 'rb') as f:
            files = {'file': ('song.mp3', f.read(), 'audio/mpeg')}
        
        data = {
            'token': BOT_INSTANCE.token,
            'uploadType': 'audio',
            'UserID': BOT_INSTANCE.user_id or 0
        }
        
        # High timeout for large files on slow connections
        r = requests.post(url, files=files, data=data, timeout=90)
        
        if r.status_code == 200:
            res = r.json()
            return res.get('url') or res.get('data', {}).get('url')
        else:
            print(f"[Music] Upload Failed: {r.text}")
            
    except Exception as e:
        print(f"[Music] Upload Error: {e}")
    return None

def player_thread(room_id):
    """
    A dedicated thread for each room. It manages the song queue,
    uploads songs, and sends the player to the chat.
    """
    global music_state
    
    with lock:
        if room_id not in music_state: return
        state = music_state[room_id]
        state['is_playing'] = True

    while True:
        with lock:
            if not state['queue']:
                state['is_playing'] = False
                state['current_song'] = None
                BOT_INSTANCE.send_message(room_id, "⏹️ Queue finished. Player is now idle.")
                break # Exit thread
            
            song = state['queue'].pop(0)
            state['current_song'] = song

        # --- UPLOAD & PLAY ---
        
        # 1. Upload the song (This might take time)
        BOT_INSTANCE.send_message(room_id, f"
Uploading **{song['title']}**...")
        audio_url = upload_audio(song['filepath'])
        
        # Cleanup downloaded file
        try:
            if os.path.exists(song['filepath']):
                os.remove(song['filepath'])
        except: pass
        
        if not audio_url:
            BOT_INSTANCE.send_message(room_id, f"❌ Upload failed for **{song['title']}**. Skipping.")
            continue
            
        # 2. Create the HTML5 Audio Player
        # `controls` shows play/pause, `autoplay` starts it automatically
        player_html = f"<audio src='{audio_url}' controls autoplay></audio>"
        
        # 3. Send the player to the chat
        BOT_INSTANCE.send_message(room_id, f"🎶 Now Playing: **{song['title']}**\n{player_html}")
        
        # 4. Wait for the song's duration before playing the next one
        # This loop allows the `!skip` command to work instantly
        duration = song.get('duration', 180)
        for _ in range(duration):
            time.sleep(1)
            with lock:
                # If stop or skip was called, break the wait
                if not state['is_playing']:
                    break
        
        with lock:
            # If the loop was broken by a stop command, exit the thread completely
            if not state['is_playing']:
                break

    print(f"[Music] Player thread for room {room_id} has stopped.")

# ==========================================
# 📨 COMMAND HANDLER
# ==========================================

def handle_command(bot, command, room_id, user, args, data):
    global music_state
    cmd = command.lower().strip()
    
    # 1. PLAY COMMAND
    if cmd in ["p", "play"]:
        if not args:
            bot.send_message(room_id, "Usage: `!p <song name or youtube url>`")
            return True
            
        query = " ".join(args)
        bot.send_message(room_id, f"
Searching for **{query}**...")
        
        song = search_and_download(query)
        if not song:
            bot.send_message(room_id, "❌ Song not found or download failed.")
            return True
            
        with lock:
            if room_id not in music_state:
                music_state[room_id] = {'queue': [], 'is_playing': False, 'current_song': None}
            
            state = music_state[room_id]
            if len(state['queue']) >= MAX_QUEUE_SIZE:
                bot.send_message(room_id, "Queue is full!"); return True
                
            state['queue'].append(song)
            bot.send_message(room_id, f"✅ Added to queue: **{song['title']}**")
            
            # If the player isn't already running for this room, start it.
            if not state['is_playing']:
                threading.Thread(target=player_thread, args=(room_id,), daemon=True).start()
        return True

    # 2. SKIP COMMAND
    if cmd == "skip":
        with lock:
            state = music_state.get(room_id)
            if state and state['is_playing']:
                # Setting is_playing to False signals the player_thread to stop waiting
                # and move to the next song.
                state['is_playing'] = False 
        bot.send_message(room_id, "⏭️ Skipping song...")
        # A small delay to allow the current thread to stop
        time.sleep(1.5)
        # Re-activate the player if there are more songs
        with lock:
            state = music_state.get(room_id)
