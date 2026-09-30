# Telegram Video Downloader

> **Testing / Beta:** Active development. Use only with content you are legally permitted to access, download, copy, or convert. See [TERMS.md](TERMS.md).

A self-hosted Telegram media downloader built with Python, python-telegram-bot, yt-dlp, and FFmpeg.

## Features

### Downloader
- YouTube, Shorts, Instagram/Reels, TikTok, X/Twitter, Facebook, Reddit, Vimeo, Dailymotion and other yt-dlp-supported sites
- Multiple URLs per message
- Interactive Best / 1080p / 720p / 480p / MP3 selection
- Smart format inspection and available-resolution display
- File-size estimate when the source exposes it
- MP3 extraction with FFmpeg
- Subtitle/caption download (`/subs` or Captions button)
- Playlist/batch downloading with configurable item limit
- Original-title based filenames with collision-safe temporary handling
- Resume-capable yt-dlp transfers

### User experience
- Inline-button main menu
- Live progress message with percentage, speed and ETA
- Cancel active jobs
- Per-user queue and global concurrency control
- User-specific rate limiting
- Persistent SQLite history
- Favorites
- Saved quality/audio/caption preferences
- English, Malayalam, Hindi and Tamil UI preference

### Reliability and administration
- Robust retry layer for transient failures
- HTTP 401/403/404/429 classification
- Timeout, DNS and TLS/SSL error classification
- IPv4 fallback option
- Fragment/file/extractor retries
- Optional authorized cookies
- FFmpeg availability check
- Admin dashboard with users, success/failure counts, disk space and yt-dlp version
- Automatic temporary-file cleanup

### Deployment and maintenance
- Docker + Render deployment
- Render health endpoint
- GitHub Actions validation
- `.env` configuration
- Existing-user updater preserving local secrets
- Versioned releases

## Configuration

```bash
cp .env.example .env
```

Configure at least:

```env
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

# Optional
ADMIN_USER_IDS=123456789
COOKIES_FILE=/absolute/path/to/cookies.txt

YTDLP_MAX_ATTEMPTS=3
YTDLP_RETRY_DELAY=2
YTDLP_FORCE_IPV4=0
# YTDLP_USER_AGENT=
```

Never commit the real `.env` or expose `BOT_TOKEN`. For Render, enter these values in the service Environment Variables instead of storing a real `.env` in GitHub.

## Commands

| Command | Description |
|---|---|
| `/start` | Main menu |
| `/help` | Usage help |
| `/quality <URL>` | Inspect formats and choose quality |
| `/mp3 <URL>` | Extract audio |
| `/subs <URL>` | Download with available captions |
| `/playlist <URL>` | Queue an authorized playlist batch |
| `/settings` | Language, quality, audio and caption preferences |
| `/history` | Recent downloads |
| `/favorites` | Saved URLs |
| `/status` | Active jobs/resources |
| `/cancel` | Cancel your jobs |
| `/terms` | Beta/legal-use notice |
| `/admin` | Admin dashboard |

## Installation

```bash
git clone https://github.com/rolexai-os/telegram-video-downloader.git
cd telegram-video-downloader
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env and add BOT_TOKEN
python runner.py
```

### Termux

```bash
pkg update
pkg install python ffmpeg git
cd telegram-video-downloader
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env
python runner.py
```

## Existing-user updates

```bash
cd telegram-video-downloader
bash update.sh
# or
python update.py
```

The updater preserves `.env` and authorized local cookies, updates dependencies, checks the latest Git revision and asks the user to restart. Do not run a self-update over a running production process without restarting it afterward.

## Render

Use the repository `Dockerfile`/`render.yaml`, connect the `main` branch and add `BOT_TOKEN` as a Render Environment Variable. Enable auto-deploy so new releases are deployed after validated commits. `web.py` launches `runner.py`, keeping local and Render download behavior aligned.

## Validation

```bash
python -m compileall -q bot.py runner.py web.py update.py
```

GitHub Actions also validates Python syntax, required files, entrypoint wiring and configuration consistency on pushes and pull requests.

## Responsible use

Only download content you are legally permitted to access/download. Do not bypass DRM, authentication, access controls, paywalls, technical restrictions, or platform rules. See [TERMS.md](TERMS.md).

## Status

**Testing / Beta — v1.3.0**
