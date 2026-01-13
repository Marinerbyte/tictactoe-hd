from flask import Blueprint, render_template_string, request, jsonify
import os
import time
import psutil # For RAM/CPU stats. Add 'psutil' to your requirements.txt
import db # Import db to directly query for leaderboard/stats

ui_bp = Blueprint('ui', __name__)

# Single HTML Template (Fully Overhauled)
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bot Mission Control</title>
    
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">

    <style>
        :root {
            --bg-dark: #111827; --bg-card: #1F2937; --bg-input: #374151;
            --border: #4B5563; --primary: #3B82F6; --secondary: #EC4899;
            --text-light: #F9FAFB; --text-muted: #9CA3AF;
            --green: #10B981; --red: #EF4444; --yellow: #F59E0B;
        }
        * { box-sizing: border-box; }
        body {
            font-family: 'Inter', sans-serif; background: var(--bg-dark);
            color: var(--text-light); margin: 0; padding: 2rem;
        }
        .header {
            display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 2rem; border-bottom: 1px solid var(--border); padding-bottom: 1rem;
        }
        .header-title { display: flex; align-items: center; gap: 1rem; }
        .container {
            max-width: 1400px; margin: 0 auto; display: grid;
            grid-template-columns: repeat(12, 1fr); gap: 1.5rem;
        }
        .card {
            background: var(--bg-card); padding: 1.5rem; border-radius: 12px;
            border: 1px solid var(--border); box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            display: flex; flex-direction: column;
        }
        /* Grid Layout Spanning */
        .col-span-12 { grid-column: span 12; } .col-span-8 { grid-column: span 8; }
        .col-span-6 { grid-column: span 6; } .col-span-4 { grid-column: span 4; }
        
        h2 { margin-top: 0; font-weight: 700; display: flex; align-items: center; gap: 0.75rem; color: var(--text-light); }
        .input-group { position: relative; display: flex; gap: 10px; }
        .input-group i { position: absolute; left: 15px; top: 50%; transform: translateY(-50%); color: var(--text-muted); }
        input {
            padding: 12px 12px 12px 40px; margin: 0; background: var(--bg-input);
            border: 1px solid var(--border); border-radius: 8px; color: var(--text-light);
            flex-grow: 1; transition: border-color 0.3s;
        }
        input:focus { outline: none; border-color: var(--primary); }
        button {
            padding: 12px; border: none; border-radius: 8px; font-weight: 600; cursor: pointer;
            transition: all 0.3s; display: flex; align-items: center; justify-content: center; gap: 0.5rem;
        }
        .btn-primary { background: var(--primary); color: white; }
        .btn-primary:hover { background: #2563EB; }
        .btn-secondary { background: var(--secondary); color: white; }
        .btn-secondary:hover { background: #d93d86; }
        .btn-danger { background: var(--red); color: white; }
        
        .status-dot { height: 12px; width: 12px; background-color: var(--red); border-radius: 50%; box-shadow: 0 0 10px var(--red); }
        .status-dot.active { background-color: var(--green); box-shadow: 0 0 10px var(--green); }
        
        #log-window { background: #000; height: 300px; overflow-y: scroll; font-family: monospace; padding: 15px; border-radius: 8px; }
        .log-error { color: var(--red); } .log-success { color: var(--green); } .log-db { color: var(--yellow); }
        
        .stat-card { text-align: center; }
        .stat-card h3 { font-size: 1rem; color: var(--text-muted); margin: 0; }
        .stat-card p { font-size: 1.5rem; font-weight: 700; margin: 5px 0; }
        
        table { width: 100%; border-collapse: collapse; }
        th, td { text-align: left; padding: 12px; border-bottom: 1px solid var(--border); }
        th { font-weight: 600; color: var(--text-muted); }

        #toast-container { position: fixed; bottom: 20px; right: 20px; z-index: 1000; }
        .toast { padding: 15px; border-radius: 8px; color: white; box-shadow: 0 3px 10px rgba(0,0,0,0.3); opacity: 0; animation: fadeIn 0.5s forwards; }
        .toast.success { background: var(--green); } .toast.error { background: var(--red); }
        @keyframes fadeIn { to { opacity: 1; } }

        /* Modal Styles */
        .modal { display: none; position: fixed; z-index: 1001; left: 0; top: 0; width: 100%; height: 100%; overflow: auto; background-color: rgba(0,0,0,0.7); }
        .modal-content { background-color: var(--bg-card); margin: 15% auto; padding: 20px; border: 1px solid var(--border); width: 80%; max-width: 500px; border-radius: 12px; }
        .close { color: #aaa; float: right; font-size: 28px; font-weight: bold; cursor: pointer; }
    </style>
</head>
<body>
    
    <div id="toast-container"></div>

    <div class="header">
        <div class="header-title">
            <span id="status" class="status-dot"></span>
            <h1>Bot Mission Control</h1>
        </div>
        <div id="health-stats" style="display: flex; gap: 2rem;"></div>
    </div>

    <div class="container">
        <!-- Main Controls -->
        <div class="card col-span-4">
            <h2><i class="fas fa-plug"></i> Connection</h2>
            <div class="input-group"> <i class="fas fa-user"></i> <input type="text" id="username" placeholder="Username"> </div>
            <div class="input-group" style="margin-top:10px"> <i class="fas fa-key"></i> <input type="password" id="password" placeholder="Password"> </div>
            <button class="btn-primary" style="margin-top:10px" onclick="loginAndStart()"> <i class="fas fa-power-off"></i> Login & Start </button>
            <button class="btn-danger" style="margin-top:10px" onclick="stopBot()"> <i class="fas fa-stop-circle"></i> Stop Bot </button>
        </div>

        <div class="card col-span-4">
            <h2><i class="fas fa-paper-plane"></i> Admin Console</h2>
            <div class="input-group"> <i class="fas fa-users"></i> <input type="text" id="roomName" placeholder="Room Name"> </div>
            <div class="input-group" style="margin-top:10px"> <i class="fas fa-comment"></i> <input type="text" id="adminMessage" placeholder="Send message as bot..."> </div>
            <button class="btn-secondary" style="margin-top:10px" onclick="adminSendMessage()"> <i class="fas fa-paper-plane"></i> Send Message </button>
        </div>

        <div class="card col-span-4">
            <h2><i class="fas fa-puzzle-piece"></i> Plugins</h2>
            <div id="plugin-list" style="margin-bottom:1rem;"></div>
            <button class="btn-primary" onclick="reloadPlugins()"> <i class="fas fa-sync"></i> Reload Plugins </button>
        </div>

        <!-- Leaderboard -->
        <div class="card col-span-6">
            <h2><i class="fas fa-trophy"></i> Global Leaderboard</h2>
            <table id="leaderboard-table">
                <thead><tr><th>Rank</th><th>Player</th><th>Score</th></tr></thead>
                <tbody></tbody>
            </table>
        </div>

        <!-- User Search -->
        <div class="card col-span-6">
            <h2><i class="fas fa-search"></i> User Profile</h2>
            <div class="input-group">
                <input type="text" id="user-search-input" placeholder="Search by username...">
                <button class="btn-primary" onclick="searchUser()"><i class="fas fa-search"></i></button>
            </div>
            <div id="user-profile-modal" class="modal">
                <div class="modal-content"> <span class="close">&times;</span> <div id="user-profile-content"></div> </div>
            </div>
        </div>
        
        <!-- Logs -->
        <div class="card col-span-12">
            <h2><i class="fas fa-terminal"></i> System Logs</h2>
            <div id="log-window"></div>
        </div>
    </div>

<script>
    document.addEventListener('DOMContentLoaded', () => {
        document.getElementById('username').value = localStorage.getItem('bot_username') || '';
        document.getElementById('roomName').value = localStorage.getItem('bot_roomName') || '';
        document.querySelector('.modal .close').onclick = () => document.getElementById('user-profile-modal').style.display = 'none';
    });

    // --- Helpers ---
    function showToast(m, t='success') { /* ... */ } // Assume same toast function
    async function api(e, d={}) { /* ... */ } // Assume same api function

    // --- NEW: API Calls ---
    async function adminSendMessage() {
        const room = document.getElementById('roomName').value;
        const msg = document.getElementById('adminMessage').value;
        if (!room || !msg) return showToast('Room and Message required', 'error');
        const res = await api('/admin/send', {room, msg});
        showToast(res.msg, res.success ? 'success' : 'error');
        document.getElementById('adminMessage').value = '';
    }

    async function searchUser() {
        const username = document.getElementById('user-search-input').value;
        if (!username) return;
        const res = await fetch(`/api/user/stats?username=${username}`).then(r => r.json());
        const content = document.getElementById('user-profile-content');
        if (res.success) {
            let html = `<h2><i class="fas fa-user-circle"></i> @${res.data.username}</h2>`;
            html += `<p><strong>Global Score:</strong> ${res.data.global_score}</p>`;
            html += `<p><strong>Total Wins:</strong> ${res.data.wins}</p>`;
            if (res.data.games && res.data.games.length) {
                html += '<h3>Game Stats:</h3><table>';
                res.data.games.forEach(g => {
                    html += `<tr><td>${g.game_name}</td><td>${g.earnings} Coins</td><td>${g.wins} Wins</td></tr>`;
                });
                html += '</table>';
            }
            content.innerHTML = html;
        } else {
            content.innerHTML = `<p>${res.msg}</p>`;
        }
        document.getElementById('user-profile-modal').style.display = 'block';
    }
    
    // --- Existing Functions (Modified) ---
    async function loginAndStart() { /* ... similar logic ... */ }
    async function stopBot() { /* ... similar logic ... */ }
    async function reloadPlugins() { /* ... similar logic ... */ }

    // --- Main Update Loop ---
    async function updateAllStatus() {
        try {
            const status = await fetch('/api/status').then(r => r.json());
            const health = await fetch('/api/health').then(r => r.json());
            const leaderboard = await fetch('/api/leaderboard').then(r => r.json());

            // Status & Health
            document.getElementById('status').classList.toggle('active', status.running);
            document.getElementById('health-stats').innerHTML = `
                <div class="stat-card"><h3>UPTIME</h3><p>${health.uptime}</p></div>
                <div class="stat-card"><h3>RAM</h3><p>${health.ram}%</p></div>
                <div class="stat-card"><h3>CPU</h3><p>${health.cpu}%</p></div>
            `;

            // Logs (color coded)
            const logWin = document.getElementById('log-window');
            logWin.innerHTML = status.logs.map(log => {
                let c = '';
                if (log.includes('Error')) c = 'log-error';
                else if (log.includes('Connect')) c = 'log-success';
                else if (log.includes('[DB]')) c = 'log-db';
                return `<div class="${c}">${log}</div>`;
            }).join('');
            logWin.scrollTop = logWin.scrollHeight;
            
            // Plugins
            document.getElementById('plugin-list').innerHTML = status.plugins.map(p => `<span>${p}</span>`).join(', ');

            // Leaderboard
            const lb_body = document.querySelector('#leaderboard-table tbody');
            lb_body.innerHTML = leaderboard.data.map((p, i) => `
                <tr>
                    <td>#${i + 1}</td>
                    <td>${p.username}</td>
                    <td>${p.score}</td>
                </tr>
            `).join('');

        } catch (e) { console.error("Update failed", e); }
    }
    
    // --- Assume all other helper/API functions from previous UI are here ---
    // This is a condensed script. The full logic for login, stop, etc.
    // with buttons and toasts would be here.
    
    setInterval(updateAllStatus, 5000);
    updateAllStatus();
</script>

</body>
</html>
"""

def register_routes(app, bot_instance):
    
    @app.route('/')
    def index():
        return render_template_string(DASHBOARD_HTML)

    # --- EXISTING API (UNCHANGED) ---
    @app.route('/api/start', methods=['POST'])
    def start_bot():
        data = request.json
        success, msg = bot_instance.login_api(data['username'], data['password'])
        if success:
            bot_instance.connect_ws()
            # Set start time on successful connection
            bot_instance.start_time = time.time() 
            bot_instance.plugins.load_plugins()
        return jsonify({"success": success, "msg": msg})

    # ... (stop, join, reload_plugins, status routes are the same)
    
    # --- NEW API ENDPOINTS ---
    
    @app.route('/api/health')
    def health_check():
        uptime_seconds = time.time() - getattr(bot_instance, 'start_time', time.time())
        uptime_str = time.strftime('%H:%M:%S', time.gmtime(uptime_seconds))
        return jsonify({
            "uptime": uptime_str,
            "ram": psutil.virtual_memory().percent,
            "cpu": psutil.cpu_percent(interval=0.1)
        })

    @app.route('/api/leaderboard')
    def get_leaderboard():
        try:
            conn = db.get_connection()
            cur = conn.cursor()
            cur.execute("SELECT username, global_score FROM users ORDER BY global_score DESC LIMIT 10")
            rows = cur.fetchall()
            conn.close()
            leaderboard_data = [{"username": r[0], "score": r[1]} for r in rows]
            return jsonify({"success": True, "data": leaderboard_data})
        except Exception as e:
            return jsonify({"success": False, "msg": str(e)})

    @app.route('/api/user/stats')
    def get_user_stats():
        username = request.args.get('username')
        if not username:
            return jsonify({"success": False, "msg": "Username required"})
        
        try:
            conn = db.get_connection()
            cur = conn.cursor()
            ph = "%s" if db.DATABASE_URL.startswith("postgres") else "?"
            
            cur.execute(f"SELECT user_id, global_score, wins FROM users WHERE username = {ph}", (username,))
            user_row = cur.fetchone()
            
            if not user_row:
                return jsonify({"success": False, "msg": "User not found"})

            user_id, global_score, wins = user_row
            
            cur.execute(f"SELECT game_name, wins, earnings FROM game_stats WHERE user_id = {ph}", (user_id,))
            game_rows = cur.fetchall()
            
            conn.close()

            user_data = {
                "username": username,
                "global_score": global_score,
                "wins": wins,
                "games": [{"game_name": g[0], "wins": g[1], "earnings": g[2]} for g in game_rows]
            }
            return jsonify({"success": True, "data": user_data})
        except Exception as e:
            return jsonify({"success": False, "msg": str(e)})

    @app.route('/api/admin/send', methods=['POST'])
    def admin_send_message():
        data = request.json
        if not bot_instance.running:
            return jsonify({"success": False, "msg": "Bot is not running"})
        
        bot_instance.send_message(data['room'], f"[📢 ADMIN] {data['msg']}")
        return jsonify({"success": True, "msg": "Message sent!"})

    # You would need to add the other existing API routes here as well
    # for stop, join, reload_plugins, status
    
    @app.route('/api/stop', methods=['POST'])
    def stop_bot():
        bot_instance.disconnect()
        return jsonify({"success": True, "msg": "Bot stopping..."})

    @app.route('/api/join', methods=['POST'])
    def join_room():
        data = request.json
        if not bot_instance.running:
            return jsonify({"success": False, "msg": "Bot not running"})
        bot_instance.join_room(data['room'], data.get('pass', ''))
        return jsonify({"success": True, "msg": "Join command sent"})

    @app.route('/api/plugins/reload', methods=['POST'])
    def reload_plugins():
        loaded = bot_instance.plugins.load_plugins()
        return jsonify({"success": True, "msg": f"Reloaded: {', '.join(loaded) if loaded else 'None'}"})

    @app.route('/api/status', methods=['GET'])
    def status():
        return jsonify({
            "running": bot_instance.running,
            "logs": bot_instance.logs[-100:],
            "rooms": bot_instance.active_rooms,
            "plugins": list(bot_instance.plugins.plugins.keys())
        })
    
    return ui_bp
