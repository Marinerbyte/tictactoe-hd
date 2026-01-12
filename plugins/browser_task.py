import requests
import threading
import time
import os
from uuid import uuid4

# --- Plugin setup ---
TASK_SERVER_URL = "https://browser-server.onrender.com/task"  # Tumhare Render server URL
CLEANUP_INTERVAL = 300  # 5 minutes

# Plugin state
plugin_state = {"last_files": []}
state_lock = threading.Lock()

def cleanup_files():
    with state_lock:
        for f in plugin_state["last_files"]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except:
                    pass
        plugin_state["last_files"] = []

def start_cleanup_thread():
    def loop():
        while True:
            time.sleep(CLEANUP_INTERVAL)
            cleanup_files()
    t = threading.Thread(target=loop, daemon=True)
    t.start()

start_cleanup_thread()

# --- Helper functions ---
def call_browser_server(task_type, query):
    """
    Calls the browser-server /task API
    task_type: 'audio', 'image', 'text'
    query: search query
    """
    payload = {"type": task_type, "query": query}
    r = requests.post(TASK_SERVER_URL, json=payload, timeout=60)
    if r.status_code != 200:
        return {"error": r.text}
    return r.json()

def send_file_to_howdies(bot, room_id, file_path, text=""):
    """
    Upload file (mp3, image) to Howdies chat
    """
    # Tumhare HowdiesBot ke send_json/send_message structure ke hisab se
    with open(file_path, "rb") as f:
        file_data = f.read()
    # Simple implementation: Upload via existing bot method (adjust if API needs)
    bot.send_message(room_id, text)
    # Track file for cleanup
    with state_lock:
        plugin_state["last_files"].append(file_path)

# --- Plugin entry point ---
def handle_command(bot, command, room_id, user, args, data):
    """
    Standard handle_command signature
    command: str, e.g., '!play'
    args: list of args
    data: full raw data dict
    """
    if not command.startswith("!"):
        return False  # Not our command

    cmd = command[1:].lower()

    if cmd == "play" and args:
        query = " ".join(args)
        result = call_browser_server("audio", query)
        if "file" in result:
            send_file_to_howdies(bot, room_id, result["file"], text=f"🎵 {query}")
        else:
            bot.send_message(room_id, f"Could not find audio for '{query}'")
        return True

    elif cmd == "img" and args:
        query = " ".join(args)
        result = call_browser_server("image", query)
        if "file" in result:
            send_file_to_howdies(bot, room_id, result["file"], text=f"🖼️ {query}")
        else:
            bot.send_message(room_id, f"Could not find image for '{query}'")
        return True

    elif cmd == "info" and args:
        query = " ".join(args)
        result = call_browser_server("text", query)
        if "content" in result:
            bot.send_message(room_id, f"ℹ️ {result['content']}")
        else:
            bot.send_message(room_id, f"No info found for '{query}'")
        return True

    return False

# Optional: Add setup function if plugin_loader uses it
def setup(bot):
    print("[Plugin] browser_task loaded")
