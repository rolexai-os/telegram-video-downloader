#!/usr/bin/env python3
"""Safe updater for existing Git-based installations.

Usage: python update.py
Secrets such as .env and cookies.txt are preserved locally and are never fetched
from GitHub by this script.
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

    print("🔄 Checking for updates...")
    run("git", "fetch", "--quiet", "origin", BRANCH)
    local = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    remote = subprocess.check_output(["git", "rev-parse", f"origin/{BRANCH}"], cwd=ROOT, text=True).strip()

    if local == remote:
        print(f"✅ Already up to date: {local[:7]}")
        return 0

    backup = ROOT / f".update-backup-{local[:7]}"
    backup.mkdir(exist_ok=True)
    for name in (".env", "cookies.txt"):
        src = ROOT / name
        if src.is_file():
            shutil.copy2(src, backup / name)

    dirty = subprocess.run(["git", "diff", "--quiet"], cwd=ROOT).returncode != 0
    cached = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT).returncode != 0
    if dirty or cached:
        print("⚠️ Local source changes detected; creating a safety stash.")
        run("git", "stash", "push", "-u", "-m", "pre-auto-update")

    print(f"⬇️ Updating {local[:7]} → {remote[:7]}")
    run("git", "pull", "--ff-only", "origin", BRANCH)

    for name in (".env", "cookies.txt"):
        saved = backup / name
        if saved.is_file() and not (ROOT / name).exists():
            shutil.copy2(saved, ROOT / name)

    pip = ROOT / ".venv" / "bin" / "pip"
    if pip.exists():
        run(str(pip), "install", "-q", "-r", "requirements.txt")
    else:
        run(sys.executable, "-m", "pip", "install", "-q", "-r", "requirements.txt")

    print(f"✅ Update completed: {remote[:7]}")
    print("Restart the bot/application to load the new version.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
