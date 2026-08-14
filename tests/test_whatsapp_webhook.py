import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from tests.fixtures import (
    FIXED_TS,
    TEST_SECRET,
    VALID_TIMESTAMP,
    signed_headers,
    text_message,
    webhook_payload,
)
from whatsapp_webhook import (
    PayloadError,
    SignatureError,
    parse_webhook,
    validate_signature,
)


# ---------------------------------------------------------------------------
# Helper for building non-text message dicts in summary tests
# ---------------------------------------------------------------------------

def _msg(msg_type, wamid="wamid.test-1", sender="31600000000",
         timestamp=VALID_TIMESTAMP, **extra):
    msg = {
        "id": wamid,
        "from": sender,
        "type": msg_type,
        "timestamp": timestamp,
    }
    msg.update(extra)
    return msg


# ===================================================================
# Signature validation
# ===================================================================

class SignatureTests(unittest.TestCase):

    def test_accepts_valid_signature_for_exact_raw_bytes(self):
        body = b'{"test": true}'
        headers = signed_headers(body, TEST_SECRET)
        validate_signature(body, headers["X-Hub-Signature-256"], TEST_SECRET)

    def test_accepts_uppercase_hex(self):
        body = b'{"test": true}'
        headers = signed_headers(body, TEST_SECRET)
        scheme, hexdig = headers["X-Hub-Signature-256"].split("=", 1)
        upper_sig = f"{scheme}={hexdig.upper()}"
        validate_signature(body, upper_sig, TEST_SECRET)

    def test_rejects_changed_body(self):
        body = b'{"test": true}'
        headers = signed_headers(body, TEST_SECRET)
        with self.assertRaises(SignatureError):
            validate_signature(b'{"test": false}',
                               headers["X-Hub-Signature-256"], TEST_SECRET)

    def test_rejects_missing_wrong_scheme_wrong_length_non_hex_and_mismatch(self):
        body = b'{"test": true}'
        with self.assertRaises(SignatureError):
            validate_signature(body, None, TEST_SECRET)
        with self.assertRaises(SignatureError):
            validate_signature(body, "sha1=" + "a" * 64, TEST_SECRET)
        with self.assertRaises(SignatureError):
            validate_signature(body, "sha256=abcd", TEST_SECRET)
        with self.assertRaises(SignatureError):
            validate_signature(body, "sha256=" + "x" * 64, TEST_SECRET)
        with self.assertRaises(SignatureError):
            validate_signature(body, "sha256=" + "a" * 64, TEST_SECRET)

    def test_well_formed_signature_uses_compare_digest(self):
        body = b'{"test": true}'
        headers = signed_headers(body, TEST_SECRET)
        with patch("whatsapp_webhook.hmac.compare_digest",
                   return_value=True) as mock_cd:
            validate_signature(body, headers["X-Hub-Signature-256"], TEST_SECRET)
            mock_cd.assert_called_once()


# ===================================================================
# Parser — stable record schema
# ===================================================================

