# app.py
from flask import Flask, request, jsonify
import threading
import os
import logging
import telebot
import importlib
import datetime
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

bot_thread = None
start_time = time.time()  # Track server start time

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
        import bot  # Lazy import
        bot_thread = threading.Thread(target=bot.start_bot)
        bot_thread.daemon = True
        bot_thread.start()
        return jsonify({"status": "Bot started successfully"})
    return jsonify({"status": "Bot is already running"})

@app.route('/ping')
def ping():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.datetime.now().isoformat(),
        "uptime_seconds": round(time.time() - start_time, 2),
        "status_code": 200
    })

def start_server():
    global bot_thread
    import bot
    bot_thread = threading.Thread(target=bot.start_bot)
    bot_thread.daemon = True
    bot_thread.start()
    logger.info("Bot started in background thread")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    start_server()
    app.run(host="0.0.0.0", port=port)
else:
    start_server()  # When run with gunicorn
