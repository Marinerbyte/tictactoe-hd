import random

def setup(bot):
    print("Basic Plugin Loaded")

def handle_command(bot, command, room_id, user, args, data): # <--- Added 'data'
    cmd = command.lower().strip()
    
    if cmd == "ping":
        bot.send_message(room_id, f"@{user} Pong!")
        return True

    if cmd == "roll":
        result = random.randint(1, 100)
        bot.send_message(room_id, f"@{user} rolled: {result}")
        return True
        
    return False
