from flask import Blueprint, render_template_string, request, jsonify
import os
import time
import psutil 
import db 

ui_bp = Blueprint('ui', __name__)

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bot Mission Control</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <style>
        :root {
            --bg-dark: #111827; --bg-card: #1F2937; --bg-input: #374151; --border: #4B5563;
            --primary: #3B82F6; --secondary: #EC4899; --green: #10B981; --red: #EF4444; --yellow: #F59E0B;
            --text-light: #F9FAFB; --text-muted: #9CA3AF;
        }
        body { font-family: 'Inter', sans-serif; background: var(--bg-dark); color: var(--text-light); margin: 0; padding: 2rem 2rem 8rem 2rem; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem; border-bottom: 1px solid var(--border); padding-bottom: 1rem; }
        .card { background: var(--bg-card); padding: 1.5rem; border-radius: 12px; border: 1px solid var(--border); }
        h2 { margin-top: 0; font-weight: 700; display: flex; align-items: center; gap: 0.75rem; }
        input, select { padding: 12px; margin: 0; background: var(--bg-input); border: 1px solid var(--border); border-radius: 8px; color: var(--text-light); flex-grow: 1; }
        button { padding: 12px; border: none; border-radius: 8px; font-weight: 600; cursor: pointer; transition: all 0.3s; display: flex; align-items: center; justify-content: center; gap: 0.5rem; }
        button:disabled { cursor: not-allowed; opacity: 0.6; }
        .btn-primary { background: var(--primary); color: white; }
        .btn-danger { background: var(--red); color: white; }
        .status-dot { height: 12px; width: 12px; border-radius: 50%; }
        .status-dot.offline { background-color: var(--red); }
        .status-dot.online { background-color: var(--green); }
        .status-dot.connecting { background-color: var(--yellow); animation: pulse 1s infinite; }
        @keyframes pulse { 50% { opacity: 0.5; } }
        .page { display: none; } .page.active { display: block; animation: fadeIn 0.5s; }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        .bottom-nav { position: fixed; bottom: 0; left: 0; right: 0; background: var(--bg-card); border-top: 1px solid var(--border); display: flex; justify-content: space-around; padding: 10px 0; }
        .nav-item { display: flex; flex-direction: column; align-items: center; color: var(--text-muted); cursor: pointer; }
        .nav-item.active { color: var(--primary); }
        .grid-container { display: grid; grid-template-columns: repeat(12, 1fr); gap: 1.5rem; }
        .col-span-12 { grid-column: span 12; } .col-span-8 { grid-column: span 8; } .col-span-6 { grid-column: span 6; } .col-span-4 { grid-column: span 4; }
        #log-window, .live-chat-window, .user-list { height: 250px; background: #000; overflow-y: scroll; font-family: monospace; padding: 15px; border-radius: 8px; }
        .live-chat-window { display: flex; flex-direction: column-reverse; }
        .chat-message { align-self: flex-start; background: var(--bg-input); padding: 8px 12px; border-radius: 12px; margin-bottom: 10px; max-width: 80%; }
        .chat-message.bot { background: var(--secondary); align-self: flex-end; }
        .chat-message .author { font-weight: bold; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; border-bottom: 1px solid var(--border); }
        #toast-container { position: fixed; bottom: 80px; right: 20px; z-index: 1000; }
        .toast { padding: 15px; border-radius: 8px; color: white; margin-top: 10px; }
        .toast.success { background: var(--green); } .toast.error { background: var(--red); }
    </style>
