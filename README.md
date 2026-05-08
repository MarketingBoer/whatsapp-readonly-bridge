# WhatsApp Readonly Bridge

**Your customers send WhatsApp messages. They disappear into someone's phone. You lose the lead.**

This bridge catches every incoming WhatsApp message and turns it into a team task list on Telegram — so nothing falls through the cracks. Free, safe, takes 5 minutes to set up.

```
Customer sends WhatsApp → your team gets a Telegram checklist → discuss, assign, done.
```

## Who is this for?

- **Agencies and freelancers** where clients message on WhatsApp but nobody tracks follow-ups
- **Small businesses** that want a shared WhatsApp inbox without paying €50/month for a SaaS tool
- **Anyone with a chatbot** who wants to read and discuss WhatsApp messages without ever opening WhatsApp
- **Developers** who need a clean WhatsApp data feed for AI agents, CRMs, or dashboards

A developer sets it up once. The team uses Telegram from there.

## What your team sees

Every hour (or however often you want), your Telegram gets this:

```
📱 WhatsApp Digest — 6 messages

👤 Jan de Vries (31612345678)
  ☐ 09:14 💬 Hoi, ik wil graag een afspraak maken voor volgende week
  ☐ 09:15 📷 [image]

👤 Lisa Bakker (31687654321)
  ☐ 11:32 💬 Kunnen jullie morgen langskomen? Het gaat om de achttertuin

👤 Pieter Jansen (31698765432)
  ☐ 14:05 💬 Bedankt voor de offerte, we gaan ermee akkoord
  ☐ 14:06 📄 [document: offerte-getekend.pdf]

👤 31676543210
  ☐ 16:48 💬 Is er nog plek deze week?

Reply to this message to discuss actions.
```

Your team discusses it right there. Someone picks it up. No message gets lost.

## Why not Baileys?

