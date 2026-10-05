#!/usr/bin/env python3
"""Advanced Telegram-native admin control panel.

The panel is intentionally Telegram-only: no public admin HTTP endpoint,
and no credential or session data is ever accepted or displayed.
"""
import html
import platform
import shutil
import sys
import time

import bot

PANEL_PATTERN = r"^ap\|"

def _admin(uid):
    return uid in bot.ADMIN_USER_IDS

def _size(n):
    return bot.size_text(n)

def _esc(value):
    return html.escape(str(value or ""))

def _when(ts):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts or 0))

def _keyboard():
    return bot.InlineKeyboardMarkup([
        [bot.InlineKeyboardButton("📊 Overview", callback_data="ap|overview"),
         bot.InlineKeyboardButton("📈 Analytics", callback_data="ap|analytics")],
        [bot.InlineKeyboardButton("👥 Users", callback_data="ap|users"),
         bot.InlineKeyboardButton("📥 History", callback_data="ap|history")],
        [bot.InlineKeyboardButton("📝 Audit logs", callback_data="ap|logs"),
         bot.InlineKeyboardButton("🖥️ Servers", callback_data="ap|servers")],
        [bot.InlineKeyboardButton("⚙️ Jobs", callback_data="ap|jobs"),
         bot.InlineKeyboardButton("💾 Storage", callback_data="ap|storage")],
        [bot.InlineKeyboardButton("🩺 Health", callback_data="ap|health"),
         bot.InlineKeyboardButton("🔐 Privacy", callback_data="ap|privacy")],
        [bot.InlineKeyboardButton("👑 Admins", callback_data="ap|admins"),
         bot.InlineKeyboardButton("➕ Add admin", callback_data="ap|adminhelp")],
        [bot.InlineKeyboardButton("🔧 Runtime", callback_data="ap|runtime"),
         bot.InlineKeyboardButton("📄 System log", callback_data="ap|systemlog")],
        [bot.InlineKeyboardButton("🧹 Cleanup", callback_data="ap|cleanup"),
         bot.InlineKeyboardButton("📣 Broadcast", callback_data="ap|broadcast")],
        [bot.InlineKeyboardButton("🔄 Refresh", callback_data="ap|home")],
    ])

def _back():
    return bot.InlineKeyboardMarkup([[bot.InlineKeyboardButton("⬅️ Admin panel", callback_data="ap|home")]])

def _overview():
    c = bot.db()
    users = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total = c.execute("SELECT COUNT(*) FROM history").fetchone()[0]
    success = c.execute("SELECT COUNT(*) FROM history WHERE status='success'").fetchone()[0]
    failed = c.execute("SELECT COUNT(*) FROM history WHERE status='failed'").fetchone()[0]
    events = c.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0]
    online = c.execute("SELECT COUNT(*) FROM servers WHERE status='online' AND last_seen>=?", (int(time.time())-90,)).fetchone()[0]
    announcements = c.execute("SELECT COUNT(*) FROM announcements").fetchone()[0]
    c.close()
    disk = shutil.disk_usage(bot.DOWNLOAD_DIR)
    return (
        "🛡️ <b>Advanced Admin Control Panel</b>\n\n"
        f"👥 Users: <b>{users}</b>\n"
        f"📝 Audit events: <b>{events}</b>\n"
        f"📥 Download history: <b>{total}</b>\n"
        f"✅ Successful: <b>{success}</b>\n"
        f"❌ Failed: <b>{failed}</b>\n"
        f"📣 Announcements: <b>{announcements}</b>\n"
        f"🖥️ Servers online: <b>{online}</b>\n"
        f"📍 Server: <b>{_esc(bot.SERVER_LABEL)}</b>\n"
        f"💾 Free disk: <b>{_size(disk.free)}</b>\n"
        f"🎞️ FFmpeg: <b>{'OK' if shutil.which('ffmpeg') else 'MISSING'}</b>\n"
        f"📦 yt-dlp: <b>{bot.yt_dlp.version.__version__}</b>\n"
        f"🤖 Release: <b>{_esc(getattr(__import__('runner'), 'FEATURE_VERSION', 'unknown'))}</b>"
    )

