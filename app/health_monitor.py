"""Read-only health collector for Phase 18B.8.

Repository code only. It does not enable Sync, create ``study_sync.db``, or
open the live accounts database. ``PROVIDER_ACCEPTED`` is recorded by the
notify module and is not proof a person received the message.

A witness is written only after a check observes a regular sync database.
Polling cannot see a file that is created and removed between checks.
"""

from __future__ import annotations

import json
import os
import secrets
import sqlite3
import stat
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional
from zoneinfo import ZoneInfo

import health_notify

VERIFIED = "VERIFIED"
SKIPPED = "SKIPPED"
NOT_INSTALLED = "NOT INSTALLED"
UNKNOWN = "UNKNOWN"
WARNING = "WARNING"
FAILED = "FAILED"
OVERALL_OK = "OK"

HEALTH_MESSAGE = "Language Guard account server is running."
AMSTERDAM = ZoneInfo("Europe/Amsterdam")
CHANNELS = ("telegram", "email")
ACCOUNTS_WARNING = timedelta(hours=26)
ACCOUNTS_FAILED = timedelta(hours=48)
# The verifier runs at 08:00 Europe/Amsterdam. A record taken at or after that
# run stays current until 10:00 Europe/Amsterdam on the next civil day: two
# wall-clock hours after the next scheduled run. A fixed 26 UTC hours would
# leave only one hour of grace across the October fall-back. A stopped timer
# does not stay VERIFIED after the deadline.
VERIFY_FUTURE_SKEW = timedelta(minutes=5)
DISK_WARNING = 0.80
DISK_FAILED = 0.95
LOCK_TIMEOUT = 5.0
_PROCESS_GATE = threading.Lock()
_THREAD_LOCKS = {}
_THREAD_LOCKS_GUARD = threading.Lock()

_SEVERITY = {
    VERIFIED: 0,
    SKIPPED: 1,
    WARNING: 2,
    NOT_INSTALLED: 3,
    UNKNOWN: 4,
    FAILED: 5,
}
_MANDATORY = (
    "account_service",
    "public_health",
    "accounts_backup_age",
    "accounts_integrity",
    "disk",
    "sync_flag",
)


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str = ""


@dataclass
class HealthConfig:
    """Paths and thresholds. Tests use temporary directories."""

    state_path: str
    witness_path: str
    accounts_backup_dir: str
    accounts_live_db: str
    sync_live_db: str
    sync_backup_dir: str
    systemd_dir: str
    verify_result_path: str = ""
    rpo_hours: Optional[float] = None
    now: Optional[datetime] = None


@dataclass
class HealthResult:
    overall: str
    text: str
    checks: list[Check]
    deliveries: dict
    heartbeat: str
    logs: list[str] = field(default_factory=list)


