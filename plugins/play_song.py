import requests
from utils import run_in_bg

SERVER_A_URL = "https://song-1x9x.onrender.com"  # Tumhara Server A

def setup(bot):
    """Plugin registration"""
    bot.log("[Plugin] Play Song plugin loaded.")

# ------------------------------
# COMMAND HANDLER
# ------------------------------
def handle_command(bot, cmd, room_id, user, args, raw_data):
    """
    Chat me !play <song name> command se trigger hoga
    """
    if cmd.lower() != "play":
        return False  # ignore

    if not args:
        bot.send_message(room_id, f"@{user} Usage: !play <song name>")
        return True

    song_name = " ".join(args)
    bot.send_message(room_id, f"@{user} Searching for '{song_name}'... 🎵")

    # Run in background
    run_in_bg(fetch_and_send, bot, room_id, user, song_name)
    return True

# ------------------------------
# CORE FUNCTION
# ------------------------------
def fetch_and_send(bot, room_id, user, song_name):
    try:
        # 1️⃣ Server A ko search query bhejo
        resp = requests.post(f"{SERVER_A_URL}/api/search", json={"query": song_name}, timeout=15)
        if resp.status_code != 200:
            bot.send_message(room_id, f"@{user} Error fetching song. Try again later.")
            return

        data = resp.json()
        # Assume server A returns {"url": "/audio/song123.mp3"}
        if not data.get("url"):
            bot.send_message(room_id, f"@{user} No results found for '{song_name}'.")
            return

        audio_url = SERVER_A_URL + data["url"]

        # 2️⃣ Send message with play button style
        bot.send_message(room_id, f"@{user} 🎵 Here’s your song!\n{audio_url}")

    except Exception as e:
        bot.send_message(room_id, f"@{user} Something went wrong: {str(e)}")
