# Telegram Video Downloader

> **Testing / Beta:** Active development. Use only with content you are legally permitted to access, download, copy, or convert. See [TERMS.md](TERMS.md).

A self-hosted Telegram media downloader built with Python, python-telegram-bot, yt-dlp, and FFmpeg.

## Connected release architecture

The repository is maintained as one connected release: `bot.py`, `runner.py`, `web.py`, `requirements.txt`, `Dockerfile`, `render.yaml`, `.env.example`, updater scripts, documentation, and validation workflow are kept synchronized.

Every feature release should update `VERSION`, keep local and Render entrypoints on `runner.py`, update dependencies/configuration when needed, and pass the validation workflow before release.

## Features
- Multi-user and multi-device support
- Multiple media URLs per message
- Best / 720p / 480p quality profiles
- MP3 extraction
- Per-user job tracking and cancellation
- Rate limiting and global concurrency control
- Defensive yt-dlp retries and classified errors
- Optional authorized cookies
- Temporary-file cleanup
- Render/Docker deployment
- Existing-user updater preserving local `.env` and authorized cookies

## Configuration (`.env`)

Create your private configuration from the template:

```bash
cp .env.example .env
```

Then edit `.env`:

```env
BOT_TOKEN=YOUR_BOTFATHER_TOKEN
DOWNLOAD_DIR=downloads
MAX_FILE_SIZE_MB=49
MAX_CONCURRENT_DOWNLOADS=4
MAX_LINKS_PER_MESSAGE=0
MAX_QUEUE_PER_USER=0
RATE_LIMIT_SECONDS=2

# Optional
ADMIN_USER_IDS=123456789
COOKIES_FILE=/absolute/path/to/cookies.txt

# yt-dlp reliability
YTDLP_MAX_ATTEMPTS=3
YTDLP_RETRY_DELAY=2
YTDLP_FORCE_IPV4=0
# YTDLP_USER_AGENT=
```

### Configuration reference

| Variable | Purpose | Example |
|---|---|---|
| `BOT_TOKEN` | Telegram BotFather token. **Required. Keep secret.** | `123456:AA...` |
| `DOWNLOAD_DIR` | Temporary download directory | `downloads` |
| `MAX_FILE_SIZE_MB` | Maximum file size accepted by the bot | `49` |
| `MAX_CONCURRENT_DOWNLOADS` | Maximum simultaneous downloads | `4` |
| `MAX_LINKS_PER_MESSAGE` | Maximum links in one message; `0` means no application limit | `10` |
| `MAX_QUEUE_PER_USER` | Maximum queued jobs per user; `0` means no application limit | `5` |
| `RATE_LIMIT_SECONDS` | Minimum delay between requests from a user | `2` |
| `ADMIN_USER_IDS` | Comma-separated Telegram user IDs for admin functions | `123456789` |
| `COOKIES_FILE` | Optional path to an authorized yt-dlp cookies file | `/path/cookies.txt` |
| `YTDLP_MAX_ATTEMPTS` | Number of downloader attempts | `3` |
| `YTDLP_RETRY_DELAY` | Base retry delay in seconds | `2` |
| `YTDLP_FORCE_IPV4` | Use IPv4 when set to `1` | `0` |
| `YTDLP_USER_AGENT` | Optional custom HTTP User-Agent | blank |

### How to configure the token

1. Open Telegram and start a chat with **@BotFather**.
2. Create a bot with `/newbot`.
3. Copy the token BotFather provides.
4. Put it only in your local `.env` as `BOT_TOKEN=...`.
5. Never commit `.env`, paste the token into GitHub, or share it in logs/screenshots.

For Render, add the same values under **Environment Variables** instead of creating a real `.env` in the repository.

### Changing configuration later

Edit your local `.env` and restart the bot:

```bash
nano .env
python runner.py
```

For Render, update the Environment Variables and redeploy/restart the service. Keep secrets out of source control.

## Commands
| Command | Description |
|---|---|
| `/start` | Introduction |
| `/help` | Usage help |
| `/status` | Active jobs |
| `/cancel` | Cancel your jobs |
| `/mp3 <URL>` | MP3 extraction |
| `/quality <URL>` | Best / 720p / 480p / MP3 |
| `/admin` | Authorized admin status |
| `/terms` | Beta/legal-use notice |

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

## Existing installation update
```bash
cd telegram-video-downloader
bash update.sh
# or: python update.py
```

The updater uses fast-forward-only Git updates, creates a safety stash for local changes, preserves `.env` and `cookies.txt`, updates Python dependencies, and asks you to restart. It never fetches secrets from GitHub.

## Render
`Dockerfile` and `render.yaml` are included. Render auto-deploys `main`. `web.py` provides `/healthz` and launches `runner.py`, ensuring production uses the same robust downloader layer as local installations.

## Development validation
```bash
python -m compileall -q bot.py runner.py web.py update.py
```

The GitHub Actions workflow validates syntax, imports, required files, entrypoint wiring, and configuration consistency on pushes and pull requests.

## Responsible use
Only download content you are legally permitted to access/download. Do not bypass DRM, authentication, access controls, paywalls, technical restrictions, or platform rules. See [TERMS.md](TERMS.md).

## Credits
Project: Telegram Video Downloader  
Maintainer: rolexai-os  
Code assistance: AI-assisted development  
Core technologies: Python, python-telegram-bot, yt-dlp, FFmpeg

## License
MIT — see [LICENSE](LICENSE).

## Status
**Testing / Beta — v1.2.0**
