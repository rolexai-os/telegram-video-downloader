# Cookie folder

Place only **authorized yt-dlp Netscape-format cookie files** in this directory.

## Default layout

    telegram-video-downloader/
    ├── .env
    ├── bot.py
    ├── runner.py
    ├── admin_panel.py
    ├── downloads/
    ├── cookies/
    │   ├── youtube.txt
    │   ├── instagram.txt
    │   ├── facebook.txt
    │   ├── tiktok.txt
    │   ├── x.txt
    │   ├── reddit.txt
    │   ├── vimeo.txt
    │   ├── dailymotion.txt
    │   ├── snapchat.txt
    │   ├── pinterest.txt
    │   ├── linkedin.txt
    │   ├── twitch.txt
    │   ├── threads.txt
    │   ├── telegram.txt
    │   └── generic.txt
    └── bot.db

The bot automatically selects the cookie jar from the URL platform. Missing files are ignored.

## Exact path examples

Linux / VPS:

    /app/telegram-video-downloader/cookies/youtube.txt
    /app/telegram-video-downloader/cookies/instagram.txt

Termux:

    ~/telegram-video-downloader/cookies/youtube.txt
    ~/telegram-video-downloader/cookies/instagram.txt

Or set an explicit path in .env:

    COOKIES_YOUTUBE=/secure/cookies/youtube.txt
    COOKIES_INSTAGRAM=/secure/cookies/instagram.txt

## Security

Real cookie files contain session credentials. Do not upload them to GitHub, do not put them in .env, and do not send them to the bot in Telegram. The repository ignores cookie contents; this README is the tracked guide.

The admin panel shows only whether a cookie file exists and its size; it never displays cookie values.

Cookies do not bypass DRM, paywalls, authentication controls, or unsupported extractors. They only allow yt-dlp to use an already-authorized session where the extractor supports it.
