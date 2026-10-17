"""Regression tests for downloader features; no network or real downloads required."""
import asyncio
import unittest
from unittest.mock import patch

import bot
import runner


class DownloaderFeatureTests(unittest.TestCase):
    def test_mp3_postprocessor_and_bitrate(self):
        with patch.object(bot, "DEFAULT_AUDIO_QUALITY", "320"):
            options = bot.opts("sample.%(ext)s", audio=True)
        self.assertEqual(options["postprocessors"][0]["preferredcodec"], "mp3")
        self.assertEqual(options["postprocessors"][0]["preferredquality"], "320")
        self.assertTrue(options["outtmpl"].endswith("%(ext)s"))

    def test_history_search_is_parameterized_and_user_scoped(self):
        sql, params = bot.history_search_query(42, "x' OR 1=1 --")
        self.assertIn("user_id=?", sql)
        self.assertIn("title LIKE ?", sql)
        self.assertNotIn("x' OR 1=1 --", sql)
        self.assertEqual(params[0], 42)
        self.assertEqual(params[1], "%x' OR 1=1 --%")

    def test_latest_failed_history_query_is_user_scoped(self):
        sql, params = bot.history_latest_failed_query(314)
        self.assertIn("user_id=?", sql)
        self.assertIn("status='failed'", sql)
        self.assertEqual(params, (314,))

    def test_history_limit_is_bounded(self):
        sql, params = bot.history_search_query(7, "", 999)
        self.assertTrue(sql.endswith("LIMIT ?"))
        self.assertEqual(params, (7, 50))

    def test_error_messages_do_not_echo_raw_source_error(self):
        message = bot.user_error_message("HTTP Error 403: Forbidden")
        self.assertIn("source rejected", message.lower())
        self.assertNotIn("HTTP Error", message)

    def test_spotify_downloads_remain_disabled(self):
        with self.assertRaisesRegex(RuntimeError, "Spotify downloads are disabled"):
            bot.ensure_supported_url("https://open.spotify.com/track/example")

    def test_runner_mp3_options_use_configured_bitrate(self):
        with patch.object(bot, "DEFAULT_AUDIO_QUALITY", "256"):
            options = runner.download_options("sample.%(ext)s", True, None, 1)
        self.assertEqual(options["postprocessors"][0]["preferredquality"], "256")

    def test_diagnostics_and_retry_handlers_are_callable(self):
        self.assertTrue(callable(runner.health_cmd))
        self.assertTrue(callable(runner.platforms_cmd))
        self.assertTrue(callable(bot.retry_cmd))


class InputValidationTests(unittest.TestCase):
    def test_settings_values_are_allow_listed(self):
        self.assertEqual(bot.validate_setting_value("language", "ml"), "ml")
        self.assertIsNone(bot.validate_setting_value("language", "not-a-language"))
        self.assertEqual(bot.validate_setting_value("quality", "1080"), "1080")
        self.assertIsNone(bot.validate_setting_value("quality", "best-and-secret"))
        self.assertEqual(bot.validate_setting_value("audio", True), 1)
        self.assertEqual(bot.validate_setting_value("captions", "off"), 0)
        self.assertIsNone(bot.validate_setting_value("unknown", "anything"))

    def test_cancel_selection_matches_only_one_job(self):
        class FakeTask:
            def __init__(self, name):
                self.name = name
            def get_name(self):
                return self.name

        tasks = [
            FakeTask("download-42-a1b2c3d4"),
            FakeTask("download-42-e5f6a7b8"),
        ]
        self.assertEqual(bot.select_jobs_for_cancel(tasks, "a1b2c3d4"), [tasks[0]])
        self.assertEqual(bot.select_jobs_for_cancel(tasks, "missing"), [])
        self.assertEqual(bot.select_jobs_for_cancel(tasks, ""), tasks)
        ambiguous = [FakeTask("one-sameid"), FakeTask("two-sameid")]
        self.assertEqual(bot.select_jobs_for_cancel(ambiguous, "sameid"), [])

    def test_cancellation_aware_hook_stops_worker_on_next_progress(self):
        import threading
        event = threading.Event()
        seen = []
        hook = bot.cancellation_aware_hook(event, lambda info: seen.append(info))
        hook({"status": "downloading"})
        self.assertEqual(len(seen), 1)
        event.set()
        with self.assertRaises(bot.DownloadCancelled):
            hook({"status": "downloading"})

    def test_task_names_include_unique_short_ids(self):
        first = bot.task_name("download", 123)
        second = bot.task_name("download", 123)
        self.assertTrue(first.startswith("download-123-"))
        self.assertEqual(len(first.rsplit("-", 1)[-1]), 8)
        self.assertNotEqual(first, second)


class QueueLimitTests(unittest.IsolatedAsyncioTestCase):
    async def test_user_queue_limit_rejects_excess_jobs(self):
        old_limit, old_jobs, old_lock = bot.MAX_QUEUE_PER_USER, bot.JOBS, bot.LOCK
        try:
            bot.MAX_QUEUE_PER_USER = 1
            bot.JOBS = {}
            bot.LOCK = asyncio.Lock()
            first, second = object(), object()
            self.assertTrue(await bot.register(987654, first))
            self.assertFalse(await bot.register(987654, second))
            await bot.unregister(987654, first)
            self.assertTrue(await bot.register(987654, second))
            await bot.unregister(987654, second)
        finally:
            bot.MAX_QUEUE_PER_USER, bot.JOBS, bot.LOCK = old_limit, old_jobs, old_lock


class PluginManagerTests(unittest.TestCase):
    def test_plugins_are_disabled_by_default(self):
        from plugin_manager import load_plugins
        state = load_plugins(object(), bot, runner, enabled=False, plugin_dir="missing-plugins")
        self.assertEqual(state, {"enabled": False, "loaded": [], "errors": []})

    def test_discovery_ignores_private_and_non_python_files(self):
        import tempfile
        from pathlib import Path
        from plugin_manager import discover_plugins
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "one.py").write_text("def register(app, bot_module, runner_module): pass")
            (root / "_private.py").write_text("not valid python!")
            (root / "notes.txt").write_text("not a plugin")
            self.assertEqual([p.name for p in discover_plugins(root)], ["one.py"])

    def test_loader_isolates_a_failing_plugin(self):
        import tempfile
        from pathlib import Path
        from plugin_manager import load_plugins
        class FakeApp:
            pass
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "good.py").write_text("def register(app, bot_module, runner_module): app.loaded = True")
            (root / "bad.py").write_text("def register(app, bot_module, runner_module): raise RuntimeError('expected test failure')")
            app = FakeApp()
            state = load_plugins(app, bot, runner, enabled=True, plugin_dir=root)
            self.assertTrue(app.loaded)
            self.assertEqual(state["loaded"], ["good"])
            self.assertEqual(state["errors"][0][0], "bad")

    def test_queue_and_plugins_commands_are_available(self):
        self.assertTrue(callable(runner.queue_cmd))
        self.assertTrue(callable(runner.plugins_cmd))


if __name__ == "__main__":
    unittest.main()