class ParserSchemaTests(unittest.TestCase):

    SCHEMA_KEYS = frozenset({
        "ts", "message_id", "message_timestamp", "from", "name",
        "type", "text", "phone_number_id", "raw",
    })

    def test_normalizes_text_to_exact_nine_key_schema(self):
        payload = webhook_payload(text_message("Hi"))
        records = parse_webhook(payload, FIXED_TS)
        self.assertEqual(len(records), 1)
        r = records[0]
        self.assertEqual(set(r.keys()), self.SCHEMA_KEYS)
        self.assertEqual(r["ts"], FIXED_TS.isoformat())
        self.assertEqual(r["message_id"], "wamid.test-1")
        self.assertEqual(r["from"], "31600000000")
        self.assertEqual(r["type"], "text")
        self.assertEqual(r["text"], "Hi")
        self.assertEqual(r["phone_number_id"], "123456789")
        self.assertIsNotNone(r["message_timestamp"])
        self.assertIsNotNone(r["name"])
        self.assertIsNotNone(r["raw"])

    def test_multi_entry_multi_message_preserves_order(self):
        msg1 = text_message("First", wamid="wamid.1", sender="31600000001")
        msg2 = text_message("Second", wamid="wamid.2", sender="31600000002")
        msg3 = text_message("Third", wamid="wamid.3", sender="31600000003")
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {"id": "E1", "changes": [{"field": "messages", "value": {
                    "metadata": {"phone_number_id": "111"},
                    "messages": [msg1],
                    "contacts": [{"wa_id": "31600000001",
                                  "profile": {"name": "User1"}}],
                }}]},
                {"id": "E2", "changes": [{"field": "messages", "value": {
                    "metadata": {"phone_number_id": "222"},
                    "messages": [msg2, msg3],
                    "contacts": [
                        {"wa_id": "31600000002",
                         "profile": {"name": "User2"}},
                        {"wa_id": "31600000003",
                         "profile": {"name": "User3"}},
                    ],
                }}]},
            ],
        }
        records = parse_webhook(payload, FIXED_TS)
        self.assertEqual(len(records), 3)
        self.assertEqual(records[0]["message_id"], "wamid.1")
        self.assertEqual(records[1]["message_id"], "wamid.2")
        self.assertEqual(records[2]["message_id"], "wamid.3")

    def test_matches_contact_name_by_wa_id(self):
        msg_a = text_message("A", wamid="wamid.a", sender="31600000001")
        msg_b = text_message("B", wamid="wamid.b", sender="31600000002")
        contacts = [
            {"wa_id": "31600000002", "profile": {"name": "Bob"}},
            {"wa_id": "31600000001", "profile": {"name": "Alice"}},
        ]
        payload = webhook_payload(msg_a, msg_b, contacts=contacts)
        records = parse_webhook(payload, FIXED_TS)
        self.assertEqual(records[0]["name"], "Alice")
        self.assertEqual(records[1]["name"], "Bob")

    def test_missing_contacts_metadata_and_captions_are_tolerated(self):
        msg = text_message("Hi")
        payload = webhook_payload(msg)
        value = payload["entry"][0]["changes"][0]["value"]
        del value["contacts"]
        del value["metadata"]
        records = parse_webhook(payload, FIXED_TS)
        self.assertEqual(len(records), 1)
        self.assertIsNone(records[0]["name"])
        self.assertIsNone(records[0]["phone_number_id"])

    def test_invalid_missing_negative_and_out_of_range_timestamps_are_none(self):
        cases = [
            ("abc", "non-numeric"),
            ("", "empty string"),
            ("-1", "negative"),
            ("99999999999999", "out of range"),
        ]
        for ts_val, label in cases:
            with self.subTest(label=label):
                msg = text_message("Hi", timestamp=ts_val)
                payload = webhook_payload(msg)
                records = parse_webhook(payload, FIXED_TS)
                self.assertIsNone(records[0]["message_timestamp"],
                                  f"Expected None for {label}")

        msg_no_ts = text_message("Hi")
        del msg_no_ts["timestamp"]
        payload = webhook_payload(msg_no_ts)
        records = parse_webhook(payload, FIXED_TS)
        self.assertIsNone(records[0]["message_timestamp"],
                          "Expected None for missing key")

    def test_raw_false_keeps_raw_key_as_none(self):
        payload = webhook_payload(text_message("Hi"))
        records = parse_webhook(payload, FIXED_TS, store_raw=False)
        self.assertEqual(len(records), 1)
        self.assertIn("raw", records[0])
        self.assertIsNone(records[0]["raw"])

    def test_raw_is_a_defensive_copy(self):
        msg = text_message("Hi")
        payload = webhook_payload(msg)
        records = parse_webhook(payload, FIXED_TS, store_raw=True)
        original_raw = records[0]["raw"]
        payload["entry"][0]["changes"][0]["value"]["messages"][0]["text"]["body"] = "Changed"
        self.assertEqual(original_raw["text"]["body"], "Hi")