def amsterdam_date(moment: datetime) -> str:
    """Civil date in Europe/Amsterdam. 09:00 is not an ambiguous DST time."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(AMSTERDAM).date().isoformat()


def file_identity(path: str) -> str:
    info = os.stat(path)
    return f"{info.st_dev}:{info.st_ino}:{info.st_size}:{info.st_mtime_ns}"


def snapshot_integrity(path: str, live_db: str) -> str:
    """Open one completed snapshot read-only. Refuse the live accounts file.

    Symlinks are not followed. A hard link to the live database is the same
    file identity and is refused before SQLite reads it.
    """
    _assert_no_symlink(path)
    _assert_no_symlink(live_db)
    if os.path.abspath(path) == os.path.abspath(live_db):
        raise RuntimeError("refusing to open the live accounts database")
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise RuntimeError("refusing to open the snapshot") from error
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise RuntimeError("refusing to open the snapshot")
        live_identity = _live_file_identity(live_db)
        if live_identity is not None and (info.st_dev, info.st_ino) == live_identity:
            raise RuntimeError("refusing to open the live accounts database")
        connection = _connect_snapshot(descriptor, path)
        try:
            connection.execute("PRAGMA query_only=ON")
            row = connection.execute("PRAGMA integrity_check").fetchone()
        finally:
            connection.close()
    finally:
        os.close(descriptor)
    if row and row[0] == "ok":
        return VERIFIED
    return FAILED


def note_sync_backup_event(kind: str, environ=None) -> None:
    """Record an ADR-021 outcome. Failures here must not change backup exits.

    ``absent`` does not erase an earlier incident. ``published`` does not erase
    an incident until both Telegram and Email have returned
    ``PROVIDER_ACCEPTED`` for it. Displaying the incident is not delivery.
    This function does not record that an alert was delivered.
    """
    env = os.environ if environ is None else environ
    state_path = (env.get("HEALTH_STATE_PATH") or "").strip()
    if not state_path or kind == "absent":
        return
    lock_path = state_path + ".lock"
    with _lock(lock_path):
        state = _load(state_path)
        current = state.get("sync_backup_notice")
        if kind == "published" and current in {"failed", "retention_warning"}:
            state["sync_backup_clear_after_report"] = True
        elif kind in {"failed", "retention_warning", "published"}:
            state["sync_backup_notice"] = kind
            if kind in {"failed", "retention_warning"}:
                state.pop("sync_backup_clear_after_report", None)
                state["sync_backup_alert_accepted"] = {}
                state["sync_backup_incident"] = {
                    "id": secrets.token_hex(8),
                    "kind": kind,
                }
        _save(state_path, state)


def note_sync_verify_result(
    path: str,
    status: str,
    *,
    backup_name: str = "",
    backup_bytes: int = 0,
    backup_mtime_ns: int = 0,
    backup_sha256: str = "",
    checked_at: str = "",
) -> None:
    """Atomically record one real verification. Never records ``UNKNOWN``."""
    if status not in {VERIFIED, SKIPPED, FAILED}:
        raise ValueError("verification status")
    if status == VERIFIED and (not backup_name or not _sha256_text(backup_sha256)):
        raise ValueError("verified result needs a backup identity")
    if status == SKIPPED and (backup_name or backup_sha256):
        raise ValueError("skipped result has no backup")
    if backup_sha256 and not _sha256_text(backup_sha256):
        raise ValueError("backup identity")
    stamp = checked_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if _parse_checked_at(stamp) is None:
        raise ValueError("checked_at")
    _assert_no_symlink(path)
    payload = {
        "status": status,
        "checked_at": stamp,
        "backup_name": backup_name,
        "backup_bytes": int(backup_bytes),
        "backup_mtime_ns": int(backup_mtime_ns),
        "backup_sha256": backup_sha256,
    }
    lock_path = path + ".lock"
    with _lock(lock_path):
        existing = _read_verify_result_unlocked(path)
        if isinstance(existing, dict) and existing.get("status") == FAILED and status == SKIPPED:
            return
        _atomic_write(
            path,
            json.dumps(payload, sort_keys=True).encode("utf-8"),
            mode=0o640,
        )


def run_health(
    mode: str,
    config: HealthConfig,
    probes: dict,
    senders: dict,
    *,
    heartbeat: Optional[Callable[[], bool]] = None,
    secrets: Optional[list[str]] = None,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
    transport: Optional[Callable] = None,
) -> HealthResult:
    """Run ``check`` or ``report``. Concurrent callers share the state lock."""
    if mode not in {"check", "report"}:
        raise ValueError("mode must be check or report")
    moment = config.now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    secret_values = list(secrets or [])
    lock_path = config.state_path + ".lock"
    # One process serializes its own collector runs. Slow probes run outside
    # the state lock. The lock is held only around the merge and the later
    # delivery record, never around provider calls. Two processes can both
    # send. That overlap, and a crash after the provider accepts but before
    # the state write, is at-least-once delivery.
    with _PROCESS_GATE:
        with _lock(lock_path):
            cached = _load(config.state_path)
            integrity = cached.get("integrity") if isinstance(cached.get("integrity"), dict) else {}
        view = {"integrity": dict(integrity)}
        checks = _collect(config, probes, view, moment)
        with _lock(lock_path):
            state = _load(config.state_path)
            if isinstance(view.get("integrity"), dict):
                state["integrity"] = view["integrity"]
            checks = _merge_backup_check(config, checks, state, moment)
            fingerprint = [[item.name, item.status] for item in checks]
            changed = fingerprint != state.get("fingerprint")
            recovery = _recovered(state.get("fingerprint") or [], fingerprint)
            civil = amsterdam_date(moment)
            overall = _overall(checks)
            text = _render(overall, checks, recovery)
            incident = state.get("sync_backup_incident") if isinstance(state.get("sync_backup_incident"), dict) else {}
            incident_id = incident.get("id")
            request_heartbeat = mode == "report" and state.get("heartbeat_date") != civil
            targets = _targets(mode, state, civil, changed, recovery)
            envelope = _envelope(mode, checks, recovery, state, civil)
            _save(config.state_path, state)
        deliveries, logs, handed_heartbeat = _send(
            targets,
            text,
            envelope,
            senders,
            secret_values,
            sleep,
            monotonic,
            transport,
            request_heartbeat,
        )
        with _lock(lock_path):
            state = _load(config.state_path)
            _record_deliveries(state, mode, civil, fingerprint, deliveries)
            _settle_backup_incident(state, checks, deliveries, incident_id if isinstance(incident_id, str) else "")
            state["fingerprint"] = fingerprint
            heartbeat_result = "not-sent"
            if handed_heartbeat is not None:
                heartbeat_result = handed_heartbeat
                if heartbeat_result == "ping-accepted" and mode == "report":
                    state["heartbeat_date"] = civil
            elif mode == "report" and _any_accepted(deliveries):
                if state.get("heartbeat_date") != civil:
                    if heartbeat is None:
                        heartbeat_result = health_notify.NOT_SENT
                    else:
                        try:
                            heartbeat_result = "ping-accepted" if heartbeat() else "ping-rejected"
                        except Exception:
                            heartbeat_result = "ping-rejected"
                    if heartbeat_result == "ping-accepted":
                        state["heartbeat_date"] = civil
            elif mode == "report":
                heartbeat_result = "withheld"
            _save(config.state_path, state)
            _maybe_witness(config)
    return HealthResult(overall, text, checks, deliveries, heartbeat_result, logs)


def _merge_backup_check(
    config: HealthConfig, checks: list[Check], state: dict, moment: datetime
) -> list[Check]:
    """Replace the backup check with one read from the latest state.

    The probe copy can be older than an incident recorded while hashing or
    integrity checking. The merge keeps that incident, its id, and channel
    acceptance, and only refreshes the displayed backup check.
    """
    fresh = _sync_backup(config, state, moment)
    merged = []
    placed = False
    for item in checks:
        if item.name == "sync_backup":
            continue
        if item.name == "sync_verify" and not placed:
            merged.append(fresh)
            placed = True
        merged.append(item)
    if not placed:
        merged.append(fresh)
    return merged


def _collect(config: HealthConfig, probes: dict, state: dict, moment: datetime) -> list[Check]:
    checks = [
        _service(probes),
        _public(probes),
        *_accounts(config, state, moment),
        _disk(probes),
        _flag(probes),
        _sync_database(config),
        _sync_backup(config, state, moment),
        _sync_verify(config),
    ]
    return checks


def _service(probes: dict) -> Check:
    value = probes.get("service")
    if value is None:
        return Check("account_service", UNKNOWN, "unreadable")
    if value == "active":
        return Check("account_service", VERIFIED, "active")
    return Check("account_service", FAILED, str(value))


def _public(probes: dict) -> Check:
    value = probes.get("public_health")
    if value is None:
        return Check("public_health", UNKNOWN, "unreadable")
    if value == HEALTH_MESSAGE:
        return Check("public_health", VERIFIED, "health")
    return Check("public_health", FAILED, "unexpected")


def _accounts(config: HealthConfig, state: dict, moment: datetime) -> list[Check]:
    directory = config.accounts_backup_dir
    if not os.path.isdir(directory):
        return [
            Check("accounts_backup_age", FAILED, "missing"),
            Check("accounts_integrity", FAILED, "missing"),
        ]
    names = [
        name
        for name in os.listdir(directory)
        if name.startswith("accounts-") and name.endswith(".db")
    ]
    if not names:
        return [
            Check("accounts_backup_age", FAILED, "missing"),
            Check("accounts_integrity", FAILED, "missing"),
        ]
    newest = max(names, key=lambda name: os.stat(os.path.join(directory, name)).st_mtime_ns)
    path = os.path.join(directory, newest)
    if os.path.abspath(path) == os.path.abspath(config.accounts_live_db):
        return [
            Check("accounts_backup_age", FAILED, "live-path"),
            Check("accounts_integrity", FAILED, "live-path"),
        ]
    modified = datetime.fromtimestamp(os.stat(path).st_mtime, timezone.utc)
    age = moment.astimezone(timezone.utc) - modified
    if age >= ACCOUNTS_FAILED:
        age_status = FAILED
    elif age >= ACCOUNTS_WARNING:
        age_status = WARNING
    else:
        age_status = VERIFIED
    identity = file_identity(path)
    cached = state.get("integrity") or {}
    if cached.get("identity") == identity and cached.get("status") in {VERIFIED, FAILED}:
        integrity = cached["status"]
    else:
        try:
            integrity = snapshot_integrity(path, config.accounts_live_db)
        except Exception:
            integrity = FAILED
        state["integrity"] = {"identity": identity, "status": integrity, "name": newest}
    hours = int(age.total_seconds() // 3600)
    return [
        Check("accounts_backup_age", age_status, f"utc_age_hours={hours}"),
        Check("accounts_integrity", integrity, newest),
    ]


def _disk(probes: dict) -> Check:
    usage = probes.get("disk")
    if not usage or not usage[0]:
        return Check("disk", UNKNOWN, "unreadable")
    total, used = usage
    fraction = used / total
    if fraction >= DISK_FAILED:
        status = FAILED
    elif fraction >= DISK_WARNING:
        status = WARNING
    else:
        status = VERIFIED
    return Check("disk", status, f"used={int(fraction * 100)}%")


def _flag(probes: dict) -> Check:
    readings = probes.get("flags")
    if readings is None:
        return Check("sync_flag", UNKNOWN, "unreadable")
    for reading in readings:
        if not reading.get("readable", False):
            return Check("sync_flag", UNKNOWN, "unreadable")
        if str(reading.get("value") or "").strip() == "1":
            return Check("sync_flag", FAILED, "on")
    return Check("sync_flag", VERIFIED, "off")


def _sync_database(config: HealthConfig) -> Check:
    path = config.sync_live_db
    if os.path.islink(path):
        return Check("sync_database", FAILED, "symlink")
    if os.path.isfile(path):
        return Check("sync_database", VERIFIED, "present")
    if os.path.lexists(path):
        return Check("sync_database", FAILED, "not-a-file")
    if os.path.isfile(config.witness_path):
        return Check("sync_database", FAILED, "disappeared")
    return Check("sync_database", SKIPPED, "absent")


def _sync_backup(config: HealthConfig, state: dict, moment: datetime) -> Check:
    witnessed = os.path.isfile(config.witness_path)
    live = os.path.isfile(config.sync_live_db) and not os.path.islink(config.sync_live_db)
    # A recorded incident stays in the notification after the live file changes.
    # Disappearance of a witnessed database remains its own check when no
    # incident is waiting.
    notice = state.get("sync_backup_notice")
    if notice == "failed":
        return Check("sync_backup", FAILED, "backup-failed")
    if notice == "retention_warning":
        return Check("sync_backup", WARNING, "retention")
    if witnessed and not live:
        return Check("sync_backup", FAILED, "disappeared")
    if not _unit_installed(config.systemd_dir, "language-guard-sync-backup.timer"):
        return Check("sync_backup", NOT_INSTALLED, "timer")
    if not live and not witnessed:
        return Check("sync_backup", SKIPPED, "no study_sync.db yet")
    newest = _newest_sync_backup(config.sync_backup_dir)
    if newest is None:
        return Check("sync_backup", FAILED, "missing-backup")
    if config.rpo_hours is None:
        return Check("sync_backup", VERIFIED, "rpo-inactive")
    age = moment.astimezone(timezone.utc) - datetime.fromtimestamp(
        os.stat(newest).st_mtime, timezone.utc
    )
    if age > timedelta(hours=config.rpo_hours):
        return Check("sync_backup", FAILED, "stale")
    return Check("sync_backup", VERIFIED, "within-rpo")


def _sync_verify(config: HealthConfig) -> Check:
    witnessed = os.path.isfile(config.witness_path)
    live = os.path.isfile(config.sync_live_db) and not os.path.islink(config.sync_live_db)
    if witnessed and not live:
        return Check("sync_verify", FAILED, "disappeared")
    record = _read_verify_result(config.verify_result_path)
    if record is not None and record.get("status") == "unreadable":
        return Check("sync_verify", UNKNOWN, "unreadable")
    if record is None:
        if not _unit_installed(config.systemd_dir, "language-guard-sync-verify.timer"):
            return Check("sync_verify", NOT_INSTALLED, "timer")
        return Check("sync_verify", UNKNOWN, "never-run")
    status = record.get("status")
    if status == FAILED:
        return Check("sync_verify", FAILED, "verify-failed")
    if status == VERIFIED:
        if _verify_identity_current(config, record):
            detail = f"{record.get('checked_at') or ''} {record.get('backup_name') or ''}".strip()
            return Check("sync_verify", VERIFIED, detail)
        return Check("sync_verify", UNKNOWN, "stale")
    if status == SKIPPED and _skip_still_current(config, record):
        return Check("sync_verify", SKIPPED, "recorded-skip")
    if status == SKIPPED:
        return Check("sync_verify", UNKNOWN, "stale")
    if not _unit_installed(config.systemd_dir, "language-guard-sync-verify.timer"):
        return Check("sync_verify", NOT_INSTALLED, "timer")
    return Check("sync_verify", UNKNOWN, "never-run")


def _read_verify_result_unlocked(path: str) -> Optional[dict]:
    if not path or os.path.islink(path) or not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {"status": "unreadable"}
    return _published_result(payload)


def _read_verify_result(path: str) -> Optional[dict]:
    """Read a published result without creating or writing the verifier lock.

    The verifier keeps ``result.json.lock`` for its own replace. The collector
    only opens the published file read-only. A symlink, a non-regular file,
    or unreadable or malformed content is ``unreadable``. A missing file is
    ``None``.
    """
    if not path:
        return None
    try:
        _assert_no_symlink(path)
    except OSError:
        return {"status": "unreadable"}
    if os.path.islink(path):
        return {"status": "unreadable"}
    if os.path.lexists(path) and not os.path.isfile(path):
        return {"status": "unreadable"}
    if not os.path.isfile(path):
        return None
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError:
        return {"status": "unreadable"}
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            return {"status": "unreadable"}
        chunks = []
        while True:
            piece = os.read(descriptor, 65536)
            if not piece:
                break
            if sum(len(item) for item in chunks) + len(piece) > 65536:
                return {"status": "unreadable"}
            chunks.append(piece)
        payload = json.loads(b"".join(chunks).decode("utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return {"status": "unreadable"}
    finally:
        os.close(descriptor)
    return _published_result(payload)


def _parse_checked_at(value: str) -> Optional[datetime]:
    if not isinstance(value, str) or len(value) != 20 or not value.endswith("Z"):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _published_result(payload) -> dict:
    """Return a schema-valid result, or ``unreadable`` for malformed content."""
    if not isinstance(payload, dict) or payload.get("status") not in {VERIFIED, SKIPPED, FAILED}:
        return {"status": "unreadable"}
    if _parse_checked_at(payload.get("checked_at")) is None:
        return {"status": "unreadable"}
    name = payload.get("backup_name")
    digest = payload.get("backup_sha256")
    size = payload.get("backup_bytes")
    modified = payload.get("backup_mtime_ns")
    if not isinstance(name, str) or not isinstance(digest, str):
        return {"status": "unreadable"}
    if name != os.path.basename(name) or name in {".", ".."}:
        return {"status": "unreadable"}
    if type(size) is not int or type(modified) is not int or size < 0 or modified < 0:
        return {"status": "unreadable"}
    status = payload.get("status")
    if status == VERIFIED:
        if not name or not _sha256_text(digest):
            return {"status": "unreadable"}
    elif status == SKIPPED:
        if name or digest or size or modified:
            return {"status": "unreadable"}
    elif digest and not _sha256_text(digest):
        return {"status": "unreadable"}
    return payload


def _verification_deadline(stamp: datetime) -> datetime:
    """10:00 Europe/Amsterdam after the next scheduled 08:00 run."""
    local = stamp.astimezone(AMSTERDAM)
    civil = local.date()
    scheduled = datetime(civil.year, civil.month, civil.day, 8, 0, tzinfo=AMSTERDAM)
    if local >= scheduled:
        following = civil + timedelta(days=1)
        scheduled = datetime(following.year, following.month, following.day, 8, 0, tzinfo=AMSTERDAM)
    return scheduled + timedelta(hours=2)


def _checked_at_current(config: HealthConfig, record: dict) -> bool:
    """True only for a timestamp inside the verifier's freshness window."""
    stamp = _parse_checked_at(record.get("checked_at"))
    if stamp is None:
        return False
    moment = config.now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    moment = moment.astimezone(timezone.utc)
    if stamp > moment + VERIFY_FUTURE_SKEW:
        return False
    return moment <= _verification_deadline(stamp)


