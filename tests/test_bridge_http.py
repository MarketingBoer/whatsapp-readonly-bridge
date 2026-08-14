import http.client
import json
import socket
import tempfile
import threading
import time
import unittest
from dataclasses import replace
from datetime import timezone
from pathlib import Path
from unittest import mock

from bridge import BridgeConfig, ConfigError, create_server, load_config, main
from jsonl_store import JsonlStore, StorageError, read_jsonl
from tests.fixtures import FIXED_TS, TEST_SECRET, signed_headers, text_message, webhook_payload


def _config(tmp: Path, **overrides) -> BridgeConfig:
    env = {
        "WA_VERIFY_TOKEN": "test-verify-token",
        "WA_APP_SECRET": TEST_SECRET,
        "WA_INBOX": str(tmp / "messages.jsonl"),
    }
    env.update({k: str(v) for k, v in overrides.items()})
    return replace(load_config(env, tmp), port=0)


class ServerHarness:
    def __init__(self, testcase, config=None, store=None):
        self.tmp = tempfile.TemporaryDirectory()
        testcase.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.config = config or _config(self.base)
        self.store = store or JsonlStore(self.config.inbox)
        self.store.initialize()
        self.server = create_server(self.config, self.store, clock=lambda: FIXED_TS)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        testcase.addCleanup(self.close)

    @property
    def address(self):
        host, port = self.server.server_address[:2]
        return host, port

    def request(self, method, path, body=None, headers=None, timeout=3):
        host, port = self.address
        conn = http.client.HTTPConnection(host, port, timeout=timeout)
        conn.request(method, path, body=body, headers=headers or {})
        response = conn.getresponse()
        data = response.read()
        conn.close()
        return response, data

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)


def _signed_body(payload):
    body = json.dumps(payload, separators=(",", ":")).encode()
    headers = signed_headers(body, TEST_SECRET)
    headers.update({"Content-Type": "application/json",
                    "Content-Length": str(len(body))})
    return body, headers


class BridgeRoutingTests(unittest.TestCase):
    def test_health_is_json_and_no_store(self):
        harness = ServerHarness(self)
        response, data = harness.request("GET", "/health")
        self.assertEqual(response.status, 200)
        self.assertEqual(response.getheader("Content-Type"), "application/json")
        self.assertEqual(response.getheader("Cache-Control"), "no-store")
        self.assertEqual(json.loads(data), {"status": "ok"})

    def test_verification_is_exact_utf8_text_plain_on_both_routes(self):
        harness = ServerHarness(self)
        for path in ("/webhook", "/webhook/whatsapp-cloud"):
            with self.subTest(path=path):
                response, data = harness.request(
                    "GET",
                    f"{path}?hub.mode=subscribe&hub.verify_token=test-verify-token&hub.challenge=h%C3%A9",
                )
                self.assertEqual(response.status, 200)
                self.assertEqual(response.getheader("Content-Type"), "text/plain; charset=utf-8")
                self.assertEqual(data, "hé".encode())

    def test_wrong_mode_or_token_is_403_json_no_store(self):
        harness = ServerHarness(self)
        for query in ("hub.mode=wrong&hub.verify_token=test-verify-token",
                      "hub.mode=subscribe&hub.verify_token=wrong"):
            response, _ = harness.request("GET", f"/webhook?{query}")
            self.assertEqual(response.status, 403)
            self.assertEqual(response.getheader("Cache-Control"), "no-store")

    def test_unknown_get_and_post_are_404_json_no_store_without_body_read(self):
        harness = ServerHarness(self)
        response, _ = harness.request("GET", "/unknown")
        self.assertEqual(response.status, 404)
        response, _ = harness.request("POST", "/unknown", body=b"x" * 10,
                                      headers={"Content-Length": "10"})
        self.assertEqual(response.status, 404)

    def test_custom_route_pair_works(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)
        config = _config(base, WA_WEBHOOK_PATH="/custom/")
        harness = ServerHarness(self, config=config)
        response, _ = harness.request(
            "GET",
            "/custom/whatsapp-cloud?hub.mode=subscribe&hub.verify_token=test-verify-token&hub.challenge=ok",
        )
        self.assertEqual(response.status, 200)


