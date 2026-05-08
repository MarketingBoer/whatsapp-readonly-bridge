"""
WhatsApp Cloud API → JSONL readonly bridge.

Receives webhook events from the official Meta Cloud API,
extracts messages, and appends them to a local JSONL file.
Read-only by design: this bridge never sends messages.

Zero dependencies beyond Python 3.10+ stdlib.
"""
from __future__ import annotations
import json
import os
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

VERIFY_TOKEN = os.environ.get("WA_VERIFY_TOKEN", "change-me")
INBOX_FILE = os.environ.get("WA_INBOX", "./inbox/messages.jsonl")
PORT = int(os.environ.get("WA_PORT", "3100"))
WEBHOOK_PATH = os.environ.get("WA_WEBHOOK_PATH", "/webhook")


def append_message(entry: dict):
    os.makedirs(os.path.dirname(INBOX_FILE) or ".", exist_ok=True)
    with open(INBOX_FILE, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def extract_text(msg: dict) -> str:
    msg_type = msg.get("type", "text")
    if msg_type == "text":
        return msg.get("text", {}).get("body", "")
    if msg_type == "image":
        return msg.get("image", {}).get("caption", "[image]")
    if msg_type == "video":
        return msg.get("video", {}).get("caption", "[video]")
    if msg_type == "document":
        return msg.get("document", {}).get("filename", "[document]")
    if msg_type == "audio":
        return "[audio]"
    if msg_type == "sticker":
        return "[sticker]"
    if msg_type == "location":
        loc = msg.get("location", {})
        return f"[location: {loc.get('latitude')},{loc.get('longitude')}]"
    if msg_type == "contacts":
        contacts = msg.get("contacts", [{}])
        names = [c.get("name", {}).get("formatted_name", "?") for c in contacts]
        return f"[contacts: {', '.join(names)}]"
    if msg_type == "interactive":
        return json.dumps(msg.get("interactive", {}), ensure_ascii=False)
    if msg_type == "reaction":
        return msg.get("reaction", {}).get("emoji", "[reaction]")
    if msg_type == "button":
        return msg.get("button", {}).get("text", "[button]")
    return f"[{msg_type}]"


class WebhookHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {fmt % args}")

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
            return
        if parsed.path in (WEBHOOK_PATH, f"{WEBHOOK_PATH}/whatsapp-cloud"):
            params = parse_qs(parsed.query)
            mode = params.get("hub.mode", [""])[0]
            token = params.get("hub.verify_token", [""])[0]
            challenge = params.get("hub.challenge", [""])[0]
            if mode == "subscribe" and token == VERIFY_TOKEN:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(challenge.encode())
                print("[bridge] Webhook verification OK")
                return
        self.send_response(403)
        self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path not in (WEBHOOK_PATH, f"{WEBHOOK_PATH}/whatsapp-cloud"):
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        try:
            data = json.loads(body)
        except Exception:
            self.send_response(400)
            self.end_headers()
            return

        count = 0
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                for msg in value.get("messages", []):
                    phone = msg.get("from", "unknown")
                    msg_type = msg.get("type", "text")
                    text = extract_text(msg)

                    record = {
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "from": phone,
                        "type": msg_type,
                        "text": text,
                        "name": value.get("contacts", [{}])[0]
                            .get("profile", {}).get("name"),
                        "raw": msg,
                    }
                    append_message(record)
                    count += 1
                    print(f"[bridge] +{phone} ({msg_type}): {text[:80]}")

        self.send_response(200)
        self.end_headers()
        self.wfile.write(f"{count} messages received".encode())


if __name__ == "__main__":
    print(f"[bridge] WhatsApp readonly bridge on port {PORT}")
    print(f"[bridge] Inbox: {INBOX_FILE}")
    print(f"[bridge] Webhook path: {WEBHOOK_PATH}")
    server = HTTPServer(("0.0.0.0", PORT), WebhookHandler)
    server.serve_forever()
