from flask import Blueprint, render_template_string, request, jsonify, redirect, url_for
import os

ui_bp = Blueprint('ui', __name__)

# Single HTML Template
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Howdies Bot Control</title>
    <style>
        body { font-family: sans-serif; background: #222; color: #fff; margin: 0; padding: 20px; }
        .container { max-width: 1000px; margin: 0 auto; display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .card { background: #333; padding: 15px; border-radius: 8px; }
        h2 { margin-top: 0; border-bottom: 1px solid #555; padding-bottom: 10px; }
        input, button { padding: 8px; margin: 5px 0; width: 100%; box-sizing: border-box; }
        button { cursor: pointer; background: #007bff; color: white; border: none; font-weight: bold; }
        button.stop { background: #dc3545; }
        button.action { background: #28a745; width: auto; }
        #log-window { background: #000; height: 300px; overflow-y: scroll; font-family: monospace; padding: 10px; border: 1px solid #444; }
        .status-dot { height: 10px; width: 10px; background-color: red; border-radius: 50%; display: inline-block; }
        .active { background-color: #0f0; }
        table { width: 100%; border-collapse: collapse; }
        th, td { text-align: left; padding: 8px; border-bottom: 1px solid #444; }
    </style>
</head>
<body>

<h1>Howdies Bot Dashboard <span id="status" class="status-dot"></span></h1>

<div class="container">
    
    <!-- Controls -->
    <div class="card">
        <h2>Connection</h2>
        <input type="text" id="username" placeholder="Username">
        <input type="password" id="password" placeholder="Password">
        <button onclick="loginAndStart()">Login & Start Bot</button>
        <button class="stop" onclick="stopBot()">Stop Bot</button>
        
        <h3>Room Management</h3>
        <input type="text" id="roomName" placeholder="Room Name">
        <input type="text" id="roomPass" placeholder="Room Password (Optional)">
        <button onclick="joinRoom()">Join Room</button>
    </div>

    <!-- Stats & Plugins -->
    <div class="card">
        <h2>Plugins</h2>
        <div id="plugin-list"></div>
        <button class="action" onclick="reloadPlugins()">Reload Plugins</button>

        <h2>Active Rooms</h2>
        <ul id="room-list"></ul>
    </div>

    <!-- Logs -->
    <div class="card" style="grid-column: 1 / -1;">
        <h2>System Logs</h2>
        <div id="log-window"></div>
    </div>
</div>

<script>
    async function api(endpoint, data={}) {
        const response = await fetch('/api' + endpoint, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data)
        });
        return await response.json();
    }

    async function loginAndStart() {
        const u = document.getElementById('username').value;
        const p = document.getElementById('password').value;
        const res = await api('/start', {username: u, password: p});
        alert(res.msg);
    }

    async function stopBot() {
        const res = await api('/stop');
        alert(res.msg);
    }

    async function joinRoom() {
        const r = document.getElementById('roomName').value;
        const p = document.getElementById('roomPass').value;
        const res = await api('/join', {room: r, pass: p});
        if(!res.success) alert(res.msg);
    }

    async function reloadPlugins() {
        const res = await api('/plugins/reload');
        alert(res.msg);
        updateStatus();
    }

    async function updateStatus() {
        const res = await fetch('/api/status').then(r => r.json());
        
        // Update Dot
        const dot = document.getElementById('status');
        dot.classList.toggle('active', res.running);
        
        // Logs
        const logWin = document.getElementById('log-window');
        logWin.innerHTML = res.logs.join('<br>');
        logWin.scrollTop = logWin.scrollHeight;

        // Rooms
        const roomList = document.getElementById('room-list');
        roomList.innerHTML = res.rooms.map(r => `<li>${r}</li>`).join('');

        // Plugins
        const plugList = document.getElementById('plugin-list');
        plugList.innerHTML = res.plugins.map(p => `<span>${p}</span>`).join(', ');
    }

    // Poll status
    setInterval(updateStatus, 2000);
    updateStatus();
</script>

</body>
</html>
"""

def register_routes(app, bot_instance):
    
    @app.route('/')
    def index():
        return render_template_string(DASHBOARD_HTML)

    @app.route('/api/start', methods=['POST'])
    def start_bot():
        data = request.json
        success, msg = bot_instance.login_api(data['username'], data['password'])
        if success:
            bot_instance.connect_ws()
            bot_instance.plugins.load_plugins()
        return jsonify({"success": success, "msg": msg})

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
        return jsonify({"success": True, "msg": f"Reloaded: {loaded}"})

    @app.route('/api/status', methods=['GET'])
    def status():
        return jsonify({
            "running": bot_instance.running,
            "logs": bot_instance.logs,
            "rooms": bot_instance.active_rooms,
            "plugins": list(bot_instance.plugins.plugins.keys())
        })
