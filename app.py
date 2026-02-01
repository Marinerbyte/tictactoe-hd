from flask import Flask
from bot_engine import HowdiesBot
from ui import register_routes
import os, threading
from dotenv import load_dotenv

load_dotenv() # .env fetch karne ke liye
app = Flask(__name__)
app.secret_key = os.urandom(24)

# Start Bot Instance
bot = HowdiesBot()

# Connect UI to Bot
register_routes(app, bot)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # 'threaded=True' is crucial here
    app.run(host="0.0.0.0", port=port, threaded=True)
