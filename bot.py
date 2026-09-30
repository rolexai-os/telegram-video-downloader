#!/usr/bin/env python3
"""Telegram media downloader bot.

The application layer owns Telegram UI, user settings/history and job
management. The production runner may replace the download functions with a
more defensive network layer at import time.
"""
import asyncio
import json
import logging
import os
import re
import shutil
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Optional

import yt_dlp
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputFile, Update
from telegram.constants import ChatAction
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", "downloads"))
DB_FILE = Path(os.getenv("DB_FILE", "bot.db"))
MAX_FILE_SIZE_MB = max(1, int(os.getenv("MAX_FILE_SIZE_MB", "49")))
MAX_FILE_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024
MAX_CONCURRENT_DOWNLOADS = max(1, int(os.getenv("MAX_CONCURRENT_DOWNLOADS", "2")))
MAX_LINKS_PER_MESSAGE = max(0, int(os.getenv("MAX_LINKS_PER_MESSAGE", "0")))
MAX_QUEUE_PER_USER = max(0, int(os.getenv("MAX_QUEUE_PER_USER", "0")))
RATE_LIMIT_SECONDS = max(0, float(os.getenv("RATE_LIMIT_SECONDS", "2")))
PLAYLIST_MAX_ITEMS = max(1, int(os.getenv("PLAYLIST_MAX_ITEMS", "10")))
PROGRESS_UPDATE_SECONDS = max(2, int(os.getenv("PROGRESS_UPDATE_SECONDS", "3")))
ADMIN_USER_IDS = {int(x.strip()) for x in os.getenv("ADMIN_USER_IDS", "").split(",") if x.strip().isdigit()}
COOKIES_FILE = os.getenv("COOKIES_FILE", "").strip()
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip() or os.getenv("RENDER_EXTERNAL_URL", "").strip()
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()
PORT = int(os.getenv("PORT", "10000"))

DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
DB_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("telegram-video-downloader")

GLOBAL_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)
URL_REGEX = re.compile(r"https?://[^\s<>\"]+", re.IGNORECASE)
USER_JOBS: dict[int, set[asyncio.Task]] = {}
LAST_REQUEST: dict[int, float] = {}
QUALITY_REQUESTS: dict[str, dict] = {}
JOB_LOCK = asyncio.Lock()

LANG = {
    "en": {"welcome": "🎬 Social Media Downloader", "choose": "Choose an option:", "settings": "⚙️ Settings", "history": "📚 History", "favorites": "⭐ Favorites"},
    "ml": {"welcome": "🎬 സോഷ്യൽ മീഡിയ ഡൗൺലോഡർ", "choose": "ഒരു ഓപ്ഷൻ തിരഞ്ഞെടുക്കുക:", "settings": "⚙️ ക്രമീകരണങ്ങൾ", "history": "📚 ചരിത്രം", "favorites": "⭐ പ്രിയപ്പെട്ടവ"},
    "hi": {"welcome": "🎬 सोशल मीडिया डाउनलोडर", "choose": "एक विकल्प चुनें:", "settings": "⚙️ सेटिंग्स", "history": "📚 इतिहास", "favorites": "⭐ पसंदीदा"},
    "ta": {"welcome": "🎬 சமூக ஊடக பதிவிறக்கி", "choose": "ஒரு விருப்பத்தைத் தேர்ந்தெடுக்கவும்:", "settings": "⚙️ அமைப்புகள்", "history": "📚 வரலாறு", "favorites": "⭐ பிடித்தவை"},
}


def db():
    con = sqlite3.connect(DB_FILE)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, language TEXT NOT NULL DEFAULT 'en', quality TEXT NOT NULL DEFAULT 'best', audio INTEGER NOT NULL DEFAULT 0, captions INTEGER NOT NULL DEFAULT 0, created_at INTEGER NOT NULL, last_seen INTEGER NOT NULL)")
    con.execute("CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, url TEXT NOT NULL, title TEXT, status TEXT NOT NULL, size INTEGER DEFAULT 0, created_at INTEGER NOT NULL)")
    con.execute("CREATE TABLE IF NOT EXISTS favorites (user_id INTEGER NOT NULL, url TEXT NOT NULL, title TEXT, created_at INTEGER NOT NULL, PRIMARY KEY(user_id,url))")
    con.commit()
    return con


