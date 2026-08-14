# WhatsApp Readonly Bridge v1.0.0 Relaunch Design

**Date:** 2026-08-14
**Repository:** `MarketingBoer/whatsapp-readonly-bridge`
**Status:** Ready for implementation planning

## 1. Objective

Relaunch the existing repository and history as a credible v1.0.0: a small,
self-hosted receiver for inbound WhatsApp Business Platform Cloud API webhook
events that validates Meta signatures, stores messages in durable JSONL, and
exposes no WhatsApp send or reply capability.

The relaunch must improve reliability, installation, documentation, release
packaging, and promotion readiness without turning the project into a complete
inbox, chatbot framework, or SaaS platform.

## 2. Verified baseline

The pre-change audit established the following facts:

- `main` is at `593814b`; the remote has no tags, releases, Actions workflows,
  or public GHCR image.
- The tracked core is Python standard-library code, but it has no committed
  bridge tests.
- `bridge.py` verifies the GET challenge token but accepts unsigned POST
  payloads.
- `WA_VERIFY_TOKEN` defaults to `change-me`; there is no Meta app-secret
  setting.
- `cp .env.example .env && python3 bridge.py` does not load `.env`.
- Malformed JSON structures can crash the handler; duplicate Meta deliveries
  are appended more than once.
- The current Docker image builds, but the build context is 46 MB because
  `.dockerignore` is missing; the container runs as root.
- The current Compose file builds locally and persists a bind-mounted inbox;
  it does not use GHCR.
- The current README contains unsupported absolutes about cost, account risk,
  GDPR, Business App coexistence, capacity, and competitor behavior.
- Local untracked `mcp_server.py` and `tests/test_mcp_server.py` contain private
  `/home/wiz` fallbacks and add an undeclared third-party dependency. They are
  user-owned experiments and are excluded from public v1.0.0.

Official Meta sources used by the design:

- Webhook endpoint validation and `X-Hub-Signature-256`:
  <https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/create-webhook-endpoint>
- Webhook retries, duplicate notifications, payload limit, and fields:
  <https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/overview>
- Current pricing model:
  <https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing>
- WhatsApp Business App Coexistence conditions:
  <https://developers.facebook.com/documentation/business-messaging/whatsapp/embedded-signup/onboarding-business-app-users>

## 3. Positioning

The defensible positioning is:

> Receive inbound WhatsApp messages through Meta's official Cloud API and
> route them into tools you control, without WhatsApp Web or session scraping.

The project is a focused ingress component. Its differentiation is the
combination of official Cloud API webhooks, inbound-only behavior, a small
stdlib Python core, local JSONL, simple downstream examples, and a ready-to-run
container. It is not presented as the only official-API project.

Claims must distinguish three boundaries:

1. **Toward WhatsApp:** the bridge contains no Graph API send/reply call,
   access token, or outbound WhatsApp functionality.
2. **Downstream:** optional Telegram and Discord examples do make outbound
   calls to those services.
3. **Operations/compliance:** official API use and self-hosting do not remove
   Meta policy, privacy, retention, security, or legal obligations.

## 4. Scope and non-goals

### In scope

- GET webhook verification.
- HMAC-SHA256 validation of every POST to an accepted webhook path using the
  Meta app secret.
- Defensive parsing of subscribed inbound `messages` events.
- Readable summaries for known types and, when `WA_STORE_RAW` is enabled,
  preservation of unknown message data.
- Persistent JSONL with message identifiers and practical duplicate
  suppression for Meta retries.
- Telegram digest, Discord digest, local reader, statistics, and local API
  examples hardened in proportion to their role.
- Docker/GHCR, Compose, systemd example, healthcheck, tests, CI, documentation,
  release, repository metadata, and offline launch copy.

### Explicitly out of scope

- Sending or replying through WhatsApp.
- Media download or storage of media binaries.
- A browser UI, shared inbox, CRM, campaign tool, or chatbot framework.
- Multi-tenant routing or horizontal multi-replica guarantees.
- Queues, databases, Redis, third-party Python runtime dependencies, or an MCP
  server.
