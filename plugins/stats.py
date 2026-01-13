import sys
import os
import threading
import traceback

# --- DB IMPORT ---
try:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    import db
except Exception as e:
    print(f"DB Import Error: {e}")

def handle_command(bot, command, room_id, user, args, data):
    user_id = data.get('userid', user)
    cmd = command.lower().strip()

    # --- 1. VIEW SCORE (!score, !balance, !bal) ---
    if cmd in ["score", "balance", "bal", "coins", "stats"]:
        
        # Agar user kisi aur ka score dekhna chahe (!score @username)
        # (Abhi ke liye simple rakhte hain, sirf apna score)
        target_user = user
        target_uid = user_id

        try:
            conn = db.get_connection()
            cur = conn.cursor()

            # A. Get Global Stats
            cur.execute("SELECT global_score, wins FROM users WHERE user_id = ?", (str(target_uid),))
            row = cur.fetchone()

            if not row:
                bot.send_message(room_id, f"🚫 @{target_user}, aapne abhi tak koi game nahi khela!")
                conn.close()
                return True

            global_score, total_wins = row

            # B. Get Game-Specific Breakdown
            cur.execute("SELECT game_name, wins, earnings FROM game_stats WHERE user_id = ?", (str(target_uid),))
            game_rows = cur.fetchall()

            # C. Format Message
            msg = f"📊 **STATS: @{target_user}**\n"
            msg += f"💰 **Wallet:** {global_score} Coins\n"
            msg += f"🏆 **Total Wins:** {total_wins}\n"
            
            if game_rows:
                msg += "\n**Game History:**\n"
                for g_name, g_wins, g_earn in game_rows:
                    # Emoji mapping based on game name
                    icon = "🎮"
                    if "ludo" in g_name: icon = "🎲"
                    elif "tic" in g_name: icon = "❌"
                    elif "race" in g_name: icon = "🐎"
                    
                    msg += f"{icon} **{g_name.capitalize()}:** {g_earn} Coins ({g_wins} Wins)\n"
            else:
                msg += "\n_(No specific game stats yet)_"

            bot.send_message(room_id, msg)
            conn.close()
            return True

        except Exception as e:
            traceback.print_exc()
            bot.send_message(room_id, "Error fetching stats.")
            return True

    # --- 2. LEADERBOARD (!top, !leaderboard) ---
    if cmd in ["top", "lb", "leaderboard"]:
        try:
            conn = db.get_connection()
            cur = conn.cursor()

            # Top 10 Richest Users
            cur.execute("SELECT username, global_score FROM users ORDER BY global_score DESC LIMIT 10")
            rows = cur.fetchall()
            conn.close()

            if not rows:
                bot.send_message(room_id, "📉 Leaderboard is empty.")
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
