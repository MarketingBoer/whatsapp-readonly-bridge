#!/bin/sh
set -eu

ENV_FILE=/etc/whatsapp-readonly-bridge-digest.env
if [ ! -r "$ENV_FILE" ]; then
  echo "Missing readable $ENV_FILE" >&2
  exit 1
fi

set -a
. "$ENV_FILE"
set +a

exec /usr/bin/python3 /opt/whatsapp-readonly-bridge/digest.py "$@"