- Automatic posting to social networks or community sites.
- Modification of the live `openclaw.scootone.nl` endpoint, live verify token,
  Hermes configuration, or the currently deployed service.

## 5. Component design

### `bridge.py` — configuration, HTTP transport, lifecycle

- Load `.env` from the directory containing `bridge.py` if present; real process
  environment variables take precedence. The parser supports blank lines,
  comments, `KEY=VALUE`, and matching single/double quotes, but deliberately
  performs no shell expansion. A non-comment line without `=`, an empty key,
  mismatched quotes, or a duplicate key is a startup `ConfigError`. Inline `#`
  characters are data; only lines whose first non-space character is `#` are
  comments.
- Require non-empty, non-placeholder `WA_VERIFY_TOKEN` and `WA_APP_SECRET` at
  startup. Validate port, webhook path, log level, and boolean settings.
- Retain both `/webhook` and the backward-compatible
  `/webhook/whatsapp-cloud` route under the default configuration.
- Use `ThreadingHTTPServer`, a 10-second per-connection timeout, and graceful
  SIGINT / SIGTERM shutdown.
- Never log query strings, tokens, phone numbers, names, message bodies, or raw
  payloads. Request logs contain method, normalized path, status, duration,
  record count, and duplicate count only.
- Return small JSON responses with explicit content type and `Cache-Control:
  no-store`.

HTTP contract:

| Request | Result |
|---|---|
| `GET /health` | `200` and `{"status":"ok"}` after successful startup |
| Valid verification GET | `200` with the exact challenge |
| Invalid verification token/mode | `403` |
| Unknown GET/POST path | `404` |
| Missing `Content-Length` | `411` |
| Invalid `Content-Length` | `400` |
| Body over 3 MiB | `413` |
| Non-JSON content type | `415` |
| Missing/invalid Meta signature | `401` |
| Invalid JSON or invalid top-level webhook shape | `400` |
| Valid non-message/status webhook | `200`, zero records |
| Valid message webhook persisted | `200` after durable append |
| Storage failure | `500`, allowing Meta to retry |

Webhook verification is the only non-JSON response: it returns the exact raw
challenge as UTF-8 `text/plain`. All other responses are JSON.

POST processing order is deterministic:

1. Match the normalized path. An unknown path returns `404` without reading or
   authenticating the body.
2. Require no `Transfer-Encoding` header and exactly one `Content-Length`
   header. Transfer encoding, duplicate lengths, non-integers, and negative
   lengths return `400`; a missing length returns `411`.
3. Reject lengths above 3,145,728 bytes with `413`.
4. Require `application/json`, allowing charset parameters, otherwise `415`.
5. Read exactly the declared byte count. A socket timeout returns `408`; an
   early EOF/short body returns `400`.
6. Validate `X-Hub-Signature-256`; a missing, malformed, non-hex, or mismatched
   `sha256=<64 hex characters>` value returns `401`.
7. Decode UTF-8 JSON and validate the complete payload before any append.
8. Append the validated batch. Only a completed durable append returns `200`.

Configuration is a single immutable `BridgeConfig` with this contract:

| Variable | Default | Accepted values / failure |
|---|---|---|
| `WA_VERIFY_TOKEN` | none | Required; reject empty, `change-me`, and values beginning `your-` |
| `WA_APP_SECRET` | none | Required; reject empty, `change-me`, and values beginning `your-` |
| `WA_BIND` | `127.0.0.1` | IPv4/IPv6 address or hostname accepted by `ThreadingHTTPServer`; bind errors fail startup |
| `WA_PORT` | `3100` | Integer `1..65535`; otherwise fail startup |
| `WA_INBOX` | `./inbox/messages.jsonl` | Non-empty path; relative paths resolve from the process working directory |
| `WA_WEBHOOK_PATH` | `/webhook` | One absolute URL path, no query/fragment, no `..`, not `/` or `/health`; trailing slash removed |
| `WA_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`; otherwise fail startup |
| `WA_STORE_RAW` | `true` | Case-insensitive `true/false`, `1/0`, `yes/no`, or `on/off`; otherwise fail startup |
| `WA_REQUEST_TIMEOUT` | `10` | Float `1..60` seconds; otherwise fail startup |
| `WA_SHUTDOWN_TIMEOUT` | `15` | Float `1..60` seconds; otherwise fail startup |

