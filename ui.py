from flask import Flask, render_template_string, request, jsonify
import requests

app = Flask(__name__)

# ==========================
# HTML Template (TailwindCSS)
# ==========================
HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Bot Dashboard</title>
<script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 min-h-screen p-6">
<div class="max-w-3xl mx-auto bg-white p-6 rounded-xl shadow-lg">

<h1 class="text-2xl font-bold mb-4">Bot Dashboard</h1>

<div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
  <input id="username" type="text" placeholder="Username" class="border rounded px-3 py-2">
  <input id="password" type="password" placeholder="Password" class="border rounded px-3 py-2">
  <input id="room" type="text" placeholder="Room" class="border rounded px-3 py-2">
</div>

<div class="flex gap-4 mb-4">
  <button onclick="login()" class="flex-1 bg-green-500 text-white px-4 py-2 rounded hover:bg-green-600">Login</button>
  <button onclick="logout()" class="flex-1 bg-red-500 text-white px-4 py-2 rounded hover:bg-red-600">Logout</button>
</div>

<div class="mb-4">
  <span class="font-semibold">Status:</span> <span id="status">Disconnected</span>
</div>

<div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
  <div>
    <h2 class="font-semibold mb-1">Active Rooms</h2>
    <ul id="rooms" class="border rounded p-2 h-32 overflow-y-auto bg-gray-50"></ul>
  </div>
  <div>
    <h2 class="font-semibold mb-1">Plugins</h2>
    <ul id="plugins" class="border rounded p-2 h-32 overflow-y-auto bg-gray-50"></ul>
  </div>
</div>

<div class="mb-4">
  <h2 class="font-semibold mb-1">Games</h2>
  <ul id="games" class="border rounded p-2 h-32 overflow-y-auto bg-gray-50"></ul>
</div>

<div>
  <h2 class="font-semibold mb-1">Logs</h2>
  <div id="logs" class="border rounded p-2 h-40 overflow-y-auto bg-gray-50"></div>
</div>

<script>
async function login() {
  const username = document.getElementById("username").value;
  const password = document.getElementById("password").value;
  const room = document.getElementById("room").value;

  const res = await fetch("/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ botId: username, password, room })
  });
  const data = await res.json();
  if (data.ok) {
    document.getElementById("status").innerText = "Connected";
    fetchStatus();
    fetchLogs();
  } else {
    alert(data.error);
  }
}

async function logout() {
  const res = await fetch("/logout", { method: "POST" });
  const data = await res.json();
  if (data.ok) {
    document.getElementById("status").innerText = "Disconnected";
    document.getElementById("rooms").innerHTML = "";
    document.getElementById("plugins").innerHTML = "";
    document.getElementById("games").innerHTML = "";
    document.getElementById("logs").innerHTML = "";
  }
}

async function fetchStatus() {
  const res = await fetch("/status");
  const data = await res.json();

  document.getElementById("rooms").innerHTML = data.rooms.map(r => `<li>${r}</li>`).join("");
  document.getElementById("plugins").innerHTML = data.plugins.map(p => `<li>${p}</li>`).join("");
  document.getElementById("games").innerHTML = data.games.map(g => `<li>${g}</li>`).join("");
}

async function fetchLogs() {
  const res = await fetch("/get_logs");
  const data = await res.json();
  document.getElementById("logs").innerHTML = data.logs.map(l => `<div>${l}</div>`).join("");
}

setInterval(() => {
  if (document.getElementById("status").innerText === "Connected") {
    fetchStatus();
    fetchLogs();
  }
}, 5000);
</script>

</div>
</body>
</html>
"""

# ==========================
# ROUTES
# ==========================
@app.route("/")
def dashboard():
    return render_template_string(HTML)

# ==========================
# BOOT
# ==========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
