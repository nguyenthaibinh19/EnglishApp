"""Phase 18B.2 — study_sync.db backup and restore (tmp_path only)."""

from __future__ import annotations

import os
import sqlite3
import stat
import subprocess
import sys
from pathlib import Path

import pytest

import sync_backup
import sync_store
from sync_backup import SyncBackupError, backup_database, restore_database

VOCAB_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
VOCAB_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
ROOT = Path(__file__).resolve().parents[1]


def _payload(vocab_id: str, meaning: str) -> dict:
    return {"id": vocab_id, "word": "huis", "meaning": meaning}


def _seed(path: Path) -> None:
    connection = sync_store.connect(str(path))
    try:
        sync_store.put_vocabulary(
            connection,
            user_id=1,
            language_code="nl",
            vocab_id=VOCAB_A,
            payload=_payload(VOCAB_A, "house"),
            expected_revision=0,
            operation_id="op-create",
        )
        sync_store.put_vocabulary(
            connection,
            user_id=1,
            language_code="nl",
            vocab_id=VOCAB_A,
            payload=_payload(VOCAB_A, "home"),
            expected_revision=1,
            operation_id="op-update",
        )
        sync_store.delete_vocabulary(
            connection,
            user_id=1,
            language_code="nl",
            vocab_id=VOCAB_A,
            expected_revision=2,
            operation_id="op-delete",
        )
        sync_store.put_vocabulary(
            connection,
            user_id=2,
            language_code="nl",
            vocab_id=VOCAB_A,
            payload=_payload(VOCAB_A, "other"),
            expected_revision=0,
            operation_id="op-other",
        )
        sync_store.put_vocabulary(
            connection,
            user_id=2,
            language_code="de",
            vocab_id=VOCAB_B,
            payload=_payload(VOCAB_B, "book"),
            expected_revision=0,
            operation_id="op-book",
        )
    finally:
        connection.close()


def _changes(path: Path, user_id: int):
    connection = sync_store.connect(str(path))
    try:
        return sync_store.list_vocabulary_changes(connection, user_id=user_id, limit=50)
    finally:
        connection.close()


def test_missing_source_is_not_created(tmp_path):
    source = tmp_path / "missing" / "study_sync.db"
    backup_dir = tmp_path / "backups"
    assert backup_database(str(source), str(backup_dir)) is None
    assert not source.exists()
    assert not backup_dir.exists()


def test_backup_publishes_only_after_integrity_check(tmp_path):
    source = tmp_path / "study_sync.db"
    _seed(source)
    before = source.read_bytes()
    published = backup_database(str(source), str(tmp_path / "backups"))
    assert published is not None
    assert published.retention_warning is None
    assert Path(published.path).name.startswith("study-sync-")
    assert Path(published.path).suffix == ".db"
    assert source.read_bytes() == before
    assert list((tmp_path / "backups").glob("*.partial")) == []
    if os.name != "nt":
        mode = stat.S_IMODE(os.stat(published.path).st_mode)
        assert mode == 0o600


def test_failed_backup_is_not_published(tmp_path, monkeypatch):
    source = tmp_path / "study_sync.db"
    _seed(source)
    before = source.read_bytes()
    monkeypatch.setattr(sync_backup, "_integrity_ok", lambda _connection: False)
    backup_dir = tmp_path / "backups"
    with pytest.raises(SyncBackupError):
        backup_database(str(source), str(backup_dir))
    assert list(backup_dir.glob("study-sync-*.db")) == []
    assert list(backup_dir.glob("*.partial")) == []
    assert source.read_bytes() == before


def test_corrupt_source_does_not_publish_or_delete_original(tmp_path):
    source = tmp_path / "study_sync.db"
    source.write_bytes(b"not a database")
    before = source.read_bytes()
    with pytest.raises(SyncBackupError):
        backup_database(str(source), str(tmp_path / "backups"))
    assert source.read_bytes() == before
    assert list((tmp_path / "backups").glob("study-sync-*.db")) == []


def test_retention_is_scoped_to_sync_prefix(tmp_path):
    source = tmp_path / "study_sync.db"
    _seed(source)
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    accounts_keep = backup_dir / "accounts-20000101-000000.db"
    accounts_keep.write_bytes(b"accounts")
    published = []
    for _ in range(3):
        result = backup_database(str(source), str(backup_dir), keep=2)
        assert result is not None and result.retention_warning is None
        published.append(result.path)
    names = sorted(path.name for path in backup_dir.iterdir())
    sync_names = [name for name in names if name.startswith("study-sync-")]
    assert len(sync_names) == 2
    assert accounts_keep.name in names
    assert all(Path(path).is_file() for path in published[-2:])
    assert not Path(published[0]).exists()


