#!/usr/bin/env python3
import asyncio
import logging
import os
import re
import shutil
import time
import uuid
from pathlib import Path

import yt_dlp
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputFile, Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", "downloads"))
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "49"))
MAX_FILE_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024
MAX_CONCURRENT_DOWNLOADS = max(1, int(os.getenv("MAX_CONCURRENT_DOWNLOADS", "2")))
MAX_LINKS_PER_MESSAGE = max(0, int(os.getenv("MAX_LINKS_PER_MESSAGE", "0")))
MAX_QUEUE_PER_USER = max(0, int(os.getenv("MAX_QUEUE_PER_USER", "0")))
RATE_LIMIT_SECONDS = max(0, float(os.getenv("RATE_LIMIT_SECONDS", "2")))
ADMIN_USER_IDS = {
    int(x.strip())
    for x in os.getenv("ADMIN_USER_IDS", "").split(",")
    if x.strip().isdigit()
}
COOKIES_FILE = os.getenv("COOKIES_FILE", "").strip()

DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("telegram-video-downloader")

GLOBAL_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)
URL_REGEX = re.compile(r"https?://[^\s<>\"]+", re.IGNORECASE)
USER_JOBS: dict[int, set[asyncio.Task]] = {}
LAST_REQUEST: dict[int, float] = {}
QUALITY_REQUESTS: dict[str, tuple[int, str]] = {}
JOB_LOCK = asyncio.Lock()



def clean_url(url: str) -> str:
    return url.rstrip(".,!?)]}>\"'")


def human_size(value: int) -> str:
    return f"{value / 1024 / 1024:.1f} MB"


def progress_text(info: dict) -> str:
    status = info.get("status", "")
    if status == "downloading":
        percent = info.get("_percent_str", "0%").strip()
        speed = info.get("_speed_str", "?").strip()
        eta = info.get("_eta_str", "?").strip()
        return f"⬇️ {percent} • {speed} • ETA {eta}"
    if status == "finished":
        return "🔄 Download complete, processing…"
    return "⏳ Processing…"


def build_opts(template: str, audio_only: bool = False, progress_hook=None) -> dict:
    if audio_only:
        fmt = "bestaudio/best"
    else:
        fmt = "bv*[ext=mp4]+ba[ext=m4a]/bv*+ba/b[ext=mp4]/b"

    opts = {
        "format": fmt,
        "outtmpl": template,
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 5,
        "fragment_retries": 5,
        "concurrent_fragment_downloads": 4,
        "restrictfilenames": False,
        "windowsfilenames": True,
        "overwrites": False,
        "socket_timeout": 30,
    }
    if audio_only:
        opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ]
    if progress_hook:
        opts["progress_hooks"] = [progress_hook]
    if COOKIES_FILE and Path(COOKIES_FILE).is_file():
        opts["cookiefile"] = COOKIES_FILE
    return opts


