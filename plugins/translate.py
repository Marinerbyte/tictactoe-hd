from deep_translator import GoogleTranslator
import threading
import time

# --- GLOBAL MEMORY ---
watched_users = {} # { 'room_id': { 'username': 'target_language' } }
immunity_list = {} # { 'username': expiry_timestamp } (Jo !rme use karega)

lock = threading.Lock()

# --- CONSTANTS ---
MIN_TIME = 60
MAX_TIME = 300
IMMUNITY_DURATION = 300 # 5 Minutes

# --- LANGUAGE MAP ---
LANG_MAP = {
    "en": "english", "eng": "english",
    "hi": "hindi",   "hin": "hindi",
    "ur": "urdu",    "urd": "urdu",
    "pa": "punjabi", "pun": "punjabi",
    "bn": "bengali", "ben": "bengali",
    "mr": "marathi", "mar": "marathi",
    "ar": "arabic",  "ara": "arabic",
    "fr": "french",  "fre": "french",
    "es": "spanish", "spa": "spanish",
    "ru": "russian", "rus": "russian",
}

def setup(bot):
    print("[Auto-Translate] Pro Version (Timer + Privacy) Loaded!")

def get_full_lang_name(code):
    return LANG_MAP.get(code.lower().strip(), code)

def auto_stop_task(bot, room_id, username):
    """Timer khatam hone par chalega"""
    with lock:
        if room_id in watched_users and username in watched_users[room_id]:
            del watched_users[room_id][username]
            try:
                bot.send_message(room_id, f"⏰ **Time Up!** Stopped spying on @{username}.")
            except: pass

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    sender = data.get("username")
    text = data.get("text", "")
    current_time = time.time()
    
    # ==========================================
    # 1. COMMANDS
    # ==========================================
    
    # --- START (!atr user [lang] [time]) ---
    if cmd in ["atr", "autotr"]:
        if not args:
            bot.send_message(room_id, "⚠️ **Usage:** `!atr @user [lang] [time]`\nEx: `!atr @yasin hin 120`")
            return True
            
        target_user = args[0].replace("@", "")
        
        # 🛡️ CHECK IMMUNITY (Agar user ne !rme dabaya tha)
        with lock:
            if target_user in immunity_list:
                expiry = immunity_list[target_user]
                if current_time < expiry:
                    remaining = int(expiry - current_time)
                    bot.send_message(room_id, f"🛡️ **Access Denied:** @{target_user} ne privacy mode on kiya hai. ({remaining}s left)")
                    return True
                else:
                    del immunity_list[target_user] # Expired, remove from list

        # Parsing Arguments
        target_lang = "english"
        duration = MIN_TIME # Default 60s
        
        # Logic to find Lang and Time in arguments
        # Args can be: ['hin'], ['120'], ['hin', '120'], ['120', 'hin']
        for arg in args[1:]:
            if arg.isdigit():
                duration = int(arg)
            else:
                target_lang = get_full_lang_name(arg)
        
        # ⏱️ CLAMP TIME (60s to 300s)
        if duration < MIN_TIME: duration = MIN_TIME
        if duration > MAX_TIME: duration = MAX_TIME
        
        # Check Lang Validity
        try:
            GoogleTranslator(source='auto', target=target_lang)
        except:
            bot.send_message(room_id, f"❌ Invalid Language: {target_lang}")
            return True
        
        with lock:
            if room_id not in watched_users: watched_users[room_id] = {}
            watched_users[room_id][target_user] = target_lang
            
        bot.send_message(room_id, f"👁️ **Spying:** @{target_user} ({target_lang.upper()})\n⏳ Timer: **{duration}s**")
        
        # Start Background Timer
        t = threading.Timer(duration, auto_stop_task, args=[bot, room_id, target_user])
        t.daemon = True
        t.start()
        return True

    # --- PRIVACY SHIELD (!rme) ---
    if cmd == "rme": # Remove Me
        # Check if user is being watched
        was_watched = False
        with lock:
            if room_id in watched_users and sender in watched_users[room_id]:
                del watched_users[room_id][sender]
                was_watched = True
            
            # Add to Immunity List (for 5 mins)
            immunity_list[sender] = current_time + IMMUNITY_DURATION
            
        if was_watched:
            bot.send_message(room_id, f"🛑 **Privacy On:** @{sender} ne tracking band kar di.\n🛡️ **Immune** for 5 minutes.")
        else:
            bot.send_message(room_id, f"🛡️ **Privacy Shield Active!** Koi aapko agle 5 min tak track nahi kar payega.")
        return True

    # --- MANUAL STOP (!rtr user) ---
    if cmd in ["rtr", "stoptr"]:
        if not args: return True
        target_user = args[0].replace("@", "")
        with lock:
            if room_id in watched_users and target_user in watched_users[room_id]:
                del watched_users[room_id][target_user]
                bot.send_message(room_id, f"🛑 Stopped translation for @{target_user}.")
            else:
                bot.send_message(room_id, "❌ User not tracked.")
        return True

    # ==========================================
    # 2. LISTENER
    # ==========================================
    is_watched = False
    target_lang = "english"
    
    with lock:
        if room_id in watched_users and sender in watched_users[room_id]:
            is_watched = True
            target_lang = watched_users[room_id][sender]
    
    if is_watched and text and not text.startswith("!"):
        try:
            if text.isdigit() or len(text) < 2: return False
            translator = GoogleTranslator(source='auto', target=target_lang)
            translated_text = translator.translate(text)
            if translated_text and translated_text.lower() != text.lower():
                reply = f"🗣️ **@{sender}:** {translated_text}"
                bot.send_message(room_id, reply)
        except: pass
        return False

    return False
