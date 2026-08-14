from __future__ import annotations
"""Create and optionally send a periodic Telegram digest."""

import argparse
from collections import defaultdict
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import sys
import urllib.parse
import urllib.request

from jsonl_store import read_jsonl


DEFAULT_INBOX = "./inbox/messages.jsonl"
TELEGRAM_LIMIT = 4096


def parse_ts(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def load_messages(since: datetime, path: str | Path | None = None) -> list[dict]:
    since = since.astimezone(timezone.utc)
    records = read_jsonl(Path(path or os.environ.get("WA_INBOX", DEFAULT_INBOX))).records
    return [record for record in records
            if (ts := parse_ts(record.get("ts"))) is not None and ts >= since]


def format_digest(messages: list[dict]) -> str:
    if not messages:
        return "No new WhatsApp messages."
    by_contact = defaultdict(list)
    for msg in messages:
        phone = msg.get("from", "unknown")
        key = f"{msg.get('name')} ({phone})" if msg.get("name") else phone
        by_contact[key].append(msg)
    lines = [f"WhatsApp Digest - {len(messages)} messages", ""]
    for contact, msgs in by_contact.items():
        lines.append(contact)
        for msg in msgs:
            ts = parse_ts(msg.get("ts"))
            time_str = ts.strftime("%H:%M") if ts else "??:??"
            prefix = "" if msg.get("type") == "text" else f"[{msg.get('type', 'unknown')}] "
            lines.append(f"  [ ] {time_str} {prefix}{msg.get('text', '')}")
        lines.append("")
    lines.append("Reply in Telegram to discuss actions; this bridge never replies on WhatsApp.")
    return "\n".join(lines).rstrip()


def split_chunks(text: str, limit: int = TELEGRAM_LIMIT) -> list[str]:
    chunks = []
    remaining = text
    while len(remaining) > limit:
        cut = remaining.rfind("\n", 0, limit + 1)
        if cut <= 0:
            cut = limit
        chunks.append(remaining[:cut])
        remaining = remaining[cut:].lstrip("\n")
    chunks.append(remaining)
    return chunks


def send_telegram(text: str, token: str, chat_id: str) -> bool:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    for chunk in split_chunks(text):
        payload = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": chunk,
            "disable_web_page_preview": "true",
        }).encode("utf-8")
        request = urllib.request.Request(url, data=payload)
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                ok = 200 <= response.status < 300
                data = json.loads(response.read() or b"{}")
        except Exception:
            return False
        if not ok or not data.get("ok", False):
            return False
    return True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inbox", default=os.environ.get("WA_INBOX", DEFAULT_INBOX))
    parser.add_argument("--hours", type=float, default=1)
    parser.add_argument("--since")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if args.since:
        since = parse_ts(args.since)
        if since is None:
            print("invalid --since", file=sys.stderr)
            return 1
    else:
        since = datetime.now(timezone.utc) - timedelta(hours=args.hours)

    text = format_digest(load_messages(since, args.inbox))
    if args.dry_run:
        print(text)
        return 0

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        print(text)
        print("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to send to Telegram.",
              file=sys.stderr)
        return 1
    if not send_telegram(text, token, chat_id):
        print("Telegram send failed", file=sys.stderr)
        return 1
    print("Telegram digest sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
