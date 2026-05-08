"""
Example: expose the JSONL inbox as a simple JSON API.

WARNING: No authentication. For local/internal use only.
Do not expose to the internet without adding auth.

GET /messages           → last 20 messages
GET /messages?limit=50  → last 50 messages
GET /messages?from=316… → filter by phone
GET /stats              → inbox statistics

Run: python3 examples/api-server.py
"""
from __future__ import annotations
import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from reader import read_all
from stats import load_messages, compute_stats

API_PORT = int(os.environ.get("API_PORT", "3101"))


class APIHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if parsed.path == "/messages":
            messages = read_all()
            limit = min(int(params.get("limit", ["20"])[0]), 200)
            phone_filter = params.get("from", [None])[0]
            if phone_filter:
                messages = [m for m in messages if m.get("from") == phone_filter]
            messages = messages[-limit:]
            self._json_response({"messages": messages, "count": len(messages)})

        elif parsed.path == "/stats":
            messages = load_messages()
            stats = compute_stats(messages)
            self._json_response(stats)

        else:
            self._json_response({"error": "Not found", "endpoints": ["/messages", "/stats"]}, 404)

    def _json_response(self, data: dict, status: int = 200):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    print(f"[api] Inbox API on http://localhost:{API_PORT}")
    HTTPServer(("0.0.0.0", API_PORT), APIHandler).serve_forever()
