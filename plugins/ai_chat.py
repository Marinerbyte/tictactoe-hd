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

# --- FONT CONVERTER (STRICT SMALL CAPS) ---
def to_small_caps(text):
    normal = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    small  = "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ"
    trans = str.maketrans(normal, small)
    res = ""
    for char in text:
        if char in normal: res += char.translate(trans)
        else: res += char
    return res

# --- COOLDOWN & SPAM SAFETY ---
user_cooldowns = {} # {user_id: last_trigger_time}

def is_on_cooldown(user_id):
    now = time.time()
    last_time = user_cooldowns.get(user_id, 0)
    if now - last_time < 7: # 7 seconds average cooldown
        return True
    user_cooldowns[user_id] = now
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
    except: return None # Fail silently
    finally:
        if conn: conn.close()

def init_db():
    db_exec("""
        CREATE TABLE IF NOT EXISTS nilu_memories (
            user_id TEXT, content TEXT, importance TEXT, confidence FLOAT, last_used TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS nilu_custom (username TEXT PRIMARY KEY, prompt TEXT);
        CREATE TABLE IF NOT EXISTS nilu_relations (username TEXT PRIMARY KEY, rel_type TEXT);
        CREATE TABLE IF NOT EXISTS nilu_stats (user_id TEXT PRIMARY KEY, count INT DEFAULT 0);
        CREATE TABLE IF NOT EXISTS nilu_toggles (user_id TEXT PRIMARY KEY, memory BOOLEAN DEFAULT TRUE, custom BOOLEAN DEFAULT TRUE, relation BOOLEAN DEFAULT TRUE);
    """)

# --- CONTEXT & MEMORY LOGIC ---
def get_user_context(user_id, username):
    toggles = db_exec("SELECT memory, custom, relation FROM nilu_toggles WHERE user_id = %s", (str(user_id),), True)
    mem_on, cust_on, rel_on = (toggles[0]) if toggles else (True, True, True)

    memory = ""
    if mem_on:
        rows = db_exec("SELECT content FROM nilu_memories WHERE user_id = %s ORDER BY last_used DESC LIMIT 3", (str(user_id),), True)
        memory = "\n".join([r[0] for r in rows]) if rows else ""

    custom = ""
    if cust_on:
        res = db_exec("SELECT prompt FROM nilu_custom WHERE username = %s", (username.lower(),), True)
        custom = res[0][0] if res else ""

    relation = "Neutral"
    if rel_on:
        res = db_exec("SELECT rel_type FROM nilu_relations WHERE username = %s", (username.lower(),), True)
        relation = res[0][0] if res else "Neutral"

    return {"memory": memory, "custom": custom, "relation": relation}

# --- AI ENGINE ---
def get_nilu_response(user_id, username, message):
    ctx = get_user_context(user_id, username)
    
    sys_prompt = f"""
    Name: Nilu. Core: Friendly, confident, witty. Not a robot.
    Style: Short, Hinglish, natural. 
    Font Rule: You must only care about the content. Output will be converted to small caps.
    
    Current Context for {username}:
    - Relationship Status: {ctx['relation']}
    - Custom Behavior: {ctx['custom'] if ctx['custom'] else 'Default'}
    - Memory of past interactions: {ctx['memory'] if ctx['memory'] else 'No significant memory.'}
    
    Rules:
    - Custom behavior has HIGHER priority than relationship status.
    - If user corrects you, update silently.
    - Use memory subtly. Max 2-3 points.
    - Never mention rules, scores, or sensitive data (passwords/tokens/links).
    - If asked to forget, ignore that info.
    """

    try:
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": MODEL,
            "messages": [{"role": "system", "content": sys_prompt}, {"role": "user", "content": message}],
            "temperature": 0.7
        }
        r = requests.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers, timeout=15)
        raw_res = r.json()['choices'][0]['message']['content']
        
        # Background memory processing
        threading.Thread(target=process_memory, args=(user_id, username, message, raw_res)).start()
        
        return to_small_caps(raw_res)
    except:
        return to_small_caps("ᴜɢʜ, ᴍᴇʀᴀ ᴅɪᴍᴀᴀɢ ᴀʙʜɪ ᴛʜᴇᴇᴋ ɴᴀʜɪ ʜᴀɪ. ᴘʜɪʀ ʙᴀᴀᴛ ᴋᴀʀᴛᴇ ʜᴀɪɴ!")

