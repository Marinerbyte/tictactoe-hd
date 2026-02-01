import sys
import os
import time
import asyncio
import threading
from aiortc import RTCPeerConnection, MediaPlayer
import music_utils # Humne jo abhi upar banaya

active_sessions = {}
session_lock = threading.Lock()

def setup(bot):
    print("[Music Pro] AIORTC Engine Active.")

def send_req(bot, action, room_id, data={}):
    payload = {"handler": "audioroom", "action": action, "roomId": str(room_id)}
    payload.update(data)
    bot.send_json(payload)

def run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

def handle_system_message(bot, data):
    if data.get("handler") != "audioroom": return
    msg_type = data.get("type")

    if msg_type == "transport-created":
        transports = data.get("transports", {})
        send_t = transports.get("send", {})
        room_id = next(iter(active_sessions)) if active_sessions else None

        if room_id and send_t:
            pc = RTCPeerConnection()
            with session_lock:
                active_sessions[room_id]['pc'] = pc
                url = active_sessions[room_id].get('url')
            
            if url:
                player = MediaPlayer(url)
                pc.addTrack(player.audio)
                with session_lock: active_sessions[room_id]['player'] = player
            
            async def connect():
                offer = await pc.createOffer()
                await pc.setLocalDescription(offer)
                fp = offer.sdp.split("fingerprint:sha-256 ")[1].split("\r\n")[0]
                
                send_req(bot, "connect-transport", room_id, {
                    "direction": "send",
                    "transportId": send_t.get("id"),
                    "dtlsParameters": {"role": "client", "fingerprints": [{"algorithm": "sha-256", "value": fp}]}
                })
                send_req(bot, "transports-ready", room_id)
                send_req(bot, "produce", room_id, {
                    "kind": "audio",
                    "rtpParameters": {"codecs": [{"mimeType": "audio/opus", "payloadType": 111, "clockRate": 48000, "channels": 2, "parameters": {"minptime": 10, "useinbandfec": 1}}], "encodings": [{"ssrc": 11111111}]},
                    "requestId": int(time.time() * 1000)
                })
            threading.Thread(target=run_async, args=(connect(),)).start()

    elif msg_type == "producer-created":
        print("[Music] ✅ LIVE!")

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()

    if cmd == "play":
        if not args: return True
        url = args[0]
        bot.send_message(room_id, "🎵 **Processing...**")
        
        def start():
            real_url, title = run_async(music_utils.get_stream_url(url))
            if real_url:
                bot.send_message(room_id, f"🎶 **Playing:** {title}")
                with session_lock: active_sessions[room_id] = {'url': real_url}
                send_req(bot, "join", room_id)
            else:
                bot.send_message(room_id, "❌ Audio error.")
        
        threading.Thread(target=start).start()
        return True

    if cmd == "stop":
        with session_lock:
            if room_id in active_sessions:
                s = active_sessions.pop(room_id)
                if s.get('player'): s['player'].stop()
                send_req(bot, "leave", room_id)
                bot.send_message(room_id, "⏹️ Stopped.")
        return True
    return False
