Status: Draft — do not post automatically

# Competitive research

Last verified: 2026-08-14

Sources checked:

- Evolution API: https://github.com/evolution-foundation/evolution-api
- WAHA: https://github.com/devlikeapro/waha
- WPPConnect: https://github.com/wppconnect-team/wppconnect
- Whatomate: https://github.com/shridarpatil/whatomate
- Heyoo topic listing: https://github.com/topics/whatsapp-business-api
- Meta-hosted Node SDK receiving messages: https://whatsapp.github.io/WhatsApp-Nodejs-SDK/receivingMessages/

Snapshot:

- Evolution API is a broad TypeScript messaging platform. It supports Baileys and WhatsApp Cloud API paths plus CRM, bot, queues, object storage, and many integrations. It is not a tiny inbound-only JSONL receiver.
- WAHA is a WhatsApp HTTP API focused on sessions and sending through WEBJS/NOWEB/GOWS engines. Its README demonstrates `/api/sendText`.
- WPPConnect exports WhatsApp Web functions to Node and includes interaction/media/send-oriented use cases.
- Whatomate is a self-hosted WhatsApp Business Platform with UI, roles, campaigns, bots, calling, analytics, and Docker.
- Heyoo is a Python wrapper for WhatsApp Cloud API, not a self-hosted JSONL ingress component.
- Meta's Node SDK includes a receiving web server utility and notes a single-process context.

Inference:

The defensible niche is small inbound-only official Cloud API webhook ingress with HMAC-before-JSON, local JSONL, and optional periodic sinks. Do not claim this is the only WhatsApp bridge or a replacement for full inbox/platform products.
