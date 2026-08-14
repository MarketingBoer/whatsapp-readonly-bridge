import importlib.util
import io
import tempfile
import threading
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from bridge import create_server, load_config
from jsonl_store import JsonlStore
from tests.fixtures import FIXED_TS, TEST_SECRET


def _load_smoke():
    path = Path(__file__).resolve().parents[1] / "scripts" / "smoke-test.py"
    spec = importlib.util.spec_from_file_location("smoke_test_client", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SmokeClientTests(unittest.TestCase):
    def _server(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)
        config = replace(load_config({
            "WA_VERIFY_TOKEN": "test-verify-token",
            "WA_APP_SECRET": TEST_SECRET,
            "WA_INBOX": str(base / "messages.jsonl"),
        }, base), port=0)
        store = JsonlStore(config.inbox)
        store.initialize()
        server = create_server(config, store, clock=lambda: FIXED_TS)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join, 3)
        return server

    def test_health_verification_and_signed_dummy_message(self):
        server = self._server()
        smoke = _load_smoke()
        host, port = server.server_address[:2]
        code = smoke.main([
            "--base-url", f"http://{host}:{port}",
            "--verify-token", "test-verify-token",
            "--app-secret", TEST_SECRET,
        ])
        self.assertEqual(code, 0)

    def test_failure_is_nonzero_and_secrets_are_not_printed(self):
        smoke = _load_smoke()
        err = io.StringIO()
        with mock.patch("sys.stderr", err):
            code = smoke.main([
                "--base-url", "http://127.0.0.1:1",
                "--verify-token", "secret-verify-token",
                "--app-secret", "secret-app-secret",
            ])
        self.assertNotEqual(code, 0)
        self.assertNotIn("secret-verify-token", err.getvalue())
        self.assertNotIn("secret-app-secret", err.getvalue())


if __name__ == "__main__":
    unittest.main()
