"""Phase 18B.9B local restic recovery proof. Temporary files only."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import offbox_poc
import sync_backup
import sync_store
from offbox_poc import (
    STATUS_ACCOUNTS_ONLY,
    STATUS_RESTORED,
    SYNC_PRESENT,
    SYNC_SKIPPED,
    CommandResult,
    LocalRestic,
    OffboxPocError,
    OffboxStaleSnapshot,
    RecoveryReport,
    assert_sqlite_integrity,
    backup_inbox,
    ensure_fresh,
    file_sha256,
    parse_snapshot_time,
    plan_inputs,
    prove_local_recovery,
    redact,
    reject_forbidden_paths,
    remove_private_tree,
    render_report,
    require_local_repository,
    restore_snapshot,
    stage_snapshots,
)
from sync_backup import SyncBackupError, backup_database, restore_database

ROOT = Path(__file__).resolve().parents[1]
VOCAB_ID = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
MEANING = "synthetic-marker"
LABEL = "synthetic-not-a-real-account"
PASSWORD = "canary-restic-password"
OTHER_PASSWORD = "canary-wrong-password"
ACCOUNT_KEY = "b2-canary-not-a-real-key"


def _load_accounts_backup():
    script = ROOT / "deploy" / "hetzner" / "backup_accounts.py"
    spec = importlib.util.spec_from_file_location("backup_accounts_offbox_poc", script)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _seed_sync(path: Path) -> None:
    connection = sync_store.connect(str(path))
    try:
        sync_store.put_vocabulary(
            connection,
            user_id=7,
            language_code="nl",
            vocab_id=VOCAB_ID,
            payload={"id": VOCAB_ID, "word": "offbox", "meaning": MEANING},
            expected_revision=0,
            operation_id="op-offbox-synthetic",
        )
    finally:
        connection.close()


def _seed_accounts(path: Path) -> None:
    connection = sqlite3.connect(str(path))
    try:
        connection.execute(
            "CREATE TABLE synthetic_accounts (id INTEGER PRIMARY KEY, label TEXT)"
        )
        connection.execute(
            "INSERT INTO synthetic_accounts (label) VALUES (?)",
            (LABEL,),
        )
        connection.commit()
    finally:
        connection.close()


def _published_accounts(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "fixtures" / "accounts.db"
    source.parent.mkdir(parents=True, exist_ok=True)
    _seed_accounts(source)
    backup_dir = tmp_path / "account-snapshots"
    assert _load_accounts_backup().backup_file(str(source), str(backup_dir)) == 0
    published = list(backup_dir.glob("accounts-*.db"))
    assert len(published) == 1
    return source, published[0]


def _published_sync(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "fixtures" / "study_sync.db"
    source.parent.mkdir(parents=True, exist_ok=True)
    _seed_sync(source)
    published = backup_database(str(source), str(tmp_path / "sync-snapshots"))
    assert published is not None
    return source, Path(published.path)


def _write_password(path: Path, secret: str) -> None:
    path.write_text(secret + "\n", encoding="utf-8")


def _fingerprints(paths: list[Path]) -> dict[str, str]:
    return {str(path): file_sha256(str(path)) for path in paths}


@pytest.fixture
def restic_binary() -> str:
    binary = shutil.which("restic")
    if not binary:
        pytest.fail(
            "restic is not installed. Refusing to download or install an executable."
        )
    return binary


def test_missing_accounts_snapshot_is_refused(tmp_path: Path) -> None:
    with pytest.raises(OffboxPocError, match="Accounts snapshot is required"):
        plan_inputs(
            str(tmp_path / "missing-accounts.db"),
            None,
            sync_database_ever_existed=False,
            cloud_sync_enabled=False,
        )


def test_missing_sync_is_skip_only_while_sync_is_off(tmp_path: Path) -> None:
    accounts = tmp_path / "accounts.db"
    accounts.write_bytes(b"placeholder")
    plan = plan_inputs(
        str(accounts),
        None,
        sync_database_ever_existed=False,
        cloud_sync_enabled=False,
    )
    assert plan.sync_status == SYNC_SKIPPED
    assert plan.sync_snapshot is None
    assert plan.sync_restore_completed is False


def test_missing_sync_fails_when_database_ever_existed(tmp_path: Path) -> None:
    accounts = tmp_path / "accounts.db"
    accounts.write_bytes(b"placeholder")
    with pytest.raises(OffboxPocError, match="missing"):
        plan_inputs(
            str(accounts),
            None,
            sync_database_ever_existed=True,
            cloud_sync_enabled=False,
        )


def test_missing_sync_fails_when_cloud_sync_argument_is_true(tmp_path: Path) -> None:
    accounts = tmp_path / "accounts.db"
    accounts.write_bytes(b"placeholder")
    with pytest.raises(OffboxPocError, match="missing"):
        plan_inputs(
            str(accounts),
            None,
            sync_database_ever_existed=False,
            cloud_sync_enabled=True,
        )


def test_present_sync_snapshot_is_not_a_skip(tmp_path: Path) -> None:
    accounts = tmp_path / "accounts.db"
    sync = tmp_path / "study-sync.db"
    accounts.write_bytes(b"accounts")
    sync.write_bytes(b"sync")
    plan = plan_inputs(
        str(accounts),
        str(sync),
        sync_database_ever_existed=False,
        cloud_sync_enabled=False,
    )
    assert plan.sync_status == SYNC_PRESENT
    assert plan.sync_restore_completed is False


def test_staged_copy_preserves_exact_bytes(tmp_path: Path) -> None:
    source = tmp_path / "accounts.db"
    payload = b"line\n" * 60 + b"tail"
    source.write_bytes(payload)
    plan = plan_inputs(
        str(source),
        None,
        sync_database_ever_existed=False,
        cloud_sync_enabled=False,
    )
    inbox = tmp_path / "inbox"
    stage_snapshots(plan, str(inbox))
    assert (inbox / "accounts.db").read_bytes() == payload


def test_corrupt_sqlite_snapshot_is_refused(tmp_path: Path) -> None:
    corrupt = tmp_path / "accounts-corrupt.db"
    corrupt.write_bytes(b"not a sqlite database")
    with pytest.raises(OffboxPocError, match="integrity"):
        assert_sqlite_integrity(str(corrupt))


def test_flipped_header_is_refused_and_original_snapshot_is_unchanged(
    tmp_path: Path,
) -> None:
    _source, published = _published_accounts(tmp_path)
    before = published.read_bytes()
    flipped = tmp_path / "accounts-flipped.db"
    damaged = bytearray(before)
    damaged[:16] = b"\x00" * 16
    flipped.write_bytes(damaged)
    with pytest.raises(OffboxPocError, match="integrity"):
        assert_sqlite_integrity(str(flipped))
    assert published.read_bytes() == before


def test_corrupt_snapshot_does_not_create_a_repository(tmp_path: Path) -> None:
    corrupt = tmp_path / "accounts-corrupt.db"
    corrupt.write_bytes(b"not a sqlite database")
    with pytest.raises(OffboxPocError, match="integrity"):
        prove_local_recovery(
            accounts_snapshot=str(corrupt),
            sync_snapshot=None,
            protected_files=[str(corrupt)],
            repo=str(tmp_path / "repo"),
            password_file=str(tmp_path / "password.txt"),
            inbox=str(tmp_path / "inbox"),
            restore_dir=str(tmp_path / "restore"),
            restic_binary="restic",
            expected_account_label=LABEL,
            expected_vocab_id=None,
            expected_meaning=None,
            sync_database_ever_existed=False,
            cloud_sync_enabled=False,
            now=datetime.now(timezone.utc),
            max_age=timedelta(days=7),
        )
    assert not (tmp_path / "repo").exists()
    assert not (tmp_path / "inbox").exists()
    assert not (tmp_path / "restore").exists()


def test_redact_removes_password_and_storage_keys() -> None:
    text = (
        f"RESTIC_PASSWORD={PASSWORD} "
        f"AWS_SECRET_ACCESS_KEY={ACCOUNT_KEY} "
        f"password file said {OTHER_PASSWORD}"
    )
    cleaned = redact(text, (PASSWORD, OTHER_PASSWORD, ACCOUNT_KEY))
    assert PASSWORD not in cleaned
    assert OTHER_PASSWORD not in cleaned
    assert ACCOUNT_KEY not in cleaned
    assert "[REDACTED]" in cleaned


def test_skip_report_is_not_a_completed_restore() -> None:
    report = RecoveryReport(
        status=STATUS_ACCOUNTS_ONLY,
        sync_status=SYNC_SKIPPED,
        sync_restore_completed=False,
        snapshot_id="abc123",
        accounts_integrity="ok",
        sync_integrity="",
        schema_version=None,
        vocabulary_present=False,
        accounts_label_present=True,
    )
    text = render_report(report)
    assert "status=ACCOUNTS_RESTORED_SYNC_SKIPPED" in text
    assert "sync_status=SKIPPED" in text
    assert "sync_restore_completed=false" in text
    assert "sync_restore=not_performed" in text
    assert MEANING not in text
    assert LABEL not in text
    with pytest.raises(OffboxPocError, match="cannot be a completed restore"):
        RecoveryReport(
            status=STATUS_RESTORED,
            sync_status=SYNC_SKIPPED,
            sync_restore_completed=False,
            snapshot_id="abc123",
            accounts_integrity="ok",
            sync_integrity="",
            schema_version=None,
            vocabulary_present=False,
            accounts_label_present=True,
        )


def test_non_local_repository_is_refused() -> None:
    for repo in (
        "s3:s3.us-west-000.backblazeb2.com/bucket",
        "b2:bucket:path",
        "sftp:user@example:/repo",
        "rest:https://example.invalid/repo",
    ):
        with pytest.raises(OffboxPocError, match="non-local"):
            require_local_repository(repo)


def test_secret_is_not_placed_in_child_env_or_argv(tmp_path: Path) -> None:
    password_file = tmp_path / "password.txt"
    _write_password(password_file, PASSWORD)
    seen: dict[str, object] = {}

    def runner(command, *, capture_output: bool, env: dict[str, str]) -> CommandResult:
        seen["command"] = list(command)
        seen["env"] = dict(env)
        seen["capture_output"] = capture_output
        return CommandResult(0, "[]", f"stderr {PASSWORD} {ACCOUNT_KEY}")

    previous_password = os.environ.get("RESTIC_PASSWORD")
    previous_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
    os.environ["RESTIC_PASSWORD"] = PASSWORD
    os.environ["AWS_SECRET_ACCESS_KEY"] = ACCOUNT_KEY
    try:
        client = LocalRestic(
            "restic",
            str(tmp_path / "repo"),
            str(password_file),
            runner=runner,
            extra_secrets=(ACCOUNT_KEY,),
        )
        result = client.run(["snapshots"])
    finally:
        if previous_password is None:
            os.environ.pop("RESTIC_PASSWORD", None)
        else:
            os.environ["RESTIC_PASSWORD"] = previous_password
        if previous_key is None:
            os.environ.pop("AWS_SECRET_ACCESS_KEY", None)
        else:
            os.environ["AWS_SECRET_ACCESS_KEY"] = previous_key
    command = seen["command"]
    assert isinstance(command, list)
    assert all(PASSWORD not in argument for argument in command)
    assert all(ACCOUNT_KEY not in argument for argument in command)
    child_env = seen["env"]
    assert isinstance(child_env, dict)
    assert "RESTIC_PASSWORD" not in child_env
    assert "AWS_SECRET_ACCESS_KEY" not in child_env
    assert PASSWORD not in result.stderr
    assert ACCOUNT_KEY not in result.stderr


def test_interrupted_backup_is_a_failure(tmp_path: Path) -> None:
    password_file = tmp_path / "password.txt"
    _write_password(password_file, PASSWORD)

    def runner(command, *, capture_output: bool, env: dict[str, str]) -> CommandResult:
        del command, capture_output, env
        return CommandResult(-15, "", f"killed while reading {PASSWORD}")

    client = LocalRestic("restic", str(tmp_path / "repo"), str(password_file), runner=runner)
    with pytest.raises(OffboxPocError, match="interrupted") as caught:
        client.require(["backup", str(tmp_path)])
    assert PASSWORD not in str(caught.value)


def test_occupied_restore_does_not_start(tmp_path: Path) -> None:
    password_file = tmp_path / "password.txt"
    _write_password(password_file, PASSWORD)
    destination = tmp_path / "occupied"
    destination.mkdir()
    marker = destination / "marker.txt"
    marker.write_text("keep", encoding="utf-8")

    def runner(command, *, capture_output: bool, env: dict[str, str]) -> CommandResult:
        del command, capture_output, env
        raise AssertionError("restic must not start")

    client = LocalRestic("restic", str(tmp_path / "repo"), str(password_file), runner=runner)
    with pytest.raises(OffboxPocError, match="existing path"):
        restore_snapshot(client, "abc123", str(destination))
    assert marker.read_text(encoding="utf-8") == "keep"


def test_sqlite_online_backup_preserves_synthetic_records(tmp_path: Path) -> None:
    accounts_source, accounts_snapshot = _published_accounts(tmp_path)
    sync_source, sync_snapshot = _published_sync(tmp_path)
    protected = [accounts_source, accounts_snapshot, sync_source, sync_snapshot]
    before = _fingerprints(protected)
    assert_sqlite_integrity(str(accounts_snapshot))
    _assert_accounts_marker(accounts_snapshot)
    restored = tmp_path / "sqlite-restore" / "study_sync.db"
    restore_database(str(sync_snapshot), str(restored))
    _assert_sync_record(restored)
    assert _fingerprints(protected) == before


def test_sqlite_restore_refuses_existing_destination(tmp_path: Path) -> None:
    _source, published = _published_sync(tmp_path)
    destination = tmp_path / "protected" / "study_sync.db"
    destination.parent.mkdir()
    destination.write_bytes(b"protected")
    before = destination.read_bytes()
    with pytest.raises(SyncBackupError):
        restore_database(str(published), str(destination))
    assert destination.read_bytes() == before
    assert not list(destination.parent.glob("*.partial"))


def test_stale_window_rejects_a_gap_larger_than_the_supplied_window() -> None:
    now = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
    # A 26-hour window is only a test knob. It is not an accepted RPO.
    # A snapshot 48 hours old is outside that window, so one missed daily
    # copy would already be stale.
    with pytest.raises(OffboxStaleSnapshot):
        ensure_fresh(
            now - timedelta(hours=48),
            now=now,
            max_age=timedelta(hours=26),
        )
    ensure_fresh(
        now - timedelta(hours=1),
        now=now,
        max_age=timedelta(hours=26),
    )


def test_restic_timestamp_with_nanoseconds_parses() -> None:
    parsed = parse_snapshot_time("2026-11-10T12:00:00.123456789Z")
    assert parsed == datetime(2026, 11, 10, 12, 0, 0, 123456, tzinfo=timezone.utc)


def test_symlink_snapshot_is_refused(tmp_path: Path) -> None:
    target = tmp_path / "accounts.db"
    target.write_bytes(b"accounts")
    link = tmp_path / "accounts-link.db"
    try:
        os.symlink(target, link)
    except OSError:
        pytest.skip("symlink creation is not permitted on this machine")
    with pytest.raises(OffboxPocError, match="required"):
        plan_inputs(
            str(link),
            None,
            sync_database_ever_existed=False,
            cloud_sync_enabled=False,
        )


def test_private_cleanup_stays_inside_root(tmp_path: Path) -> None:
    root = tmp_path / "allowed"
    inbox = root / "inbox"
    inbox.mkdir(parents=True)
    (inbox / "accounts.db").write_bytes(b"copy")
    sibling = tmp_path / "sibling"
    sibling.mkdir()
    (sibling / "keep.txt").write_text("keep", encoding="utf-8")
    remove_private_tree(str(inbox), allowed_root=str(root))
    assert not inbox.exists()
    with pytest.raises(OffboxPocError, match="outside"):
        remove_private_tree(str(sibling), allowed_root=str(root))
    assert (sibling / "keep.txt").read_text(encoding="utf-8") == "keep"
    with pytest.raises(OffboxPocError, match="outside"):
        remove_private_tree(str(root), allowed_root=str(root))


def test_forbidden_production_root_is_refused(tmp_path: Path) -> None:
    inside = tmp_path / "accounts.db"
    inside.write_bytes(b"x")
    with pytest.raises(OffboxPocError, match="protected"):
        reject_forbidden_paths([str(inside)], [str(tmp_path)])


def test_module_does_not_read_study_sync_enabled() -> None:
    source = Path(offbox_poc.__file__).read_text(encoding="utf-8")
    assert "STUDY_SYNC_ENABLED" not in source


def test_local_restic_round_trip(tmp_path: Path, restic_binary: str) -> None:
    accounts_source, accounts_snapshot = _published_accounts(tmp_path)
    sync_source, sync_snapshot = _published_sync(tmp_path)
    protected = [accounts_source, accounts_snapshot, sync_source, sync_snapshot]
    before = _fingerprints(protected)
    password_file = tmp_path / "password.txt"
    _write_password(password_file, PASSWORD)
    report = prove_local_recovery(
        accounts_snapshot=str(accounts_snapshot),
        sync_snapshot=str(sync_snapshot),
        protected_files=[str(path) for path in protected],
        repo=str(tmp_path / "repo"),
        password_file=str(password_file),
        inbox=str(tmp_path / "inbox"),
        restore_dir=str(tmp_path / "restore"),
        restic_binary=restic_binary,
        expected_account_label=LABEL,
        expected_vocab_id=VOCAB_ID,
        expected_meaning=MEANING,
        sync_database_ever_existed=False,
        cloud_sync_enabled=False,
        now=datetime.now(timezone.utc),
        max_age=timedelta(days=7),
        forbidden_roots=("/opt/language-guard", "/var/backups/language-guard"),
    )
    assert report.status == STATUS_RESTORED
    assert report.sync_status == "RESTORED"
    assert report.sync_restore_completed is True
    assert report.schema_version == 2
    assert report.accounts_integrity == "ok"
    assert report.sync_integrity == "ok"
    assert report.vocabulary_present is True
    assert report.accounts_label_present is True
    rendered = render_report(report)
    assert PASSWORD not in rendered
    assert MEANING not in rendered
    assert LABEL not in rendered
    assert _fingerprints(protected) == before

    restored_accounts = next((tmp_path / "restore").rglob("accounts.db"))
    restored_sync = next((tmp_path / "restore").rglob("study-sync.db"))
    assert restored_accounts.read_bytes() == accounts_snapshot.read_bytes()
    assert restored_sync.read_bytes() == sync_snapshot.read_bytes()
    _assert_sync_record(restored_sync)
    _assert_accounts_marker(restored_accounts)


def test_accounts_only_restic_round_trip_skips_sync(
    tmp_path: Path, restic_binary: str
) -> None:
    accounts_source, accounts_snapshot = _published_accounts(tmp_path)
    protected = [accounts_source, accounts_snapshot]
    before = _fingerprints(protected)
    password_file = tmp_path / "password.txt"
    _write_password(password_file, PASSWORD)
    report = prove_local_recovery(
        accounts_snapshot=str(accounts_snapshot),
        sync_snapshot=None,
        protected_files=[str(path) for path in protected],
        repo=str(tmp_path / "repo"),
        password_file=str(password_file),
        inbox=str(tmp_path / "inbox"),
        restore_dir=str(tmp_path / "restore"),
        restic_binary=restic_binary,
        expected_account_label=LABEL,
        expected_vocab_id=None,
        expected_meaning=None,
        sync_database_ever_existed=False,
        cloud_sync_enabled=False,
        now=datetime.now(timezone.utc),
        max_age=timedelta(days=7),
        forbidden_roots=("/opt/language-guard",),
    )
    rendered = render_report(report)
    assert report.status == STATUS_ACCOUNTS_ONLY
    assert report.sync_status == SYNC_SKIPPED
    assert report.sync_restore_completed is False
    assert "sync_restore=not_performed" in rendered
    assert "status=RESTORED\n" not in rendered
    assert not list((tmp_path / "restore").rglob("study-sync.db"))
    assert _fingerprints(protected) == before
    assert PASSWORD not in rendered
    assert LABEL not in rendered


def test_wrong_password_is_redacted(tmp_path: Path, restic_binary: str) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    protected = tmp_path / "protected-destination.txt"
    protected.write_text("keep-protected", encoding="utf-8")
    before = protected.read_bytes()
    good = tmp_path / "good.txt"
    bad = tmp_path / "bad.txt"
    _write_password(good, PASSWORD)
    _write_password(bad, OTHER_PASSWORD)
    client = LocalRestic(restic_binary, str(repo), str(good))
    client.require(["init"])
    opened = client.require(["snapshots", "--json"])
    assert json.loads(opened.stdout or "[]") == []
    wrong = LocalRestic(
        restic_binary,
        str(repo),
        str(bad),
        extra_secrets=(PASSWORD,),
    )
    rejected = wrong.run(["snapshots", "--json"])
    assert rejected.returncode != 0
    combined = f"{rejected.stderr}\n{rejected.stdout}".lower()
    assert "wrong password or no key found" in combined
    assert "does not exist" not in combined
    with pytest.raises(OffboxPocError, match="wrong password or no key found") as caught:
        wrong.require(["snapshots"])
    message = str(caught.value)
    assert PASSWORD not in message
    assert OTHER_PASSWORD not in message
    assert PASSWORD not in rejected.stdout
    assert PASSWORD not in rejected.stderr
    assert OTHER_PASSWORD not in rejected.stdout
    assert OTHER_PASSWORD not in rejected.stderr
    assert protected.read_bytes() == before
    still_open = client.require(["snapshots", "--json"])
    assert json.loads(still_open.stdout or "[]") == []


def test_failed_backup_publishes_no_snapshot(tmp_path: Path, restic_binary: str) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "accounts.db").write_bytes(b"not-uploaded")
    good = tmp_path / "good.txt"
    bad = tmp_path / "bad.txt"
    _write_password(good, PASSWORD)
    _write_password(bad, OTHER_PASSWORD)
    client = LocalRestic(restic_binary, str(repo), str(good))
    client.require(["init"])
    wrong = LocalRestic(
        restic_binary,
        str(repo),
        str(bad),
        extra_secrets=(PASSWORD,),
    )
    with pytest.raises(OffboxPocError, match="failed") as caught:
        backup_inbox(wrong, str(inbox))
    assert PASSWORD not in str(caught.value)
    assert OTHER_PASSWORD not in str(caught.value)
    listed = client.require(["snapshots", "--json"])
    assert json.loads(listed.stdout or "[]") == []


def test_missing_repository_fails(tmp_path: Path, restic_binary: str) -> None:
    password_file = tmp_path / "password.txt"
    _write_password(password_file, PASSWORD)
    client = LocalRestic(restic_binary, str(tmp_path / "missing-repo"), str(password_file))
    with pytest.raises(OffboxPocError, match="failed") as caught:
        client.require(["snapshots"])
    assert PASSWORD not in str(caught.value)


def test_file_repository_is_inaccessible(tmp_path: Path, restic_binary: str) -> None:
    repo = tmp_path / "not-a-directory"
    repo.write_text("blocked", encoding="utf-8")
    password_file = tmp_path / "password.txt"
    _write_password(password_file, PASSWORD)
    client = LocalRestic(restic_binary, str(repo), str(password_file))
    with pytest.raises(OffboxPocError, match="failed") as caught:
        client.require(["init"])
    assert repo.read_text(encoding="utf-8") == "blocked"
    assert PASSWORD not in str(caught.value)


def test_local_password_can_forget_a_snapshot(tmp_path: Path, restic_binary: str) -> None:
    """A local repository password can delete history.

    This is the opposite of append-only storage. It does not demonstrate B2.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "accounts.db").write_bytes(b"disposable")
    password_file = tmp_path / "password.txt"
    _write_password(password_file, PASSWORD)
    client = LocalRestic(restic_binary, str(repo), str(password_file))
    client.require(["init"])
    snapshot = backup_inbox(client, str(inbox))
    forgotten = client.require(["forget", str(snapshot["id"])])
    assert PASSWORD not in forgotten.stdout
    assert PASSWORD not in forgotten.stderr
    listed = client.require(["snapshots", "--json", "--tag", "offbox-poc"])
    assert json.loads(listed.stdout or "[]") == []


