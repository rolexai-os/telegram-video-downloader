#!/usr/bin/env python3
"""Safe updater for existing Git-based installations.

Usage: python update.py
The local .env is preserved. Legacy credential/session files are intentionally
removed because this release no longer supports cookie or browser-session imports.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BRANCH = os.getenv("UPDATE_BRANCH", "main")


def run(*args, check=True):
    return subprocess.run(args, cwd=ROOT, text=True, check=check)


def main():
    if not (ROOT / ".git").is_dir():
        print("❌ Not a Git installation. Reinstall from the official repository.")
        return 1

    if os.environ.get("PREFIX") and shutil.which("pkg") and not shutil.which("deno") and not shutil.which("node"):
        print("📦 Installing Node.js LTS for YouTube support...")
        run("pkg", "install", "-y", "nodejs-lts")

    print("🔄 Checking for updates...")
    run("git", "fetch", "--quiet", "origin", BRANCH)
    local = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    remote = subprocess.check_output(["git", "rev-parse", f"origin/{BRANCH}"], cwd=ROOT, text=True).strip()

    if local == remote:
        print(f"✅ Already up to date: {local[:7]}")
        return 0

    backup = ROOT / f".update-backup-{local[:7]}"
    backup.mkdir(exist_ok=True)
    src = ROOT / ".env"
    if src.is_file():
        shutil.copy2(src, backup / ".env")

    dirty = subprocess.run(["git", "diff", "--quiet"], cwd=ROOT).returncode != 0
    cached = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT).returncode != 0
    if dirty or cached:
        print("⚠️ Local source changes detected; creating a safety stash.")
        run("git", "stash", "push", "-u", "-m", "pre-auto-update")

    print(f"⬇️ Updating {local[:7]} → {remote[:7]}")
    run("git", "pull", "--ff-only", "origin", BRANCH)

    saved = backup / ".env"
    if saved.is_file() and not (ROOT / ".env").exists():
        shutil.copy2(saved, ROOT / ".env")

    for legacy in (ROOT / "cookies.txt", ROOT / "cookies"):
        try:
            if legacy.is_dir():
                shutil.rmtree(legacy)
            elif legacy.exists():
                legacy.unlink()
        except OSError as exc:
            print(f"⚠️ Could not remove legacy credential data {legacy}: {exc}")


    pip = ROOT / ".venv" / "bin" / "pip"
    if pip.exists():
        run(str(pip), "install", "-q", "-r", "requirements.txt")
    else:
        run(sys.executable, "-m", "pip", "install", "-q", "-r", "requirements.txt")

    print(f"✅ Update completed: {remote[:7]}")
    print("Legacy cookie/session data has been removed.")
    print("Restart the bot/application to load the new version.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
