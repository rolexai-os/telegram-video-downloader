#!/usr/bin/env python3
"""Human-readable Telegram media downloader application layer."""
import asyncio
import logging
import os
import re
import shutil
import subprocess
import tempfile
import sqlite3
import socket
import time
import uuid
from pathlib import Path

import yt_dlp
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputFile, Update
from telegram.constants import ChatAction
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

load_dotenv()
BOT_TOKEN=os.getenv("BOT_TOKEN","").strip()
DOWNLOAD_DIR=Path(os.getenv("DOWNLOAD_DIR","downloads")); DOWNLOAD_DIR.mkdir(parents=True,exist_ok=True)
DB_FILE=Path(os.getenv("DB_FILE","bot.db"))
SERVER_KIND=os.getenv("SERVER_KIND","render" if os.getenv("RENDER_SERVICE_ID") else "local")
SERVER_NAME=os.getenv("SERVER_NAME","").strip()
SERVER_HOSTNAME=os.getenv("RENDER_EXTERNAL_HOSTNAME","").strip() or socket.gethostname()
SERVER_ID=os.getenv("SERVER_ID","").strip() or f"{SERVER_KIND}:{SERVER_HOSTNAME}"
SERVER_LABEL=SERVER_NAME or (f"Render / {os.getenv('RENDER_SERVICE_NAME', 'telegram-video-downloader')}" if SERVER_KIND=="render" else f"Local / {SERVER_HOSTNAME}")
LOG_URLS=os.getenv("LOG_URLS","1").lower() in {"1","true","yes","on"}
MAX_FILE_SIZE_MB=max(0,int(os.getenv("MAX_FILE_SIZE_MB","0"))); MAX_FILE_SIZE=MAX_FILE_SIZE_MB*1024*1024 if MAX_FILE_SIZE_MB else 0
TELEGRAM_UPLOAD_CHUNK_MB=max(5,int(os.getenv("TELEGRAM_UPLOAD_CHUNK_MB","45"))); TELEGRAM_UPLOAD_CHUNK_SIZE=TELEGRAM_UPLOAD_CHUNK_MB*1024*1024
STORAGE_QUOTA_GB=max(0,float(os.getenv("STORAGE_QUOTA_GB","0")))
KEEP_MEDIA=os.getenv("KEEP_MEDIA","0").lower() in {"1","true","yes","on"}
STORAGE_BACKEND=os.getenv("STORAGE_BACKEND","local").strip().lower()
MAX_CONCURRENT_DOWNLOADS=max(1,int(os.getenv("MAX_CONCURRENT_DOWNLOADS","2")))
MAX_LINKS_PER_MESSAGE=max(0,int(os.getenv("MAX_LINKS_PER_MESSAGE","0")))
MAX_QUEUE_PER_USER=max(0,int(os.getenv("MAX_QUEUE_PER_USER","0")))
RATE_LIMIT_SECONDS=max(0,float(os.getenv("RATE_LIMIT_SECONDS","2")))
PLAYLIST_MAX_ITEMS=max(1,int(os.getenv("PLAYLIST_MAX_ITEMS","10")))
PROGRESS_UPDATE_SECONDS=max(2,int(os.getenv("PROGRESS_UPDATE_SECONDS","3")))
BOT_OWNER_ID=int(os.getenv("BOT_OWNER_ID","0").strip() or "0")
ADMIN_USER_IDS={int(x.strip()) for x in os.getenv("ADMIN_USER_IDS","").split(",") if x.strip().isdigit()}
WEBHOOK_URL=os.getenv("WEBHOOK_URL","").strip() or os.getenv("RENDER_EXTERNAL_URL","").strip()
WEBHOOK_SECRET=os.getenv("WEBHOOK_SECRET","").strip(); PORT=int(os.getenv("PORT","10000"))

LOG_FILE=Path(os.getenv("APP_LOG_FILE","bot.log"))
logging.basicConfig(level=logging.INFO,format="%(asctime)s | %(levelname)s | %(message)s",handlers=[logging.StreamHandler(),logging.FileHandler(LOG_FILE,encoding="utf-8")])
logger=logging.getLogger("telegram-video-downloader")
GLOBAL_SEMAPHORE=asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS); JOBS={}; LAST_REQUEST={}; QUALITY_REQUESTS={}; LOCK=asyncio.Lock()
URL_RE=re.compile(r"https?://[^\s<>\"]+|www\.[^\s<>\"]+",re.I)
def is_youtube_url(url):
    try:
        from urllib.parse import urlparse
        host=urlparse(url).netloc.lower().split("@")[-1].split(":")[0]
        return host in {"youtube.com","www.youtube.com","m.youtube.com","music.youtube.com","youtu.be","www.youtu.be","youtube-nocookie.com","www.youtube-nocookie.com"} or host.endswith(".youtube.com")
    except Exception:
        return False

