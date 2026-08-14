#!/usr/bin/env python3
"""Send a periodic WhatsApp JSONL digest to Discord."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
import argparse
import json
import os
from pathlib import Path
import sys
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jsonl_store import read_jsonl

DEFAULT_INBOX = "./inbox/messages.jsonl"
DISCORD_LIMIT = 2000


def _parse_ts(value):
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def load_recent(path, hours):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    return [msg for msg in read_jsonl(Path(path)).records
            if (ts := _parse_ts(msg.get("ts"))) is not None
            and ts.astimezone(timezone.utc) >= cutoff]


def format_discord(messages):
    if not messages:
        return "No new WhatsApp messages."
    lines = [f"WhatsApp Digest - {len(messages)} messages", ""]
    for msg in messages:
        ts = _parse_ts(msg.get("ts"))
        when = ts.strftime("%H:%M") if ts else "??:??"
        who = msg.get("name") or msg.get("from", "unknown")
        lines.append(f"{when} - {who}: {msg.get('text', '')}")
    lines.append("")
    lines.append("Periodic summary only; this bridge never replies on WhatsApp.")
    return "\n".join(lines)


def split_chunks(text, limit=DISCORD_LIMIT):
    return [text[i:i + limit] for i in range(0, len(text), limit)] or [""]


def send(webhook_url, content):
    for chunk in split_chunks(content):
        data = json.dumps({"content": chunk}).encode("utf-8")
        req = urllib.request.Request(webhook_url, data,
                                     {"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status < 200 or response.status >= 300:
                    return False
                body = response.read()
        except Exception:
            return False
        if body:
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                payload = {}
            if payload.get("code") or payload.get("message") == "error":
                return False
    return True


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--inbox", default=os.environ.get("WA_INBOX", DEFAULT_INBOX))
    parser.add_argument("--hours", type=float, default=float(os.environ.get("DIGEST_HOURS", "1")))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    body = format_discord(load_recent(args.inbox, args.hours))
    if args.dry_run:
        print(body)
        return 0
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "")
    if not webhook_url:
        print("Set DISCORD_WEBHOOK_URL", file=sys.stderr)
        return 1
    if not send(webhook_url, body):
        print("Discord send failed", file=sys.stderr)
        return 1
    print("Discord digest sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
