# WhatsApp Readonly Bridge v1.0.0 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents are available) or superpowers:executing-plans to implement this plan task-by-task. Use superpowers:terminal-proof-loop whenever a human must run or paste terminal commands.

**Goal:** Relaunch the existing `MarketingBoer/whatsapp-readonly-bridge` repository as a secure, tested, easy-to-install v1.0.0, publish its multi-architecture container to GHCR, and prepare honest platform-specific launch material without posting it.

**Architecture:** Keep the runtime a small Python-standard-library inbound component. `bridge.py` owns configuration, HTTP, and lifecycle; `whatsapp_webhook.py` validates Meta signatures and normalizes complete payloads; `jsonl_store.py` provides durable single-node JSONL storage and retry deduplication. Downstream readers and Telegram/Discord examples remain separate, and nothing in the bridge can send or reply through WhatsApp.

**Tech Stack:** Python 3.10+ standard library, `unittest`, Docker/Compose, systemd, GitHub Actions, GitHub Container Registry, GitHub CLI, Markdown/Mermaid.

---

## Execution contract

- Execute from an isolated worktree, never from the user's dirty `main`
  checkout.
- Preserve the repository URL, Git history, and both accepted webhook routes:
  `/webhook` and `/webhook/whatsapp-cloud`.
- Do not modify or deploy the live `openclaw.scootone.nl` service, its token,
  or any Hermes/HQ configuration.
- Do not edit, delete, stage, or publish the user-owned untracked
  `mcp_server.py` or `tests/test_mcp_server.py` from the original checkout.
- Use only dummy secrets in tests, screenshots, commands, logs, and CI.
- Make each commit substantive. Never add activity-only commits, fake metrics,
  testimonials, stars, downloads, or benchmark claims.
- Stop on a failed gate. Diagnose and repair it before moving forward; never tag
  or release around a red check.
- Cross-terminal release evidence lives only in the explicit mode-`0600` file
  `/tmp/whatsapp-readonly-bridge-v100-release-state`. Create/update it with
  `apply_patch`, never `source` it, parse named fields, and validate every SHA
  as 40 lowercase hex, PR as digits, and clone path under
  `/tmp/whatsapp-bridge-v100-branch-` before use. It contains no secret.
- Remote writes explicitly authorized by the original relaunch request are
  limited to the relaunch branch/PR, repository metadata, `v1.0.0` tag, GHCR
  package visibility, and the GitHub Release. Do not post launch copy anywhere.
- The accepted design is
  [`docs/superpowers/specs/2026-08-14-whatsapp-readonly-bridge-v1-relaunch-design.md`](../specs/2026-08-14-whatsapp-readonly-bridge-v1-relaunch-design.md).
  If implementation pressure conflicts with it, update and review the design
  before changing behavior.

## Chunk 1: Secure and reliable Python core

### Task 1: Create the implementation worktree and protect the baseline

**Files:**

- Inspect only: `/home/wiz/Projects/whatsapp-readonly-bridge`
- Work in: `/home/wiz/.config/superpowers/worktrees/whatsapp-readonly-bridge/v1.0.0`
- Create branch: `relaunch/v1.0.0`

Prerequisite: the design and this plan have been reviewed, committed together
on `plan/v1-relaunch`, and that worktree is clean. The executor must not create
an implementation worktree from untracked planning files.

- [ ] **Step 1: Confirm that the original checkout still contains only the pre-existing user files**

Run:

```bash
git -C /home/wiz/Projects/whatsapp-readonly-bridge status --short --branch
```

Expected: `main...origin/main` plus only untracked `mcp_server.py` and `tests/`.
If anything else appears, record it and avoid that path; do not clean or reset.

- [ ] **Step 2: Create a fresh implementation branch from the reviewed plan**

First prove that the planning artifacts are in the branch tip:

```bash
git -C /home/wiz/.config/superpowers/worktrees/whatsapp-readonly-bridge/v1-relaunch-plan status --short --branch
git -C /home/wiz/.config/superpowers/worktrees/whatsapp-readonly-bridge/v1-relaunch-plan show HEAD:docs/superpowers/specs/2026-08-14-whatsapp-readonly-bridge-v1-relaunch-design.md >/dev/null
git -C /home/wiz/.config/superpowers/worktrees/whatsapp-readonly-bridge/v1-relaunch-plan show HEAD:docs/superpowers/plans/2026-08-14-whatsapp-readonly-bridge-v1-relaunch.md >/dev/null
```

Expected: the plan worktree is clean and both `git show` calls exit `0`.

Run:

```bash
git -C /home/wiz/Projects/whatsapp-readonly-bridge worktree add /home/wiz/.config/superpowers/worktrees/whatsapp-readonly-bridge/v1.0.0 -b relaunch/v1.0.0 plan/v1-relaunch
git -C /home/wiz/.config/superpowers/worktrees/whatsapp-readonly-bridge/v1.0.0 status --short --branch
```

Expected: the worktree is on `relaunch/v1.0.0` and clean. If the branch or
worktree already exists, inspect it and reuse it only if its HEAD is the plan
commit and its status is clean.

- [ ] **Step 3: Record the immutable starting point**

Run:

```bash
git -C /home/wiz/.config/superpowers/worktrees/whatsapp-readonly-bridge/v1.0.0 log -1 --format='%H %s'
git -C /home/wiz/.config/superpowers/worktrees/whatsapp-readonly-bridge/v1.0.0 ls-files
git -C /home/wiz/Projects/whatsapp-readonly-bridge merge-base --is-ancestor 593814b relaunch/v1.0.0
```

Expected: the ancestry check exits `0`, the branch descends from tracked
baseline `593814b`, and neither `mcp_server.py` nor
`tests/test_mcp_server.py` is tracked.

- [ ] **Step 4: Enter and guard the implementation worktree**

Run once in the terminal session used for Tasks 2–19:

```bash
cd /home/wiz/.config/superpowers/worktrees/whatsapp-readonly-bridge/v1.0.0
test "$(git rev-parse --show-toplevel)" = "/home/wiz/.config/superpowers/worktrees/whatsapp-readonly-bridge/v1.0.0"
test "$(git branch --show-current)" = "relaunch/v1.0.0"
mkdir -p tests scripts
```

Expected: all guards exit `0`; only the two empty directories may be new, and
every later relative path resolves inside this implementation worktree. Repeat
the top-level and branch assertions at the start of every new terminal session.

### Task 2: Specify signature validation and payload normalization with tests

**Files:**

- Create: `tests/__init__.py`
- Create: `tests/fixtures.py`
- Create: `tests/test_whatsapp_webhook.py`
- Create: `whatsapp_webhook.py`

- [ ] **Step 1: Add reusable payload and signature fixtures**

In `tests/fixtures.py`, define builders rather than copy-pasting large payloads:
`webhook_payload(*messages, contacts=None, phone_number_id="123456789") -> dict`
and `signed_headers(body: bytes, secret: str) -> dict[str, str]`.

Use only obvious test values such as `wamid.test-1`, `31600000000`,
`test-app-secret-32-characters-long`, and a fixed aware UTC datetime.

- [ ] **Step 2: Write failing signature tests**

Create these tests:

```text
SignatureTests.test_accepts_valid_signature_for_exact_raw_bytes
SignatureTests.test_accepts_uppercase_hex
SignatureTests.test_rejects_changed_body
SignatureTests.test_rejects_missing_wrong_scheme_wrong_length_non_hex_and_mismatch
SignatureTests.test_well_formed_signature_uses_compare_digest
```

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_whatsapp_webhook.SignatureTests -v
```

Expected RED: `ModuleNotFoundError: No module named 'whatsapp_webhook'`. If a
different error occurs, fix the test harness before implementing production
code.

- [ ] **Step 3: Implement the narrow signature API**

Add:

```python
class SignatureError(ValueError):
    pass

def validate_signature(body: bytes, header: str | None, app_secret: str) -> None:
    """Raise SignatureError unless header authenticates the exact body."""
```

Validate the header shape before comparing and never expose the supplied or
expected digest in an exception.

- [ ] **Step 4: Run the signature tests to green**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_whatsapp_webhook.SignatureTests -v
```

Expected: every signature test passes.

- [ ] **Step 5: Write failing parser tests for the stable record schema**

Assert that every record always contains exactly:

```text
ts, message_id, message_timestamp, from, name, type, text,
phone_number_id, raw
```

Create:

```text
ParserSchemaTests.test_normalizes_text_to_exact_nine_key_schema
ParserSchemaTests.test_multi_entry_multi_message_preserves_order
ParserSchemaTests.test_matches_contact_name_by_wa_id
ParserSchemaTests.test_missing_contacts_metadata_and_captions_are_tolerated
ParserSchemaTests.test_invalid_missing_negative_and_out_of_range_timestamps_are_none
ParserSchemaTests.test_raw_false_keeps_raw_key_as_none
ParserSchemaTests.test_raw_is_a_defensive_copy
```

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_whatsapp_webhook.ParserSchemaTests -v
```

Expected: failures because parser behavior is not implemented.

- [ ] **Step 6: Write failing parser tests for malformed and non-message payloads**

Create:

```text
PayloadShapeTests.test_rejects_scalar_wrong_object_and_non_list_entry
PayloadShapeTests.test_rejects_malformed_entry_change_and_value_containers
PayloadShapeTests.test_status_only_and_non_messages_changes_yield_no_records
PayloadShapeTests.test_empty_messages_yields_no_records
PayloadShapeTests.test_rejects_non_list_messages_metadata_and_contacts
PayloadShapeTests.test_rejects_non_mapping_contacts
PayloadShapeTests.test_rejects_missing_empty_and_non_string_required_message_fields
PayloadShapeTests.test_later_malformed_message_rejects_complete_batch
```

Expected policy: valid status/non-message changes return an empty list;
structural errors raise `PayloadError`; no partial result is returned.

- [ ] **Step 7: Write failing type-normalization tests**

Create `SummaryTests.test_fixed_summary_matrix` for the exact design table and
`SummaryTests.test_malformed_optional_subobjects_fall_back_to_placeholder` for
text, media, location, contacts, interactive, reaction, and button fallbacks.

Run the new RED groups immediately:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_whatsapp_webhook.ParserSchemaTests tests.test_whatsapp_webhook.PayloadShapeTests tests.test_whatsapp_webhook.SummaryTests -v
```

Expected RED: missing `parse_webhook`/`PayloadError` or schema assertions, not a
fixture/import error.

- [ ] **Step 8: Implement pure payload parsing**

Add `PayloadError(ValueError)` and
`parse_webhook(payload: object, received_at: datetime, store_raw: bool = True)
-> list[dict[str, object]]`.

Keep this module free of files, sockets, environment reads, logging of user
data, and outbound calls. Convert valid Unix timestamps to aware UTC and make
defensive copies for `raw`.

- [ ] **Step 9: Run the complete parser unit suite**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_whatsapp_webhook -v
```

Expected: all tests pass with no warnings or network activity.

- [ ] **Step 10: Commit the pure webhook boundary**

Run:

```bash
git add whatsapp_webhook.py tests/__init__.py tests/fixtures.py tests/test_whatsapp_webhook.py
git diff --cached --check
git commit -m "feat: validate and normalize Meta webhook payloads"
```

Expected: one substantive commit containing only the parser and its tests.

### Task 3: Build durable JSONL storage and practical retry deduplication

**Files:**

- Create: `jsonl_store.py`
- Create: `tests/test_jsonl_store.py`

- [ ] **Step 1: Write failing initialization and read tests**

Create:

```text
StoreInitializationTests.test_creates_parent_0700_and_file_0600
StoreInitializationTests.test_restricts_existing_modes
StoreInitializationTests.test_empty_and_missing_reads
StoreInitializationTests.test_reads_utf8_jsonl
StoreInitializationTests.test_skips_invalid_utf8_malformed_and_partial_lines_without_content_in_logs
StoreInitializationTests.test_rebuilds_existing_ids_for_restart
```

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_jsonl_store.StoreInitializationTests -v
```

Expected RED: `ModuleNotFoundError: No module named 'jsonl_store'`.

- [ ] **Step 2: Implement the public storage interfaces**

Implement exactly the immutable `AppendResult(written: int, duplicates: int)`
and `ReadResult(records: list[dict], malformed_lines: int)` dataclasses,
`StorageError(RuntimeError)`, `JsonlStore.__init__(path: Path)`,
`JsonlStore.initialize() -> None`, `JsonlStore.append(records: list[dict]) ->
AppendResult`, and `read_jsonl(path: Path) -> ReadResult`.

