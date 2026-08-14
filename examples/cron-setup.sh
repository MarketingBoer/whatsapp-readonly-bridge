#!/bin/sh
# Example crontab line for a periodic Telegram digest.
# Create /etc/whatsapp-readonly-bridge-digest.env as root-owned mode 0600 with:
# TELEGRAM_BOT_TOKEN=your-telegram-bot-token
# TELEGRAM_CHAT_ID=your-telegram-chat-id
# WA_INBOX=/var/lib/whatsapp-readonly-bridge/messages.jsonl

cat <<'EOF'
# WhatsApp readonly bridge Telegram digest.
# Periodic summary only; not real-time delivery.
0 8 * * * /opt/whatsapp-readonly-bridge/examples/run-telegram-digest.sh --hours 24
EOF
