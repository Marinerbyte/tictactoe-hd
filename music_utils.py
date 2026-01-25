import requests
import time
import io
import re

def upload_audio_to_howdies(bot, audio_bytes, filename="song.mp3"):
    """Documentation ke mutabik Howdies server par upload"""
    try:
        url = "https://api.howdies.app/api/upload"
        files = {'file': (filename, audio_bytes, 'audio/mpeg')}
        data = {
            'token': bot.token,
            'uploadType': 'audio', 
            'UserID': bot.user_id 
        }
        
        print(f"[MusicUtils] Uploading {filename} to Howdies...")
        r = requests.post(url, files=files, data=data, timeout=60)
        
        if r.status_code == 200:
            res = r.json()
            final_url = res.get('url') or res.get('data', {}).get('url')
            if final_url:
                print(f"[MusicUtils] Upload Success: {final_url}")
                return final_url
        print(f"[MusicUtils] Upload Failed: {r.text}")
    except Exception as e:
        print(f"[MusicUtils] Error during upload: {e}")
    return None

def get_direct_mp3_content(video_id):
    """
    Multi-API Fallback System
    YouTube ID se MP3 bytes download karne ke liye.
    """
    # List of alternative APIs
    api_list = [
        f"https://api.vevioz.com/@api/button/mp3/{video_id}", # API 1
        f"https://vkr-api.vercel.app/server/api/ytdl?url=https://www.youtube.com/watch?v={video_id}" # API 2
    ]

    for api_url in api_list:
        try:
            print(f"[MusicUtils] Trying to fetch audio from: {api_url}")
            # Step 1: Link fetch karo
            resp = requests.get(api_url, timeout=15)
            
            # Agar API 1 (vevioz) hai, toh ye seedha file content ya redirect de sakta hai
            if "vevioz" in api_url:
                if resp.status_code == 200 and len(resp.content) > 100000: # Kam se kam 100KB
                    return resp.content
            
            # Agar API 2 (JSON based) hai
            elif resp.status_code == 200:
                data = resp.json()
                dl_link = data.get('url') or data.get('download')
                if dl_link:
                    audio_data = requests.get(dl_link, timeout=30).content
                    if len(audio_data) > 100000:
                        return audio_data
        except Exception as e:
            print(f"[MusicUtils] API failed: {e}")
            continue # Agli API try karo

    return None
