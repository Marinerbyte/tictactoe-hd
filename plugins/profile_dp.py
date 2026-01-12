import requests

# Howdies endpoints (reference bot style)
USER_API = "https://api.howdies.app/api/user/{}"
AVATAR_CDN = "https://cdn.howdies.app/avatar?image={}"

def setup(bot):
    pass


def fetch_user(username):
    """
    Reference bot logic:
    direct username → API call
    """
    try:
        r = requests.get(USER_API.format(username), timeout=10)
        if r.status_code != 200:
            return None
        data = r.json()
        return data.get("data") or data
    except Exception:
        return None


def handle_command(bot, command, room_id, user, args):
    command = command.lower()

    if command not in ("dp", "pro"):
        return False

    if not args:
        bot.send_message(room_id, "❌ Username missing")
        return True

    username = args[0].lstrip("@")

    data = fetch_user(username)
    if not data:
        bot.send_message(room_id, f"❌ User not found: @{username}")
        return True

    # ---------------- DP ----------------
    if command == "dp":
        avatar = data.get("avatar")
        if not avatar:
            bot.send_message(room_id, f"❌ @{username} has no profile picture")
            return True

        avatar_url = AVATAR_CDN.format(avatar)
        bot.send_message(room_id, avatar_url)
        return True

    # ---------------- PROFILE ----------------
    if command == "pro":
        msg = (
            f"🆔 User ID  : {data.get('id', '—')}\n"
            f"👤 Username : @{data.get('username', '—')}\n"
            f"🪪 Nick     : {data.get('nickname', '—')}\n"
            f"♂️ ASL      : {data.get('age', '—')}, {data.get('gender', '—')}, {data.get('country', '—')}\n"
            f"📅 Created  : {data.get('created_at', '—')}\n\n"
            f"💬 Status   : {data.get('status', '—')}\n"
            f"👁️ Views    : {data.get('views', 0)}\n"
            f"👍 Likes    : {data.get('likes', 0)}\n\n"
            f"👥 Friends  : {data.get('friends', 0)}\n"
            f"❤️ Lover    : @{data.get('lover', '—')}\n\n"
            f"🎁 Received : {data.get('gifts_received', 0)}\n"
            f"🎁 Sent     : {data.get('gifts_sent', 0)}"
        )

        bot.send_message(room_id, msg)
        return True