# ===================================================================
# Parser — malformed and non-message payloads
# ===================================================================

class PayloadShapeTests(unittest.TestCase):

    def test_rejects_scalar_wrong_object_and_non_list_entry(self):
        with self.assertRaises(PayloadError):
            parse_webhook("scalar", FIXED_TS)
        with self.assertRaises(PayloadError):
            parse_webhook(42, FIXED_TS)
        with self.assertRaises(PayloadError):
            parse_webhook({"object": "instagram", "entry": []}, FIXED_TS)
        with self.assertRaises(PayloadError):
            parse_webhook({"object": "whatsapp_business_account",
                           "entry": "not_a_list"}, FIXED_TS)

    def test_rejects_malformed_entry_change_and_value_containers(self):
        base = {"object": "whatsapp_business_account"}
        with self.assertRaises(PayloadError):
            parse_webhook({**base, "entry": ["not_a_dict"]}, FIXED_TS)
        with self.assertRaises(PayloadError):
            parse_webhook({**base, "entry": [{"changes": "not_a_list"}]},
                          FIXED_TS)
        with self.assertRaises(PayloadError):
            parse_webhook({**base, "entry": [{"changes": ["not_a_dict"]}]},
                          FIXED_TS)
        with self.assertRaises(PayloadError):
            parse_webhook({**base, "entry": [{"changes": [
                {"value": "not_a_dict", "field": "messages"}
            ]}]}, FIXED_TS)

    def test_status_only_and_non_messages_changes_yield_no_records(self):
        status_payload = {
            "object": "whatsapp_business_account",
            "entry": [{"id": "E1", "changes": [{"field": "messages", "value": {
                "messaging_product": "whatsapp",
                "metadata": {"phone_number_id": "123"},
                "statuses": [{"id": "wamid.s1", "status": "delivered"}],
            }}]}],
        }
        self.assertEqual(parse_webhook(status_payload, FIXED_TS), [])

        non_msg_payload = {
            "object": "whatsapp_business_account",
            "entry": [{"id": "E1", "changes": [{"field": "account_update",
                        "value": {"ban_info": {}}}]}],
        }
        self.assertEqual(parse_webhook(non_msg_payload, FIXED_TS), [])

    def test_empty_messages_yields_no_records(self):
        payload = webhook_payload()
        payload["entry"][0]["changes"][0]["value"]["messages"] = []
        self.assertEqual(parse_webhook(payload, FIXED_TS), [])

    def test_rejects_non_list_messages_metadata_and_contacts(self):
        p1 = webhook_payload()
        p1["entry"][0]["changes"][0]["value"]["messages"] = "bad"
        with self.assertRaises(PayloadError):
            parse_webhook(p1, FIXED_TS)

        p2 = webhook_payload()
        p2["entry"][0]["changes"][0]["value"]["metadata"] = "bad"
        with self.assertRaises(PayloadError):
            parse_webhook(p2, FIXED_TS)

        p3 = webhook_payload()
        p3["entry"][0]["changes"][0]["value"]["contacts"] = "bad"
        with self.assertRaises(PayloadError):
            parse_webhook(p3, FIXED_TS)

    def test_rejects_non_mapping_contacts(self):
        payload = webhook_payload()
        payload["entry"][0]["changes"][0]["value"]["contacts"] = ["not_a_dict"]
        with self.assertRaises(PayloadError):
            parse_webhook(payload, FIXED_TS)

    def test_rejects_missing_empty_and_non_string_required_message_fields(self):
        for field in ("id", "from", "type"):
            with self.subTest(field=field, case="missing"):
                msg = text_message()
                del msg[field]
                with self.assertRaises(PayloadError):
                    parse_webhook(webhook_payload(msg), FIXED_TS)
            with self.subTest(field=field, case="empty"):
                msg = text_message()
                msg[field] = ""
                with self.assertRaises(PayloadError):
                    parse_webhook(webhook_payload(msg), FIXED_TS)
            with self.subTest(field=field, case="non-string"):
                msg = text_message()
                msg[field] = 12345
                with self.assertRaises(PayloadError):
                    parse_webhook(webhook_payload(msg), FIXED_TS)

    def test_later_malformed_message_rejects_complete_batch(self):
        good = text_message("OK", wamid="wamid.good")
        bad = text_message("Bad", wamid="wamid.bad")
        del bad["from"]
        payload = webhook_payload(good, bad)
        with self.assertRaises(PayloadError):
            parse_webhook(payload, FIXED_TS)