def test_accounts_backup_does_not_remove_sync_backups(tmp_path):
    import importlib.util

    script = ROOT / "deploy" / "hetzner" / "backup_accounts.py"
    spec = importlib.util.spec_from_file_location("backup_accounts", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    source = tmp_path / "accounts.db"
    connection = sqlite3.connect(str(source))
    connection.execute("CREATE TABLE users (id INTEGER PRIMARY KEY)")
    connection.commit()
    connection.close()
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    (backup_dir / "accounts-20000101-000000.db").write_bytes(b"old")
    (backup_dir / "accounts-20000101-000001.db").write_bytes(b"older")
    sync_file = backup_dir / "study-sync-20000101-000000.db"
    sync_file.write_bytes(b"sync")

    assert module.backup_file(str(source), str(backup_dir), keep=2) == 0
    names = {path.name for path in backup_dir.iterdir()}
    assert sync_file.name in names
    assert sum(1 for name in names if name.startswith("accounts-")) == 2
    assert source.is_file()


def test_restore_round_trip_preserves_history_and_retry(tmp_path):
    source = tmp_path / "study_sync.db"
    _seed(source)
    published = backup_database(str(source), str(tmp_path / "backups"))
    assert published is not None
    restored = tmp_path / "restored" / "study_sync.db"
    restore_database(published.path, str(restored))

    probe = sqlite3.connect(str(restored))
    try:
        assert probe.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        probe.close()

    restored_conn = sync_store.connect(str(restored))
    try:
        assert sync_store.schema_version(restored_conn) == sync_store.SCHEMA_VERSION
        owner = sync_store.get_vocabulary(
            restored_conn, user_id=1, language_code="nl", vocab_id=VOCAB_A
        )
        other = sync_store.get_vocabulary(
            restored_conn, user_id=2, language_code="nl", vocab_id=VOCAB_A
        )
        assert owner is not None and owner.deleted is True
        assert owner.revision == 3 and owner.expected_revision == 2
        assert other is not None and other.deleted is False and other.revision == 1
        user_one = _changes(source, 1)
        user_two = _changes(source, 2)
        restored_one = sync_store.list_vocabulary_changes(restored_conn, user_id=1, limit=50)
        restored_two = sync_store.list_vocabulary_changes(restored_conn, user_id=2, limit=50)
        assert [item.cursor for item in restored_one] == [item.cursor for item in user_one]
        assert [item.deleted for item in restored_one] == [False, False, True]
        assert [item.cursor for item in restored_two] == [item.cursor for item in user_two]
        assert all(item.user_id == 2 for item in restored_two)
        before = len(restored_one)
        replay = sync_store.put_vocabulary(
            restored_conn,
            user_id=1,
            language_code="nl",
            vocab_id=VOCAB_A,
            payload=_payload(VOCAB_A, "home"),
            expected_revision=1,
            operation_id="op-update",
        )
        assert replay.revision == 2
        assert replay.deleted is False
        after = sync_store.list_vocabulary_changes(restored_conn, user_id=1, limit=50)
        assert len(after) == before
    finally:
        restored_conn.close()

    with pytest.raises(SyncBackupError):
        restore_database(published.path, str(restored))
    assert restored.is_file()


def test_cli_backup_uses_explicit_paths_and_skips_missing_source(tmp_path):
    script = ROOT / "deploy" / "hetzner" / "backup_sync.py"
    env = os.environ.copy()
    env["STUDY_SYNC_DB"] = str(tmp_path / "absent.db")
    env["STUDY_SYNC_BACKUP_DIR"] = str(tmp_path / "backups")
    env.pop("STUDY_SYNC_ENABLED", None)
    skipped = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert skipped.returncode == 0, skipped.stderr
    assert not (tmp_path / "absent.db").exists()

    source = tmp_path / "study_sync.db"
    _seed(source)
    env["STUDY_SYNC_DB"] = str(source)
    ran = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert ran.returncode == 0, ran.stderr
    assert list((tmp_path / "backups").glob("study-sync-*.db"))
    assert source.is_file()


def test_restore_does_not_overwrite_destination_created_before_publish(tmp_path, monkeypatch):
    source = tmp_path / "study_sync.db"
    _seed(source)
    published = backup_database(str(source), str(tmp_path / "backups"))
    assert published is not None
    destination = tmp_path / "dest.db"
    original_check = sync_backup._integrity_ok

    def plant_destination(connection):
        ok = original_check(connection)
        destination.write_bytes(b"do-not-clobber")
        return ok

    monkeypatch.setattr(sync_backup, "_integrity_ok", plant_destination)
    with pytest.raises(SyncBackupError):
        restore_database(published.path, str(destination))
    assert destination.read_bytes() == b"do-not-clobber"


def test_restore_leaves_dangling_symlink_in_place(tmp_path):
    source = tmp_path / "study_sync.db"
    _seed(source)
    published = backup_database(str(source), str(tmp_path / "backups"))
    assert published is not None
    destination = tmp_path / "dest.db"
    try:
        os.symlink(tmp_path / "missing-target", destination)
    except OSError:
        pytest.skip("symlinks are not available")
    with pytest.raises(SyncBackupError):
        restore_database(published.path, str(destination))
    assert os.path.islink(destination)
    assert not os.path.exists(destination)


def test_restore_partial_is_private_before_sqlite_writes(tmp_path, monkeypatch):
    source = tmp_path / "study_sync.db"
    _seed(source)
    published = backup_database(str(source), str(tmp_path / "backups"))
    assert published is not None
    shared = tmp_path / "shared"
    shared.mkdir()
    if os.name == "posix":
        os.chmod(shared, 0o777)
    opened = []
    real_open = os.open

    def spy_open(path, flags, mode=0o777, *args, **kwargs):
        if str(path).endswith(".partial"):
            opened.append((flags, mode))
        return real_open(path, flags, mode, *args, **kwargs)

    monkeypatch.setattr(os, "open", spy_open)
    real_connect = sqlite3.connect

    def spy_connect(target, *args, **kwargs):
        if isinstance(target, str) and target.endswith(".partial") and os.name == "posix":
            mode = stat.S_IMODE(os.stat(target).st_mode)
            assert mode & 0o077 == 0
        return real_connect(target, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", spy_connect)
    restore_database(published.path, str(shared / "restored.db"))
    assert opened
    flags, mode = opened[0]
    assert flags & os.O_CREAT
    assert flags & os.O_EXCL
    assert mode == 0o600


def test_backup_directory_permission_failure_does_not_publish(tmp_path, monkeypatch):
    source = tmp_path / "study_sync.db"
    _seed(source)
    before = source.read_bytes()
    monkeypatch.setattr(sync_backup, "_posix_permissions", lambda: True)

    def deny_chmod(_path, _mode):
        raise OSError("chmod denied")

    monkeypatch.setattr(os, "chmod", deny_chmod)
    backup_dir = tmp_path / "backups"
    with pytest.raises(SyncBackupError, match="directory permissions"):
        backup_database(str(source), str(backup_dir))
    assert list(backup_dir.glob("study-sync-*.db")) == []
    assert source.read_bytes() == before


def test_retention_failure_keeps_published_backup(tmp_path, monkeypatch):
    source = tmp_path / "study_sync.db"
    _seed(source)
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    accounts = backup_dir / "accounts-20000101-000000.db"
    accounts.write_bytes(b"accounts")
    first = backup_database(str(source), str(backup_dir), keep=5)
    assert first is not None and first.retention_warning is None

    def fail_remove(_path):
        raise OSError("retention blocked")

    monkeypatch.setattr(os, "remove", fail_remove)
    second = backup_database(str(source), str(backup_dir), keep=1)
    assert second is not None
    assert second.retention_warning == "Retention cleanup failed; the new backup was kept."
    assert Path(second.path).is_file()
    assert Path(first.path).is_file()
    assert accounts.read_bytes() == b"accounts"


def test_paths_with_literal_percent_round_trip_read_only(tmp_path):
    folder = tmp_path / "dir%20name"
    folder.mkdir()
    source = folder / "study%20sync.db"
    decoy = folder / "study sync.db"
    _seed(source)
    decoy.write_bytes(b"not-the-source")
    readonly = sqlite3.connect(sync_backup._sqlite_uri(str(source), read_only=True), uri=True)
    try:
        with pytest.raises(sqlite3.OperationalError):
            readonly.execute("CREATE TABLE should_fail(x)")
    finally:
        readonly.close()
    published = backup_database(str(source), str(folder / "backups%20"))
    assert published is not None
    restored = folder / "out%20.db"
    restore_database(published.path, str(restored))
    connection = sync_store.connect(str(restored))
    try:
        record = sync_store.get_vocabulary(
            connection, user_id=1, language_code="nl", vocab_id=VOCAB_A
        )
        assert record is not None and record.deleted is True and record.revision == 3
    finally:
        connection.close()
    assert decoy.read_bytes() == b"not-the-source"
