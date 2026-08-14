import os
import tempfile
import unittest
from pathlib import Path

from bridge import ConfigError, load_config


VALID_ENV = {
    "WA_VERIFY_TOKEN": "test-verify-token",
    "WA_APP_SECRET": "test-app-secret-32-characters-long",
}


class DotenvTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base_dir = Path(self.tmp.name)

    def test_supported_syntax_and_literal_no_expansion(self):
        marker = self.base_dir / "must-not-exist"
        dotenv = self.base_dir / ".env"
        dotenv.write_text(
            "\n"
            "   # full-line comment\n"
            "WA_VERIFY_TOKEN='file-token'\n"
            'WA_APP_SECRET="file-secret-32-characters-long"\n'
            "WA_INBOX=./data#not-comment/messages.jsonl\n"
            "WA_BIND=127.0.0.1\n"
            "WA_PORT=3101\n"
            "WA_WEBHOOK_PATH=/meta-hook/\n"
            "WA_LOG_LEVEL=debug\n"
            "WA_STORE_RAW=no\n"
            "WA_REQUEST_TIMEOUT=1\n"
            "WA_SHUTDOWN_TIMEOUT=60\n"
            f"LITERAL_DOLLAR=${{NAME}}\n"
            f"LITERAL_COMMAND=$(touch {marker})\n",
            encoding="utf-8",
        )
        config = load_config({}, self.base_dir)
        self.assertEqual(config.verify_token, "file-token")
        self.assertEqual(config.app_secret, "file-secret-32-characters-long")
        self.assertEqual(config.inbox, Path("./data#not-comment/messages.jsonl"))
        self.assertEqual(config.bind, "127.0.0.1")
        self.assertEqual(config.port, 3101)
        self.assertEqual(config.webhook_path, "/meta-hook")
        self.assertEqual(config.log_level, "DEBUG")
        self.assertFalse(config.store_raw)
        self.assertEqual(config.request_timeout, 1.0)
        self.assertEqual(config.shutdown_timeout, 60.0)
        self.assertFalse(marker.exists())

    def test_process_environment_wins_without_mutation(self):
        (self.base_dir / ".env").write_text(
            "WA_VERIFY_TOKEN=file-token\n"
            "WA_APP_SECRET=file-secret-32-characters-long\n"
            "WA_PORT=3101\n",
            encoding="utf-8",
        )
        env = {
            "WA_VERIFY_TOKEN": "env-token",
            "WA_APP_SECRET": "env-secret-32-characters-long",
            "WA_PORT": "3102",
        }
        before = dict(env)
        config = load_config(env, self.base_dir)
        self.assertEqual(config.verify_token, "env-token")
        self.assertEqual(config.app_secret, "env-secret-32-characters-long")
        self.assertEqual(config.port, 3102)
        self.assertEqual(env, before)

    def test_invalid_lines_and_duplicates_raise_config_error(self):
        cases = {
            "missing_equals": "WA_VERIFY_TOKEN\n",
            "empty_key": "=value\n",
            "mismatched_single": "WA_VERIFY_TOKEN='abc\n",
            "mismatched_double": 'WA_VERIFY_TOKEN="abc\n',
            "duplicate": "WA_VERIFY_TOKEN=a\nWA_VERIFY_TOKEN=b\n",
        }
        for name, content in cases.items():
            with self.subTest(name=name):
                (self.base_dir / ".env").write_text(content, encoding="utf-8")
                with self.assertRaises(ConfigError):
                    load_config(VALID_ENV, self.base_dir)


class ConfigValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base_dir = Path(self.tmp.name)

    def _config(self, **overrides):
        env = dict(VALID_ENV)
        for key, value in overrides.items():
            if value is None:
                env.pop(key, None)
            else:
                env[key] = str(value)
        return load_config(env, self.base_dir)

    def _invalid(self, **overrides):
        with self.assertRaises(ConfigError):
            self._config(**overrides)

    def test_required_secret_rejection(self):
        for key in ("WA_VERIFY_TOKEN", "WA_APP_SECRET"):
            for value in ("", "change-me", "your-secret", "your-token"):
                with self.subTest(key=key, value=value):
                    self._invalid(**{key: value})
        self._invalid(WA_VERIFY_TOKEN=None)
        self._invalid(WA_APP_SECRET=None)

    def test_defaults_and_route_pairs(self):
        config = self._config()
        self.assertEqual(config.bind, "127.0.0.1")
        self.assertEqual(config.port, 3100)
        self.assertEqual(config.inbox, Path("./inbox/messages.jsonl"))
        self.assertEqual(config.webhook_path, "/webhook")
        self.assertEqual(config.log_level, "INFO")
        self.assertTrue(config.store_raw)
        self.assertEqual(config.request_timeout, 10.0)
        self.assertEqual(config.shutdown_timeout, 15.0)
        self.assertEqual(config.accepted_webhook_paths,
                         ("/webhook", "/webhook/whatsapp-cloud"))

        custom = self._config(WA_WEBHOOK_PATH="/custom/")
        self.assertEqual(custom.webhook_path, "/custom")
        self.assertEqual(custom.accepted_webhook_paths,
                         ("/custom", "/custom/whatsapp-cloud"))

    def test_port_boundaries(self):
        self.assertEqual(self._config(WA_PORT=1).port, 1)
        self.assertEqual(self._config(WA_PORT=65535).port, 65535)
        for value in ("0", "65536", "-1", "abc", "3.14"):
            with self.subTest(value=value):
                self._invalid(WA_PORT=value)

    def test_timeout_boundaries(self):
        self.assertEqual(self._config(WA_REQUEST_TIMEOUT=1).request_timeout, 1.0)
        self.assertEqual(self._config(WA_REQUEST_TIMEOUT=60).request_timeout, 60.0)
        self.assertEqual(self._config(WA_SHUTDOWN_TIMEOUT=1).shutdown_timeout, 1.0)
        self.assertEqual(self._config(WA_SHUTDOWN_TIMEOUT=60).shutdown_timeout, 60.0)
        for key in ("WA_REQUEST_TIMEOUT", "WA_SHUTDOWN_TIMEOUT"):
            for value in ("0", "60.1", "-1", "abc"):
                with self.subTest(key=key, value=value):
                    self._invalid(**{key: value})

    def test_boolean_spellings(self):
        for value in ("true", "TRUE", "1", "yes", "on"):
            with self.subTest(value=value):
                self.assertTrue(self._config(WA_STORE_RAW=value).store_raw)
        for value in ("false", "FALSE", "0", "no", "off"):
            with self.subTest(value=value):
                self.assertFalse(self._config(WA_STORE_RAW=value).store_raw)
        self._invalid(WA_STORE_RAW="maybe")

    def test_invalid_log_levels(self):
        for value in ("DEBUG", "info", "Warning", "ERROR", "critical"):
            with self.subTest(value=value):
                self.assertEqual(self._config(WA_LOG_LEVEL=value).log_level,
                                 value.upper())
        self._invalid(WA_LOG_LEVEL="TRACE")

    def test_webhook_path_validation(self):
        for value in ("webhook", "/", "/health", "/a/../b", "/a?b=c",
                      "/a#fragment", ""):
            with self.subTest(value=value):
                self._invalid(WA_WEBHOOK_PATH=value)

    def test_inbox_and_bind_validation(self):
        self.assertEqual(self._config(WA_INBOX="relative/path.jsonl").inbox,
                         Path("relative/path.jsonl"))
        self.assertEqual(self._config(WA_INBOX="/tmp/messages.jsonl").inbox,
                         Path("/tmp/messages.jsonl"))
        self._invalid(WA_INBOX="")
        self._invalid(WA_BIND="")


if __name__ == "__main__":
    unittest.main()
