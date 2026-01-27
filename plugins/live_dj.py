import asyncio
import threading
import uuid
import fractions

from aiortc import RTCPeerConnection, RTCRtpSender
from aiortc.mediastreams import AudioStreamTrack
from av.audio.frame import AudioFrame
import av
import numpy as np

# ======================================================
# GLOBAL
# ======================================================
BOT = None
sessions = {}

# ======================================================
# AUDIO TRACK (FILE → RTP AUDIO)
# ======================================================

class FileAudioTrack(AudioStreamTrack):
    kind = "audio"

    def __init__(self, filepath):
        super().__init__()
        self.container = av.open(filepath)
        self.stream = self.container.streams.audio[0]

    async def recv(self):
        frame = next(self.container.decode(self.stream))
        frame.pts = None
        return frame


# ======================================================
# SETUP
# ======================================================

def setup(bot):
    global BOT
    BOT = bot
    print("[DJ] Producer system ready")


# ======================================================
# WEBRTC PRODUCER SESSION
# ======================================================

async def run_dj_producer(room_id, audio_path):
    pc = RTCPeerConnection()

    # -----------------------------
    # 1. JOIN ROOM
    # -----------------------------
    BOT.send_json({
        "handler": "audioroom",
        "action": "join",
        "roomId": room_id
    })

    # -----------------------------
    # 2. WAIT FOR TRANSPORT
    # -----------------------------
    transport_event = asyncio.Event()
    transport_data = {}

    def on_transport_created(data):
        transport_data.update(data)
        transport_event.set()

    BOT.on("audioroom.transport-created", on_transport_created)
    await transport_event.wait()

    send_transport = transport_data["transports"]["send"]
    rtp_caps = transport_data["routerRtpCapabilities"]

    # -----------------------------
    # 3. CONNECT TRANSPORT (DTLS)
    # -----------------------------
    BOT.send_json({
        "handler": "audioroom",
        "action": "connect-transport",
        "roomId": room_id,
        "direction": "send",
        "transportId": send_transport["id"],
        "dtlsParameters": send_transport["dtlsParameters"]
    })

    # -----------------------------
    # 4. ADD AUDIO TRACK
    # -----------------------------
    track = FileAudioTrack(audio_path)
    sender = pc.addTrack(track)

    # RTP parameters from aiortc
    params = sender.getParameters()

    # -----------------------------
    # 5. PRODUCE AUDIO
    # -----------------------------
    request_id = str(uuid.uuid4())

    BOT.send_json({
        "handler": "audioroom",
        "action": "produce",
        "roomId": room_id,
        "kind": "audio",
        "rtpParameters": {
            "codecs": [
                {
                    "mimeType": "audio/opus",
                    "clockRate": 48000,
                    "channels": 2,
                    "payloadType": 111
                }
            ],
            "headerExtensions": [],
            "encodings": [{"ssrc": 11111111}],
            "rtcp": {"cname": "dj-bot"}
        },
        "requestId": request_id
    })

    print("[DJ] Producing audio 🎶")

    await asyncio.Event().wait()


# ======================================================
# COMMAND HANDLER
# ======================================================

def handle_command(bot, command, room_id, user, args, data):
    if command.lower() != "dj":
        return False

    audio_path = "sample.mp3"  # already downloaded

    def runner():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_dj_producer(room_id, audio_path))

    threading.Thread(target=runner, daemon=True).start()
    bot.send_message(room_id, "🎧 DJ started (producer mode)")
    return True