def touch_user(user_id: int):
    now = int(time.time())
    con = db()
    con.execute("INSERT INTO users(user_id,created_at,last_seen) VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET last_seen=excluded.last_seen", (user_id, now, now))
    con.commit(); con.close()


def get_settings(user_id: int):
    touch_user(user_id)
    con = db(); row = con.execute("SELECT language,quality,audio,captions FROM users WHERE user_id=?", (user_id,)).fetchone(); con.close()
    return row or ("en", "best", 0, 0)


def set_setting(user_id: int, field: str, value):
    allowed = {"language", "quality", "audio", "captions"}
    if field not in allowed: return
    touch_user(user_id)
    con = db(); con.execute(f"UPDATE users SET {field}=? WHERE user_id=?", (value, user_id)); con.commit(); con.close()


def add_history(user_id, url, title, status, size=0):
    con = db(); con.execute("INSERT INTO history(user_id,url,title,status,size,created_at) VALUES(?,?,?,?,?,?)", (user_id,url,title,status,size,int(time.time()))); con.commit(); con.close()


def add_favorite(user_id, url, title=""):
    con = db(); con.execute("INSERT OR REPLACE INTO favorites(user_id,url,title,created_at) VALUES(?,?,?,?)", (user_id,url,title,int(time.time()))); con.commit(); con.close()


def clean_url(url: str) -> str:
    return url.rstrip(".,!?)]}>\"'")


def human_size(value: int) -> str:
    if not value: return "unknown"
    units = ["B", "KB", "MB", "GB"]
    n = float(value)
    for unit in units:
        if n < 1024: return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def progress_text(info: dict) -> str:
    if info.get("status") == "downloading":
        return f"⬇️ {info.get('_percent_str','0%').strip()} • {info.get('_speed_str','?').strip()} • ETA {info.get('_eta_str','?').strip()}"
    if info.get("status") == "finished": return "🔄 Download complete, processing…"
    return "⏳ Processing…"


def format_for_quality(profile: str) -> str:
    if profile == "1080": return "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/bv*[height<=1080]+ba/b[height<=1080]/b"
    if profile == "720": return "bv*[height<=720][ext=mp4]+ba[ext=m4a]/bv*[height<=720]+ba/b[height<=720]/b"
    if profile == "480": return "bv*[height<=480][ext=mp4]+ba[ext=m4a]/bv*[height<=480]+ba/b[height<=480]/b"
    return "bv*[ext=mp4]+ba[ext=m4a]/bv*+ba/b[ext=mp4]/b"


def build_opts(template: str, audio_only=False, progress_hook=None, profile="best", captions=False, playlist=False):
    opts = {"format": "bestaudio/best" if audio_only else format_for_quality(profile), "outtmpl": template, "merge_output_format": "mp4", "noplaylist": not playlist, "quiet": True, "no_warnings": False, "retries": 5, "fragment_retries": 5, "file_access_retries": 3, "extractor_retries": 3, "socket_timeout": 30, "connecttimeout": 30, "continuedl": True, "overwrites": False, "restrictfilenames": False, "windowsfilenames": True, "concurrent_fragment_downloads": 2}
    if audio_only: opts["postprocessors"] = [{"key":"FFmpegExtractAudio","preferredcodec":"mp3","preferredquality":"192"}]
    if captions:
        opts.update({"writesubtitles": True, "writeautomaticsub": True, "subtitleslangs": ["all"], "subtitlesformat": "srt/vtt/best"})
    if progress_hook: opts["progress_hooks"] = [progress_hook]
    if COOKIES_FILE and Path(COOKIES_FILE).is_file(): opts["cookiefile"] = COOKIES_FILE
    return opts