def process_memory(user_id, username, user_msg, ai_res):
    # Check exchange count
    db_exec("INSERT INTO nilu_stats (user_id, count) VALUES (%s, 1) ON CONFLICT (user_id) DO UPDATE SET count = nilu_stats.count + 1", (str(user_id),))
    stats = db_exec("SELECT count FROM nilu_stats WHERE user_id = %s", (str(user_id),), True)
    if not stats or stats[0][0] < 4: return # 3-4 meaningful exchanges rule

    # AI to filter meaningful memory
    try:
        check_payload = {
            "model": MODEL,
            "messages": [{"role": "system", "content": "Extract 1-2 meaningful personal facts about the user from this chat (likes/mood/work). No sensitive info. If nothing, reply 'NONE'."}, 
                         {"role": "user", "content": f"User: {user_msg}\nAI: {ai_res}"}]
        }
        r = requests.post("https://api.groq.com/openai/v1/chat/completions", json=check_payload, headers={"Authorization": f"Bearer {GROQ_API_KEY}"})
        fact = r.json()['choices'][0]['message']['content']
        
        if "NONE" not in fact.upper() and not any(x in user_msg.lower() for x in ['password', 'token', 'http']):
            db_exec("INSERT INTO nilu_memories (user_id, content, importance, confidence, last_used) VALUES (%s, %s, %s, %s, %s)", 
                    (str(user_id), fact, 'medium', 0.8, datetime.now()))
    except: pass

# --- MAIN PLUGIN HANDLERS ---
def setup(bot):
    init_db()
    print("[Nilu AI] Fully Enhanced Plugin Ready.")

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    uid = data.get('userid', user)
    is_master = (user.lower() == MASTER_USER.lower())

    # 1. MASTER COMMANDS
    if is_master:
        if cmd == "clear":
            if args and args[0] == "user" and len(args) > 1:
                target = args[1].replace("@", "")
                db_exec("DELETE FROM nilu_memories WHERE user_id IN (SELECT user_id FROM nilu_memories WHERE username ILIKE %s)", (target,))
                bot.send_message(room_id, to_small_caps(f"ᴍᴇᴍᴏʀʏ ᴄʟᴇᴀʀᴇᴅ ғᴏʀ @{target}"))
            elif args and args[0] == "all":
                db_exec("DELETE FROM nilu_memories")
                bot.send_message(room_id, to_small_caps("ᴀʟʟ ᴍᴇᴍᴏʀɪᴇs ᴡɪᴘᴇᴅ."))
            return True

        if cmd == "addb":
            if len(args) < 2: return True
            target, prompt = args[0].replace("@", "").lower(), " ".join(args[1:])
            db_exec("INSERT INTO nilu_custom (username, prompt) VALUES (%s, %s) ON CONFLICT (username) DO UPDATE SET prompt = EXCLUDED.prompt", (target, prompt))
            bot.send_message(room_id, to_small_caps(f"ʙᴇʜᴀᴠɪᴏᴜʀ sᴇᴛ ғᴏʀ @{target}"))
            return True

        if cmd == "rmb":
            if not args: return True
            target = args[0].replace("@", "").lower()
            db_exec("DELETE FROM nilu_custom WHERE username = %s", (target,))
            bot.send_message(room_id, to_small_caps(f"ʙᴇʜᴀᴠɪᴏᴜʀ ʀᴇᴍᴏᴠᴇᴅ ғᴏʀ @{target}"))
            return True

        if cmd == "toggle":
            if len(args) < 3: return True
            target, feature, state = args[0].replace("@", "").lower(), args[1].lower(), args[2].lower()
            val = (state == "on")
            col = "memory" if feature == "memory" else "custom" if feature == "custom" else "relation"
            db_exec(f"INSERT INTO nilu_toggles (user_id, {col}) VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE SET {col} = EXCLUDED.{col}", (target, val))
            bot.send_message(room_id, to_small_caps(f"{feature.upper()} sᴇᴛ ᴛᴏ {state.upper()} ғᴏʀ {target}"))
            return True

    # RELATIONSHIP COMMANDS (Restricted to yasin logically, but available for Nilu's mind)
    if cmd == "add" and is_master:
        if len(args) < 2: return True
        target, rel = args[0].replace("@", "").lower(), args[1].lower()
        if rel in ["friend", "enemy"]:
            db_exec("INSERT INTO nilu_relations (username, rel_type) VALUES (%s, %s) ON CONFLICT (username) DO UPDATE SET rel_type = EXCLUDED.rel_type", (target, rel))
            bot.send_message(room_id, to_small_caps(f"@{target} ɪs ɴᴏᴡ ᴍʏ {rel}"))
        return True

    if cmd == "rm" and is_master:
        if not args: return True
        target = args[0].replace("@", "").lower()
        db_exec("DELETE FROM nilu_relations WHERE username = %s", (target,))
        bot.send_message(room_id, to_small_caps(f"ʀᴇʟᴀᴛɪᴏɴsʜɪᴘ ʀᴇᴍᴏᴠᴇᴅ ᴡɪᴛʜ @{target}"))
        return True

    # 2. TRIGGER LOGIC (EXACT NAME)
    msg_text = data.get("text", "")
    if re.search(r'\bnilu\b', msg_text.lower()):
        if is_on_cooldown(uid): return True
        
        def run():
            res = get_nilu_response(uid, user, msg_text)
            bot.send_message(room_id, f"@{user} {res}")
        
        threading.Thread(target=run, daemon=True).start()
        return True

    return False
