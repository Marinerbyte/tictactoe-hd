import requests
import re
import urllib.parse
import time
import os
import shutil

# --- CONFIG ---
TEMP_DOWNLOAD_DIR = "temp_dj_audio_cache" # Temporary folder

# --- UTILITY ---
def clean_temp_dir():
    if os.path.exists(TEMP_DOWNLOAD_DIR):
        shutil.rmtree(TEMP_DOWNLOAD_DIR)
    os.makedirs(TEMP_DOWNLOAD_DIR)

def get_saavn_audio_info(query):
    """JioSaavn se gaana search karke uska URL aur details nikalta hai."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
        'Referer': 'https://www.jiosaavn.com/'
    }
    try:
        # 1. Search
        search_url = f"https://www.jiosaavn.com/api.php?__call=autocomplete.get&_format=json&_marker=0&includeMetaTags=1&query={query.replace(' ', '+')}"
        res = requests.get(search_url, headers=headers, timeout=10).json()
        
        if res and res['songs']['data']:
            song_id = res['songs']['data'][0]['id']
            
            # 2. Get Details (for full URL)
            detail_url = f"https://www.jiosaavn.com/api.php?__call=song.getDetails&_format=json&_marker=0&pids={song_id}"
            details = requests.get(detail_url, headers=headers, timeout=10).json()
            
            song_info = details[song_id]
            
            # 3. Extract direct download link (AAC 160kbps for quality)
            # Replace 'preview' with 'aac' and adjust bitrate
            raw_url = song_info['media_preview_url']
            dl_link = raw_url.replace('preview', 'aac').replace('96_p.mp4', '160.mp4')
            
            return {
                "title": song_info['song'],
                "artist": song_info['primary_artists'],
                "image": song_info['image'].replace('150x150', '500x500'),
                "duration": int(song_info.get('duration', 180)),
                "stream_url": dl_link
            }
    except Exception as e:
        print(f"[MusicUtils] Saavn Error: {e}")
    return None

def download_audio_to_temp(stream_url, video_id):
    """Gaane ko temporary file me download karta hai."""
    try:
        clean_temp_dir() # Clean before download
        filepath = os.path.join(TEMP_DOWNLOAD_DIR, f"{video_id}.mp3")
        
        print(f"[MusicUtils] Downloading audio from {stream_url} to {filepath}")
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
            'Referer': 'https://www.jiosaavn.com/'
        }
        audio_content = requests.get(stream_url, headers=headers, timeout=30).content
        
        with open(filepath, 'wb') as f:
            f.write(audio_content)
        
        return filepath if os.path.exists(filepath) else None
    except Exception as e:
        print(f"[MusicUtils] Download to temp failed: {e}")
    return None
