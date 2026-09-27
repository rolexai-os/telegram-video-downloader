# Telegram Video Downloader

Self-hosted Telegram media downloader powered by yt-dlp.

## Supported media

YouTube, Shorts, Instagram/Reels, X/Twitter, Facebook, TikTok, Reddit, Vimeo, Dailymotion, and other sites supported by yt-dlp.

## Features

- Highest available compatible quality
- Automatic video/audio merging with FFmpeg
- Original title-based filenames
- Concurrent download limit
- Automatic cleanup after upload
- Optional cookies.txt support
- Configuration through `.env`
- No bot token hard-coded in source

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

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`.

Edit `.env` and set your `BOT_TOKEN`.

## Run

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

For media that requires an authenticated browser session, set `COOKIES_FILE` to a valid cookies file you are authorized to use. Never commit cookies or `.env`.

## Telegram file size

The default limit is 49 MiB for normal Bot API deployments. Larger files require an appropriate Telegram Bot API configuration and application changes.

## Security

Never expose your bot token. If it is leaked, revoke it through BotFather and create a new token. Download only media you have permission to access/download.

## License

MIT
