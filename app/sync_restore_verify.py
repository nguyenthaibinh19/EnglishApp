"""Prove the newest study-sync backup can be restored and opened read-only.

Phase 18B.5 source only. Not scheduled. Does not create a missing live
database, does not migrate schema, and does not write the backup or the
live file. A missing backup is a skip only when the live path is
absent. A directory, symlink, or other non-file is a failure. That skip
is not proof the database never existed. The verification root is
resolved before any directory is created or its mode is changed.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import stat
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import sync_backup

STATUS_VERIFIED = "VERIFIED"
STATUS_SKIPPED = "SKIPPED"
STATUS_FAILED = "FAILED"

SUPPORTED_SCHEMA_VERSION = 2
_BACKUP_PREFIX = "study-sync-"
_RESTORED_NAME = "restored.db"
_PRODUCTION_ROOT = os.path.normcase(os.path.abspath("/opt/language-guard"))
_PRODUCTION_LIVE = os.path.normcase(
    os.path.abspath("/opt/language-guard/study_sync.db")
)

_REQUIRED_COLUMNS = {
    "sync_meta": frozenset({"key", "value"}),
    "vocabulary_entities": frozenset(
        {
            "user_id",
            "language_code",
            "vocab_id",
            "revision",
            "deleted",
            "payload_json",
            "change_cursor",
            "operation_id",
            "updated_at",
            "expected_revision",
        }
    ),
    "vocabulary_changes": frozenset(
        {
            "change_id",
            "user_id",
            "language_code",
            "vocab_id",
            "revision",
            "deleted",
            "payload_json",
            "operation_id",
            "created_at",
            "expected_revision",
        }
    ),
}


class VerifyError(Exception):
    """Verification did not prove the newest backup is recoverable."""


@dataclass(frozen=True)
class VerifyResult:
    """Status only. Paths and database contents stay out of this object."""

    status: str


def verify_latest_backup(
    backup_dir: str,
    verify_root: str,
    live_db: str,
) -> VerifyResult:
    """Restore the newest named backup into a new directory and check it.

    Returns ``SKIPPED`` only when no validly named backup exists and the
    live path is absent. A directory, symlink, or other non-file at that
    path is ``FAILED``. Returns ``FAILED`` when the newest valid backup
    cannot be proved recoverable. Does not try an older backup.
    """
    holder = {"run": None}
    status = STATUS_FAILED
    try:
        status = _verify(backup_dir, verify_root, live_db, holder)
    except Exception:
        status = STATUS_FAILED
    if holder["run"]:
        try:
            _cleanup_run(holder["run"], verify_root)
        except Exception:
            status = STATUS_FAILED
    return VerifyResult(status)


def _verify(
    backup_dir: str,
    verify_root: str,
    live_db: str,
    holder: dict,
) -> str:
    if not backup_dir or not verify_root or not live_db:
        raise VerifyError("missing configuration")
    _assert_writable_root(verify_root, backup_dir, live_db)

    newest = _newest_candidate(backup_dir)
    if newest is None:
        return _missing_backup_status(live_db)

    _reject_symlink_components(newest)
    if not os.path.isfile(newest):
        raise VerifyError("backup is not a regular file")

    _prepare_verify_root(verify_root)
    run_dir = _allocate_run_dir(verify_root)
    _assert_cleanup_target(run_dir, verify_root)
    holder["run"] = run_dir
    _enforce_private_directory(run_dir)
    destination = os.path.join(run_dir, _RESTORED_NAME)
    _assert_safe_destination(destination, newest, live_db, verify_root, backup_dir)
    sync_backup.restore_database(newest, destination)
    _assert_private_file(destination)
    _check_restored(destination)
    return STATUS_VERIFIED


def _newest_candidate(backup_dir: str) -> Optional[str]:
    _reject_symlink_components(backup_dir)
    if not os.path.exists(backup_dir):
        return None
    if not os.path.isdir(backup_dir):
        raise VerifyError("backup directory is not a directory")
    names = []
    with os.scandir(backup_dir) as entries:
        for entry in entries:
            if _valid_backup_name(entry.name):
                names.append(entry.name)
    if not names:
        return None
    names.sort()
    return os.path.join(backup_dir, names[-1])


def _valid_backup_name(name: str) -> bool:
    prefix = _BACKUP_PREFIX
    suffix = ".db"
    if not name.startswith(prefix) or not name.endswith(suffix):
        return False
    stamp = name[len(prefix) : -len(suffix)]
    parts = stamp.split("-")
    if len(parts) != 3:
        return False
    day, clock, fraction = parts
    if not (
        _ascii_digits(day, 8)
        and _ascii_digits(clock, 6)
        and _ascii_digits(fraction, 6)
    ):
        return False
    try:
        datetime.strptime(day + clock, "%Y%m%d%H%M%S")
    except ValueError:
        return False
    hour = int(clock[0:2])
    minute = int(clock[2:4])
    second = int(clock[4:6])
    return hour <= 23 and minute <= 59 and second <= 59


def _ascii_digits(value: str, length: int) -> bool:
    return len(value) == length and all("0" <= char <= "9" for char in value)


def _missing_backup_status(live_db: str) -> str:
    """Classify a missing backup without opening or creating the live path."""
    if os.path.islink(live_db) or _symlink_component(live_db):
        raise VerifyError("invalid live path")
    if not os.path.lexists(live_db):
        return STATUS_SKIPPED
    if os.path.isfile(live_db):
        raise VerifyError("live database has no backup")
    raise VerifyError("invalid live path")


def _prepare_verify_root(verify_root: str) -> None:
    os.makedirs(verify_root, exist_ok=True)
    _enforce_private_directory(verify_root)


def _allocate_run_dir(verify_root: str) -> str:
    path = os.path.join(verify_root, "run-" + uuid.uuid4().hex)
    os.makedirs(path, exist_ok=False)
    return path


def _assert_safe_destination(
    destination: str,
    backup_path: str,
    live_db: str,
    verify_root: str,
    backup_dir: str,
) -> None:
    if os.path.lexists(destination):
        raise VerifyError("destination already exists")
    if os.path.basename(destination) == "accounts.db":
        raise VerifyError("refusing accounts database")
    dest_real = _canonical(destination)
    _reject_protected(destination)
    if dest_real == _canonical(backup_path):
        raise VerifyError("refusing to restore onto the backup")
    if dest_real == _canonical(live_db):
        raise VerifyError("refusing to restore onto the live database")
    if not _is_inside(dest_real, _canonical(verify_root)):
        raise VerifyError("destination escaped the verification root")
    if _is_inside(dest_real, _canonical(backup_dir)) or dest_real == _canonical(backup_dir):
        raise VerifyError("destination overlaps the backup directory")
    run_parent = os.path.dirname(destination)
    if _is_inside(_canonical(backup_path), _canonical(run_parent)):
        raise VerifyError("backup is inside the run directory")


def _check_restored(path: str) -> None:
    connection = sqlite3.connect(sync_backup._sqlite_uri(path, read_only=True), uri=True)
    try:
        if not _integrity_ok(connection):
            raise VerifyError("integrity check failed")
        version = _schema_version(connection)
        if version != SUPPORTED_SCHEMA_VERSION:
            raise VerifyError("unsupported schema")
        for table, required in _REQUIRED_COLUMNS.items():
            found = _column_names(connection, table)
            if not required.issubset(found):
                raise VerifyError("required schema is missing")
    finally:
        connection.close()


def _integrity_ok(connection: sqlite3.Connection) -> bool:
    row = connection.execute("PRAGMA integrity_check").fetchone()
    return row is not None and str(row[0]) == "ok"


def _schema_version(connection: sqlite3.Connection) -> int:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'sync_meta'"
    ).fetchone()
    if row is None:
        raise VerifyError("required schema is missing")
    found = connection.execute(
        "SELECT value FROM sync_meta WHERE key = 'schema_version'"
    ).fetchone()
    if found is None:
        raise VerifyError("required schema is missing")
    raw = found[0]
    if isinstance(raw, bool) or not isinstance(raw, (int, str)):
        raise VerifyError("unsupported schema")
    try:
        return int(raw)
    except (TypeError, ValueError) as error:
        raise VerifyError("unsupported schema") from error


def _column_names(connection: sqlite3.Connection, table: str) -> set:
    rows = connection.execute("PRAGMA table_info(%s)" % table).fetchall()
    if not rows:
        raise VerifyError("required schema is missing")
    return {str(row[1]) for row in rows}


def _cleanup_run(run_dir: str, verify_root: str) -> None:
    _assert_cleanup_target(run_dir, verify_root)
    shutil.rmtree(run_dir)


def _assert_cleanup_target(run_dir: str, verify_root: str) -> None:
    if not run_dir or not verify_root:
        raise VerifyError("cleanup path missing")
    _reject_symlink_components(verify_root)
    _reject_symlink_components(run_dir)
    _reject_protected(verify_root)
    _reject_protected(run_dir)
    if not os.path.isdir(run_dir):
        raise VerifyError("cleanup path missing")
    if not _is_inside(_canonical(run_dir), _canonical(verify_root)):
        raise VerifyError("cleanup escaped the verification root")
    if os.path.basename(_canonical(run_dir)) == "accounts.db":
        raise VerifyError("refusing accounts database")


def _assert_writable_root(verify_root: str, backup_dir: str, live_db: str) -> None:
    """Reject a verification root before any mkdir, chmod, restore, or delete."""
    _reject_symlink_components(verify_root)
    _reject_protected(verify_root)
    if os.path.basename(_canonical(verify_root)) == "accounts.db":
        raise VerifyError("refusing accounts database")
    _reject_overlap(backup_dir, verify_root, live_db)


def _reject_overlap(backup_dir: str, verify_root: str, live_db: str) -> None:
    root_real = _canonical(verify_root)
    backup_real = _canonical(backup_dir)
    live_real = _canonical(live_db)
    if root_real == backup_real or _is_inside(root_real, backup_real):
        raise VerifyError("verification root overlaps backups")
    if _is_inside(backup_real, root_real):
        raise VerifyError("verification root overlaps backups")
    if live_real == root_real or _is_inside(live_real, root_real):
        raise VerifyError("verification root overlaps the live database")


def _reject_protected(path: str) -> None:
    real = _canonical(path)
    root = _canonical(_PRODUCTION_ROOT)
    live = _canonical(_PRODUCTION_LIVE)
    if real == root or real == live or _is_inside(real, root):
        raise VerifyError("refusing a protected path")
    lexical = os.path.normcase(os.path.abspath(path))
    lexical_root = os.path.normcase(os.path.abspath(_PRODUCTION_ROOT))
    lexical_live = os.path.normcase(os.path.abspath(_PRODUCTION_LIVE))
    if (
        lexical == lexical_root
        or lexical == lexical_live
        or _is_inside(lexical, lexical_root)
    ):
        raise VerifyError("refusing a protected path")


def _reject_symlink_components(path: str) -> None:
    if _symlink_component(path):
        raise VerifyError("refusing a symlink")


def _symlink_component(path: str) -> bool:
    current = os.path.abspath(path)
    chain = []
    while True:
        parent = os.path.dirname(current)
        if parent == current:
            break
        chain.append(current)
        current = parent
    for candidate in reversed(chain):
        if os.path.islink(candidate):
            return True
        if not os.path.lexists(candidate):
            return False
    return False


def _canonical(path: str) -> str:
    return os.path.normcase(os.path.realpath(path))


def _is_inside(path: str, parent: str) -> bool:
    try:
        return os.path.commonpath([path, parent]) == parent and path != parent
    except ValueError:
        return False


def _posix_permissions() -> bool:
    return os.name == "posix"


def _enforce_private_directory(path: str) -> None:
    if not _posix_permissions():
        return
    try:
        os.chmod(path, 0o700)
    except OSError as error:
        raise VerifyError("directory permissions could not be enforced") from error
    mode = stat.S_IMODE(os.stat(path).st_mode)
    if mode & 0o077:
        raise VerifyError("directory permissions could not be enforced")


def _assert_private_file(path: str) -> None:
    if not _posix_permissions():
        return
    mode = stat.S_IMODE(os.stat(path).st_mode)
    if mode & 0o077:
        raise VerifyError("restored file permissions could not be enforced")
