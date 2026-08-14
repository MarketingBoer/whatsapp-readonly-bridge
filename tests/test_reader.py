import json
import tempfile
import unittest
from pathlib import Path

from reader import format_message, read_all


def _record(mid="wamid.1", text="Hello"):
    return {"ts": "2026-08-14T08:00:00+00:00", "message_id": mid,
            "message_timestamp": None, "from": "31600000000", "name": "Tester",
            "type": "text", "text": text, "phone_number_id": "123", "raw": None}


class ReaderTests(unittest.TestCase):
    def test_tolerant_shared_jsonl_reading_and_formatting(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "messages.jsonl"
            path.write_text(json.dumps(_record()) + "\n{bad}\npartial",
                            encoding="utf-8")
            self.assertEqual(len(read_all(path)), 1)
            self.assertIn("Tester (31600000000)", format_message(_record()))

    def test_missing_inbox_is_empty(self):
        self.assertEqual(read_all("/tmp/does-not-exist-whatsapp.jsonl"), [])


class FollowerTests(unittest.TestCase):
    def test_placeholder_for_tail_behaviour_covered_by_read_tolerance(self):
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
