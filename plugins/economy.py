import os
import sys
import math
import db

# --- CONFIG ---
MASTER_USER = "yasin"
CURRENCY = "Chips 🎰"
PAGE_SIZE = 10  # Ek page par 10 bande

def setup(bot):
    print("[Economy] Text-based Stats, Pagination & Help Ready.")

# --- UTILS ---
def get_detailed_stats(uid):
    conn = db.get_connection()
    cur = conn.cursor()
    # Game wise wins fetch
    cur.execute("SELECT game_name, wins FROM game_stats WHERE user_id = %s", (str(uid),))
    rows = cur.fetchall()
    conn.close()
    
    stats = {"mines": 0, "tictactoe": 0}
    for name, wins in rows:
        if name in stats: 
            stats[name] = wins
    return stats

def handle_command(bot, command, room_id, user, args, data):
    cmd = command.lower().strip()
    uid = str(data.get('userid', user))
    ph = "%s" if db.DATABASE_URL.startswith("postgres") else "?"

    # 1. !help score - Commands ki list dikhane ke liye
    if cmd == "help":
        if args and args[0].lower() == "score":
            help_msg =  "📖 ECONOMY HELP MENU\n"
            help_msg += "━━━━━━━━━━━━━━━━━━\n"
            help_msg += "💰 !score : Apna profile aur Chips dekhein.\n"
            help_msg += "🏆 !global [page] : Global Leaderboard (10 per page).\n"
            help_msg += f"🎰 Reward: Games jeet kar {CURRENCY} kamayein.\n"
            
            if user.lower() == MASTER_USER:
                help_msg += "\n👑 MASTER COMMANDS:\n"
                help_msg += "🔹 !set @user [amt] : Balance set karein.\n"
                help_msg += "🔹 !reset @user : User data clear karein.\n"
                help_msg += "🔹 !wipeall : Poori DB saaf karein.\n"
            
            help_msg += "━━━━━━━━━━━━━━━━━━"
            bot.send_message(room_id, help_msg)
            return True

    # 2. !score - Text-Based Profile
    if cmd == "score":
        try:
            conn = db.get_connection()
            cur = conn.cursor()
            cur.execute(f"SELECT global_score, wins FROM users WHERE user_id = {ph}", (uid,))
            row = cur.fetchone()
            conn.close()

            chips = row[0] if row else 0
            total_wins = row[1] if row else 0
            g_stats = get_detailed_stats(uid)

            msg =  f"👤 PROFILE: @{user}\n"
            msg += f"━━━━━━━━━━━━━━━━━━\n"
            msg += f"💰 BALANCE: {chips:,} {CURRENCY}\n"
            msg += f"🏆 TOTAL WINS: {total_wins}\n"
            msg += f"━━━━━━━━━━━━━━━━━━\n"
            msg += f"🎮 GAME STATS:\n"
            msg += f"💣 Mines: {g_stats['mines']} Wins\n"
            msg += f"❌ TicTacToe: {g_stats['tictactoe']} Wins\n"
            msg += f"━━━━━━━━━━━━━━━━━━"
            
            bot.send_message(room_id, msg)
            return True
        except Exception as e:
            print(f"Score Error: {e}")
            return True

    # 3. !global [page] - Pagination System
    if cmd == "global":
        try:
            page = 1
            if args and args[0].isdigit():
                page = int(args[0])
            
            offset = (page - 1) * PAGE_SIZE
            conn = db.get_connection()
            cur = conn.cursor()
            
            cur.execute("SELECT COUNT(*) FROM users")
            total_users = cur.fetchone()[0]
            total_pages = math.ceil(total_users / PAGE_SIZE)

            cur.execute(f"SELECT username, global_score FROM users ORDER BY global_score DESC LIMIT {PAGE_SIZE} OFFSET {offset}")
            rows = cur.fetchall()
            conn.close()

            if not rows:
                bot.send_message(room_id, f"❌ Page {page} khali hai. Total pages: {total_pages}")
                return True

            msg = f"🏆 GLOBAL LEADERBOARD (Page {page}/{total_pages})\n"
            msg += f"━━━━━━━━━━━━━━━━━━\n"
            for i, (name, score) in enumerate(rows):
                rank = offset + i + 1
                medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"#{rank}"
                msg += f"{medal} {name} • {score:,}\n"
            
            if page < total_pages:
                msg += f"━━━━━━━━━━━━━━━━━━\n"
                msg += f"👉 Type !global {page + 1} for next page"
            
            bot.send_message(room_id, msg)
            return True
        except Exception as e:
            print(f"Global Error: {e}")
            return True

    # 4. ADMIN COMMANDS (Master Only)
    if user.lower() == MASTER_USER:
        if cmd == "set":
            if len(args) < 2: return True
            target = args[0].replace("@", "")
            try:
                amount = int(args[1])
                target_id = None
                for r_name, details in bot.room_details.items():
                    if target.lower() in details.get('id_map', {}):
                        target_id = details['id_map'][target.lower()]
                        break
                
                if target_id:
                    conn = db.get_connection()
                    cur = conn.cursor()
                    cur.execute(f"UPDATE users SET global_score = {ph} WHERE user_id = {ph}", (amount, target_id))
                    conn.commit(); conn.close()
                    bot.send_message(room_id, f"✅ @{target} ka balance {amount} Chips set ho gaya.")
            except: pass
            return True

        if cmd == "reset":
            if not args: return True
            target = args[0].replace("@", "")
            target_id = None
            for r_name, details in bot.room_details.items():
                if target.lower() in details.get('id_map', {}):
                    target_id = details['id_map'][target.lower()]
                    break
            if target_id:
                conn = db.get_connection()
                cur = conn.cursor()
                cur.execute(f"UPDATE users SET global_score = 0, wins = 0 WHERE user_id = {ph}", (target_id,))
                cur.execute(f"DELETE FROM game_stats WHERE user_id = {ph}", (target_id,))
                conn.commit(); conn.close()
                bot.send_message(room_id, f"🧹 @{target} ke stats reset kar diye gaye.")
            return True

        if cmd == "wipeall":
            conn = db.get_connection()
            cur = conn.cursor()
            cur.execute("DELETE FROM users")
            cur.execute("DELETE FROM game_stats")
            conn.commit(); conn.close()
            bot.send_message(room_id, "🔥 DATABASE WIPED. Sabka score zero ho gaya.")
            return True

    return False
