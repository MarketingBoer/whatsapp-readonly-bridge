from __future__ import annotations
"""Read or follow the local WhatsApp JSONL inbox."""

import argparse
import json
import os
from pathlib import Path
import sys
import time

from jsonl_store import read_jsonl


DEFAULT_INBOX = "./inbox/messages.jsonl"


def read_all(path: str | Path | None = None) -> list[dict]:
    result = read_jsonl(Path(path or os.environ.get("WA_INBOX", DEFAULT_INBOX)))
    return result.records


def format_message(msg: dict) -> str:
    ts = str(msg.get("ts", ""))[:19]
    phone = msg.get("from", "?")
    name = msg.get("name")
    sender = f"{name} ({phone})" if name else phone
    msg_type = msg.get("type", "text")
    indicator = "" if msg_type == "text" else f" [{msg_type}]"
    return f"{ts}  {sender}{indicator}: {msg.get('text', '')}"


def follow(path: str | Path, phone_filter: str | None = None,
           emit=print, sleep=time.sleep):
    path = Path(path)
    inode = None
    offset = 0
    buffer = b""
    while True:
        try:
            stat = path.stat()
        except FileNotFoundError:
            sleep(2)
            continue
        if inode != stat.st_ino or stat.st_size < offset:
            inode = stat.st_ino
            offset = 0
            buffer = b""
        with path.open("rb") as handle:
            handle.seek(offset)
            chunk = handle.read()
            offset = handle.tell()
        if chunk:
            buffer += chunk
            lines = buffer.split(b"\n")
            buffer = lines.pop()
            for raw in lines:
                if not raw:
                    continue
                try:
                    msg = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
                if phone_filter and msg.get("from") != phone_filter:
                    continue
                emit(msg)
        sleep(2)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inbox", default=os.environ.get("WA_INBOX", DEFAULT_INBOX))
    parser.add_argument("--last", type=int)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--from", dest="phone_filter")
    args = parser.parse_args(argv)

    if args.last is None:
        print(f"[reader] Tailing {args.inbox} (Ctrl+C to stop)")
        try:
            follow(args.inbox, args.phone_filter,
                   emit=lambda msg: print(format_message(msg)))
        except KeyboardInterrupt:
            return 0
        return 0

    messages = read_all(args.inbox)
    if args.phone_filter:
        messages = [m for m in messages if m.get("from") == args.phone_filter]
    for msg in messages[-max(args.last, 0):]:
        if args.json:
            print(json.dumps(msg, ensure_ascii=False))
        else:
            print(format_message(msg))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
