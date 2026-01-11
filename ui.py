<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Howdies Bot Dashboard</title>
<style>
    body { font-family: Arial; background: #f0f2f5; margin: 0; padding: 0; }
    header { background: #007bff; color: white; padding: 1em; text-align: center; }
    main { padding: 1em; max-width: 800px; margin: auto; }
    section { margin-bottom: 2em; background: white; padding: 1em; border-radius: 5px; box-shadow: 0 0 5px rgba(0,0,0,0.1); }
    input, select, button { margin: 0.3em 0; padding: 0.5em; width: 100%; box-sizing: border-box; }
    .logs { background: #000; color: #0f0; font-family: monospace; height: 200px; overflow-y: scroll; padding: 0.5em; border-radius: 5px; }
</style>
</head>
<body>
<header>
    <h1>Howdies Bot Dashboard</h1>
</header>
<main>
    <!-- Bot Login -->
    <section>
        <h2>Bot Login</h2>
        <form id="loginForm">
            <input type="text" id="bot_id" placeholder="Bot ID" required>
            <input type="password" id="bot_pass" placeholder="Password" required>
            <input type="text" id="room" placeholder="Room Name" required>
            <button type="submit">Login</button>
        </form>
        <div id="loginStatus"></div>
    </section>

    <!-- Plugins -->
    <section>
        <h2>Plugins</h2>
        <select id="pluginSelect">
            <option value="auto_reply">Auto Reply</option>
            <option value="welcome">Welcome</option>
            <option value="game_plugin">TicTacToe</option>
        </select>
        <button onclick="enablePlugin()">Enable Plugin</button>
        <button onclick="disablePlugin()">Disable Plugin</button>
        <div id="pluginStatus"></div>
    </section>

    <!-- Logs -->
    <section>
        <h2>Bot Logs</h2>
        <div class="logs" id="logs"></div>
        <button onclick="refreshLogs()">Refresh Logs</button>
    </section>
</main>

<script>
// ----- Bot Login -----
const loginForm = document.getElementById("loginForm");
loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const bot_id = document.getElementById("bot_id").value;
    const bot_pass = document.getElementById("bot_pass").value;
    const room = document.getElementById("room").value;

    try {
        const res = await fetch("/bot/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ bot_id, bot_pass, room })
        });
        const data = await res.json();
        document.getElementById("loginStatus").innerText = data.message;
    } catch(err) {
        document.getElementById("loginStatus").innerText = "Login failed";
    }
});

// ----- Plugin Enable/Disable -----
async function enablePlugin() {
    const plugin = document.getElementById("pluginSelect").value;
    const res = await fetch("/bot/plugin/enable", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plugin })
    });
    const data = await res.json();
    document.getElementById("pluginStatus").innerText = data.message;
}

async function disablePlugin() {
    const plugin = document.getElementById("pluginSelect").value;
    const res = await fetch("/bot/plugin/disable", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plugin })
    });
    const data = await res.json();
    document.getElementById("pluginStatus").innerText = data.message;
}

// ----- Logs Refresh -----
async function refreshLogs() {
    const res = await fetch("/bot/logs");
    const data = await res.json();
    document.getElementById("logs").innerText = data.logs.join("\n");
}
</script>
</body>
</html>
