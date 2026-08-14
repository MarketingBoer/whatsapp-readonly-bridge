Status: Draft — do not post automatically

# r/selfhosted

RULES NEED MANUAL RECHECK before posting. Secondary rule summaries indicate self-promotion should be limited, contextual, documented, and genuinely self-hostable.

Source to recheck: https://www.reddit.com/r/selfhosted/about/rules/

Draft:

I built a small self-hosted WhatsApp Cloud API webhook receiver for inbound messages only.

It validates Meta signatures, writes a local JSONL inbox, and ships with Docker Compose, a hardened systemd example, reader/stats commands, and optional periodic Telegram/Discord digest examples. It has no WhatsApp send/reply path.

This is not a shared inbox or campaign platform. It is meant as a local ingress component for people who want their own scripts, dashboards, or automations to consume WhatsApp inbound messages from a file.

Repo: https://github.com/MarketingBoer/whatsapp-readonly-bridge

I am the author. Feedback on deployment defaults and the JSONL schema would be useful.
