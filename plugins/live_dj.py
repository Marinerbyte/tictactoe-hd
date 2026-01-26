import os
import threading
import time
import uuid
import asyncio
import requests
import collections # For deque
import music_utils # For downloading songs

# --- WebRTC & Music Libraries ---
try:
    from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceCandidate
    from aiortc.contrib.media import MediaStreamTrack, MediaPlayer
    import av
    RTC_READY = True
except ImportError:
    print("[LiveDJ] CRITICAL: 'aiortc' and 'av' not installed. Live streaming is disabled.")
    RTC_READY = False
    RTCPeerConnection = RTCSessionDescription = MediaStreamTrack = av = object

# --- GLOBALS ---
# { room_id: { pc: peer_connection, producer_track: object, audio_room_id: str, 
#               state: str, queue: deque, pending_offer: Event, transports: {}, rtp_caps: {} } }
sessions = {}
lock = threading.Lock() # Global lock for shared state
BOT_INSTANCE = None # Reference to the main bot object

# --- Custom MediaStreamTrack for Queuing ---
class DJMixerTrack(MediaStreamTrack):
    kind = "audio"

    def __init__(self, room_id):
        super().__init__()
        self.room_id = room_id
        self.player = None
        self.current_song_info = None
        self.queue = collections.deque()
        self.play_next_event = asyncio.Event()
        self.loop_task = asyncio.create_task(self._play_loop())

    def add_song(self, song_info):
        self.queue.append(song_info)
        self.play_next_event.set() # Signal to play next if idle

    async def _play_loop(self):
        while True:
            if not self.queue:
                # Produce silent frames to keep connection alive if nothing to play
                # This is crucial for 'always live' requirement.
                self.current_song_info = {"title": "Silent Standby"}
                print(f"[{self.room_id}] Producing silence...")
                self.player = MediaPlayer(os.path.join(os.path.dirname(__file__), "silent.mp3")) # Small silent mp3 file
                await self._play_current_player()
            else:
                song = self.queue.popleft()
                self.current_song_info = song
                print(f"[{self.room_id}] Now playing: {song['title']}")
                # Signal to main bot thread to send chat message
                if BOT_INSTANCE:
                    BOT_INSTANCE.send_message(self.room_id, f"🎶 Now Playing: **{song['title']}**")
                
                # Use MediaPlayer to stream the local file
                self.player = MediaPlayer(song['filepath'])
                await self._play_current_player()

            # Wait for next song or signal
            await self.play_next_event.wait()
            self.play_next_event.clear()

    async def _play_current_player(self):
        while True:
            try:
                frame = await self.player.audio.recv()
                if frame is None:
                    break
                # Yield frame to aiortc
                yield frame
            except Exception as e:
                print(f"[{self.room_id}] Error in player loop: {e}")
                break

    async def recv(self):
        # This recv is called by aiortc. We yield frames from our internal player.
        return await self._play_current_player().__anext__() # Correct way to yield from async generator

    def stop(self):
        if self.loop_task: self.loop_task.cancel()
        if self.player: self.player.audio.close() # Close any open files


def setup(bot):
    global BOT_INSTANCE
    BOT_INSTANCE = bot
    if RTC_READY:
        # Create a dummy silent mp3 file if it doesn't exist for standby mode
        silent_file = os.path.join(os.path.dirname(__file__), "silent.mp3")
        if not os.path.exists(silent_file):
            print("[LiveDJ] Creating silent.mp3 for standby mode...")
            from pydub import AudioSegment
            silent_audio = AudioSegment.silent(duration=5000) # 5 seconds of silence
            silent_audio.export(silent_file, format="mp3")
        music_utils.clean_temp_dir() # Clean up any previous temp downloads
        print("[LiveDJ] On-Demand WebRTC Engine Loaded.")
    else:
        print("[LiveDJ] Live Streaming Disabled (Missing Libraries).")


# ==========================================
# ⚡ WebRTC SESSION MANAGER
# ==========================================

async def run_webrtc_session(room_id):
    """
    Manages the full WebRTC handshake and maintains the connection.
    """
    pc = RTCPeerConnection()
    
    with lock:
        s = sessions.get(room_id)
        if not s: return # Session might have been deleted
        s['pc'] = pc
        offer_received_event = s['offer_received_event'] # To wait for server's offer

    # 1. ICE Connection State Listener
    @pc.on("iceconnectionstatechange")
    async def on_ice_change():
        print(f"[{room_id}] ICE connection state: {pc.iceConnectionState}")
        if pc.iceConnectionState in ["failed", "closed", "disconnected"]:
            print(f"[{room_id}] WebRTC connection lost. Closing session.")
            await pc.close()
            with lock:
                if room_id in sessions: del sessions[room_id]
            
    # 2. Add Audio Track (Our custom mixer which handles queue/silence)
    mixer_track = DJMixerTrack(room_id)
    pc.addTrack(mixer_track)
    with lock:
        sessions[room_id]['mixer_track'] = mixer_track

    try:
        # 3. Wait for Server's Transport Details (Triggered by 'audioroom:join')
        print(f"[{room_id}] Waiting for server's WebRTC offer (transport-created)...")
        # This event is set in handle_system_message when 'transport-created' is received
        await offer_received_event.wait() 
        
        with lock:
            s = sessions[room_id]
            transport_details = s['transport_details']
            router_rtp_caps = s['router_rtp_capabilities']

        # 4. Connect Transports (DTLS Handshake)
        # As per docs 5.3: Client sends 'connect-transport' action
        BOT_INSTANCE.send_json({
            "handler": "audioroom", "action": "connect-transport", "roomId": room_id,
            "direction": "send", "transportId": transport_details['send']['id'],
            "dtlsParameters": transport_details['send']['dtlsParameters'] # Simplified for aiortc
        })
        
        await asyncio.sleep(2) # Give some time for DTLS to connect

        # 5. Send 'produce' Payload (To start sending audio data - even if silence)
        # As per docs 5.5: Request creation of a Producer on SFU
        req_id = str(uuid.uuid4())
        BOT_INSTANCE.send_json({
            "handler": "audioroom", "action": "produce", "roomId": room_id,
            "kind": "audio", "rtpParameters": router_rtp_caps['codecs'][0], # Simplified RTP params
            "requestId": req_id
        })
        
        # 6. Wait indefinitely to keep the connection alive (for 'always live' requirement)
        # The mixer_track will produce silence or music.
        print(f"[{room_id}] Bot is now live in audio (producing silence or music).")
        await asyncio.Event().wait() # Keep this task running forever
        
    except asyncio.CancelledError:
        print(f"[{room_id}] WebRTC session task was cancelled.")
    except Exception as e:
        print(f"[{room_id}] WebRTC Session Error: {e}")
        traceback.print_exc()
    finally:
        if pc.connectionState != "closed": await pc.close()
        if mixer_track: mixer_track.stop()
        with lock:
            if room_id in sessions: del sessions[room_id]
        print(f"[{room_id}] Audio session fully cleaned up.")

