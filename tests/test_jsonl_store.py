import json
import logging
import os
import stat
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX fallback
    fcntl = None

from jsonl_store import JsonlStore, StorageError, read_jsonl


def _record(message_id="wamid.test-1", text="Hello", sender="31600000000",
            name="Test User"):
    return {
        "ts": "2026-08-14T14:00:00+00:00",
        "message_id": message_id,
        "message_timestamp": "2026-08-14T13:59:58+00:00",
        "from": sender,
        "name": name,
        "type": "text",
        "text": text,
        "phone_number_id": "123456789",
        "raw": {"id": message_id, "type": "text", "body": text},
    }


class StoreInitializationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "inbox" / "messages.jsonl"

    def test_creates_parent_0700_and_file_0600(self):
        JsonlStore(self.path).initialize()
        self.assertTrue(self.path.exists())
        parent_mode = stat.S_IMODE(self.path.parent.stat().st_mode)
        file_mode = stat.S_IMODE(self.path.stat().st_mode)
        self.assertEqual(parent_mode, 0o700)
        self.assertEqual(file_mode, 0o600)

    def test_restricts_existing_modes(self):
        self.path.parent.mkdir(parents=True)
        self.path.parent.chmod(0o777)
        self.path.write_text("", encoding="utf-8")
        self.path.chmod(0o666)
        JsonlStore(self.path).initialize()
        self.assertEqual(stat.S_IMODE(self.path.parent.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)

    def test_empty_and_missing_reads(self):
        self.assertEqual(read_jsonl(self.path).records, [])
        self.assertEqual(read_jsonl(self.path).malformed_lines, 0)
        self.path.parent.mkdir()
        self.path.write_text("", encoding="utf-8")
        result = read_jsonl(self.path)
        self.assertEqual(result.records, [])
        self.assertEqual(result.malformed_lines, 0)

    def test_reads_utf8_jsonl(self):
        record = _record(text="Hé")
        self.path.parent.mkdir()
        self.path.write_text(json.dumps(record, ensure_ascii=False) + "\n",
                             encoding="utf-8")
        result = read_jsonl(self.path)
        self.assertEqual(result.records, [record])
        self.assertEqual(result.malformed_lines, 0)

    def test_skips_invalid_utf8_malformed_and_partial_lines_without_content_in_logs(self):
        self.path.parent.mkdir()
        secret_body = "PRIVATE_BODY_31600000000_Test User"
        self.path.write_bytes(
            json.dumps(_record("wamid.ok")).encode() + b"\n"
            + b"\xff\xfe\n"
            + b"{not-json}\n"
            + json.dumps({"message_id": "partial", "text": secret_body}).encode()
        )
        with self.assertLogs("jsonl_store", level="WARNING") as logs:
            result = read_jsonl(self.path)
        self.assertEqual([r["message_id"] for r in result.records], ["wamid.ok"])
        self.assertEqual(result.malformed_lines, 3)
        joined = "\n".join(logs.output)
        self.assertNotIn(secret_body, joined)
        self.assertNotIn("31600000000", joined)
        self.assertNotIn("Test User", joined)

    def test_rebuilds_existing_ids_for_restart(self):
        self.path.parent.mkdir()
        existing = _record("wamid.existing")
        self.path.write_text(json.dumps(existing) + "\n", encoding="utf-8")
        store = JsonlStore(self.path)
        store.initialize()
        result = store.append([existing, _record("wamid.new")])
        self.assertEqual(result.written, 1)
        self.assertEqual(result.duplicates, 1)
        records = read_jsonl(self.path).records
        self.assertEqual([r["message_id"] for r in records],
                         ["wamid.existing", "wamid.new"])


class StoreAppendTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "inbox" / "messages.jsonl"
        self.store = JsonlStore(self.path)
        self.store.initialize()

    def test_writes_one_atomic_utf8_batch(self):
        records = [_record("wamid.1", text="Hé"), _record("wamid.2")]
        result = self.store.append(records)
        self.assertEqual(result.written, 2)
        self.assertEqual(result.duplicates, 0)
        self.assertEqual(read_jsonl(self.path).records, records)

    def test_same_request_duplicate_is_suppressed(self):
        result = self.store.append([_record("wamid.1"), _record("wamid.1")])
        self.assertEqual(result.written, 1)
        self.assertEqual(result.duplicates, 1)
        self.assertEqual(len(read_jsonl(self.path).records), 1)

    def test_repeated_request_duplicate_is_suppressed(self):
        self.store.append([_record("wamid.1")])
        result = self.store.append([_record("wamid.1")])
        self.assertEqual(result.written, 0)
        self.assertEqual(result.duplicates, 1)
        self.assertEqual(len(read_jsonl(self.path).records), 1)

    def test_concurrent_threads_write_one_copy(self):
        barrier = threading.Barrier(6)
        results = []
        errors = []

        def worker():
            try:
                barrier.wait(timeout=5)
                results.append(self.store.append([_record("wamid.same")]))
            except Exception as exc:  # pragma: no cover - failure diagnostics
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for thread in threads:
            thread.start()
        barrier.wait(timeout=5)
        for thread in threads:
            thread.join(timeout=5)
        self.assertEqual(errors, [])
        self.assertEqual(sum(r.written for r in results), 1)
        self.assertEqual(sum(r.duplicates for r in results), 4)
        self.assertEqual(len(read_jsonl(self.path).records), 1)

    def test_restart_suppresses_existing_id(self):
        self.store.append([_record("wamid.1")])
        restarted = JsonlStore(self.path)
        restarted.initialize()
        result = restarted.append([_record("wamid.1"), _record("wamid.2")])
        self.assertEqual(result.written, 1)
        self.assertEqual(result.duplicates, 1)
        self.assertEqual([r["message_id"] for r in read_jsonl(self.path).records],
                         ["wamid.1", "wamid.2"])

    def test_output_is_stable_newline_delimited_json(self):
        self.store.append([_record("wamid.2"), _record("wamid.1")])
        data = self.path.read_bytes()
        self.assertTrue(data.endswith(b"\n"))
        lines = data.splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[0])["message_id"], "wamid.2")
        self.assertEqual(json.loads(lines[1])["message_id"], "wamid.1")
        self.assertNotIn(b"\n\n", data)

    def test_advisory_lock_covers_dedup_write_fsync_and_unlock(self):
        if fcntl is None:
            self.skipTest("fcntl is unavailable")
        events = []
        real_flock = fcntl.flock
        real_fsync = os.fsync

        def record_flock(fileobj, operation):
            if operation == fcntl.LOCK_EX:
                events.append("lock")
            elif operation == fcntl.LOCK_UN:
                events.append("unlock")
            return real_flock(fileobj, operation)

        def record_write(fileobj, data):
            events.append("write")
            return fileobj.write(data)

        def record_flush(fileobj):
            events.append("flush")
            return fileobj.flush()

        def record_fsync(fd):
            events.append("fsync")
            return real_fsync(fd)

        with mock.patch("jsonl_store.fcntl.flock", side_effect=record_flock), \
                mock.patch("jsonl_store._write_bytes", side_effect=record_write), \
                mock.patch("jsonl_store._flush_file", side_effect=record_flush), \
                mock.patch("os.fsync", side_effect=record_fsync):
            self.store.append([_record("wamid.locked")])

        self.assertLess(events.index("lock"), events.index("write"))
        self.assertLess(events.index("write"), events.index("flush"))
        self.assertLess(events.index("flush"), events.index("fsync"))
        self.assertLess(events.index("fsync"), events.index("unlock"))


class StoreFailureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "inbox" / "messages.jsonl"
        self.store = JsonlStore(self.path)
        self.store.initialize()
        self.store.append([_record("wamid.existing")])

    def test_write_flush_and_fsync_failures_roll_back_without_mutating_ids(self):
        faults = [
            ("write", "jsonl_store._write_bytes", OSError("write failed")),
            ("flush", "jsonl_store._flush_file", OSError("flush failed")),
            ("fsync", "os.fsync", OSError("fsync failed")),
        ]
        for label, target, exc in faults:
            with self.subTest(label=label):
                before = self.path.read_bytes()
                fresh = JsonlStore(self.path)
                fresh.initialize()
                if target == "os.fsync":
                    side_effect = [exc, None]
                else:
                    side_effect = exc
                with mock.patch(target, side_effect=side_effect):
                    with self.assertRaises(StorageError):
                        fresh.append([_record(f"wamid.{label}")])
                self.assertEqual(self.path.read_bytes(), before)
                result = fresh.append([_record(f"wamid.{label}")])
                self.assertEqual(result.written, 1)
                self.assertEqual(result.duplicates, 0)

    def test_corrupt_tail_is_separated_before_new_output(self):
        self.path.write_bytes(self.path.read_bytes() + b'{"partial": true')
        self.store.append([_record("wamid.after-tail")])
        data = self.path.read_bytes()
        self.assertIn(b'{"partial": true\n', data)
        result = read_jsonl(self.path)
        self.assertEqual(result.malformed_lines, 1)
        self.assertIn("wamid.after-tail",
                      [r["message_id"] for r in result.records])

    def test_parent_directory_sync_on_first_creation_where_supported(self):
        path = Path(self.tmp.name) / "new" / "messages.jsonl"
        real_open = os.open
        opened_dirs = []

        def record_open(name, flags, *args, **kwargs):
            fd = real_open(name, flags, *args, **kwargs)
            if Path(name) == path.parent:
                opened_dirs.append(name)
            return fd

        with mock.patch("os.open", side_effect=record_open):
            JsonlStore(path).initialize()
        if hasattr(os, "O_DIRECTORY"):
            self.assertEqual(opened_dirs, [path.parent])

    def test_rollback_failure_logs_critical_metadata_only(self):
        distinctive = _record(
            "wamid.private",
            text="PRIVATE_BODY_TOKEN",
            sender="31699999999",
            name="Private Name",
        )
        fresh = JsonlStore(self.path)
        fresh.initialize()
        with mock.patch("jsonl_store._flush_file", side_effect=OSError("flush failed")), \
                mock.patch("os.ftruncate", side_effect=OSError("truncate failed")), \
                self.assertLogs("jsonl_store", level="CRITICAL") as logs:
            with self.assertRaises(StorageError):
                fresh.append([distinctive])
        joined = "\n".join(logs.output)
        self.assertIn("CRITICAL", joined)
        self.assertNotIn("PRIVATE_BODY_TOKEN", joined)
        self.assertNotIn("31699999999", joined)
        self.assertNotIn("Private Name", joined)
        self.assertNotIn("wamid.private", joined)


if __name__ == "__main__":
    unittest.main()
