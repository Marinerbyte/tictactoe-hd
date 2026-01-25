import os
import requests
import threading
import time
import psycopg2
import re
from datetime import datetime

# --- CONFIGURATION ---
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
MODEL = "llama-3.1-8b-instant"
MASTER_USER = "yasin"
DB_URL = "postgresql://neondb_owner:npg_gJOAT9c7HhQd@ep-odd-term-ahhlsjch-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

# --- FONT CONVERTER (STRICTLY SMALL CAPS FOR TEXT ONLY) ---
def to_small_caps(text):
    normal = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    small  = "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ"
    trans = str.maketrans(normal, small)
    
    # Hum sirf words ko convert karenge, emojis aur symbols ko nahi
    result = ""
    for char in text:
        if char in normal:
            result += char.translate(trans)
        else:
            result += char
    return result

# --- COOLDOWN SYSTEM ---
user_cooldowns = {} 

def is_spamming(user_id):
    now = time.time()
    if user_id not in user_cooldowns:
        user_cooldowns[user_id] = []
    user_cooldowns[user_id] = [t for t in user_cooldowns[user_id] if now - t < 10]
    if len(user_cooldowns[user_id]) > 3:
        return True
    user_cooldowns[user_id].append(now)
    return False

# --- DATABASE LAYER ---
def db_exec(query, params=(), fetch=False):
    conn = None
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute(query, params)
        res = cur.fetchall() if fetch else None
        conn.commit()
        return res
    except: return None
    finally:
        if conn: conn.close()

def init_ai_db():
    db_exec("""
        CREATE TABLE IF NOT EXISTS nilu_memories (
            user_id TEXT, username TEXT, content TEXT, importance TEXT, 
            confidence FLOAT, last_used TIMESTAMP, created_at TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS nilu_custom (username TEXT PRIMARY KEY, prompt TEXT);
        CREATE TABLE IF NOT EXISTS nilu_relations (username TEXT PRIMARY KEY, rel_type TEXT);
        CREATE TABLE IF NOT EXISTS nilu_stats (user_id TEXT PRIMARY KEY, exchange_count INTEGER DEFAULT 0);
    """)

# --- MEMORY LOGIC ---
def get_user_memory(user_id):
    rows = db_exec("SELECT content FROM nilu_memories WHERE user_id = %s ORDER BY last_used DESC LIMIT 5", (str(user_id),), True)
    return "\n".join([r[0] for r in rows]) if rows else ""

def update_exchange_count(user_id):
    db_exec("""
        INSERT INTO nilu_stats (user_id, exchange_count) VALUES (%s, 1)
        ON CONFLICT (user_id) DO UPDATE SET exchange_count = nilu_stats.exchange_count + 1
    """, (str(user_id),))
    res = db_exec("SELECT exchange_count FROM nilu_stats WHERE user_id = %s", (str(user_id),), True)
    return res[0][0] if res else 0

# --- AI CORE ---
def get_nilu_response(username, user_id, message):
    custom = db_exec("SELECT prompt FROM nilu_custom WHERE username = %s", (username.lower(),), True)
    relation = db_exec("SELECT rel_type FROM nilu_relations WHERE username = %s", (username.lower(),), True)
    memory = get_user_memory(user_id)
    
    # System Instruction for Emojis and Tone
    sys_prompt = f"""
    You are Nilu, a witty, confident, and friendly girl in a chatroom.
    TONE: Not a robot. Be consistent. If you know the user, be warmer. If they are a jerk, be sassy.
    
    EMOJI RULES:
    1. Use emojis naturally within your sentences based on the MOOD. 
       - If happy/laughing: 😂, 🤣, ✨
       - If cool/confident: 😎, 😏, 💅
       - If annoyed/witty: 🙄, 💢, 🤨
       - If friendly/sweet: 😊, 🤍, 🌸
    2. Do NOT spam emojis. Use 1 or 2 where it fits.
    3. MANDATORY ENDING: Every single reply MUST end with this exact string: _🙂_ _🫰_
    
    CURRENT CONTEXT:
    - Talking to: {username}
    - Relationship: {relation[0][0] if relation else 'Neutral'}
    - Custom Behavior for this user: {custom[0][0] if custom else 'Normal'}
    - Memory of past chats: {memory if memory else 'First time meeting.'}

    REPLY STYLE: Hinglish, short, meaningful.
    """

    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": message}
            ],
            "temperature": 0.8
        }
        r = requests.post(url, json=payload, headers=headers, timeout=15)
        response_text = r.json()['choices'][0]['message']['content']
        
        # Save memory in background
        threading.Thread(target=memory_worker, args=(user_id, username, message, response_text)).start()
        
        return to_small_caps(response_text)
    except:
        return to_small_caps("ᴜɢʜ, ᴍᴇʀᴀ ᴅɪᴍᴀᴀɢ ᴀʙʜɪ ᴛʜᴇᴇᴋ ɴᴀʜɪ ʜᴀɪ. ᴘʜɪʀ ʙᴀᴀᴛ ᴋᴀʀᴛᴇ ʜᴀɪɴ! _🙂_ _🫰_")

