#!/usr/bin/env python3
"""Telegram-native admin control panel with user, audit and server visibility."""
import html
import os
import shutil
import time
from pathlib import Path

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
         bot.InlineKeyboardButton("👥 Users", callback_data="ap|users")],
        [bot.InlineKeyboardButton("📝 Audit logs", callback_data="ap|logs"),
         bot.InlineKeyboardButton("🖥️ Servers", callback_data="ap|servers")],
        [bot.InlineKeyboardButton("📄 System log", callback_data="ap|systemlog"),
        [bot.InlineKeyboardButton("⚙️ Jobs", callback_data="ap|jobs"),
         bot.InlineKeyboardButton("💾 Storage", callback_data="ap|storage")],
        [bot.InlineKeyboardButton("🍪 Cookies", callback_data="ap|cookies"),
         bot.InlineKeyboardButton("🧹 Cleanup", callback_data="ap|cleanup")],
        [bot.InlineKeyboardButton("📣 Broadcast help", callback_data="ap|broadcast"),
         bot.InlineKeyboardButton("🔄 Refresh", callback_data="ap|home")],
    ])

def _back():
    return bot.InlineKeyboardMarkup([[bot.InlineKeyboardButton("⬅️ Admin panel", callback_data="ap|home")]])

def _cookie_report():
    rows = []
    for platform in sorted(bot.PLATFORM_COOKIE_ENV):
        configured = os.getenv(bot.PLATFORM_COOKIE_ENV[platform], "").strip()
        candidates = [Path(configured)] if configured else []
        candidates.append(bot.COOKIES_DIR / f"{platform}.txt")
        if platform == "x":
            candidates.append(bot.COOKIES_DIR / "twitter.txt")
        if bot.COOKIES_FILE:
            candidates.append(Path(bot.COOKIES_FILE))
        p = next((x for x in candidates if x.is_file()), None)
        rows.append(f"✅ {platform}: {p.name} ({_size(p.stat().st_size)})" if p else f"⚪ {platform}: not configured")
    return "\n".join(rows)

