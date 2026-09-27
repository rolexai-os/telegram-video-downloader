#!/usr/bin/env python3
import asyncio
import logging
import os
import re
import shutil
from pathlib import Path

import yt_dlp
from dotenv import load_dotenv
from telegram import InputFile, Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", "downloads"))
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "49"))
MAX_FILE_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024
MAX_CONCURRENT_DOWNLOADS = int(os.getenv("MAX_CONCURRENT_DOWNLOADS", "2"))
COOKIES_FILE = os.getenv("COOKIES_FILE", "").strip()
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("telegram-video-downloader")
semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)
URL_REGEX = re.compile(r"https?://[^\s<>\"]+", re.IGNORECASE)


def clean_url(url: str) -> str:
    return url.rstrip(".,!?)]}>\"'")


def build_opts(template: str) -> dict:
    opts = {
        "format": "bv*[ext=mp4]+ba[ext=m4a]/bv*+ba/b[ext=mp4]/b",
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
    if COOKIES_FILE and Path(COOKIES_FILE).is_file():
        opts["cookiefile"] = COOKIES_FILE
    return opts


def locate_result(ydl, info) -> Path | None:
    requested = Path(ydl.prepare_filename(info))
    candidates = [requested]
    if requested.suffix.lower() != ".mp4":
        candidates.append(requested.with_suffix(".mp4"))
    candidates.extend(sorted(DOWNLOAD_DIR.glob(f"{requested.stem}.*"), key=lambda p: p.stat().st_mtime, reverse=True))
    return next((p for p in candidates if p.is_file() and p.stat().st_size > 0), None)


def sync_download(url: str) -> Path | None:
    template = str(DOWNLOAD_DIR / "%(title).180B [%(id)s].%(ext)s")
    with yt_dlp.YoutubeDL(build_opts(template)) as ydl:
        info = ydl.extract_info(url, download=True)
        if info and info.get("entries"):
            info = next((x for x in info["entries"] if x), None)
        return locate_result(ydl, info) if info else None


async def download_media(url: str) -> Path | None:
    async with semaphore:
        return await asyncio.to_thread(sync_download, url)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 Social Media Video Downloader\n\n"
        "Send a public media URL from YouTube, Shorts, Instagram, Reels, X/Twitter, Facebook, TikTok, Reddit, Vimeo, Dailymotion, or another site supported by yt-dlp.\n\n"
        "The bot downloads the highest available compatible quality and returns the file."
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 Help\n\nSend one media URL and wait for the upload.\n\n"
        "For authenticated media, configure COOKIES_FILE with a valid cookies.txt you are authorized to use.\n"
        "Only download content you have permission to access/download."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        return
    urls = [clean_url(u) for u in URL_REGEX.findall(message.text)]
    if not urls:
        await message.reply_text("❌ Please send a valid media URL.")
        return
    url = urls[0]
    status = await message.reply_text("⏳ Downloading highest available quality…")
    file_path = None
    try:
        await context.bot.send_chat_action(message.chat_id, ChatAction.UPLOAD_VIDEO)
        file_path = await download_media(url)
        if not file_path or not file_path.exists():
            await status.edit_text("❌ Download failed: no media file was produced.")
            return
        size = file_path.stat().st_size
        if size > MAX_FILE_SIZE:
            await status.edit_text(f"❌ File is {size / 1024 / 1024:.1f} MB, above the configured {MAX_FILE_SIZE_MB} MB limit.")
            return
        await status.edit_text("📤 Uploading…")
        with file_path.open("rb") as fh:
            await message.reply_video(video=InputFile(fh, filename=file_path.name), caption=f"✅ {file_path.name}"[:1024], supports_streaming=True)
        await status.delete()
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


def main():
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN is not set. Copy .env.example to .env and configure it.")
    if shutil.which("ffmpeg") is None:
        logger.warning("ffmpeg was not found; some downloads may not merge correctly")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot is running")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
