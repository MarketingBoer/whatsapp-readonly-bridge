from __future__ import annotations
"""Compute local inbox statistics."""

import argparse
from collections import Counter
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path

from jsonl_store import read_jsonl


DEFAULT_INBOX = "./inbox/messages.jsonl"


def _parse_ts(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def load_messages(since: datetime | None = None,
                  path: str | Path | None = None) -> list[dict]:
    records = read_jsonl(Path(path or os.environ.get("WA_INBOX", DEFAULT_INBOX))).records
    if since is None:
        return records
    since = since.astimezone(timezone.utc)
    return [record for record in records
            if (ts := _parse_ts(record.get("ts"))) is not None and ts >= since]


def compute_stats(messages: list[dict]) -> dict:
    if not messages:
        return {"total": 0, "unique_contacts": 0, "message_types": {},
                "top_contacts": [], "peak_hours": [], "messages_per_day": {}}
    contacts = Counter()
    names = {}
    types = Counter()
    hours = Counter()
    days = Counter()
    for msg in messages:
        phone = msg.get("from", "unknown")
        contacts[phone] += 1
        if msg.get("name"):
            names[phone] = msg["name"]
        types[msg.get("type", "text")] += 1
        ts = _parse_ts(msg.get("ts"))
        if ts is not None:
            hours[ts.hour] += 1
            days[ts.date().isoformat()] += 1
    return {
        "total": len(messages),
        "unique_contacts": len(contacts),
        "first_message": str(messages[0].get("ts", ""))[:19],
        "last_message": str(messages[-1].get("ts", ""))[:19],
        "message_types": dict(types.most_common()),
        "top_contacts": [
            {"contact": f"{names[p]} ({p})" if p in names else p, "messages": c}
            for p, c in contacts.most_common(10)
        ],
        "peak_hours": [{"hour": f"{h:02d}:00", "messages": c}
                       for h, c in sorted(hours.items(), key=lambda item: -item[1])[:5]],
        "messages_per_day": dict(sorted(days.items())),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inbox", default=os.environ.get("WA_INBOX", DEFAULT_INBOX))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--days", type=float)
    args = parser.parse_args(argv)
    since = None
    if args.days is not None:
        since = datetime.now(timezone.utc) - timedelta(days=args.days)
    stats = compute_stats(load_messages(since, args.inbox))
    if args.json:
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    elif stats["total"] == 0:
        print("No messages found.")
    else:
        print(f"Total messages: {stats['total']}")
        print(f"Unique contacts: {stats['unique_contacts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
