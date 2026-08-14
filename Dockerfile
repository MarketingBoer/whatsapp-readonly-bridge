FROM python:3.12.14-alpine3.24@sha256:3b80023c96c186093365774a00db452bfc635476319e71e56a840e251457701f

ARG VCS_REF=unknown

LABEL org.opencontainers.image.source="https://github.com/MarketingBoer/whatsapp-readonly-bridge" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.description="Inbound-only WhatsApp Cloud API webhook receiver with local JSONL storage" \
      org.opencontainers.image.title="whatsapp-readonly-bridge" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.revision="${VCS_REF}"

ENV PYTHONUNBUFFERED=1 \
    WA_PORT=3100 \
    WA_INBOX=/data/messages.jsonl

RUN addgroup -g 10001 -S bridge \
    && adduser -u 10001 -S -D -H -G bridge bridge \
    && mkdir -p /app/examples /data \
    && chown -R root:root /app \
    && chown -R 10001:10001 /data \
    && chmod 0555 /app /app/examples \
    && chmod 0700 /data

WORKDIR /app

COPY --chown=root:root bridge.py /app/bridge.py
COPY --chown=root:root whatsapp_webhook.py /app/whatsapp_webhook.py
COPY --chown=root:root jsonl_store.py /app/jsonl_store.py
COPY --chown=root:root reader.py /app/reader.py
COPY --chown=root:root stats.py /app/stats.py
COPY --chown=root:root digest.py /app/digest.py
COPY --chown=root:root examples/api-server.py /app/examples/api-server.py
COPY --chown=root:root examples/discord-webhook.py /app/examples/discord-webhook.py

USER 10001:10001
EXPOSE 3100
STOPSIGNAL SIGTERM

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python3 -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('WA_PORT', '3100'), timeout=2).read()"

CMD ["python3", "/app/bridge.py"]
