import threading
import time
import uuid
import asyncio
import requests
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaStreamTrack
import av # Must be installed

# ... (Rest of the setup and global vars from previous message) ...

# --- [Only the critical parts are shown, assume rest is as given before] ---

async def run_webrtc_session(room_id):
    pc = RTCPeerConnection()
    # ... (ICE change handler) ...
    
    try:
        # Wait for server offer details (Crucial)
        while True:
            with lock:
                if 'transports' in sessions.get(room_id, {}): break
            await asyncio.sleep(0.1)

        with lock:
            s = sessions[room_id]
            transport_data = s['transports']
            rtp_caps = s['rtp_caps']
        
        # 1. Send 'connect-transport' (As per docs)
        BOT_INSTANCE.send_json({
            "handler": "audioroom", "action": "connect-transport", "roomId": room_id,
            "direction": "send", "transportId": transport_data['send']['id'],
            "dtlsParameters": transport_data['send']['dtlsParameters']
        })
        
        # 2. Add Audio Track and wait for it to be ready
        track = DJAudioTrack(s['song_path']) # Path is set in handle_command
        pc.addTrack(track)
        
        await asyncio.sleep(2) 

        # 3. Send 'produce' Payload (To start sending audio)
        req_id = str(uuid.uuid4())
        rtp_params = { "codecs": rtp_caps.get('codecs', []) } 
        BOT_INSTANCE.send_json({
            "handler": "audioroom", "action": "produce", "roomId": room_id,
            "kind": "audio", "rtpParameters": rtp_params, "requestId": req_id
        })
        
        # Wait for song to finish (using duration from song data is better here)
        await asyncio.sleep(song_path['duration'] + 5) # Wait a bit longer
        
    except Exception as e:
        print(f"WebRTC Error: {e}")
    finally:
        if pc and pc.connectionState != "closed": await pc.close()
        with lock:
            if room_id in sessions: del sessions[room_id]
        print(f"[LiveDJ] Session ended for room {room_id}")

# ... (handle_system_message and handle_command follow) ...

def handle_command(bot, command, room_id, user, args, data):
    # ... (join/start logic) ...
    
    if cmd == "dj":
        # ... (setup logic) ...
        
        # 1. Download (Using Saavn or a stable source)
        # Use Saavn API from music_utils.py to get URL
        # song_data = music_utils.get_saavn_audio_data(...)
        # path = download_to_temp_file(song_data)
        
        # --- CRITICAL: Use a known stable URL for the first test ---
        test_song_url = "https://files.catbox.moe/kftu8t.mp3" # Temporary stable link
        
        # ... (Save path, Send 'join' payload) ...
        
        # Start Async Task
        # ...
        
        # After sending 'join', we wait for 'transport-created' in handle_system_message
        
        return True
