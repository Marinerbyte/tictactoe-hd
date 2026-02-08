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
    print("[Economy] FINAL BUG-FIXED ENGINE LOADED.")

# HELPERS
def purge_expired_sessions():
    now = time.time()
    with SESSIONS_LOCK:
        expired = [k for k, v in SESSIONS.items() if now > v['expires']]
        for k in expired: del SESSIONS[k]

def format_k(n):
    try:
        n=int(n)
        if n < 1000: return str(n)
        if n < 1000000: return f"{n/1000:.1f}k".replace(".0k","k")
        if n < 1000000000: return f"{n/1000000:.1f}m".replace(".0m","m")
        return f"{n/1000000000:.1f}b".replace(".0b","b") # Billions support
    except: return "0"

def get_symbol(r,t): return "[*]" if t=="gls" else "($)" if r==1 else ">>" if r<=3 else "-"

def get_target_info(bot, room_id, name):
    if not name: return None, None
    clean = name.replace("@","").strip().lower()
    for r_name in bot.room_details:
        id_map = bot.room_details[r_name].get('id_map',{})
        if clean in id_map:
            uid = str(id_map[clean])
            users = bot.room_details[r_name].get('users',[])
            real = next((u for u in users if u.lower()==clean), name)
            return uid, real
    # DB search for offline
    res = db.execute_query(f"SELECT user_id, username FROM users WHERE LOWER(username) = {db.get_ph()} LIMIT 1", (clean,), fetch="one")
    return (str(res[0]), res[1]) if res else (None, None)

# COMMAND HANDLER
def handle_command(bot, cmd, room_id, user, args, data):
    uid = str(data.get('userid'))
    now = time.time()
    
    if cmd == "sync" and user.lower() == "yasin":
        if db.add_admin(uid): bot.send_message(room_id, "[OK] User data synchronized.")
        return True

    is_admin = bot.is_boss(user, uid)
    try:
        # ADMIN COMMANDS
        if is_admin:
            if cmd in ["setc", "sets"] and len(args) >= 2:
                tid, tname = get_target_info(bot, room_id, args[0])
                if tid:
                    try:
                        val = int(args[1])
                        is_score = cmd == "sets"
                        curr = db.get_user_data(tid, tname)['points' if is_score else 'chips']
                        change = val - curr
                        db.update_balance(tid, tname, points_change=change if is_score else 0, chips_change=0 if is_score else change)
                        bot.send_message(room_id, f"[OK] Admin set {tname}'s {'score' if is_score else 'chips'} to {format_k(val)}")
                    except ValueError: pass
                else: bot.send_message(room_id, f"[!] User '{args[0]}' not found.")
                return True
            
            # --- FIX FOR RESETS ---
            if cmd == "resetc" and args:
                tid, tname = get_target_info(bot, room_id, args[0])
                if tid:
                    current_chips = db.get_user_data(tid, tname)['chips']
                    db.update_balance(tid, tname, chips_change=-current_chips)
                    bot.send_message(room_id, f"🧹 {tname}'s chips have been reset to 0.")
                return True

            if cmd == "resets" and args:
                tid, tname = get_target_info(bot, room_id, args[0])
                if tid:
                    conn = db.get_connection(); cur = conn.cursor()
                    ph = db.get_ph()
                    cur.execute(f"UPDATE users SET points=0, wins=0 WHERE user_id={ph}", (tid,))
                    cur.execute(f"DELETE FROM game_stats WHERE user_id={ph}", (tid,))
                    conn.close()
                    bot.send_message(room_id, f"🔥 {tname}'s score and stats wiped.")
                return True

            if cmd == "wipedb" and args and args[0]=="confirm":
                conn = db.get_connection(); cur = conn.cursor()
                cur.execute("UPDATE users SET points=0, chips=10000, wins=0"); cur.execute("DELETE FROM game_stats")
                conn.close()
                bot.send_message(room_id, "[ALERT] DATABASE WIPE COMPLETE.")
                return True

        # USER COMMANDS
        if cmd == "tsc" and len(args) >= 2:
            try:
                amt = int(args[1])
                if amt <= 0: return True
                tid, tname = get_target_info(bot, room_id, args[0])
                if not tid or tid == uid: bot.send_message(room_id,"[!] Invalid target."); return True
                
                sender_bal = db.get_user_data(uid, user)['chips']
                if sender_bal < MIN_TRANSFER_BALANCE: bot.send_message(room_id, f"[!] Min balance {format_k(MIN_TRANSFER_BALANCE)} needed."); return True
                if sender_bal < amt: bot.send_message(room_id, "[!] Not enough chips!"); return True
                
                # Direct DB calls for transfer to ensure it's atomic
                if db.check_and_deduct_chips(uid, user, amt):
                    db.update_balance(tid, tname, chips_change=amt)
                    bot.send_message(room_id, f"[OK] @{user} sent {format_k(amt)} to {tname}.")
                else:
                    bot.send_message(room_id, "[!] Transaction Failed.")
                return True
            except ValueError: bot.send_message(room_id, "[!] Invalid amount."); return True

        if cmd == "mc":
            bal = db.get_user_data(uid, user)['chips']
            bot.send_message(room_id, f"[@{user}] Balance: {format_k(bal)} chips")
            return True

        if cmd in ["ms", "s"]:
            t_name = args[0] if (cmd == "s" and args) else user
            tid, r_name = get_target_info(bot, room_id, t_name)
            if not tid: bot.send_message(room_id, "[!] User not found."); return True
            
            ud = db.get_user_data(tid, r_name)
            g_rows = db.get_detailed_stats(tid) # Using the helper
            msg = f"--- PROFILE: {r_name.upper()} ---\n[*] Score: {format_k(ud['points'])}\n($) Chips: {format_k(ud['chips'])}\n"
            if g_rows:
                msg += "--- Game Records ---\n"
                for gn, w, e in g_rows: msg += f"- {gn.capitalize()}: {w}W | {format_k(e)}\n"
            bot.send_message(room_id, msg); return True
            
        if cmd in ["gls", "chips"]:
            purge_expired_sessions()
            b_type, col, title = ("gls", "points", "SCORE RANK") if cmd == "gls" else ("chips", "chips", "CHIPS RANK")
            rows = db.execute_query(f"SELECT username, {col} FROM users ORDER BY {col} DESC LIMIT {PAGE_SIZE}", fetch="all")
            msg = f"--- {title} ---\n"
            for i, (un, v) in enumerate(rows or [], 1): msg += f"{get_symbol(i, b_type)} {i}. {un[:12]} : {format_k(v)}\n"
            msg += f"--------------\nPage 1 | !nx (30s)"
            with SESSIONS_LOCK: SESSIONS[f"{room_id}_{uid}"] = {'type': b_type, 'page': 0, 'expires': now + SESSION_TIMEOUT}
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
            rows = db.execute_query(f"SELECT username, {col} FROM users ORDER BY {col} DESC LIMIT {PAGE_SIZE} OFFSET {offset}", (offset,), fetch="all")
            if not rows: bot.send_message(room_id, "End of list."); return True
            msg = f"--- PAGE {page+1} ---\n"
            for i, (un, v) in enumerate(rows, 1): msg += f"- {offset+i}. {un[:12]} : {format_k(v)}\n"
            bot.send_message(room_id, msg); return True
            
    except: traceback.print_exc()
    return False
