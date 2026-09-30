#!/usr/bin/env python3
"""Production runner with defensive yt-dlp error handling."""
import asyncio
import logging
import os
import random
import time
from pathlib import Path
import yt_dlp
import bot

logger = logging.getLogger("telegram-video-downloader.runner")
MAX_ATTEMPTS = max(1, int(os.getenv("YTDLP_MAX_ATTEMPTS", "3")))
RETRY_DELAY = max(0.5, float(os.getenv("YTDLP_RETRY_DELAY", "2")))
FORCE_IPV4 = os.getenv("YTDLP_FORCE_IPV4", "0").lower() in {"1","true","yes","on"}
USER_AGENT = os.getenv("YTDLP_USER_AGENT", "").strip()
DEFAULT_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"


def _error_text(exc): return " ".join(str(exc).replace("\n", " ").split())[:1000]

def classify_error(exc):
    text=_error_text(exc).lower()
    checks=[
        (("403","forbidden"),"HTTP 403 Forbidden: the source rejected the media request"),
        (("429","too many requests","rate limit"),"HTTP 429: the source rate-limited the request"),
        (("401","unauthorized"),"HTTP 401 Unauthorized: authentication may be required"),
        (("404","not found"),"HTTP 404: media was not found or is no longer available"),
        (("timed out","timeout"),"Network timeout while contacting the source"),
        (("name or service not known","temporary failure in name resolution"),"DNS/network resolution failed"),
        (("certificate","ssl","tls"),"TLS/SSL connection error"),
        (("ffmpeg",),"FFmpeg processing error"),
        (("unsupported url",),"This URL is not supported by yt-dlp"),
        (("login","sign in","authentication"),"The source requires authentication"),
    ]
    for needles,label in checks:
        if any(x in text for x in needles): return label
    return "Download failed"


def _base_opts(template, audio_only, progress_hook=None, attempt=1, profile="best", captions=False, playlist=False):
    opts={"format":"bestaudio/best" if audio_only else bot.format_for_quality(profile),"outtmpl":template,"merge_output_format":"mp4","noplaylist":not playlist,"quiet":True,"no_warnings":False,"retries":3,"fragment_retries":5,"file_access_retries":3,"extractor_retries":3,"socket_timeout":30,"connecttimeout":30,"continuedl":True,"overwrites":False,"restrictfilenames":False,"windowsfilenames":True,"concurrent_fragment_downloads":1,"http_chunk_size":10*1024*1024}
    if audio_only: opts["postprocessors"]=[{"key":"FFmpegExtractAudio","preferredcodec":"mp3","preferredquality":"192"}]
    if captions: opts.update({"writesubtitles":True,"writeautomaticsub":True,"subtitleslangs":["all"],"subtitlesformat":"srt/vtt/best"})
    if progress_hook: opts["progress_hooks"]=[progress_hook]
    if bot.COOKIES_FILE and Path(bot.COOKIES_FILE).is_file(): opts["cookiefile"]=bot.COOKIES_FILE
    if FORCE_IPV4 or attempt>=2: opts["source_address"]="0.0.0.0"
    ua=USER_AGENT or (DEFAULT_UA if attempt>=2 else "")
    if ua: opts["http_headers"]={"User-Agent":ua}
    return opts


def robust_sync_download(url, audio_only=False, progress_hook=None, profile="best", captions=False):
    suffix="mp3" if audio_only else "%(ext)s"
    template=str(bot.DOWNLOAD_DIR / f"%(title).180B [%(id)s].{suffix}")
    last=None
    for attempt in range(1,MAX_ATTEMPTS+1):
        try:
            opts=_base_opts(template,audio_only,progress_hook,attempt,profile,captions)
            logger.info("yt-dlp attempt %d/%d: %s",attempt,MAX_ATTEMPTS,url)
            with yt_dlp.YoutubeDL(opts) as ydl:
                info=ydl.extract_info(url,download=True)
                if info and info.get("entries"): info=next((x for x in info["entries"] if x),None)
                result=bot.locate_result(ydl,info,audio_only) if info else None
                if result:return result
                raise RuntimeError("yt-dlp completed without producing a media file")
        except (asyncio.CancelledError,KeyboardInterrupt): raise
        except Exception as exc:
            last=exc; logger.warning("Attempt %d/%d failed: %s | %s",attempt,MAX_ATTEMPTS,classify_error(exc),_error_text(exc))
            if attempt<MAX_ATTEMPTS: time.sleep(RETRY_DELAY*attempt+random.uniform(0,0.75))
    raise last if last else RuntimeError("Download failed")


def robust_sync_quality_download(url, profile, progress_hook=None, captions=False):
    return robust_sync_download(url,False,progress_hook,profile,captions)


async def robust_download_media(url, audio_only=False, progress_hook=None, profile="best", captions=False):
    async with bot.GLOBAL_SEMAPHORE:
        return await asyncio.to_thread(robust_sync_download,url,audio_only,progress_hook,profile,captions)


bot.sync_download=robust_sync_download
bot.sync_quality_download=robust_sync_quality_download
bot.download_media=robust_download_media

if __name__ == "__main__": bot.main()
