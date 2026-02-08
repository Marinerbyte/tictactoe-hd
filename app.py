from flask import Flask
from bot_engine import HowdiesBot
from ui import register_routes
import os
import threading
import time

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Start Bot Instance
bot = HowdiesBot()

# Connect UI to Bot
register_routes(app, bot)

# ==========================================
# 🚀 GHOST-PROOF AUTO PILOT
# ==========================================
def start_auto_pilot():
    auto_user = os.environ.get("AUTO_USER")
    auto_pass = os.environ.get("AUTO_PASS")

    if auto_user and auto_pass:
        print(f"[Auto-Pilot] Config found for {auto_user}")
        
        def runner():
            # 🛑 30 SECONDS DELAY: Taaki Render purane bot ko kill kar sake
            print("[Auto-Pilot] Waiting 30s for session cleanup...")
            time.sleep(30)
            
            if bot.running or bot.token:
                print("[Auto-Pilot] Bot already active via UI. Skipping.")
                return

            print("[Auto-Pilot] Attempting Fresh Connection...")
            success, msg = bot.login_api(auto_user, auto_pass)
            if success:
                bot.connect_ws()
                bot.start_time = time.time()
                bot.plugins.load_plugins()
                print(f"[Auto-Pilot] ✅ SUCCESS: Bot is ONLINE.")
            else:
                print(f"[Auto-Pilot] ❌ FAILED: {msg}")

        threading.Thread(target=runner, daemon=True).start()

# Call Auto Pilot
start_auto_pilot()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, threaded=True)
