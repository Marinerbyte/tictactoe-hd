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
            --bg-dark: #111827; --bg-card: #1F2937; --bg-input: #374151;
            --border: #4B5563; --primary: #3B82F6; --secondary: #EC4899; --accent: #8B5CF6;
            --text-light: #F9FAFB; --text-muted: #9CA3AF;
            --green: #10B981; --red: #EF4444; --yellow: #F59E0B;
        }
        * { box-sizing: border-box; }
        body { font-family: 'Inter', sans-serif; background: var(--bg-dark); color: var(--text-light); margin: 0; padding: 2rem 2rem 8rem 2rem; }

        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem; border-bottom: 1px solid var(--border); padding-bottom: 1rem; }
        .container { max-width: 1400px; margin: 0 auto; }
        .card { background: var(--bg-card); padding: 1.5rem; border-radius: 12px; border: 1px solid var(--border); box-shadow: 0 4px 20px rgba(0,0,0,0.3); transition: transform 0.3s; }
        .card:hover { transform: translateY(-5px); }
        h2 { margin-top: 0; font-weight: 700; display: flex; align-items: center; gap: 0.75rem; }
        input, select { padding: 12px; margin: 0; background: var(--bg-input); border: 1px solid var(--border); border-radius: 8px; color: var(--text-light); flex-grow: 1; }
        input:focus, select:focus { outline: none; border-color: var(--primary); }
        button { padding: 12px; border: none; border-radius: 8px; font-weight: 600; cursor: pointer; transition: all 0.3s; display: flex; align-items: center; justify-content: center; gap: 0.5rem; }
        button:disabled { cursor: not-allowed; opacity: 0.6; }
        .btn-primary { background: var(--primary); color: white; } .btn-primary:hover:not(:disabled) { background: #2563EB; }
        .btn-danger { background: var(--red); color: white; }
        .status-dot { height: 12px; width: 12px; border-radius: 50%; transition: all 0.5s; }
        .status-dot.offline { background-color: var(--red); box-shadow: 0 0 10px var(--red); }
        .status-dot.online { background-color: var(--green); box-shadow: 0 0 10px var(--green); }
        .status-dot.connecting { background-color: var(--yellow); box-shadow: 0 0 10px var(--yellow); animation: pulse 1s infinite; }
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }

        .page { display: none; animation: fadeIn 0.5s; }
        .page.active { display: block; }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }

        .bottom-nav { position: fixed; bottom: 0; left: 0; right: 0; background: var(--bg-card); border-top: 1px solid var(--border); display: flex; justify-content: space-around; padding: 10px 0; }
        .nav-item { display: flex; flex-direction: column; align-items: center; color: var(--text-muted); cursor: pointer; transition: color 0.3s; }
        .nav-item i { font-size: 1.5rem; }
        .nav-item span { font-size: 0.75rem; }
        .nav-item.active, .nav-item:hover { color: var(--primary); }

        .grid-container { display: grid; grid-template-columns: repeat(12, 1fr); gap: 1.5rem; }
        .col-span-12 { grid-column: span 12; } .col-span-8 { grid-column: span 8; } .col-span-6 { grid-column: span 6; } .col-span-4 { grid-column: span 4; }
        
        #log-window { background: #000; height: 200px; overflow-y: scroll; font-family: monospace; padding: 15px; border-radius: 8px; }
        .live-chat-window { height: 400px; background: #111827; border-radius: 8px; padding: 1rem; overflow-y: auto; display: flex; flex-direction: column-reverse; }
        .chat-message { align-self: flex-start; background: var(--bg-input); padding: 8px 12px; border-radius: 12px; margin-bottom: 10px; max-width: 80%; }
        .chat-message.bot { background: var(--secondary); align-self: flex-end; }
        .chat-message .author { font-weight: bold; font-size: 0.9rem; color: var(--primary); }
        .chat-message.bot .author { color: white; }
        
        .user-list { list-style: none; padding: 0; height: 400px; overflow-y: auto; }
        .user-list li { padding: 8px; border-bottom: 1px solid var(--border); display: flex; align-items: center; gap: 10px; }
        
        table { width: 100%; border-collapse: collapse; }
        th, td { text-align: left; padding: 12px; border-bottom: 1px solid var(--border); }
        
        #toast-container { position: fixed; bottom: 20px; right: 20px; z-index: 1000; }
        .toast { padding: 15px; border-radius: 8px; color: white; box-shadow: 0 3px 10px rgba(0,0,0,0.3); opacity: 0; animation: fadeIn 0.5s forwards; margin-top: 10px; }
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
        <!-- PAGE 1: DBA -->
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

        <!-- PAGE 2: ROOM EXPLORER -->
        <div id="page-explorer" class="page">
            <div class="grid-container">
                <div class="card col-span-12">
                    <h2><i class="fas fa-search"></i> Select a Room to Inspect</h2>
                    <select id="room-selector" onchange="updateRoomExplorer()"></select>
                </div>
                <div class="card col-span-4">
                    <h2><i class="fas fa-users"></i> Users Online (<span id="user-count">0</span>)</h2>
                    <ul id="user-list" class="user-list"></ul>
                </div>
                <div class="card col-span-8">
                    <h2><i class="fas fa-comments"></i> Live Chat Feed</h2>
                    <div id="chat-window" class="live-chat-window"></div>
                </div>
            </div>
        </div>

        <!-- PAGE 3: STATS & PLUGINS -->
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
    let currentRooms = [];
    
    // --- UI HELPERS ---
    function showPage(pageId) {
        activePage = pageId;
        document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
        document.getElementById(pageId).classList.add('active');
        document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
        document.querySelector(`.nav-item[onclick="showPage('${pageId}')"]`).classList.add('active');
        if (pageId === 'page-explorer') updateRoomExplorer();
    }

    function showToast(message, type = 'success') {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        container.appendChild(toast);
        setTimeout(() => toast.remove(), 4000);
    }

    async function api(endpoint, data = {}) {
        const response = await fetch('/api' + endpoint, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data)
        });
        return await response.json();
    }
    
    // --- API FUNCTIONS ---
    async function loginAndStart() {
        const u = document.getElementById('username').value;
        const p = document.getElementById('password').value;
        if (!u || !p) return showToast('Username and Password required', 'error');
        
        const btn = document.getElementById('btn-login');
        const statusDot = document.getElementById('status');
        
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Connecting';
        btn.disabled = true;
        statusDot.className = 'status-dot connecting';

        const res = await api('/start', {username: u, password: p});
        showToast(res.msg, res.success ? 'success' : 'error');
        
        btn.disabled = false;
        if(res.success) {
            btn.style.background = 'var(--green)';
            btn.innerHTML = '<i class="fas fa-check-circle"></i> Connected';
        } else {
            statusDot.className = 'status-dot offline';
            btn.innerHTML = 'Connect';
        }
    }
    
    async function stopBot() {
        const res = await api('/stop');
        showToast(res.msg, 'error');
        const loginBtn = document.getElementById('btn-login');
        loginBtn.style.background = 'var(--primary)';
        loginBtn.innerHTML = 'Connect';
    }

    async function joinRoom() {
        const roomName = document.getElementById('roomName').value;
        if (!roomName) return showToast('Room Name required', 'error');
        
        await api('/join', {room: roomName});
        showToast(`Join command sent to '${roomName}'`, 'success');
        setTimeout(updateDashboardData, 1000);
    }

    async function updateRoomExplorer() {
        const roomName = document.getElementById('room-selector').value;
        if (!roomName) {
            document.getElementById('user-count').innerText = '0';
            document.getElementById('user-list').innerHTML = '<li>Select a room</li>';
            document.getElementById('chat-window').innerHTML = '';
            return;
        }

        const res = await fetch(`/api/room/details?name=${roomName}`).then(r => r.json());
        
        if (res.success) {
            document.getElementById('user-count').innerText = res.users.length;
            document.getElementById('user-list').innerHTML = res.users.map(u => `<li><i class="fas fa-user"></i> ${u}</li>`).join('');
            
            document.getElementById('chat-window').innerHTML = res.chat.map(m => {
                const authorClass = m.type;
                return `<div class="chat-message ${authorClass}"><div class="author">${m.author}</div><div>${m.text}</div></div>`;
            }).join('');
        }
    }

    async function updateDashboardData() {
        try {
            const [status, health, leaderboard] = await Promise.all([
                fetch('/api/status').then(r => r.json()),
                fetch('/api/health').then(r => r.json()),
                fetch('/api/leaderboard').then(r => r.json())
            ]);

            // Header
            const statusDot = document.getElementById('status');
            if (!statusDot.classList.contains('connecting')) { // Don't override connecting state
                statusDot.className = `status-dot ${status.running ? 'online' : 'offline'}`;
            }
            document.getElementById('health-stats').innerHTML = `<span><i class="fas fa-clock"></i> ${health.uptime}</span> | <span><i class="fas fa-memory"></i> ${health.ram}%</span> | <span><i class="fas fa-microchip"></i> ${health.cpu}%</span>`;

            // Page 1
            document.getElementById('room-count').innerText = status.rooms.length;
            document.getElementById('log-window').innerHTML = status.logs.map(log => `<div>${log}</div>`).join('');

            // Page 2
            const selector = document.getElementById('room-selector');
            if (JSON.stringify(currentRooms) !== JSON.stringify(status.rooms)) {
                currentRooms = status.rooms;
                const currentSelected = selector.value;
                selector.innerHTML = '<option value="">-- Select a Room --</option>' + currentRooms.map(r => `<option value="${r}">${r}</option>`).join('');
                if (currentRooms.includes(currentSelected)) {
                    selector.value = currentSelected;
                } else if (currentRooms.length > 0) {
                    selector.value = currentRooms[0];
                }
            }
            
            // Page 3
            document.getElementById('plugin-list').innerHTML = status.plugins.map(p => `<div><i class="fas fa-check-circle" style="color:var(--green)"></i> ${p}</div>`).join('');
            document.querySelector('#leaderboard-table tbody').innerHTML = leaderboard.data.map((p, i) => `<tr><td>#${i + 1}</td><td>${p.username}</td><td>${p.score}</td><td>${p.wins}</td></tr>`).join('');

            if (activePage === 'page-explorer') {
                updateRoomExplorer();
            }

        } catch (e) { /* silent fail */ }
    }
    
    setInterval(updateDashboardData, 3000);
</script>

</body>
</html>
"""

def register_routes(app, bot_instance):
    # Python code is correct, no changes needed here.
    # The previous backend code is fine.
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
