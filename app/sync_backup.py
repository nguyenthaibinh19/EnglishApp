"""Online backup and restore for ``study_sync.db`` (Phase 18B.2).

Not scheduled. Does not touch ``accounts.db``. A missing source is skipped
and is never created. A backup is published only after ``PRAGMA integrity_check``
succeeds. Restore publishes with a no-clobber hard link so an existing
destination, including one created during the copy, is left unchanged.

Retention runs only after a backup is published. If cleanup fails, the new
backup is kept and ``SyncBackupResult.retention_warning`` is set. Retention
deletes only ``study-sync-*.db`` names.
"""

from __future__ import annotations

import os
import sqlite3
import stat
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

SYNC_BACKUP_PREFIX = "study-sync"
DEFAULT_KEEP = 14
_RETENTION_WARNING = "Retention cleanup failed; the new backup was kept."


class SyncBackupError(Exception):
    """A backup or restore did not finish as a usable database."""


@dataclass(frozen=True)
class SyncBackupResult:
    """A published backup. ``retention_warning`` is set only after success."""

    path: str
    retention_warning: Optional[str] = None


def backup_database(
    source: str,
    backup_dir: str,
    *,
    keep: int = DEFAULT_KEEP,
) -> Optional[SyncBackupResult]:
    """Copy ``source`` into ``backup_dir`` using SQLite's online backup API.

    Returns ``None`` when ``source`` is not an existing file. Raises
    ``SyncBackupError`` when the copy or integrity check fails. Does not
    delete ``source``. A retention failure does not fail a finished backup.
    """
    if not source or not os.path.isfile(source):
        return None
    if isinstance(keep, bool) or not isinstance(keep, int) or keep < 1:
        raise SyncBackupError("keep must be an integer >= 1.")

    os.makedirs(backup_dir, exist_ok=True)
    _enforce_private_directory(backup_dir)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    final_path = os.path.join(backup_dir, f"{SYNC_BACKUP_PREFIX}-{stamp}.db")
    partial = final_path + ".partial"
    _copy_private(source, partial, integrity_error="Backup failed integrity check.")
    _publish_exclusive(partial, final_path)
    warning = _retain_after_publish(backup_dir, keep)
    return SyncBackupResult(final_path, warning)


def restore_database(backup_path: str, destination: str) -> str:
    """Restore ``backup_path`` into a new file at ``destination``.

    Publication fails if the destination name already exists, including a
    dangling symlink or a file created while the copy was running. The
    backup file is not deleted.
    """
    if not backup_path or not os.path.isfile(backup_path):
        raise SyncBackupError("Backup file does not exist.")
    if not destination:
        raise SyncBackupError("Refusing to restore onto an existing database.")
    if os.path.abspath(backup_path) == os.path.abspath(destination):
        raise SyncBackupError("Refusing to restore a backup onto itself.")

    parent = os.path.dirname(os.path.abspath(destination))
    if parent:
        os.makedirs(parent, exist_ok=True)
    partial = destination + ".partial"
    _copy_private(backup_path, partial, integrity_error="Restore failed integrity check.")
    _publish_exclusive(partial, destination)
    return destination


def _copy_private(source: str, partial: str, *, integrity_error: str) -> None:
    """Create ``partial`` as a private file, then fill it from ``source``."""
    created = False
    failed = True
    source_conn = None
    dest_conn = None
    try:
        _create_private_file(partial)
        created = True
        source_conn = sqlite3.connect(_sqlite_uri(source, read_only=True), uri=True)
        dest_conn = sqlite3.connect(partial)
        source_conn.backup(dest_conn)
        if not _integrity_ok(dest_conn):
            raise SyncBackupError(integrity_error)
        _assert_private_file(partial)
        failed = False
    except SyncBackupError:
        raise
    except (sqlite3.Error, OSError) as error:
        raise SyncBackupError("Backup failed.") from error
    finally:
        if dest_conn is not None:
            dest_conn.close()
        if source_conn is not None:
            source_conn.close()
        if created and failed:
            _discard(partial)


def _publish_exclusive(partial: str, destination: str) -> None:
    """Attach ``partial`` to ``destination`` without replacing an existing name.

    ``os.link`` fails if the destination name exists, including a dangling
    symlink. There is no ``os.replace`` fallback.
    """
    try:
        os.link(partial, destination)
    except OSError as error:
        _discard(partial)
        raise SyncBackupError(
            "Refusing to publish onto an existing path."
        ) from error
    _discard(partial)


def _retain_after_publish(backup_dir: str, keep: int) -> Optional[str]:
    try:
        _retain(backup_dir, keep)
    except OSError:
        return _RETENTION_WARNING
    return None


def _integrity_ok(connection: sqlite3.Connection) -> bool:
    row = connection.execute("PRAGMA integrity_check").fetchone()
    return row is not None and str(row[0]) == "ok"


def _retain(backup_dir: str, keep: int) -> None:
    names = sorted(
        name
        for name in os.listdir(backup_dir)
        if name.startswith(SYNC_BACKUP_PREFIX + "-")
        and name.endswith(".db")
        and not name.endswith(".partial")
    )
    for name in names[:-keep]:
        os.remove(os.path.join(backup_dir, name))


def _sqlite_uri(path: str, *, read_only: bool) -> str:
    """File URI with reserved characters encoded. ``mode=ro`` is query-only."""
    uri = Path(path).resolve().as_uri()
    if read_only:
        return uri + "?mode=ro"
    return uri


def _posix_permissions() -> bool:
    return os.name == "posix"


def _create_private_file(path: str) -> None:
    """Create an empty file that is owner-only before any database bytes are written."""
    flags = os.O_RDWR | os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags, 0o600)
    os.close(fd)
    _assert_private_file(path)


def _assert_private_file(path: str) -> None:
    if not _posix_permissions():
        return
    mode = stat.S_IMODE(os.stat(path).st_mode)
    if mode & 0o077:
        _discard(path)
        raise SyncBackupError("Temporary file permissions could not be enforced.")


def _enforce_private_directory(path: str) -> None:
    """On POSIX, require mode 0700. On Windows, directory modes are not enforced."""
    if not _posix_permissions():
        return
    try:
        os.chmod(path, 0o700)
    except OSError as error:
        raise SyncBackupError(
            "Backup directory permissions could not be enforced."
        ) from error
    mode = stat.S_IMODE(os.stat(path).st_mode)
    if mode & 0o077:
        raise SyncBackupError("Backup directory permissions could not be enforced.")


def _discard(path: str) -> None:
    try:
        if path and os.path.lexists(path):
            os.remove(path)
    except OSError:
        pass
