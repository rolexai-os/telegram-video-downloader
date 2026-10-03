#!/usr/bin/env python3
"""Telegram inline admin panel.

This panel is intentionally Telegram-native: no public admin HTTP endpoint is
exposed. It shows operational metadata, never cookie contents or secrets.
"""
import asyncio
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

def _keyboard():
    return bot.InlineKeyboardMarkup([
        [bot.InlineKeyboardButton("📊 Overview", callback_data="ap|overview"),
         bot.InlineKeyboardButton("👥 Users", callback_data="ap|users")],
        [bot.InlineKeyboardButton("⚙️ Jobs", callback_data="ap|jobs"),
         bot.InlineKeyboardButton("💾 Storage", callback_data="ap|storage")],
        [bot.InlineKeyboardButton("🍪 Cookies", callback_data="ap|cookies"),
         bot.InlineKeyboardButton("🧹 Cleanup", callback_data="ap|cleanup")],
        [bot.InlineKeyboardButton("📣 Broadcast help", callback_data="ap|broadcast"),
         bot.InlineKeyboardButton("🖥️ System", callback_data="ap|system")],
    ])

def _back():
    return bot.InlineKeyboardMarkup(
        [[bot.InlineKeyboardButton("⬅️ Admin panel", callback_data="ap|home")]]
    )

def _cookie_report():
    rows = []
    for platform in sorted(bot.PLATFORM_COOKIE_ENV):
        configured = os.getenv(bot.PLATFORM_COOKIE_ENV[platform], "").strip()
        candidates = []
        if configured:
            candidates.append(Path(configured))
        candidates.append(bot.COOKIES_DIR / f"{platform}.txt")
        if platform == "x":
            candidates.append(bot.COOKIES_DIR / "twitter.txt")
        if bot.COOKIES_FILE:
            candidates.append(Path(bot.COOKIES_FILE))
        p = next((x for x in candidates if x.is_file()), None)
        if p and p.is_file():
            rows.append(f"✅ {platform}: {p.name} ({_size(p.stat().st_size)})")
        else:
            rows.append(f"⚪ {platform}: not configured")
    return "\n".join(rows)

def _overview():
    c = bot.db()
    users = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total = c.execute("SELECT COUNT(*) FROM history").fetchone()[0]
    success = c.execute("SELECT COUNT(*) FROM history WHERE status='success'").fetchone()[0]
    failed = c.execute("SELECT COUNT(*) FROM history WHERE status='failed'").fetchone()[0]
    active = c.execute("SELECT COUNT(*) FROM announcements WHERE active=1").fetchone()[0] if _table_exists(c, "announcements") else 0
    c.close()
    disk = shutil.disk_usage(bot.DOWNLOAD_DIR)
    return (
        "🛡️ <b>Admin Control Panel</b>\n\n"
        f"👥 Users: <b>{users}</b>\n"
        f"📥 History: <b>{total}</b>\n"
        f"✅ Successful: <b>{success}</b>\n"
        f"❌ Failed: <b>{failed}</b>\n"
        f"📣 Saved announcements: <b>{active}</b>\n"
        f"📁 Downloads: <code>{bot.DOWNLOAD_DIR}</code>\n"
        f"💾 Free disk: <b>{_size(disk.free)}</b>\n"
        f"🎞️ FFmpeg: <b>{'OK' if shutil.which('ffmpeg') else 'MISSING'}</b>\n"
        f"📦 yt-dlp: <b>{bot.yt_dlp.version.__version__}</b>"
    )

def _table_exists(c, name):
    return c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None

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

    if action == "users":
        c = bot.db()
        rows = c.execute(
            "SELECT user_id,last_seen FROM users ORDER BY last_seen DESC LIMIT 12"
        ).fetchall()
        total = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        c.close()
        lines = [f"👥 <b>Users: {total}</b>", "", "Recent user IDs:"]
        lines += [f"• <code>{uid}</code> — {time.strftime('%Y-%m-%d %H:%M', time.localtime(ts or 0))}" for uid, ts in rows]
        return await q.edit_message_text("\n".join(lines), parse_mode="HTML", reply_markup=_back())

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
        text = (
            "💾 <b>Storage</b>\n\n"
            f"Download files: <b>{files}</b>\n"
            f"Download directory: <code>{bot.DOWNLOAD_DIR}</code>\n"
            f"Database: <b>{_size(db_size)}</b> — <code>{bot.DB_FILE}</code>\n"
            f"Cookie files: <b>{cookie_files}</b> — <code>{bot.COOKIES_DIR}</code>\n"
            f"Free: <b>{_size(d.free)}</b>\nUsed: <b>{_size(d.used)}</b>"
        )
        return await q.edit_message_text(text, parse_mode="HTML", reply_markup=_back())

    if action == "cookies":
        text = (
            "🍪 <b>Authorized cookie status</b>\n\n"
            + _cookie_report()
            + "\n\n🔐 Cookie contents are never displayed or uploaded by this panel."
            + f"\n📁 Default folder: <code>{bot.COOKIES_DIR}</code>"
        )
        return await q.edit_message_text(text[:3900], parse_mode="HTML", reply_markup=_back())

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
            parse_mode="HTML", reply_markup=_back()
        )

    if action == "broadcast":
        return await q.edit_message_text(
            "📣 <b>Broadcast</b>\n\nUse <code>/announce your message</code> to send an announcement to registered users.\n\n"
            "The broadcast is stored in the announcements table for audit/history.",
            parse_mode="HTML", reply_markup=_back()
        )

    if action == "system":
        version = Path("VERSION").read_text().strip() if Path("VERSION").exists() else "dev"
        return await q.edit_message_text(
            "🖥️ <b>System</b>\n\n"
            f"Release: <b>v{version}</b>\n"
            f"Python: <code>{os.sys.version.split()[0]}</code>\n"
            f"PID: <code>{os.getpid()}</code>\n"
            f"Platform: <code>{os.name}</code>\n"
            f"Cookie directory: <code>{bot.COOKIES_DIR}</code>\n"
            f"Download directory: <code>{bot.DOWNLOAD_DIR}</code>\n"
            f"Max file size: <b>{bot.MAX_FILE_SIZE_MB} MB</b>\n"
            f"Rate limit: <b>{bot.RATE_LIMIT_SECONDS}s</b>",
            parse_mode="HTML", reply_markup=_back()
        )

    await q.edit_message_text(_overview(), parse_mode="HTML", reply_markup=_keyboard())