def locate_result(ydl, info, audio_only=False):
    if not info: return None
    requested = Path(ydl.prepare_filename(info)); candidates = [requested]
    if audio_only: candidates += [requested.with_suffix(".mp3"), requested.with_suffix(".m4a")]
    candidates += sorted(DOWNLOAD_DIR.glob(f"{requested.stem}.*"), key=lambda p: p.stat().st_mtime, reverse=True)
    return next((p for p in candidates if p.is_file() and p.stat().st_size > 0), None)


def sync_download(url, audio_only=False, progress_hook=None, profile="best", captions=False):
    suffix = "mp3" if audio_only else "%(ext)s"
    template = str(DOWNLOAD_DIR / f"%(title).180B [%(id)s].{suffix}")
    with yt_dlp.YoutubeDL(build_opts(template, audio_only, progress_hook, profile, captions)) as ydl:
        info = ydl.extract_info(url, download=True)
        if info and info.get("entries"): info = next((x for x in info["entries"] if x), None)
        return locate_result(ydl, info, audio_only)


async def download_media(url, audio_only=False, progress_hook=None, profile="best", captions=False):
    async with GLOBAL_SEMAPHORE:
        return await asyncio.to_thread(sync_download, url, audio_only, progress_hook, profile, captions)


def is_admin(uid): return uid in ADMIN_USER_IDS


async def register_job(uid, task):
    async with JOB_LOCK:
        jobs = USER_JOBS.setdefault(uid, set())
        if MAX_QUEUE_PER_USER and len(jobs) >= MAX_QUEUE_PER_USER: return False
        jobs.add(task); return True


async def unregister_job(uid, task):
    async with JOB_LOCK:
        jobs = USER_JOBS.get(uid)
        if jobs:
            jobs.discard(task)
            if not jobs: USER_JOBS.pop(uid, None)


async def rate_limited(uid):
    if RATE_LIMIT_SECONDS <= 0: return False
    now=time.monotonic(); previous=LAST_REQUEST.get(uid,0)
    if now-previous < RATE_LIMIT_SECONDS: return True
    LAST_REQUEST[uid]=now; return False


def main_keyboard(uid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎥 Download", callback_data="menu|download"), InlineKeyboardButton("⚙️ Settings", callback_data="menu|settings")],
        [InlineKeyboardButton("📚 History", callback_data="menu|history"), InlineKeyboardButton("⭐ Favorites", callback_data="menu|favorites")],
        [InlineKeyboardButton("❌ Cancel jobs", callback_data="menu|cancel"), InlineKeyboardButton("📊 Status", callback_data="menu|status")],
    ])


def quality_keyboard(token):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎥 Best", callback_data=f"q|best|{token}"), InlineKeyboardButton("📱 1080p", callback_data=f"q|1080|{token}")],
        [InlineKeyboardButton("📱 720p", callback_data=f"q|720|{token}"), InlineKeyboardButton("📱 480p", callback_data=f"q|480|{token}")],
        [InlineKeyboardButton("🎵 MP3", callback_data=f"q|mp3|{token}"), InlineKeyboardButton("💬 Captions", callback_data=f"q|subs|{token}")],
    ])


async def start(update, context):
    uid=update.effective_user.id; touch_user(uid); lang, *_=get_settings(uid)
    await update.message.reply_text(f"{LANG.get(lang,LANG['en'])['welcome']}\n\nSend a video URL, multiple URLs, or use /quality <URL>.\n\nYou can also use the buttons below.", reply_markup=main_keyboard(uid))


async def help_cmd(update, context):
    await update.message.reply_text("📖 Commands\n\n/start — main menu\n/help — help\n/quality <URL> — interactive formats\n/mp3 <URL> — audio\n/subs <URL> — subtitles\n/playlist <URL> — authorized playlist batch\n/settings — preferences\n/history — recent downloads\n/favorites — saved URLs\n/status — active jobs\n/cancel — cancel jobs\n/terms — beta/legal notice\n/admin — admin dashboard")