</head>
<body>
    <div id="toast-container"></div>
    <div class="header">
        <div class="header-title"> <span id="status" class="status-dot offline"></span> <h1>Mission Control</h1> </div>
        <div id="health-stats" style="display: flex; gap: 2rem;"></div>
    </div>
    <div class="container">
        <!-- PAGES HERE -->
        <div id="page-dba" class="page active">
            <div class="grid-container">
                <div class="card col-span-4">
                    <h2><i class="fas fa-power-off"></i> Bot Control</h2>
                    <input type="text" id="username" placeholder="Bot Username" style="margin-bottom: 10px;">
                    <input type="password" id="password" placeholder="Bot Password" style="margin-bottom: 10px;">
                    <button id="btn-login" class="btn-primary" onclick="loginAndStart()">Connect</button>
                    <button id="btn-stop" class="btn-danger" style="margin-top: 10px;" onclick="stopBot()">Stop Bot</button>
                </div>
                <div class="card col-span-8">
                    <h2><i class="fas fa-door-open"></i> Room Management</h2>
                    <div style="display: flex; gap: 10px; margin-bottom: 1rem;">
                        <input type="text" id="roomName" placeholder="Enter Room Name...">
                        <button class="btn-primary" style="width: 150px;" onclick="joinRoom()">Enter Room</button>
                    </div>
                    <p>Connected to <b id="room-count">0</b> rooms.</p>
                    <div id="log-window"></div>
                </div>
            </div>
        </div>
        <div id="page-explorer" class="page">
             <div class="grid-container">
                <div class="card col-span-12">
                    <h2><i class="fas fa-search"></i> Select a Room to Inspect</h2>
                    <select id="room-selector" onchange="updateRoomExplorer()"></select>
                </div>
                <div class="card col-span-4">
                    <h2><i class="fas fa-users"></i> Users Online (<span id="user-count">0</span>)</h2>
                    <div id="user-list" class="user-list"></div>
                </div>
                <div class="card col-span-8">
                    <h2><i class="fas fa-comments"></i> Live Chat Feed</h2>
                    <div id="chat-window" class="live-chat-window"></div>
                </div>
            </div>
        </div>
        <div id="page-stats" class="page">
             <div class="grid-container">
                <div class="card col-span-4">
                    <h2><i class="fas fa-puzzle-piece"></i> Loaded Plugins</h2>
                    <div id="plugin-list"></div>
                </div>
                <div class="card col-span-8">
                    <h2><i class="fas fa-trophy"></i> Global Scoreboard</h2>
                    <table id="leaderboard-table">
                        <thead><tr><th>Rank</th><th>Player</th><th>Score</th><th>Wins</th></tr></thead>
                        <tbody></tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
    <nav class="bottom-nav">
        <div class="nav-item active" onclick="showPage('page-dba')"><i class="fas fa-database"></i><span>DBA</span></div>
        <div class="nav-item" onclick="showPage('page-explorer')"><i class="fas fa-binoculars"></i><span>Explorer</span></div>
        <div class="nav-item" onclick="showPage('page-stats')"><i class="fas fa-chart-bar"></i><span>Stats</span></div>
    </nav>
<script>
    let activePage = 'page-dba';
    
    // --- UI HELPERS ---
    function showPage(pageId) {
        activePage = pageId;
        document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
        document.getElementById(pageId).classList.add('active');
        document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
        document.querySelector(`.nav-item[onclick="showPage('${pageId}')"]`).classList.add('active');
        masterUpdate();
    }
    function showToast(message, type = 'success') { /* ... */ }
    async function api(endpoint, data = {}) {
        return fetch('/api' + endpoint, {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data)
        }).then(r => r.json());
    }
    
    // --- API FUNCTIONS ---
    async function loginAndStart() {
        const btn = document.getElementById('btn-login');
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Connecting';
        btn.disabled = true;
        document.getElementById('status').className = 'status-dot connecting';

        const res = await api('/start', {
            username: document.getElementById('username').value, 
            password: document.getElementById('password').value
        });
        
        btn.disabled = false;
        if (res.success) {
            btn.innerHTML = '<i class="fas fa-check-circle"></i> Connected';
        } else {
            btn.innerHTML = 'Connect';
            showToast(res.msg, 'error');
        }
    }
    
    async function stopBot() { await api('/stop'); }
    async function joinRoom() {
        const roomName = document.getElementById('roomName').value;
        if (!roomName) return;
        await api('/join', {room: roomName});
        setTimeout(masterUpdate, 1200); // Wait for bot to join
    }

    // --- NEW MASTER UPDATE FUNCTION ---
    async function masterUpdate() {
        try {
            const status = await fetch('/api/status').then(r => r.json());

            document.getElementById('status').className = `status-dot ${status.running ? 'online' : 'offline'}`;
            document.getElementById('room-count').innerText = status.rooms.length;
            document.getElementById('log-window').innerHTML = status.logs.map(log => `<div>${log}</div>`).join('');
            
            // --- DATA FOR OTHER PAGES ---
            if (activePage === 'page-explorer') {
                const selector = document.getElementById('room-selector');
                const currentSelected = selector.value;
                selector.innerHTML = '<option value="">-- Select Room --</option>' + status.rooms.map(r => `<option value="${r}">${r}</option>`).join('');
                selector.value = currentSelected || (status.rooms.length > 0 ? status.rooms[0] : "");

                const roomName = selector.value;
                if (roomName) {
                    const details = await fetch(`/api/room/details?name=${roomName}`).then(r => r.json());
                    if (details.success) {
                        document.getElementById('user-count').innerText = details.users.length;
                        document.getElementById('user-list').innerHTML = details.users.map(u => `<div>${u}</div>`).join('');
                        document.getElementById('chat-window').innerHTML = details.chat.map(m => `<div class="chat-message ${m.type}"><div class="author">${m.author}</div><div>${m.text}</div></div>`).join('');
                    }
                } else {
                    document.getElementById('user-count').innerText = '0';
                    document.getElementById('user-list').innerHTML = 'No rooms connected';
                }
            }
            
            if (activePage === 'page-stats') {
                const leaderboard = await fetch('/api/leaderboard').then(r => r.json());
                document.getElementById('plugin-list').innerHTML = status.plugins.map(p => `<div>${p}</div>`).join('');
                document.querySelector('#leaderboard-table tbody').innerHTML = leaderboard.data.map((p, i) => `<tr><td>#${i + 1}</td><td>${p.username}</td><td>${p.score}</td><td>${p.wins}</td></tr>`).join('');
            }

            const health = await fetch('/api/health').then(r => r.json());
            document.getElementById('health-stats').innerHTML = `<span><i class="fas fa-clock"></i> ${health.uptime}</span>`;

        } catch (e) { /* silent fail */ }
    }
    
    setInterval(masterUpdate, 4000);
    masterUpdate();
