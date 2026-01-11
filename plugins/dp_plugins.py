def setup(bot):
    print("[Plugin] dp_plugin loaded!")

def handle_command(bot, command, room_id, user, args, avatar_url=None):
    if command.lower() == "dp":
        if not args:
            bot.send_message(room_id, "Usage: !dp <username>")
            return True
        
        target_user = args[0]
        
        # Check if user is in current messages (simple version)
        # Bot ka user_data ya game engine me nahi hai, to hum assume current session me avatar known nahi
        # Better: Agar tumhare paas kisi user ka avatar URL cache hai to wahan se fetch kar sakte ho

        # For now: agar command user ne khud diya to avatar_url dikhao
        if target_user.lower() == user.lower():
            if avatar_url:
                bot.send_message(room_id, f"{user}'s avatar URL: {avatar_url}")
            else:
                bot.send_message(room_id, f"{user} has no avatar URL!")
        else:
            # Placeholder: dusre user ka avatar agar cache ya DB me hai tabhi fetch karo
            bot.send_message(room_id, f"Avatar URL for {target_user} not available.")
        return True
    return False
