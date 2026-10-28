"""Phase 18B.4 — sync backup alerts and unit files (tmp_path only)."""

from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

import sync_alert
import sync_backup
import sync_store
from sync_alert import (
    ALERT_NOT_DELIVERED,
    EVENT_BACKUP_FAILED,
    EVENT_RETENTION_WARNING,
    RecordingSink,
    SyncAlertError,
    dispatch,
    load_sink,
    make_event,
)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy" / "hetzner" / "backup_sync.py"
SERVICE = ROOT / "deploy" / "hetzner" / "language-guard-sync-backup.service"
TIMER = ROOT / "deploy" / "hetzner" / "language-guard-sync-backup.timer"
ACCOUNTS_SERVICE = ROOT / "deploy" / "hetzner" / "language-guard-backup.service"
ACCOUNTS_TIMER = ROOT / "deploy" / "hetzner" / "language-guard-backup.timer"
SETUP = ROOT / "deploy" / "hetzner" / "setup.sh"
VOCAB = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


def _load_cli():
    spec = importlib.util.spec_from_file_location("backup_sync_cli", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _seed(path: Path) -> None:
    connection = sync_store.connect(str(path))
    try:
        sync_store.put_vocabulary(
            connection,
            user_id=1,
            language_code="nl",
            vocab_id=VOCAB,
            payload={"id": VOCAB, "word": "huis", "meaning": "house"},
            expected_revision=0,
            operation_id="op-create",
        )
    finally:
        connection.close()


def _run(source: str, backup_dir: str, sink, capsys):
    module = _load_cli()
    code = module.execute(source, backup_dir, sink)
    captured = capsys.readouterr()
    return code, captured.err


def test_missing_source_creates_nothing_and_does_not_alert(tmp_path, capsys):
    sink = RecordingSink()
    source = tmp_path / "absent.db"
    code, err = _run(str(source), str(tmp_path / "study-sync"), sink, capsys)
    assert code == 0
    assert err == ""
    assert sink.events == []
    assert not source.exists()
    assert list((tmp_path / "study-sync").glob("*")) == []


def test_backup_failure_exits_1_and_records_safe_alert(tmp_path, capsys):
    source = tmp_path / "study_sync.db"
    source.write_bytes(b"not-a-database")
    sink = RecordingSink()
    code, err = _run(str(source), str(tmp_path / "study-sync"), sink, capsys)
    assert code == 1
    assert err == "study_sync backup failed\n"
    assert "not-a-database" not in err
    assert len(sink.events) == 1
    event = sink.events[0]
    assert set(event) == {"event_type", "timestamp", "status"}
    assert event["event_type"] == EVENT_BACKUP_FAILED
    assert event["status"] == "failed"
    assert event["timestamp"].endswith("Z")
    assert list((tmp_path / "study-sync").glob("study-sync-*.db")) == []


def test_retention_warning_keeps_backup_exits_0_and_alerts(tmp_path, monkeypatch, capsys):
    source = tmp_path / "study_sync.db"
    _seed(source)
    backup_dir = tmp_path / "study-sync"
    accounts = tmp_path / "accounts-keep.db"
    accounts.write_bytes(b"accounts")

    def fail_retain(path, keep):
        raise OSError("retention path should not be alerted")

    monkeypatch.setattr(sync_backup, "_retain", fail_retain)
    sink = RecordingSink()
    code, err = _run(str(source), str(backup_dir), sink, capsys)
    assert code == 0
    assert err == "Retention cleanup failed; the new backup was kept.\n"
    assert "retention path" not in err
    published = list(backup_dir.glob("study-sync-*.db"))
    assert len(published) == 1
    assert accounts.read_bytes() == b"accounts"
    assert sink.events[0]["event_type"] == EVENT_RETENTION_WARNING
    assert sink.events[0]["status"] == "warning"
    assert set(sink.events[0]) == {"event_type", "timestamp", "status"}


def test_undelivered_alert_is_exit_2_and_not_recorded(tmp_path, capsys):
    source = tmp_path / "study_sync.db"
    source.write_bytes(b"not-a-database")
    code, err = _run(str(source), str(tmp_path / "study-sync"), None, capsys)
    assert code == 2
    assert err == "study_sync backup failed\nstudy_sync alert was not delivered\n"
    assert ALERT_NOT_DELIVERED in err


def test_retention_warning_without_sink_keeps_file_and_exits_2(tmp_path, monkeypatch, capsys):
    source = tmp_path / "study_sync.db"
    _seed(source)
    monkeypatch.setattr(sync_backup, "_retain", lambda path, keep: (_ for _ in ()).throw(OSError("x")))
    code, err = _run(str(source), str(tmp_path / "study-sync"), None, capsys)
    assert code == 2
    assert err.startswith("Retention cleanup failed; the new backup was kept.\n")
    assert err.endswith("study_sync alert was not delivered\n")
    assert list((tmp_path / "study-sync").glob("study-sync-*.db"))


def test_rejecting_sink_is_not_delivery():
    class Rejecting:
        def emit(self, event):
            raise OSError("down")

    with pytest.raises(SyncAlertError):
        dispatch(make_event(EVENT_BACKUP_FAILED), Rejecting())
    with pytest.raises(SyncAlertError):
        dispatch(make_event(EVENT_BACKUP_FAILED), None)


def test_unknown_sink_name_is_not_echoed(tmp_path, capsys):
    source = tmp_path / "study_sync.db"
    source.write_bytes(b"not-a-database")
    secret = "https://hooks.example/secret-token"
    env = os.environ.copy()
    env["STUDY_SYNC_DB"] = str(source)
    env["STUDY_SYNC_BACKUP_DIR"] = str(tmp_path / "study-sync")
    env["STUDY_SYNC_ALERT_SINK"] = secret
    env.pop("STUDY_SYNC_ENABLED", None)
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert secret not in result.stderr
    assert secret not in result.stdout
    assert result.stderr == (
        "study_sync backup failed\nstudy_sync alert was not delivered\n"
    )


def test_test_sink_records_failure_without_external_call(tmp_path):
    source = tmp_path / "study_sync.db"
    source.write_bytes(b"not-a-database")
    record = tmp_path / "alerts.jsonl"
    env = os.environ.copy()
    env["STUDY_SYNC_DB"] = str(source)
    env["STUDY_SYNC_BACKUP_DIR"] = str(tmp_path / "study-sync")
    env["STUDY_SYNC_ALERT_SINK"] = "test"
    env["STUDY_SYNC_ALERT_RECORD"] = str(record)
    env.pop("STUDY_SYNC_ENABLED", None)
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1, result.stderr
    assert result.stderr == "study_sync backup failed\n"
    payload = json.loads(record.read_text(encoding="utf-8").strip())
    assert set(payload) == {"event_type", "timestamp", "status"}
    assert payload["event_type"] == EVENT_BACKUP_FAILED


def test_import_does_not_enable_sync_or_create_database(tmp_path):
    env = os.environ.copy()
    env.pop("STUDY_SYNC_ENABLED", None)
    env["PYTHONPATH"] = str(ROOT / "app")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    script = (
        "import os\n"
        "from pathlib import Path\n"
        "import sync_alert\n"
        "import sync_backup\n"
        "assert os.environ.get('STUDY_SYNC_ENABLED') != '1'\n"
        "assert list(Path('.').glob('study_sync.db')) == []\n"
        "print('import-ok')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "import-ok" in result.stdout
    assert list(tmp_path.glob("study_sync.db")) == []


def test_dedicated_directory_leaves_account_backups_untouched(tmp_path):
    accounts_dir = tmp_path / "language-guard"
    accounts_dir.mkdir()
    kept = accounts_dir / "accounts-20261028.db"
    kept.write_bytes(b"accounts-backup")
    before_mode = accounts_dir.stat().st_mode
    source = tmp_path / "study_sync.db"
    _seed(source)
    dedicated = accounts_dir / "study-sync"
    published = sync_backup.backup_database(str(source), str(dedicated))
    assert published is not None
    assert published.path.startswith(str(dedicated))
    assert kept.read_bytes() == b"accounts-backup"
    assert accounts_dir.stat().st_mode == before_mode
    assert _load_cli().BACKUP_DIR == "/var/backups/language-guard/study-sync"
    assert _load_cli().SOURCE_DB == "/opt/language-guard/study_sync.db"


def test_sync_units_are_independent_repository_artifacts():
    service = SERVICE.read_text(encoding="utf-8")
    timer = TIMER.read_text(encoding="utf-8")
    accounts_service = ACCOUNTS_SERVICE.read_text(encoding="utf-8")
    accounts_timer = ACCOUNTS_TIMER.read_text(encoding="utf-8")
    setup = SETUP.read_text(encoding="utf-8")
    assert "User=guard" in service
    assert "Group=guard" in service
    assert "Type=oneshot" in service
    assert (
        "ExecStart=/opt/language-guard/venv/bin/python "
        "/opt/language-guard/deploy/hetzner/backup_sync.py"
    ) in service
    assert "STUDY_SYNC_DB=/opt/language-guard/study_sync.db" in service
    assert "STUDY_SYNC_BACKUP_DIR=/var/backups/language-guard/study-sync" in service
    assert "backup_sync.py" in service
    assert "STUDY_SYNC_ENABLED" not in service
    assert "OnFailure=" not in service
    assert "OnCalendar=*-*-* 04:45:00" in timer
    assert "03:15" not in timer
    assert "Persistent=true" in timer
    assert "RandomizedDelaySec=10m" in timer
    assert "OnCalendar=*-*-* 03:15:00" in accounts_timer
    assert "RandomizedDelaySec=20m" in accounts_timer
    assert "backup_accounts.py" in accounts_service
    assert "backup_sync.py" not in accounts_service
    assert "systemctl enable --now language-guard-backup.timer" in setup
    assert "systemctl enable --now language-guard-sync-backup.timer" not in setup
    assert "systemctl enable language-guard-sync-backup.timer" not in setup
    assert "/etc/systemd/system/language-guard-sync-backup.timer" not in setup


def test_unconfigured_sink_and_bad_record_are_not_delivery(tmp_path):
    assert load_sink({}) is None
    with pytest.raises(SyncAlertError):
        load_sink({"STUDY_SYNC_ALERT_SINK": "email"})
    with pytest.raises(SyncAlertError):
        load_sink({"STUDY_SYNC_ALERT_SINK": "test", "STUDY_SYNC_ALERT_RECORD": ""})
    record = tmp_path / "missing" / "alerts.jsonl"
    sink = load_sink(
        {"STUDY_SYNC_ALERT_SINK": "test", "STUDY_SYNC_ALERT_RECORD": str(record)}
    )
    with pytest.raises(SyncAlertError):
        dispatch(make_event(EVENT_RETENTION_WARNING), sink)


def test_backup_dir_occupied_by_file_alerts_without_raw_error(tmp_path, capsys):
    source = tmp_path / "study_sync.db"
    _seed(source)
    occupied = tmp_path / "not-a-directory"
    occupied.write_bytes(b"occupied")
    sink = RecordingSink()
    code, err = _run(str(source), str(occupied), sink, capsys)
    assert code == 1
    assert err == "study_sync backup failed\n"
    assert str(occupied) not in err
    assert "FileExistsError" not in err
    assert "Traceback" not in err
    assert occupied.read_bytes() == b"occupied"
    assert source.is_file()
    assert sink.events[0]["event_type"] == EVENT_BACKUP_FAILED
    assert set(sink.events[0]) == {"event_type", "timestamp", "status"}


def test_backup_dir_occupied_by_file_without_sink_exits_2(tmp_path, capsys):
    source = tmp_path / "study_sync.db"
    _seed(source)
    occupied = tmp_path / "not-a-directory"
    occupied.write_bytes(b"occupied")
    code, err = _run(str(source), str(occupied), None, capsys)
    assert code == 2
    assert err == (
        "study_sync backup failed\nstudy_sync alert was not delivered\n"
    )
    assert str(occupied) not in err
    assert occupied.read_bytes() == b"occupied"


def test_systemd_analyze_accepts_units_when_available(tmp_path):
    analyze = shutil_which("systemd-analyze")
    if analyze is None:
        pytest.skip("systemd-analyze is not available")
    original_service = SERVICE.read_text(encoding="utf-8")
    original_timer = TIMER.read_text(encoding="utf-8")
    assert (
        "ExecStart=/opt/language-guard/venv/bin/python "
        "/opt/language-guard/deploy/hetzner/backup_sync.py"
    ) in original_service
    service_copy = tmp_path / SERVICE.name
    timer_copy = tmp_path / TIMER.name
    executable = sys.executable
    if " " in executable:
        executable = '"' + executable + '"'
    rewritten = []
    for line in original_service.splitlines(keepends=True):
        if line.startswith("ExecStart="):
            rewritten.append("ExecStart=" + executable + "\n")
        else:
            rewritten.append(line if line.endswith("\n") else line + "\n")
    service_copy.write_text("".join(rewritten), encoding="utf-8", newline="\n")
    timer_copy.write_text(original_timer, encoding="utf-8", newline="\n")
    assert "/etc/systemd/system" not in str(service_copy)
    assert "/etc/systemd/system" not in str(timer_copy)
    result = subprocess.run(
        [analyze, "verify", str(service_copy), str(timer_copy)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert SERVICE.read_text(encoding="utf-8") == original_service
    assert TIMER.read_text(encoding="utf-8") == original_timer


def shutil_which(name: str):
    from shutil import which

    return which(name)


def test_corrupt_source_does_not_open_accounts_db(tmp_path):
    accounts = tmp_path / "accounts.db"
    connection = sqlite3.connect(accounts)
    connection.execute("CREATE TABLE users (id INTEGER)")
    connection.commit()
    connection.close()
    source = tmp_path / "bad.db"
    source.write_bytes(b"not-a-database")
    sink = RecordingSink()
    module = _load_cli()
    assert module.execute(str(source), str(tmp_path / "study-sync"), sink) == 1
    check = sqlite3.connect(accounts)
    try:
        assert check.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
    finally:
        check.close()
