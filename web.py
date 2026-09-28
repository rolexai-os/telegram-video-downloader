"""Small Render-compatible WSGI wrapper.

Gunicorn serves the health endpoint while the Telegram bot runs as one child
process. The child uses runner.py so yt-dlp gets defensive retry handling.
"""

import os
import signal
import subprocess
import sys
from pathlib import Path

BOT_PROCESS = None


def start_bot():
    global BOT_PROCESS
    if BOT_PROCESS is not None and BOT_PROCESS.poll() is None:
        return
    BOT_PROCESS = subprocess.Popen([sys.executable, str(Path(__file__).with_name("runner.py"))])


start_bot()


def app(environ, start_response):
    path = environ.get("PATH_INFO", "/")
    if path not in ("/", "/health", "/healthz"):
        start_response("404 Not Found", [("Content-Type", "text/plain; charset=utf-8")])
        return [b"Not found"]

    bot_running = BOT_PROCESS is not None and BOT_PROCESS.poll() is None
    body = b"telegram-video-downloader: ok\n" if bot_running else b"telegram-video-downloader: bot stopped\n"
    status = "200 OK" if bot_running else "503 Service Unavailable"
    start_response(status, [("Content-Type", "text/plain; charset=utf-8"), ("Content-Length", str(len(body)))])
    return [body]


def cleanup(_signum=None, _frame=None):
    if BOT_PROCESS is not None and BOT_PROCESS.poll() is None:
        BOT_PROCESS.terminate()


signal.signal(signal.SIGTERM, cleanup)
signal.signal(signal.SIGINT, cleanup)
