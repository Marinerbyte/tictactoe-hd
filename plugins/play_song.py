import requests
from utils import run_in_bg

# Render server jahan yt-dlp backend chal raha hai
SERVER_URL = "https://song-1x9x.onrender.com"  # apna deploy URL

def setup(bot):
    bot.log("[Plugin] Play Song Final plugin loaded.")

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
        # Server se request: yt-dlp backend API
        resp = requests.post(f"{SERVER_URL}/api/search", json={"query": song_name}, timeout=30)
        if resp.status_code != 200:
            bot.send_message(room_id, f"@{user} Error fetching song. Try again later.")
            return

        data = resp.json()
        if not data.get("url"):
            bot.send_message(room_id, f"@{user} No results found for '{song_name}'.")
            return

        audio_url = SERVER_URL + data["url"]
        thumbnail = data.get("thumbnail") or ""

        # Howdies style audio message
        message = f"@{user} 🎵 **{song_name}**\n[▶️ Play]({audio_url})"
        if thumbnail:
            message += f"\n![thumbnail]({thumbnail})"

        bot.send_message(room_id, message)

    except Exception as e:
        bot.send_message(room_id, f"@{user} Something went wrong: {str(e)}")
