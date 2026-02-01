import sys
import os
import json
import time
import asyncio
import threading
from aiortc import RTCPeerConnection, MediaPlayer
import yt_dlp

# --- GLOBAL STATE ---
active_sessions = {}
session_lock = threading.Lock()

def setup(bot):
    print("[Music Pro] AIORTC Engine Loaded! (Real Streaming)")

# ==========================================
# 🎵 MUSIC PLAYER ENGINE
# ==========================================

async def start_ffmpeg_stream(url):
    options = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "quiet": True
    }
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)
            return info['url'], info.get('title', 'Audio Track')
    except Exception as e:
        print(f"[Music Error] {e}")
        return None, None

def send_req(bot, action, room_id, data={}):
    payload = {"handler": "audioroom", "action": action, "roomId": str(room_id)}
    payload.update(data)
    bot.send_json(payload)

def run_async(coro):
    try:
        loop = asyncio.get_event_loop()
    except:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

def handle_system_message(bot, data):
    if data.get("handler") != "audioroom": return
    msg_type = data.get("type")

    if msg_type == "transport-created":
        transports = data.get("transports", {})
        send_t = transports.get("send", {})
        
        room_id = None
        with session_lock:
            if active_sessions: room_id = list(active_sessions.keys())[0]

        if room_id and send_t:
            print(f"[Music] Starting Handshake...")
            pc = RTCPeerConnection()
            
            with session_lock:
                active_sessions[room_id]['pc'] = pc
                stream_url = active_sessions[room_id].get('stream_url')
            
            if stream_url:
                player = MediaPlayer(stream_url)
                pc.addTrack(player.audio)
                with session_lock: active_sessions[room_id]['player'] = player
            
            async def connect_flow():
                offer = await pc.createOffer()
                await pc.setLocalDescription(offer)
                
                # Fingerprint Extraction logic
                fp = offer.sdp.split("fingerprint:sha-256 ")[1].split("\r\n")[0]
                
                send_req(bot, "connect-transport", room_id, {
                    "direction": "send",
                    "transportId": send_t.get("id"),
                    "dtlsParameters": {
                        "role": "client",
                        "fingerprints": [{"algorithm": "sha-256", "value": fp}]
                    }
                })
                
                send_req(bot, "transports-ready", room_id)
                
                # Opus Parameters
                send_req(bot, "produce", room_id, {
                    "kind": "audio",
                    "rtpParameters": {
                        "codecs": [{
                            "mimeType": "audio/opus",
                            "payloadType": 111,
                            "clockRate": 48000,
                            "channels": 2,
                            "parameters": { "minptime": 10, "useinbandfec": 1 }
                        }],
                        "encodings": [{ "ssrc": 11111111 }]
                    },
                    "requestId": int(time.time() * 1000)
                })
                print("[Music] Handshake Sent.")

            threading.Thread(target=run_async, args=(connect_flow(),)).start()

    elif msg_type == "producer-created":
        print("[Music] ✅ Stream is LIVE!")

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()

    if cmd == "play":
        if not args:
            bot.send_message(room_id, "Usage: `!play <url>`")
            return True
        
        url = args[0]
        bot.send_message(room_id, "🔍 **Processing Audio...**")
        
        def process():
            real_url, title = run_async(start_ffmpeg_stream(url))
            if not real_url:
                bot.send_message(room_id, "❌ Error loading audio.")
                return
            
            bot.send_message(room_id, f"🎵 **Joining:** {title}")
            with session_lock:
                active_sessions[room_id] = {'stream_url': real_url}
            send_req(bot, "join", room_id)
            
        threading.Thread(target=process).start()
        return True

    if cmd == "stop":
        with session_lock:
            if room_id in active_sessions:
                s = active_sessions[room_id]
                if s.get('player'): s['player'].stop()
                if s.get('pc'): run_async(s['pc'].close())
                del active_sessions[room_id]
                send_req(bot, "leave", room_id)
                bot.send_message(room_id, "⏹️ Stopped.")
        return True
    return False
