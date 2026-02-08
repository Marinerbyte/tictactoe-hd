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
# 🚀 AUTO-PILOT LOGIC (GUNICORN FRIENDLY)
# ==========================================
# Is function ko hum file load hote hi call karenge
def start_auto_pilot():
    auto_user = os.environ.get("AUTO_USER")
    auto_pass = os.environ.get("AUTO_PASS")

    if auto_user and auto_pass:
        print(f"[Auto-Pilot] Credentials found for: {auto_user}")
        
        def runner():
            # 5 Second wait taaki server fully ready ho jaye
            time.sleep(5)
            
            # Check if already running (Restart prevention)
            if bot.running or bot.token:
                print("[Auto-Pilot] Bot already running. Skipping.")
                return

            print("[Auto-Pilot] Connecting...")
            success, msg = bot.login_api(auto_user, auto_pass)
            
            if success:
                bot.connect_ws()
                bot.start_time = time.time()
                bot.plugins.load_plugins()
                print(f"[Auto-Pilot] ✅ SUCCESS: Bot Connected automatically!")
            else:
                print(f"[Auto-Pilot] ❌ FAILED: {msg}")

        # Thread start
        threading.Thread(target=runner, daemon=True).start()
    else:
        print("[Auto-Pilot] No credentials found (AUTO_USER/AUTO_PASS missing).")

# 🔥 ISKO BAHAR CALL KARO (Taki Render isse ignore na kare)
start_auto_pilot()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, threaded=True)
