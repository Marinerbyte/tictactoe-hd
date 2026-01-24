import os
import threading
import time
import uuid
import traceback
import asyncio
import yt_dlp
from pydub import AudioSegment

# Attempt to import aiortc
try:
    from aiortc import RTCPeerConnection, RTCSessionDescription
    from aiortc.contrib.media import MediaStreamTrack
    import av
except ImportError:
    print("[MusicLive] CRITICAL: 'aiortc' and 'av' are not installed. Run 'pip install aiortc av'.")
    # Define dummy classes to prevent crash on load
    RTCPeerConnection = object
    RTCSessionDescription = object
    MediaStreamTrack = object

# --- CONFIG ---
DOWNLOAD_DIR = "music_cache_live"
MAX_QUEUE_SIZE = 15

# --- GLOBALS ---
# { room_id: { queue: [], is_playing: bool, rtc_connection: object } }
music_state = {}
lock = threading.Lock()
BOT_INSTANCE = None

class AudioPlayerTrack(MediaStreamTrack):
    """
    A custom MediaStreamTrack that reads from an audio file and streams it.
    """
    kind = "audio"

    def __init__(self, filepath):
        super().__init__()
        self.container = av.open(filepath)
        self.stream = self.container.streams.audio[0]
        self.last_pts = None

    async def recv(self):
        try:
            frame = next(self.container.decode(self.stream))
            # Handle timestamps correctly
            if self.last_pts is not None:
                time_diff = frame.pts - self.last_pts
                await asyncio.sleep(time_diff * self.stream.time_base)
            self.last_pts = frame.pts
            return frame
        except StopIteration:
            # Song finished, signal end
            return None

def setup(bot):
    global BOT_INSTANCE
    BOT_INSTANCE = bot
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)
    print("[MusicLive] EXPERIMENTAL Live Streaming Engine Loaded.")

# ==========================================
# 🎵 MUSIC & WebRTC ENGINE
# ==========================================

async def create_webrtc_connection(room_id, offer_sdp, ice_candidates):
    """
    Uses aiortc to establish a connection with the server's audio bridge.
    """
    pc = RTCPeerConnection()

    @pc.on("iceconnectionstatechange")
    async def on_iceconnectionstatechange():
        print(f"ICE connection state is {pc.iceConnectionState}")
        if pc.iceConnectionState == "failed":
            await pc.close()
            with lock:
                if room_id in music_state: music_state[room_id]['is_playing'] = False

    # Set the remote description from the server's offer
    await pc.setRemoteDescription(RTCSessionDescription(sdp=offer_sdp['sdp'], type=offer_sdp['type']))
    
    # Add received ICE candidates
    for candidate_info in ice_candidates:
        # Construct RTCIceCandidate object
        # Note: The exact format might differ. This is a common structure.
        candidate = candidate_info # This needs to be parsed correctly based on what the server sends
        await pc.addIceCandidate(candidate)
        
    # Create an answer
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    
    # Send our answer back to the server (GUESSWORK PAYLOAD)
    answer_payload = {
        "handler": "webrtc",
        "action": "answer",
        "roomid": int(room_id),
        "sdp": {"type": pc.localDescription.type, "sdp": pc.localDescription.sdp}
    }
    BOT_INSTANCE.send_json(answer_payload)
    
    return pc

async def play_song_on_track(pc, filepath):
    """Adds an audio track to the peer connection and plays it."""
    player = AudioPlayerTrack(filepath)
    pc.addTrack(player)
    
    # Wait for the track to finish
    # The recv loop in AudioPlayerTrack will naturally end
    # We need a way to detect this.
    # For now, we'll just wait for the song duration.
    audio = AudioSegment.from_mp3(filepath)
    duration = len(audio) / 1000.0
    await asyncio.sleep(duration)

