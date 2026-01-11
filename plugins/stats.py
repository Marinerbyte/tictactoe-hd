import sys
import os
import threading

# Root folder se 'db.py' ko import karne ka tarika
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import db

def handle_command(bot, command, room_id, user, args):
    """
    Commands:
    !score - Apna score dekhein
    !free  - Test karne ke liye 100 coins lein
    !top   - Top 5 ameer log dekhein
    """
    
    # Database connection
    conn = db.get_connection()
    if not conn: return False
    cur = conn.cursor()

    # Pehle ensure karein ki user database mein exist karta hai
    # (user_id ko hum username maan rahe hain abhi ke liye)
    try:
        cur.execute("INSERT INTO users (user_id, username) VALUES (%s, %s) ON CONFLICT (user_id) DO NOTHING", (user, user))
    except:
        # SQLite fallback syntax agar Postgres fail ho (waise Render par Postgres hai)
        try:
            cur.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user, user))
        except:
            pass
    conn.commit()

    # --- !score Command ---
    if command == "score":
        try:
            # Check for Postgres syntax first
            cur.execute("SELECT global_score, wins FROM users WHERE user_id = %s", (user,))
        except:
            # Fallback to SQLite
            cur.execute("SELECT global_score, wins FROM users WHERE user_id = ?", (user,))
            
        row = cur.fetchone()
        score = row[0] if row else 0
        wins = row[1] if row else 0
        
        bot.send_message(room_id, f"💳 @{user} | Coins: {score} | Wins: {wins}")
        conn.close()
        return True

    # --- !free Command (Testing ke liye) ---
    if command == "free":
        try:
            cur.execute("UPDATE users SET global_score = global_score + 100 WHERE user_id = %s", (user,))
        except:
            cur.execute("UPDATE users SET global_score = global_score + 100 WHERE user_id = ?", (user,))
            
        conn.commit()
        bot.send_message(room_id, f"💰 @{user} ko mile 100 Free Coins! Maze karo!")
        conn.close()
        return True

    # --- !top Command (Leaderboard) ---
    if command == "top":
        cur.execute("SELECT username, global_score FROM users ORDER BY global_score DESC LIMIT 5")
        rows = cur.fetchall()
        
        msg = "🏆 TOP 5 PLAYERS 🏆\n"
        for i, row in enumerate(rows):
            msg += f"{i+1}. {row[0]} - 💰 {row[1]}\n"
            
        bot.send_message(room_id, msg)
        conn.close()
        return True

    conn.close()
    return False
