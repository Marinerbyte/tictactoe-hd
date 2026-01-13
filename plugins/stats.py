import sys
import os
import traceback

# --- DB IMPORT ---
try:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    import db
except Exception as e:
    print(f"DB Import Error: {e}")

def handle_command(bot, command, room_id, user, args, data):
    user_id = data.get('userid', user) # Prefer UserID, fallback to Username
    cmd = command.lower().strip()

    # --- SQL PLACEHOLDER DETECTION ---
    # Postgres ke liye '%s', SQLite ke liye '?'
    ph = "%s" if db.DATABASE_URL.startswith("postgres") else "?"

    # --- 1. VIEW SCORE (!score, !balance) ---
    if cmd in ["score", "balance", "bal", "coins", "stats"]:
        
        target_user = user
        target_uid = str(user_id) # Ensure String format

        try:
            conn = db.get_connection()
            cur = conn.cursor()

            # A. Get Global Stats
            # Query format fix based on DB type
            query_user = f"SELECT global_score, wins FROM users WHERE user_id = {ph}"
            cur.execute(query_user, (target_uid,))
            row = cur.fetchone()

            if not row:
                bot.send_message(room_id, f"🚫 @{target_user}, aapka koi record nahi mila. Pehle game khelo!")
                conn.close()
                return True

            global_score, total_wins = row

            # B. Get Game-Specific Breakdown
            query_games = f"SELECT game_name, wins, earnings FROM game_stats WHERE user_id = {ph}"
            cur.execute(query_games, (target_uid,))
            game_rows = cur.fetchall()

            # C. Format Message
            msg = f"📊 **STATS: @{target_user}**\n"
            msg += f"💰 **Global Wallet:** {global_score} Coins\n"
            msg += f"🏆 **Total Wins:** {total_wins}\n"
            
            if game_rows:
                msg += "────────────────\n"
                for g_name, g_wins, g_earn in game_rows:
                    icon = "🎮"
                    if "ludo" in g_name: icon = "🎲"
                    elif "tic" in g_name: icon = "❌"
                    elif "race" in g_name: icon = "🐎"
                    
                    msg += f"{icon} **{g_name.capitalize()}:** {g_earn} Coins ({g_wins} Wins)\n"
            else:
                msg += "\n_(New Player)_"

            bot.send_message(room_id, msg)
            conn.close()
            return True

        except Exception as e:
            traceback.print_exc()
            bot.send_message(room_id, f"Stats Error: {e}")
            return True

    # --- 2. LEADERBOARD (!top) ---
    if cmd in ["top", "lb", "leaderboard"]:
        try:
            conn = db.get_connection()
            cur = conn.cursor()

            # Top 10 Richest Users
            cur.execute("SELECT username, global_score FROM users ORDER BY global_score DESC LIMIT 10")
            rows = cur.fetchall()
            conn.close()

            if not rows:
                bot.send_message(room_id, "📉 Leaderboard khali hai.")
                return True

            msg = "🏆 **GLOBAL LEADERBOARD** 🏆\n\n"
            for idx, (name, score) in enumerate(rows):
                rank = idx + 1
                icon = "🔹"
                if rank == 1: icon = "🥇"
                elif rank == 2: icon = "🥈"
                elif rank == 3: icon = "🥉"
                
                msg += f"{icon} **{name}**: {score}\n"

            bot.send_message(room_id, msg)
            return True

        except Exception as e:
            traceback.print_exc()
            return True

    return False
