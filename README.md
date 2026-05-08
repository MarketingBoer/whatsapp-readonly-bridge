# WhatsApp Readonly Bridge

**Read your business WhatsApp messages. Discuss them on Telegram. Never miss a lead again.**

A zero-dependency Python bridge that receives WhatsApp messages via the **official Meta Cloud API** and turns them into an actionable Telegram checklist your team can discuss.

```
WhatsApp → Meta Cloud API → Your webhook URL → bridge.py → Telegram digest
                                                    ↓
                                               messages.jsonl
```

## Why this exists

Every agency, freelancer, and small business has the same problem: customers send WhatsApp messages, and they disappear into someone's phone. No history. No team access. No follow-up.

This bridge fixes that — for free, in 5 minutes, without risking your WhatsApp account.

## Nothing like this exists

We checked. There are [649-star PHP wrappers](https://github.com/netflie/whatsapp-cloud-api) and [541-star Python SDKs](https://github.com/david-lev/pywa) for the Cloud API — but those are **libraries**, not solutions. You still need to build everything yourself.

There are WhatsApp-to-Telegram bridges like [watgbridge](https://github.com/akshettrj/watgbridge) — but they **all use Baileys**, the reverse-engineered protocol that gets accounts banned.

There's [wacrawl](https://github.com/steipete/wacrawl) for archiving — but it reads from your **local desktop SQLite**, not from webhooks.

**The gap:** Nobody combined official Meta Cloud API + readonly webhook receiver + Telegram digest + zero dependencies. Until now.

| What exists | What's missing |
|---|---|
| Cloud API wrapper libraries (PHP, Python, Node) | A ready-to-run bridge you deploy in 5 minutes |
| Baileys-based Telegram bridges (ban risk) | An official API bridge that's safe for business |
| Enterprise platforms ($$$) | A free, self-hosted alternative |
| Local-only archivers | Webhook-based real-time monitoring |

## What you get

**📱 WhatsApp → JSONL inbox** — Every incoming message is saved to a local file. Text, images, documents, locations, contacts, reactions — everything.

**📋 Telegram task digest** — Run `digest.py` on a schedule and your team gets a formatted checklist in Telegram. Discuss, assign, resolve — right where you already are.

**👀 Real-time tail** — `reader.py` follows your inbox live, like `tail -f` for WhatsApp.

**📊 Inbox statistics** — `stats.py` shows message counts, top contacts, peak hours, daily activity. Know who's messaging and when.

**🔌 API server** — `examples/api-server.py` exposes your inbox as a JSON API. Connect it to dashboards, CRMs, or AI agents.

## 100% free. 100% official. 0% ban risk.

| | This bridge | Baileys / unofficial |
|---|---|---|
| **Cost** | Free (Meta Cloud API free tier: 1,000 conversations/month) | Free |
| **Ban risk** | Zero — official Meta API | High — reverse-engineered protocol, accounts get banned |
| **Setup** | 5 minutes | Hours of session management |
| **Multi-device** | Works alongside your WhatsApp Business app | Conflicts with phone sessions |
| **Uptime** | Meta's infrastructure | Your server, your problem |
| **Compliance** | GDPR-friendly, official data processing | Gray area |

### How it stays free

- **Meta Cloud API**: First 1,000 service-initiated conversations per month are free. Receiving messages (webhooks) is always free — you only pay when you *send*
- **Business Solution Provider** (optional): Use a BSP like ChakraHQ for easier setup, or connect directly via the Meta Developer Console — both work
- **This bridge**: MIT licensed, zero dependencies, runs on anything with Python 3.10+
- **Telegram Bot API**: Free, unlimited messages
- **Hosting**: A €5/month VPS is more than enough. Or use your existing server

**Total cost: €0/month** for receiving and monitoring messages.

## The stack

```
┌─────────────────────────────────────────────────────┐
│  WhatsApp user sends a message                      │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│  Meta Cloud API (official, free tier)               │
│  Webhook fires on every incoming message            │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│  Your webhook URL (direct or via BSP like ChakraHQ) │
│  Meta sends every incoming message here             │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│  bridge.py (this repo)                              │
│  ~100 lines Python, zero dependencies               │
│  Receives POST, extracts message, appends to JSONL  │
│  READ-ONLY: never sends messages back               │
└──────────┬───────────────────────┬──────────────────┘
           ▼                       ▼
┌──────────────────┐   ┌──────────────────────────────┐
│  messages.jsonl  │   │  Telegram digest (cron)      │
│  Append-only     │   │  Team checklist per contact  │
│  Your data,      │   │  Discuss & resolve together  │
│  your server     │   └──────────────────────────────┘
└──────────────────┘
```

## Quick start

### 1. Get your webhook URL

You need a public URL. Use any of these:

```bash
# Cloudflare Tunnel (recommended, free)
cloudflared tunnel --url http://localhost:3100

# ngrok
ngrok http 3100

# Or just point your reverse proxy to port 3100
```

### 2. Set up ChakraHQ + Meta

1. Create a free account at [ChakraHQ](https://app.chakrahq.com)
2. Connect your WhatsApp Business number
3. In ChakraHQ settings, set the webhook URL to: `https://your-domain.com/webhook`
4. Set your verify token (same as `WA_VERIFY_TOKEN` below)
5. **Important:** Keep "Chakra Webhooks (Beta)" turned **OFF** — use standard Meta webhook passthrough

### 3. Run the bridge

**Option A: Direct**

```bash
git clone https://github.com/MarketingBoer/whatsapp-readonly-bridge.git
cd whatsapp-readonly-bridge

cp .env.example .env
# Edit .env with your verify token

python3 bridge.py
```

**Option B: Docker**

```bash
git clone https://github.com/MarketingBoer/whatsapp-readonly-bridge.git
cd whatsapp-readonly-bridge

WA_VERIFY_TOKEN=your-secret-token docker compose up -d
```

**Option C: systemd (production)**

```bash
sudo cp whatsapp-bridge.service /etc/systemd/system/
sudo systemctl edit whatsapp-bridge  # set your WA_VERIFY_TOKEN
sudo systemctl enable --now whatsapp-bridge
```

### 4. Set up Telegram digest (optional but powerful)

```bash
# Create a Telegram bot via @BotFather, get the token
# Get your chat ID via @userinfobot

export TELEGRAM_BOT_TOKEN="123456:ABC-DEF..."
export TELEGRAM_CHAT_ID="your-chat-id"
export WA_INBOX="./inbox/messages.jsonl"

# Test it
python3 digest.py --dry-run

# Run every hour via cron
# crontab -e
0 * * * * cd /opt/whatsapp-bridge && TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... python3 digest.py --hours 1
```

Your Telegram will look like this:

```
📱 WhatsApp Digest — 3 messages

👤 Jan de Vries (31612345678)
  ☐ 14:23 💬 Hoi, ik wil graag een afspraak maken
  ☐ 14:25 📷 [image with caption]

👤 Lisa Bakker (31687654321)
  ☐ 15:01 💬 Kunnen jullie morgen langskomen?

Reply to this message to discuss actions.
```

## Reading the inbox

### Tail mode (live)

```bash
python3 reader.py
```

### Last N messages

```bash
python3 reader.py --last 20
```

### Filter by contact

```bash
python3 reader.py --from 31612345678
```

### Raw JSON (for piping to other tools)

```bash
python3 reader.py --last 5 --json | jq .
```

### Direct from any language

The inbox is just a JSONL file — one JSON object per line. Read it from Node.js, Go, Rust, whatever:

```python
import json
with open("inbox/messages.jsonl") as f:
    messages = [json.loads(line) for line in f if line.strip()]
```

## Message format

Each line in `messages.jsonl`:

```json
{
  "ts": "2026-05-08T14:23:51.762317+00:00",
  "from": "31612345678",
  "type": "text",
  "text": "Hoi, ik wil graag een afspraak maken",
  "name": "Jan de Vries",
  "raw": { }
}
```

| Field | Description |
|-------|-------------|
| `ts` | ISO 8601 timestamp (UTC) |
| `from` | Phone number with country code |
| `type` | `text`, `image`, `video`, `audio`, `document`, `location`, `contacts`, `sticker`, `reaction`, `interactive`, `button` |
| `text` | Extracted message text (caption for media, coordinates for location, etc.) |
| `name` | WhatsApp profile name (if available) |
| `raw` | Full Meta webhook payload for this message |

## Why read-only?

This is a deliberate architectural choice, not a limitation.

1. **No ban risk** — You literally cannot send messages, even if your code has a bug
2. **No API costs** — Sending messages costs money (Meta charges per conversation). Reading is free
3. **No compliance headaches** — You're monitoring, not communicating. Different legal category
4. **Team-first workflow** — Discuss on Telegram, then reply from the WhatsApp Business app where you have full context

If you need to send messages too, check out the [WhatsApp Cloud API docs](https://developers.facebook.com/docs/whatsapp/cloud-api). This bridge gives you a clean read pipeline that works alongside any send solution.

## Integrations

The JSONL inbox is a universal interface. Plug it into anything:

| Integration | How |
|---|---|
| **AI agents** (LangChain, CrewAI, custom) | Read JSONL, summarize, route to right agent |
| **CRM** | Cron job that POSTs new messages to your CRM API |
| **Slack/Discord** | Replace `digest.py` Telegram calls with Slack webhook |
| **Dashboard** | Expose via simple API endpoint ([example included](examples/api-server.py)) |
| **Database** | Cron that inserts JSONL lines into PostgreSQL/SQLite |
| **n8n / Make.com** | Webhook trigger on file change, or poll the API |

## Production tips

- **Tunnel:** Use Cloudflare Tunnel (free, stable) over ngrok for production
- **Backup:** The JSONL file is your data. Back it up. `cp messages.jsonl messages-$(date +%F).jsonl`
- **Rotation:** For high-volume numbers, rotate the file monthly and archive
- **Monitoring:** Bridge returns 200 on `/health` — use this for uptime checks and Docker healthchecks
- **Permissions:** The inbox file is append-only by design. Your consumer should only need read access

## FAQ

**Q: Is this really free?**
Yes. Meta Cloud API free tier (1,000 conversations/month), ChakraHQ free tier, Telegram Bot API (free), this code (MIT). You pay only for your server (a €5 VPS is overkill).

**Q: Will my WhatsApp account get banned?**
No. This uses the official Meta Cloud API through an approved Business Solution Provider (ChakraHQ). It's the same infrastructure WhatsApp Business Platform runs on.

**Q: Can I still use my phone for WhatsApp?**
Yes. The Cloud API works alongside the WhatsApp Business app. You receive messages in both places simultaneously.

**Q: Why not just use Baileys?**
Baileys reverse-engineers the WhatsApp protocol. It works until it doesn't — and when it breaks, your number gets banned. We've seen it happen to agencies. The official route is free anyway, so why risk it?

**Q: Can I send messages with this?**
No, by design. This is a read-only bridge. Reply from the WhatsApp Business app, or build a send layer on top using the Cloud API directly.

**Q: How many messages can it handle?**
The bridge is a single-threaded Python HTTP server. It handles hundreds of messages per minute easily. If you're processing thousands per minute, put nginx in front.

**Q: Does it work with WhatsApp groups?**
The Cloud API only receives messages sent directly to your business number. Group messages are not forwarded.

## License

MIT — use it, fork it, sell it, whatever. A star would be nice though.

---

Built by [Mediadeboer](https://mediadeboer.nl) — a Dutch digital agency that builds AI-powered business tools. We use this bridge in production every day to monitor client WhatsApp channels and route messages to AI agents.
