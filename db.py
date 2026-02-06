import os
import sqlite3
import psycopg2
import threading
from urllib.parse import urlparse

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///bot.db")
db_lock = threading.Lock()

def get_connection():
    if DATABASE_URL.startswith("postgres"):
        try:
            return psycopg2.connect(DATABASE_URL, sslmode='require')
        except:
            result = urlparse(DATABASE_URL)
            return psycopg2.connect(
                database=result.path[1:], user=result.username,
                password=result.password, host=result.hostname, port=result.port
            )
    else:
        return sqlite3.connect("bot.db", check_same_thread=False)

def init_db():
    with db_lock:
        conn = get_connection(); cur = conn.cursor()
        # Naya Table Structure: points (reputation) aur chips (paisa)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY, 
                username TEXT, 
                points INTEGER DEFAULT 0, 
                chips INTEGER DEFAULT 10000, 
                wins INTEGER DEFAULT 0
            )
        """)
        cur.execute("CREATE TABLE IF NOT EXISTS game_stats (user_id TEXT, game_name TEXT, wins INTEGER DEFAULT 0, earnings INTEGER DEFAULT 0, PRIMARY KEY (user_id, game_name))")
        cur.execute("CREATE TABLE IF NOT EXISTS bot_admins (user_id TEXT PRIMARY KEY)")
        cur.execute("CREATE TABLE IF NOT EXISTS game_guides (game_name TEXT PRIMARY KEY, description TEXT)")
        conn.commit(); conn.close()
        print("[DB] Points & Chips Economy System Ready.")

# --- ECONOMY CORE ---

def get_user_data(user_id):
    """User ka balance aur points check karne ke liye"""
    with db_lock:
        try:
            conn = get_connection(); cur = conn.cursor()
            ph = "%s" if DATABASE_URL.startswith("postgres") else "?"
            cur.execute(f"SELECT points, chips FROM users WHERE user_id = {ph}", (str(user_id),))
            row = cur.fetchone(); conn.close()
            if row: return {"points": row[0], "chips": row[1]}
            return {"points": 0, "chips": 10000}
        except: return {"points": 0, "chips": 0}

def update_balance(user_id, username, chips_change=0, points_change=0):
    """Points aur Chips ko update karne wala master function"""
    if not user_id or user_id == "BOT": return False
    with db_lock:
        try:
            conn = get_connection(); cur = conn.cursor()
            ph = "%s" if DATABASE_URL.startswith("postgres") else "?"
            uid = str(user_id)
            if DATABASE_URL.startswith("postgres"):
                cur.execute(f"INSERT INTO users (user_id, username, points, chips, wins) VALUES ({ph}, {ph}, 0, 10000, 0) ON CONFLICT (user_id) DO NOTHING", (uid, username))
            else:
                cur.execute(f"INSERT OR IGNORE INTO users (user_id, username, points, chips, wins) VALUES ({ph}, {ph}, 0, 10000, 0)", (uid, username))
            
            cur.execute(f"UPDATE users SET points = points + {ph}, chips = chips + {ph} WHERE user_id = {ph}", (points_change, chips_change, uid))
            conn.commit(); conn.close()
            return True
        except: return False

def check_and_deduct_chips(user_id, username, amount):
    """PvP games ke liye: Bet kaatne ke liye pehle check karta hai"""
    if amount < 0: return False
    with db_lock:
        try:
            conn = get_connection(); cur = conn.cursor()
            ph = "%s" if DATABASE_URL.startswith("postgres") else "?"
            uid = str(user_id)
            cur.execute(f"SELECT chips FROM users WHERE user_id = {ph}", (uid,))
            row = cur.fetchone()
            if row and row[0] >= amount:
                cur.execute(f"UPDATE users SET chips = chips - {ph} WHERE user_id = {ph}", (amount, uid))
                conn.commit(); conn.close()
                return True
            conn.close(); return False
        except: return False

def add_game_result(user_id, username, game_name, chips_won, is_win=False, points_reward=0):
    """Game khatam hone par score save karne ke liye"""
    if not user_id or user_id == "BOT": return
    update_balance(user_id, username, chips_won, points_reward)
    with db_lock:
        try:
            conn = get_connection(); cur = conn.cursor()
            ph = "%s" if DATABASE_URL.startswith("postgres") else "?"
            uid = str(user_id); win_val = 1 if is_win else 0
            cur.execute(f"UPDATE users SET wins = wins + {ph} WHERE user_id = {ph}", (win_val, uid))
            # Stats table update logic
            conn.commit(); conn.close()
        except: pass

# --- ADMIN & GUIDES (No Changes) ---
def add_admin(user_id):
    with db_lock:
        try:
            conn = get_connection(); cur = conn.cursor()
            ph = "%s" if DATABASE_URL.startswith("postgres") else "?"
            if DATABASE_URL.startswith("postgres"):
                cur.execute(f"INSERT INTO bot_admins (user_id) VALUES ({ph}) ON CONFLICT (user_id) DO NOTHING", (str(user_id),))
            else:
                cur.execute(f"INSERT OR IGNORE INTO bot_admins (user_id) VALUES ({ph})", (str(user_id),))
            conn.commit(); conn.close(); return True
        except: return False

def get_all_admins():
    with db_lock:
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute("SELECT user_id FROM bot_admins")
            rows = [item[0] for item in cur.fetchall()]
            conn.close(); return rows
        except: return []

def save_guide(g, d):
    with db_lock:
        try:
            conn = get_connection(); cur = conn.cursor()
            ph = "%s" if DATABASE_URL.startswith("postgres") else "?"
            if DATABASE_URL.startswith("postgres"):
                cur.execute(f"INSERT INTO game_guides (game_name, description) VALUES ({ph}, {ph}) ON CONFLICT (game_name) DO UPDATE SET description = EXCLUDED.description", (g.lower(), d))
            else:
                cur.execute(f"INSERT OR REPLACE INTO game_guides (game_name, description) VALUES ({ph}, {ph})", (g.lower(), d))
            conn.commit(); conn.close(); return True
        except: return False

def get_guide(g):
    with db_lock:
        try:
            conn = get_connection(); cur = conn.cursor()
            ph = "%s" if DATABASE_URL.startswith("postgres") else "?"
            cur.execute(f"SELECT description FROM game_guides WHERE game_name = {ph}", (g.lower(),))
            r = cur.fetchone(); conn.close(); return r[0] if r else None
        except: return None

def get_all_guide_names():
    with db_lock:
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute("SELECT game_name FROM game_guides")
            r = cur.fetchall(); conn.close(); return [x[0] for x in r]
        except: return []
