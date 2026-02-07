import os
import sqlite3
import psycopg2
import threading
import time
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
        # Timeout badha diya taaki "Database Locked" error na aaye
        return sqlite3.connect("bot.db", check_same_thread=False, timeout=10)

def init_db():
    with db_lock:
        conn = get_connection()
        cur = conn.cursor()
        try:
            # Users Table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY, 
                    username TEXT, 
                    points INTEGER DEFAULT 0, 
                    chips INTEGER DEFAULT 10000, 
                    wins INTEGER DEFAULT 0
                )
            """)
            # Game Stats Table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS game_stats (
                    user_id TEXT, 
                    game_name TEXT, 
                    wins INTEGER DEFAULT 0, 
                    earnings INTEGER DEFAULT 0, 
                    PRIMARY KEY (user_id, game_name)
                )
            """)
            # Admins Table
            cur.execute("CREATE TABLE IF NOT EXISTS bot_admins (user_id TEXT PRIMARY KEY)")
            conn.commit()
            print("[DB] Database Connected & Tables Ready.")
        except Exception as e:
            print(f"[DB Error] Init Failed: {e}")
        finally:
            conn.close()

# --- ECONOMY CORE (SAFE MODE) ---

def get_user_data(user_id):
    """User ka data laata hai, agar nahi hai to create karta hai"""
    with db_lock:
        conn = get_connection()
        try:
            cur = conn.cursor()
            ph = "%s" if DATABASE_URL.startswith("postgres") else "?"
            cur.execute(f"SELECT points, chips FROM users WHERE user_id = {ph}", (str(user_id),))
            row = cur.fetchone()
            if row: 
                return {"points": row[0], "chips": row[1]}
            return {"points": 0, "chips": 10000} # Default values
        except Exception as e:
            print(f"[DB Error] Get Data: {e}")
            return {"points": 0, "chips": 0}
        finally:
            conn.close()

def update_balance(user_id, username, chips_change=0, points_change=0):
    """Safe Update function - Ye fail nahi hoga"""
    if not user_id or user_id == "BOT": return False
    
    with db_lock:
        conn = get_connection()
        try:
            cur = conn.cursor()
            ph = "%s" if DATABASE_URL.startswith("postgres") else "?"
            uid = str(user_id)
            
            # 1. Ensure User Exists
            if DATABASE_URL.startswith("postgres"):
                cur.execute(f"INSERT INTO users (user_id, username, points, chips, wins) VALUES ({ph}, {ph}, 0, 10000, 0) ON CONFLICT (user_id) DO NOTHING", (uid, username))
            else:
                cur.execute(f"INSERT OR IGNORE INTO users (user_id, username, points, chips, wins) VALUES ({ph}, {ph}, 0, 10000, 0)", (uid, username))
            
            # 2. Update Balance
            cur.execute(f"UPDATE users SET points = points + {ph}, chips = chips + {ph} WHERE user_id = {ph}", (points_change, chips_change, uid))
            conn.commit()
            return True
        except Exception as e:
            print(f"[DB Error] Update Balance: {e}")
            return False
        finally:
            conn.close()

def check_and_deduct_chips(user_id, username, amount):
    """Betting ke liye deduction logic"""
    if amount < 0: return False
    with db_lock:
        conn = get_connection()
        try:
            cur = conn.cursor()
            ph = "%s" if DATABASE_URL.startswith("postgres") else "?"
            uid = str(user_id)
            
            # Ensure user exists first
            if DATABASE_URL.startswith("postgres"):
                cur.execute(f"INSERT INTO users (user_id, username, points, chips, wins) VALUES ({ph}, {ph}, 0, 10000, 0) ON CONFLICT (user_id) DO NOTHING", (uid, username))
            else:
                cur.execute(f"INSERT OR IGNORE INTO users (user_id, username, points, chips, wins) VALUES ({ph}, {ph}, 0, 10000, 0)", (uid, username))

            # Check Balance
            cur.execute(f"SELECT chips FROM users WHERE user_id = {ph}", (uid,))
            row = cur.fetchone()
            
            if row and row[0] >= amount:
                cur.execute(f"UPDATE users SET chips = chips - {ph} WHERE user_id = {ph}", (amount, uid))
                conn.commit()
                return True
            return False
        except Exception as e:
            print(f"[DB Error] Deduct: {e}")
            return False
        finally:
            conn.close()

def add_game_result(user_id, username, game_name, chips_won, is_win=False, points_reward=0):
    """Game ka Result Save karna"""
    if not user_id or user_id == "BOT": return
    
    # Pehle Balance Update karo
    update_balance(user_id, username, chips_won, points_reward)
    
    with db_lock:
        conn = get_connection()
        try:
            cur = conn.cursor()
            ph = "%s" if DATABASE_URL.startswith("postgres") else "?"
            uid = str(user_id)
            win_val = 1 if is_win else 0
            
            # Update Total Wins
            cur.execute(f"UPDATE users SET wins = wins + {ph} WHERE user_id = {ph}", (win_val, uid))
            
            # Update Game Specific Stats
            # (Simplified check for SQLite/Postgres compatibility)
            cur.execute(f"SELECT wins FROM game_stats WHERE user_id={ph} AND game_name={ph}", (uid, game_name))
            if cur.fetchone():
                cur.execute(f"UPDATE game_stats SET wins=wins+{ph}, earnings=earnings+{ph} WHERE user_id={ph} AND game_name={ph}", (win_val, chips_won, uid, game_name))
            else:
                cur.execute(f"INSERT INTO game_stats (user_id, game_name, wins, earnings) VALUES ({ph}, {ph}, {ph}, {ph})", (uid, game_name, win_val, chips_won))
                
            conn.commit()
        except Exception as e:
            print(f"[DB Error] Game Result: {e}")
        finally:
            conn.close()

# --- ADMIN HELPERS ---
def add_admin(user_id):
    with db_lock:
        conn = get_connection()
        try:
            cur = conn.cursor()
            ph = "%s" if DATABASE_URL.startswith("postgres") else "?"
            if DATABASE_URL.startswith("postgres"):
                cur.execute(f"INSERT INTO bot_admins (user_id) VALUES ({ph}) ON CONFLICT (user_id) DO NOTHING", (str(user_id),))
            else:
                cur.execute(f"INSERT OR IGNORE INTO bot_admins (user_id) VALUES ({ph})", (str(user_id),))
            conn.commit()
            print(f"[DB] Admin Added: {user_id}")
            return True
        except Exception as e:
            print(f"[DB Error] Add Admin: {e}")
            return False
        finally:
            conn.close()

def get_all_admins():
    with db_lock:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT user_id FROM bot_admins")
            rows = [item[0] for item in cur.fetchall()]
            return rows
        except: return []
        finally: conn.close()