def _verify_identity_current(config: HealthConfig, record: dict) -> bool:
    if not _checked_at_current(config, record):
        return False
    try:
        import sync_restore_verify

        newest = sync_restore_verify._newest_candidate(config.sync_backup_dir)
    except Exception:
        return False
    if not newest or not os.path.isfile(newest):
        return False
    size = record.get("backup_bytes")
    modified = record.get("backup_mtime_ns")
    digest = record.get("backup_sha256")
    if type(size) is not int or type(modified) is not int or not _sha256_text(str(digest or "")):
        return False
    info = os.stat(newest)
    return (
        record.get("backup_name") == os.path.basename(newest)
        and size == int(info.st_size)
        and modified == int(info.st_mtime_ns)
        and digest == sync_restore_verify.file_sha256(newest)
    )


def _skip_still_current(config: HealthConfig, record: dict) -> bool:
    if not _checked_at_current(config, record):
        return False
    if record.get("backup_name"):
        return False
    if os.path.isfile(config.sync_live_db) or os.path.isfile(config.witness_path):
        return False
    try:
        import sync_restore_verify

        return sync_restore_verify._newest_candidate(config.sync_backup_dir) is None
    except Exception:
        return False


def _unit_installed(directory: str, name: str) -> bool:
    return os.path.isfile(os.path.join(directory, name))


