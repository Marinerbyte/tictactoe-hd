import os
import sqlite3
import psycopg2
import threading
import traceback
from urllib.parse import urlparse

# ==========================================
# ⚙️ CONFIG & CONNECTION
# ==========================================
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///bot.db")
db_lock = threading.Lock()

def get_connection():
    """Industrial Grade Connection: Autocommit enabled"""
    if DATABASE_URL.startswith("postgres"):
        # Postgres connection with autocommit
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        conn.autocommit = True
        return conn
    else:
        # SQLite with WAL mode and autocommit
        conn = sqlite3.connect("bot.db", check_same_thread=False, timeout=20)
        conn.isolation_level = None # Enables autocommit
        return conn

def get_ph():
    return "%s" if DATABASE_URL.startswith("postgres") else "?"

# ==========================================
# 🚀 INITIALIZATION
# ==========================================
def init_db():
    with db_lock:
        conn = get_connection()
        try:
            cur = conn.cursor()
            if not DATABASE_URL.startswith("postgres"):
                cur.execute("PRAGMA journal_mode=WAL") # For high concurrency
            
            cur.execute("CREATE TABLE IF NOT EXISTS users (user_id TEXT PRIMARY KEY, username TEXT, points INTEGER DEFAULT 0, chips INTEGER DEFAULT 10000, wins INTEGER DEFAULT 0)")
            cur.execute("CREATE TABLE IF NOT EXISTS game_stats (user_id TEXT, game_name TEXT, wins INTEGER DEFAULT 0, earnings INTEGER DEFAULT 0, PRIMARY KEY (user_id, game_name))")
            cur.execute("CREATE TABLE IF NOT EXISTS bot_admins (user_id TEXT PRIMARY KEY)")
            
            print("[DB] Industrial Engine Initialized.")
        except Exception:
            print("[DB Critical] Init Failed!")
            traceback.print_exc()
        finally:
            conn.close()

# ==========================================
# 💰 ECONOMY CORE (FAIL-SAFE)
# ==========================================
def execute_query(query, params=(), fetch=None):
    """Universal function to handle all DB interactions"""
    with db_lock:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(query, params)
            if fetch == "one": return cur.fetchone()
            if fetch == "all": return cur.fetchall()
            return True # For INSERT, UPDATE, DELETE
        except Exception:
            traceback.print_exc()
            return None if fetch else False
        finally:
            conn.close()

def get_user_data(user_id, username="Unknown"):
    ph = get_ph()
    uid = str(user_id)
    
    user = execute_query(f"SELECT points, chips FROM users WHERE user_id = {ph}", (uid,), fetch="one")
    if user:
        return {"points": user[0], "chips": user[1]}
    
    # Auto-create user
    execute_query(f"INSERT INTO users (user_id, username) VALUES ({ph}, {ph})", (uid, str(username)))
    return {"points": 0, "chips": 10000}

def update_balance(user_id, username, chips_change=0, points_change=0):
    if not user_id or str(user_id) == "BOT": return False
    ph = get_ph()
    uid, uname = str(user_id), str(username)
    c_delta, p_delta = int(chips_change), int(points_change)

    # Ensure user exists first
    get_user_data(uid, uname)
    
    # Update
    return execute_query(f"UPDATE users SET points = points + {ph}, chips = chips + {ph} WHERE user_id = {ph}", (p_delta, c_delta, uid))

def check_and_deduct_chips(user_id, username, amount):
    amt = int(amount)
    if amt < 0: return False
    ph = get_ph()
    uid = str(user_id)
    
    current_data = get_user_data(uid, username)
    
    if current_data and current_data['chips'] >= amt:
        return execute_query(f"UPDATE users SET chips = chips - {ph} WHERE user_id = {ph}", (amt, uid))
    return False

def add_game_result(user_id, username, game_name, chips_won, is_win=False, points_reward=0):
    if not user_id or str(user_id) == "BOT": return
    
    update_balance(user_id, username, chips_won, points_reward)
    
    ph = get_ph()
    uid, g_name = str(user_id), str(game_name).lower()
    win_val, c_won = 1 if is_win else 0, int(chips_won)
    
    execute_query(f"UPDATE users SET wins = wins + {ph} WHERE user_id = {ph}", (win_val, uid))
    
    upsert_q = f"""
        INSERT INTO game_stats (user_id, game_name, wins, earnings) VALUES ({ph}, {ph}, {ph}, {ph})
        ON CONFLICT(user_id, game_name) DO UPDATE SET 
        wins = game_stats.wins + EXCLUDED.wins, earnings = game_stats.earnings + EXCLUDED.earnings
    """
    execute_query(upsert_q, (uid, g_name, win_val, c_won))

def add_admin(user_id):
    ph = get_ph()
    uid = str(user_id)
    return execute_query(f"INSERT INTO bot_admins (user_id) VALUES ({ph}) ON CONFLICT(user_id) DO NOTHING", (uid,))

def get_all_admins():
    rows = execute_query("SELECT user_id FROM bot_admins", fetch="all")
    return [str(item[0]) for item in rows] if rows else []