async def terms_cmd(update, context):
    await update.message.reply_text("⚖️ Testing/Beta project. Download only content you own or are legally permitted to access/download. Do not bypass DRM, authentication, access controls, paywalls or platform rules. You are responsible for your use of the bot.")


async def status_cmd(update, context):
    uid=update.effective_user.id
    async with JOB_LOCK: count=len(USER_JOBS.get(uid,set())); total=sum(len(v) for v in USER_JOBS.values())
    await update.message.reply_text(f"📊 Your active jobs: {count}\nGlobal active jobs: {total}\nConcurrent slots: {MAX_CONCURRENT_DOWNLOADS}\nQueue limit: {'unlimited' if not MAX_QUEUE_PER_USER else MAX_QUEUE_PER_USER}")


async def cancel_cmd(update, context):
    uid=update.effective_user.id
    async with JOB_LOCK: jobs=list(USER_JOBS.get(uid,set()))
    for task in jobs: task.cancel()
    await update.message.reply_text(f"🛑 Cancellation requested for {len(jobs)} job(s).")


async def settings_cmd(update, context):
    uid=update.effective_user.id; lang,quality,audio,captions=get_settings(uid)
    await update.message.reply_text(f"⚙️ Settings\nLanguage: {lang}\nQuality: {quality}\nAudio default: {'ON' if audio else 'OFF'}\nCaptions: {'ON' if captions else 'OFF'}", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("🇬🇧 English",callback_data="set|lang|en"),InlineKeyboardButton("🇮🇳 മലയാളം",callback_data="set|lang|ml")],
        [InlineKeyboardButton("🇮🇳 हिन्दी",callback_data="set|lang|hi"),InlineKeyboardButton("🇮🇳 தமிழ்",callback_data="set|lang|ta")],
        [InlineKeyboardButton("Best",callback_data="set|quality|best"),InlineKeyboardButton("1080p",callback_data="set|quality|1080"),InlineKeyboardButton("720p",callback_data="set|quality|720")],
        [InlineKeyboardButton("480p",callback_data="set|quality|480"),InlineKeyboardButton("🎵 Audio",callback_data="set|audio|toggle"),InlineKeyboardButton("💬 Captions",callback_data="set|captions|toggle")],
    ]))


async def history_cmd(update, context):
    uid=update.effective_user.id; con=db(); rows=con.execute("SELECT title,url,status,size FROM history WHERE user_id=? ORDER BY id DESC LIMIT 10",(uid,)).fetchall(); con.close()
    if not rows: await update.message.reply_text("📚 No download history yet."); return
    text="📚 Recent downloads\n\n"+"\n".join(f"{i}. {r[0] or r[1]} — {r[2]} — {human_size(r[3])}" for i,r in enumerate(rows,1))
    await update.message.reply_text(text[:4000])


async def favorites_cmd(update, context):
    uid=update.effective_user.id; con=db(); rows=con.execute("SELECT title,url FROM favorites WHERE user_id=? ORDER BY created_at DESC LIMIT 20",(uid,)).fetchall(); con.close()
    if not rows: await update.message.reply_text("⭐ No favorites yet."); return
    await update.message.reply_text("⭐ Favorites\n\n"+"\n".join(f"• {r[0] or r[1]}\n{r[1]}" for r in rows)[:4000])


async def admin_cmd(update, context):
    uid=update.effective_user.id
    if not is_admin(uid): await update.message.reply_text("❌ Admin only."); return
    con=db(); users=con.execute("SELECT COUNT(*) FROM users").fetchone()[0]; downloads=con.execute("SELECT COUNT(*) FROM history WHERE status='success'").fetchone()[0]; failures=con.execute("SELECT COUNT(*) FROM history WHERE status='failed'").fetchone()[0]; con.close()
    disk=shutil.disk_usage(DOWNLOAD_DIR)
    await update.message.reply_text(f"🛡️ Admin dashboard\n👥 Users: {users}\n✅ Downloads: {downloads}\n❌ Failures: {failures}\n💾 Disk free: {human_size(disk.free)}\n🧠 Python: {shutil.which('python') or 'unknown'}\n🎞️ FFmpeg: {'available' if shutil.which('ffmpeg') else 'missing'}\n📦 yt-dlp: {yt_dlp.version.__version__}")