Use explicit UTF-8 and binary append for atomic batch bytes. Support POSIX
`fcntl.flock` when available and an in-process lock on all platforms. At this
boundary implement initialization and tolerant reading only; `append()`
deliberately raises `NotImplementedError` until Steps 3–5. Rerun
`StoreInitializationTests` and require GREEN before writing append tests.

- [ ] **Step 3: Write failing append and duplicate tests**

Create:

```text
StoreAppendTests.test_writes_one_atomic_utf8_batch
StoreAppendTests.test_same_request_duplicate_is_suppressed
StoreAppendTests.test_repeated_request_duplicate_is_suppressed
StoreAppendTests.test_concurrent_threads_write_one_copy
StoreAppendTests.test_restart_suppresses_existing_id
StoreAppendTests.test_output_is_stable_newline_delimited_json
StoreAppendTests.test_advisory_lock_covers_dedup_write_fsync_and_unlock
```

Use a deterministic `threading.Barrier` in the concurrency test. Run now:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_jsonl_store.StoreAppendTests -v
```

Expected RED: `append()` is absent/incomplete; the race assertion must not rely
on probabilistic repetition. On POSIX, the lock test records calls and requires
`LOCK_EX` before duplicate checking, continued ownership through write/flush/
`fsync`, and `LOCK_UN` only afterward; on platforms without `fcntl`, it uses an
explicit skip reason while the in-process-lock concurrency test still runs.

- [ ] **Step 4: Write failing durability and rollback tests**

Inject write, flush, and `fsync` failures. Require attempted truncation to the
pre-batch byte offset, no mutation of the known-ID set, and `StorageError`.
Test corrupt-tail separation and parent-directory sync on first creation where
supported. Add
`StoreFailureTests.test_rollback_failure_logs_critical_metadata_only` and
assert that neither record text, phone, name, nor raw JSON occurs in the log.
Do not assert filesystem guarantees that the OS cannot provide.

Concrete failure assertions capture `before = inbox.read_bytes()`, call
`append()` inside `assertRaises(StorageError)`, require
`inbox.read_bytes() == before`, then remove the injected fault and require the
same ID to be written once. The rollback-failure case uses `assertLogs`, checks
level `CRITICAL`, and asserts the distinctive body/name/phone/raw fixture
strings are absent.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_jsonl_store.StoreFailureTests -v
```

Expected RED: rollback/error-log behavior is not complete.

- [ ] **Step 5: Finish append/rollback implementation**

Encode and validate the whole new-record batch before opening the file. Under
the locks, re-check IDs, record the old offset, separate a partial last line,
write once, flush, and `fsync`. Update IDs only after success. Log only path,
line number/count, and exception type—never a record body.

- [ ] **Step 6: Run storage tests repeatedly to expose races**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_jsonl_store -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_jsonl_store -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_jsonl_store -v
```

Expected: all three runs pass; the same-ID concurrency test writes exactly one
line each time.

- [ ] **Step 7: Commit the storage boundary**

Run:

```bash
git add jsonl_store.py tests/test_jsonl_store.py
git diff --cached --check
git commit -m "feat: add durable deduplicated JSONL storage"
```

Expected: only storage code and tests are committed.

### Task 4: Make configuration explicit and fail closed

**Files:**

- Modify: `bridge.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing `.env` grammar tests**

Use temporary directories and cover blank lines, full-line comments,
`KEY=VALUE`, matching quotes, inline `#` as data, duplicate keys, empty keys,
missing `=`, and mismatched quotes. Assert process environment values override
file values. Explicitly assert `$NAME`, `${NAME}`, backticks, and `$(command)`
remain literal data and execute/expand nothing. Clear the ambient environment
for each test.

Create:

```text
DotenvTests.test_supported_syntax_and_literal_no_expansion
DotenvTests.test_process_environment_wins_without_mutation
DotenvTests.test_invalid_lines_and_duplicates_raise_config_error
```

- [ ] **Step 2: Write failing `BridgeConfig` validation tests**

Create `ConfigValidationTests` methods covering every variable and boundary
from the design table, including placeholder
secret rejection; ports `1` and `65535`; request/shutdown timeouts `1` and
`60`; accepted boolean spellings; invalid log levels; unsafe webhook paths;
relative `WA_INBOX` behavior from the working directory; and default/custom
route pairs.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_config -v
```

Expected: failures against the current module-level defaults.

- [ ] **Step 3: Refactor import-time settings into an immutable config**

Implement `ConfigError(ValueError)`, the immutable `BridgeConfig` containing
all ten fields from the design table, and
`load_config(env: Mapping[str, str], base_dir: Path) -> BridgeConfig`.

Load `<base_dir>/.env`, overlay the supplied process environment, and return a
fully validated immutable object. Do not mutate `os.environ`, and do not start
a server at import.

- [ ] **Step 4: Prove fail-closed startup and direct `.env` loading**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_config -v
```

Expected: unit tests pass. The real-process missing-config check runs after
`main()` is wired in Task 5, not against a partially refactored entrypoint.

- [ ] **Step 5: Commit the green configuration boundary**

Run:

```bash
git add bridge.py tests/test_config.py
git diff --cached --check
git commit -m "feat: validate bridge configuration and dotenv"
```

Expected: configuration tests are green and no HTTP behavior is claimed by
this commit.

### Task 5: Harden HTTP behavior, logging, and process lifecycle

**Files:**

- Modify: `bridge.py`
- Create: `tests/test_bridge_http.py`
- Create: `tests/test_bridge_lifecycle.py`
- Create: `tests/test_inbound_only.py`
- Create: `scripts/smoke-test.py`
- Create: `tests/test_smoke_test.py`

- [ ] **Step 1: Add an in-process HTTP test harness**

Tests load a valid config through `load_config`, then use
`dataclasses.replace(config, port=0)` only at the injected `create_server`
boundary so the OS chooses an ephemeral port. Production environment parsing
must continue to reject `0`. Use a temporary store and fixed UTC clock. Send
raw requests with `http.client` or a directly constructed socket where
duplicate headers, short bodies, or timeouts must be controlled. Register
server shutdown/socket cleanup before sending any request. Never bind live port
3100.

- [ ] **Step 2: Write failing verification and routing tests**

Create:

```text
BridgeRoutingTests.test_health_is_json_and_no_store
BridgeRoutingTests.test_verification_is_exact_utf8_text_plain_on_both_routes
BridgeRoutingTests.test_wrong_mode_or_token_is_403_json_no_store
BridgeRoutingTests.test_unknown_get_and_post_are_404_json_no_store_without_body_read
BridgeRoutingTests.test_custom_route_pair_works
```

Run RED, implement only routing/response helpers plus the server factory, then
run GREEN:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_bridge_http.BridgeRoutingTests -v
```

Expected RED before implementation: missing `create_server`/wrong status or
headers. Expected GREEN afterward: every method passes; verification alone is
`text/plain`, and every other response is JSON with `Cache-Control: no-store`.

- [ ] **Step 3: Write failing HTTP framing and authentication tests**

Create named `BridgeFramingTests` methods for the exact processing order and
status codes:

- transfer encoding/duplicate/invalid/negative length: `400`;
- no length: `411`;
- 3,145,728 bytes crosses later gates but 3,145,729 bytes returns `413`;
- non-JSON media type: `415`, while `application/json; charset=utf-8` is
  accepted;
- declared-body timeout: `408`; short EOF: `400`;
- missing/malformed/mismatched signature: `401` before JSON parsing;
- signed invalid UTF-8/JSON/scalar/wrong webhook object: `400`.

Run the class to observe assertion failures, implement the bounded exact-read
and signature-first path, then rerun:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_bridge_http.BridgeFramingTests -v
```

Expected GREEN: all matrix cases return promptly and exactly the designed code;
no invalid request reaches the store.

- [ ] **Step 4: Write failing persistence and response tests**

Create:

```text
BridgePersistenceTests.test_signed_text_and_unknown_type_are_persisted_before_200
BridgePersistenceTests.test_status_only_returns_200_without_write
BridgePersistenceTests.test_later_malformed_message_has_zero_partial_write
BridgePersistenceTests.test_duplicate_returns_200_without_second_line
BridgePersistenceTests.test_storage_error_returns_500
```

For the first test, block `store.append()` on an Event and assert the client has
not received `200`; release the Event, then require durable append and `200`.
Also cover signed text and unknown-type messages, status-only `200` with no write,
later malformed message with no partial write, duplicates reported without a
second line, and injected `StorageError` returning `500` so Meta can retry.

Run RED, implement the parse/append/error mapping, and run GREEN:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_bridge_http.BridgePersistenceTests -v
```

- [ ] **Step 5: Test, then implement the import-safe server boundaries**

Add `BridgeStartupTests.test_store_initializes_before_server_bind`,
`test_config_store_and_bind_failures_exit_one`, and
`test_no_server_starts_on_import`. Patch the store initializer and server
factory with ordered sentinels so pre-initializing the HTTP-test store cannot
mask startup order. Failure-log assertions use distinctive dummy secrets and
require them to be absent. Run these tests first and require RED for missing
startup wiring—not a fixture error:

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_bridge_http.BridgeStartupTests -v
```

Then implement the typed `make_handler(config, store, clock)`,
`create_server(config, store, clock=utc_now) -> ThreadingHTTPServer`, and
`main() -> int` boundaries from the approved design. Set the per-connection
timeout before body reads; verify raw bytes before JSON parsing; parse the
complete batch before append; and initialize/scan the store before binding in
`main()`. Rerun `BridgeStartupTests` to GREEN, then run:

```bash
env -i PATH="$PATH" PYTHONDONTWRITEBYTECODE=1 python3 bridge.py
```

Expected: non-zero concise `ConfigError`, no port bind, and no secret output.

- [ ] **Step 6: Capture logs and prove privacy redaction**

Create `BridgeLoggingTests.test_every_response_has_expected_content_type_and_no_store`
and `test_logs_exclude_all_secret_and_message_values`. Tests submit distinctive
values for verify token, app secret, query,
phone, name, body, and raw payload, then assert none appears in captured logs.
Expected request fields are only method, normalized path, status, duration,
record count, and duplicate count. Run RED, disable the inherited request-line
logger and implement metadata-only logging, then rerun this class GREEN.

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_bridge_http.BridgeLoggingTests -v
```

- [ ] **Step 7: Write RED lifecycle tests, then implement bounded draining**

A `multiprocessing` child constructs the server with direct test-only port `0`,
starts `serve_forever()` in a dedicated server thread, sends its bound address
to the parent through a `Pipe`, and uses a blocking store whose
`started`/`release` Events are held by the parent. The parent starts the blocked
request in a separate client thread, waits for `started`, sends SIGTERM to that
exact child PID, releases the append, joins the client, and joins the child
with hard timeouts. Cleanup order is: set `release`, close the client socket,
request shutdown, join server/client/child, then terminate only that child PID
if it is still alive.

Create:

```text
BridgeLifecycleTests.test_threaded_server_sets_connection_timeout
BridgeLifecycleTests.test_health_already_accepted_returns_503_after_shutdown_begins
BridgeLifecycleTests.test_sigterm_drains_inflight_append_and_exits_zero
BridgeLifecycleTests.test_shutdown_deadline_exits_one
BridgeLifecycleTests.test_sigint_uses_same_bounded_path
```

Expected: no test uses port 3100; the blocked request completes with `200` and
the SIGTERM child exits `0` within 15 seconds; the configured deadline child
exits `1`. Always terminate/join only the spawned test PID on failure.

Run the class and require RED for the missing lifecycle boundary:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_bridge_lifecycle.BridgeLifecycleTests -v
```

Then implement internal `run_server(server, shutdown_timeout) -> int` with an
in-flight counter and `Condition`. A signal handler only marks stopping and
notifies a coordinator; that coordinator calls
`ThreadingHTTPServer.shutdown()` outside the active `serve_forever()` thread,
waits for in-flight handlers to drain, closes the server, and returns `0` or
`1`. Rerun the same class to GREEN.

- [ ] **Step 8: Add a reusable dummy-data smoke-test client**

