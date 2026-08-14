import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


def _load(rel, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DiscordExampleTests(unittest.TestCase):
    def test_dry_run_format_timeout_and_no_secret_output(self):
        discord = _load("examples/discord-webhook.py", "discord_example")
        self.assertEqual(discord.DEFAULT_INBOX, "./inbox/messages.jsonl")
        self.assertEqual(len(discord.split_chunks("x" * 2500)), 2)
        with mock.patch("urllib.request.Request") as req, \
                mock.patch("urllib.request.urlopen") as urlopen:
            self.assertEqual(discord.main(["--dry-run"]), 0)
        req.assert_not_called()
        urlopen.assert_not_called()
        with mock.patch("urllib.request.urlopen", side_effect=OSError("no")) as urlopen:
            self.assertFalse(discord.send("https://discord.example/private", "hello"))
        self.assertEqual(urlopen.call_args.args[0].full_url,
                         "https://discord.example/private")
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 10)


class APIExampleTests(unittest.TestCase):
    def test_loopback_default_no_wildcard_cors_and_limit_validation(self):
        api = _load("examples/api-server.py", "api_example")
        self.assertEqual(api.API_BIND, "127.0.0.1")
        text = (ROOT / "examples/api-server.py").read_text(encoding="utf-8")
        self.assertIn("WARNING", text)
        self.assertNotIn("Access-Control-Allow-Origin", text)


class ScriptAndGoldenTests(unittest.TestCase):
    def test_wrapper_mode_crontab_and_shell_syntax(self):
        wrapper = ROOT / "examples/run-telegram-digest.sh"
        self.assertTrue(os.access(wrapper, os.X_OK))
        output = subprocess.check_output(["bash", str(ROOT / "examples/cron-setup.sh")],
                                         text=True)
        jobs = [line for line in output.splitlines()
                if line.strip() and not line.startswith("#")]
        self.assertEqual(jobs, [
            "0 8 * * * /opt/whatsapp-readonly-bridge/examples/run-telegram-digest.sh --hours 24"
        ])
        self.assertEqual(len(jobs[0].split()[:5]), 5)
        self.assertIn("/etc/whatsapp-readonly-bridge-digest.env",
                      wrapper.read_text(encoding="utf-8"))

    def test_sample_records_have_nine_keys_and_golden_mentions_no_whatsapp_reply(self):
        keys = {"ts", "message_id", "message_timestamp", "from", "name", "type",
                "text", "phone_number_id", "raw"}
        for line in (ROOT / "examples/sample-inbox.jsonl").read_text(encoding="utf-8").splitlines():
            self.assertEqual(set(json.loads(line)), keys)
        golden = (ROOT / "examples/telegram-digest-example.txt").read_text(encoding="utf-8")
        self.assertIn("Reply in Telegram", golden)
        self.assertIn("never replies on WhatsApp", golden)


if __name__ == "__main__":
    unittest.main()
