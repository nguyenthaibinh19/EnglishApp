"""Read-only SQLite snapshot through the Online Backup API.

The production helper path keeps the consistent image in memory and returns
its bytes. It does not create a plaintext database file. A metadata JSON
file may record the hash and size only.

The file-based function remains for comparison with the accepted D3 path.
The helper does not call it.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import stat
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

DISK_FLOOR = 512 * 1024 * 1024
MAX_SOURCE_BYTES = 32 * 1024 * 1024
MAX_IMAGE_BYTES = 64 * 1024 * 1024


class SnapshotInterrupted(RuntimeError):
    """Raised by a test hook before the backup API runs."""


@dataclass(frozen=True)
class SnapshotResult:
    status: str
    detail: str
    sha256: str
    captured_at: str
    image: bytes = b""


def disk_decision(free_bytes: int, reserve_bytes: int = DISK_FLOOR) -> str:
    if free_bytes < reserve_bytes:
        return "disk-space"
    return "ok"


def available_bytes(path: str) -> int:
    if not hasattr(os, "statvfs"):
        raise OSError("statvfs-unavailable")
    info = os.statvfs(path)
    return int(info.f_bavail) * int(info.f_frsize)


def snapshot_memory(
    source: str,
    metadata_path: str | None = None,
    *,
    timeout: float = 30.0,
    pages: int = 32,
    pace: float = 0.0,
    max_source_bytes: int = MAX_SOURCE_BYTES,
    max_image_bytes: int = MAX_IMAGE_BYTES,
    interrupt=None,
) -> SnapshotResult:
    captured_at = datetime.now(timezone.utc).isoformat()
    if not source or _redirected(source) or not os.path.isfile(source):
        return SnapshotResult("FAILED", "source-absent", "", captured_at)
    try:
        footprint = _footprint(source)
    except OSError:
        return SnapshotResult("FAILED", "source-absent", "", captured_at)
    if footprint > max_source_bytes:
        return SnapshotResult("FAILED", "too-large", "", captured_at)
    if metadata_path and (_redirected(metadata_path) or os.path.lexists(metadata_path)):
        return SnapshotResult("FAILED", "path-exists", "", captured_at)
    if not hasattr(sqlite3.Connection, "serialize"):
        return SnapshotResult("FAILED", "serialize-unavailable", "", captured_at)
    try:
        image = _backup_memory(source, timeout, pages, pace, interrupt)
    except SnapshotInterrupted:
        return SnapshotResult("FAILED", "interrupted", "", captured_at)
    except sqlite3.OperationalError as error:
        detail = "locked" if "lock" in str(error).lower() else "sqlite-failed"
        return SnapshotResult("FAILED", detail, "", captured_at)
    except sqlite3.DatabaseError as error:
        detail = "serialize-unavailable" if "serialize" in str(error).lower() else "integrity-failed"
        return SnapshotResult("FAILED", detail, "", captured_at)
    except OSError:
        return SnapshotResult("FAILED", "disk", "", captured_at)
    if len(image) > max_image_bytes or not image.startswith(b"SQLite format 3"):
        return SnapshotResult("FAILED", "too-large" if len(image) > max_image_bytes else "integrity-failed", "", captured_at)
    digest = hashlib.sha256(image).hexdigest()
    if metadata_path:
        metadata = {"captured_at": captured_at, "sha256": digest, "size": len(image)}
        try:
            _exclusive_write(metadata_path, json.dumps(metadata, sort_keys=True).encode("utf-8") + b"\n")
        except FileExistsError:
            return SnapshotResult("FAILED", "path-exists", digest, captured_at)
        except OSError:
            return SnapshotResult("FAILED", "disk", digest, captured_at)
    return SnapshotResult("SNAPSHOTTED", "integrity-ok", digest, captured_at, image)


def _backup_memory(source: str, timeout: float, pages: int, pace: float, interrupt) -> bytes:
    uri = Path(source).resolve().as_uri() + "?mode=ro"
    source_conn = sqlite3.connect(uri, uri=True, timeout=timeout)
    memory = sqlite3.connect(":memory:")
    deadline = time.monotonic() + timeout

    def progress(status, remaining, total):
        if time.monotonic() >= deadline:
            raise sqlite3.OperationalError("database is locked")

    try:
        if interrupt is not None:
            interrupt()
        source_conn.backup(memory, pages=pages, sleep=pace, progress=progress)
        row = memory.execute("PRAGMA integrity_check").fetchone()
        if row is None or str(row[0]) != "ok":
            raise sqlite3.DatabaseError("integrity")
        image = _standalone_image(memory.serialize())
        _require_integrity(image)
    finally:
        memory.close()
        source_conn.close()
    return image


def _standalone_image(image: bytes) -> bytes:
    """Return a single-file image. A WAL header would look for a sidecar."""
    if len(image) < 20 or image[18] != 2:
        return image
    patched = bytearray(image)
    patched[18] = 1
    patched[19] = 1
    return bytes(patched)


def _require_integrity(image: bytes) -> None:
    check = sqlite3.connect(":memory:")
    try:
        check.deserialize(image)
        row = check.execute("PRAGMA integrity_check").fetchone()
        if row is None or str(row[0]) != "ok":
            raise sqlite3.DatabaseError("integrity")
    finally:
        check.close()


def _footprint(path: str) -> int:
    total = os.path.getsize(path)
    for suffix in ("-wal", "-shm"):
        extra = path + suffix
        if os.path.isfile(extra) and not os.path.islink(extra):
            total += os.path.getsize(extra)
    return total


def file_sha256(path: str) -> str:
    digest = hashlib.sha256()
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    handle = os.open(path, flags)
    try:
        while True:
            chunk = os.read(handle, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    finally:
        os.close(handle)
    return digest.hexdigest()


def _exclusive_write(path: str, payload: bytes) -> None:
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
    handle = os.open(path, flags, 0o600)
    try:
        _fchmod(handle, 0o600)
        os.write(handle, payload)
    finally:
        os.close(handle)


def _fchmod(handle: int, mode: int) -> None:
    try:
        os.fchmod(handle, mode)
    except OSError:
        pass


def _redirected(path: str) -> bool:
    if not path or not os.path.lexists(path):
        return False
    if os.path.islink(path):
        return True
    attrs = getattr(os.lstat(path), "st_file_attributes", 0)
    return bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))