def locate_result(ydl, info: dict, audio_only: bool = False) -> Path | None:
    requested = Path(ydl.prepare_filename(info))
    candidates = [requested]
    if audio_only:
        candidates.extend([requested.with_suffix(".mp3"), requested.with_suffix(".m4a")])
    elif requested.suffix.lower() != ".mp4":
        candidates.append(requested.with_suffix(".mp4"))
    candidates.extend(
        sorted(
            DOWNLOAD_DIR.glob(f"{requested.stem}.*"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
    )
    return next((p for p in candidates if p.is_file() and p.stat().st_size > 0), None)


def sync_download(url: str, audio_only: bool = False, progress_hook=None) -> Path | None:
    suffix = "mp3" if audio_only else "mp4"
    template = str(DOWNLOAD_DIR / f"%(title).180B [%(id)s].{suffix}")
    with yt_dlp.YoutubeDL(build_opts(template, audio_only, progress_hook)) as ydl:
        info = ydl.extract_info(url, download=True)
        if info and info.get("entries"):
            info = next((x for x in info["entries"] if x), None)
        return locate_result(ydl, info, audio_only) if info else None


async def download_media(url: str, audio_only: bool = False, progress_hook=None) -> Path | None:
    async with GLOBAL_SEMAPHORE:
        return await asyncio.to_thread(sync_download, url, audio_only, progress_hook)


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_USER_IDS


async def register_job(user_id: int, task: asyncio.Task, url: str, chat_id: int) -> bool:
    async with JOB_LOCK:
        jobs = USER_JOBS.setdefault(user_id, set())
        # 0 means unlimited per-user queued jobs (still bounded by server resources).
        if MAX_QUEUE_PER_USER > 0 and len(jobs) >= MAX_QUEUE_PER_USER:
            return False
        jobs.add(task)
        return True


async def unregister_job(user_id: int, task: asyncio.Task):
    async with JOB_LOCK:
        jobs = USER_JOBS.get(user_id)
        if jobs:
            jobs.discard(task)
            if not jobs:
                USER_JOBS.pop(user_id, None)


async def rate_limited(user_id: int) -> bool:
    if RATE_LIMIT_SECONDS <= 0:
        return False
    now = time.monotonic()
    previous = LAST_REQUEST.get(user_id, 0)
    if now - previous < RATE_LIMIT_SECONDS:
        return True
    LAST_REQUEST[user_id] = now
    return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 Social Media Downloader\n\n"
        "Send one or multiple media URLs in the same message. Each link is processed independently, "
        "so unlimited Telegram users/devices can use the bot concurrently, subject to server/Telegram limits.\n\n"
        "Supported: YouTube, Shorts, Instagram/Reels, X/Twitter, Facebook, TikTok, Reddit, Vimeo, "
        "Dailymotion and other yt-dlp-supported sites.\n\n"
        "Commands: /help  /status  /cancel  /mp3 <URL>"
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 Help\n\n"
        "• Multiple links per message are supported; set MAX_LINKS_PER_MESSAGE=0 for unlimited links.\n"
        "• Unlimited Telegram users/devices can use the same bot; jobs are isolated per user/chat.\n"
        "• /status shows your active jobs.\n"
        "• /cancel stops your queued/running jobs.\n"
        "• /mp3 <URL> extracts MP3 audio.\n"
        "• Use /quality <URL> to choose a quality profile.\n\n"
        "For authenticated media, configure COOKIES_FILE with a valid cookies.txt you are authorized to use.\n"
        "Only download content you have permission to access/download."
    )


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    async with JOB_LOCK:
        count = len(USER_JOBS.get(user_id, set()))
    queue_label = "unlimited" if MAX_QUEUE_PER_USER == 0 else str(MAX_QUEUE_PER_USER)
    await update.message.reply_text(f"📊 Active jobs: {count}/{queue_label}\nGlobal download slots: {MAX_CONCURRENT_DOWNLOADS}")


async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    async with JOB_LOCK:
        jobs = list(USER_JOBS.get(user_id, set()))
    for task in jobs:
        task.cancel()
    await update.message.reply_text(f"🛑 Cancellation requested for {len(jobs)} job(s).")


async def admin_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Admin only.")
        return
    async with JOB_LOCK:
        total = sum(len(v) for v in USER_JOBS.values())
        users = len(USER_JOBS)
    await update.message.reply_text(f"🛡️ Admin status\nActive users: {users}\nActive jobs: {total}\nGlobal slots: {MAX_CONCURRENT_DOWNLOADS}")


def quality_keyboard(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🎥 Best", callback_data=f"q|best|{token}"),
                InlineKeyboardButton("📱 720p", callback_data=f"q|720|{token}"),
                InlineKeyboardButton("📱 480p", callback_data=f"q|480|{token}"),
            ],
            [InlineKeyboardButton("🎵 MP3", callback_data=f"q|mp3|{token}")],
        ]
    )