async def quality_cmd(update, context):
    uid=update.effective_user.id
    if await rate_limited(uid): await update.message.reply_text("⏱️ Please wait a moment."); return
    urls=[clean_url(u) for u in URL_REGEX.findall(" ".join(context.args))]
    if not urls: await update.message.reply_text("Usage: /quality <URL>"); return
    token=uuid.uuid4().hex[:16]; QUALITY_REQUESTS[token]={"uid":uid,"url":urls[0],"created":time.time()}
    await update.message.reply_text("Choose quality or captions:",reply_markup=quality_keyboard(token))


async def inspect_formats(url):
    def run():
        opts={"quiet":True,"no_warnings":True,"skip_download":True,"noplaylist":True,"socket_timeout":20}
        if COOKIES_FILE and Path(COOKIES_FILE).is_file(): opts["cookiefile"]=COOKIES_FILE
        with yt_dlp.YoutubeDL(opts) as ydl: return ydl.extract_info(url,download=False)
    return await asyncio.to_thread(run)


async def quality_callback(update, context):
    q=update.callback_query; await q.answer(); parts=q.data.split("|"); profile=parts[1]; token=parts[2]
    item=QUALITY_REQUESTS.pop(token,None)
    if not item or item["uid"]!=q.from_user.id or time.time()-item["created"]>900: await q.edit_message_text("❌ Expired quality request."); return
    url=item["url"]
    if profile=="inspect": return
    await q.edit_message_text("⏳ Preparing download…")
    task=asyncio.current_task(); uid=q.from_user.id
    if not await register_job(uid,task): await q.edit_message_text("❌ Queue full."); return
    file_path=None
    try:
        _,quality,audio,captions=get_settings(uid); captions = captions or profile=="subs"; audio_only=profile=="mp3" or bool(audio and profile=="best")
        if profile=="subs": audio_only=False
        progress={"last":0.0}
        def hook(info):
            if time.monotonic()-progress["last"]>=PROGRESS_UPDATE_SECONDS:
                progress["last"]=time.monotonic(); logger.info("%s | %s",url,progress_text(info))
        # Give users real format information before the transfer.
        info=await inspect_formats(url)
        title=info.get("title",url) if info else url
        if profile not in {"subs","mp3"} and info:
            available=sorted({f.get("height") for f in info.get("formats",[]) if f.get("height")}, reverse=True)
            if profile.isdigit() and not any(h and h>=int(profile) for h in available): profile="best"
        await q.edit_message_text(f"⬇️ Downloading {title[:80]}…")
        async with GLOBAL_SEMAPHORE:
            file_path=await asyncio.to_thread(sync_download,url,audio_only,hook,profile if profile in {"best","1080","720","480"} else "best",captions)
        if not file_path or not file_path.exists(): raise RuntimeError("No media file was produced")
        size=file_path.stat().st_size
        if size>MAX_FILE_SIZE: raise RuntimeError(f"File is {human_size(size)}, above {MAX_FILE_SIZE_MB} MB")
        add_history(uid,url,title,"success",size); add_favorite(uid,url,title)
        await q.edit_message_text("📤 Uploading…")
        with file_path.open("rb") as fh:
            if audio_only: await q.message.reply_audio(audio=InputFile(fh,filename=file_path.name),title=title[:64])
            else: await q.message.reply_video(video=InputFile(fh,filename=file_path.name),caption=f"✅ {title}"[:1024],supports_streaming=True)
        await q.message.reply_text("⭐ Saved to your history/favorites. Use /settings to change defaults.")
    except asyncio.CancelledError: add_history(uid,url,"","cancelled"); await q.edit_message_text("🛑 Job cancelled.")
    except Exception as exc: add_history(uid,url,"","failed"); logger.exception("quality job failed"); await q.edit_message_text(f"❌ {str(exc).replace(chr(10),' ')[:500]}")
    finally:
        if file_path and file_path.exists():
            try:file_path.unlink()
            except OSError:pass
        await unregister_job(uid,task)


