from __future__ import annotations
"""
Inbox statistics — show message counts, top contacts, activity by hour.

Usage:
    python3 stats.py                # full summary
    python3 stats.py --json         # machine-readable output
    python3 stats.py --days 7       # last 7 days only
"""
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta

INBOX_FILE = os.environ.get("WA_INBOX", "./inbox/messages.jsonl")


def load_messages(since: datetime | None = None) -> list[dict]:
    try:
        with open(INBOX_FILE) as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"No inbox found at {INBOX_FILE}")
        return []

    messages = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
            if since:
                ts = datetime.fromisoformat(msg["ts"]).replace(tzinfo=timezone.utc)
                if ts < since:
                    continue
            messages.append(msg)
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
    return messages


def compute_stats(messages: list[dict]) -> dict:
    if not messages:
        return {"total": 0}

    contacts = Counter()
    types = Counter()
    hours = Counter()
    daily = Counter()
    contact_names = {}

    for msg in messages:
        phone = msg.get("from", "unknown")
        contacts[phone] += 1
        types[msg.get("type", "text")] += 1

        if msg.get("name"):
            contact_names[phone] = msg["name"]

        try:
            ts = datetime.fromisoformat(msg["ts"])
            hours[ts.hour] += 1
            daily[ts.strftime("%Y-%m-%d")] += 1
        except (ValueError, KeyError):
            pass

    first_ts = messages[0].get("ts", "?")[:19]
    last_ts = messages[-1].get("ts", "?")[:19]

    top_contacts = []
    for phone, count in contacts.most_common(10):
        name = contact_names.get(phone)
        label = f"{name} ({phone})" if name else phone
        top_contacts.append({"contact": label, "messages": count})

    peak_hours = sorted(hours.items(), key=lambda x: -x[1])[:5]

    return {
        "total": len(messages),
        "unique_contacts": len(contacts),
        "first_message": first_ts,
        "last_message": last_ts,
        "message_types": dict(types.most_common()),
        "top_contacts": top_contacts,
        "peak_hours": [{"hour": f"{h:02d}:00", "messages": c} for h, c in peak_hours],
        "messages_per_day": dict(sorted(daily.items())),
    }


def print_stats(stats: dict):
    if stats["total"] == 0:
        print("No messages found.")
        return

    print(f"{'='*50}")
    print(f"  WhatsApp Inbox Statistics")
    print(f"{'='*50}")
    print(f"  Total messages:    {stats['total']}")
    print(f"  Unique contacts:   {stats['unique_contacts']}")
    print(f"  First message:     {stats['first_message']}")
    print(f"  Last message:      {stats['last_message']}")
    print()

    print("  Message types:")
    for msg_type, count in stats["message_types"].items():
        bar = "█" * min(count, 40)
        print(f"    {msg_type:<15} {count:>5}  {bar}")
    print()

    print("  Top contacts:")
    for item in stats["top_contacts"]:
        bar = "█" * min(item["messages"], 40)
        print(f"    {item['contact']:<30} {item['messages']:>5}  {bar}")
    print()

    print("  Peak hours:")
    for item in stats["peak_hours"]:
        bar = "█" * min(item["messages"], 40)
        print(f"    {item['hour']}  {item['messages']:>5}  {bar}")
    print()

    if stats["messages_per_day"]:
        print("  Daily activity:")
        for day, count in stats["messages_per_day"].items():
            bar = "█" * min(count, 40)
            print(f"    {day}  {count:>5}  {bar}")

    print(f"{'='*50}")


def main():
    args = sys.argv[1:]
    output_json = "--json" in args
    days = None

    i = 0
    while i < len(args):
        if args[i] == "--days" and i + 1 < len(args):
            days = int(args[i + 1])
            i += 2
        else:
            i += 1

    since = None
    if days:
        since = datetime.now(timezone.utc) - timedelta(days=days)

    messages = load_messages(since)
    stats = compute_stats(messages)

    if output_json:
        print(json.dumps(stats, indent=2, ensure_ascii=False))
    else:
        print_stats(stats)


if __name__ == "__main__":
    main()
