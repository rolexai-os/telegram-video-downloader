# Local plugins

Plugins are **disabled by default**. To opt in, set `ENABLE_PLUGINS=1` in your
local `.env` and restart the bot. The loader imports only top-level `*.py`
files in this directory and calls their `register(app, bot_module, runner_module)`
function. A failing plugin is reported in `/plugins` without stopping startup.

**Security:** a plugin is arbitrary Python code running with the bot's permissions.
Only enable plugins you wrote or have reviewed. Never install untrusted plugin files.
The included `example_plugin.py` adds `/pluginhello` as a minimal demonstration.
