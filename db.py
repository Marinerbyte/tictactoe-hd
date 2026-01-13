import os
import sqlite3
import psycopg2
import threading
from urllib.parse import urlparse

# Database URL
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///bot.db")
db_lock = threading.Lock()

def get_connection():
    if DATABASE_URL.startswith("postgres"):
        try:
            return psycopg2.connect(DATABASE_URL, sslmode='require')
        except:
            result = urlparse(DATABASE_URL)
            return psycopg2.connect(
                database=result.path[1:],
                user=result.username,
                password=result.password,
                host=result.hostname,
                port=result.port
            )
    else:
        return sqlite3.connect("bot.db", check_same_thread=False)

def init_db():
    with db_lock:
        conn = get_connection()
        cur = conn.cursor()
        
        # 1. User Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT,
                global_score INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0
            )
        """)
        
        # 2. Game Stats Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS game_stats (
                user_id TEXT,
                game_name TEXT,
                wins INTEGER DEFAULT 0,
                earnings INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, game_name)
            )
        """)
        
        conn.commit()
        conn.close()
        print("[DB] Ready.")

# --- MASTER FUNCTION ---
# Ye function saare games ka score save karega
def add_game_result(user_id, username, game_name, amount, is_win=False):
    if not user_id or user_id == "BOT": return

    with db_lock:
        try:
            conn = get_connection()
            cur = conn.cursor()
            
            ph = "%s" if DATABASE_URL.startswith("postgres") else "?"
            win_count = 1 if is_win else 0
            uid = str(user_id)

            # 1. Update Global Score
            try: cur.execute(f"INSERT INTO users (user_id, username, global_score, wins) VALUES ({ph}, {ph}, 0, 0)", (uid, username))
            except: pass 
            
            q1 = f"UPDATE users SET global_score = global_score + {ph}, wins = wins + {ph} WHERE user_id = {ph}"
            cur.execute(q1, (amount, win_count, uid))

            # 2. Update Game Specific Score
            try: cur.execute(f"INSERT INTO game_stats (user_id, game_name, wins, earnings) VALUES ({ph}, {ph}, 0, 0)", (uid, game_name))
            except: pass
            
            q2 = f"UPDATE game_stats SET wins = wins + {ph}, earnings = earnings + {ph} WHERE user_id = {ph} AND game_name = {ph}"
            cur.execute(q2, (win_count, amount, uid, game_name))

            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[DB Error] {e}")
