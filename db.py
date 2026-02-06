import os
import sqlite3
import psycopg2
import threading
from urllib.parse import urlparse

# --- CONFIGURATION ---
# Auto-detects: Cloud Database (Postgres) OR Local File (sqlite)
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///bot.db")
db_lock = threading.Lock()

# ==========================================
# 🛠️ INTERNAL CONNECTION ENGINE
# ==========================================

def get_connection():
    """Smart Connection Handler"""
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
        # Check_same_thread=False is needed for multi-threaded bots
        return sqlite3.connect("bot.db", check_same_thread=False)

def init_db():
    """Initializes the database structure. Safe to run multiple times."""
    with db_lock:
        conn = get_connection()
        cur = conn.cursor()
        
        # TABLE 1: USERS (Global Wallet & Rank)
        # chips = Currency (Spending Money)
        # points = Score/XP (Permanent Level)
        # total_games = Only counts Finished games (Win/Loss/Draw)
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

        # TABLE 2: GAME STATS (Detailed History per Game)
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
        
        # TABLE 3: ADMINS (For future panel access)
        cur.execute("CREATE TABLE IF NOT EXISTS bot_admins (user_id TEXT PRIMARY KEY)")
        
        conn.commit()
        conn.close()
        print("[DB] Bulletproof Engine Ready. (Chips + Points System)")

# ==========================================
# 💳 TRANSACTION SYSTEM (Use this in Games)
# ==========================================

def check_and_deduct(user_id, username, amount):
    """
    GAME START se pehle call karein.
    - Agar Chips >= Amount hai: Chips kaat lega aur True return karega.
    - Agar Chips kam hain: False return karega (Game mat start karna).
    - Amount 0 hai (Free game): True return karega.
    """
    if amount < 0: return False # Security check
    if amount == 0: return True # Free game, allow immediately

    with db_lock:
        try:
            conn = get_connection(); cur = conn.cursor()
            ph = "%s" if DATABASE_URL.startswith("postgres") else "?"
            uid = str(user_id)

            # 1. Ensure User Exists
            if DATABASE_URL.startswith("postgres"):
                cur.execute(f"INSERT INTO users (user_id, username) VALUES ({ph}, {ph}) ON CONFLICT (user_id) DO NOTHING", (uid, username))
            else:
                cur.execute(f"INSERT OR IGNORE INTO users (user_id, username) VALUES ({ph}, {ph})", (uid, username))
            
            # 2. Check Balance
            cur.execute(f"SELECT chips FROM users WHERE user_id = {ph}", (uid,))
            row = cur.fetchone()
            current_balance = row[0] if row else 0

            if current_balance >= amount:
                # 3. Deduct Money
                cur.execute(f"UPDATE users SET chips = chips - {ph} WHERE user_id = {ph}", (amount, uid))
                conn.commit(); conn.close()
                return True # Transaction Successful
            else:
                conn.close()
                return False # Not enough money
        except Exception as e:
            print(f"[DB Error] Deduct: {e}")
            return False

def add_game_result(user_id, username, game_name, chips_won, points_won, result_type):
    """
    GAME END hone par call karein.
    - chips_won: Kitne chips user ko dene hain (Winnings).
    - points_won: Kitne Points (Score) dene hain.
    - result_type: 'win', 'loss', 'draw', 'refund'
    """
    if not user_id or user_id == "BOT": return

    with db_lock:
        try:
            conn = get_connection(); cur = conn.cursor()
            ph = "%s" if DATABASE_URL.startswith("postgres") else "?"
            uid = str(user_id)

            # Stats Calculation
            win_inc = 1 if result_type == 'win' else 0
            loss_inc = 1 if result_type == 'loss' else 0
            # Game tabhi count hoga jab result win/loss/draw ho (Refund me count nahi hoga)
            game_inc = 1 if result_type in ['win', 'loss', 'draw'] else 0

            # 1. Ensure User Exists (Safety)
            if DATABASE_URL.startswith("postgres"):
                cur.execute(f"INSERT INTO users (user_id, username) VALUES ({ph}, {ph}) ON CONFLICT (user_id) DO NOTHING", (uid, username))
            else:
                cur.execute(f"INSERT OR IGNORE INTO users (user_id, username) VALUES ({ph}, {ph})", (uid, username))

            # 2. Update Wallet & Global Stats
            q1 = f"""
                UPDATE users 
                SET chips = chips + {ph}, 
                    points = points + {ph}, 
                    total_wins = total_wins + {ph}, 
                    total_games = total_games + {ph} 
                WHERE user_id = {ph}
            """
            cur.execute(q1, (chips_won, points_won, win_inc, game_inc, uid))

            # 3. Update Game Specific Stats (Only if not a refund)
            if result_type != 'refund':
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
                # Note: Earnings tracks net chips added here
                cur.execute(q2, (win_inc, loss_inc, chips_won, uid, game_name))

            conn.commit(); conn.close()
            return True
        except Exception as e:
            print(f"[DB Error] Add Result: {e}")
            return False

# ==========================================
# 📊 DATA FETCHING & ADMIN TOOLS
# ==========================================

def get_user_profile(user_id):
    """Returns: {'chips': 1000, 'points': 50, 'wins': 5, 'games': 10}"""
    with db_lock:
        try:
            conn = get_connection(); cur = conn.cursor()
            ph = "%s" if DATABASE_URL.startswith("postgres") else "?"
            cur.execute(f"SELECT chips, points, total_wins, total_games FROM users WHERE user_id = {ph}", (str(user_id),))
            row = cur.fetchone(); conn.close()
            if row:
                return {"chips": row[0], "points": row[1], "wins": row[2], "games": row[3]}
            return {"chips": 1000, "points": 0, "wins": 0, "games": 0} # Default
        except: return None

def admin_update_balance(user_id, username, chips=0, points=0):
    """
    Economy Management ke liye.
    External plugins (Shop/Daily Bonus) isko use karke chips add/remove kar sakte hain.
    chips: Positive to add, Negative to remove.
    points: Positive to add, Negative to remove.
    """
    with db_lock:
        try:
            conn = get_connection(); cur = conn.cursor()
            ph = "%s" if DATABASE_URL.startswith("postgres") else "?"
            uid = str(user_id)
            
            # Create if not exists
            if DATABASE_URL.startswith("postgres"):
                cur.execute(f"INSERT INTO users (user_id, username) VALUES ({ph}, {ph}) ON CONFLICT (user_id) DO NOTHING", (uid, username))
            else:
                cur.execute(f"INSERT OR IGNORE INTO users (user_id, username) VALUES ({ph}, {ph})", (uid, username))
            
            cur.execute(f"UPDATE users SET chips = chips + {ph}, points = points + {ph} WHERE user_id = {ph}", (chips, points, uid))
            conn.commit(); conn.close()
            return True
        except: return False

def get_leaderboard(limit=10):
    """Returns top players by POINTS (Score)"""
    with db_lock:
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute(f"SELECT username, points, chips, total_wins FROM users ORDER BY points DESC LIMIT {limit}")
            rows = cur.fetchall(); conn.close()
            # Returns list of tuples: (name, points, chips, wins)
            return rows
        except: return []

def wipe_everything():
    """⚠️ DANGER: Resets the entire database"""
    with db_lock:
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute("DELETE FROM users")
            cur.execute("DELETE FROM game_stats")
            conn.commit(); conn.close()
            print("[DB] Wipe Complete.")
            return True
        except: return False
