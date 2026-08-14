import hashlib
import hmac
from datetime import datetime, timezone

FIXED_TS = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
TEST_SECRET = "test-app-secret-32-characters-long"
VALID_TIMESTAMP = "1700000000"


def text_message(body="Hello", wamid="wamid.test-1", sender="31600000000",
                 timestamp=VALID_TIMESTAMP):
    return {
        "id": wamid,
        "from": sender,
        "type": "text",
        "timestamp": timestamp,
        "text": {"body": body},
    }


def webhook_payload(*messages, contacts=None, phone_number_id="123456789"):
    if not messages:
        messages = (text_message(),)

    value = {
        "messaging_product": "whatsapp",
        "metadata": {
            "display_phone_number": "15551234567",
            "phone_number_id": phone_number_id,
        },
        "messages": list(messages),
    }

    if contacts is None:
        seen = {}
        for msg in messages:
            wa_id = msg.get("from", "31600000000")
            if wa_id not in seen:
                suffix = wa_id[-4:] if isinstance(wa_id, str) else "0000"
                seen[wa_id] = {
                    "profile": {"name": f"Test User {suffix}"},
                    "wa_id": wa_id,
                }
        value["contacts"] = list(seen.values())
    else:
        value["contacts"] = contacts

    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "ENTRY_ID",
            "changes": [{
                "value": value,
                "field": "messages",
            }],
        }],
    }


def signed_headers(body: bytes, secret: str) -> dict[str, str]:
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return {"X-Hub-Signature-256": f"sha256={sig}"}
