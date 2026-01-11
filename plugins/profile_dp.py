import requests

API_PROFILE = "https://api.howdies.app/api/user/{}"
API_AVATAR = "https://api.howdies.app/api/user/{}/avatar"


def setup(bot):
    print("[Plugin] profile_dp loaded")


def handle_command(bot, command, room_id, user, args):
    command = command.lower()

    if command not in ("dp", "pro"):
        return False

    if not args:
        bot.send_message(room_id, "❌ Usage: !dp username  |  !pro username")
        return True

    username = args[0].lstrip("@")

    try:
        # 1️⃣ Fetch profile
        r = requests.get(API_PROFILE.format(username), timeout=10)

        if r.status_code != 200:
            bot.send_message(room_id, f"❌ User `{username}` not found.")
            return True

        data = r.json()

        user_id = data.get("id")
        if not user_id:
            bot.send_message(room_id, "❌ User ID not available.")
            return True

        # 2️⃣ DP command
        if command == "dp":
            avatar_url = f"https://cdn.howdies.app/avatar/{user_id}.jpg"

            bot.send_message(
                room_id,
                f"🖼 Avatar for @{username}\n{avatar_url}"
            )
            return True

        # 3️⃣ PRO command
        profile = (
            f"🆔 User ID  : {user_id}\n"
            f"👤 Username : @{username}\n"
            f"🪪 Nick     : {data.get('nickname', '—')}\n"
            f"♂️ ASL      : {data.get('age', '—')}, {data.get('gender', '—')}, {data.get('country', '—')}\n"
            f"📅 Created  : {data.get('created', '—')}\n\n"
            f"💬 Status   : {data.get('status', '—')}\n"
            f"👁️ Views    : {data.get('views', 0)}\n"
            f"👍 Likes    : {data.get('likes', 0)}\n\n"
            f"👥 Friends  : {data.get('friends', 0)}\n"
            f"❤️ Lover    : {data.get('lover', '—')}\n"
        )

        bot.send_message(room_id, profile)
        return True

    except Exception as e:
        bot.send_message(room_id, f"⚠️ Error: {str(e)}")
        return True
