import os
import sqlite3
import psycopg2
import threading
import time
from urllib.parse import urlparse

# --- CONFIGURATION ---
# Local testing ke liye 'sqlite:///bot.db', Production ke liye env variable
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///bot.db")
db_lock = threading.Lock()

def get_connection():
    """Database se connect karne ka universal tareeka"""
    if DATABASE_URL.startswith("postgres"):
        try:
            return psycopg2.connect(DATABASE_URL, sslmode='require')
        except:
            # Fallback parsing agar seedha connect na ho
            result = urlparse(DATABASE_URL)
            return psycopg2.connect(
                database=result.path[1:],
                user=result.username,
                password=result.password,
                host=result.hostname,
                port=result.port
            )
    else:
        # Local file database
        return sqlite3.connect("bot.db", check_same_thread=False)

def init_db():
    """
    Tables banayega agar nahi hain.
    Yahan hum Chips aur Points alag-alag define kar rahe hain.
    """
    with db_lock:
        conn = get_connection()
        cur = conn.cursor()
        
        # 1. MAIN USER TABLE
        # user_id: Unique ID
        # chips: Jeb ka paisa (Kam/Zyada hoga)
        # points: Rank/XP (Sirf badhega, kabhi kam nahi hoga)
        if DATABASE_URL.startswith("postgres"):
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY, 
                    username TEXT, 
                    chips BIGINT DEFAULT 1000, 
                    points BIGINT DEFAULT 0,
                    total_wins INTEGER DEFAULT 0,
                    total_games INTEGER DEFAULT 0
                )
            """)
        else:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY, 
                    username TEXT, 
                    chips INTEGER DEFAULT 1000, 
                    points INTEGER DEFAULT 0,
                    total_wins INTEGER DEFAULT 0,
                    total_games INTEGER DEFAULT 0
                )
            """)

        # 2. GAME SPECIFIC STATS
        # Har game ka alag hisaab (Kitna jeeta, kitna haara)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS game_stats (
                user_id TEXT, 
                game_name TEXT, 
                wins INTEGER DEFAULT 0, 
                losses INTEGER DEFAULT 0,
                earnings BIGINT DEFAULT 0, 
                PRIMARY KEY (user_id, game_name)
            )
        """)
        
        # 3. ADMIN TABLE
        cur.execute("CREATE TABLE IF NOT EXISTS bot_admins (user_id TEXT PRIMARY KEY)")
        
        conn.commit()
        conn.close()
        print("[DB] Core System Ready (Dual Currency: Chips + Points)")

# ==========================================
# 💰 CORE TRANSACTIONS (Plugin Functions)
# ==========================================

def get_user_data(user_id):
    """User ka data laane ke liye (Chips, Points, etc.)"""
    with db_lock:
        try:
            conn = get_connection()
            cur = conn.cursor()
            ph = "%s" if DATABASE_URL.startswith("postgres") else "?"
            cur.execute(f"SELECT username, chips, points, total_wins FROM users WHERE user_id = {ph}", (str(user_id),))
            row = cur.fetchone()
            conn.close()
            return row # (username, chips, points, wins)
        except: return None

def update_balance(user_id, username, amount):
    """
    Sirf Chips update karne ke liye (Bet lagane ke waqt).
    Ye Points (Rank) ko touch nahi karega.
    """
    with db_lock:
        try:
            conn = get_connection()
            cur = conn.cursor()
            ph = "%s" if DATABASE_URL.startswith("postgres") else "?"
            uid = str(user_id)
            
            # Ensure user exists
            if DATABASE_URL.startswith("postgres"):
                cur.execute(f"INSERT INTO users (user_id, username) VALUES ({ph}, {ph}) ON CONFLICT (user_id) DO NOTHING", (uid, username))
            else:
                cur.execute(f"INSERT OR IGNORE INTO users (user_id, username) VALUES ({ph}, {ph})", (uid, username))
            
            # Update Chips
            cur.execute(f"UPDATE users SET chips = chips + {ph} WHERE user_id = {ph}", (amount, uid))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"[DB Error] Balance Update: {e}")
            return False

def add_game_result(user_id, username, game_name, profit_amount, is_win):
    """
    GAME KHATAM HONE PAR CALL KAREIN.
    - Chips: Profit add hoga.
    - Points: Sirf agar jeeta hai toh add honge.
    - Stats: Win/Loss update hoga.
    """
    if not user_id or user_id == "BOT": return

    with db_lock:
        try:
            conn = get_connection()
            cur = conn.cursor()
            ph = "%s" if DATABASE_URL.startswith("postgres") else "?"
            uid = str(user_id)
            
            # Logic:
            # 1. Chips hamesha update honge (Win hai to +, Loss hai to 0 kyunki bet pehle hi kat gayi thi)
            # 2. Points sirf Win par badhenge (jitna profit hua utne points)
            
            points_added = profit_amount if (is_win and profit_amount > 0) else 0
            win_inc = 1 if is_win else 0
            loss_inc = 0 if is_win else 1
            
            # Ensure user exists
            if DATABASE_URL.startswith("postgres"):
                cur.execute(f"INSERT INTO users (user_id, username) VALUES ({ph}, {ph}) ON CONFLICT (user_id) DO NOTHING", (uid, username))
            else:
                cur.execute(f"INSERT OR IGNORE INTO users (user_id, username) VALUES ({ph}, {ph})", (uid, username))

            # 1. Update Global Stats
            q1 = f"""
                UPDATE users 
                SET chips = chips + {ph}, 
                    points = points + {ph}, 
                    total_wins = total_wins + {ph}, 
                    total_games = total_games + 1 
                WHERE user_id = {ph}
            """
            cur.execute(q1, (profit_amount, points_added, win_inc, uid))

            # 2. Update Game-Specific Stats
            # Pehle row banayenge agar nahi hai
            if DATABASE_URL.startswith("postgres"):
                cur.execute(f"INSERT INTO game_stats (user_id, game_name) VALUES ({ph}, {ph}) ON CONFLICT (user_id, game_name) DO NOTHING", (uid, game_name))
            else:
                cur.execute(f"INSERT OR IGNORE INTO game_stats (user_id, game_name) VALUES ({ph}, {ph})", (uid, game_name))
            
            q2 = f"""
                UPDATE game_stats 
                SET wins = wins + {ph}, 
                    losses = losses + {ph}, 
                    earnings = earnings + {ph} 
                WHERE user_id = {ph} AND game_name = {ph}
            """
            cur.execute(q2, (win_inc, loss_inc, profit_amount, uid, game_name))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"[DB Error] Game Result: {e}")
            return False

# ==========================================
# 👑 ADMIN & LEADERBOARD HELPERS
# ==========================================

def get_top_players(limit=10, order_by="points"):
    """Leaderboard ke liye data lata hai"""
    with db_lock:
        try:
            conn = get_connection()
            cur = conn.cursor()
            # Order by 'points' (Rank) or 'chips' (Wealth)
            col = "points" if order_by == "points" else "chips"
            cur.execute(f"SELECT username, {col} FROM users ORDER BY {col} DESC LIMIT {limit}")
            rows = cur.fetchall()
            conn.close()
            return rows
        except: return []

def admin_set_chips(username, amount):
    """Admin command ke liye (Chips set karna)"""
    with db_lock:
        try:
            conn = get_connection()
            cur = conn.cursor()
            ph = "%s" if DATABASE_URL.startswith("postgres") else "?"
            cur.execute(f"UPDATE users SET chips = {ph} WHERE username = {ph}", (amount, username))
            conn.commit()
            conn.close()
            return True
        except: return False

def wipe_database():
    """RESET EVERYTHING (Danger Zone)"""
    with db_lock:
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("DELETE FROM users")
            cur.execute("DELETE FROM game_stats")
            conn.commit()
            conn.close()
            return True
        except: return False
