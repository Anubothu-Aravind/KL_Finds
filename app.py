# app.py
from flask import Flask, request, jsonify
import threading
import os
import logging
from bot import start_bot

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

bot_thread = None

@app.route('/')
def home():
    return "Telegram Bot Server is running!"

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

@app.route('/start', methods=['POST'])
def start_bot_route():
    global bot_thread
    if bot_thread is None or not bot_thread.is_alive():
        bot_thread = threading.Thread(target=start_bot)
        bot_thread.daemon = True
        bot_thread.start()
        return jsonify({"status": "Bot started successfully"})
    return jsonify({"status": "Bot is already running"})

def start_server():
    # Start the bot in a separate thread when the app starts
    global bot_thread
    bot_thread = threading.Thread(target=start_bot)
    bot_thread.daemon = True
    bot_thread.start()
    logger.info("Bot started in background thread")

if __name__ == "__main__":
    # Get port from environment variable or use 5000 as default
    port = int(os.environ.get("PORT", 5000))
    
    # Start the bot in background thread
    start_server()
    
    # Run Flask app
    app.run(host="0.0.0.0", port=port)
