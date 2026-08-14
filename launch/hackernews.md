Status: Draft — do not post automatically

# Hacker News

Rules checked:

- HN FAQ: https://news.ycombinator.com/newsfaq.html
- Show HN guidance discussion/source: https://news.ycombinator.com/showhn.html
- HN guidelines reference: https://news.ycombinator.com/newsguidelines.html

Title:

Show HN: A small inbound-only WhatsApp bridge using Meta's Cloud API

Draft:

Hi HN, I built a small Python service for one narrow job: receive signed WhatsApp Cloud API webhook events, normalize inbound messages, and append them to local JSONL.

The reason was practical. A lot of WhatsApp tooling is either a full inbox/platform or a session-based Web bridge. I wanted a boring ingress component that an automation script, dashboard, or agent can read without the bridge itself having any WhatsApp send/reply capability.

The core is stdlib Python. POST requests are HMAC-checked against the raw body before JSON parsing, malformed batches fail without partial writes, and duplicate Meta retry deliveries are suppressed for the normal single-process deployment. Docker, Compose, systemd, a smoke client, and optional Telegram/Discord digest examples are included.

Things intentionally not built: media downloads, browser UI, shared inbox, chatbot logic, or multi-replica storage.

I would appreciate feedback on the schema, failure behavior, and whether the scope is too narrow or narrow enough.