def is_disabled_url(url):
    return False

def ensure_supported_url(url):
    if "open.spotify.com/" in str(url).lower() or "play.spotify.com/" in str(url).lower():
        raise RuntimeError("Spotify downloads are disabled in this release. Send a supported direct media URL instead.")
    return None

def extract_message_urls(message):
    """Extract visible and Telegram-embedded URLs from text or media captions."""
    raw=message.text or message.caption or ""
    urls=[clean_url(x) for x in URL_RE.findall(raw)]
    entities=message.entities if message.text is not None else message.caption_entities
    for entity in entities or ():
        if entity.type == "text_link" and entity.url:
            urls.append(clean_url(entity.url))
        elif entity.type == "url":
            try:
                urls.append(clean_url(message.parse_entity(entity)))
            except (RuntimeError, AttributeError):
                pass
    seen=set(); result=[]
    for url in urls:
        if not url: continue
        if url.startswith("www."): url="https://"+url
        if url.startswith(("http://","https://")) and url not in seen:
            seen.add(url); result.append(url)
    return result

LANG={"en":"🎬 Social Media Downloader","ml":"🎬 സോഷ്യൽ മീഡിയ ഡൗൺലോഡർ","hi":"🎬 सोशल मीडिया डाउनलोडर","ta":"🎬 சமூக ஊடக பதிவிறக்கி"}


def db():
    c=sqlite3.connect(DB_FILE, timeout=30)
    c.execute("PRAGMA busy_timeout=30000"); c.execute("PRAGMA journal_mode=WAL")
    c.execute("CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY,username TEXT DEFAULT '',first_name TEXT DEFAULT '',last_name TEXT DEFAULT '',language TEXT DEFAULT 'en',quality TEXT DEFAULT 'best',audio INTEGER DEFAULT 0,captions INTEGER DEFAULT 0,created_at INTEGER,last_seen INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS history(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,url TEXT,title TEXT,status TEXT,size INTEGER DEFAULT 0,created_at INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS favorites(user_id INTEGER,url TEXT,title TEXT,created_at INTEGER,PRIMARY KEY(user_id,url))")
    c.execute("CREATE TABLE IF NOT EXISTS audit_logs(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,username TEXT DEFAULT '',event TEXT,url TEXT DEFAULT '',details TEXT DEFAULT '',server_id TEXT DEFAULT '',created_at INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS servers(server_id TEXT PRIMARY KEY,kind TEXT,label TEXT,hostname TEXT,pid INTEGER,started_at INTEGER,last_seen INTEGER,status TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS admins(user_id INTEGER PRIMARY KEY,added_by INTEGER DEFAULT 0,created_at INTEGER)")
    admin_count=c.execute("SELECT COUNT(*) FROM admins").fetchone()[0]
    if admin_count == 0:
        for admin_id in sorted(ADMIN_USER_IDS):
            c.execute("INSERT OR IGNORE INTO admins(user_id,added_by,created_at) VALUES(?,?,?)",(admin_id,0,int(time.time())))
    rows=c.execute("SELECT user_id FROM admins").fetchall()
    ADMIN_USER_IDS.clear(); ADMIN_USER_IDS.update(int(row[0]) for row in rows)
    if BOT_OWNER_ID > 0:
        c.execute("INSERT OR IGNORE INTO admins(user_id,added_by,created_at) VALUES(?,?,?)",(BOT_OWNER_ID,0,int(time.time())))
        c.commit(); ADMIN_USER_IDS.add(BOT_OWNER_ID)
    for column, definition in (("username","TEXT DEFAULT ''"),("first_name","TEXT DEFAULT ''"),("last_name","TEXT DEFAULT ''")):
        try: c.execute(f"ALTER TABLE users ADD COLUMN {column} {definition}")
        except sqlite3.OperationalError: pass
    c.commit(); return c


def is_owner(uid):
    return BOT_OWNER_ID > 0 and int(uid or 0) == BOT_OWNER_ID

def is_admin(uid):
    return int(uid or 0) in ADMIN_USER_IDS

def ensure_owner_is_admin():
    if BOT_OWNER_ID <= 0:
        return
    c=db()
    c.execute("INSERT OR IGNORE INTO admins(user_id,added_by,created_at) VALUES(?,?,?)",(BOT_OWNER_ID,0,int(time.time())))
    c.commit(); c.close()
    ADMIN_USER_IDS.add(BOT_OWNER_ID)

def admin_list():
    c=db(); rows=c.execute("SELECT user_id,added_by,created_at FROM admins ORDER BY user_id").fetchall(); c.close(); return rows

