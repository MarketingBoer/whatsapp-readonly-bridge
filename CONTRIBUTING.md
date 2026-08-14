# Contributing

Keep changes inside the v1 scope: signed inbound WhatsApp Cloud API webhooks, durable local JSONL, tested readers, and optional downstream examples.

Before opening a pull request, run:

```bash
python3 -m compileall -q bridge.py whatsapp_webhook.py jsonl_store.py reader.py digest.py stats.py examples tests scripts
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 scripts/release_audit.py --source-only
```

Use dummy data in tests and documentation. Do not add real phone numbers, names, message bodies, app secrets, verify tokens, or webhook URLs.

Tests should not call real third-party networks. Mock Telegram, Discord, GHCR, Meta, and any other external service.

Claims about Meta behavior must link to current official Meta documentation. If Meta changes pricing, webhook behavior, signatures, retries, or Coexistence requirements, update code or copy with the dated source.

Adding a WhatsApp send/reply path, WhatsApp access-token setting, third-party core dependency, database, queue, browser UI, or multi-tenant routing requires an explicit design decision. Those are outside the v1 release scope.
