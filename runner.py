#!/usr/bin/env python3
"""Production runner with defensive yt-dlp error handling.

The Telegram handlers stay in bot.py. This wrapper replaces the two download
functions at runtime so existing bot behaviour is preserved while transient
HTTP/network errors receive controlled retries and useful user-facing errors.
"""

import asyncio
import logging
import os
import random
import shutil
import time
from pathlib import Path

import yt_dlp

import bot

logger = logging.getLogger("telegram-video-downloader.runner")

MAX_ATTEMPTS = max(1, int(os.getenv("YTDLP_MAX_ATTEMPTS", "3")))
RETRY_DELAY = max(0.5, float(os.getenv("YTDLP_RETRY_DELAY", "2")))
FORCE_IPV4 = os.getenv("YTDLP_FORCE_IPV4", "0").lower() in {"1", "true", "yes", "on"}
USER_AGENT = os.getenv("YTDLP_USER_AGENT", "").strip()

DEFAULT_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)


def _error_text(exc: BaseException) -> str:
    return " ".join(str(exc).replace("\n", " ").split())[:1000]


def classify_error(exc: BaseException) -> str:
    text = _error_text(exc).lower()
    if "403" in text or "forbidden" in text:
        return "HTTP 403 Forbidden: the source rejected the media request"
    if "429" in text or "too many requests" in text or "rate limit" in text:
        return "HTTP 429: the source rate-limited the request"
    if "401" in text or "unauthorized" in text:
        return "HTTP 401 Unauthorized: authentication may be required"
    if "404" in text or "not found" in text:
        return "HTTP 404: media was not found or is no longer available"
    if "timed out" in text or "timeout" in text:
        return "Network timeout while contacting the source"
    if "name or service not known" in text or "temporary failure in name resolution" in text:
        return "DNS/network resolution failed"
    if "certificate" in text or "ssl" in text or "tls" in text:
        return "TLS/SSL connection error"
    if "ffmpeg" in text:
        return "FFmpeg processing error"
    if "unsupported url" in text:
        return "This URL is not supported by yt-dlp"
    if "login" in text or "sign in" in text or "authentication" in text:
        return "The source requires authentication"
    return "Download failed"


def _base_opts(template: str, audio_only: bool, progress_hook=None, attempt: int = 1) -> dict:
    # Keep the same format strategy as bot.py, but make the network layer more
    # tolerant. No authentication or access-control bypass is attempted.
    fmt = "bestaudio/best" if audio_only else "bv*[ext=mp4]+ba[ext=m4a]/bv*+ba/b[ext=mp4]/b"
    opts = {
        "format": fmt,
        "outtmpl": template,
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": False,
        "retries": 3,
        "fragment_retries": 5,
        "file_access_retries": 3,
        "extractor_retries": 3,
        "socket_timeout": 30,
        "connecttimeout": 30,
        "continuedl": True,
        "overwrites": False,
        "restrictfilenames": False,
        "windowsfilenames": True,
        "concurrent_fragment_downloads": 1,
        "http_chunk_size": 10 * 1024 * 1024,
    }
    if audio_only:
        opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]
    if progress_hook:
        opts["progress_hooks"] = [progress_hook]
    if bot.COOKIES_FILE and Path(bot.COOKIES_FILE).is_file():
        opts["cookiefile"] = bot.COOKIES_FILE
    if FORCE_IPV4 or attempt >= 2:
        opts["source_address"] = "0.0.0.0"
    if USER_AGENT:
        opts["http_headers"] = {"User-Agent": USER_AGENT}
    elif attempt >= 2:
        opts["http_headers"] = {"User-Agent": DEFAULT_UA}
    return opts


def _download(url: str, audio_only: bool = False, progress_hook=None) -> Path | None:
    suffix = "mp3" if audio_only else "mp4"
    template = str(bot.DOWNLOAD_DIR / f"%(title).180B [%(id)s].{suffix}")
    last_exc = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            opts = _base_opts(template, audio_only, progress_hook, attempt)
            logger.info("yt-dlp attempt %d/%d: %s", attempt, MAX_ATTEMPTS, url)
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if info and info.get("entries"):
                    info = next((x for x in info["entries"] if x), None)
                if info:
                    result = bot.locate_result(ydl, info, audio_only)
                    if result:
                        return result
            raise RuntimeError("yt-dlp completed without producing a media file")
        except (asyncio.CancelledError, KeyboardInterrupt):
            raise
        except Exception as exc:
            last_exc = exc
            category = classify_error(exc)
            logger.warning("Attempt %d/%d failed: %s | %s", attempt, MAX_ATTEMPTS, category, _error_text(exc))
            if attempt < MAX_ATTEMPTS:
                # Backoff avoids hammering a source after 403/429/network errors.
                delay = RETRY_DELAY * attempt + random.uniform(0, 0.75)
                time.sleep(delay)

    if last_exc:
        raise last_exc
    return None


def robust_sync_download(url: str, audio_only: bool = False, progress_hook=None):
    return _download(url, audio_only, progress_hook)


def robust_sync_quality_download(url: str, profile: str, progress_hook=None):
    if profile == "mp3":
        return _download(url, True, progress_hook)

    if profile == "720":
        fmt = "bv*[height<=720][ext=mp4]+ba[ext=m4a]/bv*[height<=720]+ba/b[height<=720]/b"
    elif profile == "480":
        fmt = "bv*[height<=480][ext=mp4]+ba[ext=m4a]/bv*[height<=480]+ba/b[height<=480]/b"
    else:
        fmt = "bv*[ext=mp4]+ba[ext=m4a]/bv*+ba/b[ext=mp4]/b"

    template = str(bot.DOWNLOAD_DIR / "%(title).180B [%(id)s].%(ext)s")
    last_exc = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            opts = _base_opts(template, False, progress_hook, attempt)
            opts["format"] = fmt
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if info and info.get("entries"):
                    info = next((x for x in info["entries"] if x), None)
                if info:
                    result = bot.locate_result(ydl, info)
                    if result:
                        return result
            raise RuntimeError("yt-dlp completed without producing a media file")
        except (asyncio.CancelledError, KeyboardInterrupt):
            raise
        except Exception as exc:
            last_exc = exc
            logger.warning("Quality attempt %d/%d failed: %s | %s", attempt, MAX_ATTEMPTS, classify_error(exc), _error_text(exc))
            if attempt < MAX_ATTEMPTS:
                time.sleep(RETRY_DELAY * attempt + random.uniform(0, 0.75))
    raise last_exc if last_exc else RuntimeError("Download failed")


async def robust_download_media(url: str, audio_only: bool = False, progress_hook=None):
    async with bot.GLOBAL_SEMAPHORE:
        return await asyncio.to_thread(robust_sync_download, url, audio_only, progress_hook)


# Replace only the download layer. The Telegram handlers, commands and UI in
# bot.py remain unchanged.
bot.sync_download = robust_sync_download
bot.sync_quality_download = robust_sync_quality_download
bot.download_media = robust_download_media


if __name__ == "__main__":
    bot.main()