def add_admin(uid, added_by):
    uid=int(uid); c=db()
    c.execute("INSERT OR IGNORE INTO admins(user_id,added_by,created_at) VALUES(?,?,?)",(uid,int(added_by),int(time.time())))
    changed=c.total_changes; c.commit(); c.close(); ADMIN_USER_IDS.add(uid)
    return bool(changed)

def remove_admin(uid):
    uid=int(uid); c=db()
    count=c.execute("SELECT COUNT(*) FROM admins").fetchone()[0]
    if uid == BOT_OWNER_ID:
        c.close(); return False, "The bot owner cannot be removed."
    if count <= 1:
        c.close(); return False, "At least one admin must remain."
    changed=c.execute("DELETE FROM admins WHERE user_id=?",(uid,)).rowcount
    c.commit(); c.close()
    if changed:
        ADMIN_USER_IDS.discard(uid); return True, "Admin removed."
    return False, "That user is not an admin."

def touch(uid,user=None):
    c=db(); now=int(time.time())
    username=(getattr(user,"username","") or "") if user else ""
    first_name=(getattr(user,"first_name","") or "") if user else ""
    last_name=(getattr(user,"last_name","") or "") if user else ""
    c.execute("""INSERT INTO users(user_id,username,first_name,last_name,created_at,last_seen)
                 VALUES(?,?,?,?,?,?)
                 ON CONFLICT(user_id) DO UPDATE SET
                 username=CASE WHEN excluded.username<>'' THEN excluded.username ELSE users.username END,
                 first_name=CASE WHEN excluded.first_name<>'' THEN excluded.first_name ELSE users.first_name END,
                 last_name=CASE WHEN excluded.last_name<>'' THEN excluded.last_name ELSE users.last_name END,
                 last_seen=excluded.last_seen""",
              (uid,username,first_name,last_name,now,now)); c.commit(); c.close()


def audit_event(user,event,url="",details=""):
    if not user:return
    uid=getattr(user,"id",0) or 0
    username=getattr(user,"username","") or ""
    touch(uid,user)
    if not LOG_URLS:url=""
    try:
        c=db(); c.execute("INSERT INTO audit_logs(user_id,username,event,url,details,server_id,created_at) VALUES(?,?,?,?,?,?,?)",
                          (uid,username,event,url,details,SERVER_ID,int(time.time()))); c.commit(); c.close()
    except sqlite3.Error as exc:
        logger.warning("audit database write failed: %s", exc)


def server_heartbeat(status="online"):
    now=int(time.time()); started=int(os.getenv("SERVER_STARTED_AT",str(now)))
    os.environ.setdefault("SERVER_STARTED_AT",str(started))
    c=db(); c.execute("""INSERT INTO servers(server_id,kind,label,hostname,pid,started_at,last_seen,status)
                        VALUES(?,?,?,?,?,?,?,?)
                        ON CONFLICT(server_id) DO UPDATE SET
                        kind=excluded.kind,label=excluded.label,hostname=excluded.hostname,
                        pid=excluded.pid,last_seen=excluded.last_seen,status=excluded.status""",
                     (SERVER_ID,SERVER_KIND,SERVER_LABEL,SERVER_HOSTNAME,os.getpid(),started,now,status))
    c.commit(); c.close()


def touch_update(update):
    user=getattr(update,"effective_user",None)
    if not user:return
    touch(user.id,user)
    message=getattr(update,"effective_message",None)
    text_value=getattr(message,"text",None) or getattr(message,"caption",None) or ""
    urls=extract_message_urls(message) if message else []
    if urls:
        event="command" if text_value.lstrip().startswith("/") else "link_received"
        audit_event(user,event,urls[0] if len(urls)==1 else "",f"links={len(urls)}")
    elif getattr(update,"callback_query",None):
        audit_event(user,"button",details=f"callback={getattr(update.callback_query,'data','')[:120]}")
    else:
        audit_event(user,"message",details=f"type={type(update).__name__}")


def settings(uid):
    touch(uid); c=db(); r=c.execute("SELECT language,quality,audio,captions FROM users WHERE user_id=?",(uid,)).fetchone(); c.close(); return r or ("en","best",0,0)


def set_setting(uid,field,value):
    if field not in {"language","quality","audio","captions"}: return
    touch(uid); c=db(); c.execute(f"UPDATE users SET {field}=? WHERE user_id=?",(value,uid)); c.commit(); c.close()


def history(uid,url,title,status,size=0):
    c=db(); c.execute("INSERT INTO history(user_id,url,title,status,size,created_at) VALUES(?,?,?,?,?,?)",(uid,url,title,status,size,int(time.time()))); c.commit(); c.close()


def favorite(uid,url,title):
    c=db(); c.execute("INSERT OR REPLACE INTO favorites(user_id,url,title,created_at) VALUES(?,?,?,?)",(uid,url,title,int(time.time()))); c.commit(); c.close()


def clean_url(url): return url.rstrip(".,!?)]}>\"'")