First create failing `SmokeClientTests.test_health_verification_and_signed_dummy_message`
and `test_failure_is_nonzero_and_secrets_are_not_printed`, using only the
ephemeral local server. Then implement `scripts/smoke-test.py`: it accepts
`--base-url`, `--verify-token`, and
`--app-secret`, performs health, verification, and one signed dummy inbound
request, and exit non-zero on any mismatch. It must never print either secret
or support a WhatsApp send endpoint. Run the two tests again to GREEN.

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_smoke_test -v
```

- [ ] **Step 9: Run focused and full core tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_config tests.test_bridge_http tests.test_bridge_lifecycle tests.test_smoke_test -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Expected: all tests pass; no request hangs and no PII/secret appears in output.

- [ ] **Step 10: Run the inbound-only integration and static gates**

Create `InboundOnlyTests.test_signed_inbound_path_makes_no_outbound_calls`.
Send the request with a direct local socket while patching core outbound
primitives (`urllib.request.urlopen`, `socket.create_connection`, and
`http.client.HTTPConnection.request`) to fail/count; require zero calls. Add
`test_core_source_has_no_graph_send_or_access_token_boundary`, parsing all core
runtime Python files. `digest.py`, `examples/discord-webhook.py`, and the local
smoke client are explicit named exceptions; no wildcard exception is allowed.

The integration finishes with `assert_not_called()` on all three outbound
mocks after the direct-socket client receives `200` and the temporary store
contains exactly one record.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_inbound_only -v
if rg -n -i 'graph\.facebook\.com|access[_-]?token|urllib\.request|urlopen|HTTPConnection|send.*whatsapp|reply.*whatsapp' bridge.py whatsapp_webhook.py jsonl_store.py reader.py stats.py examples/api-server.py; then exit 1; else exit 0; fi
```

Expected: integration tests pass and the static shell gate exits `0` only when
there are no matches. The smoke client is separately audited to allow only its
explicitly supplied local bridge URL and no Meta Graph endpoint.

- [ ] **Step 11: Commit the completed server hardening**

Run:

```bash
git add bridge.py scripts/smoke-test.py tests/test_bridge_http.py tests/test_bridge_lifecycle.py tests/test_inbound_only.py tests/test_smoke_test.py
git diff --cached --check
git commit -m "feat: harden webhook HTTP handling and lifecycle"
```

Expected: transport, lifecycle, smoke client, and their tests form one green
commit; configuration already has its own Task 4 commit.

### Task 6: Harden readers and optional downstream examples

**Files:**

- Modify: `reader.py`
- Modify: `stats.py`
- Modify: `digest.py`
- Modify: `examples/discord-webhook.py`
- Modify: `examples/api-server.py`
- Modify: `examples/cron-setup.sh`
- Create: `examples/run-telegram-digest.sh`
- Modify: `examples/sample-inbox.jsonl`
- Modify: `examples/telegram-digest-example.txt`
- Create: `tests/test_reader.py`
- Create: `tests/test_stats.py`
- Create: `tests/test_digest.py`
- Create: `tests/test_examples.py`

- [ ] **Step 1: Write and run failing reader and stats tests**

Clear `WA_INBOX`, Telegram, Discord, and API ambient variables in every test;
inject temporary paths and loopback ephemeral ports. Create tests for tolerant
shared JSONL reading, clean `stats.py --json` output when the
inbox is absent, correct timezone conversion, and stable handling of malformed
lines. Tail tests must cover incomplete final lines, truncation, and inode
replacement without emitting corrupt/partial data. Name the classes
`ReaderTests`, `FollowerTests`, and `StatsTests`, with one method per behavior.

Run RED before production changes:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_reader tests.test_stats -v
```

- [ ] **Step 2: Implement robust local readers**

Reuse `read_jsonl()` for finite reads. Implement the design's inode/offset
tail behavior without loading an unbounded growing file during tail mode.
Never include a malformed line's content in warnings.

Rerun `tests.test_reader tests.test_stats` and require GREEN.

- [ ] **Step 3: Write failing Telegram digest tests**

Patch every network primitive and prove `--dry-run` constructs no request and
makes zero calls even if credential environment variables were present before
module import. Cover aware-timezone cutoffs, a 10-second timeout, 4096-character
chunking, API/non-2xx failure exit `1`, and absence of tokens in errors.

Run RED before changing `digest.py`:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_digest -v
```

- [ ] **Step 4: Fix `digest.py` around an injectable send boundary**

Read credentials after argument parsing only when not dry-run. Return explicit
exit codes, convert timestamps rather than replacing offsets, and split on
safe Unicode string boundaries. Rerun `tests.test_digest` and require GREEN.

- [ ] **Step 5: Write failing Discord and local API tests**

For Discord, require the core inbox default, tolerant reads, 10-second timeout,
2000-character chunks, true `--dry-run` with zero request construction,
non-2xx and Discord JSON/API-error failure status, and no webhook URL in logs. For
the API example, require loopback default, no wildcard CORS, `400` for invalid
or negative limits, clamping to `1..200`, and a prominent unauthenticated API
warning in its module help/documentation.

Run RED before modifying either example:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_examples -v
```

Then implement both examples and rerun the same module to GREEN.

- [ ] **Step 6: Fix examples and scheduled-run guidance**

First extend `tests.test_examples` with executable-mode, emitted-crontab, exact
environment-key, golden-output, and periodic-not-real-time assertions and run
it RED. Then create `examples/run-telegram-digest.sh`, which loads required
`/etc/whatsapp-readonly-bridge-digest.env` with `set -a`, runs the absolute
`/opt/whatsapp-readonly-bridge/digest.py` path, and never echoes its contents.
The documented mode-`0600` file contains only these key names with placeholder
values: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, and `WA_INBOX`.

Make `examples/cron-setup.sh` emit valid comments plus exactly one crontab job:

```cron
0 8 * * * /opt/whatsapp-readonly-bridge/examples/run-telegram-digest.sh --hours 24
```

Extend `tests.test_examples` to parse emitted non-comment/nonblank lines and
require five schedule fields plus the absolute wrapper command. Run `bash -n`
on both scripts. Regenerate `examples/telegram-digest-example.txt` through the
final formatter with fixed dummy input; a golden-file test requires exact
output and clarifies that any reply is in Telegram, never WhatsApp. Make clear
that Telegram/Discord are periodic summaries, not real-time guarantees. Update
sample records to the nine-key schema with no real personal data.

Set and test the wrapper mode, then rerun the examples tests to GREEN:

```bash
chmod 0755 examples/run-telegram-digest.sh
test -x examples/run-telegram-digest.sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_examples -v
```

- [ ] **Step 7: Run all tool/example tests and shell syntax**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_reader tests.test_stats tests.test_digest tests.test_examples -v
bash -n examples/cron-setup.sh
bash -n examples/run-telegram-digest.sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Expected: all tests pass; shell syntax exits `0`; mocked dry runs report zero
network calls for both Telegram and Discord; emitted crontab and golden digest
tests pass.

- [ ] **Step 8: Commit ancillary reliability fixes**

Run:

```bash
git add reader.py stats.py digest.py examples/api-server.py examples/cron-setup.sh examples/discord-webhook.py examples/run-telegram-digest.sh examples/sample-inbox.jsonl examples/telegram-digest-example.txt tests/test_reader.py tests/test_stats.py tests/test_digest.py tests/test_examples.py
git diff --cached --check
git commit -m "fix: make readers and downstream examples resilient"
```

Expected: no unrelated or user-owned files are staged.

- [ ] **Step 9: Recheck the two worktrees after the chunk**

Run:

```bash
git status --short --branch
git -C /home/wiz/Projects/whatsapp-readonly-bridge status --short --branch
if git ls-files --error-unmatch mcp_server.py >/dev/null 2>&1; then exit 1; fi
if git ls-files --error-unmatch tests/test_mcp_server.py >/dev/null 2>&1; then exit 1; fi
if git -C /home/wiz/Projects/whatsapp-readonly-bridge ls-files --error-unmatch mcp_server.py >/dev/null 2>&1; then exit 1; fi
if git -C /home/wiz/Projects/whatsapp-readonly-bridge ls-files --error-unmatch tests/test_mcp_server.py >/dev/null 2>&1; then exit 1; fi
```

Expected: implementation worktree clean; original checkout still shows its two
untracked user-owned paths; all four shell gates exit `0`, proving neither path
became tracked in either worktree.

## Chunk 2: Reproducible deployment, CI, and GHCR publishing

### Task 7: Lock deployment contracts in tests before changing packaging

**Files:**

- Create: `tests/test_deployment_artifacts.py`
- Create: `tests/test_release_audit.py`
- Create: `scripts/release_audit.py`
- Modify later: `Dockerfile`
- Create later: `.dockerignore`
- Modify later: `.gitignore`
- Modify later: `.env.example`
- Modify later: `docker-compose.yml`
- Create later: `docker-compose.build.yml`
- Modify later: `whatsapp-bridge.service`

- [ ] **Step 1: Write failing static deployment-contract tests**

Split assertions into `RuntimeArtifactTests`, `CIArtifactTests`, and
`PublishArtifactTests` so each creation step has an honest green target. Assert
that the eventual artifacts satisfy all of these conditions:

- the official Python base has a versioned tag and a 64-character digest;
- the image uses fixed non-root UID/GID `10001`, `/data`, unbuffered output,
  `STOPSIGNAL SIGTERM`, a dynamic-port healthcheck, and OCI source, license,
  description, title, version, and revision labels;
- no Docker layer defines `WA_VERIFY_TOKEN`, `WA_APP_SECRET`, or a placeholder;
- every `COPY` is allowlisted and `COPY .` is forbidden;
- `.dockerignore` begins deny-all and re-allows only runtime inputs;
- primary Compose uses the GHCR image, requires both secrets, publishes only on
  loopback by default, persists a named `/data` volume, and applies the design's
  runtime restrictions;
- the Compose override alone adds the local build stanza;
- the systemd unit has the required dynamic user, state/environment handling,
  stop timing, journald, and sandbox directives;
- every remote GitHub Action is pinned to a full 40-character SHA;
- the publish workflow is tag-only, strict SemVer without leading-zero numeric
  components, builds exactly amd64/arm64,
  emits provenance/SBOM, and cannot create a GitHub Release.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_deployment_artifacts -v
```

Expected: descriptive failures for the current insecure/missing artifacts.

- [ ] **Step 2: Create a stdlib release audit with failing unit tests first**

`scripts/release_audit.py` must provide importable pure checks plus a CLI. Its
tests create temporary synthetic repositories/image-inspection data and prove
that it rejects:

- tracked `.env`, inbox data, caches, `mcp_server.py`,
  `tests/test_mcp_server.py`, or operator paths;
- unpinned/root/secret-bearing/broad-copy Dockerfiles;
- divergence between Docker COPY and context allowlists;
- symbolic GitHub Action refs;
- Graph send URLs, WhatsApp access-token configuration, WhatsApp send/reply
  handlers, or outbound network calls in the core runtime;
- forbidden files, a root user, missing OCI labels, or secret-like image
  configuration/history in an inspected image.

Telegram and Discord destination files are explicit named network exceptions;
no generic exception pattern is allowed.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_release_audit -v
```

Expected: RED before the audit exists, then green after implementing pure
checks. Do not require Docker for these unit tests.

- [ ] **Step 3: Run the source-only audit and retain expected failures**

Run:

```bash
python3 scripts/release_audit.py --source-only
```

Expected now: non-zero with path-specific findings for the old Docker,
deployment, and missing workflow contracts. Output must never echo file
contents or a possible secret value. Continue to Task 8 to remediate it.

### Task 8: Harden the image and keep the build context secret-free

**Files:**

- Modify: `Dockerfile`
- Create: `.dockerignore`
- Modify: `.gitignore`
- Modify: `.env.example`

- [ ] **Step 1: Revalidate the official multi-architecture base digest**

The latest plan review observed the index digest
`sha256:3b80023c96c186093365774a00db452bfc635476319e71e56a840e251457701f`
for official `python:3.12.14-alpine3.24` on 2026-08-14. Before editing, run:

```bash
docker pull python:3.12.14-alpine3.24
docker image inspect python:3.12.14-alpine3.24 --format '{{json .RepoDigests}}'
docker manifest inspect --verbose python:3.12.14-alpine3.24
```

Expected: the official index digest printed by the first two commands and
manifests including
`linux/amd64` and `linux/arm64`. If the digest differs, verify it against the
official Docker Hub library image and use the newly observed multi-architecture
index; never substitute an architecture-specific child digest.

- [ ] **Step 2: Write the non-root, digest-pinned Dockerfile**

Use the verified base as both versioned tag and digest. Create UID/GID `10001`,
make `/app` read-only-owned and `/data` mode `0700`, then finish with
`USER 10001:10001`. Set only these operational defaults:

```text
PYTHONUNBUFFERED=1
WA_PORT=3100
WA_INBOX=/data/messages.jsonl
```

Explicitly copy only this runtime tree:

```text
/app/bridge.py
/app/whatsapp_webhook.py
/app/jsonl_store.py
/app/reader.py
/app/stats.py
/app/digest.py
/app/examples/api-server.py
/app/examples/discord-webhook.py
```

Add `STOPSIGNAL SIGTERM`, exec-form `CMD`, a `/health` check that reads
`WA_PORT`, and OCI labels. Do not bake either secret into any layer.

- [ ] **Step 3: Make the Docker context deny-by-default**

Start `.dockerignore` with `**`, then re-allow only `Dockerfile`, the six named
root Python files, and the two named example Python files. Ensure `.env`,
`.env.*`, inbox/JSONL data, `.git`, docs,
tests, launch material, caches, `mcp_server.py`, and all unlisted operator
artifacts remain denied.

Update `.gitignore` to ignore `.env.*` while re-allowing `.env.example`, plus
inbox data, JSONL output, caches, coverage/build output, and local operator
files. Never add a rule that hides tracked source unexpectedly.

- [ ] **Step 4: Make `.env.example` complete but unusable as a secret**

List both required values as placeholders that intentionally fail startup:

```dotenv
WA_VERIFY_TOKEN=your-random-verification-token
WA_APP_SECRET=your-meta-app-secret
```

Document all optional variables with the exact design defaults. Do not include
a real token, hostname, phone number, or production inbox path.

- [ ] **Step 5: Re-run static deployment tests for the image subset**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_deployment_artifacts -v
python3 scripts/release_audit.py --source-only
```