# ==========================================
# 📡 SYSTEM MESSAGE LISTENER (Crucial for Handshake)
# ==========================================
def handle_system_message(bot, data):
    """
    Parses 'audioroom' messages from server and advances WebRTC state.
    """
    if data.get("handler") != "audioroom": return
    
    msg_type = data.get("type")
    room_id = str(data.get("roomId")) # Server sends 'roomId' (text)
    
    with lock:
        s = sessions.get(room_id)
        if not s: 
            print(f"[LiveDJ] Received audioroom message for unknown session {room_id}: {msg_type}")
            return
            
        # 1. Server sends transport details (after 'audioroom:join')
        # As per docs 6.1: 'transport-created'
        if msg_type == "transport-created":
            s['transport_details'] = data.get("transports")
            s['router_rtp_capabilities'] = data.get("routerRtpCapabilities")
            s['offer_received_event'].set() # Signal the main session task to proceed
            print(f"[{room_id}] Received 'transport-created' from server.")
            
        # 2. Server confirms mic is ON (after 'produce' action)
        # As per docs 6.8: 'producer-created'
        elif msg_type == "producer-created":
            print(f"[{room_id}] Producer confirmed by server. Live streaming is active!")

        # 3. Handle Errors
        elif msg_type == "error":
            error_code = data.get('data', {}).get('code', 'UNKNOWN')
            error_msg = data.get('data', {}).get('message', 'An unknown error occurred.')
            print(f"[{room_id}] Server ERROR: {error_code} - {error_msg}")
            # Trigger cleanup
            if s.get('pc'): asyncio.run(s['pc'].close())


# ==========================================
# 📨 COMMAND HANDLER (DJ Control)
# ==========================================
def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    
    if cmd == "dj":
        if not RTC_READY:
            bot.send_message(room_id, "❌ DJ System Not Ready (aiortc/av missing)."); return True
        
        # Check if already active
        with lock:
            if room_id in sessions:
                bot.send_message(room_id, "⚠️ DJ is already active in this room. Use `!djplay` or `!djstop`."); return True
        
        query = " ".join(args) # Song query
        if not query:
            bot.send_message(room_id, "Usage: `!dj <song name>` to start a session."); return True
        
        # 1. Download Song (Async task)
        bot.send_message(room_id, f"🎵 Fetching song: **{query}** from JioSaavn...")
        song_info = music_utils.get_saavn_audio_info(query)
        if not song_info:
            bot.send_message(room_id, "❌ Song not found on Saavn."); return True
        
        # 2. Save song to temp file (Mandatory for aiortc)
        # Using song ID for unique filename
        temp_file_path = music_utils.download_audio_to_temp(song_info['stream_url'], song_info['id'])
        if not temp_file_path:
            bot.send_message(room_id, "❌ Song download to temp failed."); return True

        # 3. Initialize Session State
        with lock:
            sessions[room_id] = {
                "song_path": temp_file_path,
                "title": song_info['title'],
                "duration": song_info['duration'],
                "pc": None, # PeerConnection object
                "mixer_track": None, # Our custom track
                "offer_received_event": asyncio.Event() # To sync with server offer
            }
            
        # 4. Send 'join' payload (As per docs 5.1)
        BOT_INSTANCE.send_json({
            "handler": "audioroom", "action": "join", "roomId": room_id
        })
        
        # 5. Start the WebRTC session manager in a new thread
        def run_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(run_webrtc_session(room_id))
            loop.close()
        threading.Thread(target=run_loop, daemon=True).start()
        
        bot.send_message(room_id, f"✅ DJ joining mic. Playing: **{song_info['title']}**")
        return True
        
    if cmd == "djplay":
        # Play next song in queue (User can queue multiple songs)
        pass # To be implemented
        
    if cmd == "djstop":
        # 1. Send 'leave' payload (As per docs 5.2)
        BOT_INSTANCE.send_json({
            "handler": "audioroom", "action": "leave", "roomId": room_id
        })
        
        # 2. Clean up local session
        with lock:
            s = sessions.get(room_id)
            if s and s.get('pc'): asyncio.run(s['pc'].close()) # Close WebRTC
            if s and s.get('mixer_track'): s['mixer_track'].stop() # Stop local player
            if room_id in sessions: del sessions[room_id]
        
        BOT_INSTANCE.send_message(room_id, "⏹️ DJ has left the mic.")
        return True
        
    return False