def _newest_sync_backup(directory: str) -> Optional[str]:
    if not os.path.isdir(directory):
        return None
    names = [
        name
        for name in os.listdir(directory)
        if name.startswith("study-sync-") and name.endswith(".db")
    ]
    if not names:
        return None
    newest = max(names, key=lambda name: os.stat(os.path.join(directory, name)).st_mtime_ns)
    return os.path.join(directory, newest)


def _overall(checks: list[Check]) -> str:
    by_name = {item.name: item for item in checks}
    for name in _MANDATORY:
        item = by_name.get(name)
        if item is None or item.status != VERIFIED:
            return _worst(checks)
    for item in checks:
        if item.status in {FAILED, WARNING, UNKNOWN, NOT_INSTALLED}:
            return _worst(checks)
    return OVERALL_OK


def _worst(checks: list[Check]) -> str:
    return max((item.status for item in checks), key=lambda status: _SEVERITY[status])


def _render(overall: str, checks: list[Check], recovery: bool) -> str:
    sync = next(item for item in checks if item.name == "sync_backup")
    if overall == OVERALL_OK and sync.status == SKIPPED:
        first = "OK — sync backup SKIPPED, no study_sync.db yet"
    else:
        first = f"{overall} — sync backup {sync.status}"
        if sync.detail:
            first += f", {sync.detail}"
    lines = [first]
    if recovery:
        lines.append("recovery: a previous warning or failure cleared")
    for item in checks:
        lines.append(f"{item.name} {item.status} {item.detail}".rstrip())
    return "\n".join(lines)


