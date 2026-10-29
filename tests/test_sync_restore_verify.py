"""Phase 18B.5 — restore verification uses temporary files only."""

from __future__ import annotations

import importlib.util
import os
import sqlite3
import stat
import sys
import uuid
from pathlib import Path

import pytest

import sync_backup
import sync_restore_verify
import sync_store
from sync_backup import backup_database
from sync_restore_verify import (
    STATUS_FAILED,
    STATUS_SKIPPED,
    STATUS_VERIFIED,
    verify_latest_backup,
)

VOCAB_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
VOCAB_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
ROOT = Path(__file__).resolve().parents[1]
OLDER = "study-sync-20200101-000000-000000.db"
NEWER = "study-sync-20260101-000000-000001.db"
MIDDLE = "study-sync-20230101-000000-000000.db"


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


def _place(source: Path, backup_dir: Path, name: str) -> Path:
    published = backup_database(str(source), str(backup_dir))
    assert published is not None
    destination = backup_dir / name
    os.replace(published.path, destination)
    return destination


def _layout(tmp_path: Path):
    source = tmp_path / "study_sync.db"
    live = tmp_path / "live" / "study_sync.db"
    backups = tmp_path / "backups"
    verify = tmp_path / "verify"
    backups.mkdir()
    return source, live, backups, verify


