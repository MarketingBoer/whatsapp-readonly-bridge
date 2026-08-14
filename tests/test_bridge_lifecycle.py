import http.client
import json
import multiprocessing
import os
import signal
import tempfile
import threading
import time
import unittest
from dataclasses import replace
from pathlib import Path

from bridge import create_server, load_config, run_server
from jsonl_store import JsonlStore
from tests.fixtures import FIXED_TS, TEST_SECRET, signed_headers, text_message, webhook_payload


def _config(base: Path, **overrides):
    env = {
        "WA_VERIFY_TOKEN": "test-verify-token",
        "WA_APP_SECRET": TEST_SECRET,
        "WA_INBOX": str(base / "messages.jsonl"),
        "WA_REQUEST_TIMEOUT": "2",
        "WA_SHUTDOWN_TIMEOUT": "2",
    }
    env.update({k: str(v) for k, v in overrides.items()})
    return replace(load_config(env, base), port=0)


def _signed(payload):
    body = json.dumps(payload, separators=(",", ":")).encode()
    headers = signed_headers(body, TEST_SECRET)
    headers["Content-Type"] = "application/json"
    headers["Content-Length"] = str(len(body))
    return body, headers


class BlockingStore:
    def __init__(self, started, release):
        self.started = started
        self.release = release
        self.records = []

    def append(self, records):
        from jsonl_store import AppendResult
        self.started.set()
        if not self.release.wait(timeout=10):
            raise RuntimeError("release timeout")
        self.records.extend(records)
        return AppendResult(written=len(records), duplicates=0)


def _child(pipe, signum, release_on_parent, deadline=False):
    base = Path(tempfile.mkdtemp())
    config = _config(base, WA_SHUTDOWN_TIMEOUT="1" if deadline else "5")
    started = multiprocessing.Event()
    release = multiprocessing.Event()
    if not release_on_parent:
        release.set()
    store = BlockingStore(started, release)
    server = create_server(config, store, clock=lambda: FIXED_TS)
    pipe.send(("addr", server.server_address[:2]))
    pipe.send(("pid", os.getpid()))
    raise SystemExit(run_server(server, config.shutdown_timeout))


class BridgeLifecycleTests(unittest.TestCase):
    def test_threaded_server_sets_connection_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = _config(Path(tmp), WA_REQUEST_TIMEOUT="1")
            store = JsonlStore(config.inbox)
            store.initialize()
            server = create_server(config, store, clock=lambda: FIXED_TS)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                conn = http.client.HTTPConnection(*server.server_address[:2], timeout=3)
                conn.request("GET", "/health")
                self.assertEqual(conn.getresponse().status, 200)
                conn.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_health_already_accepted_returns_503_after_shutdown_begins(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = _config(Path(tmp))
            store = JsonlStore(config.inbox)
            store.initialize()
            server = create_server(config, store, clock=lambda: FIXED_TS)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                server._bridge_stopping = True
                conn = http.client.HTTPConnection(*server.server_address[:2], timeout=3)
                conn.request("GET", "/health")
                response = conn.getresponse()
                self.assertEqual(response.status, 503)
                conn.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_sigterm_drains_inflight_append_and_exits_zero(self):
        self._signal_drains(signal.SIGTERM)

    def test_sigint_uses_same_bounded_path(self):
        self._signal_drains(signal.SIGINT)

    def test_shutdown_deadline_exits_one(self):
        parent, child = multiprocessing.Pipe()
        proc = multiprocessing.Process(target=_child, args=(child, signal.SIGTERM, True, True))
        proc.start()
        kind, addr = parent.recv()
        self.assertEqual(kind, "addr")
        parent.recv()  # pid
        body, headers = _signed(webhook_payload(text_message()))
        client = threading.Thread(target=self._post_ignore_errors, args=(addr, body, headers), daemon=True)
        client.start()
        time.sleep(0.2)
        os.kill(proc.pid, signal.SIGTERM)
        proc.join(timeout=5)
        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=3)
        self.assertNotEqual(proc.exitcode, 0)

    def _signal_drains(self, signum):
        parent, child = multiprocessing.Pipe()
        proc = multiprocessing.Process(target=self._drain_child, args=(child,))
        proc.start()
        kind, addr = parent.recv()
        self.assertEqual(kind, "addr")
        body, headers = _signed(webhook_payload(text_message()))
        result = {}

        def client():
            conn = http.client.HTTPConnection(*addr, timeout=10)
            conn.request("POST", "/webhook", body=body, headers=headers)
            result["status"] = conn.getresponse().status
            conn.close()

        client_thread = threading.Thread(target=client)
        client_thread.start()
        self.assertEqual(parent.recv(), ("started", True))
        os.kill(proc.pid, signum)
        parent.send(("release", True))
        client_thread.join(timeout=10)
        proc.join(timeout=10)
        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=3)
        self.assertEqual(result.get("status"), 200)
        self.assertEqual(proc.exitcode, 0)

    @staticmethod
    def _drain_child(pipe):
        base = Path(tempfile.mkdtemp())
        config = _config(base, WA_SHUTDOWN_TIMEOUT="5")
        started = threading.Event()
        release = threading.Event()

        class Store:
            def append(self, records):
                from jsonl_store import AppendResult
                started.set()
                pipe.send(("started", True))
                while not release.is_set():
                    if pipe.poll(0.05):
                        msg = pipe.recv()
                        if msg == ("release", True):
                            release.set()
                return AppendResult(written=len(records), duplicates=0)

        server = create_server(config, Store(), clock=lambda: FIXED_TS)
        pipe.send(("addr", server.server_address[:2]))
        raise SystemExit(run_server(server, config.shutdown_timeout))

    @staticmethod
    def _post_ignore_errors(addr, body, headers):
        try:
            conn = http.client.HTTPConnection(*addr, timeout=5)
            conn.request("POST", "/webhook", body=body, headers=headers)
            conn.getresponse().read()
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    unittest.main()
