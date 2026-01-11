import random

def setup(bot):
    print("Basic Plugin Loaded")

def handle_command(bot, command, room_id, user, args):
    """
    Returns True if command is handled.
    """
    
    if command == "ping":
        bot.send_message(room_id, f"@{user} Pong!")
        return True

    if command == "roll":
        result = random.randint(1, 100)
        bot.send_message(room_id, f"@{user} rolled: {result}")
        return True
        
    if command == "join":
        # Master only command example
        # In a real scenario, check user against a master list in DB
        if user == bot.user_data.get('username'):
            if args:
                bot.join_room(args[0])
                bot.send_message(room_id, f"Joining {args[0]}...")
            return True

    return False
