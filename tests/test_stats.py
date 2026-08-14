import json
import tempfile
import unittest
from pathlib import Path

from stats import compute_stats, load_messages


class StatsTests(unittest.TestCase):
    def test_json_stats_for_absent_and_timezone_aware_messages(self):
        self.assertEqual(load_messages(path="/tmp/no-such-inbox.jsonl"), [])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "messages.jsonl"
            path.write_text(json.dumps({
                "ts": "2026-08-14T10:00:00+02:00",
                "message_id": "wamid.1",
                "from": "31600000000",
                "name": None,
                "type": "text",
                "text": "Hi",
            }) + "\n", encoding="utf-8")
            stats = compute_stats(load_messages(path=path))
        self.assertEqual(stats["total"], 1)
        self.assertEqual(stats["peak_hours"], [{"hour": "08:00", "messages": 1}])


if __name__ == "__main__":
    unittest.main()