async def quality_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if await rate_limited(user_id):
        await update.message.reply_text("⏱️ Please wait a moment before starting another request.")
        return
    urls = [clean_url(u) for u in URL_REGEX.findall(" ".join(context.args))]
    if not urls:
        await update.message.reply_text("Usage: /quality <URL>")
        return
    token = uuid.uuid4().hex[:16]
    QUALITY_REQUESTS[token] = (user_id, urls[0])
    await update.message.reply_text("Choose a quality:", reply_markup=quality_keyboard(token))


def format_for_quality(profile: str) -> str:
    if profile == "720":
        return "bv*[height<=720][ext=mp4]+ba[ext=m4a]/bv*[height<=720]+ba/b[height<=720]/b"
    if profile == "480":
        return "bv*[height<=480][ext=mp4]+ba[ext=m4a]/bv*[height<=480]+ba/b[height<=480]/b"
    return "bv*[ext=mp4]+ba[ext=m4a]/bv*+ba/b[ext=mp4]/b"


def sync_quality_download(url: str, profile: str, progress_hook=None) -> Path | None:
    if profile == "mp3":
        return sync_download(url, audio_only=True, progress_hook=progress_hook)
    template = str(DOWNLOAD_DIR / "%(title).180B [%(id)s].%(ext)s")
    opts = build_opts(template, False, progress_hook)
    opts["format"] = format_for_quality(profile)
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        if info and info.get("entries"):
            info = next((x for x in info["entries"] if x), None)
        return locate_result(ydl, info) if info else None


async def quality_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        _, profile, token = query.data.split("|", 2)
        stored = QUALITY_REQUESTS.pop(token, None)
        if not stored:
            raise ValueError("expired")
        owner_id, url = stored
    except ValueError:
        await query.edit_message_text("❌ Invalid or expired quality request.")
        return

    user_id = query.from_user.id
    if user_id != owner_id:
        await query.edit_message_text("❌ This quality menu belongs to another user.")
        return
    if await rate_limited(user_id):
        await query.edit_message_text("⏱️ Please wait before starting another request.")
        return

    task = asyncio.current_task()
    if task is None or not await register_job(user_id, task, url, query.message.chat_id):
        await query.edit_message_text("❌ Your job queue is full.")
        return

    try:
        status = await query.edit_message_text("⏳ Downloading selected quality…")
        progress = {"last": 0.0, "text": ""}
        def hook(info):
            now = time.monotonic()
            if now - progress["last"] >= 2 or info.get("status") == "finished":
                progress["last"] = now
                progress["text"] = progress_text(info)

        file_path = None
        async with GLOBAL_SEMAPHORE:
            file_path = await asyncio.to_thread(sync_quality_download, url, profile, hook)
        if not file_path or not file_path.exists():
            await status.edit_text("❌ Download failed.")
            return
        if file_path.stat().st_size > MAX_FILE_SIZE:
            await status.edit_text(f"❌ File is {human_size(file_path.stat().st_size)}, above the {MAX_FILE_SIZE_MB} MB limit.")
            return
        await status.edit_text("📤 Uploading…")
        with file_path.open("rb") as fh:
            if profile == "mp3":
                await query.message.reply_audio(audio=InputFile(fh, filename=file_path.name))
            else:
                await query.message.reply_video(
                    video=InputFile(fh, filename=file_path.name),
                    caption=f"✅ {file_path.name}"[:1024],
                    supports_streaming=True,
                )
        await status.delete()
    except asyncio.CancelledError:
        await query.edit_message_text("🛑 Job cancelled.")
    except Exception as exc:
        logger.exception("Quality job failed")
        await query.edit_message_text(f"❌ Error: {str(exc)[:500]}")
    finally:
        if file_path and file_path.exists():
            try:
                file_path.unlink()
            except OSError:
                pass
        await unregister_job(user_id, task)