async def audio_player_task(room_id):
    """
    The main async task that manages the WebRTC connection and song queue.
    """
    global music_state
    pc = None
    
    while True:
        with lock:
            state = music_state.get(room_id)
            if not state or not state['queue'] or not state['is_playing']:
                if pc: await pc.close()
                if state: state['is_playing'] = False; state['current_song'] = None
                send_audio_payload(room_id, "leave")
                break
            
            song = state['queue'].pop(0)
            state['current_song'] = song
        
        BOT_INSTANCE.send_message(room_id, f"🎶 Now Playing: **{song['title']}**")
        
        try:
            # Wait for server's offer
            # This requires a listener for the WebRTC offer payload
            # For this example, we assume we get it within a few seconds
            # In a real bot, `handle_system_message` would trigger this.
            
            # Placeholder: In reality, you'd wait for an event from the WebSocket reader.
            await asyncio.sleep(2) 
            
            with lock:
                state = music_state[room_id]
                offer_sdp = state.get("offer_sdp")
                ice_candidates = state.get("ice_candidates")

            if not offer_sdp:
                BOT_INSTANCE.send_message(room_id, "❌ Did not receive audio session info from server.")
                continue

            # Create WebRTC connection
            pc = await create_webrtc_connection(room_id, offer_sdp, ice_candidates)
            
            # Stream the song
            await play_song_on_track(pc, song['filepath'])
            
            # Close connection after song
            await pc.close()
            pc = None

        except Exception as e:
            print(f"Player Task Error: {e}")
            traceback.print_exc()
            if pc: await pc.close()
            pc = None

# ==========================================
# 📡 PAYLOAD GUESSES
# ==========================================

def send_audio_payload(room_id, action):
    """
    GUESS: This payload tells the server we WANT to join the audio.
    The server should respond with WebRTC offer details.
    """
    payload = {
        "handler": "joinAudio", # A very common handler name
        "action": action, # "join" or "leave"
        "roomid": int(room_id),
        "id": uuid.uuid4().hex
    }
    print(f"[MusicLive] Sending '{action}' payload for room {room_id}")
    BOT_INSTANCE.send_json(payload)

# ==========================================
# 📥 SYSTEM MESSAGE LISTENER
# ==========================================
def handle_system_message(bot, data):
    """
    This function MUST listen for the server's WebRTC offer.
    """
    handler = data.get("handler")
    
    # GUESS: The server might send a handler like "webrtcOffer"
    if handler == "webrtcOffer":
        room_id = data.get("roomid")
        offer_sdp = data.get("sdp")
        ice_candidates = data.get("iceCandidates", [])
        
        with lock:
            if room_id in music_state:
                music_state[room_id]["offer_sdp"] = offer_sdp
                music_state[room_id]["ice_candidates"] = ice_candidates
                print(f"[MusicLive] Received WebRTC offer for room {room_id}")

# ==========================================
# 📨 COMMAND HANDLER
# ==========================================
def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    
    if cmd in ["livep", "liveplay"]:
        query = " ".join(args)
        if not query: return True
        
        bot.send_message(room_id, f"
Searching for **{query}**...")
        
        # This part should be async too, but for simplicity...
        song = search_and_download(query) # `yt_dlp` is blocking
        if not song:
            bot.send_message(room_id, "❌ Download failed.")
            return True
            
        with lock:
            if room_id not in music_state:
                music_state[room_id] = {'queue': [], 'is_playing': False, 'current_song': None}
            
            state = music_state[room_id]
            state['queue'].append(song)
            bot.send_message(room_id, f"✅ Queued: **{song['title']}**")
            
            if not state['is_playing']:
                state['is_playing'] = True
                # 1. Tell server we want to join
                send_audio_payload(room_id, "join")
                # 2. Start the async player task in a new thread
                def run_async_loop():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(audio_player_task(room_id))
                    loop.close()
                
                threading.Thread(target=run_async_loop).start()
        return True
        
    if cmd == "livestop":
        with lock:
            if room_id in music_state:
                music_state[room_id]['queue'] = []
                music_state[room_id]['is_playing'] = False # This will signal the thread to stop
        bot.send_message(room_id, "⏹️ Live music stopped.")
        return True

    return False