With the default path, `/webhook` and `/webhook/whatsapp-cloud` are accepted.
For a custom path, that exact path and `<custom>/whatsapp-cloud` are accepted,
preserving existing behavior. Compose explicitly sets `WA_BIND=0.0.0.0`; direct
execution retains the safer loopback default.

Startup parses configuration, creates and permission-checks the inbox, scans
existing IDs, and only then binds the listening socket. `/health` is therefore
a startup-readiness plus process-liveness signal, not a continuous disk-write
probe. An already accepted health request returns `503` after shutdown begins;
new connections are no longer accepted. SIGINT/SIGTERM stops accepting
new requests, waits at most `WA_SHUTDOWN_TIMEOUT` seconds for tracked in-flight
handlers, and exits `0` if they drain. If the deadline expires, it logs a
metadata-only error and exits `1`; Docker's stop grace is 20 seconds. The
graceful-stop test holds an append in flight, sends SIGTERM, releases the
append, and requires the original request to finish and the process to exit
`0` within 15 seconds.

### `whatsapp_webhook.py` — pure signature and payload logic

- `validate_signature(body, header, app_secret)` validates the exact raw bytes
  with HMAC-SHA256 and `hmac.compare_digest` before JSON parsing.
- `parse_webhook(payload, received_at, store_raw=True)` accepts only an object
  whose `object` is `whatsapp_business_account`, walks entry/change/value
  structures defensively, ignores valid changes without a `messages` list, and
  returns a complete list of normalized records before storage begins.
- Each message must be a mapping with non-empty `id`, `from`, and `type`.
  Missing optional contacts or captions are tolerated. Structurally malformed
  message objects reject the batch with a controlled `PayloadError`.
- Contact names are matched by `wa_id`, not blindly taken from the first
  contact.
- Known message types receive concise summaries. Unknown types use `[type]`
  while retaining the raw message object when `WA_STORE_RAW=true`.
- No media bytes are fetched.

Every stored record always has all nine schema keys. `name`,
`message_timestamp`, `phone_number_id`, and `raw` are JSON `null` when
unavailable or disabled; keys are never omitted. `received_at` is an injected
aware UTC datetime. A valid Unix message timestamp is converted to aware UTC;
missing, non-numeric, negative, or out-of-range timestamps produce `null` and
do not reject an otherwise valid message.

Parsing policy:

- Top-level payload must be a mapping with
  `object=whatsapp_business_account` and an `entry` list.
- Every entry must be a mapping with a `changes` list; every change must be a
  mapping with a mapping `value`. A malformed container rejects the entire
  request with `PayloadError`.
- Changes whose `field` is not `messages` are valid and ignored.
- A `messages` change containing only a list-valued `statuses` member is valid
  and yields zero records. If `messages` is present it must be a list.
- `metadata` is optional; when present it must be a mapping.
- `contacts` is optional; when present it must be a list of mappings. Profile
  names are used only when the contact `wa_id` matches the message `from`.
- Every item in `messages` must be a mapping with non-empty string `id`,
  `from`, and `type`. One malformed later item rejects the full batch, so no
  earlier record is persisted.
- Malformed optional type-specific subobjects do not crash or reject the
  message; they fall back to the type placeholder and remain available in
  `raw` when enabled.

Summary normalization is fixed for v1.0.0:

