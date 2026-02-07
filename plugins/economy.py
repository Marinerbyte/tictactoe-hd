import time
import threading
import db
import utils

# --- CONFIG ---
PAGE_SIZE = 10
SESSION_TIMEOUT = 15 
MIN_TRANSFER_BALANCE = 5000  # User must have > 5k to transfer

# Pagination Sessions: {room_id: {'type': 'score/chips', 'page': 0, 'expires': float}}
SESSIONS = {}
SESSIONS_LOCK = threading.Lock()

def setup(bot):
    print("[Economy] Admin & User Ledger System Ready.")

# --- HELPERS ---

def format_k(n):
    """1000 -> 1k, 1100 -> 1.1k logic"""
    try:
        n = int(n)
        if n < 1000: return str(n)
        if n < 1000000:
            val = n / 1000
            return f"{val:.1f}k".replace(".0k", "k").replace(".0", "")
        val = n / 1000000
        return f"{val:.1f}m".replace(".0m", "m").replace(".0", "")
    except: return "0"

def get_symbol(rank, board_type):
    if rank == 1: return "👑" if board_type == "score" else "💎"
    if rank <= 3: return "⭐"
    return "•"

def get_target_id(bot, room_id, name):
    if not name: return None
    clean_name = name.replace("@", "").strip().lower()
    room_data = bot.room_details.get(room_id)
    if room_data:
        id_map = room_data.get('id_map', {})
        return id_map.get(clean_name)
    return None

def get_detailed_stats(user_id):
    conn = db.get_connection(); cur = conn.cursor()
    ph = "%s" if db.DATABASE_URL.startswith("postgres") else "?"
    cur.execute(f"SELECT game_name, wins, earnings FROM game_stats WHERE user_id = {ph}", (str(user_id),))
    rows = cur.fetchall(); conn.close()
    return rows

# --- COMMAND HANDLER ---

