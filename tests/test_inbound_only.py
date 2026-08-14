import http.client
import json
import re
import socket
import tempfile
import threading
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from bridge import create_server, load_config
from jsonl_store import JsonlStore, read_jsonl
from tests.fixtures import FIXED_TS, TEST_SECRET, signed_headers, text_message, webhook_payload


class InboundOnlyTests(unittest.TestCase):
    def test_signed_inbound_path_makes_no_outbound_calls(self):
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

        body = json.dumps(webhook_payload(text_message()),
                          separators=(",", ":")).encode()
        headers = signed_headers(body, TEST_SECRET)
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(body))

        with mock.patch("urllib.request.urlopen") as urlopen, \
                mock.patch("socket.create_connection", wraps=socket.create_connection) as create_connection, \
                mock.patch("http.client.HTTPConnection.request") as http_request:
            host, port = server.server_address[:2]
            with socket.socket() as sock:
                sock.settimeout(3)
                sock.connect((host, port))
                raw_headers = "".join(f"{k}: {v}\r\n" for k, v in headers.items())
                sock.sendall(b"POST /webhook HTTP/1.1\r\nHost: local\r\n" +
                             raw_headers.encode() + b"\r\n" + body)
                response = sock.recv(1024)
            self.assertIn(b" 200 ", response.split(b"\r\n", 1)[0])
            urlopen.assert_not_called()
            http_request.assert_not_called()
            create_connection.assert_not_called()

        self.assertEqual(len(read_jsonl(config.inbox).records), 1)

    def test_core_source_has_no_graph_send_or_access_token_boundary(self):
        pattern = re.compile(
            r"graph\.facebook\.com|access[_-]?token|urllib\.request|urlopen|"
            r"HTTPConnection|send.*whatsapp|reply.*whatsapp",
            re.IGNORECASE,
        )
        root = Path(__file__).resolve().parents[1]
        files = [
            "bridge.py",
            "whatsapp_webhook.py",
            "jsonl_store.py",
            "reader.py",
            "stats.py",
            "examples/api-server.py",
        ]
        matches = []
        for rel in files:
            text = (root / rel).read_text(encoding="utf-8")
            for line_no, line in enumerate(text.splitlines(), start=1):
                if pattern.search(line):
                    matches.append(f"{rel}:{line_no}:{line}")
        self.assertEqual(matches, [])


if __name__ == "__main__":
    unittest.main()
