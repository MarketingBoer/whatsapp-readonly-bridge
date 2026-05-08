"""
Telegram digest — reads the JSONL inbox and posts a summary to Telegram.

Run on a schedule (cron, systemd timer) or manually:
    python3 digest.py                   # last hour
    python3 digest.py --hours 24        # last 24 hours
    python3 digest.py --since 2026-05-01

Each message becomes a checklist item. Your team discusses and
resolves them right inside Telegram — no extra app needed.
"""
import json
import os
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from collections import defaultdict

INBOX_FILE = os.environ.get("WA_INBOX", "./inbox/messages.jsonl")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


def load_messages(since: datetime) -> list[dict]:
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
            msg = json.loads(line)
            ts = datetime.fromisoformat(msg["ts"]).replace(tzinfo=timezone.utc)
            if ts >= since:
                messages.append(msg)
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
    return messages


def format_digest(messages: list[dict]) -> str:
    if not messages:
        return "📭 No new WhatsApp messages."

    by_contact = defaultdict(list)
    for msg in messages:
        phone = msg.get("from", "unknown")
        name = msg.get("name") or phone
        key = f"{name} ({phone})" if msg.get("name") else phone
        by_contact[key].append(msg)

    lines = [f"📱 *WhatsApp Digest* — {len(messages)} messages\n"]

    for contact, msgs in by_contact.items():
        lines.append(f"\n👤 *{_escape_md(contact)}*")
        for msg in msgs:
            ts = datetime.fromisoformat(msg["ts"])
            time_str = ts.strftime("%H:%M")
            text = msg.get("text", "")[:120]
            emoji = _type_emoji(msg.get("type", "text"))
            lines.append(f"  ☐ `{time_str}` {emoji} {_escape_md(text)}")

    lines.append(f"\n_Reply to this message to discuss actions\\._")
    return "\n".join(lines)


def _type_emoji(msg_type: str) -> str:
    return {
        "text": "💬",
        "image": "📷",
        "video": "🎥",
        "audio": "🎤",
        "document": "📄",
        "location": "📍",
        "contacts": "👥",
        "sticker": "🏷",
        "reaction": "❤️",
    }.get(msg_type, "📨")


def _escape_md(text: str) -> str:
    for char in ("_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"):
        text = text.replace(char, f"\\{char}")
    return text


def send_telegram(text: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(text)
        print("\n[digest] Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to send to Telegram.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = urllib.parse.urlencode({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "MarkdownV2",
        "disable_web_page_preview": "true",
    }).encode()

    req = urllib.request.Request(url, data=payload)
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
            if result.get("ok"):
                print(f"[digest] Sent to Telegram chat {TELEGRAM_CHAT_ID}")
                return True
            print(f"[digest] Telegram API error: {result}")
            return False
    except Exception as e:
        print(f"[digest] Failed to send: {e}")
        return False


def main():
    hours = 1
    since = None

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--hours" and i + 1 < len(args):
            hours = float(args[i + 1])
            i += 2
        elif args[i] == "--since" and i + 1 < len(args):
            since = datetime.fromisoformat(args[i + 1]).replace(tzinfo=timezone.utc)
            i += 2
        elif args[i] == "--dry-run":
            os.environ.pop("TELEGRAM_BOT_TOKEN", None)
            i += 1
        else:
            i += 1

    if since is None:
        since = datetime.now(timezone.utc) - timedelta(hours=hours)

    messages = load_messages(since)
    digest = format_digest(messages)
    send_telegram(digest)


if __name__ == "__main__":
    main()
