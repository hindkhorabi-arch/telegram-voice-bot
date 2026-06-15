import logging
from flask import Flask
from threading import Thread

app = Flask(__name__)

# إيقاف رسائل الـ Logs المزعجة في الـ Console
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

@app.route('/')
def home():
    return "🟢 Bot is alive and running 24/7!", 200

def run_server():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    server_thread = Thread(target=run_server, daemon=True)
    server_thread.start()