def _assert_sync_record(path: Path) -> None:
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        assert integrity is not None and integrity[0] == "ok"
        version = connection.execute(
            "SELECT value FROM sync_meta WHERE key = 'schema_version'"
        ).fetchone()
        assert version is not None and int(version[0]) == 2
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert {"sync_meta", "vocabulary_entities", "vocabulary_changes"} <= tables
        row = connection.execute(
            "SELECT payload_json FROM vocabulary_entities WHERE vocab_id = ?",
            (VOCAB_ID,),
        ).fetchone()
        assert row is not None
        assert json.loads(row[0])["meaning"] == MEANING
    finally:
        connection.close()


def _assert_accounts_marker(path: Path) -> None:
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        assert integrity is not None and integrity[0] == "ok"
        row = connection.execute(
            "SELECT label FROM synthetic_accounts WHERE label = ?",
            (LABEL,),
        ).fetchone()
        assert row is not None and row[0] == LABEL
    finally:
        connection.close()


def test_restore_failure_does_not_report_success(
    tmp_path: Path, restic_binary: str
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "accounts.db").write_bytes(b"disposable")
    good = tmp_path / "good.txt"
    bad = tmp_path / "bad.txt"
    _write_password(good, PASSWORD)
    _write_password(bad, OTHER_PASSWORD)
    client = LocalRestic(restic_binary, str(repo), str(good))
    client.require(["init"])
    snapshot = backup_inbox(client, str(inbox))
    destination = tmp_path / "restore"
    wrong = LocalRestic(
        restic_binary,
        str(repo),
        str(bad),
        extra_secrets=(PASSWORD,),
    )
    with pytest.raises(OffboxPocError, match="failed") as caught:
        restore_snapshot(wrong, str(snapshot["id"]), str(destination))
    assert PASSWORD not in str(caught.value)
    assert OTHER_PASSWORD not in str(caught.value)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, *sys.argv[1:]]))
