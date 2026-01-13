import sys
import os
import threading

# Root folder se 'db.py' import karne ka setup
try:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    import db
except Exception as e:
    print(f"DB Import Error: {e}")

def handle_command(bot, command, room_id, user, args, data):
    """
    Commands:
    !score / !coins - Check Balance & Wins
    !top  - Leaderboard
    !free - Get 100 free coins (Once per day logic can be added later)
    """
    
    cmd_clean = command.lower().strip()
    
    # Database Connection
    conn = db.get_connection()
    if not conn: return False
    cur = conn.cursor()

    # Ensure user exists in DB
    try:
        # Postgres syntax
        try:
            cur.execute("INSERT INTO users (user_id, username, global_score, wins) VALUES (%s, %s, 0, 0) ON CONFLICT (user_id) DO NOTHING", (user, user))
        except:
            # SQLite syntax
            cur.execute("INSERT OR IGNORE INTO users (user_id, username, global_score, wins) VALUES (?, ?, 0, 0)", (user, user))
        conn.commit()
    except:
        pass

    # --- COMMAND: !SCORE / !COINS ---
    if cmd_clean in ["score", "coins", "bal", "balance"]:
        try:
            query = "SELECT global_score, wins FROM users WHERE user_id = %s"
            if not db.DATABASE_URL.startswith("postgres"): query = "SELECT global_score, wins FROM users WHERE user_id = ?"
            
            cur.execute(query, (user,))
            row = cur.fetchone()
            
            score = row[0] if row else 0
            wins = row[1] if row else 0
            
            msg = f"💳 **@{user}** Wallet:\n💰 Coins: **{score}**\n🏆 Wins: **{wins}**"
            bot.send_message(room_id, msg)
            return True
        except Exception as e:
            print(f"Score Error: {e}")

    # --- COMMAND: !TOP (Leaderboard) ---
    if cmd_clean == "top":
        try:
            cur.execute("SELECT username, global_score FROM users ORDER BY global_score DESC LIMIT 5")
            rows = cur.fetchall()
            
            msg = "🏆 **RICH LIST** 🏆\n"
            for i, row in enumerate(rows):
                medal = "🥇" if i==0 else "🥈" if i==1 else "🥉" if i==2 else f"{i+1}."
                msg += f"{medal} {row[0]}: {row[1]}\n"
            
            bot.send_message(room_id, msg)
            return True
        except Exception as e:
            print(f"Top Error: {e}")

    # --- COMMAND: !FREE (Testing Money) ---
    if cmd_clean == "free":
        try:
            query = "UPDATE users SET global_score = global_score + 1000 WHERE user_id = %s"
            if not db.DATABASE_URL.startswith("postgres"): query = "UPDATE users SET global_score = global_score + 1000 WHERE user_id = ?"
            
            cur.execute(query, (user,))
            conn.commit()
            bot.send_message(room_id, f"💰 @{user} received **1000 Free Coins**!")
            return True
        except: pass

    conn.close()
    return False
