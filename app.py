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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    
    # ==========================================
    # 🚀 SMART AUTO-PILOT (Ghost Fix Version)
    # ==========================================
    auto_user = os.environ.get("AUTO_USER")
    auto_pass = os.environ.get("AUTO_PASS")

    if auto_user and auto_pass:
        print(f"[Auto-Pilot] Credentials detected for: {auto_user}")
        
        def auto_boot():
            # 🛑 10 Second Wait: Taaki purana 'Ghost Session' server se clear ho jaye
            print("[Auto-Pilot] Waiting 10s for previous session to clear...")
            time.sleep(10) 
            
            # Check: Agar kisi ne UI se pehle hi login kar diya to hum ruk jayenge
            if bot.running or bot.token:
                print("[Auto-Pilot] Bot already running via UI. Skipping auto-login.")
                return

            print("[Auto-Pilot] Connecting now...")
            success, msg = bot.login_api(auto_user, auto_pass)
            
            if success:
                bot.connect_ws()
                bot.start_time = time.time()
                bot.plugins.load_plugins()
                print(f"[Auto-Pilot] ✅ SUCCESS: Bot is connected and ready!")
            else:
                print(f"[Auto-Pilot] ❌ FAILED: {msg}")

        # Thread start
        threading.Thread(target=auto_boot, daemon=True).start()
    else:
        print("[Auto-Pilot] No credentials. Manual mode active.")

    # Server Start
    app.run(host="0.0.0.0", port=port, threaded=True)
