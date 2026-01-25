import requests
import re
import urllib.parse

def get_audio_bytes(video_id):
    """3 Alag Raste: Ek fail hoga toh doosra chalega"""
    # Rasta 1: VKR API
    # Rasta 2: Cobalt Mirror
    # Rasta 3: Bravo Mirror
    
    sources = [
        f"https://api.vkrtool.in/youtube/v1/get?id={video_id}",
        "https://cobalt.shifuserver.xyz/api/json",
        "https://api.bravo.zip/api/json"
    ]
    
    for url in sources:
        try:
            print(f"[MusicUtils] Trying Source: {url}")
            if "vkrtool" in url:
                res = requests.get(url, timeout=15).json()
                dl_link = res.get('url') or res.get('download')
                if dl_link:
                    return requests.get(dl_link, timeout=30).content
            else:
                # Cobalt logic
                payload = {"url": f"https://www.youtube.com/watch?v={video_id}", "downloadMode": "audio", "audioFormat": "mp3"}
                res = requests.post(url, json=payload, headers={"Accept": "application/json"}, timeout=15).json()
                if 'url' in res:
                    return requests.get(res['url'], timeout=30).content
        except:
            continue
    return None

def upload_to_howdies(bot, audio_bytes, filename="song.mp3"):
    try:
        url = "https://api.howdies.app/api/upload"
        files = {'file': (filename, audio_bytes, 'audio/mpeg')}
        data = {'token': bot.token, 'uploadType': 'audio', 'UserID': bot.user_id}
        r = requests.post(url, files=files, data=data, timeout=60)
        if r.status_code == 200:
            res = r.json()
            return res.get('url') or res.get('data', {}).get('url')
    except: pass
    return None