def memory_worker(user_id, username, user_msg, ai_res):
    count = update_exchange_count(user_id)
    if count < 4: return 

    try:
        payload = {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": "Extract meaningful info (hobbies, work, mood, names mentioned). Reply 'NONE' if useless."},
                {"role": "user", "content": f"User: {user_msg}\nNilu: {ai_res}"}
            ]
        }
        r = requests.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers={"Authorization": f"Bearer {GROQ_API_KEY}"})
        important_info = r.json()['choices'][0]['message']['content']
        
        if "NONE" not in important_info.upper():
            db_exec("""
                INSERT INTO nilu_memories (user_id, username, content, importance, confidence, last_used, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (str(user_id), username, important_info, 'medium', 0.9, datetime.now(), datetime.now()))
    except: pass

# --- MAIN PLUGIN FUNCTIONS ---
def setup(bot):
    init_ai_db()
    print("[Nilu AI] Dynamic Emojis & Memory Ready.")

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    uid = data.get('userid', user)
    is_master = (user.lower() == MASTER_USER.lower())

    # --- ADMIN COMMANDS ---
    if cmd == "clear":
        if args and args[0] == "user" and len(args) > 1:
            target = args[1].replace("@", "")
            db_exec("DELETE FROM nilu_memories WHERE username ILIKE %s", (target,))
            bot.send_message(room_id, to_small_caps(f"ᴍᴇᴍᴏʀʏ ᴄʟᴇᴀʀᴇᴅ ғᴏʀ @{target}"))
        elif args and args[0] == "all" and is_master:
            db_exec("DELETE FROM nilu_memories")
            bot.send_message(room_id, to_small_caps("ᴀʟʟ ᴍᴇᴍᴏʀɪᴇs ᴡɪᴘᴇᴅ ᴏᴜᴛ!"))
        return True

    if cmd == "addb" and is_master:
        if len(args) < 2: return True
        target = args[0].replace("@", "").lower()
        prompt = " ".join(args[1:])
        db_exec("INSERT INTO nilu_custom (username, prompt) VALUES (%s, %s) ON CONFLICT (username) DO UPDATE SET prompt = EXCLUDED.prompt", (target, prompt))
        bot.send_message(room_id, to_small_caps(f"ʙᴇʜᴀᴠɪᴏᴜʀ sᴇᴛ ғᴏʀ @{target}"))
        return True

    # Relationship Commands
    if cmd == "add":
        if len(args) < 2: return True
        target = args[0].replace("@", "").lower()
        rel = args[1].lower()
        if rel in ["friend", "enemy"]:
            db_exec("INSERT INTO nilu_relations (username, rel_type) VALUES (%s, %s) ON CONFLICT (username) DO UPDATE SET rel_type = EXCLUDED.rel_type", (target, rel))
            bot.send_message(room_id, to_small_caps(f"@{target} ɪs ɴᴏᴡ ᴍʏ {rel}"))
        return True

    # --- TRIGGER LOGIC ---
    msg_text = data.get("text", "")
    # Check for exact 'nilu' word
    if re.search(r'\bnilu\b', msg_text.lower()):
        if is_spamming(uid): return True

        def run_ai():
            response = get_nilu_response(user, uid, msg_text)
            bot.send_message(room_id, f"@{user} {response}")

        threading.Thread(target=run_ai, daemon=True).start()
        return True

    return False