| Type | `text` value |
|---|---|
| `text` | body string, otherwise `[text]` |
| `image`, `video` | caption string, otherwise `[image]` / `[video]` |
| `document` | `[document: filename]` when present, otherwise `[document]` |
| `audio`, `sticker`, `order`, `system` | `[audio]`, `[sticker]`, `[order]`, `[system]` |
| `location` | `[location: latitude,longitude]` for numeric coordinates, otherwise `[location]` |
| `contacts` | `[contacts: Name, ...]` for formatted names, otherwise `[contacts]` |
| `interactive` | button/list reply title when present, otherwise `[interactive]` |
| `reaction` | emoji string when present, otherwise `[reaction]` |
| `button` | button text when present, otherwise `[button]` |
| any other non-empty type | `[<type>]` |

Stable JSONL record schema:

```json
{
  "ts": "2026-08-14T14:00:00+00:00",
  "message_id": "wamid.example",
  "message_timestamp": "2026-08-14T13:59:58+00:00",
  "from": "31612345678",
  "name": "Example User",
  "type": "text",
  "text": "Hello",
  "phone_number_id": "123456789",
  "raw": {"id": "wamid.example", "type": "text"}
}
```

`ts` remains the bridge receipt time for compatibility. The Meta event time is
stored separately as `message_timestamp`.

### `jsonl_store.py` — durable single-node inbox

- Create parent directories with mode `0700` and the inbox file with mode
  `0600`; enforce restrictive mode on existing files where supported.
- Serialize check-and-append operations with an in-process lock and POSIX
  advisory file lock where available.
- Parse all existing valid records at startup and rebuild the known
  `message_id` set. Corrupt lines are counted and warned about without logging
  their content.
- Suppress repeated IDs within a request and across restarts.
- Encode a validated request batch before opening the file. Ensure a damaged
  trailing partial line is separated before new output, write in binary mode,
  then flush and `fsync` before returning success.
- Shared readers skip malformed/partial lines and optionally report counts.
- The deployment contract is one bridge process/replica per inbox. Network
  filesystems and active-active writers are unsupported for v1.0.0.

The store API is independently testable:

```python
@dataclass(frozen=True)
class AppendResult:
    written: int
    duplicates: int

class StorageError(RuntimeError): ...

class JsonlStore:
    def __init__(self, path: Path): ...
    def initialize(self) -> None: ...
    def append(self, records: list[dict]) -> AppendResult: ...

@dataclass(frozen=True)
class ReadResult:
    records: list[dict]
    malformed_lines: int

def read_jsonl(path: Path) -> ReadResult: ...
```

The file offset before a batch is recorded. If write, flush, or `fsync` fails,
the store attempts to truncate and sync back to that offset, does not update
the in-memory ID set, and raises `StorageError`. If rollback also fails it logs
metadata-only critical state and still raises. Durability is documented as a
local-filesystem best effort, not transactional exactly-once storage. When the
file is first created, its parent directory is synced on POSIX where supported.

`bridge.py` exposes import-safe boundaries:

```python
def load_config(env: Mapping[str, str], base_dir: Path) -> BridgeConfig: ...
def make_handler(config: BridgeConfig, store: JsonlStore,
                 clock: Callable[[], datetime]) -> type[BaseHTTPRequestHandler]: ...
def create_server(config: BridgeConfig, store: JsonlStore,
                  clock: Callable[[], datetime] = utc_now) -> ThreadingHTTPServer: ...
def main() -> int: ...
```

No server starts at import. Tests inject a temporary store and deterministic
clock. Handler responses use `AppendResult`; `PayloadError`, `StorageError`,
and `ConfigError` map to controlled responses/startup failure.

The system offers practical duplicate suppression, not an impossible
exactly-once guarantee across arbitrary filesystem failures. Documentation
states this explicitly.

### Reader and destination examples

- `reader.py` uses the shared tolerant JSONL reader and survives truncation or
  rotation while tailing. Tail mode tracks inode and byte offset, polls every
  two seconds, reopens when inode changes or size becomes smaller than the
  offset, buffers an incomplete last line until its newline arrives, and never
  emits a partial/corrupt record.
- `stats.py` emits clean JSON in `--json` mode even if the inbox is absent and
  handles aware timestamps correctly.
