"""Example local JSON API for the inbox.

WARNING: This example has no authentication. It binds to 127.0.0.1 by default
and is for local/internal use behind your own access controls only.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reader import read_all
from stats import compute_stats


API_BIND = os.environ.get("API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("API_PORT", "3101"))


class APIHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        if parsed.path == "/messages":
            limit_raw = params.get("limit", ["20"])[0]
            try:
                limit = int(limit_raw)
            except ValueError:
                self._json({"error": "invalid limit"}, 400)
                return
            if limit < 0:
                self._json({"error": "invalid limit"}, 400)
                return
            limit = min(max(limit, 1), 200)
            messages = read_all()
            phone = params.get("from", [None])[0]
            if phone:
                messages = [m for m in messages if m.get("from") == phone]
            messages = messages[-limit:]
            self._json({"messages": messages, "count": len(messages)})
            return
        if parsed.path == "/stats":
            self._json(compute_stats(read_all()))
            return
        self._json({"error": "not found", "endpoints": ["/messages", "/stats"]}, 404)

    def _json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        return


if __name__ == "__main__":
    print(f"[api] Local unauthenticated inbox API on http://{API_BIND}:{API_PORT}")
    HTTPServer((API_BIND, API_PORT), APIHandler).serve_forever()