def _recovered(previous: list, current: list) -> bool:
    old = {name: status for name, status in previous}
    new = {name: status for name, status in current}
    for name, status in new.items():
        before = old.get(name)
        if before in {FAILED, WARNING} and status in {VERIFIED, SKIPPED}:
            return True
    return False


def _settle_backup_incident(state: dict, checks: list[Check], deliveries: dict, notified_id: str) -> None:
    """Record acceptance only for the incident id included in this notification.

    A newer incident created while the send was in flight keeps its own empty
    acceptance map. Observation is not delivery.
    """
    if not notified_id:
        return
    current = state.get("sync_backup_incident")
    if not isinstance(current, dict) or current.get("id") != notified_id:
        return
    expected = {"failed": "backup-failed", "retention_warning": "retention"}.get(current.get("kind"))
    shown = next((item for item in checks if item.name == "sync_backup"), None)
    if expected is None or shown is None or shown.detail != expected:
        return
    accepted = state.get("sync_backup_alert_accepted")
    if not isinstance(accepted, dict):
        accepted = {}
        state["sync_backup_alert_accepted"] = accepted
    for channel, result in deliveries.items():
        if result == health_notify.PROVIDER_ACCEPTED:
            accepted[channel] = True
    if state.get("sync_backup_clear_after_report") and accepted.get("telegram") is True and accepted.get("email") is True:
        state["sync_backup_notice"] = "published"
        state.pop("sync_backup_clear_after_report", None)
        state.pop("sync_backup_alert_accepted", None)


