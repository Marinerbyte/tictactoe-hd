# ui.py
from flask import Flask, request, jsonify, render_template_string
import requests
import os

app = Flask(__name__)

BOT_API = os.environ.get("BOT_API_URL", "http://localhost:5000")

# =========================================================
# SINGLE UI PAGE
# =========================================================
HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Bot Dashboard</title>
    <style>
        body { font-family: Arial; background:#111; color:#eee; padding:20px }
        h2 { margin-top:30px }
        input, button { padding:6px; margin:5px }
        button { cursor:pointer }
        table { border-collapse: collapse; margin-top:10px }
        td, th { border:1px solid #555; padding:6px }
    </style>
</head>
<body>

<h1>Bot Control Panel</h1>

<h2>Room Control</h2>
<input id="room" placeholder="room name">
<button onclick="startRoom()">Join Room</button>
<button onclick="leaveRoom()">Leave Room</button>
<pre id="roomResult"></pre>

<h2>Plugin Control</h2>
<input id="plugin" placeholder="plugin name">
<button onclick="loadPlugin()">Load Plugin</button>
<button onclick="unloadPlugin()">Unload Plugin</button>
<pre id="pluginResult"></pre>

<h2>Leaderboard</h2>
<button onclick="loadScores()">Refresh Scores</button>
<table id="scores"></table>

<script>
function startRoom(){
    fetch("/api/start_room",{
        method:"POST",
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({room:room.value})
    }).then(r=>r.json()).then(d=>roomResult.innerText=JSON.stringify(d,null,2))
}

function leaveRoom(){
    fetch("/api/leave_room",{
        method:"POST",
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({room:room.value})
    }).then(r=>r.json()).then(d=>roomResult.innerText=JSON.stringify(d,null,2))
}

function loadPlugin(){
    fetch("/api/load_plugin",{
        method:"POST",
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({plugin:plugin.value})
    }).then(r=>r.json()).then(d=>pluginResult.innerText=JSON.stringify(d,null,2))
}

function unloadPlugin(){
    fetch("/api/unload_plugin",{
        method:"POST",
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({plugin:plugin.value})
    }).then(r=>r.json()).then(d=>pluginResult.innerText=JSON.stringify(d,null,2))
}

function loadScores(){
    fetch("/api/leaderboard")
    .then(r=>r.json())
    .then(d=>{
        let html="<tr><th>User</th><th>Score</th></tr>";
        d.users.forEach(u=>{
            html+=`<tr><td>${u.username}</td><td>${u.score}</td></tr>`
        })
        scores.innerHTML=html
    })
}
</script>

</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML)

# =========================================================
# API BRIDGE → app.py
# =========================================================
@app.route("/api/start_room", methods=["POST"])
def start_room():
    return jsonify(requests.post(f"{BOT_API}/dashboard/start_room", json=request.json).json())

@app.route("/api/leave_room", methods=["POST"])
def leave_room():
    return jsonify(requests.post(f"{BOT_API}/dashboard/leave_room", json=request.json).json())

@app.route("/api/load_plugin", methods=["POST"])
def load_plugin():
    return jsonify(requests.post(f"{BOT_API}/dashboard/load_plugin", json=request.json).json())

@app.route("/api/unload_plugin", methods=["POST"])
def unload_plugin():
    return jsonify(requests.post(f"{BOT_API}/dashboard/unload_plugin", json=request.json).json())

@app.route("/api/leaderboard")
def leaderboard():
    return jsonify(requests.get(f"{BOT_API}/dashboard/leaderboard").json())

# =========================================================
# RUN
# =========================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("UI_PORT", 8000)))