class BridgeFramingTests(unittest.TestCase):
    def test_framing_content_type_signature_and_bad_json_matrix(self):
        harness = ServerHarness(self)
        valid_body, valid_headers = _signed_body(webhook_payload(text_message()))
        cases = [
            (b"POST /webhook HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: chunked\r\nContent-Length: 0\r\nContent-Type: application/json\r\n\r\n", 400),
            (b"POST /webhook HTTP/1.1\r\nHost: x\r\nContent-Length: 1\r\nContent-Length: 1\r\nContent-Type: application/json\r\n\r\n{}", 400),
            (b"POST /webhook HTTP/1.1\r\nHost: x\r\nContent-Length: abc\r\nContent-Type: application/json\r\n\r\n", 400),
            (b"POST /webhook HTTP/1.1\r\nHost: x\r\nContent-Length: -1\r\nContent-Type: application/json\r\n\r\n", 400),
            (b"POST /webhook HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\n\r\n", 411),
        ]
        for raw, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(self._raw_status(harness, raw), expected)

        too_large_headers = dict(valid_headers)
        too_large_headers["Content-Length"] = str(3_145_729)
        response, _ = harness.request("POST", "/webhook", body=b"{}",
                                      headers=too_large_headers)
        self.assertEqual(response.status, 413)

        headers = dict(valid_headers)
        headers["Content-Type"] = "text/plain"
        response, _ = harness.request("POST", "/webhook", body=valid_body,
                                      headers=headers)
        self.assertEqual(response.status, 415)

        for header in (None, "sha1=" + "a" * 64, "sha256=abcd",
                       "sha256=" + "x" * 64, "sha256=" + "a" * 64):
            headers = dict(valid_headers)
            if header is None:
                headers.pop("X-Hub-Signature-256")
            else:
                headers["X-Hub-Signature-256"] = header
            response, _ = harness.request("POST", "/webhook", body=valid_body,
                                          headers=headers)
            self.assertEqual(response.status, 401)

        for body in (b"\xff", b"{not-json}", b"[]"):
            headers = signed_headers(body, TEST_SECRET)
            headers.update({"Content-Type": "application/json",
                            "Content-Length": str(len(body))})
            response, _ = harness.request("POST", "/webhook", body=body,
                                          headers=headers)
            self.assertEqual(response.status, 400)

    def test_timeout_and_short_body(self):
        harness = ServerHarness(self, config=replace(_config(Path(tempfile.mkdtemp())), request_timeout=1.0))
        host, port = harness.address
        with socket.create_connection((host, port), timeout=3) as sock:
            sock.sendall(b"POST /webhook HTTP/1.1\r\nHost: x\r\nContent-Length: 10\r\nContent-Type: application/json\r\nX-Hub-Signature-256: sha256=" + b"a" * 64 + b"\r\n\r\n{}")
            sock.shutdown(socket.SHUT_WR)
            data = sock.recv(1024)
        self.assertIn(b"400", data.split(b"\r\n", 1)[0])

    def _raw_status(self, harness, raw: bytes) -> int:
        host, port = harness.address
        with socket.create_connection((host, port), timeout=3) as sock:
            sock.sendall(raw)
            data = sock.recv(1024)
        return int(data.split(b" ", 2)[1])