# ===================================================================
# Summary / type normalization
# ===================================================================

class SummaryTests(unittest.TestCase):

    def _parse_single(self, msg):
        payload = webhook_payload(msg)
        records = parse_webhook(payload, FIXED_TS)
        self.assertEqual(len(records), 1)
        return records[0]["text"]

    def test_fixed_summary_matrix(self):
        cases = [
            (text_message("Hello"), "Hello"),
            (_msg("image", image={"caption": "Nice pic"}), "Nice pic"),
            (_msg("image", image={"mime_type": "image/jpeg"}), "[image]"),
            (_msg("video", video={"caption": "My vid"}), "My vid"),
            (_msg("video", video={}), "[video]"),
            (_msg("document", document={"filename": "report.pdf"}),
             "[document: report.pdf]"),
            (_msg("document", document={}), "[document]"),
            (_msg("audio"), "[audio]"),
            (_msg("sticker"), "[sticker]"),
            (_msg("order"), "[order]"),
            (_msg("system"), "[system]"),
            (_msg("location", location={"latitude": 52.3676,
                                        "longitude": 4.9041}),
             "[location: 52.3676,4.9041]"),
            (_msg("location", location={}), "[location]"),
            (_msg("contacts", contacts=[
                {"name": {"formatted_name": "Alice"}},
                {"name": {"formatted_name": "Bob"}},
            ]), "[contacts: Alice, Bob]"),
            (_msg("contacts", contacts=[]), "[contacts]"),
            (_msg("interactive", interactive={
                "type": "button_reply",
                "button_reply": {"id": "b1", "title": "Yes"},
            }), "Yes"),
            (_msg("interactive", interactive={
                "type": "list_reply",
                "list_reply": {"id": "l1", "title": "Option A"},
            }), "Option A"),
            (_msg("interactive", interactive={"type": "unknown"}),
             "[interactive]"),
            (_msg("reaction", reaction={"emoji": "\U0001f44d"}), "\U0001f44d"),
            (_msg("reaction", reaction={}), "[reaction]"),
            (_msg("button", button={"text": "Click me"}), "Click me"),
            (_msg("button", button={}), "[button]"),
            (_msg("unknown_type"), "[unknown_type]"),
        ]
        for msg, expected in cases:
            with self.subTest(type=msg.get("type"), expected=expected):
                self.assertEqual(self._parse_single(msg), expected)

    def test_malformed_optional_subobjects_fall_back_to_placeholder(self):
        cases = [
            (_msg("text", text="not_a_dict"), "[text]"),
            (_msg("image", image="not_a_dict"), "[image]"),
            (_msg("video", video=42), "[video]"),
            (_msg("document", document=[]), "[document]"),
            (_msg("location", location=[1, 2]), "[location]"),
            (_msg("contacts", contacts="not_a_list"), "[contacts]"),
            (_msg("interactive", interactive=None), "[interactive]"),
            (_msg("reaction", reaction=True), "[reaction]"),
            (_msg("button", button=[]), "[button]"),
        ]
        for msg, expected in cases:
            with self.subTest(type=msg.get("type")):
                self.assertEqual(self._parse_single(msg), expected)


if __name__ == "__main__":
    unittest.main()
