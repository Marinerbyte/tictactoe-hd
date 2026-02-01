from flask import Flask
from bot_engine import HowdiesBot
from ui import register_routes
import os, threading
from dotenv import load_dotenv

# VPS par .env ka pura rasta (path) dena zaroori hai
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

# --- DEBUG: Bot start hote hi terminal mein check kar ---
db_url = os.environ.get("DATABASE_URL")
ai_key = os.environ.get("GROK_API_KEY")

print("--- [SYSTEM CHECK] ---")
if db_url: print(f"✅ DATABASE URL: Found (Starts with: {db_url[:15]}...)")
else: print("❌ DATABASE URL: MISSING!")

if ai_key: print(f"✅ GROK API KEY: Found (Length: {len(ai_key)})")
else: print("❌ GROK API KEY: MISSING!")
print("----------------------")

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Start Bot Instance
bot = HowdiesBot()

# Connect UI to Bot
register_routes(app, bot)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, threaded=True)