def _cli():
    script = ROOT / "deploy" / "hetzner" / "verify_sync_backup.py"
    spec = importlib.util.spec_from_file_location("verify_sync_backup_cli", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_valid_backup_verifies_and_leaves_bytes_unchanged(tmp_path):
    source, live, backups, verify = _layout(tmp_path)
    _seed(source)
    placed = _place(source, backups, NEWER)
    before_source = source.read_bytes()
    before_backup = placed.read_bytes()
    result = verify_latest_backup(str(backups), str(verify), str(live))
    assert result.status == STATUS_VERIFIED
    assert source.read_bytes() == before_source
    assert placed.read_bytes() == before_backup
    assert list(verify.glob("run-*")) == []


def test_revision_tombstone_and_history_survive_restore(tmp_path, monkeypatch):
    source, live, backups, verify = _layout(tmp_path)
    _seed(source)
    _place(source, backups, NEWER)
    kept = {}

    def keep(run_dir, _verify_root):
        kept["run"] = run_dir

    monkeypatch.setattr(sync_restore_verify, "_cleanup_run", keep)
    assert verify_latest_backup(str(backups), str(verify), str(live)).status == STATUS_VERIFIED
    restored = Path(kept["run"]) / "restored.db"
    connection = sqlite3.connect(
        sync_backup._sqlite_uri(str(restored), read_only=True), uri=True
    )
    try:
        owner = connection.execute(
            "SELECT revision, deleted, expected_revision FROM vocabulary_entities "
            "WHERE user_id = 1 AND vocab_id = ?",
            (VOCAB_A,),
        ).fetchone()
        other = connection.execute(
            "SELECT revision, deleted FROM vocabulary_entities WHERE user_id = 2"
        ).fetchall()
        changes = connection.execute(
            "SELECT deleted FROM vocabulary_changes WHERE user_id = 1 ORDER BY change_id"
        ).fetchall()
        assert owner == (3, 1, 2)
        assert (1, 0) in other
        assert [row[0] for row in changes] == [0, 0, 1]
    finally:
        connection.close()


def test_missing_live_and_missing_backup_skips_without_creating_database(tmp_path):
    live = tmp_path / "live" / "study_sync.db"
    backups = tmp_path / "backups"
    verify = tmp_path / "verify"
    result = verify_latest_backup(str(backups), str(verify), str(live))
    assert result.status == STATUS_SKIPPED
    assert not live.exists()
    assert not backups.exists()
    assert not verify.exists()
    assert list(tmp_path.rglob("*.db")) == []


def test_live_without_backup_fails_and_does_not_create_database(tmp_path):
    _source, live, backups, verify = _layout(tmp_path)
    live.parent.mkdir()
    live.write_bytes(b"live-marker")
    result = verify_latest_backup(str(backups), str(verify), str(live))
    assert result.status == STATUS_FAILED
    assert live.read_bytes() == b"live-marker"
    assert list(backups.iterdir()) == []
    assert not verify.exists()


def test_corrupt_newest_does_not_fall_back(tmp_path, monkeypatch):
    source, live, backups, verify = _layout(tmp_path)
    _seed(source)
    older = _place(source, backups, OLDER)
    newer = backups / NEWER
    newer.write_bytes(b"not-a-database")
    older_bytes = older.read_bytes()
    seen = []
    real = sync_backup.restore_database

    def spy(backup_path, destination):
        seen.append(os.path.basename(backup_path))
        return real(backup_path, destination)

    monkeypatch.setattr(sync_backup, "restore_database", spy)
    assert verify_latest_backup(str(backups), str(verify), str(live)).status == STATUS_FAILED
    assert seen == [NEWER]
    assert older.read_bytes() == older_bytes
    assert newer.read_bytes() == b"not-a-database"


def test_future_schema_fails_without_migration(tmp_path, monkeypatch):
    source, live, backups, verify = _layout(tmp_path)
    _seed(source)
    placed = _place(source, backups, NEWER)
    connection = sqlite3.connect(str(placed))
    try:
        connection.execute(
            "UPDATE sync_meta SET value = '3' WHERE key = 'schema_version'"
        )
        connection.commit()
    finally:
        connection.close()

    def refuse_connect(*_args, **_kwargs):
        raise AssertionError("schema init")

    monkeypatch.setattr(sync_store, "connect", refuse_connect)
    assert verify_latest_backup(str(backups), str(verify), str(live)).status == STATUS_FAILED
    probe = sqlite3.connect(
        sync_backup._sqlite_uri(str(placed), read_only=True), uri=True
    )
    try:
        version = probe.execute(
            "SELECT value FROM sync_meta WHERE key = 'schema_version'"
        ).fetchone()[0]
    finally:
        probe.close()
    assert version == "3"


def test_missing_required_column_fails(tmp_path):
    _source, live, backups, verify = _layout(tmp_path)
    path = backups / NEWER
    connection = sqlite3.connect(str(path))
    try:
        connection.execute(
            "CREATE TABLE sync_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO sync_meta (key, value) VALUES ('schema_version', '2')"
        )
        connection.execute(
            """
            CREATE TABLE vocabulary_entities (
                user_id INTEGER NOT NULL,
                language_code TEXT NOT NULL,
                vocab_id TEXT NOT NULL,
                revision INTEGER NOT NULL,
                deleted INTEGER NOT NULL,
                payload_json TEXT,
                change_cursor INTEGER NOT NULL,
                operation_id TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE vocabulary_changes (
                change_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                language_code TEXT NOT NULL,
                vocab_id TEXT NOT NULL,
                revision INTEGER NOT NULL,
                deleted INTEGER NOT NULL,
                payload_json TEXT,
                operation_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expected_revision INTEGER NOT NULL
            )
            """
        )
        connection.commit()
    finally:
        connection.close()
    assert verify_latest_backup(str(backups), str(verify), str(live)).status == STATUS_FAILED


def test_missing_required_table_fails(tmp_path):
    source, live, backups, verify = _layout(tmp_path)
    _seed(source)
    placed = _place(source, backups, NEWER)
    connection = sqlite3.connect(str(placed))
    try:
        connection.execute("DROP TABLE vocabulary_changes")
        connection.commit()
    finally:
        connection.close()
    assert verify_latest_backup(str(backups), str(verify), str(live)).status == STATUS_FAILED


def test_existing_destination_and_unsafe_roots_are_refused(tmp_path, monkeypatch):
    source, live, backups, verify = _layout(tmp_path)
    _seed(source)
    placed = _place(source, backups, NEWER)
    before = placed.read_bytes()
    accounts = tmp_path / "accounts.db"
    accounts.write_bytes(b"accounts")

    original = sync_restore_verify._allocate_run_dir

    def plant(root):
        path = original(root)
        (Path(path) / "restored.db").write_bytes(b"occupied")
        return path

    monkeypatch.setattr(sync_restore_verify, "_allocate_run_dir", plant)
    assert verify_latest_backup(str(backups), str(verify), str(live)).status == STATUS_FAILED
    monkeypatch.undo()
    assert verify_latest_backup(str(backups), str(backups), str(live)).status == STATUS_FAILED
    assert verify_latest_backup(
        str(backups), "/opt/language-guard/verify", str(live)
    ).status == STATUS_FAILED
    assert verify_latest_backup(
        str(backups), str(tmp_path / "accounts.db"), str(live)
    ).status == STATUS_FAILED
    assert placed.read_bytes() == before
    assert accounts.read_bytes() == b"accounts"


def test_symlink_backup_and_verify_root_fail(tmp_path, monkeypatch):
    source, live, backups, verify = _layout(tmp_path)
    _seed(source)
    older = _place(source, backups, OLDER)
    newer = backups / NEWER
    try:
        os.symlink(older, newer)
    except OSError:
        pytest.skip("symlinks are not available")
    seen = []
    monkeypatch.setattr(
        sync_backup,
        "restore_database",
        lambda backup_path, destination: seen.append(backup_path),
    )
    assert verify_latest_backup(str(backups), str(verify), str(live)).status == STATUS_FAILED
    assert seen == []
    linked_root = tmp_path / "linked-verify"
    os.symlink(verify, linked_root)
    assert verify_latest_backup(str(backups), str(linked_root), str(live)).status == STATUS_FAILED


def test_destination_outside_verify_root_is_refused(tmp_path, monkeypatch):
    source, live, backups, verify = _layout(tmp_path)
    _seed(source)
    placed = _place(source, backups, NEWER)
    before = placed.read_bytes()
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.setattr(
        sync_restore_verify, "_allocate_run_dir", lambda _root: str(outside)
    )
    assert verify_latest_backup(str(backups), str(verify), str(live)).status == STATUS_FAILED
    assert not (outside / "restored.db").exists()
    assert placed.read_bytes() == before
    assert outside.is_dir()


def test_backup_path_that_is_a_file_fails(tmp_path):
    _source, live, _backups, verify = _layout(tmp_path)
    file_path = tmp_path / "not-a-directory"
    file_path.write_bytes(b"x")
    assert verify_latest_backup(str(file_path), str(verify), str(live)).status == STATUS_FAILED
    assert file_path.read_bytes() == b"x"


def test_directory_permission_and_restored_mode_fail(tmp_path, monkeypatch):
    source, live, backups, verify = _layout(tmp_path)
    _seed(source)
    placed = _place(source, backups, NEWER)
    before = placed.read_bytes()
    monkeypatch.setattr(sync_restore_verify, "_posix_permissions", lambda: True)

    def deny_chmod(_path, _mode):
        raise OSError("chmod denied")

    monkeypatch.setattr(os, "chmod", deny_chmod)
    assert verify_latest_backup(str(backups), str(verify), str(live)).status == STATUS_FAILED
    assert placed.read_bytes() == before
    monkeypatch.undo()

    monkeypatch.setattr(sync_restore_verify, "_posix_permissions", lambda: True)
    monkeypatch.setattr(sync_restore_verify, "_enforce_private_directory", lambda _path: None)
    real_stat = os.stat

    def loose_restored(path, *args, **kwargs):
        if os.path.basename(path) == "restored.db":
            return os.stat_result((0o644,) + (0,) * 9)
        return real_stat(path, *args, **kwargs)

    monkeypatch.setattr(os, "stat", loose_restored)
    assert verify_latest_backup(str(backups), str(verify), str(live)).status == STATUS_FAILED


def test_restore_integrity_and_cleanup_errors(tmp_path, monkeypatch):
    source, live, backups, verify = _layout(tmp_path)
    _seed(source)
    placed = _place(source, backups, NEWER)
    before = placed.read_bytes()
    unrelated = verify
    unrelated.mkdir()
    (unrelated / "keep.txt").write_text("keep", encoding="utf-8")

    def boom(*_args, **_kwargs):
        raise sync_backup.SyncBackupError("restore failed")

    monkeypatch.setattr(sync_backup, "restore_database", boom)
    assert verify_latest_backup(str(backups), str(verify), str(live)).status == STATUS_FAILED
    monkeypatch.undo()

    monkeypatch.setattr(sync_restore_verify, "_integrity_ok", lambda _connection: False)
    assert verify_latest_backup(str(backups), str(verify), str(live)).status == STATUS_FAILED
    monkeypatch.undo()

    def cleanup_fails(_run_dir, _verify_root):
        raise OSError("cleanup blocked")

    monkeypatch.setattr(sync_restore_verify, "_cleanup_run", cleanup_fails)
    assert verify_latest_backup(str(backups), str(verify), str(live)).status == STATUS_FAILED
    assert placed.read_bytes() == before
    assert (verify / "keep.txt").read_text(encoding="utf-8") == "keep"


def test_newest_of_several_candidates_is_selected(tmp_path, monkeypatch):
    source, live, backups, verify = _layout(tmp_path)
    _seed(source)
    _place(source, backups, OLDER)
    _place(source, backups, MIDDLE)
    _place(source, backups, NEWER)
    (backups / "accounts-20260101-000000.db").write_bytes(b"accounts")
    (backups / "study-sync-notes.db").write_bytes(b"ignore")
    seen = []
    real = sync_backup.restore_database

    def spy(backup_path, destination):
        seen.append(os.path.basename(backup_path))
        return real(backup_path, destination)

    monkeypatch.setattr(sync_backup, "restore_database", spy)
    assert verify_latest_backup(str(backups), str(verify), str(live)).status == STATUS_VERIFIED
    assert seen == [NEWER]


def test_cleanup_leaves_unrelated_files(tmp_path):
    source, live, backups, verify = _layout(tmp_path)
    _seed(source)
    _place(source, backups, NEWER)
    verify.mkdir()
    kept = verify / "keep.txt"
    kept.write_text("keep", encoding="utf-8")
    assert verify_latest_backup(str(backups), str(verify), str(live)).status == STATUS_VERIFIED
    assert kept.read_text(encoding="utf-8") == "keep"
    assert list(verify.glob("run-*")) == []


def test_accounts_and_production_databases_are_not_mutated(tmp_path):
    source, live, backups, verify = _layout(tmp_path)
    _seed(source)
    _place(source, backups, NEWER)
    accounts = tmp_path / "accounts.db"
    accounts.write_bytes(b"do-not-touch")
    calls = []
    real = sqlite3.connect

    def spy(path, *args, **kwargs):
        calls.append(str(path))
        return real(path, *args, **kwargs)

    # The verifier's read-only open and restore both use sqlite3.connect.
    # accounts.db must not be among them. Patch after the seed and backup.
    import sync_restore_verify as target

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(sqlite3, "connect", spy)
    try:
        assert target.verify_latest_backup(str(backups), str(verify), str(live)).status == (
            STATUS_VERIFIED
        )
    finally:
        monkeypatch.undo()
    assert accounts.read_bytes() == b"do-not-touch"
    assert all("accounts.db" not in call for call in calls)


def test_second_run_uses_a_new_directory(tmp_path, monkeypatch):
    source, live, backups, verify = _layout(tmp_path)
    _seed(source)
    _place(source, backups, NEWER)
    assert verify_latest_backup(str(backups), str(verify), str(live)).status == STATUS_VERIFIED
    assert verify_latest_backup(str(backups), str(verify), str(live)).status == STATUS_VERIFIED

    monkeypatch.setattr(
        sync_restore_verify.uuid,
        "uuid4",
        lambda: uuid.UUID("00000000-0000-4000-8000-000000000001"),
    )
    monkeypatch.setattr(sync_restore_verify, "_cleanup_run", lambda *_args: None)
    assert verify_latest_backup(str(backups), str(verify), str(live)).status == STATUS_VERIFIED
    restored = verify / "run-00000000000040008000000000000001" / "restored.db"
    assert restored.is_file()
    marker = restored.read_bytes()
    assert verify_latest_backup(str(backups), str(verify), str(live)).status == STATUS_FAILED
    assert restored.read_bytes() == marker


def test_verifier_needs_no_network_flag_or_credentials(tmp_path):
    source = (ROOT / "app" / "sync_restore_verify.py").read_text(encoding="utf-8")
    assert "STUDY_SYNC_ENABLED" not in source
    assert "urllib" not in source
    assert "requests" not in source
    assert "socket" not in source
    assert sync_store.SCHEMA_VERSION == sync_restore_verify.SUPPORTED_SCHEMA_VERSION
    setup = (ROOT / "deploy" / "hetzner" / "setup.sh").read_text(encoding="utf-8")
    assert "verify_sync_backup.py" in setup
    assert "systemctl enable --now language-guard-sync-backup.timer" not in setup
    assert "language-guard-sync-verify" not in setup
    _source, live, backups, verify = _layout(tmp_path)
    _seed(_source)
    _place(_source, backups, NEWER)
    env = os.environ.copy()
    env.pop("STUDY_SYNC_ENABLED", None)
    env["STUDY_SYNC_DB"] = str(live)
    env["STUDY_SYNC_BACKUP_DIR"] = str(backups)
    env["STUDY_SYNC_VERIFY_DIR"] = str(verify)
    completed = __import__("subprocess").run(
        [sys.executable, str(ROOT / "deploy" / "hetzner" / "verify_sync_backup.py")],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    assert completed.stdout == "study_sync restore verification verified\n"
    assert completed.stderr == ""
    assert "STUDY_SYNC_ENABLED" not in env or env.get("STUDY_SYNC_ENABLED") != "1"


def test_cli_distinguishes_skip_and_failure(tmp_path, capsys):
    cli = _cli()
    live = tmp_path / "missing.db"
    backups = tmp_path / "backups"
    verify = tmp_path / "verify"
    assert cli.execute(str(backups), str(verify), str(live)) == 0
    skipped = capsys.readouterr()
    assert skipped.out == cli.LINE_SKIPPED + "\n"
    assert skipped.err == ""
    live.parent.mkdir(exist_ok=True)
    live.write_bytes(b"present")
    backups.mkdir()
    assert cli.execute(str(backups), str(verify), str(live)) == 1
    failed = capsys.readouterr()
    assert failed.out == ""
    assert failed.err == cli.LINE_FAILED + "\n"
    assert live.read_bytes() == b"present"


def test_protected_verification_root_is_rejected_before_side_effects(tmp_path, monkeypatch):
    source, live, backups, verify = _layout(tmp_path)
    _seed(source)
    _place(source, backups, NEWER)
    protected = tmp_path / "protected"
    protected.mkdir()
    marker = protected / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    if os.name == "posix":
        os.chmod(protected, 0o755)
    before_mode = stat.S_IMODE(os.stat(protected).st_mode)
    before_names = sorted(path.name for path in protected.iterdir())
    monkeypatch.setattr(sync_restore_verify, "_PRODUCTION_ROOT", str(protected))

    assert verify_latest_backup(str(backups), str(protected), str(live)).status == STATUS_FAILED
    assert marker.read_text(encoding="utf-8") == "keep"
    assert sorted(path.name for path in protected.iterdir()) == before_names
    assert stat.S_IMODE(os.stat(protected).st_mode) == before_mode
    assert verify_latest_backup(str(backups), str(verify), str(live)).status == STATUS_VERIFIED


def test_symlinked_ancestor_does_not_enter_protected_directory(tmp_path, monkeypatch):
    source, live, backups, _verify = _layout(tmp_path)
    _seed(source)
    _place(source, backups, NEWER)
    protected = tmp_path / "protected"
    protected.mkdir()
    marker = protected / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    before_mode = stat.S_IMODE(os.stat(protected).st_mode)
    before_names = sorted(path.name for path in protected.iterdir())
    monkeypatch.setattr(sync_restore_verify, "_PRODUCTION_ROOT", str(protected))
    alias = tmp_path / "alias"
    nested = alias / "nested-verify"
    try:
        os.symlink(protected, alias, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks are not available")
    assert verify_latest_backup(str(backups), str(nested), str(live)).status == STATUS_FAILED
    assert marker.read_text(encoding="utf-8") == "keep"
    assert not nested.exists()
    assert sorted(path.name for path in protected.iterdir()) == before_names
    assert stat.S_IMODE(os.stat(protected).st_mode) == before_mode


def test_invalid_live_path_without_backup_fails_closed(tmp_path):
    backups = tmp_path / "no-backups"
    verify = tmp_path / "verify"
    live_dir = tmp_path / "live-dir"
    live_dir.mkdir()
    (live_dir / "marker.txt").write_text("keep", encoding="utf-8")
    calls = []
    real_connect = sqlite3.connect

    def spy(path, *args, **kwargs):
        calls.append(str(path))
        return real_connect(path, *args, **kwargs)

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(sqlite3, "connect", spy)
    try:
        assert (
            verify_latest_backup(str(backups), str(verify), str(live_dir)).status
            == STATUS_FAILED
        )
    finally:
        monkeypatch.undo()
    assert calls == []
    assert (live_dir / "marker.txt").read_text(encoding="utf-8") == "keep"
    assert not verify.exists()
    assert not backups.exists()


def test_symlink_live_path_without_backup_fails_closed(tmp_path):
    backups = tmp_path / "no-backups"
    verify = tmp_path / "verify"
    target = tmp_path / "target"
    target.mkdir()
    (target / "marker.txt").write_text("keep", encoding="utf-8")
    live_link = tmp_path / "live-link"
    try:
        os.symlink(target, live_link, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks are not available")
    assert (
        verify_latest_backup(str(backups), str(verify), str(live_link)).status
        == STATUS_FAILED
    )
    assert (target / "marker.txt").read_text(encoding="utf-8") == "keep"
    assert list(target.glob("*.db")) == []


def test_backup_names_require_real_ascii_timestamps(tmp_path, monkeypatch):
    source, live, backups, verify = _layout(tmp_path)
    _seed(source)
    valid = "study-sync-20200101-010203-000001.db"
    _place(source, backups, valid)
    rejected = (
        "study-sync-20261301-000000-000000.db",
        "study-sync-20200231-000000-000000.db",
        "study-sync-20200101-240000-000000.db",
        "study-sync-20200101-016000-000000.db",
        "study-sync-20200101-010260-000000.db",
        "study-sync-\uff12\uff10\uff12\uff16\uff10\uff11\uff10\uff11-000000-000000.db",
        "study-sync-20200101-010204-00000.db",
    )
    for name in rejected:
        (backups / name).write_bytes(b"not-a-candidate")
    seen = []
    real = sync_backup.restore_database

    def spy(backup_path, destination):
        seen.append(os.path.basename(backup_path))
        return real(backup_path, destination)

    monkeypatch.setattr(sync_backup, "restore_database", spy)
    assert verify_latest_backup(str(backups), str(verify), str(live)).status == STATUS_VERIFIED
    assert seen == [valid]
