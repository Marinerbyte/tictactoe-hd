import requests
import time
import io

def upload_audio_to_howdies(bot, audio_bytes, filename="song.mp3"):
    """
    Gaane ko Howdies ke server par upload karne ke liye.
    Documentation ke mutabik: UserID, token, uploadType='audio'
    """
    try:
        url = "https://api.howdies.app/api/upload"
        
        # Payload as per documentation
        files = {'file': (filename, audio_bytes, 'audio/mpeg')}
        data = {
            'token': bot.token,
            'uploadType': 'audio', 
            'UserID': bot.user_id # Capital U, I, D as per docs
        }
        
        print(f"[MusicUtils] Uploading {filename} to Howdies Server...")
        # 60 seconds timeout kyunki gaana bada ho sakta hai
        r = requests.post(url, files=files, data=data, timeout=60)
        
        if r.status_code == 200:
            res = r.json()
            # Howdies URL nikalte hain
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
    YouTube ID se MP3 bytes download karne ke liye
    """
    try:
        # VKR API use kar rahe hain bytes laane ke liye
        api_url = f"https://api.vkrtool.in/youtube/v1/get?id={video_id}"
        resp = requests.get(api_url, timeout=15).json()
        
        download_url = resp.get('url') or resp.get('download')
        if download_url:
            print(f"[MusicUtils] Downloading bytes from provider...")
            audio_data = requests.get(download_url, timeout=30).content
            return audio_data
    except Exception as e:
        print(f"[MusicUtils] Error fetching MP3 content: {e}")
    return None