- `digest.py --dry-run` is a real no-network mode, timestamp comparisons use
  timezone conversion, HTTP calls have timeouts, and Telegram output is split
  within platform limits.
- `examples/discord-webhook.py` shares the correct inbox default, tolerates
  damaged lines, uses a timeout, and splits messages within Discord limits.
- `examples/api-server.py` binds to `127.0.0.1` by default, clamps and validates
  limits, has no permissive CORS default, and retains a prominent warning that
  it has no authentication.
- Scheduled digest examples are described as periodic summaries, not
  real-time guaranteed delivery.

`--dry-run` never requires destination credentials, constructs no request, and
does not call a network primitive. Telegram and Discord use a 10-second HTTP
timeout, treat non-2xx/API-error responses as exit status `1`, emit no secret
URLs/tokens, and split at Telegram 4096/Discord 2000 character limits without
splitting a UTF-8 code point. The local API returns `400` for non-integer or
negative limits and clamps positive limits to `1..200`.

## 6. Deployment design

### Container

- Base image: current maintained Python 3.12 Alpine line.
- Run as an unprivileged fixed user.
- Store data under `/data`; code and root filesystem are read-only at runtime.
- Add `.dockerignore`, unbuffered Python, `STOPSIGNAL SIGTERM`, a dynamic-port
  healthcheck, and OCI source/license/description labels.
- Primary `docker-compose.yml` uses
  `ghcr.io/marketingboer/whatsapp-readonly-bridge:latest`, binds to loopback by
  default, requires both secrets, mounts a named persistent volume, drops
  capabilities, enables `no-new-privileges`, and uses an init process.
- `docker-compose.build.yml` is an explicit override for local source builds.

The Dockerfile pins `python:3.12-alpine` to the verified multi-architecture
manifest digest used at implementation time. Its `COPY` directives explicitly
name public runtime files. `.dockerignore` starts from deny-all and re-allows
only those runtime files/directories. `.env`, `.env.*` except `.env.example`,
`inbox/`, `.git/`, `mcp_server.py`, tests, caches, and operator artifacts are
also covered by release checks. `.gitignore` continues to ignore `.env`, inbox
data, caches, and local operator files.

### systemd

- Treat the unit as a production-oriented example, not a complete TLS server.
- Use `DynamicUser`, `StateDirectory`, `EnvironmentFile`, restrictive umask,
  journald, `Restart=on-failure`, and standard systemd hardening directives.
- Require a TLS reverse proxy/tunnel for the public callback URL; Meta does not
  accept a self-signed endpoint certificate.
- Run `systemd-analyze verify whatsapp-bridge.service` as a release check when
  systemd tooling is available.

## 7. Test and CI design

Committed stdlib `unittest` coverage includes:

- verification success and rejection;
- valid signed text message;
- missing and invalid signatures;
- invalid JSON, scalar JSON, oversized body, unsupported content type, and
  unknown paths;
- unknown message type and missing optional contacts;
- multi-entry/multi-message batches;
- JSONL schema, permissions, corrupt trailing-line recovery, and restart
  deduplication;
- storage failure returning `500`;
- real no-network Telegram dry-run and timezone comparisons;
- safe API limits and robust readers.

Additional required tests/gates cover:

- status-only signed payloads yielding `200` and zero writes;
- later malformed messages causing zero partial persistence;
- same-request, concurrent-thread, repeated-request, and restart duplicates;
- contact selection by matching `wa_id`;
- `WA_STORE_RAW=false` producing a present `raw: null` key;
- `.env` loading, process-environment precedence, placeholder rejection, and
  every invalid configuration range/value;
- body sizes exactly 3,145,728 and 3,145,729 bytes, duplicate length,
  transfer-encoding, timeout, and short-read behavior;
- malformed signature schemes/length/hex and constant-time comparison path;
- log capture proving token/query/body/phone/name redaction;
- store rollback behavior and corrupt-tail recovery;
- shutdown while a store append is in flight;
- container UID is non-zero, root filesystem is read-only, `/data` remains
  writable, persistence survives restart, and health becomes ready only after
  store initialization.