class BridgePersistenceTests(unittest.TestCase):
    def test_signed_text_and_unknown_type_are_persisted_before_200(self):
        harness = ServerHarness(self)
        payload = webhook_payload(
            text_message("Hello", wamid="wamid.1"),
            {"id": "wamid.2", "from": "31600000001", "type": "new_type"},
        )
        body, headers = _signed_body(payload)
        response, data = harness.request("POST", "/webhook", body=body, headers=headers)
        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(data)["records"], 2)
        records = read_jsonl(harness.config.inbox).records
        self.assertEqual([r["message_id"] for r in records], ["wamid.1", "wamid.2"])
        self.assertEqual(records[1]["text"], "[new_type]")

    def test_status_only_returns_200_without_write(self):
        harness = ServerHarness(self)
        payload = {"object": "whatsapp_business_account", "entry": [
            {"changes": [{"field": "messages", "value": {"statuses": [{"id": "s"}]}}]}
        ]}
        body, headers = _signed_body(payload)
        response, data = harness.request("POST", "/webhook", body=body, headers=headers)
        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(data)["records"], 0)
        self.assertEqual(read_jsonl(harness.config.inbox).records, [])

    def test_later_malformed_message_has_zero_partial_write(self):
        harness = ServerHarness(self)
        bad = text_message("Bad", wamid="wamid.bad")
        del bad["from"]
        body, headers = _signed_body(webhook_payload(text_message("OK"), bad))
        response, _ = harness.request("POST", "/webhook", body=body, headers=headers)
        self.assertEqual(response.status, 400)
        self.assertEqual(read_jsonl(harness.config.inbox).records, [])

    def test_duplicate_returns_200_without_second_line(self):
        harness = ServerHarness(self)
        body, headers = _signed_body(webhook_payload(text_message("Hi")))
        self.assertEqual(harness.request("POST", "/webhook", body=body, headers=headers)[0].status, 200)
        response, data = harness.request("POST", "/webhook", body=body, headers=headers)
        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(data)["duplicates"], 1)
        self.assertEqual(len(read_jsonl(harness.config.inbox).records), 1)

    def test_storage_error_returns_500(self):
        class FailingStore:
            def initialize(self): pass
            def append(self, records):
                raise StorageError("boom")
        harness = ServerHarness(self, store=FailingStore())
        body, headers = _signed_body(webhook_payload(text_message()))
        response, _ = harness.request("POST", "/webhook", body=body, headers=headers)
        self.assertEqual(response.status, 500)


class BridgeStartupTests(unittest.TestCase):
    def test_store_initializes_before_server_bind(self):
        events = []
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        config = _config(Path(tmp.name))

        class Store(JsonlStore):
            def initialize(self):
                events.append("store")
                super().initialize()

        with mock.patch("bridge.ThreadingHTTPServer") as server_cls:
            server_cls.side_effect = lambda *a, **k: events.append("bind") or mock.Mock()
            with mock.patch("bridge.JsonlStore", Store):
                main_env = {
                    "WA_VERIFY_TOKEN": "test-verify-token",
                    "WA_APP_SECRET": TEST_SECRET,
                    "WA_INBOX": str(config.inbox),
                    "WA_PORT": "1",
                }
                with mock.patch.dict("os.environ", main_env, clear=True), \
                        mock.patch("bridge.run_server", return_value=0):
                    self.assertEqual(main(), 0)
        self.assertEqual(events, ["store", "bind"])

    def test_config_store_and_bind_failures_exit_one(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertEqual(main(), 1)

    def test_no_server_starts_on_import(self):
        with mock.patch("bridge.ThreadingHTTPServer") as server_cls:
            __import__("bridge")
            server_cls.assert_not_called()


class BridgeLoggingTests(unittest.TestCase):
    def test_every_response_has_expected_content_type_and_no_store(self):
        harness = ServerHarness(self)
        for method, path in (("GET", "/health"), ("GET", "/missing")):
            response, _ = harness.request(method, path)
            self.assertIsNotNone(response.getheader("Content-Type"))
            self.assertEqual(response.getheader("Cache-Control"), "no-store")

    def test_logs_exclude_all_secret_and_message_values(self):
        harness = ServerHarness(self)
        payload = webhook_payload(text_message("PRIVATE_BODY", sender="31699999999"))
        payload["entry"][0]["changes"][0]["value"]["contacts"][0]["profile"]["name"] = "Private Name"
        body, headers = _signed_body(payload)
        with self.assertLogs("bridge", level="INFO") as logs:
            response, _ = harness.request(
                "POST",
                "/webhook?token=test-verify-token&secret=query-secret",
                body=body,
                headers=headers,
            )
        self.assertEqual(response.status, 200)
        joined = "\n".join(logs.output)
        for forbidden in ("test-verify-token", TEST_SECRET, "query-secret",
                          "31699999999", "Private Name", "PRIVATE_BODY"):
            self.assertNotIn(forbidden, joined)