def user_error_message(exc):
    """Return a safe, non-technical message for Telegram users.

    The complete exception is still logged by the caller. Authentication,
    HTTP, extractor and network details are intentionally hidden
    from the user instead of exposing raw yt-dlp output.
    """
    s=" ".join(str(exc).replace("\n"," ").split()).lower()
    if any(x in s for x in ("login", "sign in", "authentication", "requires authentication", "you need to log in")):
        return "⚠️ This link requires access/login and was skipped. The bot will not bypass authentication."
    if "403" in s or "forbidden" in s:
        return "⚠️ The source rejected this link, so it was skipped."
    if "429" in s or "rate limit" in s:
        return "⚠️ The source temporarily rate-limited this link. Please try again later."
    if "404" in s or "not found" in s:
        return "⚠️ This media is unavailable or no longer exists."
    if "unsupported url" in s:
        return "⚠️ This link is not supported."
    if "youtube support has been removed" in s:
        return "🚫 YouTube links are no longer supported by this bot."
    if "spotify download support is unavailable" in s:
        return "🚫 Spotify downloads are disabled in this release. Send a supported direct media URL instead."
    if "ffmpeg" in s:
        return "⚠️ The bot could not process this media."
    if any(x in s for x in ("timeout", "timed out", "temporary failure in name resolution", "name or service not known", "ssl", "tls")):
        return "⚠️ A temporary network problem prevented this download."
    if "above the configured" in s or ("file is " in s and "mb" in s):
        return "⚠️ This file is larger than the bot's upload limit."
    return "⚠️ This link could not be downloaded."

def size_text(n):
    if not n:return "unknown"
    for u in ("B","KB","MB","GB"):
        if n<1024:return f"{n:.1f} {u}"
        n/=1024
    return f"{n:.1f} TB"

def fmt(profile):
    if profile=="1080":return "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/bv*[height<=1080]+ba/b[height<=1080]/b"
    if profile=="720":return "bv*[height<=720][ext=mp4]+ba[ext=m4a]/bv*[height<=720]+ba/b[height<=720]/b"
    if profile=="480":return "bv*[height<=480][ext=mp4]+ba[ext=m4a]/bv*[height<=480]+ba/b[height<=480]/b"
    return "bv*[ext=mp4]+ba[ext=m4a]/bv*+ba/b[ext=mp4]/b"


def opts(template,audio=False,profile="best",captions=False,hook=None,playlist=False,url=""):
    o={"format":"bestaudio/best" if audio else fmt(profile),"outtmpl":template,"merge_output_format":"mp4","noplaylist":not playlist,"quiet":True,"no_warnings":False,"retries":5,"fragment_retries":5,"file_access_retries":3,"extractor_retries":3,"socket_timeout":30,"continuedl":True,"overwrites":False,"restrictfilenames":False,"windowsfilenames":True,"concurrent_fragment_downloads":2}
    if audio:o["postprocessors"]=[{"key":"FFmpegExtractAudio","preferredcodec":"mp3","preferredquality":"192"}]
    if captions:o.update(writesubtitles=True,writeautomaticsub=True,subtitleslangs=["all"],subtitlesformat="srt/vtt/best")
    if hook:o["progress_hooks"]=[hook]
    return o


def locate(ydl,info,audio=False):
    if not info:return None
    p=Path(ydl.prepare_filename(info)); candidates=[p]
    if audio:candidates += [p.with_suffix(".mp3"),p.with_suffix(".m4a")]
    candidates += sorted(DOWNLOAD_DIR.glob(f"{p.stem}.*"),key=lambda x:x.stat().st_mtime,reverse=True)
    return next((x for x in candidates if x.is_file() and x.stat().st_size),None)


def sync_download(url,audio=False,hook=None,profile="best",captions=False):
    ensure_supported_url(url)
    ext="mp3" if audio else "%(ext)s"; template=str(DOWNLOAD_DIR/f"%(title).180B [%(id)s].{ext}")
    with yt_dlp.YoutubeDL(opts(template,audio,profile,captions,hook,url=url)) as y:
        info=y.extract_info(url,download=True); info=next((x for x in info.get("entries",[]) if x),None) if info and info.get("entries") else info
        return locate(y,info,audio)


async def download(url,audio=False,hook=None,profile="best",captions=False):
    async with GLOBAL_SEMAPHORE:return await asyncio.to_thread(sync_download,url,audio,hook,profile,captions)


def main_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🎥 Download",callback_data="menu|download"),InlineKeyboardButton("⚙️ Settings",callback_data="menu|settings")],[InlineKeyboardButton("📚 History",callback_data="menu|history"),InlineKeyboardButton("⭐ Favorites",callback_data="menu|favorites")],[InlineKeyboardButton("📊 Status",callback_data="menu|status"),InlineKeyboardButton("❌ Cancel",callback_data="menu|cancel")]])


