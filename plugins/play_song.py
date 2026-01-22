import requests
from utils import run_in_bg

SERVER_A_URL = "https://song-1x9x.onrender.com"  # Tumhara Render server

def setup(bot):
    bot.log("[Plugin] Play Song plugin loaded.")

def handle_command(bot, cmd, room_id, user, args, raw_data):
    if cmd.lower() != "play":
        return False

    if not args:
        bot.send_message(room_id, f"@{user} Usage: !play <song name>")
        return True

    song_name = " ".join(args)
    bot.send_message(room_id, f"@{user} Searching for '{song_name}'... 🎵")
    run_in_bg(fetch_and_send, bot, room_id, user, song_name)
    return True

def fetch_and_send(bot, room_id, user, song_name):
    try:
        resp = requests.post(f"{SERVER_A_URL}/api/search", json={"query": song_name}, timeout=15)
        if resp.status_code != 200:
            bot.send_message(room_id, f"@{user} Error fetching song. Try again later.")
            return

        data = resp.json()
        if not data.get("url"):
            bot.send_message(room_id, f"@{user} No results found for '{song_name}'.")
            return

        audio_url = SERVER_A_URL + data["url"]
        message = f"🎵 **{song_name}**\n[▶️ Play]({audio_url})"
        bot.send_message(room_id, message)

    except Exception as e:
        bot.send_message(room_id, f"@{user} Something went wrong: {str(e)}")