async def panel_cmd(update, context):
    if not _admin(update.effective_user.id):
        return await update.effective_message.reply_text("❌ Admin only.")
    await update.effective_message.reply_text(_overview(), parse_mode="HTML", reply_markup=_keyboard())

async def panel_callback(update, context):
    q = update.callback_query
    if not _admin(q.from_user.id):
        await q.answer("Admin only.", show_alert=True)
        return
    await q.answer()
    action = q.data.split("|", 1)[1]

    if action == "home":
        return await q.edit_message_text(_overview(), parse_mode="HTML", reply_markup=_keyboard())

    if action == "overview":
        return await q.edit_message_text(_overview(), parse_mode="HTML", reply_markup=_back())

    if action == "analytics":
        c = bot.db()
        rows = c.execute("SELECT status, COUNT(*) FROM history GROUP BY status").fetchall()
        platform_rows = c.execute(
            "SELECT CASE WHEN instr(url,'instagram.com')>0 THEN 'Instagram' "
            ""
            "WHEN instr(url,'tiktok.com')>0 THEN 'TikTok' "
            "WHEN instr(url,'x.com')>0 OR instr(url,'twitter.com')>0 THEN 'X/Twitter' "
            "WHEN instr(url,'facebook.com')>0 OR instr(url,'fb.watch')>0 THEN 'Facebook' "
            "ELSE 'Other' END, COUNT(*) FROM history GROUP BY 1 ORDER BY 2 DESC LIMIT 10"
        ).fetchall()
        total_bytes = c.execute("SELECT COALESCE(SUM(size),0) FROM history WHERE status='success'").fetchone()[0]
        c.close()
        lines = ["📈 <b>Download Analytics</b>", "", "<b>Outcomes</b>"]
        lines += [f"• {_esc(status)}: {count}" for status, count in rows] or ["• No downloads yet"]
        lines += ["", f"📦 Successful data: <b>{_size(total_bytes)}</b>", "", "<b>Platforms</b>"]
        lines += [f"• {_esc(name)}: {count}" for name, count in platform_rows] or ["• No platform data yet"]
        return await q.edit_message_text("\n".join(lines)[:3900], parse_mode="HTML", reply_markup=_back())

    if action == "users":
        c = bot.db()
        rows = c.execute("""SELECT u.user_id,u.username,u.first_name,u.last_name,u.last_seen,
                            (SELECT COUNT(*) FROM audit_logs a WHERE a.user_id=u.user_id AND a.event IN ('link_received','command') AND a.url<>'') AS links,
                            (SELECT COUNT(*) FROM history h WHERE h.user_id=u.user_id AND h.status='success') AS success
                            FROM users u ORDER BY u.last_seen DESC LIMIT 20""").fetchall()
        total = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        c.close()
        lines = [f"👥 <b>Users: {total}</b>", "", "<b>ID | username | last seen | links | success</b>"]
        for uid, username, first, last, seen, links, success in rows:
            handle = f"@{username}" if username else ((" ".join(x for x in (first,last) if x))[:18] or "—")
            lines.append(f"• <code>{uid}</code> | {_esc(handle)} | {_when(seen)} | {links} | {success}")
        return await q.edit_message_text("\n".join(lines)[:3900], parse_mode="HTML", reply_markup=_back())

    if action == "history":
        c = bot.db()
        rows = c.execute("SELECT created_at,user_id,title,status,size,url FROM history ORDER BY id DESC LIMIT 20").fetchall()
        c.close()
        lines = ["📥 <b>Recent download history</b>", ""]
        for ts, uid, title, status, size, url in rows:
            icon = "✅" if status == "success" else "❌"
            lines.append(f"{icon} {_when(ts)} | <code>{uid}</code> | {_esc((title or 'unknown')[:45])} | {_size(size)}")
        if not rows: lines.append("No download history yet.")
        return await q.edit_message_text("\n".join(lines)[:3900], parse_mode="HTML", reply_markup=_back())

    if action == "logs":
        c = bot.db()
        rows = c.execute("""SELECT created_at,user_id,username,event,url,details,server_id
                            FROM audit_logs ORDER BY id DESC LIMIT 25""").fetchall()
        c.close()
        lines = ["📝 <b>Recent audit logs</b>", ""]
        for ts, uid, username, event, url, details, server_id in rows:
            value = url if url else details
            value = (value[:87] + "...") if value and len(value) > 90 else value
            who = f"@{username}" if username else str(uid)
            lines.append(f"• {_when(ts)} | <code>{_esc(who)}</code> | <b>{_esc(event)}</b> | {_esc(value)}")
        if not rows: lines.append("No audit events yet.")
        return await q.edit_message_text("\n".join(lines)[:3900], parse_mode="HTML", reply_markup=_back())

    if action == "servers":
        c = bot.db()
        rows = c.execute("SELECT server_id,kind,label,hostname,pid,started_at,last_seen,status FROM servers ORDER BY last_seen DESC").fetchall()
        c.close()
        now = int(time.time())
        lines = ["🖥️ <b>Bot Servers</b>", "", f"Current: <b>{_esc(bot.SERVER_LABEL)}</b>"]
        for sid, kind, label, hostname, pid, started, seen, status in rows:
            live = status == "online" and seen >= now - 90
            state = "🟢 ONLINE" if live else "⚪ OFFLINE"
            lines.append(f"• {state} <b>{_esc(label)}</b>\n  kind={_esc(kind)} host={_esc(hostname)} pid={pid} last={_when(seen)}")
        if not rows: lines.append("No heartbeat records yet.")
        return await q.edit_message_text("\n".join(lines)[:3900], parse_mode="HTML", reply_markup=_back())

    if action == "jobs":
        async with bot.LOCK:
            per_user = {uid: len(jobs) for uid, jobs in bot.JOBS.items() if jobs}
            total = sum(per_user.values())
        top = sorted(per_user.items(), key=lambda x: x[1], reverse=True)[:15]
        lines = [f"⚙️ <b>Active jobs: {total}</b>", f"🚦 Global concurrency: {bot.MAX_CONCURRENT_DOWNLOADS}", f"👤 Paused users: {len(getattr(__import__('runner'), 'PAUSED_USERS', set()))}", ""]
        lines += [f"• <code>{uid}</code>: {count} job(s)" for uid, count in top] or ["No active jobs."]
        return await q.edit_message_text("\n".join(lines), parse_mode="HTML", reply_markup=_back())

    if action == "storage":
        d = shutil.disk_usage(bot.DOWNLOAD_DIR)
        db_size = bot.DB_FILE.stat().st_size if bot.DB_FILE.exists() else 0
        files = sum(1 for p in bot.DOWNLOAD_DIR.iterdir() if p.is_file()) if bot.DOWNLOAD_DIR.exists() else 0
        text = ("💾 <b>Storage</b>\n\n"
                f"Download files: <b>{files}</b>\nDirectory: <code>{_esc(bot.DOWNLOAD_DIR)}</code>\n"
                f"Database: <b>{_size(db_size)}</b> — <code>{_esc(bot.DB_FILE)}</code>\n"

                f"Free: <b>{_size(d.free)}</b>\nUsed: <b>{_size(d.used)}</b>\n"
                f"App quota: <b>{'unlimited' if bot.STORAGE_QUOTA_GB == 0 else str(bot.STORAGE_QUOTA_GB) + ' GB'}</b>\n"
                f"Retention: <b>{'kept' if bot.KEEP_MEDIA else 'delivery-only'}</b>\nBackend: <b>{_esc(bot.STORAGE_BACKEND)}</b>")
        return await q.edit_message_text(text, parse_mode="HTML", reply_markup=_back())

    if action == "admins":
        rows=bot.admin_list()
        lines=[f"👑 <b>Administrators: {len(rows)}</b>",""]
        lines += [f"• <code>{uid}</code>" for uid,_,_ in rows]
        lines.append("")
        lines.append("Use /adminadd <Telegram ID> or /adminremove <Telegram ID>.")
        return await q.edit_message_text("\n".join(lines),parse_mode="HTML",reply_markup=_back())

    if action == "adminhelp":
        return await q.edit_message_text(
            "👑 <b>Admin Manager</b>\n\n"
            "There is no fixed admin limit. Administrators are stored persistently in SQLite.\n\n"
            "➕ Add: <code>/adminadd 123456789</code>\n"
            "➖ Remove: <code>/adminremove 123456789</code>\n"
            "📋 List: <code>/admins</code>\n\n"
            "The last administrator cannot be removed.",
            parse_mode="HTML",reply_markup=_back())

    if action == "privacy":
        text = ("🔐 <b>Privacy / Credential Policy</b>\n\n"
                "Cookie and browser-session support has been removed.\n"
                "No credential file, browser profile, session token, or imported login state is read by the downloader.\n\n"
                "Authentication-required media is skipped rather than using stored sessions.")
        return await q.edit_message_text(text, parse_mode="HTML", reply_markup=_back())

    if action == "health":
        c = bot.db()
        db_ok = True
        try:
            c.execute("SELECT 1").fetchone()
            history_count = c.execute("SELECT COUNT(*) FROM history").fetchone()[0]
            c.close()
        except Exception:
            db_ok = False
            history_count = 0
        checks = [
            ("SQLite", db_ok),
            ("FFmpeg", shutil.which("ffmpeg") is not None),
            ("Download directory", bot.DOWNLOAD_DIR.exists()),
            ("BOT_TOKEN configured", bool(bot.BOT_TOKEN)),
            ("yt-dlp", bool(getattr(bot.yt_dlp, "version", None))),
        ]
        lines = ["🩺 <b>System Health</b>", ""]
        lines += [f"{'🟢' if ok else '🔴'} {name}" for name, ok in checks]
        lines += ["", f"History rows: <b>{history_count}</b>", f"PID: <code>{os.getpid()}</code>"]
        return await q.edit_message_text("\n".join(lines), parse_mode="HTML", reply_markup=_back())

    if action == "runtime":
        import runner
        text = ("🔧 <b>Runtime Configuration</b>\n\n"
                f"Python: <b>{_esc(sys.version.split()[0])}</b>\n"
                f"Platform: <b>{_esc(platform.platform())}</b>\n"
                f"Release: <b>{_esc(runner.FEATURE_VERSION)}</b>\n"
                f"Server kind: <b>{_esc(bot.SERVER_KIND)}</b>\n"
                f"Concurrency: <b>{bot.MAX_CONCURRENT_DOWNLOADS}</b>\n"
                f"Rate limit: <b>{bot.RATE_LIMIT_SECONDS}s</b>\n"
                f"Playlist max: <b>{bot.PLAYLIST_MAX_ITEMS}</b>\n"
                f"Telegram chunk: <b>{bot.TELEGRAM_UPLOAD_CHUNK_MB} MB</b>\n"
                f"JS runtime: <b>{_esc(bot.YTDLP_JS_RUNTIME or 'disabled')}</b>\n"
                f"Storage backend: <b>{_esc(bot.STORAGE_BACKEND)}</b>\n"
                "🔐 Secrets are intentionally omitted.")
        return await q.edit_message_text(text, parse_mode="HTML", reply_markup=_back())

    if action == "systemlog":
        log_path = bot.LOG_FILE
        if not log_path.exists():
            return await q.edit_message_text("📄 <b>System Log</b>\n\nNo log file has been created yet.", parse_mode="HTML", reply_markup=_back())
        try:
            lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-35:]
        except OSError as exc:
            return await q.edit_message_text(f"❌ Cannot read log: {_esc(exc)}", reply_markup=_back())
        text = "📄 <b>Recent System Log</b>\n\n<pre>" + _esc("\n".join(lines)) + "</pre>"
        return await q.edit_message_text(text[-3900:], parse_mode="HTML", reply_markup=_back())

    if action == "cleanup":
        removed = 0
        cutoff = time.time() - 3600
        bot.DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        for p in bot.DOWNLOAD_DIR.iterdir():
            try:
                if p.is_file() and p.stat().st_mtime < cutoff:
                    p.unlink()
                    removed += 1
            except OSError:
                pass
        return await q.edit_message_text(
            f"🧹 <b>Cleanup complete</b>\nRemoved stale files: <b>{removed}</b>\nAge threshold: 1 hour.",
            parse_mode="HTML", reply_markup=_back())

    if action == "broadcast":
        return await q.edit_message_text(
            "📣 <b>Broadcast Center</b>\n\n"
            "Use <code>/announce your message</code> to send an announcement to registered users.\n\n"
            "The broadcast is recorded in the announcements table and delivery failures are ignored safely.",
            parse_mode="HTML", reply_markup=_back())

    return await q.edit_message_text(_overview(), parse_mode="HTML", reply_markup=_keyboard())
