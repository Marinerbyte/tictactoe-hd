import os
import sqlite3
import psycopg2
import threading
from urllib.parse import urlparse  # <--- Wapas daal diya safety ke liye

# Database URL check
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///bot.db")

# GLOBAL LOCK: Multi-threading safety ke liye
db_lock = threading.Lock()

def get_connection():
    if DATABASE_URL.startswith("postgres"):
        try:
            return psycopg2.connect(DATABASE_URL, sslmode='require')
        except:
            # Fallback: Agar direct URL fail ho, to urlparse use karke tod kar connect karein
            # Ye block tab kaam aayega agar future me connection issue aaye
            result = urlparse(DATABASE_URL)
            username = result.username
            password = result.password
            database = result.path[1:]
            hostname = result.hostname
            port = result.port
            return psycopg2.connect(
                database=database,
                user=username,
                password=password,
                host=hostname,
                port=port
            )
    else:
        # SQLite fallback (Local testing)
        return sqlite3.connect("bot.db", check_same_thread=False)

def init_db():
    with db_lock:
        conn = get_connection()
        cur = conn.cursor()
        
        # 1. User Stats (Global Score & Total Wins)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT,
                global_score INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0
            )
        """)
        
        # 2. Game Specific Stats (Har Game ka alag hisaab)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS game_stats (
                user_id TEXT,
                game_name TEXT,
                wins INTEGER DEFAULT 0,
                earnings INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, game_name)
            )
        """)
        
        # 3. Game Logs (Smart compatibility check)
        if DATABASE_URL.startswith("postgres"):
            # Postgres Syntax
            cur.execute("""
                CREATE TABLE IF NOT EXISTS game_logs (
                    id SERIAL PRIMARY KEY,
                    game_type TEXT,
                    room_id TEXT,
                    winner_id TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        else:
            # SQLite Syntax
            cur.execute("""
                CREATE TABLE IF NOT EXISTS game_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_type TEXT,
                    room_id TEXT,
                    winner_id TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        
        # 4. Plugin Settings (Configurations)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS plugin_settings (
                plugin_name TEXT,
                key TEXT,
                value TEXT,
                PRIMARY KEY (plugin_name, key)
            )
        """)
        
        conn.commit()
        conn.close()
        print("[DB] Database initialized successfully.")
