Status: Draft — do not post automatically

# LinkedIn

Draft:

WhatsApp automation often starts too large: a shared inbox, CRM, bot framework, or campaign system.

I published a smaller building block: an inbound-only receiver for Meta WhatsApp Cloud API webhooks. It validates signed requests, writes stable JSONL, and leaves downstream routing to tools you control.

It is for teams that want a local ingress component, not another inbox product. Docker, Compose, systemd, reader/stats commands, and optional Telegram/Discord digest examples are included.

No external promotion should happen until release and package verification are complete.
