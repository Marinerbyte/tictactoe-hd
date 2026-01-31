from deep_translator import GoogleTranslator
import threading
import time
import traceback

# --- GLOBAL MEMORY ---
watched_users = {} 
immunity_list = {} 
lock = threading.Lock()

# --- CONSTANTS ---
MIN_TIME = 60
MAX_TIME = 300
IMMUNITY_DURATION = 300 

# --- LANGUAGE MAP (Codes Fixed) ---
# Library ko 'hi', 'en', 'ur' pasand hai, 'hindi' nahi.
LANG_MAP = {
    # Hindi
    "hindi": "hi",  "hin": "hi", "hi": "hi",
    # English
    "english": "en", "eng": "en", "en": "en",
    # Urdu
    "urdu": "ur", "urd": "ur", "ur": "ur",
    # Punjabi
    "punjabi": "pa", "pun": "pa", "pa": "pa",
    # Marathi
    "marathi": "mr", "mar": "mr", "mr": "mr",
    # Bengali
    "bengali": "bn", "ben": "bn", "bn": "bn",
    # Gujarati
    "gujarati": "gu", "guj": "gu", "gu": "gu",
    # Tamil
    "tamil": "ta", "tam": "ta", "ta": "ta",
    # Telugu
    "telugu": "te", "tel": "te", "te": "te",
    # Arabic
    "arabic": "ar", "ara": "ar", "ar": "ar",
    # French
    "french": "fr", "fre": "fr", "fr": "fr",
    # Spanish
    "spanish": "es", "spa": "es", "es": "es",
    # Russian
    "russian": "ru", "rus": "ru", "ru": "ru",
}

def setup(bot):
    print("[Auto-Translate] Fixed Version Loaded!")

def get_lang_code(user_input):
    """Input se sahi Google Code nikalta hai"""
    clean_input = user_input.lower().strip()
    return LANG_MAP.get(clean_input, clean_input)

def auto_stop_task(bot, room_id, username):
    with lock:
        if room_id in watched_users and username in watched_users[room_id]:
            del watched_users[room_id][username]
            try:
                bot.send_message(room_id, f"⏰ **Time Up!** Auto-translate stopped for @{username}.")
            except: pass

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    sender = data.get("username")
    text = data.get("text", "")
    current_time = time.time()
    
    # ==========================================
    # 1. COMMANDS
    # ==========================================
    
    if cmd in ["atr", "autotr"]:
        if not args:
            bot.send_message(room_id, "⚠️ Usage: `!atr @user [lang] [time]`")
            return True
            
        target_user = args[0].replace("@", "")
        
        # Check Immunity
        with lock:
            if target_user in immunity_list:
                if current_time < immunity_list[target_user]:
                    bot.send_message(room_id, f"🛡️ **Failed:** @{target_user} has Privacy Shield ON.")
                    return True
                else:
                    del immunity_list[target_user]

        # Defaults
        target_code = "en"
        duration = MIN_TIME
        
        # Parse Args
        for arg in args[1:]:
            if arg.isdigit():
                duration = int(arg)
            else:
                target_code = get_lang_code(arg)
        
        # Clamp Time
        if duration < MIN_TIME: duration = MIN_TIME
        if duration > MAX_TIME: duration = MAX_TIME
        
        # Test Language
        try:
            # Test with a dummy word
            GoogleTranslator(source='auto', target=target_code).translate("test")
        except Exception as e:
            bot.send_message(room_id, f"❌ Error: Language code **'{target_code}'** not supported.\nTry: `hi`, `en`, `ur`.")
            print(f"Lang Check Error: {e}")
            return True
        
        with lock:
            if room_id not in watched_users: watched_users[room_id] = {}
            watched_users[room_id][target_user] = target_code
            
        bot.send_message(room_id, f"👁️ **Spying:** @{target_user} (Target: {target_code.upper()})\n⏳ Timer: {duration}s")
        
        t = threading.Timer(duration, auto_stop_task, args=[bot, room_id, target_user])
        t.daemon = True
        t.start()
        return True

    if cmd == "rme":
        with lock:
            if room_id in watched_users and sender in watched_users[room_id]:
                del watched_users[room_id][sender]
            immunity_list[sender] = current_time + IMMUNITY_DURATION
        bot.send_message(room_id, f"🛡️ **Privacy Shield Active:** You are safe for 5 mins.")
        return True

    if cmd in ["rtr", "stoptr"]:
        if not args: return True
        target_user = args[0].replace("@", "")
        with lock:
            if room_id in watched_users and target_user in watched_users[room_id]:
                del watched_users[room_id][target_user]
                bot.send_message(room_id, f"🛑 Stopped tracking @{target_user}.")
            else:
                bot.send_message(room_id, "❌ User not tracked.")
        return True

    # ==========================================
    # 2. LISTENER
    # ==========================================
    
    # Check if user is watched
    is_watched = False
    target_code = "en"
    
    with lock:
        if room_id in watched_users and sender in watched_users[room_id]:
            is_watched = True
            target_code = watched_users[room_id][sender]
    
    if is_watched and text and not text.startswith("!"):
        try:
            if text.isdigit() or len(text) < 2: return False
            
            translator = GoogleTranslator(source='auto', target=target_code)
            res = translator.translate(text)
            
            if res and res.lower() != text.lower():
                bot.send_message(room_id, f"🗣️ **@{sender}:** {res}")
                
        except Exception as e:
            print(f"Trans Error: {e}")
            # Agar baar baar error aaye to auto-stop kar do
            with lock:
                if room_id in watched_users and sender in watched_users[room_id]:
                    del watched_users[room_id][sender]
            bot.send_message(room_id, f"⚠️ Translation Error. Tracking stopped for @{sender}.")
            
        return False

    return False
