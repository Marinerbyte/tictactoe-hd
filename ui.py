from flask import Blueprint, render_template_string, request, jsonify
import os
import time
import psutil 
import db 

ui_bp = Blueprint('ui', __name__)

# The entire multi-page application is contained within this single HTML string.
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
        html { scroll-behavior: smooth; }
        body { font-family: 'Inter', sans-serif; background: var(--bg-dark); color: var(--text-light); margin: 0; padding: 2rem 2rem 8rem 2rem; }

        /* --- Global Components --- */
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem; border-bottom: 1px solid var(--border); padding-bottom: 1rem; }
        .header-title { display: flex; align-items: center; gap: 1rem; }
        .container { max-width: 1400px; margin: 0 auto; }
        .card {
            background: var(--bg-card); padding: 1.5rem; border-radius: 12px;
            border: 1px solid var(--border); box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            display: flex; flex-direction: column; transition: transform 0.3s, box-shadow 0.3s;
        }
        .card:hover { transform: translateY(-5px); box-shadow: 0 10px 30px rgba(0,0,0,0.4); }
        h2 { margin-top: 0; font-weight: 700; display: flex; align-items: center; gap: 0.75rem; color: var(--text-light); }
        input { padding: 12px; margin: 0; background: var(--bg-input); border: 1px solid var(--border); border-radius: 8px; color: var(--text-light); flex-grow: 1; transition: border-color 0.3s; }
        input:focus { outline: none; border-color: var(--primary); }
        button {
            padding: 12px; border: none; border-radius: 8px; font-weight: 600; cursor: pointer;
            transition: all 0.3s; display: flex; align-items: center; justify-content: center; gap: 0.5rem;
        }
        button:disabled { cursor: not-allowed; opacity: 0.6; }
        .btn-primary { background: var(--primary); color: white; } .btn-primary:hover:not(:disabled) { background: #2563EB; }
        .status-dot { height: 12px; width: 12px; border-radius: 50%; transition: all 0.5s; }
        .status-dot.offline { background-color: var(--red); box-shadow: 0 0 10px var(--red); }
        .status-dot.online { background-color: var(--green); box-shadow: 0 0 10px var(--green); }

        /* --- SPA Page System --- */
        .page { display: none; animation: fadeIn 0.5s; }
        .page.active { display: block; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }

        /* --- Bottom Navigation --- */
        .bottom-nav { position: fixed; bottom: 0; left: 0; right: 0; background: var(--bg-card); border-top: 1px solid var(--border); display: flex; justify-content: space-around; padding: 10px 0; z-index: 1000; }
        .nav-item { display: flex; flex-direction: column; align-items: center; color: var(--text-muted); cursor: pointer; transition: color 0.3s; }
        .nav-item i { font-size: 1.5rem; }
        .nav-item span { font-size: 0.75rem; margin-top: 5px; }
        .nav-item.active, .nav-item:hover { color: var(--primary); }

        /* --- Page Specific Styles --- */
        .grid-container { display: grid; grid-template-columns: repeat(12, 1fr); gap: 1.5rem; }
        .col-span-12 { grid-column: span 12; } .col-span-8 { grid-column: span 8; } .col-span-6 { grid-column: span 6; } .col-span-4 { grid-column: span 4; }
        #log-window { background: #000; height: 200px; overflow-y: scroll; font-family: monospace; padding: 15px; border-radius: 8px; }
        .log-error { color: var(--red); }
        .live-chat-window { height: 400px; background: #111827; border-radius: 8px; padding: 1rem; overflow-y: auto; display: flex; flex-direction: column-reverse; }
        .chat-message { margin-bottom: 1rem; }
        .chat-message.bot .author { color: var(--secondary); font-weight: bold; }
        .chat-message.user .author { color: var(--primary); font-weight: bold; }
        .user-list { list-style: none; padding: 0; height: 400px; overflow-y: auto; }
        .user-list li { padding: 8px; border-bottom: 1px solid var(--border); }
    </style>
</head>
<body>
    
    <div class="header">
        <div class="header-title"> <span id="status" class="status-dot offline"></span> <h1>Mission Control</h1> </div>
        <div id="health-stats" style="display: flex; gap: 2rem;"></div>
    </div>

    <div class="container">
        <!-- PAGE 1: DASHBOARD -->
        <div id="page-dashboard" class="page active">
            <div class="grid-container">
                <div class="card col-span-4">
                    <h2><i class="fas fa-power-off"></i> Bot Control</h2>
                    <input type="text" id="username" placeholder="Bot Username" style="margin-bottom: 10px;">
                    <input type="password" id="password" placeholder="Bot Password" style="margin-bottom: 10px;">
                    <button id="btn-login" class="btn-primary" onclick="loginAndStart()">Connect</button>
                </div>
                <div class="card col-span-8">
                    <h2><i class="fas fa-door-open"></i> Room Management</h2>
                    <div style="display: flex; gap: 10px; margin-bottom: 1rem;">
                        <input type="text" id="roomName" placeholder="Enter Room Name...">
                        <button class="btn-primary" style="width: 150px;" onclick="joinRoom()">Enter</button>
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
                    <h2><i class="fas fa-search"></i> Room Explorer</h2>
                    <input type="text" placeholder="Search for a connected room...">
                </div>
                <div class="card col-span-4">
                    <h2><i class="fas fa-users"></i> Users Online (<span id="mock-user-count">0</span>)</h2>
                    <ul id="mock-user-list" class="user-list"></ul>
                </div>
                <div class="card col-span-8">
                    <h2><i class="fas fa-comments"></i> Live Chat Feed</h2>
                    <div id="mock-chat-window" class="live-chat-window"></div>
                </div>
            </div>
        </div>

        <!-- PAGE 3: STATS & PLUGINS -->
        <div id="page-stats" class="page">
            <div class="grid-container">
                <div class="card col-span-4">
                    <h2><i class="fas fa-puzzle-piece"></i> Plugin Control</h2>
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
        <div class="nav-item active" onclick="showPage('page-dashboard')">
            <i class="fas fa-tachometer-alt"></i><span>Dashboard</span>
        </div>
        <div class="nav-item" onclick="showPage('page-explorer')">
            <i class="fas fa-binoculars"></i><span>Explorer</span>
        </div>
        <div class="nav-item" onclick="showPage('page-stats')">
            <i class="fas fa-chart-bar"></i><span>Stats</span>
        </div>
    </nav>

<script>
    // --- SPA NAVIGATION ---
    function showPage(pageId) {
        document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
        document.getElementById(pageId).classList.add('active');
        document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
        document.querySelector(`.nav-item[onclick="showPage('${pageId}')"]`).classList.add('active');
    }

    // --- MAIN UPDATE LOOP ---
    async function updateDashboardData() {
        try {
            const [status, health, leaderboard] = await Promise.all([
                fetch('/api/status').then(r => r.json()),
                fetch('/api/health').then(r => r.json()),
                fetch('/api/leaderboard').then(r => r.json())
            ]);

            // Top Status Bar
            const statusDot = document.getElementById('status');
            statusDot.className = `status-dot ${status.running ? 'online' : 'offline'}`;
            document.getElementById('health-stats').innerHTML = `
                <span><i class="fas fa-clock"></i> ${health.uptime}</span>
                <span><i class="fas fa-memory"></i> ${health.ram}%</span>
                <span><i class="fas fa-microchip"></i> ${health.cpu}%</span>
            `;

            // Page 1: Dashboard
            document.getElementById('room-count').innerText = status.rooms.length;
            const logWin = document.getElementById('log-window');
            logWin.innerHTML = status.logs.map(log => `<div>${log}</div>`).join('');
            logWin.scrollTop = logWin.scrollHeight;

            // Page 3: Stats & Plugins
            document.getElementById('plugin-list').innerHTML = status.plugins.map(p => `<div><i class="fas fa-check-circle" style="color:var(--green)"></i> ${p}</div>`).join('');
            const lb_body = document.querySelector('#leaderboard-table tbody');
            lb_body.innerHTML = leaderboard.data.map((p, i) => `
                <tr><td>#${i + 1}</td><td>${p.username}</td><td>${p.score}</td><td>${p.wins}</td></tr>
            `).join('');

        } catch (e) { console.error("Update failed", e); }
    }

    // --- MOCK DATA FOR PAGE 2 (ROOM EXPLORER) ---
    function simulateRoomExplorer() {
        const userList = document.getElementById('mock-user-list');
        const chatWindow = document.getElementById('mock-chat-window');
        const users = ['Yasin', 'Bot', 'Laila', 'Kweet', 'Nilu'];
        
        // Add a user
        if (Math.random() > 0.7 && userList.children.length < 10) {
            const user = users[Math.floor(Math.random() * users.length)];
            userList.innerHTML += `<li><i class="fas fa-user"></i> ${user}</li>`;
        }
        // Remove a user
        else if (Math.random() > 0.9 && userList.children.length > 3) {
            userList.children[0].remove();
        }
        document.getElementById('mock-user-count').innerText = userList.children.length;

        // Add a chat message
        const isBot = Math.random() > 0.8;
        const author = isBot ? 'Bot' : users[Math.floor(Math.random() * users.length)];
        const msg = isBot ? '!race' : 'Hello everyone!';
        chatWindow.innerHTML = `<div class="chat-message ${isBot ? 'bot' : 'user'}">
            <span class="author">${author}:</span>
            <div class="content">${msg}</div>
        </div>` + chatWindow.innerHTML;
    }

    // --- API & EVENT HANDLERS ---
    // (Condensed for clarity - assumes full button logic from previous response)
    async function loginAndStart() {
        const btn = document.getElementById('btn-login');
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Connecting';
        btn.disabled = true;
        const res = await fetch('/api/start', { 
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({username: document.getElementById('username').value, password: document.getElementById('password').value})
        }).then(r => r.json());
        btn.innerHTML = 'Connect';
        btn.disabled = false;
        if(res.success) btn.style.background = 'var(--green)';
    }
    
    async function joinRoom() { /* Similar API call logic */ }
    
    // --- INITIALIZE ---
    setInterval(updateDashboardData, 3000);
    setInterval(simulateRoomExplorer, 2000); // Run simulation
    updateDashboardData();
</script>

</body>
</html>
"""

def register_routes(app, bot_instance):
    
    @app.route('/')
    def index():
        return render_template_string(DASHBOARD_HTML)
    
    # --- Backend remains mostly the same, but we need the new endpoints ---

    @app.route('/api/start', methods=['POST'])
    def start_bot():
        data = request.json
        success, msg = bot_instance.login_api(data['username'], data['password'])
        if success:
            bot_instance.connect_ws()
            bot_instance.start_time = time.time() 
            bot_instance.plugins.load_plugins()
        return jsonify({"success": success, "msg": msg})

    @app.route('/api/health')
    def health_check():
        uptime_seconds = time.time() - getattr(bot_instance, 'start_time', time.time())
        uptime_str = time.strftime('%Hh %Mm %Ss', time.gmtime(uptime_seconds))
        return jsonify({
            "uptime": uptime_str,
            "ram": psutil.virtual_memory().percent,
            "cpu": psutil.cpu_percent(interval=None) # Non-blocking
        })

    @app.route('/api/leaderboard')
    def get_leaderboard():
        try:
            conn = db.get_connection()
            cur = conn.cursor()
            cur.execute("SELECT username, global_score, wins FROM users ORDER BY global_score DESC LIMIT 10")
            rows = cur.fetchall()
            conn.close()
            data = [{"username": r[0], "score": r[1], "wins": r[2]} for r in rows]
            return jsonify({"success": True, "data": data})
        except Exception as e:
            return jsonify({"success": False, "msg": str(e), "data": []})
    
    # NOTE: The following are placeholders. To make them real, bot_engine.py would need significant changes
    # to track live chat history and user lists per room.
    @app.route('/api/room/users')
    def get_room_users():
        return jsonify({"success": True, "users": ["Yasin", "Bot", "Laila"]}) # Mock data

    @app.route('/api/room/chat')
    def get_room_chat():
        return jsonify({"success": True, "messages": [{"author": "Bot", "text": "!race"}]}) # Mock data

    # --- Other existing routes ---
    @app.route('/api/stop', methods=['POST'])
    def stop_bot(): bot_instance.disconnect(); return jsonify({"success": True, "msg": "Bot stopping..."})
    @app.route('/api/join', methods=['POST'])
    def join_room():
        data = request.json
        if not bot_instance.running: return jsonify({"success": False, "msg": "Bot not running"})
        bot_instance.join_room(data['room'], data.get('pass', ''))
        return jsonify({"success": True, "msg": "Join command sent!"})
    @app.route('/api/plugins/reload', methods=['POST'])
    def reload_plugins():
        loaded = bot_instance.plugins.load_plugins()
        return jsonify({"success": True, "msg": f"Reloaded: {', '.join(loaded) if loaded else 'None'}"})
    @app.route('/api/status', methods=['GET'])
    def status():
        return jsonify({
            "running": bot_instance.running,
            "logs": bot_instance.logs[-50:], # Limit logs
            "rooms": bot_instance.active_rooms,
            "plugins": list(bot_instance.plugins.plugins.keys())
        })
        
    return ui_bp
