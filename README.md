# Telegram Video Downloader

> **Testing / Beta:** This project is currently in active testing and development. Use it only with content you are legally permitted to access, download, copy, or convert. See [TERMS.md](TERMS.md).

A self-hosted Telegram media downloader built with **Python**, **python-telegram-bot**, **yt-dlp**, and **FFmpeg**.

## Highlights

- 👥 Multi-user and multi-device support
- 🔗 Multiple media URLs per message
- ♾️ No application-level user/device registration cap
- ⚡ Concurrent download jobs with configurable global limits
- 🎚️ Best, 720p, and 480p quality profiles
- 🎵 MP3 extraction
- 📋 Per-user job tracking
- 🛑 Job cancellation
- ⏱️ Per-user rate limiting
- 🔐 Environment-based secrets and optional authorized cookies
- 🧹 Automatic temporary-file cleanup
- 🧩 Support for sites handled by yt-dlp

## Supported platforms

The project can process media from **YouTube, YouTube Shorts, Instagram/Reels, X/Twitter, Facebook, TikTok, Reddit, Vimeo, Dailymotion**, and other sites supported by the installed yt-dlp version.

Support ultimately depends on yt-dlp and the target platform's current behavior, authentication requirements, and policies.

## Commands

| Command | Description |
|---|---|
| `/start` | Show a quick introduction |
| `/help` | Show usage instructions |
| `/status` | Show your active jobs |
| `/cancel` | Request cancellation of your jobs |
| `/mp3 <URL>` | Download audio as MP3 |
| `/quality <URL>` | Choose Best / 720p / 480p / MP3 |
| `/admin` | Show admin status when authorized |
| `/terms` | Show the in-bot beta and lawful-use notice |

You can also send one or more supported media URLs as a normal message.

## Requirements

- Python **3.10+**
- FFmpeg
- A Telegram bot token from BotFather
- Network access to Telegram and the target media service

## Installation

### Linux / macOS / Termux

1. Clone the repository:

```bash
git clone https://github.com/rolexai-os/telegram-video-downloader.git
cd telegram-video-downloader
```

2. Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Create the local configuration:

```bash
cp .env.example .env
```

5. Edit `.env` and set your BotFather token.

6. Start the bot:

```bash
python bot.py
```

### Windows PowerShell

After cloning and installing the requirements:

```powershell
.venv\Scripts\Activate.ps1
python bot.py
```

## Termux

```bash
pkg update
pkg install python ffmpeg
git clone https://github.com/rolexai-os/telegram-video-downloader.git
cd telegram-video-downloader
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env
python bot.py
```

If your Termux environment has package or SSL issues, resolve those environment issues first; they are separate from the bot application.

## Configuration

Copy `.env.example` to `.env`. Never commit the real `.env`.

| Variable | Purpose |
|---|---|
| `BOT_TOKEN` | Telegram BotFather token |
| `DOWNLOAD_DIR` | Temporary/local download directory |
| `MAX_FILE_SIZE_MB` | Maximum file size the bot will upload |
| `MAX_CONCURRENT_DOWNLOADS` | Global simultaneous download limit |
| `MAX_LINKS_PER_MESSAGE` | URL limit per message; `0` = no application-level cap |
| `MAX_QUEUE_PER_USER` | Per-user queued-job limit; `0` = no application-level cap |
| `RATE_LIMIT_SECONDS` | Minimum delay between requests from the same user |
| `ADMIN_USER_IDS` | Optional comma-separated Telegram numeric user IDs |
| `COOKIES_FILE` | Optional authorized yt-dlp cookies file |

### Capacity note

Setting a limit to `0` removes that application's artificial cap; it does **not** make the service physically unlimited. Real capacity is constrained by Telegram, CPU, RAM, disk space, network bandwidth, FFmpeg/yt-dlp workload, and `MAX_CONCURRENT_DOWNLOADS`.

For public deployments, keep sensible concurrency and rate limits.

## Authenticated media

If a supported service requires authentication, configure `COOKIES_FILE` with a cookies file you are legally authorized to use.

**Never** publish cookies, session tokens, passwords, API keys, or other credentials.

## File handling

Downloaded files are temporary and are removed after processing when possible. The configured file-size limit is checked before upload.

The default configuration uses a **49 MiB** upload limit. Telegram Bot API deployments with different limits require corresponding server/application configuration.

## Security

- Secrets are loaded from environment variables.
- `.env` and cookie files are ignored by Git.
- No bot token is included in the repository.
- User jobs are tracked separately.
- Rate limiting and global concurrency controls reduce accidental overload.
- See [SECURITY.md](SECURITY.md) for vulnerability reporting.

GitHub recommends enabling repository security features such as secret scanning, push protection, Dependabot alerts, and code scanning where available.

## Legal and responsible use

This software is a tool. The maintainer does not determine which media users request.

Use the project only for content you are legally permitted to access, download, copy, or convert. Do not use it to bypass DRM, authentication, access controls, paywalls, technical restrictions, or third-party platform rules.

Review [TERMS.md](TERMS.md) before operating the bot.

## Contributing

Contributions, bug reports, documentation improvements, and compatible feature work are welcome.

Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

## Promotion

Ready-to-post announcements for Telegram, X/Twitter, Reddit, LinkedIn, and Discord are available in [PROMOTION.md](PROMOTION.md).

Please promote the project responsibly and follow each community's self-promotion rules. Do not spam, fake engagement, or misrepresent capabilities.

## Credits

- **Project:** Telegram Video Downloader
- **Maintainer:** rolexai-os
- **Code assistance:** AI-assisted development
- **Core technologies:** Python, python-telegram-bot, yt-dlp, FFmpeg

AI tools were used to help design, write, review, and improve portions of the project. The maintainer remains responsible for reviewing, testing, configuring, and operating the software.

## License

This project is licensed under the [MIT License](LICENSE).

## Status

**Current status: Testing / Beta**

The project is expected to evolve. Compatibility with third-party media services can change without notice.
