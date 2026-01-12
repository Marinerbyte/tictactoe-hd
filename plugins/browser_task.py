import requests
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import uuid

# Browser server URL
BROWSER_SERVER_URL = "https://browser-server.onrender.com/scrape"

# System font (Linux)
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

def setup(bot):
    bot.log("[BrowserTasks] Plugin loaded with image/meme/audio features.")

def handle_command(bot, cmd, room_id, user, args, data):

    # --- Command 1: !browse [url] ---
    if cmd.lower() == "browse" and args:
        url = args[0]
        bot.log(f"[BrowserTasks] {user} requested browsing {url}")
        try:
            response = requests.post(BROWSER_SERVER_URL, json={"url": url}, timeout=15)
            result = response.json().get("html", "")
            snippet = result[:300] + ("..." if len(result) > 300 else "")
            bot.send_message(room_id, f"{user}, snippet from {url}:\n{snippet}")
        except Exception as e:
            bot.send_message(room_id, f"Error fetching {url}: {e}")
        return True

    # --- Command 2: !wiki [term] ---
    elif cmd.lower() == "wiki" and args:
        term = "_".join(args)
        url = f"https://en.wikipedia.org/wiki/{term}"
        bot.log(f"[BrowserTasks] {user} requested wiki page {term}")
        try:
            response = requests.post(BROWSER_SERVER_URL, json={"url": url}, timeout=15)
            html = response.json().get("html", "")
            start = html.find("<p>")
            end = html.find("</p>", start)
            snippet = html[start+3:end] if start != -1 and end != -1 else "No summary found."
            snippet = snippet[:300] + ("..." if len(snippet) > 300 else "")
            bot.send_message(room_id, f"{user}, Wikipedia summary for {term}:\n{snippet}")
        except Exception as e:
            bot.send_message(room_id, f"Error fetching wiki for {term}: {e}")
        return True

    # --- Command 3: !avatar [username] ---
    elif cmd.lower() == "avatar" and args:
        target_user = args[0]
        bot.log(f"[BrowserTasks] {user} requested avatar of {target_user}")
        try:
            avatar_url = data.get("avatar") or f"https://api.adorable.io/avatars/150/{target_user}.png"
            resp = requests.get(avatar_url)
            img = Image.open(BytesIO(resp.content)).convert("RGBA")
            draw = ImageDraw.Draw(img)
            font = ImageFont.truetype(FONT_PATH, 20)
            draw.text((10, 10), f"{target_user}'s Avatar", font=font, fill=(255,255,255,255))
            buf = BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            files = {"file": ("avatar.png", buf, "image/png")}
            upload_resp = requests.post("https://api.howdies.app/api/upload", files=files).json()
            url = upload_resp.get("url", "Upload failed")
            bot.send_message(room_id, f"{user}, here’s the avatar: {url}")
        except Exception as e:
            bot.send_message(room_id, f"Error generating avatar image: {e}")
        return True

    # --- Command 4: !meme [text] ---
    elif cmd.lower() == "meme" and args:
        text = " ".join(args)
        bot.log(f"[BrowserTasks] {user} requested meme with text: {text}")
        try:
            img = Image.new("RGB", (400, 200), color=(0,0,0))
            draw = ImageDraw.Draw(img)
            font = ImageFont.truetype(FONT_PATH, 24)
            draw.text((10, 80), text, font=font, fill=(255,255,0))
            buf = BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            files = {"file": ("meme.png", buf, "image/png")}
            upload_resp = requests.post("https://api.howdies.app/api/upload", files=files).json()
            url = upload_resp.get("url", "Upload failed")
            bot.send_message(room_id, f"{user}, here’s your meme: {url}")
        except Exception as e:
            bot.send_message(room_id, f"Error generating meme image: {e}")
        return True

    # --- Command 5: !song [url] ---
    elif cmd.lower() == "song" and args:
        song_url = args[0]  # Example: direct MP3 URL
        bot.log(f"[BrowserTasks] {user} requested song: {song_url}")
        try:
            # Fetch MP3 bytes
            resp = requests.get(song_url)
            mp3_bytes = BytesIO(resp.content)

            # Upload to Howdies
            files = {"file": ("song.mp3", mp3_bytes, "audio/mpeg")}
            upload_resp = requests.post("https://api.howdies.app/api/upload", files=files).json()
            url = upload_resp.get("url", None)
            if url:
                # Send as audio type for play button
                bot.send_json({
                    "handler": "chatroommessage",
                    "id": uuid.uuid4().hex,
                    "type": "audio",
                    "roomid": room_id,
                    "text": "",
                    "url": url,
                    "length": "0"
                })
            else:
                bot.send_message(room_id, f"Failed to upload song.")
        except Exception as e:
            bot.send_message(room_id, f"Error sending song: {e}")
        return True

    return False
