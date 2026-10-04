"""Render-compatible health server with a supervised Telegram runner child."""
import os
import signal
import subprocess
import sys
import threading
from pathlib import Path

BOT_PROCESS = None
STOP_EVENT = threading.Event()
RESTART_DELAY = max(2, int(os.getenv("RUNNER_RESTART_DELAY", "5")))


def start_bot():
    global BOT_PROCESS
    if BOT_PROCESS is not None and BOT_PROCESS.poll() is None:
        return
    runner = Path(__file__).with_name("runner.py")
    BOT_PROCESS = subprocess.Popen([sys.executable, str(runner)])


def supervise_bot():
    """Restart the runner if it exits unexpectedly."""
    global BOT_PROCESS
    while not STOP_EVENT.wait(2):
        if BOT_PROCESS is None or BOT_PROCESS.poll() is not None:
            exit_code = None if BOT_PROCESS is None else BOT_PROCESS.returncode
            if exit_code is not None:
                print(f"runner.py exited with code {exit_code}; restarting in {RESTART_DELAY}s",
                      flush=True)
            if STOP_EVENT.wait(RESTART_DELAY):
                break
            try:
                start_bot()
            except Exception as exc:
                print(f"failed to restart runner.py: {exc}", flush=True)


start_bot()
threading.Thread(target=supervise_bot, name="runner-supervisor", daemon=True).start()


def app(environ, start_response):
    path = environ.get("PATH_INFO", "/")
    if path not in ("/", "/health", "/healthz"):
        start_response("404 Not Found", [("Content-Type", "text/plain; charset=utf-8")])
        return [b"Not found"]

    running = BOT_PROCESS is not None and BOT_PROCESS.poll() is None
    body = b"telegram-video-downloader: ok\n" if running else b"telegram-video-downloader: bot restarting\n"
    status = "200 OK" if running else "503 Service Unavailable"
    start_response(status, [("Content-Type", "text/plain; charset=utf-8"),
                            ("Content-Length", str(len(body)))])
    return [body]


def cleanup(_signum=None, _frame=None):
    STOP_EVENT.set()
    if BOT_PROCESS is not None and BOT_PROCESS.poll() is None:
        BOT_PROCESS.terminate()
        try:
            BOT_PROCESS.wait(timeout=10)
        except subprocess.TimeoutExpired:
            BOT_PROCESS.kill()


signal.signal(signal.SIGTERM, cleanup)
signal.signal(signal.SIGINT, cleanup)