def _sha256_text(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _assert_no_symlink(path: str) -> None:
    current = os.path.abspath(path)
    if os.path.lexists(current) and os.path.islink(current):
        raise OSError("refusing a symlink")
    while True:
        parent = os.path.dirname(current)
        if parent == current:
            break
        if os.path.islink(parent):
            raise OSError("refusing a symlink")
        current = parent


def _send(
    targets,
    text,
    envelope,
    senders,
    secrets,
    sleep,
    monotonic,
    transport,
    request_heartbeat,
):
    """Provider calls stay outside the state lock."""
    deliveries = {}
    logs = []
    if transport is not None:
        try:
            handed_result = transport(targets, envelope, bool(request_heartbeat))
        except Exception:
            handed_result = None
        if handed_result is None:
            for channel in targets:
                deliveries[channel] = health_notify.NOT_SENT
                logs.append(f"channel={channel} result={health_notify.NOT_SENT}")
            return deliveries, logs, "not-sent"
        for channel in targets:
            value = handed_result.results.get(channel, health_notify.NOT_SENT)
            if value not in {
                health_notify.PROVIDER_ACCEPTED,
                health_notify.PROVIDER_REJECTED,
                health_notify.NOT_SENT,
            }:
                value = health_notify.NOT_SENT
            deliveries[channel] = value
            logs.append(f"channel={channel} result={value}")
        return deliveries, logs, handed_result.heartbeat
    for channel in targets:
        sender = senders.get(channel)
        result = health_notify.deliver(
            channel,
            sender,
            text,
            secrets=secrets,
            sleep=sleep,
            monotonic=monotonic,
        )
        logs.append(health_notify.redact(result.log, secrets))
        deliveries[channel] = result.result
    return deliveries, logs, None


def _record_deliveries(state, mode, civil, fingerprint, deliveries) -> None:
    for channel, value in deliveries.items():
        state.setdefault("last_result", {})[channel] = value
        if value == health_notify.PROVIDER_ACCEPTED:
            state.setdefault("accepted", {})[_accept_key(mode, civil, fingerprint, channel)] = value
            state.setdefault("pending", {}).pop(channel, None)
        else:
            state.setdefault("pending", {})[channel] = mode
    if mode == "report":
        state["last_report_date"] = civil


def _targets(mode: str, state: dict, civil: str, changed: bool, recovery: bool) -> list[str]:
    accepted = state.get("accepted") or {}
    last = state.get("last_result") or {}
    pending = state.get("pending") or {}
    if mode == "report":
        chosen = []
        for channel in CHANNELS:
            key = _accept_key("report", civil, None, channel)
            if accepted.get(key) == health_notify.PROVIDER_ACCEPTED:
                continue
            chosen.append(channel)
    elif changed or recovery:
        chosen = list(CHANNELS)
    else:
        chosen = [
            channel
            for channel in CHANNELS
            if pending.get(channel) and last.get(channel) != health_notify.PROVIDER_ACCEPTED
        ]
    for channel in _incident_channels(state):
        if channel not in chosen:
            chosen.append(channel)
    return chosen


def _incident_channels(state: dict) -> list[str]:
    """Channels that still owe a notification for the current backup incident.

    The incident id is not the health-check severity. A new failure gets a
    new id even when another check was already ``FAILED``.
    """
    if state.get("sync_backup_notice") not in {"failed", "retention_warning"}:
        return []
    incident = state.get("sync_backup_incident")
    if not isinstance(incident, dict) or not incident.get("id"):
        return []
    if incident.get("kind") not in {"failed", "retention_warning"}:
        return []
    accepted = state.get("sync_backup_alert_accepted")
    if not isinstance(accepted, dict):
        accepted = {}
    return [channel for channel in CHANNELS if accepted.get(channel) is not True]


def _envelope(mode: str, checks: list[Check], recovery: bool, state: dict, civil: str) -> dict:
    # A daily report stays a report so its heartbeat can be tied to that
    # acceptance. Check mode still uses the incident or recovery event.
    if mode == "report":
        event = "report"
    elif state.get("sync_backup_notice") in {"failed", "retention_warning"}:
        event = "backup-incident"
    elif recovery:
        event = "recovery"
    else:
        event = "check"
    lines = []
    for item in checks:
        detail = item.detail.replace("\n", " ")[:80]
        lines.append({"name": item.name, "status": item.status, "detail": detail})
    payload = {"event": event, "lines": lines}
    if event == "report":
        payload["report_date"] = civil
    return payload


def _accept_key(mode: str, civil: str, fingerprint, channel: str) -> str:
    if mode == "report":
        return f"report:{civil}:{channel}"
    return f"alert:{json.dumps(fingerprint, separators=(',', ':'))}:{channel}"


def _any_accepted(deliveries: dict) -> bool:
    return any(value == health_notify.PROVIDER_ACCEPTED for value in deliveries.values())


def _maybe_witness(config: HealthConfig) -> None:
    """Record the first observation of a regular sync database. Never create it."""
    path = config.sync_live_db
    if os.path.islink(path) or not os.path.isfile(path):
        return
    if os.path.isfile(config.witness_path):
        return
    directory = os.path.dirname(config.witness_path) or "."
    os.makedirs(directory, exist_ok=True)
    payload = json.dumps(
        {
            "observed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "note": "first observation; polling can miss a create-and-delete between checks",
        }
    ).encode("utf-8")
    _atomic_write(config.witness_path, payload)


def _load(path: str) -> dict:
    if not os.path.isfile(path):
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _save(path: str, state: dict) -> None:
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    _atomic_write(path, json.dumps(state, sort_keys=True).encode("utf-8"))


def _atomic_write(path: str, payload: bytes, mode: int = 0o600) -> None:
    _assert_no_symlink(path)
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=directory, prefix=".health-", suffix=".tmp")
    try:
        os.write(fd, payload)
        os.fsync(fd)
        os.close(fd)
        fd = -1
        for attempt in range(5):
            try:
                os.replace(temporary, path)
                os.chmod(path, mode)
                temporary = ""
                break
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.02)
    finally:
        if fd >= 0:
            os.close(fd)
        if temporary and os.path.exists(temporary):
            os.remove(temporary)