def _overview():
    c = bot.db()
    users = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total = c.execute("SELECT COUNT(*) FROM history").fetchone()[0]
    success = c.execute("SELECT COUNT(*) FROM history WHERE status='success'").fetchone()[0]
    failed = c.execute("SELECT COUNT(*) FROM history WHERE status='failed'").fetchone()[0]
    events = c.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0]
    online = c.execute("SELECT COUNT(*) FROM servers WHERE status='online' AND last_seen>=?", (int(time.time())-90,)).fetchone()[0]
    c.close()
    disk = shutil.disk_usage(bot.DOWNLOAD_DIR)
    return (
        "🛡️ <b>Admin Control Panel</b>\n\n"
        f"👥 Users: <b>{users}</b>\n"
        f"📝 Audit events: <b>{events}</b>\n"
        f"📥 History: <b>{total}</b>\n"
        f"✅ Successful: <b>{success}</b>\n"
        f"❌ Failed: <b>{failed}</b>\n"
        f"🖥️ Servers online: <b>{online}</b>\n"
        f"📍 This server: <b>{_esc(bot.SERVER_LABEL)}</b>\n"
        f"💾 Free disk: <b>{_size(disk.free)}</b>\n"
        f"🎞️ FFmpeg: <b>{'OK' if shutil.which('ffmpeg') else 'MISSING'}</b>\n"
        f"📦 yt-dlp: <b>{bot.yt_dlp.version.__version__}</b>"
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

    if action == "home" or action == "overview":
        return await q.edit_message_text(_overview(), parse_mode="HTML", reply_markup=_keyboard() if action=="home" else _back())

    if action == "users":
        c = bot.db()
        rows = c.execute("""SELECT u.user_id,u.username,u.first_name,u.last_name,u.last_seen,
                            (SELECT COUNT(*) FROM audit_logs a WHERE a.user_id=u.user_id AND a.event='message' AND a.url<>'') AS links
                            FROM users u ORDER BY u.last_seen DESC LIMIT 20""").fetchall()
        total = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        c.close()
        lines = [f"👥 <b>Users: {total}</b>", "", "<b>ID | username | name | last seen | links</b>"]
        for uid, username, first, last, seen, links in rows:
            name = " ".join(x for x in (first, last) if x) or "—"
            handle = f"@{username}" if username else "—"
            lines.append(f"• <code>{uid}</code> | {_esc(handle)} | {_esc(name[:24])} | {_when(seen)} | {links}")
        return await q.edit_message_text("\n".join(lines)[:3900], parse_mode="HTML", reply_markup=_back())

    if action == "logs":
        c = bot.db()
        rows = c.execute("""SELECT created_at,user_id,username,event,url,details,server_id
                            FROM audit_logs ORDER BY id DESC LIMIT 25""").fetchall()
        c.close()
        lines = ["📝 <b>Recent audit logs</b>", "", "Time | user | event | link/server"]
        for ts, uid, username, event, url, details, server_id in rows:
            link = url if url else details
            if link and len(link) > 90: link = link[:87] + "..."
            who = f"@{username}" if username else str(uid)
            lines.append(f"• {_when(ts)} | <code>{_esc(who)}</code> | <b>{_esc(event)}</b> | server={_esc(server_id)} | {_esc(link)}")
        if not rows: lines.append("No audit events yet.")
        return await q.edit_message_text("\n".join(lines)[:3900], parse_mode="HTML", reply_markup=_back())

    if action == "systemlog":
        log_path = bot.LOG_FILE
        if not log_path.exists():
            return await q.edit_message_text("📄 <b>System log</b>\n\nNo log file has been created yet.", parse_mode="HTML", reply_markup=_back())
        try:
            lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-35:]
        except OSError as exc:
            return await q.edit_message_text(f"❌ Cannot read log: {_esc(exc)}", reply_markup=_back())
        text = "📄 <b>Recent system log</b>\n\n<pre>" + _esc("\n".join(lines)) + "</pre>"
        return await q.edit_message_text(text[-3900:], parse_mode="HTML", reply_markup=_back())

    if action == "servers":
        c = bot.db()
        rows = c.execute("SELECT server_id,kind,label,hostname,pid,started_at,last_seen,status FROM servers ORDER BY last_seen DESC").fetchall()
        c.close()
        now = int(time.time())
        lines = ["🖥️ <b>Bot servers</b>", "", f"Current: <b>{_esc(bot.SERVER_LABEL)}</b>"]
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
        top = sorted(per_user.items(), key=lambda x: x[1], reverse=True)[:10]
        lines = [f"⚙️ <b>Active jobs: {total}</b>", f"🚦 Global concurrency: {bot.MAX_CONCURRENT_DOWNLOADS}", ""]
        lines += [f"• <code>{uid}</code>: {count} job(s)" for uid, count in top] or ["No active jobs."]
        return await q.edit_message_text("\n".join(lines), parse_mode="HTML", reply_markup=_back())

    if action == "storage":
        d = shutil.disk_usage(bot.DOWNLOAD_DIR)
        db_size = bot.DB_FILE.stat().st_size if bot.DB_FILE.exists() else 0
        files = sum(1 for p in bot.DOWNLOAD_DIR.iterdir() if p.is_file()) if bot.DOWNLOAD_DIR.exists() else 0
        cookie_files = sum(1 for p in bot.COOKIES_DIR.glob("*.txt")) if bot.COOKIES_DIR.exists() else 0
        text = ("💾 <b>Storage</b>\n\n"
                f"Download files: <b>{files}</b>\nDownload directory: <code>{_esc(bot.DOWNLOAD_DIR)}</code>\n"
                f"Database: <b>{_size(db_size)}</b> — <code>{_esc(bot.DB_FILE)}</code>\n"
                f"Cookie files: <b>{cookie_files}</b> — <code>{_esc(bot.COOKIES_DIR)}</code>\n"
                f"Free: <b>{_size(d.free)}</b>\nUsed: <b>{_size(d.used)}</b>")
        return await q.edit_message_text(text, parse_mode="HTML", reply_markup=_back())

    if action == "cookies":
        text = ("🍪 <b>Authorized cookie status</b>\n\n" + _cookie_report() +
                "\n\n🔐 Cookie contents are never displayed or uploaded by this panel." +
                f"\n📁 Default folder: <code>{_esc(bot.COOKIES_DIR)}</code>")
        return await q.edit_message_text(text[:3900], parse_mode="HTML", reply_markup=_back())

    if action == "cleanup":
        removed = 0
        cutoff = time.time() - 3600
        bot.DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        for p in bot.DOWNLOAD_DIR.iterdir():
            try:
                if p.is_file() and p.stat().st_mtime < cutoff:
                    p.unlink(); removed += 1
            except OSError:
                pass
        return await q.edit_message_text(f"🧹 <b>Cleanup complete</b>\nRemoved stale files: <b>{removed}</b>\nAge threshold: 1 hour.", parse_mode="HTML", reply_markup=_back())

    if action == "broadcast":
        return await q.edit_message_text("📣 <b>Broadcast</b>\n\nUse <code>/announce your message</code>. Broadcasts are stored for audit/history.", parse_mode="HTML", reply_markup=_back())

    await q.edit_message_text(_overview(), parse_mode="HTML", reply_markup=_keyboard())
