import sys
import os
import time
import asyncio
import threading
import json
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaPlayer 
import music_utils

# --- GLOBAL STATE ---
# { roomId: { 'pc': RTCPeerConnection, 'player': MediaPlayer, 'url': str } }
active_sessions = {}
session_lock = threading.Lock()

def setup(bot):
    print("[Music Pro] DJ Engine with Search Active.")

# ==========================================
# 📡 SIGNALING BRIDGE
# ==========================================

def send_req(bot, action, room_id, data={}):
    """Howdies Audio Protocol Envelope"""
    payload = {
        "handler": "audioroom",
        "action": action,
        "roomId": str(room_id)
    }
    bot.send_json(payload)

def run_async(coro):
    """Sync bot ko Async AIORTC se jodne ke liye"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

# ==========================================
# 🧠 SYSTEM MESSAGE HANDLER (Signalling)
# ==========================================

def handle_system_message(bot, data):
    """Bot Engine se aane wale signals ko handle karta hai"""
    if data.get("handler") != "audioroom": 
        return
        
    msg_type = data.get("type")
    
    # 1. SERVER GAVE TRANSPORTS
    if msg_type == "transport-created":
        transports = data.get("transports", {})
        send_t = transports.get("send", {})
        
        room_id = None
        with session_lock:
            if active_sessions:
                for rid, s in active_sessions.items():
                    if 'pc' not in s:
                        room_id = rid
                        break

        if room_id and send_t:
            print(f"[Audio] Handshake initiated for Room: {room_id}")
            pc = RTCPeerConnection()
            
            with session_lock:
                active_sessions[room_id]['pc'] = pc
                stream_url = active_sessions[room_id].get('url')
            
            if stream_url:
                try:
                    player = MediaPlayer(stream_url)
                    if player and player.audio:
                        pc.addTrack(player.audio)
                        with session_lock:
                            active_sessions[room_id]['player'] = player
                except Exception as e:
                    print(f"[Audio Error] Player Init: {e}")

            async def connect_sequence():
                offer = await pc.createOffer()
                await pc.setLocalDescription(offer)
                
                sdp = pc.localDescription.sdp
                fp = sdp.split("fingerprint:sha-256 ")[1].split("\r\n")[0]
                
                send_req(bot, "connect-transport", room_id, {
                    "direction": "send",
                    "transportId": send_t.get("id"),
                    "dtlsParameters": {
                        "role": "client",
                        "fingerprints": [{"algorithm": "sha-256", "value": fp}]
                    }
                })
                send_req(bot, "transports-ready", room_id)
                send_req(bot, "produce", room_id, {
                    "kind": "audio",
                    "rtpParameters": {
                        "codecs": [{"mimeType": "audio/opus", "payloadType": 111, "clockRate": 48000, "channels": 2, "parameters": { "minptime": 10, "useinbandfec": 1 }}],
                        "encodings": [{"ssrc": 11111111 }]
                    },
                    "requestId": int(time.time() * 1000)
                })
                print(f"[Audio] ✅ Handshake Complete for {room_id}")

            threading.Thread(target=run_async, args=(connect_sequence(),)).start()

    elif msg_type == "producer-created":
        print("[Audio] 🎶 Music is now Streaming Live!")

# ==========================================
# 🎮 USER COMMANDS
# ==========================================

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()

    # --- !play <Gane ka Naam ya URL> ---
    if cmd == "play":
        if not args:
            bot.send_message(room_id, "⚠️ Kya bajana hai? Naam likho.\nExample: `!play fitoor song`")
            return True
        
        query = " ".join(args)
        bot.send_message(room_id, f"🔍 Searching: **{query}**...")
        
        def start_playback():
            real_url, title = run_async(music_utils.get_stream_url(query))
            if not real_url:
                bot.send_message(room_id, f"❌ '{query}' nahi mila.")
                return

            bot.send_message(room_id, f"🎵 **Joining Stage:** {title}")
            
            with session_lock:
                active_sessions[room_id] = {'url': real_url}
            
            send_req(bot, "join", room_id)

        threading.Thread(target=start_playback).start()
        return True

    # --- !stop ---
    if cmd == "stop":
        with session_lock:
            if room_id in active_sessions:
                s = active_sessions.pop(room_id, None)
                if s and 'player' in s and s['player']:
                    s['player'].stop()
                if s and 'pc' in s and s['pc']:
                    threading.Thread(target=run_async, args=(s['pc'].close(),)).start()
                
                send_req(bot, "leave", room_id)
                bot.send_message(room_id, "⏹️ Music Stopped and Left Stage.")
            else:
                bot.send_message(room_id, "❌ Bot is not on stage.")
        return True

    return False
