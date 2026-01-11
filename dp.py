import os
import sqlite3
import psycopg2
import threading
from urllib.parse import urlparse

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///bot.db")
db_lock = threading.Lock()

def get_connection():
    if DATABASE_URL.startswith("postgres"):
        return psycopg2.connect(DATABASE_URL, sslmode='require')
    else:
        # SQLite fallback
        return sqlite3.connect("bot.db", check_same_thread=False)

def init_db():
    with db_lock:
        conn = get_connection()
        cur = conn.cursor()
        
        # User Stats
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT,
                global_score INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0
            )
        """)
        
        # Game Logs
        cur.execute("""
            CREATE TABLE IF NOT EXISTS game_logs (
                id SERIAL PRIMARY KEY,
                game_type TEXT,
                room_id TEXT,
                winner_id TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Plugin Settings
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
        print("[DB] Database initialized.")
