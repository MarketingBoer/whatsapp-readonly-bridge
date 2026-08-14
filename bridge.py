"""WhatsApp Cloud API readonly bridge.

Import-safe configuration lives here; HTTP handling is wired by the server
boundary in the next implementation task.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import sys
from types import MappingProxyType
from typing import Mapping
from urllib.parse import urlsplit


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
        load_config(os.environ, Path(__file__).resolve().parent)
    except ConfigError as exc:
        print(f"ConfigError: {exc}", file=sys.stderr)
        return 1
    print("bridge server startup is implemented in the HTTP hardening task",
          file=sys.stderr)
    return 1


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
