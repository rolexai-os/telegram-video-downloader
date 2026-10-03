#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/rolexai-os/telegram-video-downloader.git}"
BRANCH="${UPDATE_BRANCH:-main}"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "🔄 Checking for Telegram Video Downloader updates..."

if [ ! -d .git ]; then
  echo "❌ This installation is not a Git checkout."
  echo "Reinstall using the official repository to enable automatic updates."
  exit 1
fi

git remote get-url origin >/dev/null 2>&1 || git remote add origin "$REPO_URL"
git fetch --quiet origin "$BRANCH"

LOCAL="$(git rev-parse HEAD)"
REMOTE="$(git rev-parse "origin/$BRANCH")"

if [ "$LOCAL" = "$REMOTE" ]; then
  echo "✅ Already up to date: ${LOCAL:0:7}"
  exit 0
fi

BACKUP_DIR=".update-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Keep local secrets and user-specific files out of Git operations.
[ -f .env ] && cp .env "$BACKUP_DIR/.env"
[ -f cookies.txt ] && cp cookies.txt "$BACKUP_DIR/cookies.txt"
COOKIE_DIR="${COOKIES_DIR:-cookies}"
[ -d "$COOKIE_DIR" ] && cp -a "$COOKIE_DIR" "$BACKUP_DIR/cookies"

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "⚠️ Local source changes detected. Creating a safety stash..."
  git stash push -u -m "pre-auto-update-$(date +%s)" >/dev/null
fi

echo "⬇️ Updating ${LOCAL:0:7} → ${REMOTE:0:7}"
git pull --ff-only origin "$BRANCH"

if [ -f .env ]; then
  true
elif [ -f "$BACKUP_DIR/.env" ]; then
  cp "$BACKUP_DIR/.env" .env
fi

if [ -d "$BACKUP_DIR/cookies" ]; then mkdir -p "$COOKIE_DIR"; cp -a "$BACKUP_DIR/cookies/." "$COOKIE_DIR/"; fi

PYTHON="python3"
[ -x .venv/bin/python ] && PYTHON=".venv/bin/python"

if [ -x .venv/bin/pip ]; then
  .venv/bin/pip install -q -r requirements.txt
else
  "$PYTHON" -m pip install -q -r requirements.txt
fi

echo ""
echo "✅ Update completed successfully."
echo "Version: $(git rev-parse --short HEAD)"
echo "Restart the bot/application to load the new version."
