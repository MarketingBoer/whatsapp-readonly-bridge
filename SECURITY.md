# Security

Supported security updates target the current v1 release line.

Do not publish real app secrets, verify tokens, phone numbers, names, message bodies, or raw webhook payloads in public issues. If private reporting is needed before GitHub private vulnerability reporting is enabled, contact the repository owner through an existing private channel and include only dummy reproduction data in public follow-up.

The bridge requires a trusted HTTPS reverse proxy or tunnel for the public Meta callback URL. It validates `X-Hub-Signature-256` with `WA_APP_SECRET` before JSON parsing, rejects placeholder secrets, and logs only request metadata.

JSONL inbox files are sensitive. They may contain phone numbers, names, timestamps, message summaries, and optionally raw message objects. Use restrictive filesystem permissions, retention rules, backups, and access controls appropriate for your environment. `WA_STORE_RAW=false` reduces stored raw event data but is not anonymization.

The storage design is a single-writer local filesystem contract. Active-active writers, network filesystem semantics, and multi-replica guarantees are outside v1.

The local API example is unauthenticated and binds to loopback by default. Add authentication and transport controls before exposing similar behavior beyond a trusted local environment.

The Telegram and Discord examples are explicit outbound exceptions. The core bridge itself has no WhatsApp Graph send/reply call and no WhatsApp access-token configuration.