Expected: image/context assertions pass; the audit may still fail only for
Compose/systemd/workflows not implemented yet.

### Task 9: Make GHCR Compose the default and local builds explicit

**Files:**

- Modify: `docker-compose.yml`
- Create: `docker-compose.build.yml`
- Modify: `tests/test_deployment_artifacts.py`

- [ ] **Step 1: Replace the primary service with the published image contract**

The primary file must default to:

```yaml
image: ${WA_IMAGE:-ghcr.io/marketingboer/whatsapp-readonly-bridge:latest}
```

Require `${WA_VERIFY_TOKEN:?WA_VERIFY_TOKEN is required}` and
`${WA_APP_SECRET:?WA_APP_SECRET is required}` interpolation.
Inside the container set `WA_BIND=0.0.0.0`, `WA_PORT=3100`, and
`WA_INBOX=/data/messages.jsonl`. Publish
`${WA_HOST:-127.0.0.1}:${WA_HOST_PORT:-3100}:3100` and use a named
`whatsapp-data:/data` volume.

Apply `read_only: true`, a small `/tmp` tmpfs, `cap_drop: [ALL]`,
`no-new-privileges:true`, `init: true`, `restart: unless-stopped`, and
`stop_grace_period: 20s`. Do not add host Docker socket access or an implicit
local build.

- [ ] **Step 2: Add the local-build override**

`docker-compose.build.yml` adds only:

```yaml
services:
  bridge:
    image: whatsapp-readonly-bridge:local
    build:
      context: .
      dockerfile: Dockerfile
```

- [ ] **Step 3: Verify good and fail-closed Compose interpolation**

Run:

```bash
WA_VERIFY_TOKEN=ci-verify-token-unique WA_APP_SECRET=ci-app-secret-unique docker compose -f docker-compose.yml config --quiet
WA_VERIFY_TOKEN=ci-verify-token-unique WA_APP_SECRET=ci-app-secret-unique docker compose -f docker-compose.yml -f docker-compose.build.yml config --quiet
env -i PATH="$PATH" docker compose --env-file /dev/null -f docker-compose.yml config --quiet
```

Expected: first two exit `0`; the third exits non-zero and identifies the
required variable. Repeat the negative check once with only each individual
secret present to prove both are independently required.

### Task 10: Replace the systemd example with a hardened unit

**Files:**

- Modify: `whatsapp-bridge.service`
- Modify: `tests/test_deployment_artifacts.py`

- [ ] **Step 1: Implement the service contract**

Use `network-online.target`, `DynamicUser=yes`,
`WorkingDirectory=/opt/whatsapp-readonly-bridge`, required
`EnvironmentFile=/etc/whatsapp-readonly-bridge.env`, loopback bind,
`WA_INBOX=/var/lib/whatsapp-readonly-bridge/messages.jsonl`,
`StateDirectory=whatsapp-readonly-bridge`, `StateDirectoryMode=0700`, and
`UMask=0077`.

Document creation of `/etc/whatsapp-readonly-bridge.env` as root-owned mode
`0600`. Use journald, `Restart=on-failure`, `RestartSec=5s`, `KillSignal=SIGTERM`, and
`TimeoutStopSec=20s`. Add `NoNewPrivileges`, private tmp/devices,
`ProtectSystem=strict`, `ProtectHome=yes`, empty capability sets, address-family
restriction, `ProtectKernelTunables=yes`, `ProtectKernelModules=yes`,
`ProtectKernelLogs=yes`, `ProtectControlGroups=yes`, `RestrictSUIDSGID=yes`,
`LockPersonality=yes`, and `MemoryDenyWriteExecute=yes`. Do not put a token or
app secret in the unit. If the installed systemd version rejects a directive,
verify whether it is a version-compatibility issue before changing the tracked
unit; do not silently drop hardening.

- [ ] **Step 2: Verify systemd syntax and artifact tests**

Run:

```bash
systemd-analyze verify whatsapp-bridge.service
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_deployment_artifacts -v
```

Expected: systemd reports no unit syntax/dependency errors. Artifact tests may
now fail only because workflows do not yet exist.

- [ ] **Step 3: Commit the deployment runtime artifacts**

Run:

```bash
git add Dockerfile .dockerignore .gitignore .env.example docker-compose.yml docker-compose.build.yml whatsapp-bridge.service tests/test_deployment_artifacts.py
git diff --cached --check
git commit -m "build: harden Docker Compose and systemd deployment"
```

Expected: one deployment commit; no `.env`, inbox, cache, or private experiment
is staged.

### Task 11: Add reproducible container runtime tests

**Files:**

- Create: `tests/test_container_runtime.py`
- Create: `scripts/verify_ghcr.py`
- Create: `tests/test_verify_ghcr.py`
- Modify: `scripts/release_audit.py`
- Modify: `tests/test_release_audit.py`

- [ ] **Step 1: Write a Docker-backed unittest with unique resources**

Read `WHATSAPP_BRIDGE_TEST_IMAGE`. Skip with an explicit reason when that
variable is absent, which is the expected Python-matrix behavior. When it is
present, an unavailable Docker daemon is a hard test failure, not a skip.
Generate names with a fixed project prefix plus a UUID. Register cleanup
immediately after each container, network, or volume creation; cleanup may
remove only those exact generated identifiers.

- [ ] **Step 2: Test the image security/runtime contract**

Prove:

- configured and effective UID are `10001`, not root;
- `/app` rejects writes with `--read-only` while `/data` remains writable;
- health becomes ready after store initialization;
- verification GET succeeds on the published port;
- a signed dummy text payload writes one nine-key record;
- retrying the same `message_id` writes no second line;
- a named volume preserves the record across container replacement;
- `docker stop --time 20` delivers SIGTERM and produces a clean exit.

Create a uniquely named Docker `--internal` bridge network. Start the bridge
container on it without publishing a port, then start a second disposable
container from the same image/network with its entrypoint overridden to Python
and bind-mount the repository's `scripts/smoke-test.py` read-only at
`/tmp/smoke-test.py`. Run that mounted script against the bridge container name
on port 3100. The smoke client is never copied into the production image or
build context. This keeps ingress testable while denying ordinary external routing.
Prove the bridge container cannot reach a known external test address, and
clean only the exact generated containers/network. Loopback host publishing is
tested separately through Compose. Do not use a real Meta callback or
credentials.

- [ ] **Step 3: Extend the release audit to inspect a built image**

For `--image IMAGE`, inspect config/history and a disposable exported
filesystem. Reject root/empty user, absent OCI labels, secret-like environment
or history, and unexpected `.git`, `.env*`, tests, docs, samples, MCP files,
caches, or unallowlisted `/app` files. Clean only the audit's own generated
container.

- [ ] **Step 4: Add a unit-tested anonymous GHCR verifier**

Using only stdlib HTTP/JSON, implement `scripts/verify_ghcr.py`. It obtains an
anonymous GHCR pull token, requests OCI/Docker index manifests for a supplied
repository/tag list, compares `Docker-Content-Digest`, and checks required
platforms. Unit tests mock token and manifest responses, authentication/public-
visibility failure, divergent tags, malformed indexes, and missing platforms;
they make no real registry call.

Run RED before implementation and GREEN afterward:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_verify_ghcr -v
```

- [ ] **Step 5: Build and run the complete container gate**

Run:

```bash
docker build --pull --tag whatsapp-readonly-bridge:test .
WHATSAPP_BRIDGE_TEST_IMAGE=whatsapp-readonly-bridge:test PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_container_runtime -v
python3 scripts/release_audit.py --image whatsapp-readonly-bridge:test
```

Expected: build succeeds; runtime tests explicitly report non-root UID,
read-only-root denial, writable/persistent `/data`, one record after retry, and
clean stop; audit exits `0` with a concise PASS summary.

- [ ] **Step 6: Commit runtime verification tooling**

Run:

```bash
git add scripts/release_audit.py scripts/verify_ghcr.py tests/test_release_audit.py tests/test_container_runtime.py tests/test_verify_ghcr.py
git diff --cached --check
git commit -m "test: verify container runtime and release boundaries"
```

Expected: test tooling only, with no captured image, inbox, or credentials.

### Task 12: Add Python, deployment, and Docker CI

**Files:**

- Create: `.github/workflows/ci.yml`
- Modify: `tests/test_deployment_artifacts.py`

- [ ] **Step 1: Revalidate immutable official Action refs**

Run one `git ls-remote --refs` check for each official repository/tag below:

| Action | Version comment | Required SHA observed 2026-08-14 |
|---|---|---|
| `actions/checkout` | `v7.0.1` | `3d3c42e5aac5ba805825da76410c181273ba90b1` |
| `actions/setup-python` | `v7.0.0` | `5fda3b95a4ea91299a34e894583c3862153e4b97` |
| `docker/setup-qemu-action` | `v4.2.0` | `96fe6ef7f33517b61c61be40b68a1882f3264fb8` |
| `docker/setup-buildx-action` | `v4.2.0` | `bb05f3f5519dd87d3ba754cc423b652a5edd6d2c` |
| `docker/login-action` | `v4.6.0` | `dbcb813823bdd20940b903addbd779551569679f` |
| `docker/metadata-action` | `v6.2.0` | `dc802804100637a589fabce1cb79ff13a1411302` |
| `docker/build-push-action` | `v7.3.0` | `53b7df96c91f9c12dcc8a07bcb9ccacbed38856a` |

Expected: each tag resolves to the recorded 40-character commit. A mismatch is
a release blocker until the official repository is inspected and both SHA and
version comment are updated together.

- [ ] **Step 2: Create the test matrix**

Trigger on pull requests and pushes to `main`; grant only `contents: read`.
Use `ubuntu-24.04`, timeouts, and concurrency cancellation. Test Python 3.10,
3.12, and 3.14 with:

```bash
python -m compileall -q bridge.py whatsapp_webhook.py jsonl_store.py reader.py digest.py stats.py examples tests scripts
python -m unittest discover -s tests -p 'test_*.py' -v
```

Container tests must skip in the Python matrix and run only in the dedicated
deployment job.

- [ ] **Step 3: Create the deployment job**

Validate both Compose combinations with dummy secrets, run
`systemd-analyze verify`, build `whatsapp-readonly-bridge:ci`, execute
`tests.test_container_runtime`, and run `scripts/release_audit.py --image`.
This workflow gets no `packages: write` permission and never pushes an image.

- [ ] **Step 4: Run local workflow/static gates**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_deployment_artifacts.CIArtifactTests tests.test_release_audit -v
rg -n 'uses: [^#[:space:]]+@(main|master|v[0-9])' .github/workflows
python3 -m compileall -q bridge.py whatsapp_webhook.py jsonl_store.py reader.py digest.py stats.py examples tests scripts
```

Expected: CI/release-audit tests and compile pass; `rg` returns no symbolic
Action ref. Version comments may contain `v7.0.1`, but every `uses:` value
contains the full SHA. `PublishArtifactTests` is deliberately not run until
Task 13 creates the publish workflow.

### Task 13: Add tag-only multi-architecture GHCR publishing

**Files:**

- Create: `.github/workflows/publish-container.yml`
- Modify: `tests/test_deployment_artifacts.py`

- [ ] **Step 1: Define the minimal trigger and permissions**