An inbound-only release audit searches tracked runtime Python files and the
container filesystem for Graph send endpoints, access-token configuration,
WhatsApp send/reply handlers, and outbound network calls. Bridge integration
tests monkeypatch network primitives and prove a signed inbound request causes
zero outbound calls. Telegram/Discord files are separately named exceptions.

CI runs on Python 3.10, 3.12, and 3.14, performs syntax/compile sanity checks,
runs the full test suite, validates Compose with non-secret dummy values, and
builds the Docker image. GitHub Actions are pinned to immutable current commit
SHAs with version comments.

The container publishing workflow runs only for semantic `v*.*.*` tag pushes,
builds Linux `amd64` and `arm64`, publishes to GHCR, and produces:

- `latest`
- `1`
- `1.0`
- `1.0.0`

It uses `packages: write`, GitHub's repository token, Docker metadata-action
labels, and no registry password stored in the repository.

## 8. Documentation and launch design

The README first viewport contains a precise headline, two-line value
proposition, release/CI/container/Python/MIT badges, a four-node Mermaid flow,
and a working quick start. It then covers what the project does, Meta
prerequisites, Docker/direct/systemd installation, examples, architecture,
security/privacy, pricing, Coexistence, limitations, FAQ, contributing, and
license.

No claim promises zero suspension risk, perpetual free operation, automatic
GDPR compliance, universal Business App coexistence, every message, or a
throughput number without a reproducible benchmark.

`launch/` contains separate, platform-specific drafts and a dated checklist.
The r/opensource draft is explicitly an internal briefing because that
community currently bans AI-generated copy; the Python draft targets the
monthly Showcase Thread rather than a standalone post. Product Hunt is marked
defer-until-validated. Nothing is posted automatically.

GitHub metadata is narrowed to an accurate description and focused topics:

`whatsapp`, `whatsapp-cloud-api`, `whatsapp-business`, `meta-api`, `webhook`,
`self-hosted`, `python`, `docker`, `automation`, `ai-agents`, `telegram`, and
`discord`. The README demonstrates the AI-agent interface through stable JSONL
and `reader.py --json`. `n8n` is deferred until a tested integration exists.

A social-preview brief is prepared, but upload remains a manual GitHub UI step
unless an authenticated supported API becomes available.

## 9. Release gates and order

1. Local tests, syntax checks, Compose validation, Docker build/run, signed
   webhook request, persistence test, and graceful-stop test are green.
2. Push a relaunch branch and open a PR; do not tag yet.
3. Wait for all required PR Actions to pass and inspect the exact commit SHA.
4. Merge without unrelated files, then rerun/inspect CI on `main`.
5. Preflight repository/package permissions, create annotated tag `v1.0.0`
   from the verified `main` SHA, and push only that tag. Do not create the
   GitHub Release yet.
6. Wait for the single tag-triggered GHCR workflow; set package visibility
   public if necessary.
7. Anonymously verify all four tags, verify the manifest contains both
   `linux/amd64` and `linux/arm64`, and run the published host-architecture
   image through health, verification, signed-message, persistence, and stop
   checks.
8. Only then publish the professional GitHub Release from the existing tag.
9. Verify README links/commands and repository metadata live.
10. Stop. Promotion copy is ready, but external posting requires an explicit
    separate instruction.

At release time, revalidate the pinned Python image digest, immutable GitHub
Action SHAs, official Meta documentation links/claims, and community posting
rules. Time-sensitive findings are never treated as permanent.

## 10. Success criteria

The relaunch is complete only when:

- all committed tests and CI jobs are green;
- unsigned or malformed payloads cannot enter JSONL;
- valid signed inbound text and unknown-type events are safely persisted;
- retries with the same message ID do not create a second record in the normal
  single-instance deployment;
- Docker and direct install instructions have been executed from a clean clone;
- the public GHCR tags are anonymously pullable;
- `v1.0.0` and its release notes are live;
- the public README and metadata make only verified claims;
- launch assets exist locally and no promotional post has been sent.
