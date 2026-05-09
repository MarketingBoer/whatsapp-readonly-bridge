#!/usr/bin/env python3
"""Forward WhatsApp messages to a Discord channel via webhook."""

import json, os, sys, urllib.request
from datetime import datetime, timedelta, timezone

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
INBOX = os.environ.get("WA_INBOX", "messages.jsonl")
HOURS = int(os.environ.get("DIGEST_HOURS", "1"))

def load_recent(path, hours):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    messages = []
    try:
        with open(path) as f:
            for line in f:
                msg = json.loads(line)
                ts = datetime.fromisoformat(msg["ts"])
                if ts >= cutoff:
                    messages.append(msg)
    except FileNotFoundError:
        return []
    return messages

def format_discord(messages):
    if not messages:
        return None
    lines = [f"**WhatsApp Digest — {len(messages)} messages**\n"]
    by_contact = {}
    for m in messages:
        key = m.get("name", m["from"])
        by_contact.setdefault(key, []).append(m)
    for contact, msgs in by_contact.items():
        lines.append(f"**{contact}**")
        for m in msgs:
            ts = datetime.fromisoformat(m["ts"]).strftime("%H:%M")
            text = m.get("text", f'[{m.get("type", "media")}]')
            lines.append(f"  {ts} — {text}")
        lines.append("")
    return "\n".join(lines)

def send(webhook_url, content):
    data = json.dumps({"content": content}).encode()
    req = urllib.request.Request(webhook_url, data, {"Content-Type": "application/json"})
    urllib.request.urlopen(req)

if __name__ == "__main__":
    if not WEBHOOK_URL:
        print("Set DISCORD_WEBHOOK_URL environment variable")
        sys.exit(1)
    body = format_discord(load_recent(INBOX, HOURS))
    if body:
        send(WEBHOOK_URL, body)
        print(f"Sent {len(body)} chars to Discord")
    else:
        print("No new messages")
