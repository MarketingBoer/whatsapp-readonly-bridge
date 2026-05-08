FROM python:3.12-alpine

WORKDIR /app

COPY bridge.py digest.py reader.py stats.py ./
COPY examples/ ./examples/

RUN mkdir -p /app/inbox

ENV WA_PORT=3100
ENV WA_INBOX=/app/inbox/messages.jsonl
ENV WA_VERIFY_TOKEN=change-me
ENV WA_WEBHOOK_PATH=/webhook

EXPOSE 3100

HEALTHCHECK --interval=30s --timeout=3s \
    CMD ["python3", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:3100/health')"]

CMD ["python3", "bridge.py"]
