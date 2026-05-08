from __future__ import annotations
"""
Simple inbox reader — tail the JSONL inbox in real-time or query it.

Usage:
    python3 reader.py                # tail (follow) mode
    python3 reader.py --last 10      # show last 10 messages
    python3 reader.py --json         # output raw JSON
    python3 reader.py --from 31612345678  # filter by phone number
"""
import json
import os
import sys
import time
from datetime import datetime

INBOX_FILE = os.environ.get("WA_INBOX", "./inbox/messages.jsonl")


def read_all() -> list[dict]:
    try:
        with open(INBOX_FILE) as f:
            lines = f.readlines()
    except FileNotFoundError:
        return []

    messages = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            messages.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return messages


def format_message(msg: dict) -> str:
    ts = msg.get("ts", "")[:19]
    phone = msg.get("from", "?")
    name = msg.get("name")
    sender = f"{name} ({phone})" if name else phone
    msg_type = msg.get("type", "text")
    text = msg.get("text", "")

    type_indicator = "" if msg_type == "text" else f" [{msg_type}]"
    return f"{ts}  {sender}{type_indicator}: {text}"


def tail_mode(phone_filter: str | None = None):
    print(f"[reader] Tailing {INBOX_FILE} (Ctrl+C to stop)\n")
    seen = 0
    try:
        with open(INBOX_FILE) as f:
            lines = f.readlines()
            seen = len(lines)
            for line in lines[-5:]:
                msg = json.loads(line.strip())
                if phone_filter and msg.get("from") != phone_filter:
                    continue
                print(format_message(msg))
    except FileNotFoundError:
        pass

    print("---")
    while True:
        try:
            with open(INBOX_FILE) as f:
                lines = f.readlines()
            if len(lines) > seen:
                for line in lines[seen:]:
                    msg = json.loads(line.strip())
                    if phone_filter and msg.get("from") != phone_filter:
                        continue
                    print(format_message(msg))
                seen = len(lines)
            time.sleep(2)
        except FileNotFoundError:
            time.sleep(5)
        except KeyboardInterrupt:
            break


def main():
    args = sys.argv[1:]
    last_n = None
    raw_json = False
    phone_filter = None

    i = 0
    while i < len(args):
        if args[i] == "--last" and i + 1 < len(args):
            last_n = int(args[i + 1])
            i += 2
        elif args[i] == "--json":
            raw_json = True
            i += 1
        elif args[i] == "--from" and i + 1 < len(args):
            phone_filter = args[i + 1]
            i += 2
        else:
            i += 1

    if last_n is not None:
        messages = read_all()
        if phone_filter:
            messages = [m for m in messages if m.get("from") == phone_filter]
        for msg in messages[-last_n:]:
            if raw_json:
                print(json.dumps(msg, ensure_ascii=False))
            else:
                print(format_message(msg))
    else:
        tail_mode(phone_filter)


if __name__ == "__main__":
    main()