async def process_one(message, context, uid, url, audio_only=False, profile="best", captions=False):
    task=asyncio.current_task()
    if not await register_job(uid,task): await message.reply_text("❌ Your queue is full."); return
    status=await message.reply_text("⏳ Downloading…"); file_path=None
    try:
        progress={"last":0.0}
        def hook(info):
            now=time.monotonic()
            if now-progress["last"]>=PROGRESS_UPDATE_SECONDS: progress["last"]=now; logger.info("%s | %s",url,progress_text(info))
        file_path=await download_media(url,audio_only,hook,profile,captions)
        if not file_path or not file_path.exists(): raise RuntimeError("No media file was produced")
        size=file_path.stat().st_size
        if size>MAX_FILE_SIZE: raise RuntimeError(f"File is {human_size(size)}, above {MAX_FILE_SIZE_MB} MB")
        await status.edit_text("📤 Uploading…"); await context.bot.send_chat_action(message.chat_id,ChatAction.UPLOAD_VIDEO)
        with file_path.open("rb") as fh:
            if audio_only: await message.reply_audio(audio=InputFile(fh,filename=file_path.name))
            else: await message.reply_video(video=InputFile(fh,filename=file_path.name),caption=f"✅ {file_path.name}"[:1024],supports_streaming=True)
        add_history(uid,url,file_path.stem,"success",size); add_favorite(uid,url,file_path.stem); await status.delete()
    except asyncio.CancelledError:
        add_history(uid,url,"","cancelled")
        try: await status.edit_text("🛑 Job cancelled.")
        except Exception: pass
    except yt_dlp.utils.DownloadError as exc:
        add_history(uid,url,"","failed"); logger.exception("yt-dlp error"); await status.edit_text(f"❌ Download failed: {str(exc).replace(chr(10),' ')[:500]}")
    except Exception as exc:
        add_history(uid,url,"","failed"); logger.exception("download error"); await status.edit_text(f"❌ {str(exc)[:500]}")
    finally:
        if file_path and file_path.exists():
            try:file_path.unlink()
            except OSError:pass
        await unregister_job(uid,task)


async def handle_message(update, context):
    message=update.message
    if not message or not message.text:return
    uid=update.effective_user.id; touch_user(uid)
    if await rate_limited(uid): await message.reply_text("⏱️ Please wait a moment before starting another request."); return
    urls=[clean_url(u) for u in URL_REGEX.findall(message.text)]
    if not urls: await message.reply_text("❌ Send one or more supported media URLs."); return
    if MAX_LINKS_PER_MESSAGE and len(urls)>MAX_LINKS_PER_MESSAGE: await message.reply_text(f"❌ Maximum {MAX_LINKS_PER_MESSAGE} links per message."); return
    _,quality,audio,captions=get_settings(uid)
    tasks=[asyncio.create_task(process_one(message,context,uid,u,bool(audio),quality,captions)) for u in urls]
    await message.reply_text(f"📥 Queued {len(tasks)} link(s). Use /status or /cancel.")


async def mp3_cmd(update, context):
    uid=update.effective_user.id
    if await rate_limited(uid): await update.message.reply_text("⏱️ Please wait a moment."); return
    urls=[clean_url(u) for u in URL_REGEX.findall(" ".join(context.args))]
    if not urls: await update.message.reply_text("Usage: /mp3 <URL>"); return
    for u in urls: asyncio.create_task(process_one(update.message,context,uid,u,True,"best",False))
    await update.message.reply_text(f"🎵 Queued {len(urls)} MP3 job(s).")


