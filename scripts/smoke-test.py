#!/usr/bin/env python3
"""Local smoke client for a running WhatsApp readonly bridge."""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import sys
import urllib.error
import urllib.parse
import urllib.request


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--verify-token", required=True)
    parser.add_argument("--app-secret", required=True)
    args = parser.parse_args(argv)

    base = args.base_url.rstrip("/")
    try:
        _expect_json(base + "/health", 200)
        challenge = "smoke-test-challenge"
        query = urllib.parse.urlencode({
            "hub.mode": "subscribe",
            "hub.verify_token": args.verify_token,
            "hub.challenge": challenge,
        })
        body = _request(base + "/webhook?" + query, method="GET")
        if body.decode("utf-8") != challenge:
            print("verification failed", file=sys.stderr)
            return 1

        payload = {
            "object": "whatsapp_business_account",
            "entry": [{"changes": [{"field": "messages", "value": {
                "metadata": {"phone_number_id": "123456789"},
                "contacts": [{"wa_id": "31600000000",
                              "profile": {"name": "Smoke Test"}}],
                "messages": [{
                    "id": "wamid.smoke-test",
                    "from": "31600000000",
                    "type": "text",
                    "timestamp": "1700000000",
                    "text": {"body": "Smoke test"},
                }],
            }}]}],
        }
        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        digest = hmac.new(args.app_secret.encode("utf-8"), raw,
                          hashlib.sha256).hexdigest()
        _expect_json(
            base + "/webhook",
            200,
            data=raw,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": f"sha256={digest}",
            },
        )
    except Exception as exc:
        print(f"smoke test failed: {type(exc).__name__}", file=sys.stderr)
        return 1

    print("smoke test ok")
    return 0


def _expect_json(url, status, data=None, headers=None):
    body = _request(url, method="POST" if data is not None else "GET",
                    data=data, headers=headers)
    parsed = json.loads(body)
    if not isinstance(parsed, dict):
        raise RuntimeError("expected JSON object")
    return parsed


def _request(url, method="GET", data=None, headers=None):
    request = urllib.request.Request(url, data=data, headers=headers or {},
                                     method=method)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read()
            if response.status < 200 or response.status >= 300:
                raise RuntimeError("unexpected status")
            return body
    except urllib.error.HTTPError as exc:
        exc.read()
        raise RuntimeError("unexpected status") from exc


if __name__ == "__main__":
    raise SystemExit(main())
