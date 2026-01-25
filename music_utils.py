import requests
import time
import io

# Stable Cobalt Instances (Ye jaldi block nahi hote)
COBALT_INSTANCES = [
    "https://api.cobalt.tools/api/json",
    "https://cobalt.shifuserver.xyz/api/json",
    "https://api.bravo.zip/api/json"
]

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
        
        print(f"[MusicUtils] Uploading to Howdies...")
        r = requests.post(url, files=files, data=data, timeout=60)
        
        if r.status_code == 200:
            res = r.json()
            return res.get('url') or res.get('data', {}).get('url')
    except Exception as e:
        print(f"[MusicUtils] Upload Error: {e}")
    return None

def get_direct_mp3_content(video_id):
    """
    Cobalt Engine System: Sabse professional downloader.
    """
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    
    payload = {
        "url": video_url,
        "downloadMode": "audio",
        "audioFormat": "mp3",
        "audioBitrate": "128" # Render ke liye small size best hai
    }
    
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    for instance in COBALT_INSTANCES:
        try:
            print(f"[MusicUtils] Trying Cobalt Instance: {instance}")
            # Step 1: Get Download Link from Cobalt
            resp = requests.post(instance, json=payload, headers=headers, timeout=15)
            
            if resp.status_code == 200:
                data = resp.json()
                # Cobalt link 'url' key me deta hai
                dl_link = data.get('url')
                
                if dl_link:
                    print(f"[MusicUtils] Success! Streaming from tunnel...")
                    # Step 2: Download the actual bytes
                    audio_resp = requests.get(dl_link, timeout=40, stream=True)
                    if audio_resp.status_code == 200:
                        return audio_resp.content
            else:
                print(f"[MusicUtils] Instance {instance} returned status {resp.status_code}")
                
        except Exception as e:
            print(f"[MusicUtils] Instance {instance} failed: {e}")
            continue # Agli instance try karo

    return None
