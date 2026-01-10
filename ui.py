import streamlit as st
import requests
import time
import pandas as pd
from datetime import datetime

# =========================================================
# 1. PAGE SETUP & "MAST" STYLING
# =========================================================
st.set_page_config(
    page_title="Howdies Bot Commander",
    page_icon="🕹️",
    layout="wide",
    initial_sidebar_state="collapsed"  # Mobile ke liye best
)

# Render URL (Yahan apna URL dalein)
DEFAULT_URL = "https://tictactoe-hd.onrender.com" 

# --- Custom CSS for Cyberpunk Look ---
st.markdown("""
<style>
    /* Global Dark Theme */
    .stApp { background-color: #050505; color: #e0e0e0; }
    
    /* Input Fields */
    div[data-baseweb="input"] {
        background-color: #111; 
        border: 1px solid #333; 
        color: #00ffcc; 
        border-radius: 8px;
    }
    
    /* Login Box Container */
    .login-container {
        background: rgba(20, 20, 20, 0.8);
        padding: 25px;
        border-radius: 12px;
        border: 1px solid #333;
        box-shadow: 0 0 20px rgba(0, 255, 204, 0.1);
        margin-bottom: 20px;
    }
    
    /* Dashboard Cards */
    .metric-card {
        background: linear-gradient(145deg, #0f0f0f, #161616);
        padding: 15px;
        border-radius: 10px;
        border-left: 4px solid #333;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.5);
        margin-bottom: 10px;
        transition: transform 0.2s;
    }
    .metric-card:hover { transform: translateY(-2px); border-left-color: #00ffcc; }
    .val { font-size: 1.8rem; font-weight: 700; color: #fff; }
    .lbl { font-size: 0.8rem; color: #888; text-transform: uppercase; letter-spacing: 1px; }
    
    /* Terminal Window */
    .terminal-box {
        background-color: #0a0a0a;
        border: 1px solid #333;
        border-radius: 8px;
        padding: 15px;
        height: 400px;
        overflow-y: auto;
        font-family: 'Courier New', monospace;
        font-size: 0.85rem;
        box-shadow: inset 0 0 10px rgba(0,0,0,0.8);
    }
    .log-row { display: flex; border-bottom: 1px solid #1a1a1a; padding: 4px 0; }
    .log-ts { color: #555; min-width: 80px; font-size: 0.75rem; }
    .log-txt { color: #00ffcc; word-break: break-all; }
    .log-err { color: #ff3333; }
    
    /* Custom Buttons */
    div.stButton > button {
        background-color: #222; 
        color: white; 
        border: 1px solid #444; 
        width: 100%; 
        border-radius: 8px;
        padding: 10px;
        font-weight: bold;
        transition: all 0.3s;
    }
    div.stButton > button:hover {
        background-color: #00ffcc;
        color: black;
        border-color: #00ffcc;
        box-shadow: 0 0 15px #00ffcc;
    }
    div.stButton > button:active { transform: scale(0.98); }
</style>
""", unsafe_allow_html=True)

# =========================================================
# 2. API HELPERS
# =========================================================
if "api_url" not in st.session_state:
    st.session_state.api_url = DEFAULT_URL

def get_base_url():
    return st.session_state.api_url.rstrip("/")

def api_post(endpoint, payload):
    try:
        r = requests.post(f"{get_base_url()}/{endpoint}", json=payload, timeout=10)
        return r.json(), r.status_code
    except Exception as e:
        return {"error": str(e)}, 500

def api_get(endpoint):
    try:
        r = requests.get(f"{get_base_url()}/{endpoint}", timeout=5)
        return r.json() if r.status_code == 200 else None
    except:
        return None

# =========================================================
# 3. SIDEBAR (CONFIG)
# =========================================================
with st.sidebar:
    st.title("⚙️ SETTINGS")
    st.caption("Engine Connection")
    st.session_state.api_url = st.text_input("Server Link", value=DEFAULT_URL, placeholder="https://app-name.onrender.com")
    
    if st.button("🔄 Refresh Status"):
        st.rerun()
    
    st.divider()
    st.info("Render par 'app.py' chalna zaroori hai.")

# =========================================================
# 4. MAIN LOGIC
# =========================================================

# Title
st.markdown("""
<div style="text-align: center; margin-bottom: 20px;">
    <h1 style="margin:0; text-shadow: 0 0 20px rgba(0,255,204,0.5);">🤖 HOWDIES <span style="color:#00ffcc;">COMMANDER</span></h1>
</div>
""", unsafe_allow_html=True)

