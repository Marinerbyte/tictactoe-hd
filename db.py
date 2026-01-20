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
        
        # 1. User Economy Tables
        cur.execute("CREATE TABLE IF NOT EXISTS users (user_id TEXT PRIMARY KEY, username TEXT, global_score INTEGER DEFAULT 0, wins INTEGER DEFAULT 0)")
        cur.execute("CREATE TABLE IF NOT EXISTS game_stats (user_id TEXT, game_name TEXT, wins INTEGER DEFAULT 0, earnings INTEGER DEFAULT 0, PRIMARY KEY (user_id, game_name))")
        
        # 2. Admin Table
        cur.execute("CREATE TABLE IF NOT EXISTS bot_admins (user_id TEXT PRIMARY KEY)")
        
        # 3. NEW: Game Guides Table (Help Plugin ke liye)
        cur.execute("CREATE TABLE IF NOT EXISTS game_guides (game_name TEXT PRIMARY KEY, description TEXT)")
        
        conn.commit()
        conn.close()
        print("[DB] Ready (Economy + Admin + Guides).")

# --- MASTER FUNCTION (Economy) ---
def add_game_result(user_id, username, game_name, amount, is_win=False):
    if not user_id or user_id == "BOT": return

    with db_lock:
        try:
            conn = get_connection()
            cur = conn.cursor()
            
            is_postgres = DATABASE_URL.startswith("postgres")
            ph = "%s" if is_postgres else "?"
            
            win_count = 1 if is_win else 0
            uid = str(user_id)

            # Global Score
            if is_postgres:
                cur.execute(f"INSERT INTO users (user_id, username, global_score, wins) VALUES ({ph}, {ph}, 0, 0) ON CONFLICT (user_id) DO NOTHING", (uid, username))
            else:
                cur.execute(f"INSERT OR IGNORE INTO users (user_id, username, global_score, wins) VALUES ({ph}, {ph}, 0, 0)", (uid, username))
            
            q1 = f"UPDATE users SET global_score = global_score + {ph}, wins = wins + {ph} WHERE user_id = {ph}"
            cur.execute(q1, (amount, win_count, uid))

            # Game Specific Stats
            if is_postgres:
                cur.execute(f"INSERT INTO game_stats (user_id, game_name, wins, earnings) VALUES ({ph}, {ph}, 0, 0) ON CONFLICT (user_id, game_name) DO NOTHING", (uid, game_name))
            else:
                cur.execute(f"INSERT OR IGNORE INTO game_stats (user_id, game_name, wins, earnings) VALUES ({ph}, {ph}, 0, 0)", (uid, game_name))
            
            q2 = f"UPDATE game_stats SET wins = wins + {ph}, earnings = earnings + {ph} WHERE user_id = {ph} AND game_name = {ph}"
            cur.execute(q2, (win_count, amount, uid, game_name))

            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"[DB ERROR] {e}")

# --- ADMIN MANAGEMENT ---

def add_admin(user_id):
    if not user_id: return False
    with db_lock:
        try:
            conn = get_connection()
            cur = conn.cursor()
            is_postgres = DATABASE_URL.startswith("postgres")
            ph = "%s" if is_postgres else "?"
            uid = str(user_id)

            if is_postgres:
                cur.execute(f"INSERT INTO bot_admins (user_id) VALUES ({ph}) ON CONFLICT (user_id) DO NOTHING", (uid,))
            else:
                cur.execute(f"INSERT OR IGNORE INTO bot_admins (user_id) VALUES ({ph})", (uid,))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"[DB ERROR] add_admin: {e}")
            return False

def remove_admin(user_id):
    if not user_id: return False
    with db_lock:
        try:
            conn = get_connection()
            cur = conn.cursor()
            ph = "%s" if DATABASE_URL.startswith("postgres") else "?"
            cur.execute(f"DELETE FROM bot_admins WHERE user_id = {ph}", (str(user_id),))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"[DB ERROR] remove_admin: {e}")
            return False

def get_all_admins():
    with db_lock:
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT user_id FROM bot_admins")
            rows = [item[0] for item in cur.fetchall()]
            conn.close()
            return rows
        except Exception as e:
            print(f"[DB ERROR] get_all_admins: {e}")
            return []

# --- GUIDE SYSTEM FUNCTIONS (NEW) ---

def save_guide(game_name, description):
    """Guide ko save ya update karta hai"""
    with db_lock:
        try:
            conn = get_connection()
            cur = conn.cursor()
            is_postgres = DATABASE_URL.startswith("postgres")
            ph = "%s" if is_postgres else "?"
            
            # Insert or Replace logic
            if is_postgres:
                cur.execute(f"INSERT INTO game_guides (game_name, description) VALUES ({ph}, {ph}) ON CONFLICT (game_name) DO UPDATE SET description = EXCLUDED.description", (game_name.lower(), description))
            else:
                cur.execute(f"INSERT OR REPLACE INTO game_guides (game_name, description) VALUES ({ph}, {ph})", (game_name.lower(), description))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"[DB Error] Save Guide: {e}")
            return False

def get_guide(game_name):
    """Specific game ki guide lata hai"""
    with db_lock:
        try:
            conn = get_connection()
            cur = conn.cursor()
            ph = "%s" if DATABASE_URL.startswith("postgres") else "?"
            
            cur.execute(f"SELECT description FROM game_guides WHERE game_name = {ph}", (game_name.lower(),))
            row = cur.fetchone()
            conn.close()
            return row[0] if row else None
        except Exception as e:
            return None

def get_all_guide_names():
    """Saare games ke naam lata hai jinki guide available hai"""
    with db_lock:
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT game_name FROM game_guides")
            rows = cur.fetchall()
            conn.close()
            return [r[0] for r in rows]
        except: return []
