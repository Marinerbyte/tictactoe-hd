import requests
from datetime import datetime

def setup(bot):
    print("[Plugin] profile_dp loaded")

def fetch_profile(bot, username):
    url = f"https://api.howdies.app/api/profile/{username}"
    headers = {
        "Authorization": f"Bearer {bot.token}",
        "User-Agent": "Mozilla/5.0",
        "Origin": "https://howdies.app"
    }
    r = requests.get(url, headers=headers, timeout=10)
    if r.status_code == 200:
        return r.json()
    return None

def handle_command(bot, command, room_id, user, args):
    if command not in ("dp", "pro"):
        return False

    if not args:
        bot.send_message(room_id, f"Usage: !{command} <username>")
        return True

    username = args[0].lstrip("@")

    data = fetch_profile(bot, username)
    if not data:
        bot.send_message(room_id, f"Profile not found: @{username}")
        return True

    # ---- DP COMMAND ----
    if command == "dp":
        avatar = data.get("avatar") or data.get("avatarUrl") or data.get("photo")
        if not avatar:
            bot.send_message(room_id, f"@{username} has no profile photo.")
        else:
            bot.send_message(room_id, avatar)
        return True

    # ---- PROFILE COMMAND ----
    uid   = data.get("id", "—")
    uname = f"@{data.get('username', username)}"
    nick  = data.get("nickname") or "—"

    age    = data.get("age", "—")
    gender = data.get("gender", "—")
    loc    = data.get("location", "—")

    created_raw = data.get("createdAt")
    if created_raw:
        try:
            created = datetime.fromisoformat(created_raw[:10]).strftime("%d %B %Y")
        except:
            created = created_raw[:10]
    else:
        created = "—"

    status  = data.get("status") or "—"
    views   = data.get("views", 0)
    likes   = data.get("likes", 0)
    friends = data.get("friends", 0)

    lover = data.get("lover")
    lover = f"@{lover}" if lover else "—"

    msg = (
        f"🆔 User ID  : {uid}\n"
        f"👤 Username : {uname}\n"
        f"🪪 Nick     : {nick}\n"
        f"♂️ ASL      : {age}, {gender}, {loc}\n"
        f"📅 Created  : {created}\n\n"
        f"💬 Status   : {status}\n"
        f"👁️ Views    : {views}\n"
        f"👍 Likes    : {likes}\n\n"
        f"👥 Friends  : {friends}\n"
        f"❤️ Lover    : {lover}"
    )

    bot.send_message(room_id, msg)
    return True
