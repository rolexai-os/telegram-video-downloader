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
