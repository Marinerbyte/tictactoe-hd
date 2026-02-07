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

# Sessions Memory: {UserID_RoomID: {'type', 'page', 'expires'}}
SESSIONS = {}
SESSIONS_LOCK = threading.Lock()

def setup(bot):
    print("[Economy] 100% Rock Solid Production Engine v4.0 Loaded.")

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
    if rank == 1: return "👑" if board_type == "score" else "💎"
    if rank <= 3: return "⭐"
    return "•"

def get_target_info(bot, room_id, name):
    """Robust Target Fetcher: Error-proof online/offline check"""
    if not name: return None, None
    clean_name = name.replace("@", "").strip().lower()
    
    # 1. Online Users Cache Check (Optimized - Zero DB Hit if user in room)
    room_data = bot.room_details.get(room_id, {})
    id_map = room_data.get('id_map', {})
    
    if clean_name in id_map:
        # Safe lookup for actual capitalization
        users_list = room_data.get('users', [])
        actual_name = next((u for u in users_list if u.lower() == clean_name), clean_name)
        return str(id_map[clean_name]), actual_name

    # 2. Database Deep Search (Only if user is offline/not in room)
    conn = db.get_connection(); cur = conn.cursor()
    try:
        ph = "%s" if db.DATABASE_URL.startswith("postgres") else "?"
        cur.execute(f"SELECT user_id, username FROM users WHERE LOWER(username) = {ph} LIMIT 1", (clean_name,))
        row = cur.fetchone()
        return (row[0], row[1]) if row else (None, None)
    finally:
        conn.close()

# ==========================================
# 📡 COMMAND HANDLER
# ==========================================

