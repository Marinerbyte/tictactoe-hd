import os
import threading
import time
import uuid
import asyncio
import requests
import collections
import music_utils
from io import BytesIO

# --- WebRTC Libraries ---
try:
    from aiortc import RTCPeerConnection, RTCSessionDescription
    from aiortc.contrib.media import MediaStreamTrack, MediaPlayer
    import av
    RTC_READY = True
except ImportError:
    print("[LiveDJ] CRITICAL: aiortc/av missing. Live DJ disabled.")
    RTC_READY = False
    RTCPeerConnection = RTCSessionDescription = MediaStreamTrack = av = object

# --- GLOBALS ---
sessions = {}
lock = threading.Lock()
BOT_INSTANCE = None

# --- Custom MediaStreamTrack ---
class DJMixerTrack(MediaStreamTrack):
    kind = "audio"

    def __init__(self, room_id):
        super().__init__()
        self.room_id = room_id
        self.player = None
        self.queue = collections.deque()
        self.play_next_event = asyncio.Event()
        self.loop_task = asyncio.create_task(self._play_loop())

    def add_song(self, song_info):
        self.queue.append(song_info)
        self.play_next_event.set()

    async def _play_loop(self):
        while True:
            if not self.queue:
                # Standby Mode (Silence)
                print(f"[{self.room_id}] DJ Standby: Producing silence...")
                silent_file = os.path.join(os.path.dirname(__file__), "silent.mp3")
                self.player = MediaPlayer(silent_file)
                await self._play_current_player()
            else:
                # Play Song
                song = self.queue.popleft()
                print(f"[{self.room_id}] Now Playing: {song['title']}")
                if BOT_INSTANCE:
                    BOT_INSTANCE.send_message(self.room_id, f"🎶 Now Playing: **{song['title']}**")
                
                self.player = MediaPlayer(song['filepath'])
                await self._play_current_player()

            await self.play_next_event.wait()
            self.play_next_event.clear()

    async def _play_current_player(self):
        while True:
            try:
                frame = await self.player.audio.recv()
                if frame is None: break
                yield frame
            except: break

    async def recv(self):
        return await self._play_current_player().__anext__()

    def stop(self):
        if self.loop_task: self.loop_task.cancel()
        if self.player and self.player.audio: self.player.audio.close()

def setup(bot):
    global BOT_INSTANCE
    BOT_INSTANCE = bot
    # Create silent file if missing
    silent_file = os.path.join(os.path.dirname(__file__), "silent.mp3")
    if not os.path.exists(silent_file):
        try:
            from pydub import AudioSegment
            AudioSegment.silent(duration=5000).export(silent_file, format="mp3")
        except: pass
    
    music_utils.clean_temp_dir()
    if RTC_READY: print("[LiveDJ] System Ready.")

# ==========================================
# 📡 WebRTC SESSION
# ==========================================

async def run_webrtc_session(room_id):
    pc = RTCPeerConnection()
    
    with lock:
        if room_id not in sessions: return
        sessions[room_id]['pc'] = pc
        offer_evt = sessions[room_id]['offer_event']

    @pc.on("iceconnectionstatechange")
    async def on_ice_change():
        if pc.iceConnectionState in ["failed", "closed", "disconnected"]:
            await pc.close()
            with lock:
                if room_id in sessions: del sessions[room_id]

    try:
        # 1. Wait for Offer
        print(f"[{room_id}] Waiting for server offer...")
        await offer_evt.wait()
        
        with lock:
            s = sessions[room_id]
            transport_data = s['transports']
            rtp_caps = s['rtp_caps']

        # 2. Add Mixer Track
        mixer = DJMixerTrack(room_id)
        pc.addTrack(mixer)
        with lock: sessions[room_id]['mixer_track'] = mixer
        
        # Add initial song if exists
        if s.get('initial_song'):
            mixer.add_song(s['initial_song'])

        # 3. Connect Transport
        BOT_INSTANCE.send_json({
            "handler": "audioroom", "action": "connect-transport", "roomId": room_id,
            "direction": "send", "transportId": transport_data['send']['id'],
            "dtlsParameters": transport_data['send']['dtlsParameters']
        })
        
        await asyncio.sleep(1.5) 

        # 4. Start Producing
        req_id = str(uuid.uuid4())
        BOT_INSTANCE.send_json({
            "handler": "audioroom", "action": "produce", "roomId": room_id,
            "kind": "audio", "rtpParameters": { "codecs": rtp_caps.get('codecs', []) },
            "requestId": req_id
        })
        
        # Keep alive
        await asyncio.Event().wait()
        
    except Exception as e:
        print(f"WebRTC Error: {e}")
    finally:
        if pc: await pc.close()
        if 'mixer' in locals() and mixer: mixer.stop()
        with lock:
            if room_id in sessions: del sessions[room_id]

# ==========================================
# 📨 HANDLERS
# ==========================================

def handle_system_message(bot, data):
    if data.get("handler") != "audioroom": return
    msg_type = data.get("type")
    
    if msg_type == "transport-created":
        rid = str(data.get("roomId")) # Server ID string format
        # Check against our integer Room IDs logic
        # Here we just check all sessions for a match or strict match
        # Assuming roomId matches
        with lock:
            if rid in sessions:
                sessions[rid]['transports'] = data.get("transports")
                sessions[rid]['rtp_caps'] = data.get("routerRtpCapabilities")
                sessions[rid]['offer_event'].set()

def handle_command(bot, command, room_id, user, args, data):
    # --- ERROR FIX: cmd variable define kiya ---
    cmd = command.lower().strip()
    
    if cmd == "dj":
        if not RTC_READY:
            bot.send_message(room_id, "❌ Audio System Failed (Dependencies missing).")
            return True
        
        query = " ".join(args)
        if not query:
            bot.send_message(room_id, "Usage: `!dj songname`")
            return True

        bot.send_message(room_id, f"🎵 **{query}** dhoondh raha hoon...")

        # 1. Download
        song_info = music_utils.get_saavn_audio_info(query)
        if not song_info:
            bot.send_message(room_id, "❌ Song nahi mila.")
            return True

        fpath = music_utils.download_audio_to_temp(song_info['stream_url'], song_info['id'])
        if not fpath:
            bot.send_message(room_id, "❌ Download fail.")
            return True
            
        song_data = {"title": song_info['title'], "filepath": fpath}

        # 2. Check Active Session
        with lock:
            if room_id in sessions:
                # Add to Queue
                sessions[room_id]['mixer_track'].add_song(song_data)
                bot.send_message(room_id, f"✅ Queued: **{song_info['title']}**")
                return True
            
            # Create New Session
            sessions[room_id] = {
                "initial_song": song_data,
                "offer_event": asyncio.Event()
            }
        
        # 3. Join & Start
        BOT_INSTANCE.send_json({
            "handler": "audioroom", "action": "join", "roomId": room_id
        })
        
        def run_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(run_webrtc_session(room_id))
            loop.close()
        threading.Thread(target=run_loop, daemon=True).start()
        
        return True
        
    if cmd == "djstop":
        with lock:
            if room_id in sessions:
                # Sending 'leave' will trigger cleanup
                BOT_INSTANCE.send_json({"handler": "audioroom", "action": "leave", "roomId": room_id})
                
                pc = sessions[room_id].get('pc')
                if pc: asyncio.run(pc.close())
                del sessions[room_id]
                
        bot.send_message(room_id, "⏹️ DJ Stopped.")
        return True

    return False
