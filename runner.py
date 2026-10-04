#!/usr/bin/env python3
"""Production runner with robust yt-dlp handling and roadmap feature extensions."""
import asyncio, logging, os, random, time
import httpx
from pathlib import Path
import yt_dlp
import bot
import admin_panel
from telegram import BotCommand, BotCommandScopeChat
from telegram.error import Conflict, NetworkError, RetryAfter, TimedOut
from telegram.ext import TypeHandler
from telegram.request import HTTPXRequest

log = logging.getLogger("telegram-video-downloader.runner")
MAX_ATTEMPTS = max(1, int(os.getenv("YTDLP_MAX_ATTEMPTS", "3")))
RETRY_DELAY = max(0.5, float(os.getenv("YTDLP_RETRY_DELAY", "2")))
FORCE_IPV4 = os.getenv("YTDLP_FORCE_IPV4", "0").lower() in {"1","true","yes","on"}
USER_AGENT = os.getenv("YTDLP_USER_AGENT", "").strip()
COOKIES_FROM_BROWSER = os.getenv("COOKIES_FROM_BROWSER", "").strip()
COOKIES_FROM_BROWSER_PROFILE = os.getenv("COOKIES_FROM_BROWSER_PROFILE", "").strip()
YTDLP_JS_RUNTIME = os.getenv("YTDLP_JS_RUNTIME", "deno").strip()
YTDLP_REMOTE_COMPONENTS = os.getenv("YTDLP_REMOTE_COMPONENTS", "").strip()
DEFAULT_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140 Safari/537.36"
PAUSED_USERS = set()
FEATURE_VERSION = "1.10.0"

INSTANCE_LOCK_FILE = Path(os.getenv("BOT_INSTANCE_LOCK", ".bot-instance.lock"))
INSTANCE_LOCK_HANDLE = None
CONFLICT_EXIT_CODE = 75

# Telegram Bot API network hardening.
TG_CONNECT_TIMEOUT = max(5.0, float(os.getenv("TG_CONNECT_TIMEOUT", "20")))
TG_READ_TIMEOUT = max(10.0, float(os.getenv("TG_READ_TIMEOUT", "45")))
TG_WRITE_TIMEOUT = max(20.0, float(os.getenv("TG_WRITE_TIMEOUT", "90")))
TG_POOL_TIMEOUT = max(5.0, float(os.getenv("TG_POOL_TIMEOUT", "20")))
TG_MEDIA_WRITE_TIMEOUT = max(30.0, float(os.getenv("TG_MEDIA_WRITE_TIMEOUT", "180")))
TG_CONNECTION_POOL = max(8, int(os.getenv("TG_CONNECTION_POOL", "32")))
TG_HTTP_RETRIES = max(0, int(os.getenv("TG_HTTP_RETRIES", "3")))
TG_UPDATES_TIMEOUT = max(10, int(os.getenv("TG_UPDATES_TIMEOUT", "35")))
WATCHDOG_INTERVAL = max(30, int(os.getenv("TG_WATCHDOG_INTERVAL", "60")))
SERVER_HEARTBEAT_INTERVAL = max(15, int(os.getenv("SERVER_HEARTBEAT_INTERVAL", "30")))

