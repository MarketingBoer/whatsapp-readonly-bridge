#!/bin/bash
# Example cron setup for WhatsApp digest
#
# Run this once to install the cron jobs:
#   bash examples/cron-setup.sh
#
# Or copy the lines manually into: crontab -e

BRIDGE_DIR="$(cd "$(dirname "$0")/.." && pwd)"

cat <<EOF

Add these lines to your crontab (run: crontab -e):

# WhatsApp digest every hour (new messages from last hour)
0 * * * * cd ${BRIDGE_DIR} && /usr/bin/python3 digest.py --hours 1

# Daily summary at 09:00 (all messages from last 24 hours)
0 9 * * * cd ${BRIDGE_DIR} && /usr/bin/python3 digest.py --hours 24

# Weekly stats in your Telegram every Monday at 09:05
5 9 * * 1 cd ${BRIDGE_DIR} && /usr/bin/python3 stats.py | /usr/bin/python3 -c "
import os, urllib.request, urllib.parse, sys
text = sys.stdin.read()
url = f'https://api.telegram.org/bot{os.environ[\"TELEGRAM_BOT_TOKEN\"]}/sendMessage'
data = urllib.parse.urlencode({'chat_id': os.environ['TELEGRAM_CHAT_ID'], 'text': text}).encode()
urllib.request.urlopen(urllib.request.Request(url, data=data))
"

Remember to set environment variables in your crontab:
TELEGRAM_BOT_TOKEN=your-token
TELEGRAM_CHAT_ID=your-chat-id
WA_INBOX=${BRIDGE_DIR}/inbox/messages.jsonl

EOF
