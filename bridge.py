"""WhatsApp Cloud API readonly bridge.

Import-safe configuration lives here; HTTP handling is wired by the server
boundary in the next implementation task.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import os
from pathlib import Path
import signal
import socket
import sys
import threading
import time
from types import MappingProxyType
from typing import Callable, Mapping
from urllib.parse import parse_qs, urlsplit

from jsonl_store import JsonlStore, StorageError
from whatsapp_webhook import PayloadError, SignatureError, parse_webhook, validate_signature


LOGGER = logging.getLogger("bridge")
MAX_BODY_BYTES = 3_145_728


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class BridgeConfig:
    verify_token: str
    app_secret: str
    bind: str
    port: int
    inbox: Path
    webhook_path: str
    log_level: str
    store_raw: bool
    request_timeout: float
    shutdown_timeout: float

    @property
    def accepted_webhook_paths(self) -> tuple[str, str]:
        return (self.webhook_path, f"{self.webhook_path}/whatsapp-cloud")


_DEFAULTS = MappingProxyType({
    "WA_BIND": "127.0.0.1",
    "WA_PORT": "3100",
    "WA_INBOX": "./inbox/messages.jsonl",
    "WA_WEBHOOK_PATH": "/webhook",
    "WA_LOG_LEVEL": "INFO",
    "WA_STORE_RAW": "true",
    "WA_REQUEST_TIMEOUT": "10",
    "WA_SHUTDOWN_TIMEOUT": "15",
})

_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def load_config(env: Mapping[str, str], base_dir: Path) -> BridgeConfig:
    values = dict(_DEFAULTS)
    values.update(_load_dotenv(Path(base_dir) / ".env"))
    values.update(dict(env))

    verify_token = _required_secret(values.get("WA_VERIFY_TOKEN"),
                                    "WA_VERIFY_TOKEN")
    app_secret = _required_secret(values.get("WA_APP_SECRET"), "WA_APP_SECRET")
    bind = _non_empty(values.get("WA_BIND"), "WA_BIND")
    port = _parse_int_range(values.get("WA_PORT"), "WA_PORT", 1, 65535)
    inbox = Path(_non_empty(values.get("WA_INBOX"), "WA_INBOX"))
    webhook_path = _parse_webhook_path(values.get("WA_WEBHOOK_PATH"))
    log_level = _parse_log_level(values.get("WA_LOG_LEVEL"))
    store_raw = _parse_bool(values.get("WA_STORE_RAW"), "WA_STORE_RAW")
    request_timeout = _parse_float_range(
        values.get("WA_REQUEST_TIMEOUT"), "WA_REQUEST_TIMEOUT", 1.0, 60.0,
    )
    shutdown_timeout = _parse_float_range(
        values.get("WA_SHUTDOWN_TIMEOUT"), "WA_SHUTDOWN_TIMEOUT", 1.0, 60.0,
    )

    return BridgeConfig(
        verify_token=verify_token,
        app_secret=app_secret,
        bind=bind,
        port=port,
        inbox=inbox,
        webhook_path=webhook_path,
        log_level=log_level,
        store_raw=store_raw,
        request_timeout=request_timeout,
        shutdown_timeout=shutdown_timeout,
    )


def main() -> int:
    try:
        config = load_config(os.environ, Path(__file__).resolve().parent)
        logging.basicConfig(level=getattr(logging, config.log_level))
        store = JsonlStore(config.inbox)
        store.initialize()
        server = create_server(config, store)
    except (ConfigError, StorageError, OSError) as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return run_server(server, config.shutdown_timeout)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def make_handler(config: BridgeConfig, store: JsonlStore,
                 clock: Callable[[], datetime]) -> type[BaseHTTPRequestHandler]:
    class WebhookHandler(BaseHTTPRequestHandler):
        server_version = "WhatsAppReadonlyBridge/1.0"

        def setup(self):
            super().setup()
            self.connection.settimeout(config.request_timeout)

        def handle(self):
            self.server._bridge_increment()
            try:
                super().handle()
            finally:
                self.server._bridge_decrement()

        def log_message(self, fmt, *args):
            return

        def do_GET(self):
            start = time.monotonic()
            parsed = urlsplit(self.path)
            path = parsed.path
            status = 500
            records = 0
            duplicates = 0
            try:
                if path == "/health":
                    status = 503 if self.server._bridge_stopping else 200
                    self._json(status, {"status": "ok" if status == 200 else "stopping"})
                    return
                if path in config.accepted_webhook_paths:
                    params = parse_qs(parsed.query, keep_blank_values=True)
                    mode = params.get("hub.mode", [""])[0]
                    token = params.get("hub.verify_token", [""])[0]
                    challenge = params.get("hub.challenge", [""])[0]
                    if mode == "subscribe" and token == config.verify_token:
                        body = challenge.encode("utf-8")
                        status = 200
                        self.send_response(status)
                        self.send_header("Content-Type", "text/plain; charset=utf-8")
                        self.send_header("Cache-Control", "no-store")
                        self.send_header("Content-Length", str(len(body)))
                        self.end_headers()
                        self.wfile.write(body)
                        return
                    status = 403
                    self._json(status, {"error": "forbidden"})
                    return
                status = 404
                self._json(status, {"error": "not_found"})
            finally:
                self._log_request("GET", path, status, start, records, duplicates)

        def do_POST(self):
            start = time.monotonic()
            parsed = urlsplit(self.path)
            path = parsed.path
            status = 500
            records = 0
            duplicates = 0
            try:
                if path not in config.accepted_webhook_paths:
                    status = 404
                    self._json(status, {"error": "not_found"})
                    return

                length, status = self._validated_content_length()
                if status is not None:
                    self._json(status, {"error": "bad_request"})
                    return
                if length > MAX_BODY_BYTES:
                    status = 413
                    self._json(status, {"error": "too_large"})
                    return

                content_type = self.headers.get("Content-Type", "")
                if content_type.split(";", 1)[0].strip().lower() != "application/json":
                    status = 415
                    self._json(status, {"error": "unsupported_media_type"})
                    return

                try:
                    body = self.rfile.read(length)
                except socket.timeout:
                    status = 408
                    self._json(status, {"error": "timeout"})
                    return
                if len(body) != length:
                    status = 400
                    self._json(status, {"error": "short_body"})
                    return

                try:
                    validate_signature(body, self.headers.get("X-Hub-Signature-256"),
                                       config.app_secret)
                except SignatureError:
                    status = 401
                    self._json(status, {"error": "unauthorized"})
                    return

                try:
                    payload = json.loads(body.decode("utf-8"))
                    parsed_records = parse_webhook(payload, clock(),
                                                   store_raw=config.store_raw)
                except (UnicodeDecodeError, json.JSONDecodeError, PayloadError):
                    status = 400
                    self._json(status, {"error": "invalid_payload"})
                    return

                try:
                    append_result = store.append(parsed_records)
                except StorageError:
                    status = 500
                    self._json(status, {"error": "storage_error"})
                    return

                records = append_result.written
                duplicates = append_result.duplicates
                status = 200
                self._json(status, {"records": records, "duplicates": duplicates})
            finally:
                self._log_request("POST", path, status, start, records, duplicates)

        def _validated_content_length(self) -> tuple[int, int | None]:
            if self.headers.get("Transfer-Encoding") is not None:
                return 0, 400
            values = self.headers.get_all("Content-Length")
            if values is None:
                return 0, 411
            if len(values) != 1:
                return 0, 400
            try:
                length = int(values[0])
            except ValueError:
                return 0, 400
            if str(length) != values[0].strip() or length < 0:
                return 0, 400
            return length, None

        def _json(self, status: int, payload: dict[str, object]) -> None:
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _log_request(self, method: str, path: str, status: int, start: float,
                         records: int, duplicates: int) -> None:
            duration_ms = int((time.monotonic() - start) * 1000)
            LOGGER.info(
                "request method=%s path=%s status=%d duration_ms=%d records=%d duplicates=%d",
                method,
                path,
                status,
                duration_ms,
                records,
                duplicates,
            )

    return WebhookHandler


def create_server(config: BridgeConfig, store: JsonlStore,
                  clock: Callable[[], datetime] = utc_now) -> ThreadingHTTPServer:
    handler = make_handler(config, store, clock)
    server = ThreadingHTTPServer((config.bind, config.port), handler)
    server.daemon_threads = True
    server._bridge_stopping = False
    server._bridge_inflight = 0
    server._bridge_condition = threading.Condition()

    def increment() -> None:
        with server._bridge_condition:
            server._bridge_inflight += 1

    def decrement() -> None:
        with server._bridge_condition:
            server._bridge_inflight -= 1
            server._bridge_condition.notify_all()

    server._bridge_increment = increment
    server._bridge_decrement = decrement
    return server


def run_server(server: ThreadingHTTPServer, shutdown_timeout: float) -> int:
    previous_handlers = {}
    stop_event = threading.Event()

    def request_stop(signum, _frame):
        server._bridge_stopping = True
        stop_event.set()
        threading.Thread(target=server.shutdown, daemon=True).start()

    for signum in (signal.SIGINT, signal.SIGTERM):
        try:
            previous_handlers[signum] = signal.getsignal(signum)
            signal.signal(signum, request_stop)
        except ValueError:
            pass

    try:
        try:
            server.serve_forever()
        finally:
            if not stop_event.is_set():
                server._bridge_stopping = True
        deadline = time.monotonic() + shutdown_timeout
        with server._bridge_condition:
            while server._bridge_inflight and time.monotonic() < deadline:
                server._bridge_condition.wait(timeout=0.05)
            drained = server._bridge_inflight == 0
        server.server_close()
        if not drained:
            LOGGER.error("shutdown deadline exceeded inflight=%d",
                         server._bridge_inflight)
            return 1
        return 0
    finally:
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)


def _load_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    result: dict[str, str] = {}
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(),
                                   start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in line:
            raise ConfigError(f".env line {line_no}: missing '='")
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            raise ConfigError(f".env line {line_no}: empty key")
        if key in result:
            raise ConfigError(f".env line {line_no}: duplicate key")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        elif value.startswith(("'", '"')) or value.endswith(("'", '"')):
            raise ConfigError(f".env line {line_no}: mismatched quotes")
        result[key] = value
    return result


def _required_secret(value: str | None, name: str) -> str:
    value = _non_empty(value, name)
    lowered = value.lower()
    if lowered == "change-me" or lowered.startswith("your-"):
        raise ConfigError(f"{name} must not be a placeholder")
    return value


def _non_empty(value: str | None, name: str) -> str:
    if value is None or value == "":
        raise ConfigError(f"{name} is required")
    return value


def _parse_int_range(value: str | None, name: str, minimum: int,
                     maximum: int) -> int:
    value = _non_empty(value, name)
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer") from exc
    if str(parsed) != value.strip():
        raise ConfigError(f"{name} must be an integer")
    if parsed < minimum or parsed > maximum:
        raise ConfigError(f"{name} must be between {minimum} and {maximum}")
    return parsed


def _parse_float_range(value: str | None, name: str, minimum: float,
                       maximum: float) -> float:
    value = _non_empty(value, name)
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number") from exc
    if parsed < minimum or parsed > maximum:
        raise ConfigError(f"{name} must be between {minimum:g} and {maximum:g}")
    return parsed


def _parse_bool(value: str | None, name: str) -> bool:
    value = _non_empty(value, name).lower()
    if value in {"true", "1", "yes", "on"}:
        return True
    if value in {"false", "0", "no", "off"}:
        return False
    raise ConfigError(f"{name} must be a boolean")


def _parse_log_level(value: str | None) -> str:
    level = _non_empty(value, "WA_LOG_LEVEL").upper()
    if level not in _LOG_LEVELS:
        raise ConfigError("WA_LOG_LEVEL is invalid")
    return level


def _parse_webhook_path(value: str | None) -> str:
    value = _non_empty(value, "WA_WEBHOOK_PATH")
    split = urlsplit(value)
    if split.scheme or split.netloc or split.query or split.fragment:
        raise ConfigError("WA_WEBHOOK_PATH must be a URL path only")
    path = split.path.rstrip("/") or "/"
    if not path.startswith("/"):
        raise ConfigError("WA_WEBHOOK_PATH must be absolute")
    if path in {"/", "/health"}:
        raise ConfigError("WA_WEBHOOK_PATH is reserved")
    if any(segment == ".." for segment in path.split("/")):
        raise ConfigError("WA_WEBHOOK_PATH must not contain '..'")
    return path


if __name__ == "__main__":
    raise SystemExit(main())