def handle_command(bot, cmd, room_id, user, args, data):
    uid = str(data.get('userid'))
    now = time.time()

    # ==========================================
    # 👮 ADMIN COMMANDS (Set Chips & Score)
    # ==========================================
    if uid in db.get_all_admins():
        
        # !setc <user> <amount> (Chips Set)
        if cmd == "setc" and len(args) >= 2:
            tid = get_target_id(bot, room_id, args[0])
            if tid:
                target_data = db.get_user_data(tid)
                try:
                    target_val = int(args[1])
                    diff = target_val - target_data['chips']
                    db.update_balance(tid, args[0], chips_change=diff)
                    bot.send_message(room_id, f"✅ Admin updated {args[0]}'s chips to {format_k(target_val)}")
                except: pass
            return True

        # !sets <user> <amount> (Score Set)
        if cmd == "sets" and len(args) >= 2:
            tid = get_target_id(bot, room_id, args[0])
            if tid:
                target_data = db.get_user_data(tid)
                try:
                    target_val = int(args[1])
                    diff = target_val - target_data['points']
                    db.update_balance(tid, args[0], points_change=diff)
                    bot.send_message(room_id, f"✅ Admin updated {args[0]}'s score to {format_k(target_val)}")
                except: pass
            return True

        # !resetc, !resets, !wipedb (Baaki admin commands same hain)
        if cmd == "resetc" and args:
            tid = get_target_id(bot, room_id, args[0])
            if tid:
                bal = db.get_user_data(tid)['chips']
                db.update_balance(tid, args[0], chips_change=-bal)
                bot.send_message(room_id, f"🧹 {args[0]} chips reset to 0.")
            return True

        if cmd == "resets" and args:
            tid = get_target_id(bot, room_id, args[0])
            if tid:
                conn = db.get_connection(); cur = conn.cursor()
                ph = "%s" if db.DATABASE_URL.startswith("postgres") else "?"
                cur.execute(f"UPDATE users SET points = 0, wins = 0 WHERE user_id = {ph}", (str(tid),))
                cur.execute(f"DELETE FROM game_stats WHERE user_id = {ph}", (str(tid),))
                conn.commit(); conn.close()
                bot.send_message(room_id, f"🔥 {args[0]}'s score/stats wiped.")
            return True

        if cmd == "wipedb":
            conn = db.get_connection(); cur = conn.cursor()
            cur.execute("UPDATE users SET points = 0, chips = 10000, wins = 0")
            cur.execute("DELETE FROM game_stats")
            conn.commit(); conn.close()
            bot.send_message(room_id, "☢️ SYSTEM WIPE: All scores 0, Chips 10k.")
            return True

    # ==========================================
    # 👤 USER COMMANDS
    # ==========================================

    # 1. TRANSFER CHIPS (!tsc)
    if cmd == "tsc" and len(args) >= 2:
        try:
            amt = int(args[1])
            if amt <= 0: return True
            
            # 1. Check if Target exists
            tid = get_target_id(bot, room_id, args[0])
            if not tid:
                bot.send_message(room_id, "❌ Target user not found."); return True
            
            # 2. Check Sender's Balance
            sender_data = db.get_user_data(uid)
            
            # Condition: User must have > 5k to even initiate a transfer
            if sender_data['chips'] < MIN_TRANSFER_BALANCE:
                bot.send_message(room_id, f"⚠️ @{user}, you need at least {format_k(MIN_TRANSFER_BALANCE)} chips to transfer.")
                return True
            
            # Condition: User must have enough chips for the requested amount
            if sender_data['chips'] < amt:
                bot.send_message(room_id, f"❌ @{user}, you don't have enough chips!"); return True
            
            # Execute Transfer
            if db.check_and_deduct_chips(uid, user, amt):
                db.update_balance(tid, args[0], chips_change=amt)
                bot.send_message(room_id, f"💸 @{user} transferred {format_k(amt)} to {args[0]}.")
            else:
                bot.send_message(room_id, "❌ Transaction failed.")
        except: pass
        return True

    # MY CHIPS (!mc)
    if cmd == "mc":
        bal = db.get_user_data(uid)['chips']
        bot.send_message(room_id, f"💰 @{user} Balance: {format_k(bal)} chips")
        return True

    # PROFILE / STATS (!ms / !s)
    if cmd in ["ms", "s"]:
        target_name = args[0].replace("@", "") if (cmd == "s" and args) else user
        tid = get_target_id(bot, room_id, target_name) if (cmd == "s" and args) else uid
        if not tid:
            bot.send_message(room_id, "User not found."); return True
        u_data = db.get_user_data(tid)
        game_rows = get_detailed_stats(tid)
        msg = f"👤 **PROFILE: {target_name.upper()}**\n━━━━━━━━━━━━━━\n"
        msg += f"🏆 Score: {format_k(u_data['points'])}\n💰 Chips: {format_k(u_data['chips'])}\n\n"
        if game_rows:
            msg += "🎮 **Game Records:**\n"
            for g_name, wins, earnings in game_rows:
                msg += f"• {g_name.capitalize()}: {wins} Wins | {format_k(earnings)} earned\n"
        bot.send_message(room_id, msg)
        return True

    # LEADERBOARDS (!gls / !chips)
    if cmd in ["gls", "chips"]:
        b_type = "score" if cmd == "gls" else "chips"
        col = "points" if cmd == "gls" else "chips"
        title = "GLOBAL SCORE RANK" if cmd == "gls" else "GLOBAL CHIPS RANK"
        conn = db.get_connection(); cur = conn.cursor()
        cur.execute(f"SELECT username, {col} FROM users ORDER BY {col} DESC LIMIT {PAGE_SIZE}")
        rows = cur.fetchall(); conn.close()
        msg = f"🏆 **{title}**\n━━━━━━━━━━━━━━\n"
        for i, (uname, val) in enumerate(rows, 1):
            sym = get_symbol(i, b_type)
            msg += f"{sym} {i}. {uname[:10]} : {format_k(val)}\n"
        msg += f"━━━━━━━━━━━━━━\nPage 1 | !nx for more (15s)"
        with SESSIONS_LOCK:
            SESSIONS[room_id] = {'type': b_type, 'page': 0, 'expires': now + SESSION_TIMEOUT}
        bot.send_message(room_id, msg); return True

    # NEXT PAGE (!nx)
    if cmd == "nx":
        with SESSIONS_LOCK:
            sess = SESSIONS.get(room_id)
            if not sess or now > sess['expires']: return False
            sess['page'] += 1; sess['expires'] = now + SESSION_TIMEOUT
            page = sess['page']; b_type = sess['type']
        col = "points" if b_type == "score" else "chips"
        offset = page * PAGE_SIZE
        conn = db.get_connection(); cur = conn.cursor()
        cur.execute(f"SELECT username, {col} FROM users ORDER BY {col} DESC LIMIT {PAGE_SIZE} OFFSET {offset}")
        rows = cur.fetchall(); conn.close()
        if not rows:
            bot.send_message(room_id, "End of ranking."); return True
        msg = f"🏆 **RANKING (Page {page+1})**\n━━━━━━━━━━━━━━\n"
        for i, (uname, val) in enumerate(rows, 1):
            rank_num = offset + i
            sym = get_symbol(rank_num, b_type)
            msg += f"{sym} {rank_num}. {uname[:10]} : {format_k(val)}\n"
        msg += f"━━━━━━━━━━━━━━\n!nx for next (15s)"
        bot.send_message(room_id, msg); return True

    return False
