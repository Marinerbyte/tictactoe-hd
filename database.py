# --- SAVE AS database.py ---
import sqlite3
import json
import time
import os
import threading

DB_FILE = "titan_core.db"
DB_LOCK = threading.Lock()

def get_conn():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def init_db():
    with DB_LOCK:
        conn = get_conn()
        c = conn.cursor()
        
        # 1. COMMAND QUEUE (UI -> Bot communication)
        c.execute('''CREATE TABLE IF NOT EXISTS command_queue 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, cmd TEXT, payload TEXT, status TEXT DEFAULT 'PENDING')''')
        
        # 2. LOGS (Bot -> UI communication)
        c.execute('''CREATE TABLE IF NOT EXISTS system_logs 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, level TEXT, msg TEXT, timestamp REAL)''')
        
        # 3. USERS & SCORES
        c.execute('''CREATE TABLE IF NOT EXISTS users 
                     (username TEXT PRIMARY KEY, score INTEGER DEFAULT 1000, wins INTEGER DEFAULT 0, avatar TEXT)''')
                     
        # 4. BOT STATUS (Heartbeat)
        c.execute('''CREATE TABLE IF NOT EXISTS bot_state 
                     (key TEXT PRIMARY KEY, value TEXT)''')
        
        conn.commit()
        conn.close()

def log(level, msg):
    """Log likhne ke liye wrapper"""
    print(f"[{level}] {msg}")
    try:
        with DB_LOCK:
            conn = get_conn()
            conn.execute("INSERT INTO system_logs (level, msg, timestamp) VALUES (?, ?, ?)", 
                         (level, str(msg), time.time()))
            conn.commit()
            conn.close()
    except: pass

def push_command(cmd, payload_dict):
    """UI se Bot ko order dene ke liye"""
    with DB_LOCK:
        conn = get_conn()
        conn.execute("INSERT INTO command_queue (cmd, payload) VALUES (?, ?)", 
                     (cmd, json.dumps(payload_dict)))
        conn.commit()
        conn.close()

def get_pending_commands():
    """Bot ke liye: Pending orders uthana"""
    cmds = []
    with DB_LOCK:
        conn = get_conn()
        cur = conn.execute("SELECT id, cmd, payload FROM command_queue WHERE status='PENDING'")
        rows = cur.fetchall()
        for r in rows:
            cmds.append(r)
            conn.execute("UPDATE command_queue SET status='PROCESSED' WHERE id=?", (r[0],))
        conn.commit()
        conn.close()
    return cmds

# Run Init
init_db()
