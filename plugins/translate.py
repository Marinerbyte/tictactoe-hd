from deep_translator import GoogleTranslator
import threading

# Global Memory to store who to translate
# Format: { 'room_id': { 'username': 'target_lang' } }
watched_users = {}
lock = threading.Lock()

def setup(bot):
    print("[Auto-Translate] Spy Mode Loaded!")

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    sender = data.get("username")
    text = data.get("text", "")
    
    # ==========================================
    # 1. COMMANDS: ADD/REMOVE USER (!atr / !rtr)
    # ==========================================
    
    # --- START AUTO TRANSLATE (!atr) ---
    if cmd in ["atr", "autotr"]:
        if not args:
            bot.send_message(room_id, "⚠️ Usage: `!atr @user [lang]`\nEx: `!atr @ali` (Default English)")
            return True
            
        target_user = args[0].replace("@", "")
        # Default target language is English ('en'), user can change it (e.g., 'hi')
        target_lang = args[1].lower() if len(args) > 1 else "en"
        
        with lock:
            if room_id not in watched_users:
                watched_users[room_id] = {}
            
            watched_users[room_id][target_user] = target_lang
            
        bot.send_message(room_id, f"👁️ **Monitoring:** @{target_user}\nTranslating to: **{target_lang.upper()}**")
        return True

    # --- STOP AUTO TRANSLATE (!rtr) ---
    if cmd in ["rtr", "stoptr"]:
        if not args:
            bot.send_message(room_id, "⚠️ Usage: `!rtr @user`")
            return True
            
        target_user = args[0].replace("@", "")
        
        with lock:
            if room_id in watched_users and target_user in watched_users[room_id]:
                del watched_users[room_id][target_user]
                bot.send_message(room_id, f"🛑 Stopped translating @{target_user}.")
            else:
                bot.send_message(room_id, "❌ User was not being translated.")
        return True

    # --- LIST WATCHED USERS (!trlist) ---
    if cmd == "trlist":
        with lock:
            users = watched_users.get(room_id, {})
        if users:
            msg = ", ".join([f"@{u} ({l})" for u, l in users.items()])
            bot.send_message(room_id, f"📝 **Active Translations:**\n{msg}")
        else:
            bot.send_message(room_id, "📝 No users are being translated.")
        return True

    # ==========================================
    # 2. THE LISTENER (Real-time Translation)
    # ==========================================
    
    # Check agar message sender "watched list" mein hai
    # Aur message command nahi hai (starts with !)
    is_watched = False
    target_lang = "en"
    
    with lock:
        if room_id in watched_users and sender in watched_users[room_id]:
            is_watched = True
            target_lang = watched_users[room_id][sender]
    
    # Agar watched user hai aur text normal chat hai (Command nahi)
    if is_watched and text and not text.startswith("!"):
        try:
            # Google Translate (Source = Auto Detect)
            translator = GoogleTranslator(source='auto', target=target_lang)
            translated_text = translator.translate(text)
            
            # Agar translation same hai (e.g. "Haha" -> "Haha"), to ignore karo
            if translated_text.lower() != text.lower():
                # Fast Text Reply (Image use nahi karenge taki chat fast rahe)
                reply = f"🗣️ **@{sender}:** {translated_text}"
                bot.send_message(room_id, reply)
                
        except Exception as e:
            print(f"[Auto-Tr Error] {e}")
            
        # Return False taaki baaki plugins bhi apna kaam kar sakein
        return False

    return False