async def process_one(message, context, user_id: int, url: str, audio_only: bool = False):
    task = asyncio.current_task()
    if task is None or not await register_job(user_id, task, url, message.chat_id):
        await message.reply_text("❌ Your queue is full. Use /status or /cancel.")
        return

    file_path = None
    status = await message.reply_text(f"⏳ {'MP3' if audio_only else 'Video'} download started…")
    try:
        progress = {"last": 0.0}

        def hook(info):
            now = time.monotonic()
            if now - progress["last"] >= 2:
                progress["last"] = now
                logger.info("%s | %s | %s", url, info.get("status"), progress_text(info))

        file_path = await download_media(url, audio_only, hook)
        if not file_path or not file_path.exists():
            await status.edit_text("❌ Download failed: no media file was produced.")
            return

        size = file_path.stat().st_size
        if size > MAX_FILE_SIZE:
            await status.edit_text(f"❌ File is {human_size(size)}, above the configured {MAX_FILE_SIZE_MB} MB limit.")
            return

        await status.edit_text("📤 Uploading…")
        await context.bot.send_chat_action(message.chat_id, ChatAction.UPLOAD_VIDEO)
        with file_path.open("rb") as fh:
            if audio_only:
                await message.reply_audio(audio=InputFile(fh, filename=file_path.name))
            else:
                await message.reply_video(
                    video=InputFile(fh, filename=file_path.name),
                    caption=f"✅ {file_path.name}"[:1024],
                    supports_streaming=True,
                )
        await status.delete()
    except asyncio.CancelledError:
        try:
            await status.edit_text("🛑 Job cancelled.")
        except Exception:
            pass
    except yt_dlp.utils.DownloadError as exc:
        logger.exception("yt-dlp error")
        await status.edit_text(f"❌ yt-dlp error: {str(exc).replace(chr(10), ' ')[:500]}")
    except Exception as exc:
        logger.exception("Processing error")
        await status.edit_text(f"❌ Error: {str(exc)[:500]}")
    finally:
        if file_path and file_path.exists():
            try:
                file_path.unlink()
            except OSError:
                pass
        await unregister_job(user_id, task)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        return

    user_id = update.effective_user.id
    if await rate_limited(user_id):
        await message.reply_text("⏱️ Please wait a moment before starting another request.")
        return

    urls = [clean_url(u) for u in URL_REGEX.findall(message.text)]
    if not urls:
        await message.reply_text("❌ Please send one or more valid media URLs.")
        return

    if MAX_LINKS_PER_MESSAGE > 0 and len(urls) > MAX_LINKS_PER_MESSAGE:
        await message.reply_text(f"❌ Maximum {MAX_LINKS_PER_MESSAGE} links per message.")
        return

    tasks = []
    for url in urls:
        task = asyncio.create_task(process_one(message, context, user_id, url))
        tasks.append(task)

    await message.reply_text(f"📥 Queued {len(tasks)} link(s). You can use /status to monitor your jobs.")


async def mp3_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if await rate_limited(user_id):
        await update.message.reply_text("⏱️ Please wait a moment before starting another request.")
        return
    urls = [clean_url(u) for u in URL_REGEX.findall(" ".join(context.args))]
    if not urls:
        await update.message.reply_text("Usage: /mp3 <URL>")
        return
    if MAX_LINKS_PER_MESSAGE > 0 and len(urls) > MAX_LINKS_PER_MESSAGE:
        await update.message.reply_text(f"❌ Maximum {MAX_LINKS_PER_MESSAGE} links per command.")
        return
    for url in urls:
        asyncio.create_task(process_one(update.message, context, user_id, url, audio_only=True))
    await update.message.reply_text(f"🎵 Queued {len(urls)} MP3 job(s).")


def main():
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN is not set. Copy .env.example to .env and configure it.")
    if shutil.which("ffmpeg") is None:
        logger.warning("ffmpeg was not found; some downloads/audio conversions may fail")

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("cancel", cancel_cmd))
    app.add_handler(CommandHandler("mp3", mp3_cmd))
    app.add_handler(CommandHandler("quality", quality_cmd))
    app.add_handler(CommandHandler("admin", admin_status))
    app.add_handler(CallbackQueryHandler(quality_callback, pattern=r"^q\|"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot is running")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