def quality_keyboard(token):
    return InlineKeyboardMarkup([[InlineKeyboardButton("🎥 Best",callback_data=f"q|best|{token}"),InlineKeyboardButton("📱 1080p",callback_data=f"q|1080|{token}")],[InlineKeyboardButton("📱 720p",callback_data=f"q|720|{token}"),InlineKeyboardButton("📱 480p",callback_data=f"q|480|{token}")],[InlineKeyboardButton("🎵 MP3",callback_data=f"q|mp3|{token}"),InlineKeyboardButton("💬 Captions",callback_data=f"q|subs|{token}")]])


async def start(update,context):
    uid=update.effective_user.id; lang=settings(uid)[0]
    await update.effective_message.reply_text(f"{LANG.get(lang,LANG['en'])}\n\nSend one or more supported social-media URLs. YouTube and Spotify downloads are disabled. Use /playlist <URL> for supported playlists.",reply_markup=main_keyboard())

async def help_cmd(update,context):
    await update.effective_message.reply_text(
        "📖 Commands\n"
        "/start — open bot menu\n/help — command help\n"
        "/quality <URL> — choose quality\n/mp3 <URL> — extract audio\n"
        "/subs <URL> — download with subtitles\n/playlist <URL> — playlist/batch for supported sources\n"
        "/analyze <URL> — inspect formats\n/status /queue /pause /resume /cancel\n"
        "/settings /history /favorites /stats /version /terms\n"
        "/admin or /panel — admin dashboard\n"
        "/cleanup /announce — admin tools\n\n"
        "Long videos have no application duration cap; media above Telegram's upload size is automatically split into parts."
    )

async def terms_cmd(update,context):
    await update.effective_message.reply_text("⚖️ Testing/Beta project. Download only content you own or are legally permitted to access. Do not bypass DRM, authentication, access controls, paywalls or platform rules. You are responsible for your use.")

async def status_cmd(update,context):
    uid=update.effective_user.id
    async with LOCK: own=len(JOBS.get(uid,set())); total=sum(len(x) for x in JOBS.values())
    await update.effective_message.reply_text(f"📊 Your jobs: {own}\nGlobal jobs: {total}\nConcurrent slots: {MAX_CONCURRENT_DOWNLOADS}")

async def cancel_cmd(update,context):
    uid=update.effective_user.id
    async with LOCK: jobs=list(JOBS.get(uid,set()))
    for t in jobs:t.cancel()
    await update.effective_message.reply_text(f"🛑 Cancellation requested for {len(jobs)} job(s).")

