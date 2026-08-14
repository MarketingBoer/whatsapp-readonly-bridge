Status: Draft — do not post automatically

# X

Main post:

I built a small inbound-only WhatsApp Cloud API bridge.

Signed Meta webhooks in. Stable local JSONL out. No WhatsApp send/reply path, no WhatsApp Web session scraping, no UI.

Useful if your own scripts, dashboards, or agents just need a controlled inbound feed.

Optional thread:

1. HMAC validation happens against the raw body before JSON parsing.
2. Message records use a stable nine-key schema.
3. Docker, Compose, systemd, and smoke tests are included.
4. Telegram/Discord examples are periodic summaries outside the core bridge.
