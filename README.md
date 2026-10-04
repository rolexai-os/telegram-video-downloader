# Telegram Video Downloader

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
- Existing cookies, downloads, database, admin panel, commands and updater behavior remain compatible.

> **Important:** These changes improve resilience to transient network failures and unexpected runner exits. They cannot guarantee 24/7 uptime if a free hosting provider suspends or restarts the service.


> **Testing / Beta:** Active development. Use only with content you are legally permitted to access, download, copy, or convert. See [TERMS.md](TERMS.md).

A self-hosted Telegram media downloader built with Python, python-telegram-bot, yt-dlp, and FFmpeg.

## v1.6.0 feature update

### Powerful Telegram admin panel
- `/panel` opens a protected inline admin control panel.
- Overview: users, history, success/failure totals, free disk, FFmpeg and yt-dlp.
- Users: recent Telegram user IDs and last-seen timestamps.
- Jobs: active jobs, per-user queue visibility and global concurrency.
- Storage: download/database/cookie paths, file counts and disk usage.
- Cookies: per-platform cookie-file presence and size without exposing cookie values.
- Cleanup: one-tap removal of stale download files older than 1 hour.
- Broadcast help: guided `/announce` access.
- System: release, Python, PID, paths, limits and runtime information.
- No public admin HTTP endpoint is exposed.

## v1.5.0 feature update

### Per-platform authorized cookies
- Separate cookie jars for YouTube, Instagram, Facebook, TikTok, X/Twitter, Reddit, Vimeo, Dailymotion, Snapchat, Pinterest, LinkedIn, Twitch, Threads and Telegram.
- Automatic platform detection selects only the matching cookie jar.
- Custom COOKIES_<PLATFORM> environment variables can override cookies/<platform>.txt.
- Legacy COOKIES_FILE remains available as a fallback.
- Authenticated stories/restricted media can work when yt-dlp supports the extractor and the operator provides valid, authorized cookies.
- Cookie files stay local and are excluded from Git.
- Authentication/access controls are not bypassed.

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
- Authorized-cookie support
- Existing legal-use and beta restrictions remain enabled

### Reliability
- Robust yt-dlp retry layer
- IPv4 fallback
- User-agent fallback
- Continued downloads and fragment retries
- Render-compatible webhook runner
- GitHub Actions validation
- Existing-user update scripts
- Environment and cookie preservation during updates

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
| /admin | Basic admin dashboard |\n| /panel | Powerful inline admin control panel |

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
MAX_FILE_SIZE_MB=49
MAX_CONCURRENT_DOWNLOADS=4
MAX_LINKS_PER_MESSAGE=0
MAX_QUEUE_PER_USER=0
RATE_LIMIT_SECONDS=2
PLAYLIST_MAX_ITEMS=10
PROGRESS_UPDATE_SECONDS=3
DEFAULT_AUDIO_QUALITY=192

# Optional
ADMIN_USER_IDS=123456789

COOKIES_DIR=cookies
# Optional explicit override:
# COOKIES_INSTAGRAM=/secure/path/instagram.txt
# COOKIES_YOUTUBE=/secure/path/youtube.txt

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

Never commit the real .env, cookies, bot token, API keys, or session secrets.

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

## Cookie files: where to place them

The tracked `cookies/README.md` contains the full folder layout. In a normal checkout, put authorized cookie jars here:

~~~text
cookies/youtube.txt
cookies/instagram.txt
cookies/facebook.txt
cookies/tiktok.txt
cookies/x.txt
cookies/reddit.txt
~~~

Continue the same naming pattern for the other supported platforms. The bot automatically selects the matching file. Real cookie files are ignored by Git and must never be committed or sent through Telegram. For a custom location, set `COOKIES_<PLATFORM>` in `.env`.

## Existing-user update

~~~bash
cd telegram-video-downloader
bash update.sh
# or
python update.py
~~~

The updater preserves .env and the entire local authorized cookies/ directory, installs current dependencies, and updates the checked-out release. **Restart the bot after updating.**

For existing users, do not replace your .env with .env.example; copy new variables manually when required.

## Render

For cookies on the Docker-based Render deployment, use Render **Secret Files**, not GitHub. Render makes service secret files available at runtime under `/etc/secrets/<filename>`.

Recommended setup:

1. Open the Render service → **Environment** → **Secret Files** → **Add Secret File**.
2. Upload/paste each authorized Netscape cookie jar with names such as `youtube.txt`, `instagram.txt`, `facebook.txt`, `tiktok.txt`, and `x.txt`.
3. The included `render.yaml` already maps these to `COOKIES_YOUTUBE=/etc/secrets/youtube.txt`, etc.
4. Save/deploy. The bot will detect the matching cookie file automatically.
5. Check **/panel → 🍪 Cookies** to see presence and file size only; cookie values are never shown.

Render documents a 1 MB combined limit for secret files on a service/environment group, so keep only the cookie jars you actually need.

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

**Testing / Beta — v1.7.1**
