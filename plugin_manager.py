"""Opt-in local plugin loader for Telegram Video Downloader.

Plugins are trusted Python code. Keep ENABLE_PLUGINS=0 unless every file in
plugins/ has been reviewed. Plugin failures are isolated from bot startup.
"""
import importlib.util
import logging
import os
from pathlib import Path

log = logging.getLogger("telegram-video-downloader.plugins")
PLUGIN_DIR = Path(__file__).resolve().parent / "plugins"


def discover_plugins(plugin_dir=None):
    """Return stable, local .py plugin paths; ignore private files and folders."""
    root = Path(plugin_dir) if plugin_dir is not None else PLUGIN_DIR
    if not root.is_dir():
        return []
    return sorted(
        (path for path in root.glob("*.py") if path.is_file() and not path.name.startswith("_")),
        key=lambda path: path.name.lower(),
    )


def load_plugins(app, bot_module, runner_module, *, enabled=None, plugin_dir=None):
    """Load plugins only after explicit opt-in; continue safely if one fails."""
    if enabled is None:
        enabled = os.getenv("ENABLE_PLUGINS", "0").strip().lower() in {"1", "true", "yes", "on"}
    state = {"enabled": bool(enabled), "loaded": [], "errors": []}
    if not enabled:
        return state
    for path in discover_plugins(plugin_dir):
        try:
            module_name = "tvd_plugin_" + path.stem
            spec = importlib.util.spec_from_file_location(module_name, path)
            if spec is None or spec.loader is None:
                raise ImportError("Could not create a module loader")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            register = getattr(module, "register", None)
            if not callable(register):
                raise ValueError("Plugin must define register(app, bot_module, runner_module)")
            register(app, bot_module, runner_module)
            state["loaded"].append(path.stem)
            log.info("Loaded local plugin: %s", path.stem)
        except Exception as exc:
            message = " ".join(str(exc).split())[:180] or type(exc).__name__
            state["errors"].append((path.stem, message))
            log.warning("Could not load plugin %s: %s", path.name, message)
    return state