def handle_command(bot, cmd, room_id, user, args, data):
    uid = str(data.get('userid'))
    now = time.time()
    
    # Centralized Authority Check
    is_admin = bot.is_boss(user, uid)

    try:
        # 👮 ADMIN COMMANDS
        if is_admin:
            if cmd == "setc" and len(args) >= 2:
                tid, tname = get_target_info(bot, room_id, args[0])
                if tid:
                    try:
                        target_val = int(args[1])
                        current_bal = db.get_user_data(tid)['chips']
                        db.update_balance(tid, tname, chips_change=(target_val - current_bal))
                        bot.send_message(room_id, f"✅ Admin set {tname}'s chips to {format_k(target_val)}")
                    except ValueError: bot.send_message(room_id, "❌ Usage: !setc <user> <amount_number>")
                else: bot.send_message(room_id, f"❌ User '{args[0]}' system mein nahi mila.")
                return True

            if cmd == "sets" and len(args) >= 2:
                tid, tname = get_target_info(bot, room_id, args[0])
                if tid:
                    try:
                        target_val = int(args[1])
                        current_pts = db.get_user_data(tid)['points']
                        db.update_balance(tid, tname, points_change=(target_val - current_pts))
                        bot.send_message(room_id, f"✅ Admin set {tname}'s score to {format_k(target_val)}")
                    except ValueError: bot.send_message(room_id, "❌ Usage: !sets <user> <amount_number>")
                return True

            if cmd in ["resetc", "resets"] and args:
                tid, tname = get_target_info(bot, room_id, args[0])
                if tid:
                    if cmd == "resetc":
                        bal = db.get_user_data(tid)['chips']
                        db.update_balance(tid, tname, chips_change=-bal)
                        bot.send_message(room_id, f"🧹 {tname}'s chips reset to 0.")
                    else:
                        conn = db.get_connection(); cur = conn.cursor()
                        try:
                            ph = "%s" if db.DATABASE_URL.startswith("postgres") else "?"
                            cur.execute(f"UPDATE users SET points = 0, wins = 0 WHERE user_id = {ph}", (str(tid),))
                            cur.execute(f"DELETE FROM game_stats WHERE user_id = {ph}", (str(tid),))
                            conn.commit()
                        finally: conn.close()
                        bot.send_message(room_id, f"🔥 {tname}'s profile fully wiped.")
                return True

            if cmd == "wipedb":
                if len(args) > 0 and args[0] == "confirm":
                    conn = db.get_connection(); cur = conn.cursor()
                    try:
                        cur.execute("UPDATE users SET points = 0, chips = 10000, wins = 0")
                        cur.execute("DELETE FROM game_stats")
                        conn.commit()
                    finally: conn.close()
                    bot.send_message(room_id, "☢️ SYSTEM RESET: Sab zero ho gaya, default 10k chips set.")
                else:
                    bot.send_message(room_id, "⚠️ Type `!wipedb confirm` to wipe ALL user data!")
                return True

        # 👤 USER COMMANDS

        # 1. TRANSFER (!tsc)
        if cmd == "tsc" and len(args) >= 2:
            try:
                amt = int(args[1])
                if amt <= 0:
                    bot.send_message(room_id, "❌ Amount sahi daalo."); return True
                
                tid, tname = get_target_info(bot, room_id, args[0])
                if not tid: bot.send_message(room_id, f"❌ User {args[0]} nahi mila."); return True
                if tid == uid: bot.send_message(room_id, "⚠️ Khud ko chips nahi bhej sakte!"); return True
                
                sender_bal = db.get_user_data(uid)['chips']
                if sender_bal < MIN_TRANSFER_BALANCE:
                    bot.send_message(room_id, f"⚠️ Min balance {format_k(MIN_TRANSFER_BALANCE)} honi chahiye."); return True
                
                if sender_bal < amt:
                    bot.send_message(room_id, f"❌ Balance kam hai! Current: {format_k(sender_bal)}"); return True
                
                if db.check_and_deduct_chips(uid, user, amt):
                    db.update_balance(tid, tname, chips_change=amt)
                    bot.send_message(room_id, f"💸 @{user} transferred {format_k(amt)} chips to {tname}.")
                return True
            except ValueError:
                bot.send_message(room_id, "❌ Usage: !tsc <user> <amount_number>")
                return True

        # 2. MY CHIPS (!mc)
        if cmd == "mc":
            bal = db.get_user_data(uid)['chips']
            bot.send_message(room_id, f"💰 @{user} Balance: {format_k(bal)}")
            return True

        # 3. STATS (!ms / !s)
        if cmd in ["ms", "s"]:
            target_name = args[0].replace("@", "") if (cmd == "s" and args) else user
            tid, real_name = get_target_info(bot, room_id, target_name)
            if not tid: bot.send_message(room_id, "❌ User system mein nahi hai."); return True
            
            u_data = db.get_user_data(tid)
            conn = db.get_connection(); cur = conn.cursor()
            try:
                ph = "%s" if db.DATABASE_URL.startswith("postgres") else "?"
                cur.execute(f"SELECT game_name, wins, earnings FROM game_stats WHERE user_id = {ph}", (str(tid),))
                rows = cur.fetchall()
            finally: conn.close()
            
            msg = f"👤 **PROFILE: {real_name.upper()}**\n━━━━━━━━━━━━━━\n"
            msg += f"🏆 Score: {format_k(u_data['points'])}\n💰 Chips: {format_k(u_data['chips'])}\n\n"
            if rows:
                msg += "🎮 **Game Records:**\n"
                for g_name, wins, earnings in rows:
                    msg += f"• {g_name.capitalize()}: {wins}W | {format_k(earnings)} won\n"
            bot.send_message(room_id, msg); return True

        # 4. LEADERBOARDS (!gls / !chips)
        if cmd in ["gls", "chips"]:
            purge_expired_sessions() # Periodic memory cleanup
            
            b_type = "score" if cmd == "gls" else "chips"
            col = "points" if cmd == "gls" else "chips"
            title = "GLOBAL SCORE RANK" if cmd == "gls" else "GLOBAL CHIPS RANK"
            
            conn = db.get_connection(); cur = conn.cursor()
            try:
                cur.execute(f"SELECT username, {col} FROM users ORDER BY {col} DESC LIMIT {PAGE_SIZE}")
                rows = cur.fetchall()
            finally: conn.close()
            
            msg = f"🏆 **{title}**\n━━━━━━━━━━━━━━\n"
            for i, (uname, val) in enumerate(rows, 1):
                sym = get_symbol(i, b_type)
                msg += f"{sym} {i}. {uname[:10]} : {format_k(val)}\n"
            msg += f"━━━━━━━━━━━━━━\nPage 1 | !nx for next (25s)"
            
            # User-Room specific session isolation
            with SESSIONS_LOCK:
                SESSIONS[f"{room_id}_{uid}"] = {'type': b_type, 'page': 0, 'expires': now + SESSION_TIMEOUT}
            bot.send_message(room_id, msg); return True

        # 5. NEXT PAGE (!nx)
        if cmd == "nx":
            sess_key = f"{room_id}_{uid}"
            with SESSIONS_LOCK:
                sess = SESSIONS.get(sess_key)
                if not sess: return False # No active session for this user
                if now > sess['expires']:
                    del SESSIONS[sess_key]
                    return False
                
                sess['page'] += 1; sess['expires'] = now + SESSION_TIMEOUT
                page, b_type = sess['page'], sess['type']
                
            col = "points" if b_type == "score" else "chips"
            offset = page * PAGE_SIZE
            conn = db.get_connection(); cur = conn.cursor()
            try:
                cur.execute(f"SELECT username, {col} FROM users ORDER BY {col} DESC LIMIT {PAGE_SIZE} OFFSET {offset}")
                rows = cur.fetchall()
            finally: conn.close()
            
            if not rows:
                bot.send_message(room_id, f"@{user}, ranking end."); return True
                
            msg = f"🏆 **RANKING (Page {page+1})**\n━━━━━━━━━━━━━━\n"
            for i, (uname, val) in enumerate(rows, 1):
                rank_num = offset + i
                sym = get_symbol(rank_num, b_type)
                msg += f"{sym} {rank_num}. {uname[:10]} : {format_k(val)}\n"
            msg += f"━━━━━━━━━━━━━━\n!nx for next (25s)"
            bot.send_message(room_id, msg); return True

    except Exception:
        print(f"[Economy Error] Critical Fail in {cmd}:")
        traceback.print_exc()
        
    return False
