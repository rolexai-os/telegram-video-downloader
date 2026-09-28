# Free deployment on Render

This repository is configured for Render's free Web Service plan.

## 1. Create the Telegram bot

1. Open Telegram and talk to **@BotFather**.
2. Run `/newbot`.
3. Copy the bot token. Keep it private.

## 2. Deploy from GitHub

1. Open Render and sign in.
2. Choose **New → Web Service**.
3. Connect `rolexai-os/telegram-video-downloader`.
4. Select branch `main`.
5. Choose the **Free** compute plan.
6. Render will detect the repository Dockerfile.
7. Add the environment variable `BOT_TOKEN` with the BotFather token.
8. Deploy.

The application automatically detects Render's `RENDER_EXTERNAL_URL` and uses Telegram webhook mode. No public URL needs to be hardcoded.

## 3. Recommended free-tier settings

The included `render.yaml` uses conservative defaults:

- `MAX_FILE_SIZE_MB=49`
- `MAX_CONCURRENT_DOWNLOADS=1`
- `MAX_LINKS_PER_MESSAGE=10`
- `MAX_QUEUE_PER_USER=5`
- `RATE_LIMIT_SECONDS=2`

You can increase these values, but a free instance has limited CPU/RAM/bandwidth. `0` can remove some application-level limits, but it never makes the service physically unlimited.

## 4. Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python bot.py
```

Without `WEBHOOK_URL` or `RENDER_EXTERNAL_URL`, the bot uses polling locally.

## 5. Important free-hosting behavior

Render free Web Services can spin down after 15 minutes without inbound traffic and can lose local files when the service restarts or spins down. This bot treats downloads as temporary files, so that behavior is acceptable for a beta downloader. The first request after a sleep period can take about a minute to wake the service.

Do not use the local filesystem as permanent storage.

## 6. Legal use

Only download media you own or are legally permitted to access, download, copy, or convert. Do not use the bot to bypass DRM, authentication, paywalls, access controls, or platform restrictions. Follow the target platform's terms and applicable law.

See `TERMS.md` for the project's beta terms.