Trigger only on `push` tags matching `v*.*.*`; first reject refs that do not
match
`^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$`. Run this validation
before QEMU, registry login, metadata, or build/push. Use only `contents: read`
and `packages: write`. Fetch enough history to verify the tagged commit is
contained in `origin/main`.

- [ ] **Step 2: Configure GHCR metadata and build**

Use the immutable SHAs from Task 12 for checkout, QEMU, Buildx, login,
metadata, and build-push. Login with `${{ github.actor }}` and
`${{ secrets.GITHUB_TOKEN }}`. For `v1.0.0`, metadata must produce exactly:

```text
latest
1
1.0
1.0.0
```

Build `linux/amd64,linux/arm64`, push to
`ghcr.io/marketingboer/whatsapp-readonly-bridge`, enable GitHub Actions cache,
`sbom: true`, and `provenance: mode=max`. Inspect the pushed digest and require
both target runnable platforms. SBOM/provenance descriptors reported as
`unknown/unknown` are allowed attestations and are not counted as runnable
platforms; any additional runnable OS/architecture is a failure. Do not create
a GitHub Release in this workflow.

- [ ] **Step 3: Complete the workflow contract tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_deployment_artifacts -v
python3 scripts/release_audit.py --source-only
```

Expected: both exit `0`; the audit lists the core inbound-only check and pinned
workflow check as PASS.

- [ ] **Step 4: Commit CI and publication automation**

Run:

```bash
git add .github/workflows/ci.yml .github/workflows/publish-container.yml tests/test_deployment_artifacts.py
git diff --cached --check
git commit -m "ci: test releases and publish tagged GHCR images"
```

Expected: the workflows and their contract tests are one substantive commit.
No tag, package, or release has been created.

## Chunk 3: Honest documentation, release, and promotion readiness

### Task 14: Turn documentation requirements into executable tests

**Files:**

- Create: `tests/test_documentation.py`
- Create later: `SECURITY.md`
- Create later: `CONTRIBUTING.md`
- Create later: `docs/releases/v1.0.0.md`
- Create later: `launch/*.md`

- [ ] **Step 1: Write failing README structure/link tests**

Require the final README to contain the headline/value proposition near the
top, release/CI/container/Python/MIT badges, Mermaid architecture, Quick Start,
Meta prerequisites, configuration, Docker/direct/systemd, examples,
security/privacy, pricing, Coexistence, limitations, FAQ, contributing,
security, and license sections. Parse relative Markdown links and fail with the
source link and resolved missing path.

- [ ] **Step 2: Write failing schema and launch-file tests**

Assert that every `examples/sample-inbox.jsonl` line has the exact nine-key
schema and a unique dummy `message_id`. Require these files:

```text
launch/hackernews.md
launch/reddit-selfhosted.md
launch/reddit-opensource.md
launch/reddit-python.md
launch/devto.md
launch/linkedin.md
launch/x.md
launch/producthunt.md
launch/launch-checklist.md
launch/social-preview.md
launch/competitive-research.md
```

Every platform draft must state `Status: Draft — do not post automatically`.
Require the r/opensource human-rewrite warning, Python Showcase Thread target,
Dev.to `published: false`, Product Hunt defer gate, and
`Last verified: 2026-08-14` plus T-1/Launch/After/STOP sections in
`launch/launch-checklist.md`.

- [ ] **Step 3: Write failing conservative-claim tests**

Scan public copy for these unsupported absolutes and competitor attacks:

```text
zero ban risk
no ban risk
ban-proof
free forever
always free
entire stack costs nothing
no compliance issues
GDPR-friendly
GDPR compliant
every incoming message
all incoming messages
hundreds per minute
works alongside WhatsApp Business App
every WhatsApp bridge
production-ready
used in production
```

Also reject numeric stars, downloads, throughput, user counts, or cost claims
unless the containing document names a dated verifiable source. Tests should
point to line numbers, not silently rewrite copy.

Reject `n8n` in README, release notes, badges, topics, or built-in-integration
claims for v1; it may appear only in the dated competitor/positioning research
or platform drafts as an audience whose tools can consume generic JSONL, never
as a shipped integration. Likewise, `AI`, `CRM`, Telegram, and Discord wording
must distinguish generic JSONL consumption or optional examples from a built-in
real-time connector.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_documentation -v
```

Expected: RED because the README is outdated and required docs/launch assets do
not yet exist.

### Task 15: Rewrite the README around the actual user problem

**Files:**

- Modify: `README.md`
- Modify: `examples/sample-inbox.jsonl`
- Modify: `examples/telegram-digest-example.txt`

- [ ] **Step 1: Replace the first viewport**

Lead with a precise version of:

> Receive inbound WhatsApp messages through Meta's official Cloud API and
> route them into tools you control—without WhatsApp Web or session scraping.

Follow with two short lines explaining inbound-only JSONL and optional
downstream examples. Add working badges for the latest release, `ci.yml`, GHCR,
Python 3.10+, and MIT, then a compact Mermaid flow:

```text
WhatsApp -> Meta Cloud API -> WhatsApp Readonly Bridge -> JSONL / your tools
```

Keep setup visible without making a time-to-install promise.

- [ ] **Step 2: Add the published-image Quick Start**

Use copy-paste commands for clone, `.env.example`, mode `0600`, editing both
secrets, `docker compose up -d`, and loopback `/health`. State clearly that
`WA_VERIFY_TOKEN` is chosen by the operator and `WA_APP_SECRET` comes from the
Meta app; neither is a WhatsApp access token.

Also show:

```bash
docker pull ghcr.io/marketingboer/whatsapp-readonly-bridge:latest
```

The local build path must use both Compose files. Direct Python instructions
must rely on the now-tested `.env` loader and mention the loopback default.

- [ ] **Step 3: Document Meta prerequisites precisely**

Explain public HTTPS, accepted webhook path, verification token, app secret,
webhook configuration, and subscription of the WhatsApp Business Account to
the `messages` field. Link only to the current official Meta documentation
listed in the design for Meta behavior/claims.

State that Business App Coexistence is an eligible onboarding flow with
requirements and limitations, not a universal property of this bridge.

- [ ] **Step 4: Document behavior, configuration, and examples**

Include the exact `BridgeConfig` table and nine-key JSONL schema. Demonstrate
`reader.py --json` as the generic boundary for automation/AI/CRM tools. Describe
reader, stats, Telegram, Discord, and the unauthenticated loopback API example.
Call digest destinations periodic summaries, not live delivery guarantees, and
say media metadata/placeholders are stored but media bytes are not downloaded.

- [ ] **Step 5: Add honest security, privacy, pricing, and limitations text**

State:

- signed accepted-path POST requests are mandatory;
- the bridge contains no WhatsApp Graph send/reply call or access-token config;
- Telegram/Discord examples do make outbound requests;
- JSONL can contain phone numbers, names, bodies, and optionally raw events;
- `WA_STORE_RAW=false` reduces retained raw data but is not anonymization;
- operators remain responsible for retention, access, Meta policy, privacy,
  security, and applicable law;
- Meta currently says user-to-business messages are not charged, while hosting
  and downstream services may cost money and pricing can change;
- practical single-process retry deduplication is not transactional exactly-once
  delivery or a multi-replica guarantee.

Do not claim a suspension probability or benchmark that was not measured.

- [ ] **Step 6: Update examples and run documentation tests**

Regenerate the sample JSONL and Telegram sample from final code using only
dummy data. Make sure any word “reply” in Telegram material means a Telegram
action and cannot be read as a WhatsApp reply feature.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_documentation -v
```

Expected: README structure, relative links already present, sample schema, and
claim checks pass; missing auxiliary/launch files may remain the only failures.

### Task 16: Add security, contribution, and tracked release documentation

**Files:**

- Create: `SECURITY.md`
- Create: `CONTRIBUTING.md`
- Create: `docs/releases/v1.0.0.md`
- Modify: `README.md`
- Modify: `tests/test_documentation.py`

- [ ] **Step 1: Write the security boundary**

Cover supported v1 releases, private reporting, required TLS proxy/tunnel,
secret handling, signature validation, sensitive JSONL, raw retention,
single-writer storage, the unauthenticated local API example, and the explicit
Telegram/Discord outbound exceptions. Do not invent a security email or claim
private reporting is active before enabling and checking it in Task 20.

- [ ] **Step 2: Write contribution rules that protect the scope**

Require tests, dummy data, no real-network test calls, current official Meta
sources for Meta claims, and the local quality commands. State that adding a
WhatsApp send/reply path, access-token setting, or third-party core dependency
requires an explicit design decision and is outside v1 scope.

- [ ] **Step 3: Prepare the exact GitHub Release body**

Use title:

```text
WhatsApp Readonly Bridge v1.0.0 — signed inbound webhooks and durable JSONL
```

Include purpose, highlights, installation, the four image tags, examples,
security defaults, README link, and known limitations. Call out upgrade-impact:
required `WA_APP_SECRET`, placeholder-secret rejection, `401` for unsigned
POSTs, loopback direct bind, stable schema, and named `/data` volume.

- [ ] **Step 4: Run documentation tests and the explicit claim scan**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_documentation -v
if rg -n -i 'zero.?ban|no ban risk|ban-proof|free forever|always free|entire stack costs nothing|no compliance issues|GDPR[- ]friendly|GDPR compliant|every incoming|all incoming|hundreds per minute|works alongside WhatsApp Business app|every WhatsApp bridge|production-ready|used in production' README.md SECURITY.md CONTRIBUTING.md docs/releases/v1.0.0.md; then exit 1; else exit 0; fi
```

Expected: tests may fail only for absent launch files; the claim gate returns
`0` only when there are no matches.

- [ ] **Step 5: Commit public product documentation**

Run:

```bash
git add README.md SECURITY.md CONTRIBUTING.md docs/releases/v1.0.0.md examples/sample-inbox.jsonl examples/telegram-digest-example.txt tests/test_documentation.py
git diff --cached --check
git commit -m "docs: present the verified v1 product and upgrade path"
```

Expected: one documentation commit with no promotional drafts mixed in.

### Task 17: Research the current category and prepare platform-specific drafts

**Files:**

- Create: `launch/competitive-research.md`
- Create: `launch/hackernews.md`
- Create: `launch/reddit-selfhosted.md`
- Create: `launch/reddit-opensource.md`
- Create: `launch/reddit-python.md`
- Create: `launch/devto.md`
- Create: `launch/linkedin.md`
- Create: `launch/x.md`
- Create: `launch/producthunt.md`
- Create: `launch/social-preview.md`
- Create: `launch/launch-checklist.md`

- [ ] **Step 1: Refresh the competitor snapshot from primary repository data**

Use GitHub search/API to identify and then inspect current canonical repositories
for Evolution API, WAHA, WPPConnect, Heyoo, Whatomate, and any closer official
Cloud-API inbound project found by the same queries. Record date, URL, stars,
last push/release, official Cloud API versus session/browser approach,
installation path, Docker support, README positioning/visuals, and demonstrated
use cases. Link sources and label inferences. Do not copy wording or treat stars
as product quality.

The conclusion must preserve the defensible niche: small inbound-only official
Cloud webhook ingress with JSONL and optional sinks—not “the only” WhatsApp
bridge and not a replacement for full inbox/platform products.

- [ ] **Step 2: Recheck current community rules before finalizing advice**

Open the rules/about pages for Hacker News, r/selfhosted, r/opensource,
r/Python, Dev.to, X, LinkedIn, and Product Hunt where public rules exist. Add a
dated source link and allowed submission form to the relevant draft. If access
is unavailable, mark the draft `RULES NEED MANUAL RECHECK`; never infer that
self-promotion is allowed.

- [ ] **Step 3: Write a technical Show HN draft**

Use a title such as:

```text
Show HN: A small inbound-only WhatsApp bridge using Meta's Cloud API
```

Explain problem, architecture, HMAC-before-JSON, JSONL trade-offs, limitations,
and ask for technical feedback. Avoid launch clichés, urgency, and unsupported
comparison claims.

- [ ] **Step 4: Write distinct community drafts**

- r/selfhosted: local data, Docker, no bridge SaaS subscription, operational
  responsibilities, author disclosure.
- r/opensource: internal factual briefing only, prominently stating that the
  audited current rules prohibit AI-generated copy and a human must rewrite it.
- r/Python: monthly Showcase Thread response, emphasizing stdlib architecture
  and readable webhook/storage boundaries; never propose a standalone post if
  current rules still disallow it.

- [ ] **Step 5: Write long- and short-form launch material**

- Dev.to: substantive article with front matter `published: false`, motivation,
  architecture, signature order, dedup/durability trade-offs, privacy boundary,
  and GitHub link only after the technical content.
- LinkedIn: agencies, freelancers, and automation teams; problem-first, no
  savings/compliance promises.
- X: one main post plus an optional short thread; no fabricated metrics.
- Product Hunt: `DEFER UNTIL VALIDATED`, with material prepared but no launch
  date until real users/visual demo justify it.

- [ ] **Step 6: Prepare the social preview brief and launch sequence**

The preview brief specifies accessible contrast, project name, a one-line
value proposition, and the four-node flow; it is not a fake UI screenshot.
`launch-checklist.md` must cover T-1, technical launch, spaced community
distribution, and follow-up, and start with
`Last verified: 2026-08-14`. End with:

```text
STOP — external promotion requires a separate explicit instruction.
```

- [ ] **Step 7: Run launch/documentation gates**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_documentation -v
if rg -n -i 'zero.?ban|no ban risk|ban-proof|free forever|always free|entire stack costs nothing|no compliance issues|GDPR[- ]friendly|GDPR compliant|every incoming|all incoming|hundreds per minute|works alongside WhatsApp Business app|every WhatsApp bridge|production-ready|used in production' launch README.md docs/releases/v1.0.0.md; then exit 1; else exit 0; fi
if rg -L 'Status: Draft — do not post automatically' launch/hackernews.md launch/reddit-selfhosted.md launch/reddit-opensource.md launch/reddit-python.md launch/devto.md launch/linkedin.md launch/x.md launch/producthunt.md; then exit 1; else exit 0; fi
```

Expected: tests pass; both `rg` commands produce no output. The checklist,
social preview, and research note need not carry platform-draft status.

- [ ] **Step 8: Commit launch preparation without publishing it**

Run:

```bash
git add launch tests/test_documentation.py
git diff --cached --check
git commit -m "docs: prepare evidence-based v1 launch material"
```

Expected: launch assets are tracked; no API call has posted them externally.

### Task 18: Complete all local and clean-tree quality gates

**Files:**

- Inspect: all tracked release files
- No new product behavior unless a failing gate exposes a defect

- [ ] **Step 1: Run the complete language and document suite**

Run:

```bash
python3 -m compileall -q bridge.py whatsapp_webhook.py jsonl_store.py reader.py stats.py digest.py examples tests scripts
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py' -v
bash -n examples/cron-setup.sh
systemd-analyze verify whatsapp-bridge.service
git diff --check
```

Expected: every command exits `0` and the unittest run contains substantive
webhook, store, tool, docs, deployment, and release-audit coverage.

- [ ] **Step 2: Validate Compose failure and success modes**

Run:

```bash
WA_VERIFY_TOKEN=release-test-verify-token WA_APP_SECRET=release-test-app-secret docker compose config --quiet
WA_VERIFY_TOKEN=release-test-verify-token WA_APP_SECRET=release-test-app-secret docker compose -f docker-compose.yml -f docker-compose.build.yml config --quiet
env -i PATH="$PATH" docker compose --env-file /dev/null config --quiet
env -i PATH="$PATH" WA_VERIFY_TOKEN=only-one-secret docker compose --env-file /dev/null config --quiet
env -i PATH="$PATH" WA_APP_SECRET=only-one-secret docker compose --env-file /dev/null config --quiet
```

Expected: configured files pass; the other three commands fail before container
startup, proving neither a local `.env` nor one supplied secret masks the
missing-secret gates.

- [ ] **Step 3: Build and exercise local Compose without touching port 3100**

First prove `127.0.0.1:43110` is unused. With project name
`whatsapp-bridge-v100-local`, dummy secrets, and `WA_HOST_PORT=43110`, build and
start using both Compose files. Run `scripts/smoke-test.py`, inspect exactly one
record in the named volume, restart the service, retry the same message, and
require the line count to remain one. Stop gracefully and remove only resources
whose Compose project label equals `whatsapp-bridge-v100-local`.

Expected: health, verification, signed append, persistence, deduplication,
read-only root, and graceful stop all pass.

- [ ] **Step 4: Run the source/image release audit**

Run:

```bash
python3 scripts/release_audit.py --image whatsapp-readonly-bridge:local
git status --short
git ls-files
```

Expected: audit passes; worktree status is clean; tracked files contain no
`.env`, inbox, cache, MCP experiment, or operator-specific path.

- [ ] **Step 5: Reproduce from a clean archive**

Create a unique directory with `mktemp -d`, extract `git archive HEAD` into it,
and from that directory repeat compile, unittest, both Compose configs, Docker
build, runtime tests, systemd verification, and release audit. Retain the
printed temporary path in the execution log; do not delete any broad or
unresolved path.

Expected: the clean archive succeeds without relying on ignored/untracked files
or the developer's environment.

- [ ] **Step 6: Commit only if a gate required a real correction**

If no correction was needed, make no commit. If one was needed, rerun the
affected focused test and the full gate, then use a message describing the
actual correction. Never create a “green CI” or “release prep” activity commit
with no substantive diff.

### Task 19: Push the relaunch PR and prove a clean Git clone

**Files:**

- Remote branch: `relaunch/v1.0.0`
- GitHub PR: new PR to `main`

- [ ] **Step 1: Review the exact branch delta before any remote write**

Run:

```bash
git status --short --branch
git log --oneline --decorate origin/main..HEAD
git diff --stat origin/main...HEAD
git diff --check origin/main...HEAD
```

Expected: clean branch, only meaningful relaunch commits, and no private MCP or
live-service file. Stop if this is not true.

- [ ] **Step 2: Push only the relaunch branch and open one PR**

Run:

```bash
git push -u origin relaunch/v1.0.0
gh pr create --repo MarketingBoer/whatsapp-readonly-bridge --base main --head relaunch/v1.0.0 --title "Relaunch WhatsApp Readonly Bridge as v1.0.0" --body "Signed inbound webhooks, durable JSONL, hardened deployment, tests, documentation, GHCR publishing, and offline launch drafts. No WhatsApp send/reply capability is added."
RELAUNCH_PR_NUMBER=$(gh pr view relaunch/v1.0.0 --repo MarketingBoer/whatsapp-readonly-bridge --json number --jq .number)
test -n "$RELAUNCH_PR_NUMBER"
```

Expected: one PR URL. Do not tag or create a release.

- [ ] **Step 3: Clone the branch through the documented public transport**

Keep the clone command, direct-install block, PR/head comparison, and state-file
creation below in one persistent shell/PTY session; do not split them across
agent terminal calls until the mode-`0600` evidence file exists.

Clone `https://github.com/MarketingBoer/whatsapp-readonly-bridge.git` into a
fresh printed `mktemp -d` directory with `--branch relaunch/v1.0.0 --depth 1`.
In that clone, run unit tests, Compose validation, local Docker build/runtime,
systemd verify, release audit, and relative-link tests.

```bash
BRANCH_CLONE_ROOT=$(mktemp -d -t whatsapp-bridge-v100-branch-XXXXXX)
printf '%s\n' "$BRANCH_CLONE_ROOT"
git clone --branch relaunch/v1.0.0 --depth 1 https://github.com/MarketingBoer/whatsapp-readonly-bridge.git "$BRANCH_CLONE_ROOT/whatsapp-readonly-bridge"
git -C "$BRANCH_CLONE_ROOT/whatsapp-readonly-bridge" rev-parse HEAD
```

Run the named gates from Task 18 with that clone as the working directory and
use another unique Compose project name/unused loopback port.

Also execute the documented direct-Python path before accepting the clone:

1. `cd` into the clone, run `cp .env.example .env`, and use `apply_patch` to
   replace only the two exact secret placeholders with
   `branch-clone-verify-token` and `branch-clone-app-secret`; then run
   `chmod 600 .env`.
2. Prove loopback port `43111` is unused. In one shell, install a cleanup trap,
   start `bridge.py` with only `WA_PORT=43111` and a temporary-clone inbox in
   the process environment, capture `$!` as `BRANCH_BRIDGE_PID`, and poll
   `/health` once per second for at most 30 seconds.
3. Run `scripts/smoke-test.py` against `http://127.0.0.1:43111` with the two
   dummy values, require exactly one JSONL line, send SIGTERM only to
   `BRANCH_BRIDGE_PID`, and require `wait` to return `0` within the configured
   stop window. The trap performs the same exact-PID cleanup on failure.
4. Inspect captured stdout/stderr and require that neither dummy secret, dummy
   phone/name/body, nor query string appears.

After the `apply_patch` edit in item 1, use this single-shell proof loop:

```bash
cd "$BRANCH_CLONE_ROOT/whatsapp-readonly-bridge"
if ss -ltn 'sport = :43111' | rg -q 'LISTEN'; then exit 1; fi
BRANCH_INBOX="$BRANCH_CLONE_ROOT/direct-inbox/messages.jsonl"
BRANCH_LOG="$BRANCH_CLONE_ROOT/direct-bridge.log"
BRANCH_BRIDGE_PID=''
cleanup_branch_bridge() { if test -n "$BRANCH_BRIDGE_PID" && kill -0 "$BRANCH_BRIDGE_PID" 2>/dev/null; then kill -TERM "$BRANCH_BRIDGE_PID"; wait "$BRANCH_BRIDGE_PID" || true; fi; }
trap cleanup_branch_bridge EXIT INT TERM
env -i PATH="$PATH" PYTHONDONTWRITEBYTECODE=1 WA_PORT=43111 WA_INBOX="$BRANCH_INBOX" python3 bridge.py >"$BRANCH_LOG" 2>&1 &
BRANCH_BRIDGE_PID=$!
BRANCH_HEALTHY=0
for BRANCH_ATTEMPT in $(seq 1 30); do if curl -fsS http://127.0.0.1:43111/health >/dev/null; then BRANCH_HEALTHY=1; break; fi; sleep 1; done
test "$BRANCH_HEALTHY" -eq 1
python3 scripts/smoke-test.py --base-url http://127.0.0.1:43111 --verify-token branch-clone-verify-token --app-secret branch-clone-app-secret
test "$(wc -l <"$BRANCH_INBOX")" -eq 1
kill -TERM "$BRANCH_BRIDGE_PID"
BRANCH_STOPPED=0
for BRANCH_STOP_POLL in $(seq 1 15); do BRANCH_PROCESS_STATE=$(ps -o stat= -p "$BRANCH_BRIDGE_PID" 2>/dev/null | tr -d '[:space:]'); case "$BRANCH_PROCESS_STATE" in ''|Z*) BRANCH_STOPPED=1; break;; esac; sleep 1; done
if test "$BRANCH_STOPPED" -ne 1; then kill -KILL "$BRANCH_BRIDGE_PID" 2>/dev/null || true; wait "$BRANCH_BRIDGE_PID" || true; BRANCH_BRIDGE_PID=''; exit 1; fi
if wait "$BRANCH_BRIDGE_PID"; then BRANCH_EXIT_STATUS=0; else BRANCH_EXIT_STATUS=$?; fi
test "$BRANCH_EXIT_STATUS" -eq 0
BRANCH_BRIDGE_PID=''
if rg -F -e 'branch-clone-verify-token' -e 'branch-clone-app-secret' -e '31600000000' -e 'Test User' -e 'hello from smoke test' -e 'hub.verify_token' "$BRANCH_LOG"; then exit 1; fi
trap - EXIT INT TERM
```

The lifecycle unittest supplies the hard 15-second process deadline; this
clean-install block must complete immediately after its explicit SIGTERM. If it
does not, interrupt only the captured PID through the installed trap and fail
the gate.

In the same session, recapture the PR number/head, require the clone HEAD to
match, then use `apply_patch` to create
`/tmp/whatsapp-readonly-bridge-v100-release-state` with exactly:

```text
RELAUNCH_PR_NUMBER=<validated decimal PR number>
REVIEWED_PR_HEAD_SHA=<validated 40-hex clone and PR head SHA>
BRANCH_CLONE_ROOT=<validated /tmp/whatsapp-bridge-v100-branch-* path>
BRANCH_CLONE_SHA=<same validated 40-hex SHA>
VERIFIED_RELEASE_SHA=
VERIFIED_CI_RUN=
```

Run `chmod 600 /tmp/whatsapp-readonly-bridge-v100-release-state` and verify the
mode. If that exact state file already exists from another attempt, inspect it
and stop instead of overwriting evidence silently.

Expected: `.env` loading—not ambient secrets—supplies both required values;
direct health/verification/signed persistence/clean shutdown pass before merge.

Expected: all gates pass without access to the original worktree's untracked
files. Record the clone path and commit SHA in the final report.

- [ ] **Step 4: Wait for PR CI and inspect the exact SHA**

Read (do not source) the state file, validate each field, recapture current PR
state, and compare it to the persisted reviewed values:

```bash
RELEASE_STATE=/tmp/whatsapp-readonly-bridge-v100-release-state
test "$(stat -c '%a' "$RELEASE_STATE")" = 600
RELAUNCH_PR_NUMBER=$(awk -F= '$1=="RELAUNCH_PR_NUMBER"{print $2}' "$RELEASE_STATE")
REVIEWED_PR_HEAD_SHA=$(awk -F= '$1=="REVIEWED_PR_HEAD_SHA"{print $2}' "$RELEASE_STATE")
BRANCH_CLONE_ROOT=$(awk -F= '$1=="BRANCH_CLONE_ROOT"{print $2}' "$RELEASE_STATE")
case "$RELAUNCH_PR_NUMBER" in ''|*[!0-9]*) exit 1;; esac
case "$REVIEWED_PR_HEAD_SHA" in *[!0-9a-f]*|'') exit 1;; esac
test "${#REVIEWED_PR_HEAD_SHA}" -eq 40
case "$BRANCH_CLONE_ROOT" in /tmp/whatsapp-bridge-v100-branch-*) ;; *) exit 1;; esac
CURRENT_PR_HEAD_SHA=$(gh pr view "$RELAUNCH_PR_NUMBER" --repo MarketingBoer/whatsapp-readonly-bridge --json headRefOid --jq .headRefOid)
test "$CURRENT_PR_HEAD_SHA" = "$REVIEWED_PR_HEAD_SHA"
test "$(git -C "$BRANCH_CLONE_ROOT/whatsapp-readonly-bridge" rev-parse HEAD)" = "$REVIEWED_PR_HEAD_SHA"
gh pr checks "$RELAUNCH_PR_NUMBER" --repo MarketingBoer/whatsapp-readonly-bridge --watch --fail-fast
gh pr view "$RELAUNCH_PR_NUMBER" --repo MarketingBoer/whatsapp-readonly-bridge --json headRefOid,mergeStateStatus,statusCheckRollup
```

Expected: every required job succeeds and the reported head SHA equals the
clean-clone SHA. If any job is red, fix through a meaningful commit and repeat
local plus remote checks.

### Task 20: Merge, set accurate repository metadata, and verify `main`

**Files/state:**

- GitHub default branch: `main`
- Repository metadata and security settings

- [ ] **Step 1: Merge using the repository's enabled non-destructive policy**

Prefer a normal merge so the substantive commits remain visible:

```bash
RELEASE_STATE=/tmp/whatsapp-readonly-bridge-v100-release-state
RELAUNCH_PR_NUMBER=$(awk -F= '$1=="RELAUNCH_PR_NUMBER"{print $2}' "$RELEASE_STATE")
REVIEWED_PR_HEAD_SHA=$(awk -F= '$1=="REVIEWED_PR_HEAD_SHA"{print $2}' "$RELEASE_STATE")
case "$RELAUNCH_PR_NUMBER" in ''|*[!0-9]*) exit 1;; esac
case "$REVIEWED_PR_HEAD_SHA" in *[!0-9a-f]*|'') exit 1;; esac
test "${#REVIEWED_PR_HEAD_SHA}" -eq 40
CURRENT_PR_HEAD_SHA=$(gh pr view "$RELAUNCH_PR_NUMBER" --repo MarketingBoer/whatsapp-readonly-bridge --json headRefOid --jq .headRefOid)
test "$CURRENT_PR_HEAD_SHA" = "$REVIEWED_PR_HEAD_SHA"
gh pr merge "$RELAUNCH_PR_NUMBER" --repo MarketingBoer/whatsapp-readonly-bridge --merge --delete-branch --match-head-commit "$REVIEWED_PR_HEAD_SHA"
git fetch origin main --tags
```

Expected: merged PR; local original dirty `main` checkout was never switched,
reset, or cleaned.

- [ ] **Step 2: Wait for CI on the merged main SHA**

Recapture the merged PR and SHA, assert it is still the current `main`, and poll
for the matching CI run for at most five minutes (10-second intervals):

```bash
RELEASE_STATE=/tmp/whatsapp-readonly-bridge-v100-release-state
RELAUNCH_PR_NUMBER=$(awk -F= '$1=="RELAUNCH_PR_NUMBER"{print $2}' "$RELEASE_STATE")
VERIFIED_RELEASE_SHA=$(gh pr view "$RELAUNCH_PR_NUMBER" --repo MarketingBoer/whatsapp-readonly-bridge --json mergeCommit --jq .mergeCommit.oid)
case "$VERIFIED_RELEASE_SHA" in *[!0-9a-f]*|'') exit 1;; esac
test "${#VERIFIED_RELEASE_SHA}" -eq 40
test "$(git rev-parse origin/main)" = "$VERIFIED_RELEASE_SHA"
RELEASE_CI_RUN=''
for CI_POLL in $(seq 1 30); do RELEASE_CI_RUN=$(gh run list --repo MarketingBoer/whatsapp-readonly-bridge --workflow ci.yml --commit "$VERIFIED_RELEASE_SHA" --event push --limit 100 --json databaseId,headSha --jq 'map(select(.headSha == "'"$VERIFIED_RELEASE_SHA"'")) | if length == 1 then .[0].databaseId else empty end'); test -n "$RELEASE_CI_RUN" && break; sleep 10; done
test -n "$RELEASE_CI_RUN"
gh run watch "$RELEASE_CI_RUN" --repo MarketingBoer/whatsapp-readonly-bridge --exit-status
```

Expected: success for that exact SHA. A successful older run is insufficient.
Use `apply_patch` to replace only `VERIFIED_RELEASE_SHA=` and
`VERIFIED_CI_RUN=` in the mode-`0600` release-state file with these validated
values. If a later corrective PR is needed, repeat its clean clone, exact main
CI, source/claim/pin, and permission preflight, then replace these two evidence
fields with that newer fully verified SHA/run; do not keep deriving release
state from the original PR.

- [ ] **Step 3: Apply and verify focused repository metadata**

Use this exact description:

```text
Self-hosted inbound WhatsApp Cloud API bridge with signed webhooks, durable JSONL storage, and no WhatsApp send/reply capability.
```

Replace topics with exactly:

```text
whatsapp, whatsapp-cloud-api, whatsapp-business, meta-api, webhook,
self-hosted, python, docker, automation, ai-agents, telegram, discord
```

Leave homepage blank unless a real project-specific page has been verified.
Enable private vulnerability reporting through the official GitHub API, then
read it back. If the account/repository cannot enable it, record a maintainer
blocker and keep `SECURITY.md` wording conditional.

Apply and verify with:

```bash
gh api --method PATCH repos/MarketingBoer/whatsapp-readonly-bridge -f description='Self-hosted inbound WhatsApp Cloud API bridge with signed webhooks, durable JSONL storage, and no WhatsApp send/reply capability.' -f homepage=''
gh api --method PUT repos/MarketingBoer/whatsapp-readonly-bridge/topics -f 'names[]=whatsapp' -f 'names[]=whatsapp-cloud-api' -f 'names[]=whatsapp-business' -f 'names[]=meta-api' -f 'names[]=webhook' -f 'names[]=self-hosted' -f 'names[]=python' -f 'names[]=docker' -f 'names[]=automation' -f 'names[]=ai-agents' -f 'names[]=telegram' -f 'names[]=discord'
gh api --method PUT repos/MarketingBoer/whatsapp-readonly-bridge/private-vulnerability-reporting
gh api --include repos/MarketingBoer/whatsapp-readonly-bridge/private-vulnerability-reporting
gh repo view MarketingBoer/whatsapp-readonly-bridge --json description,homepageUrl,repositoryTopics
```

Expected: exact description/topics and no invented homepage.

- [ ] **Step 4: Revalidate time-sensitive sources immediately before tagging**

Reopen the four official Meta pages in the design and compare actual current
text—not merely HTTP status—to the README/release claims. Recheck the Python
base digest and all Action tag SHAs. Recheck launch-community rules and update
only dated internal drafts if needed. Read the entire README, security file,
release notes, examples, and launch copy—not only regex hits—and create a claim
ledger in the execution report: factual claim, evidence URL/code/test, and
whether it is direct evidence or a clearly labelled inference. Confirm there
is no shipped `n8n` integration/topic and no legacy production-use,
competitor-universality, cost, ban, GDPR, capacity, or user-count claim.

Expected: a dated evidence note in the execution report; any material claim or
pin mismatch is fixed through a reviewed PR before tagging.

- [ ] **Step 5: Preflight Actions, package ownership, and visibility authority**

Before any immutable tag, verify repository ADMIN permission, Actions enabled,
the publish workflow's `packages: write`, and package namespace state:

```bash
gh api repos/MarketingBoer/whatsapp-readonly-bridge --jq '.permissions.admin'
gh api repos/MarketingBoer/whatsapp-readonly-bridge/actions/permissions
gh api repos/MarketingBoer/whatsapp-readonly-bridge/contents/.github/workflows/publish-container.yml --jq .sha
gh api '/user/packages?package_type=container&per_page=100'
```

Expected: admin is `true`, Actions is enabled, the reviewed workflow is present,
and no package owned by another namespace conflicts. If the package already
exists, open its authenticated settings and confirm it is linked to this
repository and public, or that the maintainer can access the exact “Change
visibility” control. If it does not exist, record that the first tag push will
create the user-owned package and that public visibility requires the official
package-settings UI checkpoint in Task 21. Lack of that authority/access is a
pre-tag blocker.

### Task 21: Tag only the verified commit and publish GHCR

**Files/state:**

- Annotated Git tag: `v1.0.0`
- GHCR package: `ghcr.io/marketingboer/whatsapp-readonly-bridge`
- Use: `scripts/verify_ghcr.py`
- Use: `tests/test_verify_ghcr.py`

- [ ] **Step 1: Re-run the tracked anonymous registry-verifier tests before the tag**

Confirm the reviewed verifier from Task 11 is tracked on the verified merged
SHA and
that its mocked token/manifest, authentication/public-visibility, tag-divergence,
malformed-index, and missing-platform cases still pass.

Run:

```bash
git fetch origin main --tags
RELEASE_STATE=/tmp/whatsapp-readonly-bridge-v100-release-state
VERIFIED_RELEASE_SHA=$(awk -F= '$1=="VERIFIED_RELEASE_SHA"{print $2}' "$RELEASE_STATE")
VERIFIED_CI_RUN=$(awk -F= '$1=="VERIFIED_CI_RUN"{print $2}' "$RELEASE_STATE")
case "$VERIFIED_RELEASE_SHA" in *[!0-9a-f]*|'') exit 1;; esac
test "${#VERIFIED_RELEASE_SHA}" -eq 40
case "$VERIFIED_CI_RUN" in ''|*[!0-9]*) exit 1;; esac
test "$(git rev-parse origin/main)" = "$VERIFIED_RELEASE_SHA"
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_verify_ghcr -v
git show "$VERIFIED_RELEASE_SHA":scripts/verify_ghcr.py >/dev/null
```

Expected: all mocked cases pass and
`git show VERIFIED_RELEASE_SHA:scripts/verify_ghcr.py` succeeds. If `origin/main`
has moved, stop and repeat the main-CI, clean-install, source, and permission
gates on that new exact SHA before treating it as verified. No new commit or
follow-up PR should be needed here; if the verifier is absent, return to the
normal PR/CI flow before tagging.

- [ ] **Step 2: Prove the version does not already exist**

Run:

```bash
git ls-remote --tags origin refs/tags/v1.0.0
gh release view v1.0.0 --repo MarketingBoer/whatsapp-readonly-bridge
```

Expected: no remote tag and the release lookup returns not found. If either
exists, stop; never move or overwrite a public version tag.

- [ ] **Step 3: Create and push one annotated tag from the verified SHA**

Recapture the verified merge SHA in this same shell block, assert `main` has
not drifted, and create the local tag:

```bash
RELEASE_STATE=/tmp/whatsapp-readonly-bridge-v100-release-state
VERIFIED_RELEASE_SHA=$(awk -F= '$1=="VERIFIED_RELEASE_SHA"{print $2}' "$RELEASE_STATE")
case "$VERIFIED_RELEASE_SHA" in *[!0-9a-f]*|'') exit 1;; esac
test "${#VERIFIED_RELEASE_SHA}" -eq 40
test "$(git rev-parse origin/main)" = "$VERIFIED_RELEASE_SHA"
git tag -a v1.0.0 "$VERIFIED_RELEASE_SHA" -m "WhatsApp Readonly Bridge v1.0.0"
```

Inspect it:

```bash
git show --no-patch --format=fuller v1.0.0
```

Then push only the tag:

```bash
git push origin refs/tags/v1.0.0
```

Expected: the tag points exactly to green `origin/main`. Do not create the
GitHub Release yet.

- [ ] **Step 4: Wait for exactly one tag-triggered publish workflow**

Poll for at most five minutes until exactly one `publish-container.yml` run has
event `push`, head branch `v1.0.0`, and the tag's peeled commit SHA:

```bash
VERIFIED_RELEASE_SHA=$(git rev-parse 'v1.0.0^{}')
RELEASE_PUBLISH_RUN=''
for PUBLISH_POLL in $(seq 1 30); do PUBLISH_RUN_COUNT=$(gh run list --repo MarketingBoer/whatsapp-readonly-bridge --workflow publish-container.yml --branch v1.0.0 --event push --commit "$VERIFIED_RELEASE_SHA" --limit 100 --json databaseId,headBranch,headSha --jq 'map(select(.headBranch == "v1.0.0" and .headSha == "'"$VERIFIED_RELEASE_SHA"'")) | length'); test "$PUBLISH_RUN_COUNT" -gt 1 && exit 1; if test "$PUBLISH_RUN_COUNT" -eq 1; then RELEASE_PUBLISH_RUN=$(gh run list --repo MarketingBoer/whatsapp-readonly-bridge --workflow publish-container.yml --branch v1.0.0 --event push --commit "$VERIFIED_RELEASE_SHA" --limit 100 --json databaseId,headBranch,headSha --jq 'map(select(.headBranch == "v1.0.0" and .headSha == "'"$VERIFIED_RELEASE_SHA"'"))[0].databaseId'); break; fi; sleep 10; done
test -n "$RELEASE_PUBLISH_RUN"
gh run watch "$RELEASE_PUBLISH_RUN" --repo MarketingBoer/whatsapp-readonly-bridge --exit-status
```

Expected: one successful run; no GitHub Release has appeared.

- [ ] **Step 5: Make the package public only if needed**

Inspect the exact authenticated package through the GitHub Packages REST API:

```bash
gh api /user/packages/container/whatsapp-readonly-bridge --jq '{name,package_type,visibility,html_url,repository}'
```

GitHub's supported Packages REST API does not offer a visibility-update
endpoint. If `visibility` is not `public`, open only
`https://github.com/users/MarketingBoer/packages/container/whatsapp-readonly-bridge/settings`,
confirm package name/owner/repository, use **Change visibility → Public**, and
acknowledge GitHub's irreversibility warning. This is within the requested
public-GHCR scope, but it is an explicit authenticated UI checkpoint; use safe
browser automation only when the logged-in owner and exact target are visibly
confirmed, otherwise pause for the maintainer. Read the package back with the
command above and require `public`. A `404` or permission error is a genuine
blocker, never evidence of success.

- [ ] **Step 6: Verify anonymous tags, architectures, and pulls**

Run:

```bash
python3 scripts/verify_ghcr.py ghcr.io/marketingboer/whatsapp-readonly-bridge latest 1 1.0 1.0.0
```

Create an empty temporary Docker config directory and, with `DOCKER_CONFIG`
pointing to it, run `docker pull` separately for all four tags:

```bash
RELEASE_DOCKER_CONFIG=$(mktemp -d -t whatsapp-bridge-docker-XXXXXX)
DOCKER_CONFIG="$RELEASE_DOCKER_CONFIG" docker pull ghcr.io/marketingboer/whatsapp-readonly-bridge:latest
DOCKER_CONFIG="$RELEASE_DOCKER_CONFIG" docker pull ghcr.io/marketingboer/whatsapp-readonly-bridge:1
DOCKER_CONFIG="$RELEASE_DOCKER_CONFIG" docker pull ghcr.io/marketingboer/whatsapp-readonly-bridge:1.0
DOCKER_CONFIG="$RELEASE_DOCKER_CONFIG" docker pull ghcr.io/marketingboer/whatsapp-readonly-bridge:1.0.0
```

Expected: the verifier reports one shared index digest and both architectures;
all four pulls succeed without stored GitHub credentials.

- [ ] **Step 7: Exercise the actual published image**

Use the same unique-resource container suite with
`WHATSAPP_BRIDGE_TEST_IMAGE=ghcr.io/marketingboer/whatsapp-readonly-bridge:1.0.0`.
Then use primary `docker-compose.yml` only on unused loopback port `43120` with
dummy secrets. Require health, verification, signed message, persisted
nine-key JSONL, restart persistence, retry suppression, non-root UID,
read-only root, and clean stop within 20 seconds.

Run:

```bash
WHATSAPP_BRIDGE_TEST_IMAGE=ghcr.io/marketingboer/whatsapp-readonly-bridge:1.0.0 PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_container_runtime -v
if ss -ltn 'sport = :43120' | rg -q 'LISTEN'; then exit 1; fi
cleanup_published_compose() { WA_IMAGE=ghcr.io/marketingboer/whatsapp-readonly-bridge:1.0.0 WA_VERIFY_TOKEN=published-verify-token WA_APP_SECRET=published-app-secret WA_HOST=127.0.0.1 WA_HOST_PORT=43120 docker compose -p whatsapp-bridge-v100-published down || true; }
trap cleanup_published_compose EXIT INT TERM
WA_IMAGE=ghcr.io/marketingboer/whatsapp-readonly-bridge:1.0.0 WA_VERIFY_TOKEN=published-verify-token WA_APP_SECRET=published-app-secret WA_HOST=127.0.0.1 WA_HOST_PORT=43120 docker compose -p whatsapp-bridge-v100-published up -d --wait --wait-timeout 30
python3 scripts/smoke-test.py --base-url http://127.0.0.1:43120 --verify-token published-verify-token --app-secret published-app-secret
test "$(WA_IMAGE=ghcr.io/marketingboer/whatsapp-readonly-bridge:1.0.0 WA_VERIFY_TOKEN=published-verify-token WA_APP_SECRET=published-app-secret WA_HOST=127.0.0.1 WA_HOST_PORT=43120 docker compose -p whatsapp-bridge-v100-published exec -T bridge wc -l /data/messages.jsonl | tr -d '[:space:]')" -eq 1
WA_IMAGE=ghcr.io/marketingboer/whatsapp-readonly-bridge:1.0.0 WA_VERIFY_TOKEN=published-verify-token WA_APP_SECRET=published-app-secret WA_HOST=127.0.0.1 WA_HOST_PORT=43120 docker compose -p whatsapp-bridge-v100-published restart bridge
for PUBLISHED_HEALTH_POLL in $(seq 1 30); do if curl -fsS http://127.0.0.1:43120/health >/dev/null; then break; fi; test "$PUBLISHED_HEALTH_POLL" -lt 30; sleep 1; done
python3 scripts/smoke-test.py --base-url http://127.0.0.1:43120 --verify-token published-verify-token --app-secret published-app-secret
test "$(WA_IMAGE=ghcr.io/marketingboer/whatsapp-readonly-bridge:1.0.0 WA_VERIFY_TOKEN=published-verify-token WA_APP_SECRET=published-app-secret WA_HOST=127.0.0.1 WA_HOST_PORT=43120 docker compose -p whatsapp-bridge-v100-published exec -T bridge wc -l /data/messages.jsonl | tr -d '[:space:]')" -eq 1
WA_IMAGE=ghcr.io/marketingboer/whatsapp-readonly-bridge:1.0.0 WA_VERIFY_TOKEN=published-verify-token WA_APP_SECRET=published-app-secret WA_HOST=127.0.0.1 WA_HOST_PORT=43120 docker compose -p whatsapp-bridge-v100-published stop -t 20 bridge
docker volume inspect whatsapp-bridge-v100-published_whatsapp-data --format '{{index .Labels "com.docker.compose.project"}}'
WA_IMAGE=ghcr.io/marketingboer/whatsapp-readonly-bridge:1.0.0 WA_VERIFY_TOKEN=published-verify-token WA_APP_SECRET=published-app-secret WA_HOST=127.0.0.1 WA_HOST_PORT=43120 docker compose -p whatsapp-bridge-v100-published down -v
trap - EXIT INT TERM
```

Expected: the volume label printed immediately before cleanup is exactly
`whatsapp-bridge-v100-published`; only then may `down -v` remove that project's
resources. If any prior command fails, inspect and clean the same exact project
name—never a broad container or volume pattern.

Expected: every documented published-image path works. Clean only the exact
generated test containers/volumes after confirming their labels/names.

### Task 22: Verify the public tag, then publish the GitHub Release

**Files/state:**

- Existing tag: `v1.0.0`
- Existing notes: `docs/releases/v1.0.0.md`

- [ ] **Step 1: Clone the public tag from scratch before creating a Release**

Keep Steps 1–2 in one persistent shell/PTY session so the validated temporary
clone root cannot drift between terminal calls.

Create a new printed `mktemp -d` directory and run:

```bash
RELEASE_CLONE_ROOT=$(mktemp -d -t whatsapp-bridge-v100-clone-XXXXXX)
printf '%s\n' "$RELEASE_CLONE_ROOT"
git clone --branch v1.0.0 --depth 1 https://github.com/MarketingBoer/whatsapp-readonly-bridge.git "$RELEASE_CLONE_ROOT/whatsapp-readonly-bridge"
cd "$RELEASE_CLONE_ROOT/whatsapp-readonly-bridge"
```

Confirm `git rev-parse HEAD` equals the peeled `v1.0.0` commit and the verified
merge SHA.

- [ ] **Step 2: Re-run every documented install path from that clone**

Run the full unittest suite, relative-link/documentation tests, fail-closed and
valid Compose configs, the exact Task 19 `.env` direct-Python proof loop on
unused port `43112`, local Docker build/runtime audit, anonymous four-tag pull,
and the exact Task 21 primary-Compose published-image check using a new project
name and unused port `43121`. Recapture every temporary directory, PID, image,
container, network, volume, and port variable within its own command block;
the validated `RELEASE_CLONE_ROOT` is the only state retained from Step 1 in
the same persistent session. Reuse no state from earlier tasks. Cleanup is limited to exact captured
PID/resource names after label verification.

Expected: every README installation path claimed as tested succeeds from the
public tag without developer-only files. If this fails, do not create the
GitHub Release and never move the public tag; diagnose whether a corrective
v1.0.1 is required.

- [ ] **Step 3: Create the release only after all source and GHCR gates are green**

Run:

```bash
gh release create v1.0.0 --repo MarketingBoer/whatsapp-readonly-bridge --verify-tag --title "WhatsApp Readonly Bridge v1.0.0 — signed inbound webhooks and durable JSONL" --notes-file docs/releases/v1.0.0.md
```

Expected: a non-draft, non-prerelease release URL for the existing verified tag.

- [ ] **Step 4: Verify live GitHub state**

Run:

```bash
gh release view v1.0.0 --repo MarketingBoer/whatsapp-readonly-bridge --json name,tagName,targetCommitish,isDraft,isPrerelease,url
gh repo view MarketingBoer/whatsapp-readonly-bridge --json description,homepageUrl,repositoryTopics
```

Also fetch the public README and resolve its relative links, re-run the
anonymous GHCR verifier, and confirm the release/tag commit equals the verified
main SHA.

Expected: release/tag/README/metadata/package agree on v1.0.0. A social-preview
brief may exist, but do not claim an image is uploaded unless verified in the
GitHub UI.

- [ ] **Step 5: Produce the compact evidence-backed handoff**

Report:

- changed files grouped by core, deployment, docs, and launch;
- exact tests/builds/clean-install paths and results;
- PR, main SHA, Actions run URLs, tag, Release URL, package visibility, image
  digest/platforms, and four verified tags;
- exact direct, local-build, Compose, and public-image paths tested;
- open risks such as real Meta end-to-end delivery, platform-rule drift,
  single-node filesystem limits, and manual social-preview upload;
- prepared launch files and recommended sequence;
- only genuine blockers requiring the maintainer.

End by stating that no external promotional post was made.

## Autonomous completion definition

The executor continues without asking for routine choices while all actions
remain inside this plan. It stops only for a genuine blocker such as lost
GitHub permission, unavailable Docker daemon after retry, inability to make the
package public, a failing official-platform requirement that changes scope, or
a conflict with user-owned changes. “Interesting but not required” improvements
become issues or follow-up notes; they do not delay v1.0.0.

The work is complete only when code/CI/build/docs are green, all four GHCR tags
are anonymously pullable, the public image passes the clean runtime test, the
GitHub Release exists on the verified main SHA, the README is truthful, and all
launch material remains unposted.
