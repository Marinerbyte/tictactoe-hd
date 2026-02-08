import os
import sqlite3
import psycopg2
import threading
import traceback
from urllib.parse import urlparse

# CONFIG
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///bot.db")
db_lock = threading.Lock()

def get_connection():
    if DATABASE_URL.startswith("postgres"):
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        conn.autocommit = True
        return conn
    else:
        conn = sqlite3.connect("bot.db", check_same_thread=False, timeout=20)
        conn.isolation_level = None
        return conn

def get_ph():
    return "%s" if DATABASE_URL.startswith("postgres") else "?"

def init_db():
    with db_lock:
        conn = get_connection()
        try:
            cur = conn.cursor()
            if not DATABASE_URL.startswith("postgres"):
                cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("CREATE TABLE IF NOT EXISTS users (user_id TEXT PRIMARY KEY, username TEXT, points BIGINT DEFAULT 0, chips BIGINT DEFAULT 10000, wins INTEGER DEFAULT 0)")
            cur.execute("CREATE TABLE IF NOT EXISTS game_stats (user_id TEXT, game_name TEXT, wins INTEGER DEFAULT 0, earnings BIGINT DEFAULT 0, PRIMARY KEY (user_id, game_name))")
            cur.execute("CREATE TABLE IF NOT EXISTS bot_admins (user_id TEXT PRIMARY KEY)")
            print("[DB] Polished Engine Initialized.")
        except: traceback.print_exc()
        finally: conn.close()

# ECONOMY CORE
def get_user_data(user_id, username="Unknown"):
    ph, uid = get_ph(), str(user_id)
    with db_lock:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(f"SELECT points, chips FROM users WHERE user_id = {ph}", (uid,))
            row = cur.fetchone()
            if row: return {"points": row[0], "chips": row[1]}
            cur.execute(f"INSERT INTO users (user_id, username) VALUES ({ph}, {ph})", (uid, str(username)))
            return {"points": 0, "chips": 10000}
        except:
            traceback.print_exc()
            return {"points": 0, "chips": 10000}
        finally: conn.close()

def update_balance(user_id, username, chips_change=0, points_change=0):
    if not user_id or str(user_id) == "BOT": return False
    ph = get_ph()
    uid, uname = str(user_id), str(username)
    c_delta, p_delta = int(chips_change), int(points_change)
    
    # Ensure user exists
    get_user_data(uid, uname)
    
    with db_lock:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(f"UPDATE users SET points = points + {ph}, chips = chips + {ph} WHERE user_id = {ph}", (p_delta, c_delta, uid))
            return True
        except:
            traceback.print_exc()
            return False
        finally: conn.close()

def check_and_deduct_chips(user_id, username, amount):
    amt = int(amount)
    if amt < 0: return False
    ph, uid = get_ph(), str(user_id)
    
    current_data = get_user_data(uid, username)
    if current_data and current_data['chips'] >= amt:
        with db_lock:
            conn = get_connection()
            try:
                cur = conn.cursor()
                cur.execute(f"UPDATE users SET chips = chips - {ph} WHERE user_id = {ph}", (amt, uid))
                return True
            except:
                traceback.print_exc()
                return False
            finally: conn.close()
    return False

def add_game_result(user_id, username, game_name, chips_won, is_win=False, points_reward=0):
    update_balance(user_id, username, chips_won, points_reward)
    ph, uid, g_name = get_ph(), str(user_id), str(game_name).lower()
    win_val, c_won = 1 if is_win else 0, int(chips_won)
    
    with db_lock:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(f"UPDATE users SET wins = wins + {ph} WHERE user_id = {ph}", (win_val, uid))
            upsert_q = f"INSERT INTO game_stats (user_id, game_name, wins, earnings) VALUES ({ph}, {ph}, {ph}, {ph}) ON CONFLICT(user_id, game_name) DO UPDATE SET wins = game_stats.wins + EXCLUDED.wins, earnings = game_stats.earnings + EXCLUDED.earnings"
            cur.execute(upsert_q, (uid, g_name, win_val, c_won))
        except: traceback.print_exc()
        finally: conn.close()

# ADMIN
def add_admin(user_id):
    ph, uid = get_ph(), str(user_id)
    with db_lock:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(f"INSERT INTO bot_admins (user_id) VALUES ({ph}) ON CONFLICT(user_id) DO NOTHING", (uid,))
            return True
        except:
            traceback.print_exc()
            return False
        finally: conn.close()

def get_all_admins():
    with db_lock:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT user_id FROM bot_admins")
            return [str(item[0]) for item in cur.fetchall()]
        except:
            traceback.print_exc()
            return []
        finally: conn.close()
