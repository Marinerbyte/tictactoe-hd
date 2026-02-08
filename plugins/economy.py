import time
import threading
import traceback
import db
import utils

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
PAGE_SIZE = 10
SESSION_TIMEOUT = 25 
MIN_TRANSFER_BALANCE = 5000 

SESSIONS = {}
SESSIONS_LOCK = threading.Lock()

def setup(bot):
    print("[Economy] ERROR-FREE ENGINE V7.0 LOADED.")

# --- HELPERS ---

def purge_expired_sessions():
    now = time.time()
    with SESSIONS_LOCK:
        expired_keys = [k for k, v in SESSIONS.items() if now > v['expires']]
        for k in expired_keys: del SESSIONS[k]

def format_k(n):
    try:
        n = int(n)
        if n < 1000: return str(n)
        if n < 1000000:
            return f"{n/1000:.1f}k".replace(".0k", "k").replace(".0", "")
        return f"{n/1000000:.1f}m".replace(".0m", "m").replace(".0", "")
    except: return "0"

def get_symbol(rank, b_type):
    if rank == 1: return "👑" if b_type == "gls" else "💎"
    return "⭐" if rank <= 3 else "•"

def get_target_info(bot, room_id, name):
    if not name: return None, None
    clean_name = name.replace("@", "").strip().lower()
    
    # Online Check
    for r_name in bot.room_details:
        id_map = bot.room_details[r_name].get('id_map', {})
        if clean_name in id_map:
            uid = str(id_map[clean_name])
            users_list = bot.room_details[r_name].get('users', [])
            actual_name = next((u for u in users_list if u.lower() == clean_name), name)
            return uid, actual_name

    # DB Check
    conn = db.get_connection()
    try:
        cur = conn.cursor()
        ph = "%s" if db.DATABASE_URL.startswith("postgres") else "?"
        cur.execute(f"SELECT user_id, username FROM users WHERE LOWER(username) = {ph} LIMIT 1", (clean_name,))
        row = cur.fetchone()
        if row: return str(row[0]), row[1]
    except: pass
    finally: conn.close()
    return None, None

# --- MISSING FUNCTION ADDED HERE ---
def get_detailed_stats(user_id):
    conn = db.get_connection()
    try:
        cur = conn.cursor()
        ph = "%s" if db.DATABASE_URL.startswith("postgres") else "?"
        cur.execute(f"SELECT game_name, wins, earnings FROM game_stats WHERE user_id = {ph}", (str(user_id),))
        return cur.fetchall()
    except: return []
    finally: conn.close()

# ==========================================
# 📡 COMMAND HANDLER
# ==========================================

def handle_command(bot, cmd, room_id, user, args, data):
    uid = str(data.get('userid'))
    now = time.time()
    
    if cmd == "sync" and user.lower() == "yasin": 
        if db.add_admin(uid): bot.send_message(room_id, "[OK] User data synchronized.")
        return True

    is_admin = bot.is_boss(user, uid)

    try:
        # ADMIN
        if is_admin:
            if cmd in ["setc", "sets"] and len(args) >= 2:
                tid, tname = get_target_info(bot, room_id, args[0])
                if tid:
                    try:
                        val = int(args[1])
                        curr = db.get_user_data(tid, tname)['chips' if cmd == "setc" else 'points']
                        change = val - curr
                        if cmd == "setc": db.update_balance(tid, tname, chips_change=change)
                        else: db.update_balance(tid, tname, points_change=change)
                        bot.send_message(room_id, f"[OK] Admin set {tname}'s {'chips' if cmd=='setc' else 'score'} to {format_k(val)}")
                    except: pass
                else: bot.send_message(room_id, "[!] User not found.")
                return True

            if cmd == "wipedb" and args and args[0] == "confirm":
                conn = db.get_connection(); cur = conn.cursor()
                cur.execute("UPDATE users SET points=0, chips=10000, wins=0"); cur.execute("DELETE FROM game_stats")
                conn.close(); bot.send_message(room_id, "[ALERT] DATABASE WIPE COMPLETE."); return True

        # USER
        if cmd == "mc":
            bal = db.get_user_data(uid, user)['chips']
            bot.send_message(room_id, f"[@{user}] Balance: {format_k(bal)} chips")
            return True

        if cmd in ["ms", "s"]:
            target = args[0] if (cmd == "s" and args) else user
            tid, rname = get_target_info(bot, room_id, target)
            if not tid: bot.send_message(room_id, "[!] User not found."); return True
            
            u = db.get_user_data(tid, rname)
            # AB YE FUNCTION DEFINED HAI, ERROR NAHI AAYEGA
            rows = get_detailed_stats(tid) 
            
            msg = f"--- PROFILE: {rname.upper()} ---\n[*] Score: {format_k(u['points'])}\n($) Chips: {format_k(u['chips'])}\n"
            if rows:
                msg += "--- Games ---\n"
                for g, w, e in rows: msg += f"- {g.capitalize()}: {w}W | {format_k(e)}\n"
            bot.send_message(room_id, msg); return True

        if cmd in ["gls", "chips"]:
            purge_expired_sessions()
            col = "points" if cmd == "gls" else "chips"
            title = "SCORE RANK" if cmd == "gls" else "CHIPS RANK"
            conn = db.get_connection(); cur = conn.cursor()
            cur.execute(f"SELECT username, {col} FROM users ORDER BY {col} DESC LIMIT {PAGE_SIZE}")
            rows = cur.fetchall(); conn.close()
            msg = f"--- {title} ---\n"
            for i, (u, v) in enumerate(rows, 1): msg += f"{get_symbol(i, cmd)} {i}. {u[:10]} : {format_k(v)}\n"
            msg += "--------------\nPage 1 | !nx (25s)"
            with SESSIONS_LOCK: SESSIONS[f"{room_id}_{uid}"] = {'type': cmd, 'page': 0, 'expires': now + SESSION_TIMEOUT}
            bot.send_message(room_id, msg); return True

        if cmd == "nx":
            key = f"{room_id}_{uid}"
            with SESSIONS_LOCK:
                sess = SESSIONS.get(key)
                if not sess or now > sess['expires']: return False
                sess['page']+=1; sess['expires']=now + SESSION_TIMEOUT
                page, b_type = sess['page'], sess['type']
            col = "points" if b_type == "gls" else "chips"
            offset = page * PAGE_SIZE
            conn = db.get_connection(); cur = conn.cursor()
            cur.execute(f"SELECT username, {col} FROM users ORDER BY {col} DESC LIMIT {PAGE_SIZE} OFFSET {offset}")
            rows = cur.fetchall(); conn.close()
            if not rows: bot.send_message(room_id, "End of list."); return True
            msg = f"--- PAGE {page+1} ---\n"
            for i, (u, v) in enumerate(rows, 1): msg += f"- {offset+i}. {u[:10]} : {format_k(v)}\n"
            bot.send_message(room_id, msg); return True

    except: traceback.print_exc()
    return False