# Check Server
status = api_get("status")
server_online = status is not None
is_connected = status.get("connected", False) if server_online else False

# --- SCENARIO 1: LOGIN SCREEN ---
if not is_connected:
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    
    if not server_online:
        st.error("⚠️ Cannot Connect to Engine URL. Please check Sidebar settings.")
    else:
        st.subheader("🔐 Authenticate Bot")
        
        with st.form("login_form"):
            # The 3 Fields you asked for
            c1, c2 = st.columns(2)
            with c1:
                bot_id = st.text_input("Bot ID", placeholder="Ex: 123456")
            with c2:
                # Room name input (Logic: For now UI only, backend auth doesn't require it but user asked)
                room_name = st.text_input("Target Room Name", placeholder="Ex: public")
            
            password = st.text_input("Bot Password", type="password")

            if st.form_submit_button("🚀 LAUNCH ENGINE"):
                if bot_id and password:
                    with st.spinner("Initiating Uplink..."):
                        # Logic: Username = Bot ID
                        payload = {
                            "botId": bot_id,
                            "username": bot_id, 
                            "password": password
                        }
                        resp, code = api_post("login", payload)
                        
                        if code == 200 and resp.get("ok"):
                            st.success(f"Login Verified! Target: {room_name if room_name else 'Default'}")
                            time.sleep(1.5)
                            st.rerun()
                        else:
                            st.error(f"Access Denied: {resp.get('error', 'Unknown Error')}")
                else:
                    st.warning("Bot ID & Password Required!")
    
    st.markdown('</div>', unsafe_allow_html=True)

# --- SCENARIO 2: DASHBOARD (Logged In) ---
else:
    # 1. Top Stats Cards
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"""
        <div class="metric-card" style="border-left-color: #00ff41;">
            <div class="val" style="color:#00ff41;">ONLINE</div>
            <div class="lbl">SYSTEM STATUS</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        room_count = len(status.get("rooms", []))
        st.markdown(f"""
        <div class="metric-card">
            <div class="val">{room_count}</div>
            <div class="lbl">ACTIVE ROOMS</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        # Logout Button Logic
        if st.button("🛑 SHUTDOWN (LOGOUT)"):
            api_post("logout", {})
            time.sleep(0.5)
            st.rerun()

    # 2. Main Tabs
    tab_logs, tab_rooms, tab_game = st.tabs(["📜 TERMINAL LOGS", "🌐 NETWORK", "🎮 GAME PREVIEW"])

    with tab_logs:
        col_ref, col_emp = st.columns([1, 4])
        if col_ref.button("⚡ Refresh Logs"):
            st.rerun()

        # Fetch Logs
        logs_data = api_get("get_logs")
        log_html = ""
        
        if logs_data and "logs" in logs_data:
            for l in reversed(logs_data["logs"]): # Newest on top
                ts = datetime.now().strftime("%H:%M:%S")
                # Error highlighting
                css = "log-err" if "Error" in l or "fail" in l.lower() else "log-txt"
                log_html += f"""
                <div class="log-row">
                    <span class="log-ts">[{ts}]</span>
                    <span class="{css}">{l}</span>
                </div>
                """
        else:
            log_html = "<div style='color:#555; text-align:center; padding:20px;'>No signal...</div>"

        st.markdown(f'<div class="terminal-box">{log_html}</div>', unsafe_allow_html=True)

    with tab_rooms:
        st.markdown("### 📡 Active Connections")
        if status.get("rooms"):
            # Table View
            room_df = pd.DataFrame(status["rooms"], columns=["Room ID"])
            st.dataframe(room_df, use_container_width=True, hide_index=True)
        else:
            st.info("Bot is idle. Not joined in any rooms.")
            
        st.markdown("### 🧩 Loaded Modules")
        plugins = status.get("plugins", [])
        if plugins:
            st.code(plugins)
        else:
            st.warning("No plugins loaded.")

    with tab_game:
        st.markdown("### 🎲 Visual Output")
        st.info("Latest Tic-Tac-Toe or Game Images will appear here in future updates.")
        # Placeholder
        st.markdown("""
        <div style="width:100%; height:150px; border:2px dashed #333; display:flex; align-items:center; justify-content:center; border-radius:10px; color:#555;">
            WAITING FOR IMAGE DATA...
        </div>
        """, unsafe_allow_html=True)
