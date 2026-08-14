"""Pure signature validation and payload normalization for Meta webhooks."""
from __future__ import annotations

import copy
import hashlib
import hmac
from datetime import datetime, timezone


class SignatureError(ValueError):
    pass


class PayloadError(ValueError):
    pass


def validate_signature(body: bytes, header: str | None, app_secret: str) -> None:
    """Raise SignatureError unless header authenticates the exact body."""
    if not header:
        raise SignatureError("missing signature header")

    parts = header.split("=", 1)
    if len(parts) != 2 or parts[0].lower() != "sha256":
        raise SignatureError("invalid signature scheme")

    hex_digest = parts[1]
    if len(hex_digest) != 64:
        raise SignatureError("invalid signature length")

    try:
        bytes.fromhex(hex_digest)
    except ValueError:
        raise SignatureError("invalid signature characters")

    expected = hmac.new(
        app_secret.encode(), body, hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, hex_digest.lower()):
        raise SignatureError("signature mismatch")


def _parse_timestamp(raw_ts: object) -> str | None:
    if raw_ts is None:
        return None
    try:
        ts = int(raw_ts)
    except (ValueError, TypeError):
        return None
    if ts < 0:
        return None
    try:
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    except (OSError, OverflowError, ValueError):
        return None
    return dt.isoformat()


def _summarize(msg: dict) -> str:
    msg_type = msg["type"]

    if msg_type == "text":
        sub = msg.get("text")
        if isinstance(sub, dict):
            body = sub.get("body")
            if isinstance(body, str) and body:
                return body
        return "[text]"

    if msg_type in ("image", "video"):
        sub = msg.get(msg_type)
        if isinstance(sub, dict):
            caption = sub.get("caption")
            if isinstance(caption, str) and caption:
                return caption
        return f"[{msg_type}]"

    if msg_type == "document":
        sub = msg.get("document")
        if isinstance(sub, dict):
            filename = sub.get("filename")
            if isinstance(filename, str) and filename:
                return f"[document: {filename}]"
        return "[document]"

    if msg_type in ("audio", "sticker", "order", "system"):
        return f"[{msg_type}]"

    if msg_type == "location":
        sub = msg.get("location")
        if isinstance(sub, dict):
            lat = sub.get("latitude")
            lon = sub.get("longitude")
            if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
                return f"[location: {lat},{lon}]"
        return "[location]"

    if msg_type == "contacts":
        sub = msg.get("contacts")
        if isinstance(sub, list) and sub:
            names = []
            for c in sub:
                if isinstance(c, dict):
                    name_obj = c.get("name")
                    if isinstance(name_obj, dict):
                        fn = name_obj.get("formatted_name")
                        if isinstance(fn, str) and fn:
                            names.append(fn)
            if names:
                return f"[contacts: {', '.join(names)}]"
        return "[contacts]"

    if msg_type == "interactive":
        sub = msg.get("interactive")
        if isinstance(sub, dict):
            for reply_key in ("button_reply", "list_reply"):
                reply = sub.get(reply_key)
                if isinstance(reply, dict):
                    title = reply.get("title")
                    if isinstance(title, str) and title:
                        return title
        return "[interactive]"

    if msg_type == "reaction":
        sub = msg.get("reaction")
        if isinstance(sub, dict):
            emoji = sub.get("emoji")
            if isinstance(emoji, str) and emoji:
                return emoji
        return "[reaction]"

    if msg_type == "button":
        sub = msg.get("button")
        if isinstance(sub, dict):
            text = sub.get("text")
            if isinstance(text, str) and text:
                return text
        return "[button]"

    return f"[{msg_type}]"


def _require_str(msg: dict, field: str) -> str:
    val = msg.get(field)
    if not isinstance(val, str) or not val:
        raise PayloadError(f"message {field} must be a non-empty string")
    return val


def parse_webhook(
    payload: object,
    received_at: datetime,
    store_raw: bool = True,
) -> list[dict[str, object]]:
    """Parse a Meta webhook payload into normalized records.

    Returns a list of dicts, each with exactly nine keys:
    ts, message_id, message_timestamp, from, name, type, text,
    phone_number_id, raw.

    Raises PayloadError for structural errors.
    """
    if not isinstance(payload, dict):
        raise PayloadError("payload must be a mapping")

    if payload.get("object") != "whatsapp_business_account":
        raise PayloadError("unexpected object type")

    entry = payload.get("entry")
    if not isinstance(entry, list):
        raise PayloadError("entry must be a list")

    records: list[dict[str, object]] = []
    ts_iso = received_at.isoformat()

    for e in entry:
        if not isinstance(e, dict):
            raise PayloadError("entry item must be a mapping")

        changes = e.get("changes")
        if not isinstance(changes, list):
            raise PayloadError("changes must be a list")

        for change in changes:
            if not isinstance(change, dict):
                raise PayloadError("change must be a mapping")

            value = change.get("value")
            if not isinstance(value, dict):
                raise PayloadError("value must be a mapping")

            if change.get("field") != "messages":
                continue

            messages = value.get("messages")
            if messages is None:
                continue

            if not isinstance(messages, list):
                raise PayloadError("messages must be a list")

            metadata = value.get("metadata")
            if metadata is not None and not isinstance(metadata, dict):
                raise PayloadError("metadata must be a mapping")

            phone_number_id = None
            if isinstance(metadata, dict):
                phone_number_id = metadata.get("phone_number_id")

            contacts_list = value.get("contacts")
            if contacts_list is not None:
                if not isinstance(contacts_list, list):
                    raise PayloadError("contacts must be a list")
                for c in contacts_list:
                    if not isinstance(c, dict):
                        raise PayloadError("contact must be a mapping")

            contact_names: dict[str, str | None] = {}
            if isinstance(contacts_list, list):
                for c in contacts_list:
                    wa_id = c.get("wa_id")
                    profile = c.get("profile")
                    if isinstance(profile, dict) and wa_id:
                        contact_names[wa_id] = profile.get("name")

            for msg in messages:
                if not isinstance(msg, dict):
                    raise PayloadError("message must be a mapping")
                _require_str(msg, "id")
                _require_str(msg, "from")
                _require_str(msg, "type")

            for msg in messages:
                msg_from = msg["from"]
                records.append({
                    "ts": ts_iso,
                    "message_id": msg["id"],
                    "message_timestamp": _parse_timestamp(msg.get("timestamp")),
                    "from": msg_from,
                    "name": contact_names.get(msg_from),
                    "type": msg["type"],
                    "text": _summarize(msg),
                    "phone_number_id": phone_number_id,
                    "raw": copy.deepcopy(msg) if store_raw else None,
                })

    return records
