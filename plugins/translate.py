from deep_translator import GoogleTranslator
import threading
import time

# --- GLOBAL MEMORY ---
# Format: { 'room_id': { 'username': 'target_language' } }
watched_users = {}
lock = threading.Lock()

# --- SETTINGS ---
TIMEOUT_SECONDS = 60  # Kitni der baad band hona chahiye

# --- CUSTOM SHORTCUTS MAPPING ---
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
    print("[Auto-Translate] Safe-Mode with Timer Loaded!")

def get_full_lang_name(code):
    code = code.lower().strip()
    return LANG_MAP.get(code, code)

# --- BACKGROUND TIMER FUNCTION ---
def auto_stop_task(bot, room_id, username):
    """60 Second baad ye function chalega"""
    removed = False
    with lock:
        # Check karo ki kya user abhi bhi list mein hai?
        # (Ho sakta hai user ne khud hi pehle stop kar diya ho)
        if room_id in watched_users and username in watched_users[room_id]:
            del watched_users[room_id][username]
            removed = True
            # Agar room khali ho gaya to room key bhi hata do (Clean Memory)
            if not watched_users[room_id]:
                del watched_users[room_id]

    if removed:
        try:
            bot.send_message(room_id, f"⏰ **Time's Up!** Auto-stopped translation for @{username}.")
        except:
            pass # Agar bot disconnect ho gaya ho to crash na kare

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    sender = data.get("username")
    text = data.get("text", "")
    
    # ==========================================
    # 1. COMMANDS: START & STOP
    # ==========================================
    
    # --- START (!atr user lang) ---
    if cmd in ["atr", "autotr"]:
        if not args:
            bot.send_message(room_id, "⚠️ **Usage:** `!atr @user <lang>`\nEx: `!atr @yasin hin`")
            return True
            
        target_user = args[0].replace("@", "")
        
        # Language Selection
        if len(args) > 1:
            short_code = args[1]
            target_lang = get_full_lang_name(short_code)
        else:
            target_lang = "english"
            
        # Language Validity Check
        try:
            GoogleTranslator(source='auto', target=target_lang)
        except:
            bot.send_message(room_id, f"❌ Invalid Language: **{target_lang}**")
            return True
        
        # Add to List (Thread Safe)
        with lock:
            if room_id not in watched_users:
                watched_users[room_id] = {}
            watched_users[room_id][target_user] = target_lang
        
        bot.send_message(room_id, f"👁️ **Spying:** @{target_user} ({target_lang.upper()})\n⏳ Auto-stop in {TIMEOUT_SECONDS}s.")
        
        # --- START 60s TIMER ---
        # Ye background mein chalega, bot ko rokega nahi
        t = threading.Timer(TIMEOUT_SECONDS, auto_stop_task, args=[bot, room_id, target_user])
        t.daemon = True # Agar bot band ho to ye bhi band ho jaye
        t.start()
        
        return True

    # --- STOP (!rtr user) ---
    if cmd in ["rtr", "stoptr"]:
        if not args:
            bot.send_message(room_id, "⚠️ **Usage:** `!rtr @user`")
            return True
            
        target_user = args[0].replace("@", "")
        
        with lock:
            if room_id in watched_users and target_user in watched_users[room_id]:
                del watched_users[room_id][target_user]
                bot.send_message(room_id, f"🛑 Stopped translating **@{target_user}** manually.")
            else:
                bot.send_message(room_id, "❌ User is not being watched.")
        return True

    # --- LIST (!trlist) ---
    if cmd == "trlist":
        with lock:
            users = watched_users.get(room_id, {})
        if users:
            msg = ", ".join([f"@{u}→{l}" for u, l in users.items()])
            bot.send_message(room_id, f"📝 **Active List:** {msg}")
        else:
            bot.send_message(room_id, "📝 List empty.")
        return True

    # ==========================================
    # 2. AUTOMATIC LISTENER
    # ==========================================
    
    is_watched = False
    target_lang = "english"
    
    # Fast Check (Lock ke sath)
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
                
        except Exception as e:
            print(f"[Auto-Translate Error] {e}")
        
        return False

    return False
