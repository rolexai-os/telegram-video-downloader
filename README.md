# Telegram Video Downloader

Self-hosted multi-user Telegram media downloader powered by yt-dlp.

## Supported media

YouTube, Shorts, Instagram/Reels, X/Twitter, Facebook, TikTok, Reddit, Vimeo, Dailymotion, and other sites supported by yt-dlp.

## Features

### Multi-device / multi-user
- Unlimited Telegram users and devices can use the same bot simultaneously (subject to Telegram, CPU, RAM, network, and host limits).
- Per-user job tracking; MAX_QUEUE_PER_USER=0 enables an unlimited application-level queue.
- Global concurrency control prevents the server from being overloaded.
- Per-user rate limiting.
- Jobs are isolated by Telegram user/chat.
- `/status` shows the user's active jobs.
- `/cancel` cancels the user's active/queued tasks.

### Multiple links
- Send several URLs in one Telegram message.
- Each URL becomes an independent download job.
- Unlimited links per message/command by default (MAX_LINKS_PER_MESSAGE=0); Telegram message size and server resources still apply.
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
| `MAX_LINKS_PER_MESSAGE` | Maximum URLs accepted per message; 0 = unlimited |
| `MAX_QUEUE_PER_USER` | Maximum queued jobs per user; 0 = unlimited |
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

## Unlimited users/devices and links

The bot does not maintain a fixed device/user registration list. Any Telegram account that can access the bot can submit jobs, and multiple devices/users can work at the same time. Links are processed as independent jobs.

MAX_LINKS_PER_MESSAGE=0 and MAX_QUEUE_PER_USER=0 remove the application's artificial link/queue caps. This does not make the service physically unlimited: Telegram API limits, message size, available RAM/CPU/storage, network bandwidth, FFmpeg/yt-dlp workload, and MAX_CONCURRENT_DOWNLOADS still determine real capacity.

For a public bot, keep a sensible RATE_LIMIT_SECONDS and MAX_CONCURRENT_DOWNLOADS to prevent overload.

## Notes

- Multiple devices are naturally supported because Telegram identifies each user/chat independently.
- Multiple links are processed as separate jobs.
- The bot is self-hosted: keep it running on a VPS, PC, Raspberry Pi, Termux device, or server.
- Download only media you have permission to access/download.

## License

MIT
