import os, threading
from flask import Flask
from bot_engine import HowdiesBot
from ui import register_routes
from dotenv import load_dotenv

# --- FIX: .env ko force load karne ke liye ---
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Diagnostic Print (Bot start hote hi terminal mein dikhega)
print(f"DEBUG DB URL: {os.environ.get('DATABASE_URL')[:20] if os.environ.get('DATABASE_URL') else 'NOT FOUND'}")
print(f"DEBUG AI KEY: {'FOUND' if os.environ.get('GROK_API_KEY') else 'NOT FOUND'}")

bot = HowdiesBot()
register_routes(app, bot)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, threaded=True)
