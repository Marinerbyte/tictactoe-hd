from flask import Flask
from bot_engine import HowdiesBot
from ui import register_routes
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Singleton Bot Instance
bot = HowdiesBot()

# Register UI Routes
register_routes(app, bot)

if __name__ == "__main__":
    # Ensure plugins folder exists
    if not os.path.exists('plugins'):
        os.makedirs('plugins')
        
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, threaded=True)
