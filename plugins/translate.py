from deep_translator import GoogleTranslator
import threading

# --- GLOBAL MEMORY ---
# Format: { 'room_id': { 'username': 'target_language' } }
watched_users = {}
lock = threading.Lock()

# --- CUSTOM SHORTCUTS MAPPING ---
# Aap yahan aur shortcuts add kar sakte hain
LANG_MAP = {
    # English
    "en": "english", "eng": "english",
    # Hindi
    "hi": "hindi",   "hin": "hindi",
    # Urdu
    "ur": "urdu",    "urd": "urdu",
    # Punjabi
    "pa": "punjabi", "pun": "punjabi",
    # Bengali
    "bn": "bengali", "ben": "bengali",
    # Marathi
    "mr": "marathi", "mar": "marathi",
    # Arabic
    "ar": "arabic",  "ara": "arabic",
    # French
    "fr": "french",  "fre": "french",
    # Spanish
    "es": "spanish", "spa": "spanish",
    # Russian
    "ru": "russian", "rus": "russian",
}

def setup(bot):
    print("[Auto-Translate] Short-Code Mode Loaded!")

def get_full_lang_name(code):
    """Short code (hin) ko Full Name (hindi) mein badalta hai"""
    code = code.lower().strip()
    return LANG_MAP.get(code, code) # Agar map me nahi hai, to waisa hi return karega

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
            bot.send_message(room_id, "⚠️ **Usage:** `!atr @user <lang>`\nExample: `!atr @yasin hin`")
            return True
            
        target_user = args[0].replace("@", "")
        
        # Agar language di hai to use karo, nahi to default English
        if len(args) > 1:
            short_code = args[1]
            target_lang = get_full_lang_name(short_code)
        else:
            target_lang = "english"
            
        # Validity Check (Dummy Request)
        try:
            GoogleTranslator(source='auto', target=target_lang)
        except:
            bot.send_message(room_id, f"❌ Invalid Language: **{target_lang}**")
            return True
        
        with lock:
            if room_id not in watched_users:
                watched_users[room_id] = {}
            watched_users[room_id][target_user] = target_lang
            
        bot.send_message(room_id, f"👁️ **Spying:** @{target_user}\nOutput Language: **{target_lang.upper()}**")
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
                bot.send_message(room_id, f"🛑 Stopped translating **@{target_user}**.")
            else:
                bot.send_message(room_id, "❌ User is not being watched.")
        return True

    # --- LIST WATCHED (!trlist) ---
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
    # 2. AUTOMATIC LISTENER (The Spy)
    # ==========================================
    
    # Step A: Check if current sender is being watched
    is_watched = False
    target_lang = "english"
    
    with lock:
        if room_id in watched_users and sender in watched_users[room_id]:
            is_watched = True
            target_lang = watched_users[room_id][sender]
    
    # Step B: Translate if conditions met
    # (Watched User + Text hai + Command nahi hai)
    if is_watched and text and not text.startswith("!"):
        try:
            # Skip numbers or single characters to avoid errors
            if text.isdigit() or len(text) < 2: return False

            # MAGIC: source='auto' (User ki bhasha khud pehchano)
            translator = GoogleTranslator(source='auto', target=target_lang)
            translated_text = translator.translate(text)
            
            # Agar translation same hai, to reply mat karo (Spam prevention)
            if translated_text and translated_text.lower() != text.lower():
                reply = f"🗣️ **@{sender}:** {translated_text}"
                bot.send_message(room_id, reply)
                
        except Exception as e:
            print(f"[Auto-Translate Error] {e}")
        
        return False

    return False