def acquire_instance_lock():
    """Prevent two local runner.py processes from polling the same bot token."""
    global INSTANCE_LOCK_HANDLE
    import fcntl
    INSTANCE_LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    INSTANCE_LOCK_HANDLE = INSTANCE_LOCK_FILE.open("a+")
    try:
        fcntl.flock(INSTANCE_LOCK_HANDLE.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        log.error("Another runner.py instance already owns %s; refusing to start.", INSTANCE_LOCK_FILE)
        raise SystemExit(CONFLICT_EXIT_CODE)
    INSTANCE_LOCK_HANDLE.seek(0)
    INSTANCE_LOCK_HANDLE.truncate()
    INSTANCE_LOCK_HANDLE.write(str(os.getpid()) + "\n")
    INSTANCE_LOCK_HANDLE.flush()


def release_instance_lock():
    global INSTANCE_LOCK_HANDLE
    if INSTANCE_LOCK_HANDLE is None:
        return
    try:
        import fcntl
        fcntl.flock(INSTANCE_LOCK_HANDLE.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass
    try:
        INSTANCE_LOCK_HANDLE.close()
    except OSError:
        pass
    INSTANCE_LOCK_HANDLE = None


def make_telegram_request(*, read_timeout, write_timeout, connection_pool_size):
    return HTTPXRequest(
        connection_pool_size=connection_pool_size,
        read_timeout=read_timeout,
        write_timeout=write_timeout,
        connect_timeout=TG_CONNECT_TIMEOUT,
        pool_timeout=TG_POOL_TIMEOUT,
        media_write_timeout=TG_MEDIA_WRITE_TIMEOUT,
        http_version="1.1",
        httpx_kwargs={"transport": httpx.AsyncHTTPTransport(retries=TG_HTTP_RETRIES)},
    )


async def server_watchdog():
    """Keep the current local/Render server presence fresh in SQLite."""
    while True:
        try:
            bot.server_heartbeat("online")
        except Exception as exc:
            log.warning("Server heartbeat failed: %s", error_text(exc))
        await asyncio.sleep(SERVER_HEARTBEAT_INTERVAL)


async def audit_update(update, context):
    try:
        bot.touch_update(update)
    except Exception as exc:
        log.warning("Audit logging failed: %s", error_text(exc))


async def telegram_watchdog(app):
    """Periodically verify Telegram API reachability."""
    while True:
        await asyncio.sleep(WATCHDOG_INTERVAL)
        started = time.monotonic()
        try:
            me = await app.bot.get_me(
                read_timeout=TG_READ_TIMEOUT,
                connect_timeout=TG_CONNECT_TIMEOUT,
                pool_timeout=TG_POOL_TIMEOUT,
            )
            log.info("Telegram watchdog: online as @%s (%.2fs)",
                     me.username or me.id, time.monotonic() - started)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("Telegram watchdog: connection check failed: %s", error_text(exc))


PUBLIC_COMMANDS = [
    BotCommand("start","Open the bot menu"),
    BotCommand("help","Show all commands"),
    BotCommand("quality","Choose video quality"),
    BotCommand("mp3","Download audio"),
    BotCommand("subs","Download with subtitles"),
    BotCommand("playlist","Download playlist/batch"),
    BotCommand("analyze","Inspect media formats"),
    BotCommand("status","Show active jobs"),
    BotCommand("queue","Show queue state"),
    BotCommand("pause","Pause your queue"),
    BotCommand("resume","Resume your queue"),
    BotCommand("cancel","Cancel your jobs"),
    BotCommand("settings","Open settings"),
    BotCommand("history","Show download history"),
    BotCommand("favorites","Show favorites"),
    BotCommand("stats","Show personal statistics"),
    BotCommand("version","Show bot version"),
    BotCommand("terms","Show usage terms"),
]
ADMIN_COMMANDS = PUBLIC_COMMANDS + [
    BotCommand("admin","Open admin dashboard"),
    BotCommand("panel","Open admin dashboard"),
    BotCommand("cleanup","Remove stale files"),
    BotCommand("announce","Broadcast an announcement"),
]


async def post_init(app):
    bot.server_heartbeat("online")
    await app.bot.set_my_commands(PUBLIC_COMMANDS)
    for admin_id in bot.ADMIN_USER_IDS:
        try:
            await app.bot.set_my_commands(ADMIN_COMMANDS, scope=BotCommandScopeChat(admin_id))
        except Exception as exc:
            log.warning("Could not set admin command menu for %s: %s", admin_id, error_text(exc))
    app.bot_data["telegram_watchdog_task"] = asyncio.create_task(telegram_watchdog(app))
    app.bot_data["server_watchdog_task"] = asyncio.create_task(server_watchdog())


async def post_shutdown(app):
    for key in ("telegram_watchdog_task","server_watchdog_task"):
        task = app.bot_data.pop(key, None)
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    try:
        bot.server_heartbeat("offline")
    except Exception:
        pass


async def telegram_error_handler(update, context):
    exc = context.error
    if isinstance(exc, RetryAfter):
        log.warning("Telegram API rate limit; retry after %s seconds", exc.retry_after)
    elif isinstance(exc, Conflict):
        log.error("Telegram getUpdates conflict: another active poller owns this bot token. Stop the other deployment/process.")
    elif isinstance(exc, (TimedOut, NetworkError)):
        log.warning("Telegram API network error; request/polling layer will retry: %s", error_text(exc))
    else:
        log.exception("Unhandled Telegram update error", exc_info=exc)

def error_text(exc):
    return " ".join(str(exc).replace("\n"," ").split())[:1000]

def classify_error(exc):
    s = error_text(exc).lower()
    rules = [
        (("403","forbidden"), "HTTP 403: the source rejected the media request; authorized cookies may be required."),
        (("429","rate limit"), "HTTP 429: the source rate-limited this request; wait and retry."),
        (("401","unauthorized"), "HTTP 401: authentication may be required."),
        (("404","not found"), "HTTP 404: media was not found or is no longer available."),
        (("timeout","timed out"), "Network timeout while contacting the source."),
        (("name or service not known","temporary failure in name resolution"), "DNS/network resolution failed."),
        (("ssl","tls","certificate"), "TLS/SSL connection failed."),
        (("ffmpeg",), "FFmpeg processing failed; verify FFmpeg is installed."),
        (("unsupported url",), "This URL is not supported by yt-dlp."),
        (("login","sign in","authentication"), "The source requires authentication; use only authorized cookies."),
    ]
    for needles, message in rules:
        if any(x in s for x in needles):
            return message
    return "Download failed. Check the URL and bot logs."

def download_options(template, audio, hook, attempt, profile="best", captions=False, url=""):
    o = {
        "format": "bestaudio/best" if audio else bot.format_for_quality(profile),
        "outtmpl": template, "merge_output_format": "mp4", "noplaylist": True,
        "quiet": True, "retries": 3, "fragment_retries": 5,
        "file_access_retries": 3, "extractor_retries": 3,
        "socket_timeout": 30, "connecttimeout": 30, "continuedl": True,
        "overwrites": False, "restrictfilenames": False, "windowsfilenames": True,
        "concurrent_fragment_downloads": 1, "http_chunk_size": 10*1024*1024,
    }
    if audio:
        o["postprocessors"] = [{"key":"FFmpegExtractAudio","preferredcodec":"mp3",
                                "preferredquality":os.getenv("DEFAULT_AUDIO_QUALITY","192")}]
    if captions:
        o.update(writesubtitles=True, writeautomaticsub=True,
                 subtitleslangs=["all"], subtitlesformat="srt/vtt/best")
    if hook: o["progress_hooks"] = [hook]
    # Full YouTube extraction now depends on EJS plus a supported JS runtime.
    if YTDLP_JS_RUNTIME:
        o["js_runtimes"] = YTDLP_JS_RUNTIME
    if YTDLP_REMOTE_COMPONENTS:
        o["remote_components"] = [x.strip() for x in YTDLP_REMOTE_COMPONENTS.split(",") if x.strip()]
    cookie_file = bot.cookie_file_for_url(url)
    if cookie_file:
        o["cookiefile"] = str(cookie_file)
    elif COOKIES_FROM_BROWSER:
        o["cookiesfrombrowser"] = (COOKIES_FROM_BROWSER, COOKIES_FROM_BROWSER_PROFILE or None)
    if FORCE_IPV4 or attempt >= 2: o["source_address"] = "0.0.0.0"
    ua = USER_AGENT or (DEFAULT_UA if attempt >= 2 else "")
    if ua: o["http_headers"] = {"User-Agent": ua}
    return o

def robust_sync_download(url, audio_only=False, progress_hook=None, profile="best", captions=False):
    suffix = "mp3" if audio_only else "%(ext)s"
    template = str(bot.DOWNLOAD_DIR / f"%(title).180B [%(id)s].{suffix}")
    last = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with yt_dlp.YoutubeDL(download_options(template, audio_only, progress_hook, attempt, profile, captions, url)) as ydl:
                info = ydl.extract_info(url, download=True)
                if info and info.get("entries"):
                    info = next((x for x in info["entries"] if x), None)
                result = bot.locate_result(ydl, info, audio_only) if info else None
                if result: return result
                raise RuntimeError("yt-dlp completed without producing a media file")
        except (asyncio.CancelledError, KeyboardInterrupt):
            raise
        except Exception as exc:
            last = exc
            log.warning("yt-dlp attempt %s/%s: %s | %s", attempt, MAX_ATTEMPTS, classify_error(exc), error_text(exc))
            if attempt < MAX_ATTEMPTS:
                time.sleep(RETRY_DELAY * attempt + random.uniform(0, 0.75))
    raise last or RuntimeError("Download failed")

def robust_sync_quality_download(url, profile, progress_hook=None, captions=False):
    return robust_sync_download(url, False, progress_hook, profile, captions)

async def robust_download_media(url, audio_only=False, progress_hook=None, profile="best", captions=False):
    return await asyncio.to_thread(robust_sync_download, url, audio_only, progress_hook, profile, captions)

bot.sync_download = robust_sync_download
bot.sync_quality_download = robust_sync_quality_download
bot.download_media = robust_download_media
bot.format_for_quality = getattr(bot, "format_for_quality", getattr(bot, "fmt", None))
bot.locate_result = getattr(bot, "locate_result", getattr(bot, "locate", None))

async def analyze_cmd(update, context):
    urls = [bot.clean_url(x) for x in bot.URL_RE.findall(" ".join(context.args))]
    if not urls:
        return await update.effective_message.reply_text("Usage: /analyze <URL>")
    url = urls[0]
    try:
        def inspect():
            opts = {"quiet": True, "no_warnings": True, "skip_download": True,
                    "noplaylist": True, "socket_timeout": 20}
            if YTDLP_JS_RUNTIME:
                opts["js_runtimes"] = YTDLP_JS_RUNTIME
            if YTDLP_REMOTE_COMPONENTS:
                opts["remote_components"] = [x.strip() for x in YTDLP_REMOTE_COMPONENTS.split(",") if x.strip()]
            cookie_file = bot.cookie_file_for_url(url)
            if cookie_file:
                opts["cookiefile"] = str(cookie_file)
            elif COOKIES_FROM_BROWSER:
                opts["cookiesfrombrowser"] = (COOKIES_FROM_BROWSER, COOKIES_FROM_BROWSER_PROFILE or None)
            with yt_dlp.YoutubeDL(opts) as y: return y.extract_info(url, download=False)
        info = await asyncio.to_thread(inspect)
        formats = info.get("formats", []) if info else []
        heights = sorted({f.get("height") for f in formats if f.get("height")}, reverse=True)
        sizes = [f.get("filesize") or f.get("filesize_approx") for f in formats
                 if f.get("filesize") or f.get("filesize_approx")]
        token = "an" + uuid_token()
        bot.QUALITY_REQUESTS[token] = (update.effective_user.id, url, time.time())
        msg = (f"🔎 {info.get('title','Unknown')[:120]}\n"
               f"🌐 {urlparse_host(url)}\n"
               f"👤 {info.get('uploader') or info.get('channel') or 'unknown'}\n"
               f"⏱️ {info.get('duration') or 'unknown'}s\n"
               f"📐 {', '.join(map(str, heights[:12])) or 'unknown'}p\n"
               f"💾 {bot.size_text(max(sizes)) if sizes else 'unknown'}\n"
               f"🧩 Formats: {len(formats)}")
        await update.effective_message.reply_text(msg, reply_markup=bot.quality_keyboard(token))
    except Exception as exc:
        await update.effective_message.reply_text("❌ " + classify_error(exc))

def uuid_token():
    import uuid
    return uuid.uuid4().hex[:12]

def urlparse_host(url):
    from urllib.parse import urlparse
    return urlparse(url).netloc or "unknown"

async def pause_cmd(update, context):
    PAUSED_USERS.add(update.effective_user.id)
    await update.effective_message.reply_text("⏸️ Queue paused. Active downloads continue; queued jobs wait.")

async def resume_cmd(update, context):
    PAUSED_USERS.discard(update.effective_user.id)
    await update.effective_message.reply_text("▶️ Queue resumed.")

async def queue_cmd(update, context):
    uid = update.effective_user.id
    async with bot.LOCK: jobs = len(bot.JOBS.get(uid, set()))
    state = "paused" if uid in PAUSED_USERS else "running"
    await update.effective_message.reply_text(f"📋 Jobs: {jobs}\nQueue: {state}\nConcurrency: {bot.MAX_CONCURRENT_DOWNLOADS}")

_original_process_one = bot.process_one
async def gated_process_one(*args, **kwargs):
    uid = args[2] if len(args) > 2 else kwargs.get("uid")
    while uid in PAUSED_USERS:
        await asyncio.sleep(1)
    return await _original_process_one(*args, **kwargs)
bot.process_one = gated_process_one

async def stats_cmd(update, context):
    uid = update.effective_user.id
    c = bot.db()
    total = c.execute("SELECT COUNT(*) FROM history WHERE user_id=?", (uid,)).fetchone()[0]
    ok = c.execute("SELECT COUNT(*) FROM history WHERE user_id=? AND status='success'", (uid,)).fetchone()[0]
    failed = c.execute("SELECT COUNT(*) FROM history WHERE user_id=? AND status='failed'", (uid,)).fetchone()[0]
    size = c.execute("SELECT COALESCE(SUM(size),0) FROM history WHERE user_id=?", (uid,)).fetchone()[0]
    c.close()
    await update.effective_message.reply_text(f"📈 Personal statistics\nTotal: {total}\nSuccessful: {ok}\nFailed: {failed}\nData: {bot.size_text(size)}")

async def cleanup_cmd(update, context):
    if update.effective_user.id not in bot.ADMIN_USER_IDS:
        return await update.effective_message.reply_text("❌ Admin only.")
    removed = 0
    for p in bot.DOWNLOAD_DIR.iterdir():
        if p.is_file() and time.time() - p.stat().st_mtime > 3600:
            try: p.unlink(); removed += 1
            except OSError: pass
    await update.effective_message.reply_text(f"🧹 Removed {removed} stale files.")

async def announce_cmd(update, context):
    if update.effective_user.id not in bot.ADMIN_USER_IDS:
        return await update.effective_message.reply_text("❌ Admin only.")
    msg = " ".join(context.args).strip()
    if not msg: return await update.effective_message.reply_text("Usage: /announce <message>")
    c = bot.db(); users = [r[0] for r in c.execute("SELECT user_id FROM users").fetchall()]
    c.execute("INSERT INTO announcements(message,created_at) VALUES(?,?)", (msg, int(time.time())))
    c.commit(); c.close(); sent = 0
    for uid in users:
        try: await context.bot.send_message(uid, "📣 " + msg); sent += 1
        except Exception: pass
    await update.effective_message.reply_text(f"📣 Announcement sent to {sent}/{len(users)} users.")

async def version_cmd(update, context):
    base = Path("VERSION").read_text().strip() if Path("VERSION").exists() else "dev"
    await update.effective_message.reply_text(f"🤖 Telegram Video Downloader\nBase release: v{base}\nRunner features: v{FEATURE_VERSION}\nStatus: Testing/Beta")

def ensure_feature_schema():
    c = bot.db()
    c.execute("CREATE TABLE IF NOT EXISTS announcements(id INTEGER PRIMARY KEY AUTOINCREMENT,message TEXT,created_at INTEGER,active INTEGER DEFAULT 1)")
    c.commit(); c.close()

def main():
    if not bot.BOT_TOKEN: raise SystemExit("BOT_TOKEN is not set")
    acquire_instance_lock()
    import atexit
    atexit.register(release_instance_lock)
    bot.db(); ensure_feature_schema()
    request = make_telegram_request(
        read_timeout=TG_READ_TIMEOUT,
        write_timeout=TG_WRITE_TIMEOUT,
        connection_pool_size=TG_CONNECTION_POOL,
    )
    updates_request = make_telegram_request(
        read_timeout=TG_UPDATES_TIMEOUT + 10,
        write_timeout=30,
        connection_pool_size=4,
    )
    app = (bot.Application.builder()
           .token(bot.BOT_TOKEN)
           .request(request)
           .get_updates_request(updates_request)
           .post_init(post_init)
           .post_shutdown(post_shutdown)
           .build())
    app.add_error_handler(telegram_error_handler)
    app.add_handler(TypeHandler(bot.Update, audit_update), group=-1)
    commands = {
        "start": bot.start, "help": bot.help_cmd, "terms": bot.terms_cmd,
        "status": bot.status_cmd, "queue": queue_cmd, "pause": pause_cmd, "resume": resume_cmd,
        "cancel": bot.cancel_cmd, "analyze": analyze_cmd, "quality": bot.quality_cmd,
        "mp3": bot.mp3_cmd, "subs": bot.subs_cmd, "playlist": bot.playlist_cmd,
        "settings": bot.settings_cmd, "history": bot.history_cmd, "favorites": bot.favorites_cmd,
        "stats": stats_cmd, "version": version_cmd, "admin": admin_panel.panel_cmd,
        "cleanup": cleanup_cmd, "announce": announce_cmd, "panel": admin_panel.panel_cmd,
    }
    for name, fn in commands.items(): app.add_handler(bot.CommandHandler(name, fn))
    app.add_handler(bot.CallbackQueryHandler(admin_panel.panel_callback, pattern=admin_panel.PANEL_PATTERN))
    app.add_handler(bot.CallbackQueryHandler(bot.callback, pattern=r"^(menu|set|q)\|"))
    app.add_handler(bot.MessageHandler(bot.filters.TEXT & ~bot.filters.COMMAND, bot.handle_message))
    # Render/Docker web services already have web.py binding the public PORT.
    # Do not let PTB start a second HTTP listener on the same port.
    # When WEBHOOK_URL is configured, use PTB's webhook *request handling*
    # against the externally managed web process only when explicitly enabled.
    if bot.WEBHOOK_URL and os.getenv("PTB_MANAGED_WEBHOOK", "0").lower() in {"1", "true", "yes", "on"}:
        app.run_webhook(listen="0.0.0.0", port=bot.PORT, url_path="telegram",
                        webhook_url=f"{bot.WEBHOOK_URL.rstrip('/')}/telegram",
                        secret_token=bot.WEBHOOK_SECRET or None, drop_pending_updates=True,
                        allowed_updates=bot.Update.ALL_TYPES, max_connections=20)
    else:
        try:
            app.run_polling(allowed_updates=bot.Update.ALL_TYPES, drop_pending_updates=True, timeout=TG_UPDATES_TIMEOUT, bootstrap_retries=-1, poll_interval=0.5)
        except Conflict:
            log.error("Telegram rejected getUpdates with HTTP 409: another bot instance is active. Stop the duplicate instance and restart this one.")
            raise SystemExit(CONFLICT_EXIT_CODE)

if __name__ == "__main__":
    main()