async def subs_cmd(update, context):
    uid=update.effective_user.id
    urls=[clean_url(u) for u in URL_REGEX.findall(" ".join(context.args))]
    if not urls: await update.message.reply_text("Usage: /subs <URL>"); return
    for u in urls: asyncio.create_task(process_one(update.message,context,uid,u,False,"best",True))
    await update.message.reply_text(f"💬 Queued {len(urls)} caption-enabled job(s).")


async def playlist_cmd(update, context):
    uid=update.effective_user.id
    urls=[clean_url(u) for u in URL_REGEX.findall(" ".join(context.args))]
    if not urls: await update.message.reply_text("Usage: /playlist <URL>"); return
    url=urls[0]
    await update.message.reply_text(f"📚 Inspecting playlist (maximum {PLAYLIST_MAX_ITEMS} items)…")
    try:
        def extract():
            opts={"quiet":True,"no_warnings":True,"extract_flat":"in_playlist","playlistend":PLAYLIST_MAX_ITEMS,"noplaylist":False}
            with yt_dlp.YoutubeDL(opts) as ydl:return ydl.extract_info(url,download=False)
        info=await asyncio.to_thread(extract); entries=[e for e in (info.get("entries") or []) if e][:PLAYLIST_MAX_ITEMS]
        if not entries: raise RuntimeError("No playlist entries found")
        await update.message.reply_text(f"📚 Found {len(entries)} item(s). Starting batch…")
        for e in entries:
            u=e.get("webpage_url") or e.get("url")
            if u: asyncio.create_task(process_one(update.message,context,uid,u,False,"best",False))
    except Exception as exc: await update.message.reply_text(f"❌ Playlist error: {str(exc)[:500]}")


async def callback(update, context):
    q=update.callback_query; await q.answer(); data=q.data
    if data.startswith("menu|"):
        action=data.split("|",1)[1]
        if action=="settings": await settings_cmd(update,context)
        elif action=="history": await history_cmd(update,context)
        elif action=="favorites": await favorites_cmd(update,context)
        elif action=="status": await status_cmd(update,context)
        elif action=="cancel": await cancel_cmd(update,context)
        elif action=="download": await q.message.reply_text("Send a media URL, or use /quality <URL> for format selection.")
    elif data.startswith("set|"):
        _,field,value=data.split("|",2); uid=q.from_user.id
        if value=="toggle": value=0 if get_settings(uid)[3 if field=="captions" else 2] else 1
        set_setting(uid,field,value); await q.edit_message_text("✅ Setting updated."); await settings_cmd(update,context)
    elif data.startswith("q|"): await quality_callback(update,context)


def main():
    if not BOT_TOKEN: raise SystemExit("BOT_TOKEN is not set. Configure it in .env or your hosting provider.")
    if shutil.which("ffmpeg") is None: logger.warning("ffmpeg was not found; MP3/merging may fail")
    db()
    app=Application.builder().token(BOT_TOKEN).build()
    for command,handler in [("start",start),("help",help_cmd),("terms",terms_cmd),("status",status_cmd),("cancel",cancel_cmd),("mp3",mp3_cmd),("subs",subs_cmd),("playlist",playlist_cmd),("quality",quality_cmd),("settings",settings_cmd),("history",history_cmd),("favorites",favorites_cmd),("admin",admin_cmd)]: app.add_handler(CommandHandler(command,handler))
    app.add_handler(CallbackQueryHandler(callback,pattern=r"^(menu|set|q)\|"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,handle_message))
    if WEBHOOK_URL:
        app.run_webhook(listen="0.0.0.0",port=PORT,url_path="telegram",webhook_url=f"{WEBHOOK_URL.rstrip('/')}/telegram",allowed_updates=Update.ALL_TYPES,drop_pending_updates=True,secret_token=WEBHOOK_SECRET or None,max_connections=20)
    else: app.run_polling(allowed_updates=Update.ALL_TYPES,drop_pending_updates=True)


if __name__ == "__main__": main()
