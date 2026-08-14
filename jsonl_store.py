"""Durable single-node JSONL storage for normalized webhook records."""
from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
import threading
from typing import BinaryIO

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX fallback
    fcntl = None


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class AppendResult:
    written: int
    duplicates: int


@dataclass(frozen=True)
class ReadResult:
    records: list[dict]
    malformed_lines: int


class StorageError(RuntimeError):
    pass


class JsonlStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.RLock()
        self._known_ids: set[str] = set()

    def initialize(self) -> None:
        parent_created = not self.path.parent.exists()
        try:
            self.path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
            os.chmod(self.path.parent, 0o700)
            if not self.path.exists():
                flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
                fd = os.open(self.path, flags, 0o600)
                os.close(fd)
                os.chmod(self.path, 0o600)
                if parent_created:
                    _sync_directory(self.path.parent)
            else:
                os.chmod(self.path, 0o600)
        except OSError as exc:
            raise StorageError("failed to initialize JSONL store") from exc

        result = read_jsonl(self.path)
        with self._lock:
            self._known_ids = {
                record["message_id"]
                for record in result.records
                if isinstance(record.get("message_id"), str)
            }

    def append(self, records: list[dict]) -> AppendResult:
        if not records:
            return AppendResult(written=0, duplicates=0)

        # Validate serializability before taking locks or mutating the file.
        for record in records:
            if not isinstance(record, dict):
                raise StorageError("record must be a mapping")
            if not isinstance(record.get("message_id"), str):
                raise StorageError("record message_id must be a string")
            json.dumps(record, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"))

        with self._lock:
            try:
                with open(self.path, "a+b", buffering=0) as fileobj:
                    _lock_file(fileobj)
                    try:
                        return self._append_locked(fileobj, records)
                    finally:
                        _unlock_file(fileobj)
            except StorageError:
                raise
            except OSError as exc:
                raise StorageError("failed to append JSONL records") from exc

    def _append_locked(self, fileobj: BinaryIO, records: list[dict]) -> AppendResult:
        unique: list[dict] = []
        seen_in_request: set[str] = set()
        duplicates = 0
        for record in records:
            message_id = record["message_id"]
            if message_id in self._known_ids or message_id in seen_in_request:
                duplicates += 1
                continue
            seen_in_request.add(message_id)
            unique.append(record)

        if not unique:
            return AppendResult(written=0, duplicates=duplicates)

        batch = b"".join(
            json.dumps(record, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")).encode("utf-8") + b"\n"
            for record in unique
        )

        fileobj.seek(0, os.SEEK_END)
        old_offset = fileobj.tell()
        separator = b""
        if old_offset:
            fileobj.seek(old_offset - 1)
            if fileobj.read(1) != b"\n":
                separator = b"\n"
            fileobj.seek(0, os.SEEK_END)

        try:
            if separator:
                _write_bytes(fileobj, separator)
            _write_bytes(fileobj, batch)
            _flush_file(fileobj)
            os.fsync(fileobj.fileno())
        except OSError as exc:
            try:
                os.ftruncate(fileobj.fileno(), old_offset)
                os.fsync(fileobj.fileno())
            except OSError as rollback_exc:
                LOGGER.critical(
                    "jsonl rollback failed path=%s offset=%d count=%d "
                    "write_error=%s rollback_error=%s",
                    self.path,
                    old_offset,
                    len(unique),
                    type(exc).__name__,
                    type(rollback_exc).__name__,
                )
            raise StorageError("failed to durably append JSONL records") from exc

        self._known_ids.update(record["message_id"] for record in unique)
        return AppendResult(written=len(unique), duplicates=duplicates)


def read_jsonl(path: Path) -> ReadResult:
    path = Path(path)
    if not path.exists():
        return ReadResult(records=[], malformed_lines=0)

    records: list[dict] = []
    malformed = 0
    try:
        lines = path.read_bytes().splitlines(keepends=True)
    except OSError as exc:
        raise StorageError("failed to read JSONL store") from exc

    for line_no, raw_line in enumerate(lines, start=1):
        if not raw_line.endswith(b"\n"):
            malformed += 1
            LOGGER.warning(
                "skipping malformed jsonl line path=%s line=%d error=partial",
                path,
                line_no,
            )
            continue
        stripped = raw_line.rstrip(b"\r\n")
        if not stripped:
            continue
        try:
            decoded = stripped.decode("utf-8")
            value = json.loads(decoded)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            malformed += 1
            LOGGER.warning(
                "skipping malformed jsonl line path=%s line=%d error=%s",
                path,
                line_no,
                type(exc).__name__,
            )
            continue
        if not isinstance(value, dict):
            malformed += 1
            LOGGER.warning(
                "skipping malformed jsonl line path=%s line=%d error=non_object",
                path,
                line_no,
            )
            continue
        records.append(value)

    return ReadResult(records=records, malformed_lines=malformed)


def _lock_file(fileobj: BinaryIO) -> None:
    if fcntl is not None:
        fcntl.flock(fileobj, fcntl.LOCK_EX)


def _unlock_file(fileobj: BinaryIO) -> None:
    if fcntl is not None:
        fcntl.flock(fileobj, fcntl.LOCK_UN)


def _write_bytes(fileobj: BinaryIO, data: bytes) -> int:
    return fileobj.write(data)


def _flush_file(fileobj: BinaryIO) -> None:
    fileobj.flush()


def _sync_directory(path: Path) -> None:
    if not hasattr(os, "O_DIRECTORY"):
        return
    try:
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