def _live_file_identity(path: str):
    if not path or os.path.islink(path) or not os.path.isfile(path):
        return None
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError:
        return None
    try:
        info = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if not stat.S_ISREG(info.st_mode):
        return None
    return (info.st_dev, info.st_ino)


def _connect_snapshot(descriptor: int, path: str):
    if sys.platform != "win32":
        uri = f"file:/proc/self/fd/{descriptor}?mode=ro"
        return sqlite3.connect(uri, uri=True)
    uri = Path(path).resolve().as_uri() + "?mode=ro"
    return sqlite3.connect(uri, uri=True)


def _thread_lock(path: str) -> threading.Lock:
    with _THREAD_LOCKS_GUARD:
        lock = _THREAD_LOCKS.get(path)
        if lock is None:
            lock = threading.Lock()
            _THREAD_LOCKS[path] = lock
        return lock


@contextmanager
def _lock(path: str, timeout: float = LOCK_TIMEOUT):
    """Lock a state file without treating a leftover file as a held lock.

    The operating-system lock is released when this process exits, including
    after a crash. A file left behind by the old exclusive-create lock does
    not block a later writer. The in-process lock covers threads, because a
    Windows byte lock is per process. The lock file is not deleted by age.
    """
    _assert_no_symlink(path)
    if os.path.islink(path):
        raise OSError("health state lock")
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    thread_lock = _thread_lock(os.path.abspath(path))
    if not thread_lock.acquire(timeout=timeout):
        raise TimeoutError("health state lock")
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_BINARY", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError:
        thread_lock.release()
        raise
    try:
        if os.fstat(descriptor).st_size == 0:
            os.write(descriptor, b"\0")
        os.lseek(descriptor, 0, os.SEEK_SET)
        _acquire_os_lock(descriptor, timeout)
        try:
            yield
        finally:
            _release_os_lock(descriptor)
    finally:
        os.close(descriptor)
        thread_lock.release()


def _acquire_os_lock(descriptor: int, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    if sys.platform == "win32":
        import msvcrt

        while True:
            try:
                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
                return
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("health state lock")
                time.sleep(0.01)
    import fcntl

    while True:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except BlockingIOError:
            if time.monotonic() >= deadline:
                raise TimeoutError("health state lock")
            time.sleep(0.01)


def _release_os_lock(descriptor: int) -> None:
    if sys.platform == "win32":
        import msvcrt

        os.lseek(descriptor, 0, os.SEEK_SET)
        msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
        return
    import fcntl

    fcntl.flock(descriptor, fcntl.LOCK_UN)
