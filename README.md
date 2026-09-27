# Telegram Video Downloader

Self-hosted multi-user Telegram media downloader powered by yt-dlp.

## Supported media

YouTube, Shorts, Instagram/Reels, X/Twitter, Facebook, TikTok, Reddit, Vimeo, Dailymotion, and other sites supported by yt-dlp.

## Features

### Multi-device / multi-user
- Multiple Telegram users and devices can use the same bot simultaneously.
- Per-user job tracking and queue limits.
- Global concurrency control prevents the server from being overloaded.
- Per-user rate limiting.
- Jobs are isolated by Telegram user/chat.
- `/status` shows the user's active jobs.
- `/cancel` cancels the user's active/queued tasks.

### Multiple links
- Send several URLs in one Telegram message.
- Each URL becomes an independent download job.
- Configurable maximum links per message.
- Multiple links can be downloaded concurrently, limited by `MAX_CONCURRENT_DOWNLOADS`.

### Quality and audio
- Highest available compatible video quality.
- Automatic video/audio merging with FFmpeg.
- `/quality <URL>` provides Best, 720p and 480p choices.
- `/mp3 <URL>` extracts 192 kbps MP3.
- Video and audio uploads use the appropriate Telegram media type.

### Reliability / performance
- yt-dlp retries and fragment retries.
- Concurrent fragment downloading.
- Async job scheduling so one download does not block other users.
- Automatic temporary-file cleanup.
- File-size protection.
- Socket timeout protection.

### Security
- Bot token is loaded from `.env`.
- `.env`, cookies and downloads are ignored by Git.
- Optional authorized cookies.txt support.
- Per-user queue and rate limiting.
- Optional admin-only status command.
- No secrets are hard-coded into the source.

## Configuration

Copy `.env.example` to `.env` and edit:

| Variable | Purpose |
|---|---|
| `BOT_TOKEN` | Telegram BotFather token |
| `DOWNLOAD_DIR` | Temporary download directory |
| `MAX_FILE_SIZE_MB` | Maximum file size to upload |
| `MAX_CONCURRENT_DOWNLOADS` | Global simultaneous downloads |
| `MAX_LINKS_PER_MESSAGE` | Maximum URLs accepted per message |
| `MAX_QUEUE_PER_USER` | Maximum active jobs per Telegram user |
| `RATE_LIMIT_SECONDS` | Per-user request cooldown |
| `ADMIN_USER_IDS` | Optional comma-separated Telegram IDs |
| `COOKIES_FILE` | Optional authorized yt-dlp cookies file |

## Commands

- `/start` — overview
- `/help` — usage help
- `/status` — your active jobs
- `/cancel` — cancel your jobs
- `/mp3 <URL>` — download audio as MP3
- `/quality <URL>` — choose Best / 720p / 480p / MP3
- `/admin` — admin-only server status

## Requirements

- Python 3.10+
- FFmpeg
- Telegram bot token

## Install

```bash
git clone https://github.com/rolexai-os/telegram-video-downloader.git
cd telegram-video-downloader
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

On Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Edit `.env`, set `BOT_TOKEN`, then:

```bash
python bot.py
```

## Termux

```bash
pkg update
pkg install python ffmpeg
pip install -r requirements.txt
cp .env.example .env
nano .env
python bot.py
```

## Cookies

For media requiring an authenticated browser session, set `COOKIES_FILE` to a valid cookies file you are authorized to use. Never commit cookies or `.env`.

## Telegram file size

The default limit is 49 MiB for normal Bot API deployments. Larger files require an appropriate Telegram Bot API configuration and corresponding application/server configuration.

## Notes

- Multiple devices are naturally supported because Telegram identifies each user/chat independently.
- Multiple links are processed as separate jobs.
- The bot is self-hosted: keep it running on a VPS, PC, Raspberry Pi, Termux device, or server.
- Download only media you have permission to access/download.

## License

MIT
