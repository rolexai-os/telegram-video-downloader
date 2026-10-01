# Telegram Video Downloader

> **Testing / Beta:** Active development. Use only with content you are legally permitted to access, download, copy, or convert. See [TERMS.md](TERMS.md).

A self-hosted Telegram media downloader built with Python, python-telegram-bot, yt-dlp, and FFmpeg.

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
| /admin | Admin dashboard |

Admin-only commands include /cleanup and /announce <message>. Set ADMIN_USER_IDS first.

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
COOKIES_FILE=/absolute/path/to/cookies.txt

YTDLP_MAX_ATTEMPTS=3
YTDLP_RETRY_DELAY=2
YTDLP_FORCE_IPV4=0
# YTDLP_USER_AGENT=
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

## Existing-user update

~~~bash
cd telegram-video-downloader
bash update.sh
# or
python update.py
~~~

The updater preserves .env and authorized local cookies, installs current dependencies, and updates the checked-out release. **Restart the bot after updating.**

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

## Validation

~~~bash
python -m compileall -q bot.py runner.py web.py update.py
~~~

GitHub Actions also compiles the application, imports the runner, checks downloader signatures, and verifies release/configuration wiring.

## Responsible use

Only download content you are legally permitted to access/download. Do not bypass DRM, authentication, access controls, paywalls, technical restrictions, or platform rules. See TERMS.md.

## Status

**Testing / Beta — v1.4.0**
