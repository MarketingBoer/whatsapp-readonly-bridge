import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import digest


def _record(mid="wamid.1", text="Hello"):
    return {"ts": "2026-08-14T08:00:00+00:00", "message_id": mid,
            "message_timestamp": None, "from": "31600000000", "name": "Tester",
            "type": "text", "text": text, "phone_number_id": "123", "raw": None}


class DigestTests(unittest.TestCase):
    def test_dry_run_makes_zero_network_calls_even_with_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "messages.jsonl"
            path.write_text(json.dumps(_record()) + "\n", encoding="utf-8")
            out = io.StringIO()
            with mock.patch.dict(os.environ, {
                "TELEGRAM_BOT_TOKEN": "secret-token",
                "TELEGRAM_CHAT_ID": "secret-chat",
            }), mock.patch("urllib.request.Request") as req, \
                    mock.patch("urllib.request.urlopen") as urlopen, \
                    mock.patch("sys.stdout", out):
                code = digest.main(["--inbox", str(path), "--since",
                                    "2026-08-14T00:00:00+00:00", "--dry-run"])
        self.assertEqual(code, 0)
        req.assert_not_called()
        urlopen.assert_not_called()
        self.assertIn("WhatsApp Digest", out.getvalue())

    def test_timezone_cutoff_chunking_timeout_and_failure(self):
        text = "x" * 5000
        self.assertEqual(len(digest.split_chunks(text)), 2)
        with mock.patch("urllib.request.urlopen", side_effect=OSError("no")) as urlopen:
            self.assertFalse(digest.send_telegram("hello", "token", "chat"))
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 10)
        self.assertIsNotNone(digest.parse_ts("2026-08-14T10:00:00+02:00"))


if __name__ == "__main__":
    unittest.main()
