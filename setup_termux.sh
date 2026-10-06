#!/usr/bin/env bash
set -euo pipefail

# Termux bootstrap for Telegram Video Downloader.
# Does not overwrite an existing .env file.

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

if ! command -v pkg >/dev/null 2>&1; then
  echo "❌ This setup script is intended for Termux."
  exit 1
fi

echo "📦 Installing Termux dependencies..."
pkg update
pkg install -y python ffmpeg git nodejs-lts

echo "🐍 Preparing Python environment..."
if [ ! -d .venv ]; then
  python -m venv .venv
fi
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
  echo "📝 Created .env from .env.example. Add BOT_TOKEN before starting."
else
  echo "✅ Existing .env preserved."
fi

echo ""
echo "🔎 JavaScript runtime:"
node --version
.venv/bin/python - <<'PY'
import shutil
print("node:", shutil.which("node") or "NOT FOUND")
print("deno:", shutil.which("deno") or "not installed (Node.js fallback is OK)")
PY

echo ""
echo "✅ Termux setup complete."
echo "Start with: .venv/bin/python runner.py"
