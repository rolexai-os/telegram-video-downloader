# Telegram Video Downloader

## v1.14.0 advanced admin control panel

The Telegram-native admin panel has been restored and expanded. Admins listed in `ADMIN_USER_IDS` can use `/admin` or `/panel` to access:

- 📊 Overview: users, downloads, success/failure totals, audit events, announcements, server status, disk, FFmpeg and yt-dlp.
- 📈 Analytics: outcome totals, successful data volume and top detected platforms.
- 👥 Users: recent users, usernames, last-seen time, link activity and successful downloads.
- 📥 History: recent download history with status and media size.
- 📝 Audit logs: recent user/action/server activity without exposing secrets.
- 🖥️ Servers: local/Render heartbeat and process visibility.
- ⚙️ Jobs: active jobs, global concurrency and paused-user count.
- 💾 Storage: download/database locations, file counts, disk usage, quota and retention mode.
- 🔐 Privacy: credential-free downloader status; session sessions are not supported.
- 🩺 Health: SQLite, FFmpeg, directories, token configuration and yt-dlp checks.
- 🔧 Runtime: safe non-secret Python, platform, release and downloader configuration.
- 📄 System log: recent application log output.
- 🧹 Cleanup: removes stale downloaded files older than one hour.
- 📣 Broadcast Center: guided `/announce` workflow with announcement history.
- 🔄 Refresh: reloads the live dashboard.

The panel remains Telegram-only and admin-ID protected. It does not expose a public admin HTTP endpoint or provide authentication/DRM bypass features.

# Telegram Video Downloader

## v1.11.3 automatic link detection

- Sending a normal URL directly to the bot automatically queues the download; no command is required.
- Telegram clickable text links (`TEXT_LINK`) are detected even when the URL is hidden behind formatted text.
- URLs in photo/video/document captions are detected automatically.
- `www.example.com/...` links are normalized to HTTPS before download.
- Multiple links in one message remain supported and are deduplicated.


## v1.11.1 Docker/Render build fix

- The Docker image now installs `unzip` before running the official Deno installer.
- This fixes Render/Docker builds that failed with `either unzip or 7z is required to install Deno`.
- No runtime downloader behavior was changed by this patch.

## v1.9.0 reliability, long-video delivery and command menu

- Social URL handling now recognizes more mobile/subdomain variants for major platforms.
- yt-dlp retries, fragment retries, continuation and HLS handling are tuned for longer media.
- Telegram's command menu is populated automatically; admins receive an expanded admin-only menu.
- Audit logging records commands, links, buttons, user identity, server ID and download outcomes.
- A persistent application log file is available from the admin panel.
- Large media has no application-side duration/size cap by default. Files above the configured Telegram upload chunk size are automatically split with FFmpeg and delivered in parts.
- `STORAGE_QUOTA_GB=0` means no application quota; physical disk/object-storage capacity still applies.
- `KEEP_MEDIA=1` enables local archive retention. On Render Free, local files remain ephemeral and are lost on restart/redeploy/spin-down.

### Important platform limits

yt-dlp supports many extractors, but no downloader can guarantee every social URL indefinitely because platforms change their APIs, authentication and anti-bot behavior. Authentication-required media is skipped.

Telegram's standard Bot API currently limits newly uploaded videos/files to 50 MB. The bot therefore splits larger media into parts automatically. A self-hosted Local Bot API Server can raise uploads to 2000 MB.

Render Free uses an ephemeral filesystem, so it is not an unlimited permanent file store. For durable archives use supported persistent storage or a paid persistent disk.

## v1.15.0 privacy + credential-free update

- Removed all cookie-file support, browser-cookie extraction, and session-cookie configuration.
- Removed credential handling from the downloader, runner, admin panel, Render configuration, updater, and example environment.
- Existing installations automatically delete legacy `cookies/` and `cookies.txt` data during update.
- Authentication-required media is skipped instead of using stored sessions.
- Removed tracked cookie files from the repository.
- Added an admin-panel Privacy view showing the credential-free policy.

## v1.8.0 audit + server monitoring

- `/admin` now opens the protected inline admin control panel.
- User records include Telegram ID, username, display name, first/last seen timestamps and link counts.
- Audit logs record message/link activity and download success/failure/cancellation events with date/time and the serving server ID.
- Server registry/heartbeat shows whether the current Render service or local device is online.
- Render instances identify themselves from Render environment metadata; local Termux/Linux instances identify by hostname.
- The database is created locally as `bot.db` by default, with the same schema on Render.
- Real URL logging can be disabled with `LOG_URLS=0`.
- Bot tokens and other secrets are never included in audit records.
- **Important:** separate Render and local SQLite databases are separate datasets. The panel can show multiple servers only when they share the same database (for example, a future PostgreSQL deployment). Running the same bot token on two servers is still prohibited by Telegram's polling rules.