async def settings_cmd(update,context):
    uid=update.effective_user.id; lang,q,a,c=settings(uid); msg=update.effective_message
    await msg.reply_text(f"⚙️ Settings\nLanguage: {lang}\nQuality: {q}\nAudio default: {'ON' if a else 'OFF'}\nCaptions: {'ON' if c else 'OFF'}",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🇬🇧 English",callback_data="set|language|en"),InlineKeyboardButton("🇮🇳 മലയാളം",callback_data="set|language|ml")],[InlineKeyboardButton("🇮🇳 हिन्दी",callback_data="set|language|hi"),InlineKeyboardButton("🇮🇳 தமிழ்",callback_data="set|language|ta")],[InlineKeyboardButton("Best",callback_data="set|quality|best"),InlineKeyboardButton("1080p",callback_data="set|quality|1080"),InlineKeyboardButton("720p",callback_data="set|quality|720")],[InlineKeyboardButton("480p",callback_data="set|quality|480"),InlineKeyboardButton("🎵 Audio",callback_data="set|audio|toggle"),InlineKeyboardButton("💬 Captions",callback_data="set|captions|toggle")]]))

async def history_cmd(update,context):
    uid=update.effective_user.id;c=db(); rows=c.execute("SELECT title,url,status,size FROM history WHERE user_id=? ORDER BY id DESC LIMIT 10",(uid,)).fetchall();c.close()
    text="📚 History\n\n"+"\n".join(f"{i}. {r[0] or r[1]} — {r[2]} — {size_text(r[3])}" for i,r in enumerate(rows,1)) if rows else "📚 No download history yet."
    await update.effective_message.reply_text(text[:4000])

async def favorites_cmd(update,context):
    uid=update.effective_user.id;c=db(); rows=c.execute("SELECT title,url FROM favorites WHERE user_id=? ORDER BY created_at DESC LIMIT 20",(uid,)).fetchall();c.close()
    await update.effective_message.reply_text(("⭐ Favorites\n\n"+"\n".join(f"• {r[0] or r[1]}\n{r[1]}" for r in rows))[:4000] if rows else "⭐ No favorites yet.")

async def admin_cmd(update,context):
    uid=update.effective_user.id
    if not is_admin(uid):return await update.effective_message.reply_text("❌ Admin only.")
    c=db();users=c.execute("SELECT COUNT(*) FROM users").fetchone()[0];success=c.execute("SELECT COUNT(*) FROM history WHERE status='success'").fetchone()[0];failed=c.execute("SELECT COUNT(*) FROM history WHERE status='failed'").fetchone()[0];c.close();d=shutil.disk_usage(DOWNLOAD_DIR)
    await update.effective_message.reply_text(f"🛡️ Admin dashboard\n👥 Users: {users}\n✅ Downloads: {success}\n❌ Failed: {failed}\n💾 Free disk: {size_text(d.free)}\n🎞️ FFmpeg: {'OK' if shutil.which('ffmpeg') else 'MISSING'}\n📦 yt-dlp: {yt_dlp.version.__version__}")

async def rate_limit(uid):
    if RATE_LIMIT_SECONDS<=0:return False
    now=time.monotonic();old=LAST_REQUEST.get(uid,0)
    if now-old<RATE_LIMIT_SECONDS:return True
    LAST_REQUEST[uid]=now;return False

async def register(uid,t):
    async with LOCK:
        s=JOBS.setdefault(uid,set())
        if MAX_QUEUE_PER_USER and len(s)>=MAX_QUEUE_PER_USER:return False
        s.add(t);return True

async def unregister(uid,t):
    async with LOCK:
        s=JOBS.get(uid)
        if s:s.discard(t); JOBS.pop(uid,None) if not s else None


def progress_hook(loop,status_message,url):
    state={"last":0.0}
    def hook(info):
        if info.get("status")!="downloading":return
        now=time.monotonic()
        if now-state["last"]<PROGRESS_UPDATE_SECONDS:return
        state["last"]=now; text=f"⬇️ {info.get('_percent_str','?').strip()} • {info.get('_speed_str','?').strip()} • ETA {info.get('_eta_str','?').strip()}"
        async def edit():
            try:await status_message.edit_text(f"{text}\n🔗 {url[:120]}")
            except Exception:pass
        asyncio.run_coroutine_threadsafe(edit(),loop)
    return hook

async def _send_single_media(message, path, audio=False, caption=""):
    with path.open("rb") as fh:
        if audio:
            await message.reply_audio(audio=InputFile(fh,filename=path.name),caption=caption[:1024] if caption else None)
        else:
            await message.reply_video(video=InputFile(fh,filename=path.name),
                                      caption=caption[:1024] if caption else None,
                                      supports_streaming=True)


async def send_media(message, path, audio=False, caption=""):
    """Send large media by using normal Telegram upload or FFmpeg chunks."""
    if path.stat().st_size <= TELEGRAM_UPLOAD_CHUNK_SIZE:
        await _send_single_media(message,path,audio,caption)
        return 1
    if not shutil.which("ffmpeg"):
        raise RuntimeError(f"Media is {size_text(path.stat().st_size)}; FFmpeg is required to split large files.")
    suffix=".mp3" if audio else ".mp4"
    work=Path(tempfile.mkdtemp(prefix="tvd-parts-",dir=DOWNLOAD_DIR))
    pattern=str(work / ("part-%03d"+suffix))
    try:
        cmd=["ffmpeg","-hide_banner","-loglevel","error","-i",str(path),"-map","0","-c","copy",
             "-f","segment","-segment_time","600","-reset_timestamps","1",
             "-fs",str(TELEGRAM_UPLOAD_CHUNK_SIZE-1024*1024),pattern]
        proc=await asyncio.to_thread(subprocess.run,cmd,capture_output=True,text=True)
        parts=sorted(work.glob("part-*"+suffix))
        if proc.returncode!=0 or not parts:
            raise RuntimeError("FFmpeg could not split the large media file")
        for index,part in enumerate(parts,1):
            await _send_single_media(message,part,audio,f"{caption} • Part {index}/{len(parts)}")
        return len(parts)
    finally:
        shutil.rmtree(work,ignore_errors=True)


async def process_one(message,context,uid,url,audio=False,profile="best",captions=False):
    task=asyncio.current_task()
    if not await register(uid,task):await message.reply_text("❌ Your queue is full.");return
    status=await message.reply_text("⏳ Preparing download…");file_path=None
    try:
        loop=asyncio.get_running_loop();hook=progress_hook(loop,status,url)
        file_path=await download(url,audio,hook,profile,captions)
        if not file_path or not file_path.exists():raise RuntimeError("No media file was produced")
        n=file_path.stat().st_size
        if MAX_FILE_SIZE and n>MAX_FILE_SIZE:raise RuntimeError(f"File is {size_text(n)}, above the configured {MAX_FILE_SIZE_MB} MB limit")
        await status.edit_text("📤 Uploading…");await context.bot.send_chat_action(message.chat_id,ChatAction.UPLOAD_VIDEO)
        await send_media(message,file_path,audio,f"✅ {file_path.stem}")
        history(uid,url,file_path.stem,"success",n);favorite(uid,url,file_path.stem);audit_event(message.from_user,"download_success",url,file_path.stem)
        try:await status.delete()
        except Exception:pass
    except asyncio.CancelledError:
        history(uid,url,"","cancelled");audit_event(message.from_user,"download_cancelled",url)
        try:await status.edit_text("🛑 Job cancelled.")
        except Exception:pass
    except Exception as exc:
        history(uid,url,"","failed");audit_event(message.from_user,"download_failed",url,user_error_message(exc));logger.exception("download failed")
        try:await status.edit_text(user_error_message(exc))
        except Exception:pass
    finally:
        if file_path and file_path.exists() and not KEEP_MEDIA:
            try:file_path.unlink()
            except OSError:pass
        await unregister(uid,task)

async def inspect_formats(url):
    def run():
        o={"quiet":True,"no_warnings":True,"skip_download":True,"noplaylist":True,"socket_timeout":20}
        with yt_dlp.YoutubeDL(o) as y:return y.extract_info(url,download=False)
    return await asyncio.to_thread(run)

async def quality_cmd(update,context):
    uid=update.effective_user.id
    if await rate_limit(uid):return await update.effective_message.reply_text("⏱️ Please wait a moment.")
    urls=[clean_url(x) for x in URL_RE.findall(" ".join(context.args))]
    if not urls:return await update.effective_message.reply_text("Usage: /quality <URL>")
    token=uuid.uuid4().hex[:16];QUALITY_REQUESTS[token]=(uid,urls[0],time.time())
    try:
        info=await inspect_formats(urls[0]);title=info.get("title","") if info else ""
        heights=sorted({f.get("height") for f in info.get("formats",[]) if f.get("height")},reverse=True) if info else []
        sizes=[f.get("filesize") or f.get("filesize_approx") for f in info.get("formats",[]) if f.get("filesize") or f.get("filesize_approx")]
        extra=f"\n🎬 {title[:100]}\n📐 Available: {', '.join(str(x) for x in heights[:8])}p" if heights else ""
        if sizes:extra+=f"\n💾 Largest listed format: {size_text(max(sizes))}"
        await update.effective_message.reply_text("Choose a format:"+extra,reply_markup=quality_keyboard(token))
    except Exception as exc:
        logger.exception("format inspection failed")
        await update.effective_message.reply_text(user_error_message(exc))

async def quality_callback(update,context):
    q=update.callback_query;await q.answer();_,profile,token=q.data.split("|",2);item=QUALITY_REQUESTS.pop(token,None)
    if not item or item[0]!=q.from_user.id or time.time()-item[2]>900:return await q.edit_message_text("❌ Expired request.")
    uid,url,_=item;audio=profile=="mp3";captions=profile=="subs";chosen="best" if profile in {"mp3","subs"} else profile
    task=asyncio.current_task()
    if not await register(uid,task):return await q.edit_message_text("❌ Queue is full.")
    file_path=None
    try:
        await q.edit_message_text("⏳ Downloading selected format…");loop=asyncio.get_running_loop();hook=progress_hook(loop,q.message,url)
        file_path=await download(url,audio,hook,chosen,captions)
        if not file_path or not file_path.exists():raise RuntimeError("No media file was produced")
        n=file_path.stat().st_size
        if MAX_FILE_SIZE and n>MAX_FILE_SIZE:raise RuntimeError(f"File is {size_text(n)}, above the configured {MAX_FILE_SIZE_MB} MB limit")
        await q.edit_message_text("📤 Uploading…")
        await send_media(q.message,file_path,audio,f"✅ {file_path.stem}")
        history(uid,url,file_path.stem,"success",n);favorite(uid,url,file_path.stem);audit_event(q.from_user,"download_success",url,file_path.stem)
    except asyncio.CancelledError:history(uid,url,"","cancelled");audit_event(q.from_user,"download_cancelled",url);await q.edit_message_text("🛑 Cancelled.")
    except Exception as exc:
        history(uid,url,"","failed");audit_event(q.from_user,"download_failed",url,user_error_message(exc));logger.exception("quality download failed")
        await q.edit_message_text(user_error_message(exc))
    finally:
        if file_path and file_path.exists() and not KEEP_MEDIA:
            try:file_path.unlink()
            except OSError:pass
        await unregister(uid,task)

async def mp3_cmd(update,context):
    urls=[clean_url(x) for x in URL_RE.findall(" ".join(context.args))]
    if not urls:return await update.effective_message.reply_text("Usage: /mp3 <URL>")
    uid=update.effective_user.id
    for u in urls:asyncio.create_task(process_one(update.effective_message,context,uid,u,True))
    await update.effective_message.reply_text(f"🎵 Queued {len(urls)} MP3 job(s).")

async def subs_cmd(update,context):
    urls=[clean_url(x) for x in URL_RE.findall(" ".join(context.args))]
    if not urls:return await update.effective_message.reply_text("Usage: /subs <URL>")
    uid=update.effective_user.id
    for u in urls:asyncio.create_task(process_one(update.effective_message,context,uid,u,False,"best",True))
    await update.effective_message.reply_text(f"💬 Queued {len(urls)} caption-enabled job(s).")

async def playlist_cmd(update,context):
    urls=[clean_url(x) for x in URL_RE.findall(" ".join(context.args))]
    if not urls:return await update.effective_message.reply_text("Usage: /playlist <URL>")
    uid=update.effective_user.id;url=urls[0]
    try:
        ensure_supported_url(url)
        await update.effective_message.reply_text(f"📚 Reading playlist (max {PLAYLIST_MAX_ITEMS})…")
        def extract():
            with yt_dlp.YoutubeDL({"quiet":True,"no_warnings":True,"extract_flat":"in_playlist","playlistend":PLAYLIST_MAX_ITEMS,"noplaylist":False}) as y:return y.extract_info(url,download=False)
        info=await asyncio.to_thread(extract);entries=[x for x in (info.get("entries") or []) if x][:PLAYLIST_MAX_ITEMS]
        if not entries:raise RuntimeError("No entries found")
        for e in entries:
            u=e.get("webpage_url") or e.get("url")
            if u:asyncio.create_task(process_one(update.effective_message,context,uid,u))
        await update.effective_message.reply_text(f"📥 Queued {len(entries)} playlist item(s).")
    except Exception as exc:
        logger.exception("playlist extraction failed")
        await update.effective_message.reply_text(user_error_message(exc))

async def callback(update,context):
    q=update.callback_query;await q.answer();data=q.data
    if data.startswith("menu|"):
        a=data.split("|",1)[1]
        return await {"settings":settings_cmd,"history":history_cmd,"favorites":favorites_cmd,"status":status_cmd,"cancel":cancel_cmd}.get(a,lambda u,c:q.message.reply_text("Send a URL or use /quality <URL>."))(update,context)
    if data.startswith("set|"):
        _,field,value=data.split("|",2);uid=q.from_user.id
        if value=="toggle":
            s=settings(uid);value=not bool(s[2] if field=="audio" else s[3])
        set_setting(uid,field,value);await q.edit_message_text("✅ Setting updated.");return await settings_cmd(update,context)
    if data.startswith("q|"):return await quality_callback(update,context)


def main():
    if not BOT_TOKEN:raise SystemExit("BOT_TOKEN is not set")
    db()
    if not shutil.which("ffmpeg"):logger.warning("FFmpeg not found")
    app=Application.builder().token(BOT_TOKEN).build()
    for name,fn in {"start":start,"help":help_cmd,"terms":terms_cmd,"status":status_cmd,"cancel":cancel_cmd,"quality":quality_cmd,"mp3":mp3_cmd,"subs":subs_cmd,"playlist":playlist_cmd,"settings":settings_cmd,"history":history_cmd,"favorites":favorites_cmd,"admin":admin_cmd}.items():app.add_handler(CommandHandler(name,fn))
    app.add_handler(CallbackQueryHandler(callback,pattern=r"^(menu|set|q)\|"));app.add_handler(MessageHandler((filters.TEXT | filters.CAPTION) & ~filters.COMMAND,handle_message))
    if WEBHOOK_URL:app.run_webhook(listen="0.0.0.0",port=PORT,url_path="telegram",webhook_url=f"{WEBHOOK_URL.rstrip('/')}/telegram",secret_token=WEBHOOK_SECRET or None,drop_pending_updates=True,allowed_updates=Update.ALL_TYPES,max_connections=20)
    else:app.run_polling(allowed_updates=Update.ALL_TYPES,drop_pending_updates=True)

async def handle_message(update,context):
    m=update.effective_message;uid=update.effective_user.id
    if await rate_limit(uid):return await m.reply_text("⏱️ Please wait a moment.")
    urls=extract_message_urls(m)
    if not urls:return await m.reply_text("❌ Send one or more supported media URLs.")
    if MAX_LINKS_PER_MESSAGE and len(urls)>MAX_LINKS_PER_MESSAGE:return await m.reply_text(f"❌ Maximum {MAX_LINKS_PER_MESSAGE} links per message.")
    _,profile,audio,captions=settings(uid)
    for u in urls:asyncio.create_task(process_one(m,context,uid,u,bool(audio),profile,bool(captions)))
    await m.reply_text(f"📥 Queued {len(urls)} link(s). Use /status or /cancel.")

if __name__=="__main__":main()
