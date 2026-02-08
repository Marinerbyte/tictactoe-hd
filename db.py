import os
import sqlite3
import psycopg2
import threading
import time
import traceback
from urllib.parse import urlparse

# ==========================================
# ⚙️ CONFIGURATION & LOCKING
# ==========================================
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///bot.db")
db_lock = threading.Lock()

def get_connection():
    """Universal Connection Handler with WAL Mode support for SQLite"""
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
        # isolation_level=None enable karta hai autocommit mode jo WAL mode ke liye best hai
        conn = sqlite3.connect("bot.db", check_same_thread=False, timeout=20, isolation_level=None)
        return conn

def get_ph():
    """Consistent Placeholder Handling"""
    return "%s" if DATABASE_URL.startswith("postgres") else "?"

# ==========================================
# 🚀 INITIALIZATION
# ==========================================

def init_db():
    """Initializes tables and sets performance pragmas"""
    with db_lock:
        conn = get_connection()
        try:
            cur = conn.cursor()
            # SQLite Performance Boost: Journaling Mode WAL
            if not DATABASE_URL.startswith("postgres"):
                cur.execute("PRAGMA journal_mode=WAL")
                cur.execute("PRAGMA synchronous=NORMAL")

            # Users Table: Score and Currency
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY, 
                    username TEXT, 
                    points INTEGER DEFAULT 0, 
                    chips INTEGER DEFAULT 10000, 
                    wins INTEGER DEFAULT 0
                )
            """)
            # Game Stats: Match Analytics (Wins/Earnings)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS game_stats (
                    user_id TEXT, 
                    game_name TEXT, 
                    wins INTEGER DEFAULT 0, 
                    earnings INTEGER DEFAULT 0, 
                    PRIMARY KEY (user_id, game_name)
                )
            """)
            # Admin Registry
            cur.execute("CREATE TABLE IF NOT EXISTS bot_admins (user_id TEXT PRIMARY KEY)")
            
            print("[DB] Industrial Grade Engine Initialized.")
        except Exception:
            print("[DB Critical] Init Failed!")
            traceback.print_exc()
        finally:
            conn.close()

# ==========================================
# 💰 ECONOMY CORE (Units: points=Score, chips=Currency)
# ==========================================

def get_user_data(user_id, username="Unknown User"):
    """Fetches or auto-creates user with consistent 10k default chips"""
    ph = get_ph()
    uid = str(user_id)
    uname = str(username).strip()
    
    with db_lock:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(f"SELECT points, chips FROM users WHERE user_id = {ph}", (uid,))
            row = cur.fetchone()
            if row:
                return {"points": row[0], "chips": row[1]}
            
            # Auto-Fill: Naya user register karo agar nahi hai
            cur.execute(f"INSERT INTO users (user_id, username, points, chips, wins) VALUES ({ph}, {ph}, 0, 10000, 0)", (uid, uname))
            return {"points": 0, "chips": 10000}
        except Exception:
            traceback.print_exc()
            return {"points": 0, "chips": 10000} # Consistent default fallback
        finally:
            conn.close()

def update_balance(user_id, username, chips_change=0, points_change=0):
    """
    Atomic Balance Update with Type Safety and Sanitized Upsert.
    chips_change: Amount to add/sub from currency.
    points_change: Amount to add/sub from permanent score.
    """
    if not user_id or str(user_id) == "BOT": return False
    
    ph = get_ph()
    uid, uname = str(user_id), str(username).strip()
    # Integer Casting for Safety
    c_delta, p_delta = int(chips_change), int(points_change)

    with db_lock:
        conn = get_connection()
        try:
            cur = conn.cursor()
            # High-Performance UPSERT
            if DATABASE_URL.startswith("postgres"):
                cur.execute(f"""
                    INSERT INTO users (user_id, username, points, chips, wins) 
                    VALUES ({ph}, {ph}, 0, 10000, 0) 
                    ON CONFLICT (user_id) DO UPDATE SET username = EXCLUDED.username
                """, (uid, uname))
            else:
                cur.execute(f"INSERT OR IGNORE INTO users (user_id, username, points, chips, wins) VALUES ({ph}, {ph}, 0, 10000, 0)", (uid, uname))
            
            cur.execute(f"UPDATE users SET points = points + {ph}, chips = chips + {ph} WHERE user_id = {ph}", (p_delta, c_delta, uid))
            return True
        except Exception:
            traceback.print_exc()
            return False
        finally:
            conn.close()

def check_and_deduct_chips(user_id, username, amount):
    """Betting Guard: Atomic check and partial-deduction protection"""
    amt = int(amount)
    if amt < 0: return False
    ph = get_ph()
    uid = str(user_id)
    
    # User guarantee
    update_balance(user_id, username, 0, 0)

    with db_lock:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(f"SELECT chips FROM users WHERE user_id = {ph}", (uid,))
            row = cur.fetchone()
            
            if row and row[0] >= amt:
                cur.execute(f"UPDATE users SET chips = chips - {ph} WHERE user_id = {ph}", (amt, uid))
                return True
            return False
        except Exception:
            traceback.print_exc()
            return False
        finally:
            conn.close()

# ==========================================
# 🎮 GAME ANALYTICS
# ==========================================

def add_game_result(user_id, username, game_name, chips_won, is_win=False, points_reward=0):
    """Saves match analytics using industrial Upsert logic and normalization"""
    if not user_id or str(user_id) == "BOT": return
    
    # Update master wallet and score
    update_balance(user_id, username, chips_won, points_reward)
    
    ph = get_ph()
    uid = str(user_id)
    # Case Normalization and Stripping
    g_name = str(game_name).lower().strip()
    win_val = 1 if is_win else 0
    c_won = int(chips_won)

    with db_lock:
        conn = get_connection()
        try:
            cur = conn.cursor()
            # Update Master Wins count
            cur.execute(f"UPDATE users SET wins = wins + {ph} WHERE user_id = {ph}", (win_val, uid))
            
            # Atomic Stats UPSERT (SQLite 3.24+ and Postgres compatible)
            upsert_query = f"""
                INSERT INTO game_stats (user_id, game_name, wins, earnings) 
                VALUES ({ph}, {ph}, {ph}, {ph})
                ON CONFLICT(user_id, game_name) DO UPDATE SET 
                wins = game_stats.wins + EXCLUDED.wins,
                earnings = game_stats.earnings + EXCLUDED.earnings
            """
            cur.execute(upsert_query, (uid, g_name, win_val, c_won))
        except Exception:
            print(f"[DB Error] add_game_result fail for {g_name}")
            traceback.print_exc()
        finally:
            conn.close()

# ==========================================
# 👑 ADMIN MANAGEMENT
# ==========================================

def add_admin(user_id):
    """Registers a new admin into the database registry"""
    ph = get_ph()
    uid = str(user_id)
    with db_lock:
        conn = get_connection()
        try:
            cur = conn.cursor()
            # Clean ON CONFLICT syntax
            cur.execute(f"INSERT INTO bot_admins (user_id) VALUES ({ph}) ON CONFLICT(user_id) DO NOTHING", (uid,))
            return True
        except Exception:
            traceback.print_exc()
            return False
        finally:
            conn.close()

def get_all_admins():
    """Returns a list of all registered Admin IDs"""
    with db_lock:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT user_id FROM bot_admins")
            return [str(item[0]) for item in cur.fetchall()]
        except Exception:
            traceback.print_exc()
            return []
        finally:
            conn.close()
