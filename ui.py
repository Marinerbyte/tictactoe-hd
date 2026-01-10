import streamlit as st
import requests
import pandas as pd
import time
from datetime import datetime

# =========================================================
# 1. PAGE CONFIG & CSS (THE VISUAL MAGIC)
# =========================================================
st.set_page_config(
    page_title="Howdies Command Center",
    page_icon="🕹️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom HTML/CSS Styles ---
st.markdown("""
<style>
    /* GLOBAL THEME */
    .stApp {
        background-color: #0e1117;
    }
    
    /* DASHBOARD CARDS */
    .dashboard-card {
        background: rgba(38, 39, 48, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        backdrop-filter: blur(10px);
        transition: transform 0.2s;
    }
    .dashboard-card:hover {
        transform: translateY(-2px);
        border-color: #ff4b4b;
    }
    .metric-label {
        font-size: 0.9rem;
        color: #a0a0a0;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 5px;
    }
    .metric-value {
        font-size: 2.2rem;
        font-weight: 700;
        color: #ffffff;
    }
    
    /* STATUS DOTS */
    .status-dot {
        height: 12px;
        width: 12px;
        border-radius: 50%;
        display: inline-block;
        margin-right: 8px;
    }
    .online { background-color: #00ff41; box-shadow: 0 0 10px #00ff41; }
    .offline { background-color: #ff2b2b; box-shadow: 0 0 10px #ff2b2b; }

    /* LOGS TERMINAL */
    .terminal-window {
        background-color: #0d1117;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 15px;
        font-family: 'Courier New', monospace;
        height: 400px;
        overflow-y: auto;
        color: #c9d1d9;
        font-size: 0.85rem;
    }
    .log-line {
        border-bottom: 1px solid #21262d;
        padding: 4px 0;
        display: flex;
    }
    .log-time { color: #8b949e; margin-right: 10px; min-width: 80px; }
    .log-msg { color: #58a6ff; }
    .log-err { color: #ff7b72; }

    /* BADGES */
    .plugin-badge {
        background-color: #238636;
        color: white;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.8rem;
        margin: 2px;
        display: inline-block;
    }
</style>
""", unsafe_allow_html=True)

# API Configuration
API_URL = "https://tictactoe-hd.onrender.com"

# =========================================================
# 2. STATE & API HELPERS
# =========================================================
if "token" not in st.session_state:
    st.session_state.token = None
if "log_history" not in st.session_state:
    st.session_state.log_history = []

def api_post(endpoint, data):
    try:
        r = requests.post(f"{API_URL}/{endpoint}", json=data, timeout=3)
        return r.json()
    except:
        return {"ok": False, "error": "Connection Failed"}

def api_get(endpoint):
    try:
        r = requests.get(f"{API_URL}/{endpoint}", timeout=2)
        return r.json() if r.status_code == 200 else None
    except:
        return None

# =========================================================
# 3. SIDEBAR (CONTROLS)
# =========================================================
with st.sidebar:
    st.markdown("## 🤖 **CONTROL PANEL**")
    
    if not st.session_state.token:
        st.info("🔒 Authentication Required")
        with st.form("login"):
            bot_id = st.text_input("Bot ID")
            user = st.text_input("Username")
            pwd = st.text_input("Password", type="password")
            if st.form_submit_button("🚀 Launch Engine"):
                resp = api_post("login", {"botId": bot_id, "username": user, "password": pwd})
                if resp.get("ok"):
                    st.session_state.token = "active"
                    st.toast("Access Granted!", icon="✅")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error(f"Access Denied: {resp.get('error')}")
    else:
        st.success("🟢 System Online")
        if st.button("🔌 Emergency Shutdown (Logout)"):
            api_post("logout", {})
            st.session_state.token = None
            st.rerun()

    st.markdown("---")
    st.markdown("**⚙️ Settings**")
    refresh_rate = st.slider("Poll Rate", 1, 5, 2)
    auto_ref = st.checkbox("Live Update", value=True)
    
    if st.button("🔄 Force Reconnect WS"):
        api_post("logout", {})
        st.warning("Signal Sent. Please Relogin.")
        st.session_state.token = None
        st.rerun()

# =========================================================
# 4. MAIN DASHBOARD UI
# =========================================================

if st.session_state.token:
    # --- FETCH DATA ---
    status = api_get("status")
    logs = api_get("get_logs")
    
    # Defaults
    conn_status = False
    rooms_count = 0
    plugins = []
    
    if status:
        conn_status = status.get("connected", False)
        rooms_count = len(status.get("rooms", []))
        plugins = status.get("plugins", [])

    # --- HTML HEADER ---
    st.markdown(f"""
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
        <h1 style="margin:0; text-shadow: 0 0 10px rgba(255,255,255,0.3);">🚀 ENGINE <span style="color:#ff4b4b">V1</span></h1>
        <div style="text-align:right;">
            <div class="status-dot {'online' if conn_status else 'offline'}"></div>
            <span style="font-weight:bold; color: {'#00ff41' if conn_status else '#ff2b2b'}">
                {'ONLINE' if conn_status else 'OFFLINE'}
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # --- METRIC CARDS (HTML GRID) ---
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="dashboard-card">
            <div class="metric-label">WebSocket</div>
            <div class="metric-value" style="color: {'#4caf50' if conn_status else '#f44336'}">
                {'CNCTD' if conn_status else 'DISC'}
            </div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="dashboard-card">
            <div class="metric-label">Active Rooms</div>
            <div class="metric-value">{rooms_count}</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="dashboard-card">
            <div class="metric-label">Plugins</div>
            <div class="metric-value">{len(plugins)}</div>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class="dashboard-card">
            <div class="metric-label">Uptime</div>
            <div class="metric-value" style="font-size:1.5rem">Running</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # --- TABS SECTION ---
    tab_logs, tab_rooms, tab_game = st.tabs(["📜 TERMINAL LOGS", "🌐 NETWORK MAP", "🎮 GAME VISUALS"])

    with tab_logs:
        # Update Logs History
        if logs and "logs" in logs:
            for l in logs["logs"]:
                ts = datetime.now().strftime("%H:%M:%S")
                # Add CSS class based on content
                css_class = "log-err" if "Error" in l else "log-msg"
                html_line = f"""
                <div class="log-line">
                    <span class="log-time">[{ts}]</span>
                    <span class="{css_class}">{l}</span>
                </div>
                """
                st.session_state.log_history.insert(0, html_line)
        
        # Limit history
        st.session_state.log_history = st.session_state.log_history[:200]
        
        # Render HTML Terminal
        full_html = "".join(st.session_state.log_history)
        st.markdown(f'<div class="terminal-window">{full_html}</div>', unsafe_allow_html=True)
        
        if st.button("Clear Terminal"):
            st.session_state.log_history = []
            st.rerun()

    with tab_rooms:
        col_r1, col_r2 = st.columns([1, 1])
        with col_r1:
            st.markdown("### 📡 Active Channels")
            if status and status.get("rooms"):
                # Stylish Table
                rows = "".join([f"<tr><td style='padding:10px; border-bottom:1px solid #333;'>#{r}</td><td style='color:#00ff41;'>Active</td></tr>" for r in status['rooms']])
                st.markdown(f"""
                <table style="width:100%; border-collapse: collapse; background:#161b22; border-radius:8px;">
                    {rows}
                </table>
                """, unsafe_allow_html=True)
            else:
                st.info("No rooms joined yet. Send a message to the bot.")

        with col_r2:
            st.markdown("### 🔌 Loaded Modules")
            if plugins:
                badges = "".join([f'<span class="plugin-badge">{p}</span>' for p in plugins])
                st.markdown(f"<div>{badges}</div>", unsafe_allow_html=True)
            else:
                st.warning("No plugins loaded.")

    with tab_game:
        st.markdown("### 🎲 Live Game Board (TicTacToe)")
        # Placeholder for image rendering
        st.markdown("""
        <div style="border: 2px dashed #444; padding: 40px; text-align: center; border-radius: 10px;">
            <p style="color: #666;">Waiting for game data...</p>
            <p style="font-size: 0.8rem; color: #444;">Images sent by plugins via Media_API will appear here in future updates.</p>
        </div>
        """, unsafe_allow_html=True)

    # Auto Refresh Logic
    if auto_ref:
        time.sleep(refresh_rate)
        st.rerun()

else:
    # LANDING PAGE
    st.markdown("""
    <div style="text-align:center; padding-top:50px;">
        <h1>🛡️ HOWDIES ENGINE</h1>
        <p style="color:#888;">Secure Connection Required</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Check Server Status
    try:
        r = requests.get(API_URL)
        if r.status_code == 200:
            st.success("✅ Core Engine Detected at Port 5000")
        else:
            st.warning("⚠️ Core Engine Unresponsive")
    except:
        st.error("❌ Core Engine Offline. Run 'python app.py' first.")
