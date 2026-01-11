from flask import Flask, request, jsonify, render_template
from bot.auth import login_bot
from bot.state import plugin_manager, logs

app = Flask(__name__)

@app.route("/")
def dashboard():
    return render_template("dashboard.html")

@app.route("/bot/login", methods=["POST"])
def bot_login():
    data = request.json
    bot_id = data["bot_id"]
    password = data["bot_pass"]
    room = data["room"]
    success = login_bot(bot_id, password, room)
    return jsonify({"message": "Login successful" if success else "Login failed"})

@app.route("/bot/plugin/enable", methods=["POST"])
def plugin_enable():
    plugin_name = request.json["plugin"]
    plugin_manager.enable(plugin_name)
    return jsonify({"message": f"{plugin_name} enabled"})

@app.route("/bot/plugin/disable", methods=["POST"])
def plugin_disable():
    plugin_name = request.json["plugin"]
    plugin_manager.disable(plugin_name)
    return jsonify({"message": f"{plugin_name} disabled"})

@app.route("/bot/logs")
def get_logs():
    return jsonify({"logs": logs.get_recent()})