## v1.7.1 reliability update

### Telegram 409 conflict protection
- Adds a Linux/Termux-compatible file lock so two local `runner.py` processes cannot poll the same bot token simultaneously.
- Treats Telegram HTTP 409 `getUpdates` conflicts as an ownership problem rather than a generic unhandled update error.
- Uses exit code 75 for a duplicate/foreign poller; the Render supervisor does not restart endlessly when that code is returned.
- If the bot is running on Render, do not run the same bot token with `python runner.py` on Termux/another server at the same time.

## v1.7.0 reliability update

### Telegram API connection hardening
- Dedicated HTTPX request pools for normal Bot API calls and long polling.
- Longer connect/read/write/pool timeouts for cloud and mobile-network TLS stalls.
- HTTP transport retries transient connection failures before surfacing an error.
- Long polling uses a longer getUpdates timeout and indefinite bootstrap retries.
- A background Telegram watchdog periodically checks Bot API reachability and records the result in logs.
- A global PTB error handler replaces the previous `No error handlers are registered` warning with structured network/error logging.
- The Render web process supervises `runner.py` and restarts it after an unexpected exit.
- Downloads, database, admin panel, commands and updater behavior remain compatible.

> **Important:** These changes improve resilience to transient network failures and unexpected runner exits. They cannot guarantee 24/7 uptime if a free hosting provider suspends or restarts the service.


> **Testing / Beta:** Active development. Use only with content you are legally permitted to access, download, copy, or convert. See [TERMS.md](TERMS.md).

A self-hosted Telegram media downloader built with Python, python-telegram-bot, yt-dlp, and FFmpeg.

## v1.6.0 feature update

### Powerful Telegram admin panel
- `/panel` opens a protected inline admin control panel.
- Overview: users, history, success/failure totals, free disk, FFmpeg and yt-dlp.
- Users: recent Telegram user IDs and last-seen timestamps.
- Jobs: active jobs, per-user queue visibility and global concurrency.
- Storage: download/database paths, file counts and disk usage.
- Privacy: credential-free runtime; no session import support.
- Cleanup: one-tap removal of stale download files older than 1 hour.
- Broadcast help: guided `/announce` access.
- System: release, Python, PID, paths, limits and runtime information.
- No public admin HTTP endpoint is exposed.

## v1.5.0 feature update

## v1.4.1 feature update

This patch keeps raw yt-dlp/HTTP/authentication errors out of Telegram user messages. Full technical exceptions remain in server logs for debugging. Links that require authentication are reported as skipped; the bot does not bypass authentication.

## v1.4 feature update

This release connects the roadmap features that can safely run in the existing single-process architecture:

### Smart downloader
- Smart URL analysis with title, uploader, duration, platform, available resolutions, format count and size hints
- Interactive Best / 1080p / 720p / 480p / MP3 / captions selection
- Multiple URLs per message
- Playlist/batch downloading with a configurable item limit
- Resume-capable yt-dlp transfers and fragment retries
- MP3 extraction with configurable default audio quality
- Subtitle/caption downloads
- Progress percentage, speed and ETA
- User queue pause/resume plus cancellation
- Per-user queue and global concurrency limits
- User rate limiting
- Smart error messages for 401/403/404/429, DNS, timeout, TLS and FFmpeg failures

### User features
- Persistent SQLite history
- History search
- Favorites
- Personal download statistics
- Saved language, quality, audio and caption preferences
- English, Malayalam, Hindi and Tamil UI preference

### Administration
- Admin dashboard
- Stale-download cleanup command
- Broadcast announcement command
- Recent-user visibility
- Disk, FFmpeg and yt-dlp status
- Version command
- Existing legal-use and beta restrictions remain enabled

### Reliability
- Robust yt-dlp retry layer
- IPv4 fallback
- User-agent fallback
- Continued downloads and fragment retries
- Render-compatible webhook runner
- GitHub Actions validation
- Existing-user update scripts
- Environment preservation and automatic legacy credential cleanup during updates

## YouTube and Instagram support

YouTube videos/Shorts and Instagram posts/Reels are supported through yt-dlp. This project does not use browser cookies, imported login state, or stored authentication credentials. Authentication-required media is skipped.

## Commands

| Command | Description |
|---|---|
| /start | Main menu |
| /help | Full command list |
| /analyze <URL> | Inspect media and available formats |
| /quality <URL> | Interactive quality selection |
| /mp3 <URL> | Extract audio |
| /subs <URL> | Download with available captions |
| /playlist <URL> | Queue an authorized playlist batch |
| /settings | User preferences |
| /history [search] | Recent/searchable history |
| /favorites | Saved URLs |
| /stats | Personal usage statistics |
| /status | Active jobs/resources |
| /queue | Queue status |
| /pause | Pause queued jobs for the user |
| /resume | Resume queued jobs |
| /cancel | Cancel active jobs |
| /version | Release/version information |
| /terms | Beta/legal-use notice |
| /admin | Protected full inline admin panel |
| /panel | Same protected inline admin panel |

