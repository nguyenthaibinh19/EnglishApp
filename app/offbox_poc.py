"""Local encrypted recovery proof of concept (Phase 18B.9B).

THIS MODULE IS A LOCAL SYNTHETIC RECOVERY POC, NOT A PRODUCTION BACKUP UPLOADER.

It drives a disposable local restic repository for synthetic SQLite fixtures.
It does not open a network repository, read production databases, or choose an
RPO or RTO. A passing local run does not verify external storage.

A missing sync snapshot is a skip only when the caller says Cloud Sync is off
and the sync database has never existed. That skip is not a completed restore.
The accounts snapshot is always required.

The freshness window is an argument supplied by the caller. It is not an
accepted production recovery objective.

These production controls are not implemented here:

- ``_child_env`` copies the parent environment and drops only a short deny
  list. Production code must use an explicit minimal environment allowlist.
- ``remove_private_tree`` is unsafe for production cleanup. Windows junctions
  and other path aliases are not fully protected. The recovery proof does not
  call it. Production cleanup needs a separately reviewed design.
- Account checks look for a synthetic marker. They are not a production
  accounts verifier.
- Symlink and junction protections are not fully verified.
- Local restic repositories do not prove external storage security.
- B2 restricted permissions, Object Lock, retention, and recovery access
  remain unverified.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import stat
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Mapping, Optional, Sequence

STATUS_RESTORED = "RESTORED"
STATUS_ACCOUNTS_ONLY = "ACCOUNTS_RESTORED_SYNC_SKIPPED"
SYNC_PRESENT = "PRESENT"
SYNC_SKIPPED = "SKIPPED"
SYNC_RESTORED = "RESTORED"

DEFAULT_FORBIDDEN_ROOTS = (
    "/opt/language-guard",
    "/var/backups/language-guard",
    "/etc/language-guard",
)
_REMOTE_PREFIXES = (
    "s3:",
    "b2:",
    "sftp:",
    "rest:",
    "rclone:",
    "azure:",
    "gs:",
    "swift:",
)
_STRIPPED_ENV = (
    "RESTIC_PASSWORD",
    "RESTIC_PASSWORD_COMMAND",
    "RESTIC_PASSWORD_FILE",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "B2_ACCOUNT_ID",
    "B2_ACCOUNT_KEY",
)
_REQUIRED_SYNC_TABLES = ("sync_meta", "vocabulary_entities", "vocabulary_changes")


class OffboxPocError(Exception):
    """The local proof could not produce a usable recovery report."""

    def __init__(self, message: str, *, secrets: Sequence[str] = ()):
        super().__init__(redact(message, secrets))


class OffboxStaleSnapshot(OffboxPocError):
    """The newest restic snapshot is older than the supplied window."""


@dataclass(frozen=True)
class InputPlan:
    """What a local proof is allowed to back up."""

    accounts_snapshot: str
    sync_snapshot: Optional[str]
    sync_status: str
    sync_restore_completed: bool = False

    def __post_init__(self) -> None:
        if self.sync_status == SYNC_SKIPPED and (
            self.sync_snapshot is not None or self.sync_restore_completed
        ):
            raise OffboxPocError(
                "A skipped sync snapshot cannot be a completed restore."
            )


@dataclass(frozen=True)
class RecoveryReport:
    """Non-sensitive result of one local proof. Payloads stay out."""

    status: str
    sync_status: str
    sync_restore_completed: bool
    snapshot_id: str
    accounts_integrity: str
    sync_integrity: str
    schema_version: Optional[int]
    vocabulary_present: bool
    accounts_label_present: bool

    def __post_init__(self) -> None:
        if self.sync_status == SYNC_SKIPPED and (
            self.sync_restore_completed or self.status == STATUS_RESTORED
        ):
            raise OffboxPocError(
                "A skipped sync snapshot cannot be a completed restore."
            )


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


Runner = Callable[..., object]


def redact(text: str, secrets: Sequence[str]) -> str:
    """Remove known secrets. Longer secrets are replaced first."""
    cleaned = text or ""
    ordered = sorted({item for item in secrets if item}, key=len, reverse=True)
    for secret in ordered:
        cleaned = cleaned.replace(secret, "[REDACTED]")
    return cleaned


def file_sha256(path: str) -> str:
    """Hash a regular file. Symlinks are refused."""
    if os.path.islink(path) or not os.path.isfile(path):
        raise OffboxPocError("Refusing to hash a path that is not a regular file.")
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def plan_inputs(
    accounts_snapshot: Optional[str],
    sync_snapshot: Optional[str],
    *,
    sync_database_ever_existed: bool,
    cloud_sync_enabled: bool,
) -> InputPlan:
    """Require an accounts snapshot. Skip sync only while it has never existed."""
    if not _is_regular_file(accounts_snapshot):
        raise OffboxPocError("Accounts snapshot is required.")
    if _is_regular_file(sync_snapshot):
        return InputPlan(str(accounts_snapshot), str(sync_snapshot), SYNC_PRESENT)
    if sync_snapshot and os.path.lexists(sync_snapshot):
        raise OffboxPocError("Sync snapshot is not a regular file.")
    if cloud_sync_enabled or sync_database_ever_existed:
        raise OffboxPocError(
            "Sync snapshot is missing after sync existed or was enabled."
        )
    return InputPlan(str(accounts_snapshot), None, SYNC_SKIPPED)


def assert_sqlite_integrity(path: str) -> None:
    """Require ``PRAGMA integrity_check`` = ``ok`` on a regular snapshot."""
    if not _is_regular_file(path):
        raise OffboxPocError("SQLite snapshot is not a regular file.")
    uri = Path(path).resolve().as_uri() + "?mode=ro"
    try:
        connection = sqlite3.connect(uri, uri=True)
    except sqlite3.Error as error:
        raise OffboxPocError("SQLite snapshot failed integrity check.") from error
    try:
        row = connection.execute("PRAGMA integrity_check").fetchone()
    except sqlite3.Error as error:
        raise OffboxPocError("SQLite snapshot failed integrity check.") from error
    finally:
        connection.close()
    if row is None or str(row[0]) != "ok":
        raise OffboxPocError("SQLite snapshot failed integrity check.")


def ensure_fresh(
    snapshot_time: datetime,
    *,
    now: datetime,
    max_age: timedelta,
) -> None:
    """Reject a snapshot older than ``max_age``. The window is not an RPO."""
    if snapshot_time.tzinfo is None or now.tzinfo is None:
        raise OffboxPocError("Snapshot times must be timezone-aware.")
    if max_age < timedelta(0):
        raise OffboxPocError("Freshness window must not be negative.")
    if now - snapshot_time > max_age:
        raise OffboxStaleSnapshot(
            "Restic snapshot is older than the supplied freshness window."
        )


def require_local_repository(repo: str) -> None:
    """Refuse S3, B2, SFTP, and other non-local repository names."""
    if not repo or not str(repo).strip():
        raise OffboxPocError("Restic repository path is required.")
    lowered = str(repo).replace("\\", "/").lower()
    if "://" in lowered or lowered.startswith(_REMOTE_PREFIXES) or lowered.startswith("//"):
        raise OffboxPocError("Refusing a non-local restic repository.")


def reject_forbidden_paths(paths: Sequence[str], forbidden_roots: Sequence[str]) -> None:
    """Refuse paths inside a protected root."""
    for path in paths:
        if not path:
            continue
        resolved = os.path.normcase(os.path.abspath(path))
        for root in forbidden_roots:
            root_resolved = os.path.normcase(os.path.abspath(root))
            if resolved == root_resolved or resolved.startswith(root_resolved + os.sep):
                raise OffboxPocError("Refusing a protected production path.")


def make_new_directory(path: str) -> None:
    """Create one new directory. On POSIX it must end up mode 0700."""
    if os.path.lexists(path):
        raise OffboxPocError("Refusing to reuse an existing staging path.")
    os.makedirs(path)
    if os.name != "posix":
        return
    os.chmod(path, 0o700)
    mode = stat.S_IMODE(os.stat(path).st_mode)
    if mode & 0o077:
        raise OffboxPocError("Private directory permissions could not be enforced.")


def remove_private_tree(path: str, *, allowed_root: str) -> None:
    """Local helper only. Not used by the recovery proof.

    Unsafe for production cleanup: junctions and other path aliases are not
    fully protected. Production cleanup needs a separately reviewed design.
    """
    if os.path.islink(path):
        raise OffboxPocError("Refusing to delete a symlink.")
    if not os.path.isdir(path):
        raise OffboxPocError("Refusing to delete a path that is not a directory.")
    resolved = os.path.normcase(os.path.abspath(path))
    root = os.path.normcase(os.path.abspath(allowed_root))
    if resolved == root or not resolved.startswith(root + os.sep):
        raise OffboxPocError("Refusing to delete outside the allowed root.")
    shutil.rmtree(path)


def stage_snapshots(plan: InputPlan, inbox: str) -> None:
    """Copy published snapshots into a new inbox under fixed file names."""
    make_new_directory(inbox)
    copies = {"accounts.db": plan.accounts_snapshot}
    if plan.sync_snapshot:
        copies["study-sync.db"] = plan.sync_snapshot
    for name, source in copies.items():
        _copy_regular_exclusive(source, os.path.join(inbox, name))


def render_report(report: RecoveryReport) -> str:
    """Render a report with status fields only. No payloads and no secrets."""
    lines = [
        f"status={report.status}",
        f"sync_status={report.sync_status}",
        "sync_restore_completed="
        + ("true" if report.sync_restore_completed else "false"),
        f"accounts_integrity={report.accounts_integrity}",
        f"snapshot_id={report.snapshot_id}",
        "accounts_marker="
        + ("present" if report.accounts_label_present else "missing"),
    ]
    if report.sync_status == SYNC_SKIPPED:
        lines.append("sync_restore=not_performed")
    else:
        lines.append(f"sync_integrity={report.sync_integrity}")
        lines.append(f"schema_version={report.schema_version}")
        lines.append(
            "vocabulary_record="
            + ("present" if report.vocabulary_present else "missing")
        )
    return "\n".join(lines)


class LocalRestic:
    """One disposable local repository. The password is never a command argument."""

    def __init__(
        self,
        binary: str,
        repo: str,
        password_file: str,
        *,
        runner: Optional[Runner] = None,
        extra_secrets: Sequence[str] = (),
    ) -> None:
        require_local_repository(repo)
        if not binary or not str(binary).strip():
            raise OffboxPocError("Restic binary is required.")
        if not _is_regular_file(password_file):
            raise OffboxPocError("Restic password file is missing.")
        password = _read_secret(password_file)
        if not password:
            raise OffboxPocError("Restic password file is empty.")
        self.binary = str(binary)
        self.repo = str(repo)
        self.password_file = str(password_file)
        self.runner = runner or _subprocess_runner
        self._secrets = tuple(
            item for item in (password, *extra_secrets) if item
        )

    def __repr__(self) -> str:
        return f"LocalRestic(repo={self.repo!r})"

    def run(self, args: Sequence[str], *, cwd: Optional[str] = None) -> CommandResult:
        command = [
            self.binary,
            "--repo",
            self.repo,
            "--password-file",
            self.password_file,
            *args,
        ]
        for argument in command:
            if any(secret and secret in argument for secret in self._secrets):
                raise OffboxPocError("Refusing to place a secret on the command line.")
        runner_kwargs: dict[str, object] = {
            "capture_output": True,
            "env": _child_env(),
        }
        if cwd is not None:
            runner_kwargs["cwd"] = cwd
        completed = self.runner(command, **runner_kwargs)
        returncode = int(getattr(completed, "returncode"))
        stdout = redact(_as_text(getattr(completed, "stdout", "")), self._secrets)
        stderr = redact(_as_text(getattr(completed, "stderr", "")), self._secrets)
        return CommandResult(returncode, stdout, stderr)

    def require(self, args: Sequence[str], *, cwd: Optional[str] = None) -> CommandResult:
        result = self.run(args, cwd=cwd)
        if result.returncode != 0:
            kind = "interrupted" if result.returncode < 0 else "failed"
            raise OffboxPocError(
                f"restic {args[0]} {kind}. {result.stderr}",
                secrets=self._secrets,
            )
        return result


def backup_inbox(client: LocalRestic, inbox: str) -> dict:
    """Back up a staged inbox and return the newest tagged snapshot object.

    The snapshot stores the inbox directory name, not its absolute path.
    On Windows, restoring an absolute path makes restic try to update
    timestamps on parents such as ``C:\\Users``.
    """
    parent, name = _relative_backup_target(inbox)
    client.require(["backup", name, "--tag", "offbox-poc"], cwd=parent)
    return newest_snapshot(client)


def newest_snapshot(client: LocalRestic) -> dict:
    result = client.require(["snapshots", "--json", "--tag", "offbox-poc"])
    try:
        payload = json.loads(result.stdout or "[]")
    except json.JSONDecodeError as error:
        raise OffboxPocError("restic snapshots JSON was unreadable.") from error
    if isinstance(payload, dict):
        payload = payload.get("snapshots", [])
    if not isinstance(payload, list) or not payload:
        raise OffboxPocError("restic backup produced no snapshot.")
    chosen = max(payload, key=lambda item: str(item.get("time") or ""))
    if not isinstance(chosen, dict) or not chosen.get("id") or not chosen.get("time"):
        raise OffboxPocError("restic snapshot identity was incomplete.")
    return chosen


def parse_snapshot_time(value: str) -> datetime:
    """Parse a restic timestamp, including nanosecond fractions."""
    text = str(value).strip().replace("Z", "+00:00")
    if "." in text:
        head, tail = text.split(".", 1)
        digits: list[str] = []
        rest = ""
        for index, character in enumerate(tail):
            if character.isdigit() and rest == "":
                digits.append(character)
            else:
                rest = tail[index:]
                break
        fraction = "".join(digits[:6])
        text = head + (("." + fraction) if fraction else "") + rest
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as error:
        raise OffboxPocError("restic snapshot time was unreadable.") from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def restore_snapshot(client: LocalRestic, snapshot_id: str, destination: str) -> None:
    """Restore into a path that does not exist yet."""
    if not snapshot_id or any(character in snapshot_id for character in " \t\r\n"):
        raise OffboxPocError("Restic snapshot id is invalid.")
    if os.path.lexists(destination):
        raise OffboxPocError("Refusing to restore into an existing path.")
    parent = os.path.dirname(os.path.abspath(destination))
    if parent:
        os.makedirs(parent, exist_ok=True)
    client.require(["restore", snapshot_id, "--target", destination])


def prove_local_recovery(
    *,
    accounts_snapshot: str,
    sync_snapshot: Optional[str],
    protected_files: Sequence[str],
    repo: str,
    password_file: str,
    inbox: str,
    restore_dir: str,
    restic_binary: str,
    expected_account_label: str,
    expected_vocab_id: Optional[str],
    expected_meaning: Optional[str],
    sync_database_ever_existed: bool,
    cloud_sync_enabled: bool,
    now: datetime,
    max_age: timedelta,
    forbidden_roots: Sequence[str] = DEFAULT_FORBIDDEN_ROOTS,
    runner: Optional[Runner] = None,
) -> RecoveryReport:
    """Back up published snapshots with local restic and restore them elsewhere.

    ``max_age`` is only the freshness knob for this call. It does not accept
    a production RPO.
    """
    paths = [
        accounts_snapshot,
        sync_snapshot or "",
        repo,
        password_file,
        inbox,
        restore_dir,
        *protected_files,
    ]
    reject_forbidden_paths(paths, forbidden_roots)
    plan = plan_inputs(
        accounts_snapshot,
        sync_snapshot,
        sync_database_ever_existed=sync_database_ever_existed,
        cloud_sync_enabled=cloud_sync_enabled,
    )
    if plan.sync_status == SYNC_SKIPPED and (expected_vocab_id or expected_meaning):
        raise OffboxPocError("A skipped sync snapshot has no vocabulary to verify.")
    if plan.sync_status == SYNC_PRESENT and not (expected_vocab_id and expected_meaning):
        raise OffboxPocError("Sync verification needs the synthetic record identity.")
    assert_sqlite_integrity(plan.accounts_snapshot)
    if plan.sync_snapshot:
        assert_sqlite_integrity(plan.sync_snapshot)
    before = _fingerprints(protected_files)
    stage_snapshots(plan, inbox)
    os.makedirs(repo, exist_ok=False)
    client = LocalRestic(
        restic_binary,
        repo,
        password_file,
        runner=runner,
    )
    client.require(["init"])
    snapshot = backup_inbox(client, inbox)
    ensure_fresh(parse_snapshot_time(str(snapshot["time"])), now=now, max_age=max_age)
    restore_snapshot(client, str(snapshot["id"]), restore_dir)
    restored_accounts = _one_named(restore_dir, "accounts.db")
    accounts_ok = _accounts_marker_present(restored_accounts, expected_account_label)
    if plan.sync_snapshot:
        restored_sync = _one_named(restore_dir, "study-sync.db")
        schema_version, vocabulary_present = _verify_sync_record(
            restored_sync,
            vocab_id=str(expected_vocab_id),
            meaning=str(expected_meaning),
        )
        sync_status = SYNC_RESTORED
        sync_completed = True
        sync_integrity = "ok"
        status = STATUS_RESTORED
    else:
        if _named(restore_dir, "study-sync.db"):
            raise OffboxPocError("A skipped sync snapshot was present in the restore.")
        schema_version = None
        vocabulary_present = False
        sync_status = SYNC_SKIPPED
        sync_completed = False
        sync_integrity = ""
        status = STATUS_ACCOUNTS_ONLY
    _assert_unchanged(protected_files, before)
    return RecoveryReport(
        status=status,
        sync_status=sync_status,
        sync_restore_completed=sync_completed,
        snapshot_id=str(snapshot["id"]),
        accounts_integrity="ok",
        sync_integrity=sync_integrity,
        schema_version=schema_version,
        vocabulary_present=vocabulary_present,
        accounts_label_present=accounts_ok,
    )


def _accounts_marker_present(path: str, label: str) -> bool:
    assert_sqlite_integrity(path)
    connection = _read_only(path)
    try:
        row = connection.execute(
            "SELECT label FROM synthetic_accounts WHERE label = ?",
            (label,),
        ).fetchone()
    except sqlite3.Error as error:
        raise OffboxPocError("Restored accounts snapshot could not be read.") from error
    finally:
        connection.close()
    if row is None:
        raise OffboxPocError("Restored accounts snapshot is missing the expected marker.")
    return True


def _verify_sync_record(path: str, *, vocab_id: str, meaning: str) -> tuple[int, bool]:
    assert_sqlite_integrity(path)
    connection = _read_only(path)
    try:
        version_row = connection.execute(
            "SELECT value FROM sync_meta WHERE key = 'schema_version'"
        ).fetchone()
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        record = connection.execute(
            "SELECT payload_json FROM vocabulary_entities WHERE vocab_id = ?",
            (vocab_id,),
        ).fetchone()
    except sqlite3.Error as error:
        raise OffboxPocError("Restored sync snapshot could not be read.") from error
    finally:
        connection.close()
    if version_row is None:
        raise OffboxPocError("Restored sync snapshot has no schema version.")
    try:
        version = int(version_row[0])
    except (TypeError, ValueError) as error:
        raise OffboxPocError("Restored sync snapshot schema version is unreadable.") from error
    if version != 2:
        raise OffboxPocError("Restored sync snapshot schema version is not supported.")
    missing = [name for name in _REQUIRED_SYNC_TABLES if name not in tables]
    if missing:
        raise OffboxPocError("Restored sync snapshot is missing a required table.")
    if record is None:
        raise OffboxPocError("Restored sync snapshot is missing the expected record.")
    try:
        payload = json.loads(record[0])
    except (TypeError, json.JSONDecodeError) as error:
        raise OffboxPocError("Restored sync record could not be read.") from error
    if not isinstance(payload, dict) or payload.get("meaning") != meaning:
        raise OffboxPocError("Restored sync record did not match the synthetic marker.")
    return version, True


def _fingerprints(paths: Sequence[str]) -> Mapping[str, str]:
    found = {}
    for path in paths:
        if not path:
            continue
        found[os.path.abspath(path)] = file_sha256(path)
    return found


def _assert_unchanged(paths: Sequence[str], before: Mapping[str, str]) -> None:
    after = _fingerprints(paths)
    if after != before:
        raise OffboxPocError("A protected file changed during recovery.")


def _one_named(root: str, name: str) -> str:
    matches = _named(root, name)
    if len(matches) != 1:
        raise OffboxPocError("Restored snapshot file count was not exactly one.")
    return matches[0]


def _named(root: str, name: str) -> list[str]:
    matches: list[str] = []
    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [
            item
            for item in dirnames
            if not os.path.islink(os.path.join(directory, item))
        ]
        if name not in filenames:
            continue
        path = os.path.join(directory, name)
        if os.path.islink(path) or not os.path.isfile(path):
            raise OffboxPocError("Refusing a restored path that is not a regular file.")
        matches.append(path)
    return matches


def _copy_regular_exclusive(source: str, destination: str) -> None:
    if os.path.abspath(source) == os.path.abspath(destination):
        raise OffboxPocError("Refusing to stage a snapshot onto itself.")
    if not _is_regular_file(source):
        raise OffboxPocError("Refusing a snapshot that is not a regular file.")
    # O_BINARY keeps Windows from expanding LF to CRLF and breaking SQLite pages.
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(destination, flags, 0o600)
    try:
        with open(source, "rb") as incoming:
            while True:
                chunk = incoming.read(1024 * 1024)
                if not chunk:
                    break
                os.write(descriptor, chunk)
    except Exception:
        os.close(descriptor)
        _discard(destination)
        raise
    os.close(descriptor)


def _read_only(path: str) -> sqlite3.Connection:
    return sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)


def _is_regular_file(path: Optional[str]) -> bool:
    return bool(path) and os.path.isfile(path) and not os.path.islink(path)


def _read_secret(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read().strip()


def _child_env() -> dict[str, str]:
    """Copy the parent environment after dropping a short deny list.

    This is not a production allowlist. Unlisted parent variables are inherited.
    """
    env = dict(os.environ)
    for name in _STRIPPED_ENV:
        env.pop(name, None)
    return env


def _as_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _relative_backup_target(inbox: str) -> tuple[str, str]:
    if not os.path.isdir(inbox) or os.path.islink(inbox):
        raise OffboxPocError("Staging inbox is not a directory.")
    absolute = os.path.abspath(inbox)
    parent = os.path.dirname(absolute)
    name = os.path.basename(absolute)
    if (
        not parent
        or name in ("", ".", "..")
        or os.path.sep in name
        or (os.path.altsep is not None and os.path.altsep in name)
    ):
        raise OffboxPocError("Staging inbox name is not a single directory.")
    return parent, name


def _subprocess_runner(
    command: Sequence[str],
    *,
    capture_output: bool,
    env: Mapping[str, str],
    cwd: Optional[str] = None,
):
    return subprocess.run(
        list(command),
        capture_output=capture_output,
        env=dict(env),
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _discard(path: str) -> None:
    try:
        if path and os.path.lexists(path) and not os.path.isdir(path):
            os.remove(path)
    except OSError:
        pass