Every WhatsApp bridge on GitHub uses [Baileys](https://github.com/WhiskeySockets/Baileys) — a reverse-engineered protocol. It works until WhatsApp detects it and **bans your number**. We've seen it happen to agencies.

This bridge uses the **official Meta Cloud API**. Same infrastructure that WhatsApp Business Platform runs on. Zero ban risk.

| | This bridge | Baileys |
|---|---|---|
| **Ban risk** | Zero — official Meta API | High — accounts get banned |
| **Cost** | Free (receiving is always free) | Free |
| **Setup** | 5 minutes | Hours of session management |
| **Your phone** | Works alongside WhatsApp Business app | Conflicts with phone sessions |
| **Compliance** | GDPR-friendly, official | Gray area |

## How it stays free

Receiving WhatsApp messages via the Cloud API is free. Always. You only pay when you *send* messages. Since this bridge is read-only, the entire stack costs nothing:

- **Meta Cloud API** — free for receiving
- **Telegram Bot API** — free, unlimited
- **This bridge** — MIT licensed, zero dependencies
- **Hosting** — runs on a €5 VPS, or your existing server

## How it works

```
┌──────────────────────────────────────────────┐
│  Customer sends a WhatsApp message           │
└─────────────────────┬────────────────────────┘
                      ▼
┌──────────────────────────────────────────────┐
│  Meta Cloud API (official, free)             │
│  Fires a webhook to your server              │
└─────────────────────┬────────────────────────┘
                      ▼
┌──────────────────────────────────────────────┐
│  bridge.py (~100 lines Python, zero deps)    │
│  Extracts message, appends to JSONL file     │
│  READ-ONLY: cannot send messages back        │
└──────────┬──────────────────┬────────────────┘
           ▼                  ▼
┌─────────────────┐  ┌────────────────────────┐
│  messages.jsonl │  │  Telegram digest (cron) │
│  Your data,     │  │  Team checklist         │
│  your server    │  │  Discuss & assign       │
└─────────────────┘  └────────────────────────┘
```

## Quick start

### 1. Get a public URL

```bash
# Cloudflare Tunnel (recommended, free)
cloudflared tunnel --url http://localhost:3100

# Or ngrok
ngrok http 3100
```

### 2. Connect to Meta Cloud API

1. Create a free account at [ChakraHQ](https://app.chakrahq.com) (or use Meta Developer Console directly)
2. Connect your WhatsApp Business number
3. Set the webhook URL to your public URL + `/webhook`
4. Set your verify token

### 3. Start the bridge

**Direct:**
```bash
git clone https://github.com/MarketingBoer/whatsapp-readonly-bridge.git
cd whatsapp-readonly-bridge
cp .env.example .env   # edit with your verify token
python3 bridge.py
```

**Docker:**
```bash
WA_VERIFY_TOKEN=your-secret-token docker compose up -d
```

**systemd (production):**
```bash
sudo cp whatsapp-bridge.service /etc/systemd/system/
sudo systemctl edit whatsapp-bridge  # set your WA_VERIFY_TOKEN
sudo systemctl enable --now whatsapp-bridge
```

### 4. Set up Telegram digest

```bash
# Create a bot via @BotFather, get your chat ID via @userinfobot
export TELEGRAM_BOT_TOKEN="123456:ABC-DEF..."
export TELEGRAM_CHAT_ID="your-chat-id"

# Test it
python3 digest.py --dry-run

# Run every hour via cron
0 * * * * cd /opt/whatsapp-bridge && python3 digest.py --hours 1
```

## What else you can do

**Read messages live:**
```bash
python3 reader.py              # tail mode (like watching a live feed)
python3 reader.py --last 20    # last 20 messages
python3 reader.py --from 316…  # filter by contact
```

**Get inbox stats:**
```bash
python3 stats.py               # message counts, top contacts, peak hours
```

**Expose as API:**
```bash
python3 examples/api-server.py  # JSON API on port 3101
```

**Feed into anything:** The inbox is a JSONL file — one JSON object per line. Read it from any language, pipe it into AI agents, CRMs, databases, Slack, Discord, n8n, Make.com.

## Sample data

**Each message looks like this** ([full sample](examples/sample-inbox.jsonl)):
```json
{
  "ts": "2026-05-08T14:23:51+00:00",
  "from": "31612345678",
  "type": "text",
  "text": "Hoi, ik wil graag een afspraak maken",
  "name": "Jan de Vries"
}
```

**Telegram digest example:** [examples/telegram-digest-example.txt](examples/telegram-digest-example.txt)

## Why read-only?

Not a limitation — a feature.

1. **No ban risk** — The bridge literally cannot send messages, even if your code has a bug
2. **No costs** — Sending costs money. Reading is free
3. **No compliance issues** — Monitoring ≠ communicating. Different GDPR category
4. **Better workflow** — Discuss on Telegram, reply from WhatsApp Business app with full context

## FAQ

**Is this really free?**
Yes. Receiving WhatsApp messages is free on Meta's Cloud API. You only pay for sending, and this bridge doesn't send.

**Will my WhatsApp get banned?**
No. This is the official Meta Cloud API, not a reverse-engineered hack. Same infrastructure WhatsApp Business Platform uses.

**Can I still use my phone?**
Yes. Cloud API works alongside WhatsApp Business app. Messages arrive in both places.

**Can I connect my chatbot to this?**
Yes. Your bot reads the JSONL file or calls the API server. It gets every WhatsApp message without touching WhatsApp itself.

**Why not Baileys?**
Baileys reverse-engineers WhatsApp's protocol. When WhatsApp updates, your number gets banned. The official API is free for reading, so there's no reason to risk it.

**How many messages can it handle?**
Hundreds per minute. For thousands, put nginx in front.

## License

MIT — use it, fork it, sell it. A star helps others find it.

---

Built by [Mediadeboer](https://mediadeboer.nl) — we use this in production every day to catch WhatsApp messages and route them to AI agents.