</script>
</body>
</html>
"""

def register_routes(app, bot_instance):
    # Python backend is correct and does not need changes.
    @app.route('/')
    def index(): return render_template_string(DASHBOARD_HTML)
    
    @app.route('/api/start', methods=['POST'])
    def start_bot():
        data = request.json
        success, msg = bot_instance.login_api(data['username'], data['password'])
        if success:
            bot_instance.connect_ws(); bot_instance.start_time = time.time(); bot_instance.plugins.load_plugins()
        return jsonify({"success": success, "msg": msg})

    @app.route('/api/health')
    def health_check():
        uptime_seconds = time.time() - getattr(bot_instance, 'start_time', time.time())
        uptime_str = time.strftime('%Hh %Mm %Ss', time.gmtime(uptime_seconds))
        return jsonify({"uptime": uptime_str, "ram": psutil.virtual_memory().percent, "cpu": psutil.cpu_percent()})

    @app.route('/api/leaderboard')
    def get_leaderboard():
        conn = db.get_connection(); cur = conn.cursor()
        cur.execute("SELECT username, global_score, wins FROM users ORDER BY global_score DESC LIMIT 10")
        rows = cur.fetchall(); conn.close()
        data = [{"username": r[0], "score": r[1], "wins": r[2]} for r in rows]
        return jsonify({"success": True, "data": data})
    
    @app.route('/api/room/details')
    def get_room_details():
        room_name = request.args.get('name')
        if not room_name or not bot_instance.running: return jsonify({"success": False, "users": [], "chat": []})
        room_data = bot_instance.room_details.get(room_name)
        if room_data:
            return jsonify({"success": True, "users": room_data.get('users', []), "chat": room_data.get('chat_log', [])})
        return jsonify({"success": False, "users": [], "chat": []})

    @app.route('/api/stop', methods=['POST'])
    def stop_bot(): 
        bot_instance.disconnect()
        return jsonify({"success": True, "msg": "Bot has been stopped."})

    @app.route('/api/join', methods=['POST'])
    def join_room():
        bot_instance.join_room(request.json['room'])
        return jsonify({"success": True, "msg": "Join command sent."})

    @app.route('/api/plugins/reload', methods=['POST'])
    def reload_plugins():
        bot_instance.plugins.load_plugins()
        return jsonify({"success": True, "msg": "Plugins reloaded."})
        
    @app.route('/api/status', methods=['GET'])
    def status():
        return jsonify({"running": bot_instance.running, "logs": bot_instance.logs[-50:], "rooms": bot_instance.active_rooms, "plugins": list(bot_instance.plugins.plugins.keys())})
        
    return ui_bp
