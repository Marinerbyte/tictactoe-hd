import time
import threading
import traceback
import db
import utils

# CONFIG
PAGE_SIZE = 10
SESSION_TIMEOUT = 30
MIN_TRANSFER_BALANCE = 5000 
SESSIONS = {}
SESSIONS_LOCK = threading.Lock()

def setup(bot):
    print("[Economy] SYSTEM ACTIVE.")

# --- HELPERS ---

def purge_expired_sessions():
    now = time.time()
    with SESSIONS_LOCK:
        expired = [k for k, v in SESSIONS.items() if now > v['expires']]
        for k in expired: del SESSIONS[k]

def format_k(n):
    try:
        n = int(n)
        if n < 1000: return str(n)
        if n < 1000000: return f"{n/1000:.1f}k".replace(".0k", "k")
        if n < 1000000000: return f"{n/1000000:.1f}m".replace(".0m", "m")
        return f"{n/1000000000:.1f}b".replace(".0b", "b")
    except: return "0"

def get_symbol(r, t): return "[*]" if t=="gls" else "($)" if r==1 else ">>" if r<=3 else "-"

def get_target_info(bot, room_id, name):
    if not name: return None, None
    clean = name.replace("@", "").strip().lower()
    
    # Check Online
    for r_name in bot.room_details:
        id_map = bot.room_details[r_name].get('id_map', {})
        if clean in id_map:
            uid = str(id_map[clean])
            users = bot.room_details[r_name].get('users', [])
            real = next((u for u in users if u.lower() == clean), name)
            return uid, real
            
    # Check DB
    conn = db.get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT user_id, username FROM users WHERE LOWER(username) = {db.get_ph()} LIMIT 1", (clean,))
        row = cur.fetchone()
        return (str(row[0]), row[1]) if row else (None, None)
    except: return None, None
    finally: conn.close()

# --- FUNCTION JO MISSING THA (Ab Added Hai) ---
def get_detailed_stats(user_id):
    conn = db.get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT game_name, wins, earnings FROM game_stats WHERE user_id = {db.get_ph()}", (str(user_id),))
        return cur.fetchall()
    except: return []
    finally: conn.close()

# --- HANDLER ---

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
                        is_score = (cmd == "sets")
                        # Get current
                        curr = db.get_user_data(tid, tname)['points' if is_score else 'chips']
                        change = val - curr
                        
                        db.update_balance(tid, tname, 
                                          points_change=change if is_score else 0, 
                                          chips_change=0 if is_score else change)
                        
                        bot.send_message(room_id, f"[OK] Admin set {tname}'s {'score' if is_score else 'chips'} to {format_k(val)}")
                    except ValueError: pass
                else: bot.send_message(room_id, f"[!] User '{args[0]}' not found.")
                return True

            if cmd in ["resetc", "resets"] and args:
                tid, tname = get_target_info(bot, room_id, args[0])
                if tid:
                    if cmd == "resetc":
                        db.update_balance(tid, tname, chips_change=-db.get_user_data(tid, tname)['chips'])
                        bot.send_message(room_id, f"[OK] {tname}'s chips reset.")
                    else: # resets
                        conn = db.get_connection(); cur = conn.cursor()
                        cur.execute(f"UPDATE users SET points=0, wins=0 WHERE user_id={db.get_ph()}", (tid,))
                        cur.execute(f"DELETE FROM game_stats WHERE user_id={db.get_ph()}", (tid,))
                        conn.close()
                        bot.send_message(room_id, f"[OK] {tname}'s stats wiped.")
                return True

            if cmd == "wipedb" and args and args[0] == "confirm":
                conn = db.get_connection(); cur = conn.cursor()
                cur.execute("UPDATE users SET points=0, chips=10000, wins=0"); cur.execute("DELETE FROM game_stats")
                conn.close(); bot.send_message(room_id, "[ALERT] DB WIPED.")
                return True

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
            # YE FUNCTION AB DEFINED HAI, CHALEGA
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
            for i, (u, v) in enumerate(rows, 1):
                msg += f"{get_symbol(i, cmd)} {i}. {u[:10]} : {format_k(v)}\n"
            msg += "--------------\nPage 1 | !nx (30s)"
            
            with SESSIONS_LOCK:
                SESSIONS[f"{room_id}_{uid}"] = {'type': cmd, 'page': 0, 'expires': now + SESSION_TIMEOUT}
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