Admin-only commands include `/panel`, `/cleanup` and `/announce <message>`. Set `ADMIN_USER_IDS` first. The panel is Telegram-native and restricted by numeric Telegram user ID.

## Configuration

~~~bash
cp .env.example .env
~~~

At minimum:

~~~env
BOT_TOKEN=YOUR_BOTFATHER_TOKEN
DOWNLOAD_DIR=downloads
DB_FILE=bot.db
MAX_FILE_SIZE_MB=0
TELEGRAM_UPLOAD_CHUNK_MB=45
STORAGE_QUOTA_GB=0
STORAGE_BACKEND=local
KEEP_MEDIA=0
APP_LOG_FILE=bot.log
MAX_CONCURRENT_DOWNLOADS=4
MAX_LINKS_PER_MESSAGE=0
MAX_QUEUE_PER_USER=0
RATE_LIMIT_SECONDS=2
PLAYLIST_MAX_ITEMS=10
PROGRESS_UPDATE_SECONDS=3
DEFAULT_AUDIO_QUALITY=192

# Optional
ADMIN_USER_IDS=123456789

LOG_URLS=1
SERVER_HEARTBEAT_INTERVAL=30
# Optional: SERVER_NAME=My Termux phone


YTDLP_MAX_ATTEMPTS=3
YTDLP_RETRY_DELAY=2
YTDLP_FORCE_IPV4=0
# YTDLP_USER_AGENT=

TG_CONNECT_TIMEOUT=20
TG_READ_TIMEOUT=45
TG_WRITE_TIMEOUT=90
TG_POOL_TIMEOUT=20
TG_MEDIA_WRITE_TIMEOUT=180
TG_CONNECTION_POOL=32
TG_HTTP_RETRIES=3
TG_UPDATES_TIMEOUT=35
TG_WATCHDOG_INTERVAL=60
RUNNER_RESTART_DELAY=5
~~~

Never commit the real .env, bot token, API keys, or session secrets.

## Installation

~~~bash
git clone https://github.com/rolexai-os/telegram-video-downloader.git
cd telegram-video-downloader
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env and add BOT_TOKEN
python runner.py
~~~

### Termux

~~~bash
pkg update
pkg install python ffmpeg git
cd telegram-video-downloader
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env
python runner.py
~~~

## Existing-user update

~~~bash
cd telegram-video-downloader
bash update.sh
# or
python update.py
~~~

The updater preserves `.env`, installs current dependencies, removes legacy `cookies/` and `cookies.txt` credential data, and updates the checked-out release. **Restart the bot after updating.**

For existing users, do not replace your .env with .env.example; copy new variables manually when required.

## Render

Connect the main branch to Render and add BOT_TOKEN as a secret environment variable. Auto-deploy can deploy new commits from main.

web.py launches runner.py, so the same downloader/retry logic is used locally and on Render.

**Free-tier storage limitation:** Render's local filesystem is not durable. SQLite history/favorites and temporary downloads can disappear after an instance reset/redeploy unless persistent storage or an external database is configured.

## Roadmap status

### Connected now
- Smart URL analysis and format inspection
- Queue pause/resume/cancel
- Personal statistics
- Admin cleanup and announcements
- Improved retry/error guidance
- Versioned release and synchronized configuration/docs

### Planned architecture work
Some roadmap items require infrastructure rather than another command handler and are intentionally not faked as complete:
- PostgreSQL migrations and durable multi-instance storage
- Redis-backed distributed job queue
- Dedicated worker processes
- S3/MinIO object storage
- Production monitoring/metrics
- Full multilingual translation catalog
- Automated release notification service

These belong in the next infrastructure release rather than being represented as working features without their required backend.

## Telegram/Render reliability

The service now treats Telegram connectivity as a recoverable dependency. A `TimedOut`/TLS connection failure during a reply is logged and retried by the HTTP transport where applicable instead of producing an unhandled-update warning. Long polling is configured separately from normal API traffic, and the runner process is supervised by `web.py` on Render.

For a free Render deployment, keep `PTB_MANAGED_WEBHOOK` unset. `web.py` owns Render's public port and `runner.py` uses polling; enabling a second PTB webhook listener would recreate the port-conflict problem fixed in v1.6.1.

## Validation


~~~bash
python -m compileall -q bot.py runner.py web.py update.py
~~~

GitHub Actions also compiles the application, imports the runner, checks downloader signatures, and verifies release/configuration wiring.

## Responsible use

Only download content you are legally permitted to access/download. Do not bypass DRM, authentication, access controls, paywalls, technical restrictions, or platform rules. See TERMS.md.

## Status

**Testing / Beta — v1.15.0**
