"""Phase 18B.8 health monitor. Temporary paths only. No production services."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import health_monitor
import health_notify
from health_monitor import (
    FAILED,
    HEALTH_MESSAGE,
    NOT_INSTALLED,
    SKIPPED,
    UNKNOWN,
    VERIFIED,
    WARNING,
    HealthConfig,
    amsterdam_date,
    run_health,
)
from health_notify import PROVIDER_ACCEPTED, PROVIDER_REJECTED, NOT_SENT, HttpResponse

ROOT = Path(__file__).resolve().parents[1]
HETZNER = ROOT / "deploy" / "hetzner"
NOW = datetime(2026, 11, 3, 8, 0, tzinfo=timezone.utc)


class Sink:
    def __init__(self, status=200, body="ok"):
        self.status = status
        self.body = body
        self.texts = []

    def __call__(self, text):
        self.texts.append(text)
        return HttpResponse(self.status, self.body, 0.0)


def _quiet_sleep(_seconds):
    return None


def _db(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE sample (id INTEGER)")
    connection.commit()
    connection.close()


def _config(tmp_path: Path, **overrides) -> HealthConfig:
    systemd = tmp_path / "systemd"
    systemd.mkdir(parents=True)
    (systemd / "language-guard-sync-backup.timer").write_text("template\n", encoding="utf-8")
    (systemd / "language-guard-sync-verify.timer").write_text("template\n", encoding="utf-8")
    backup = tmp_path / "accounts-backups"
    backup.mkdir(parents=True)
    snapshot = backup / "accounts-20261103-031500.db"
    _db(snapshot)
    stamp = (NOW - timedelta(hours=2)).timestamp()
    os.utime(snapshot, (stamp, stamp))
    values = dict(
        state_path=str(tmp_path / "state.json"),
        witness_path=str(tmp_path / "witness"),
        accounts_backup_dir=str(backup),
        accounts_live_db=str(tmp_path / "live-accounts.db"),
        sync_live_db=str(tmp_path / "study_sync.db"),
        sync_backup_dir=str(tmp_path / "study-sync"),
        systemd_dir=str(systemd),
        verify_result_path=str(tmp_path / "verify-result.json"),
        now=NOW,
    )
    values.update(overrides)
    return HealthConfig(**values)


def _probes(**overrides):
    values = {
        "service": "active",
        "public_health": HEALTH_MESSAGE,
        "disk": (100, 10),
        "flags": [{"name": "env", "readable": True, "value": ""}],
    }
    values.update(overrides)
    return values


def _run(config, probes, senders, mode="report", **kwargs):
    return run_health(
        mode,
        config,
        probes,
        senders,
        sleep=_quiet_sleep,
        monotonic=lambda: 0.0,
        **kwargs,
    )


def test_daily_report_marks_sync_skip_and_does_not_call_it_success(tmp_path):
    config = _config(tmp_path)
    health_monitor.note_sync_verify_result(
        config.verify_result_path,
        SKIPPED,
        checked_at="2026-11-03T08:00:00Z",
    )
    telegram = Sink()
    email = Sink()
    result = _run(config, _probes(), {"telegram": telegram, "email": email})
    assert result.overall == "OK"
    assert result.text.startswith("OK — sync backup SKIPPED, no study_sync.db yet")
    assert "successful" not in result.text
    assert len(telegram.texts) == 1
    assert len(email.texts) == 1
    assert result.deliveries == {"telegram": PROVIDER_ACCEPTED, "email": PROVIDER_ACCEPTED}
    assert not Path(config.sync_live_db).exists()


def test_second_report_on_the_same_civil_date_does_not_send_again(tmp_path):
    config = _config(tmp_path)
    telegram = Sink()
    email = Sink()
    senders = {"telegram": telegram, "email": email}
    probes = _probes()
    _run(config, probes, senders)
    _run(config, probes, senders)
    assert len(telegram.texts) == 1
    assert len(email.texts) == 1


def test_concurrent_report_sends_one_message_per_channel(tmp_path):
    config = _config(tmp_path)
    telegram = Sink()
    email = Sink()
    barrier = threading.Barrier(2)
    results = []

    def worker():
        barrier.wait()
        results.append(_run(config, _probes(), {"telegram": telegram, "email": email}))

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(telegram.texts) == 1
    assert len(email.texts) == 1
    assert sum(len(item.deliveries) for item in results) == 2


def test_catch_up_sends_the_current_civil_date_once(tmp_path):
    config = _config(tmp_path)
    telegram = Sink()
    later = HealthConfig(**{**config.__dict__, "now": NOW + timedelta(days=2)})
    _run(later, _probes(), {"telegram": telegram, "email": Sink()})
    assert len(telegram.texts) == 1
    assert amsterdam_date(later.now) in json.loads(Path(config.state_path).read_text(encoding="utf-8"))["last_report_date"]


def test_dst_report_hour_is_unique_and_the_overlap_hour_is_not():
    zone = health_monitor.AMSTERDAM
    autumn = datetime(2026, 10, 25, 9, 0, tzinfo=zone)
    autumn_fold = datetime(2026, 10, 25, 9, 0, fold=1, tzinfo=zone)
    assert autumn.timestamp() == autumn_fold.timestamp()
    overlap = datetime(2026, 10, 25, 2, 30, tzinfo=zone)
    overlap_fold = datetime(2026, 10, 25, 2, 30, fold=1, tzinfo=zone)
    assert overlap.timestamp() != overlap_fold.timestamp()
    spring = datetime(2026, 3, 29, 9, 0, tzinfo=zone)
    assert spring.utcoffset() == timedelta(hours=2)
    assert autumn.utcoffset() == timedelta(hours=1)


def test_backup_failure_keeps_adr_exit_and_records_notice(tmp_path, monkeypatch, capsys):
    import importlib.util

    script = HETZNER / "backup_sync.py"
    spec = importlib.util.spec_from_file_location("backup_sync_cli_health", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    state = tmp_path / "state.json"
    monkeypatch.setenv("HEALTH_STATE_PATH", str(state))
    source = tmp_path / "study_sync.db"
    source.write_bytes(b"not-a-database")
    occupied = tmp_path / "occupied"
    occupied.write_bytes(b"x")

    class Sink:
        def emit(self, event):
            return None

    code = module.execute(str(source), str(occupied), Sink())
    captured = capsys.readouterr()
    assert code == 1
    assert captured.err == "study_sync backup failed\n"
    assert json.loads(state.read_text(encoding="utf-8"))["sync_backup_notice"] == "failed"


def test_retention_warning_is_visible_and_exit_stays_zero(tmp_path, monkeypatch, capsys):
    import importlib.util
    import sync_backup

    script = HETZNER / "backup_sync.py"
    spec = importlib.util.spec_from_file_location("backup_sync_cli_retention", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    state = tmp_path / "state.json"
    monkeypatch.setenv("HEALTH_STATE_PATH", str(state))
    monkeypatch.setattr(sync_backup, "_retain", lambda path, keep: (_ for _ in ()).throw(OSError("hidden")))
    source = tmp_path / "study_sync.db"
    connection = sqlite3.connect(source)
    connection.execute("CREATE TABLE sample (id INTEGER)")
    connection.commit()
    connection.close()

    class Sink:
        def emit(self, event):
            return None

    code = module.execute(str(source), str(tmp_path / "study-sync"), Sink())
    captured = capsys.readouterr()
    assert code == 0
    assert captured.err == "Retention cleanup failed; the new backup was kept.\n"
    assert "hidden" not in captured.err
    notice = json.loads(state.read_text(encoding="utf-8"))["sync_backup_notice"]
    assert notice == "retention_warning"
    config = _config(tmp_path, state_path=str(state), sync_live_db=str(source))
    result = _run(config, _probes(), {"telegram": Sink(), "email": Sink()}, mode="check")
    assert result.checks[[item.name for item in result.checks].index("sync_backup")].status == WARNING


def test_missing_and_stale_account_backups(tmp_path):
    empty = _config(tmp_path)
    for name in Path(empty.accounts_backup_dir).glob("accounts-*.db"):
        name.unlink()
    missing = _run(empty, _probes(), {"telegram": Sink(), "email": Sink()}, mode="check")
    assert any(item.status == FAILED and item.detail == "missing" for item in missing.checks)
    stale = _config(tmp_path / "stale")
    snapshot = next(Path(stale.accounts_backup_dir).glob("accounts-*.db"))
    old = (NOW - timedelta(hours=49)).timestamp()
    os.utime(snapshot, (old, old))
    result = _run(stale, _probes(), {"telegram": Sink(), "email": Sink()}, mode="check")
    age = next(item for item in result.checks if item.name == "accounts_backup_age")
    assert age.status == FAILED


def test_replaced_snapshot_is_checked_again(tmp_path, monkeypatch):
    config = _config(tmp_path)
    calls = []
    real = health_monitor.snapshot_integrity

    def wrapped(path, live):
        calls.append(path)
        assert os.path.abspath(path) != os.path.abspath(config.accounts_live_db)
        return real(path, live)

    monkeypatch.setattr(health_monitor, "snapshot_integrity", wrapped)
    senders = {"telegram": Sink(), "email": Sink()}
    _run(config, _probes(), senders, mode="check")
    _run(config, _probes(), senders, mode="check")
    assert len(calls) == 1
    snapshot = Path(calls[0])
    snapshot.write_bytes(snapshot.read_bytes() + b" ")
    future = (NOW + timedelta(minutes=5)).timestamp()
    os.utime(snapshot, (future, future))
    _run(config, _probes(), senders, mode="check")
    assert len(calls) == 2


def test_disappeared_database_stays_failed_while_an_old_backup_exists(tmp_path):
    config = _config(tmp_path)
    Path(config.sync_live_db).write_bytes(b"db")
    _run(config, _probes(), {"telegram": Sink(), "email": Sink()}, mode="check")
    assert Path(config.witness_path).is_file()
    Path(config.sync_live_db).unlink()
    backup_dir = Path(config.sync_backup_dir)
    backup_dir.mkdir()
    old = backup_dir / "study-sync-20200101-000000.db"
    old.write_bytes(b"old")
    result = _run(config, _probes(), {"telegram": Sink(), "email": Sink()}, mode="check")
    assert next(item for item in result.checks if item.name == "sync_backup").status == FAILED
    assert "disappeared" in result.text
    assert "successful" not in result.text


def test_create_and_delete_between_checks_is_not_witnessed(tmp_path):
    config = _config(tmp_path)
    _run(config, _probes(), {"telegram": Sink(), "email": Sink()}, mode="check")
    assert not Path(config.witness_path).exists()
    Path(config.sync_live_db).write_bytes(b"brief")
    Path(config.sync_live_db).unlink()
    result = _run(config, _probes(), {"telegram": Sink(), "email": Sink()}, mode="check")
    assert next(item for item in result.checks if item.name == "sync_database").status == SKIPPED
    assert not Path(config.witness_path).exists()


def test_sync_off_without_database_is_skipped_not_installed_or_unknown(tmp_path):
    config = _config(tmp_path)
    result = _run(config, _probes(), {"telegram": Sink(), "email": Sink()})
    by_name = {item.name: item.status for item in result.checks}
    assert by_name["sync_flag"] == VERIFIED
    assert by_name["sync_database"] == SKIPPED
    assert by_name["sync_backup"] == SKIPPED
    assert by_name["sync_verify"] == UNKNOWN
    assert result.overall != "OK"
    health_monitor.note_sync_verify_result(
        config.verify_result_path,
        SKIPPED,
        checked_at="2026-11-03T08:00:00Z",
    )
    recorded = _run(config, _probes(), {"telegram": Sink(), "email": Sink()})
    verify = next(item for item in recorded.checks if item.name == "sync_verify")
    assert verify.status == SKIPPED
    assert verify.detail == "recorded-skip"
    assert recorded.overall == "OK"
    assert "successful" not in recorded.text
    bare = _config(tmp_path / "bare", systemd_dir=str(tmp_path / "empty-systemd"))
    (tmp_path / "empty-systemd").mkdir()
    hidden = _run(bare, _probes(), {"telegram": Sink(), "email": Sink()})
    assert next(item for item in hidden.checks if item.name == "sync_backup").status == NOT_INSTALLED
    assert hidden.overall != "OK"
    unknown = _run(config, _probes(flags=[{"readable": False, "value": ""}]), {"telegram": Sink(), "email": Sink()})
    assert next(item for item in unknown.checks if item.name == "sync_flag").status == UNKNOWN
    assert unknown.overall != "OK"


def test_one_channel_failure_is_retried_and_then_recovers(tmp_path):
    config = _config(tmp_path)
    telegram = Sink()
    email = Sink(status=400, body="later")
    senders = {"telegram": telegram, "email": email}
    first = _run(config, _probes(), senders, mode="check")
    assert first.deliveries["email"] == PROVIDER_REJECTED
    assert first.deliveries["telegram"] == PROVIDER_ACCEPTED
    email.status = 200
    second = _run(config, _probes(), senders, mode="check")
    assert second.deliveries == {"email": PROVIDER_ACCEPTED}
    assert len(telegram.texts) == 1
    assert len(email.texts) == 2


def test_both_channels_failing_withholds_the_heartbeat(tmp_path):
    config = _config(tmp_path)
    pings = []
    result = _run(
        config,
        _probes(),
        {"telegram": Sink(status=503), "email": Sink(status=503)},
        heartbeat=lambda: pings.append("ping") or True,
    )
    assert result.deliveries["telegram"] == PROVIDER_REJECTED
    assert result.deliveries["email"] == PROVIDER_REJECTED
    assert result.heartbeat == "withheld"
    assert pings == []


def test_accepted_channel_pings_and_is_not_called_user_delivery(tmp_path):
    config = _config(tmp_path)
    result = _run(
        config,
        _probes(),
        {"telegram": Sink(), "email": Sink()},
        heartbeat=lambda: True,
    )
    assert result.heartbeat == "ping-accepted"
    assert "received" not in result.text
    assert PROVIDER_ACCEPTED not in result.text


def test_missing_credentials_are_not_acceptance(tmp_path):
    config = _config(tmp_path)
    secret = "bot-token-should-not-leak"
    result = _run(config, _probes(), {"telegram": None, "email": None}, secrets=[secret])
    assert result.deliveries["telegram"] == NOT_SENT
    assert result.deliveries["email"] == NOT_SENT
    assert secret not in "\n".join(result.logs)
    assert result.heartbeat == "withheld"


def test_provider_error_body_is_redacted():
    secret = "super-secret-token"
    clock = {"now": 0.0}

    def post(_text):
        raise RuntimeError(secret)

    result = health_notify.deliver(
        "telegram",
        post,
        "hello",
        secrets=[secret],
        sleep=_quiet_sleep,
        monotonic=lambda: clock["now"],
    )
    assert result.result == PROVIDER_REJECTED
    assert secret not in result.log
    assert health_notify.REDACTED in result.log


def test_retry_stops_after_three_attempts():
    calls = []

    def post(_text):
        calls.append(1)
        return HttpResponse(503, "down", 0.0)

    result = health_notify.deliver(
        "email",
        post,
        "hello",
        secrets=[],
        sleep=_quiet_sleep,
        monotonic=lambda: 0.0,
    )
    assert result.attempts == 3
    assert len(calls) == 3
    assert result.result == PROVIDER_REJECTED


def test_service_recovery_is_reported_once(tmp_path):
    config = _config(tmp_path)
    telegram = Sink()
    senders = {"telegram": telegram, "email": Sink()}
    _run(config, _probes(service="failed"), senders, mode="check")
    recovered = _run(config, _probes(service="active"), senders, mode="check")
    assert "recovery:" in recovered.text
    quiet = _run(config, _probes(service="active"), senders, mode="check")
    assert quiet.deliveries == {}


def test_rpo_check_stays_inactive_until_configured(tmp_path):
    config = _config(tmp_path)
    Path(config.sync_live_db).write_bytes(b"db")
    backup_dir = Path(config.sync_backup_dir)
    backup_dir.mkdir()
    backup = backup_dir / "study-sync-20200101-000000.db"
    backup.write_bytes(b"backup")
    old = (NOW - timedelta(days=30)).timestamp()
    os.utime(backup, (old, old))
    inactive = _run(config, _probes(), {"telegram": Sink(), "email": Sink()}, mode="check")
    assert next(item for item in inactive.checks if item.name == "sync_backup").detail == "rpo-inactive"
    active = HealthConfig(**{**config.__dict__, "rpo_hours": 24})
    failed = _run(active, _probes(), {"telegram": Sink(), "email": Sink()}, mode="check")
    assert next(item for item in failed.checks if item.name == "sync_backup").status == FAILED


def test_unit_templates_use_explicit_calendar_zones_and_do_not_enable_production():
    check = (HETZNER / "language-guard-health-check.timer").read_text(encoding="utf-8")
    report = (HETZNER / "language-guard-health-report.timer").read_text(encoding="utf-8")
    verify = (HETZNER / "language-guard-sync-verify.timer").read_text(encoding="utf-8")
    sync = (HETZNER / "language-guard-sync-backup.timer").read_text(encoding="utf-8")
    accounts = (HETZNER / "language-guard-backup.timer").read_text(encoding="utf-8")
    setup = (HETZNER / "setup.sh").read_text(encoding="utf-8")
    service = (HETZNER / "language-guard-health-report.service").read_text(encoding="utf-8")
    assert "OnCalendar=*-*-* *:0/30:00 Europe/Amsterdam" in check
    assert "OnCalendar=*-*-* 09:00:00 Europe/Amsterdam" in report
    assert "OnCalendar=*-*-* 08:00:00 Europe/Amsterdam" in verify
    assert "OnCalendar=*-*-* 04:45:00 UTC" in sync
    assert "OnCalendar=*-*-* 03:15:00" in accounts
    assert "Timezone=" not in check + report + verify + sync + accounts
    assert "STUDY_SYNC_ENABLED" not in service
    assert "LoadCredential=" not in service
    assert "SupplementaryGroups=lg-notify-client lg-health" in service
    assert "HEALTH_NOTIFY_SOCKET=/run/language-guard/notify.sock" in service
    assert "/opt/language-guard/.env" not in service
    check_service = (HETZNER / "language-guard-health-check.service").read_text(encoding="utf-8")
    verify_service = (HETZNER / "language-guard-sync-verify.service").read_text(encoding="utf-8")
    notifier = (HETZNER / "language-guard-health-notify@.service").read_text(encoding="utf-8")
    socket_unit = (HETZNER / "language-guard-health-notify.socket").read_text(encoding="utf-8")
    sysusers = (HETZNER / "language-guard-notify.sysusers").read_text(encoding="utf-8")
    account_unit = (HETZNER / "language-guard.service").read_text(encoding="utf-8")
    for unit in (service, check_service):
        assert "UMask=0077" in unit
        assert "LoadCredential=" not in unit
        assert "InaccessiblePaths=-/etc/language-guard" in unit
    assert "User=lg-verify" in verify_service
    assert "UMask=0027" in verify_service
    assert "HEALTH_VERIFY_RESULT_PATH=/var/lib/language-guard-verify/result.json" in verify_service
    assert "accounts.db" in verify_service
    assert "User=lg-notify" in notifier
    assert "LoadCredential=telegram.token:/etc/language-guard/telegram.token" in notifier
    assert "InaccessiblePaths=-/opt/language-guard " in notifier
    assert "/opt/language-guard-notify" in notifier
    assert "python -I" in notifier
    assert "/var/backups/language-guard" in notifier
    assert "ReadOnlyPaths=/opt/language-guard/venv" not in notifier
    backup_service = (HETZNER / "language-guard-sync-backup.service").read_text(encoding="utf-8")
    assert "User=guard" in backup_service
    assert "Environment=HEALTH_STATE_PATH=/var/lib/language-guard/health-state.json" in backup_service
    assert "Environment=HEALTH_STATE_PATH=/var/lib/language-guard/health-state.json" in check_service
    assert "ReadWritePaths=/var/lib/language-guard" in check_service
    accounts_service = (HETZNER / "language-guard-backup.service").read_text(encoding="utf-8")
    assert "HEALTH_STATE_PATH" not in accounts_service
    assert "SocketGroup=lg-notify-client" in socket_unit
    assert "SocketMode=0660" in socket_unit
    assert "DirectoryMode=0755" in socket_unit
    assert "DirectoryMode=0750" not in socket_unit
    for line in setup.splitlines():
        if line.startswith("chown"):
            assert "language-guard-notify" not in line
    assert "m guard" not in sysusers
    assert "SupplementaryGroups=" not in account_unit
    assert "LoadCredential=" not in account_unit
    report_source = (HETZNER / "health_report.py").read_text(encoding="utf-8")
    assert "CREDENTIALS_DIRECTORY" not in report_source
    assert "telegram.token" not in report_source
    for unit in (
        "language-guard-health-check.timer",
        "language-guard-health-report.timer",
        "language-guard-sync-verify.timer",
        "language-guard-sync-backup.timer",
        "language-guard-health-notify.socket",
    ):
        assert f"systemctl enable --now {unit}" not in setup
        assert f"/etc/systemd/system/{unit}" not in setup


def test_systemd_analyze_calendar_when_available():
    import shutil
    import subprocess

    analyze = shutil.which("systemd-analyze")
    if analyze is None:
        pytest.skip("systemd-analyze is not available")
    expressions = [
        "*-*-* *:0/30:00 Europe/Amsterdam",
        "*-*-* 09:00:00 Europe/Amsterdam",
        "*-*-* 08:00:00 Europe/Amsterdam",
        "*-*-* 04:45:00 UTC",
    ]
    for expression in expressions:
        result = subprocess.run(
            [analyze, "calendar", expression],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        assert result.returncode == 0, result.stderr


def test_cli_reads_sync_flag_from_unit_and_dropin(tmp_path):
    import importlib.util

    spec = importlib.util.spec_from_file_location("health_report_flags", HETZNER / "health_report.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    unit_dir = tmp_path / "units"
    dropin = unit_dir / "language-guard.service.d"
    dropin.mkdir(parents=True)
    (unit_dir / "language-guard.service").write_text("[Service]\n", encoding="utf-8")
    (dropin / "10-sync.conf").write_text(
        '[Service]\nEnvironment=STUDY_SYNC_ENABLED=1\n',
        encoding="utf-8",
    )
    readings = module._unit_flags(str(unit_dir))
    assert readings[-1]["readable"] is True
    assert readings[-1]["value"] == "1"
    missing = module._unit_flags(str(tmp_path / "absent"))
    assert missing[0]["readable"] is False


def test_cli_check_does_not_create_sync_database(tmp_path, monkeypatch):
    import importlib.util

    live = tmp_path / "study_sync.db"
    monkeypatch.setenv("HEALTH_STATE_PATH", str(tmp_path / "state.json"))
    monkeypatch.setenv("HEALTH_WITNESS_PATH", str(tmp_path / "witness"))
    monkeypatch.setenv("ACCOUNTS_BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setenv("ACCOUNTS_LIVE_DB", str(tmp_path / "accounts.db"))
    monkeypatch.setenv("STUDY_SYNC_DB", str(live))
    monkeypatch.setenv("STUDY_SYNC_BACKUP_DIR", str(tmp_path / "study-sync"))
    monkeypatch.setenv("SYSTEMD_UNIT_DIR", str(tmp_path / "systemd"))
    monkeypatch.setenv("HEALTH_ENV_FILE", str(tmp_path / "missing.env"))
    monkeypatch.setenv("HEALTH_VERIFY_RESULT_PATH", str(tmp_path / "verify-result.json"))
    monkeypatch.delenv("CREDENTIALS_DIRECTORY", raising=False)
    monkeypatch.delenv("HEALTH_PUBLIC_URL", raising=False)
    (tmp_path / "backups").mkdir()
    (tmp_path / "systemd").mkdir()
    spec = importlib.util.spec_from_file_location("health_report_cli", HETZNER / "health_report.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.main(["check"]) == 0
    assert not live.exists()


def _verify_cli():
    import importlib.util

    spec = importlib.util.spec_from_file_location("verify_sync_backup_cli", HETZNER / "verify_sync_backup.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _backup_cli():
    import importlib.util

    spec = importlib.util.spec_from_file_location("backup_sync_cli_review", HETZNER / "backup_sync.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_never_run_verification_is_unknown_and_a_recorded_skip_is_not_success(tmp_path):
    config = _config(tmp_path)
    first = _run(config, _probes(), {"telegram": Sink(), "email": Sink()}, mode="check")
    verify = next(item for item in first.checks if item.name == "sync_verify")
    assert verify.status == UNKNOWN
    assert verify.detail == "never-run"
    assert first.overall != "OK"
    health_monitor.note_sync_verify_result(
        config.verify_result_path,
        SKIPPED,
        checked_at="2026-11-03T08:00:00Z",
    )
    second = _run(config, _probes(), {"telegram": Sink(), "email": Sink()}, mode="check")
    recorded = next(item for item in second.checks if item.name == "sync_verify")
    assert recorded.status == SKIPPED
    assert "successful" not in second.text
    assert not Path(config.sync_live_db).exists()


def test_verified_result_follows_backup_identity_and_failure_stays_failed(tmp_path):
    config = _config(tmp_path)
    backup_dir = Path(config.sync_backup_dir)
    backup_dir.mkdir()
    backup = backup_dir / "study-sync-20260101-000000-000001.db"
    backup.write_bytes(b"snapshot-bytes!!")
    info = backup.stat()
    digest = __import__("sync_restore_verify").file_sha256(str(backup))
    health_monitor.note_sync_verify_result(
        config.verify_result_path,
        VERIFIED,
        backup_name=backup.name,
        backup_bytes=info.st_size,
        backup_mtime_ns=info.st_mtime_ns,
        backup_sha256=digest,
        checked_at="2026-11-03T08:00:00Z",
    )
    Path(config.sync_live_db).write_bytes(b"live")
    current = _run(config, _probes(), {"telegram": Sink(), "email": Sink()}, mode="check")
    assert next(item for item in current.checks if item.name == "sync_verify").status == VERIFIED
    same_size = b"snapshot-bytes??"
    assert len(same_size) == backup.stat().st_size
    backup.write_bytes(same_size)
    os.utime(backup, ns=(info.st_mtime_ns, info.st_mtime_ns))
    reused = _run(config, _probes(), {"telegram": Sink(), "email": Sink()}, mode="check")
    reused_check = next(item for item in reused.checks if item.name == "sync_verify")
    assert reused_check.status == UNKNOWN
    assert reused_check.detail == "stale"
    backup.write_bytes(b"snapshot-replaced")
    stale = _run(config, _probes(), {"telegram": Sink(), "email": Sink()}, mode="check")
    assert next(item for item in stale.checks if item.name == "sync_verify").status == UNKNOWN
    assert next(item for item in stale.checks if item.name == "sync_verify").detail == "stale"
    replaced = backup.stat()
    health_monitor.note_sync_verify_result(
        config.verify_result_path,
        FAILED,
        backup_name=backup.name,
        backup_bytes=replaced.st_size,
        backup_mtime_ns=replaced.st_mtime_ns,
    )
    failed = _run(config, _probes(), {"telegram": Sink(), "email": Sink()}, mode="check")
    assert next(item for item in failed.checks if item.name == "sync_verify").status == FAILED
    text = Path(config.verify_result_path).read_text(encoding="utf-8")
    assert str(config.sync_backup_dir) not in text
    assert "snapshot-replaced" not in text


def test_verifier_records_skip_and_verified_without_database_contents(tmp_path, monkeypatch, capsys):
    import sync_backup
    import sync_store

    record = tmp_path / "result.json"
    monkeypatch.setenv("HEALTH_VERIFY_RESULT_PATH", str(record))
    cli = _verify_cli()
    live = tmp_path / "study_sync.db"
    code = cli.execute(str(tmp_path / "backups"), str(tmp_path / "verify"), str(live))
    skipped = capsys.readouterr()
    assert code == 0
    assert skipped.out == "study_sync restore verification skipped\n"
    assert skipped.err == ""
    assert not live.exists()
    payload = json.loads(record.read_text(encoding="utf-8"))
    assert payload["status"] == SKIPPED
    assert payload["backup_name"] == ""
    assert payload["checked_at"].endswith("Z")
    assert str(live) not in record.read_text(encoding="utf-8")

    source = tmp_path / "real-sync.db"
    connection = sync_store.connect(str(source))
    connection.close()
    backups = tmp_path / "sync-backups"
    assert sync_backup.backup_database(str(source), str(backups)) is not None
    source_before = source.read_bytes()
    newest = next(backups.glob("study-sync-*.db"))
    newest_before = newest.read_bytes()
    verified_code = cli.execute(str(backups), str(tmp_path / "verify-run"), str(source))
    verified = capsys.readouterr()
    assert verified_code == 0
    assert verified.out == "study_sync restore verification verified\n"
    assert verified.err == ""
    recorded = json.loads(record.read_text(encoding="utf-8"))
    assert recorded["status"] == VERIFIED
    assert recorded["backup_name"].startswith("study-sync-")
    assert len(recorded["backup_sha256"]) == 64
    assert str(backups) not in record.read_text(encoding="utf-8")
    assert source.read_bytes() == source_before
    assert newest.read_bytes() == newest_before


def test_verifier_record_failure_keeps_the_real_exit(tmp_path, monkeypatch, capsys):
    blocked = tmp_path / "result.json"
    blocked.mkdir()
    monkeypatch.setenv("HEALTH_VERIFY_RESULT_PATH", str(blocked))
    cli = _verify_cli()
    live = tmp_path / "study_sync.db"
    code = cli.execute(str(tmp_path / "backups"), str(tmp_path / "verify"), str(live))
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == "study_sync restore verification skipped\n"
    assert captured.err == ""
    assert not live.exists()


def test_backup_note_failure_does_not_mark_the_alert_delivered(tmp_path, monkeypatch, capsys):
    blocked = tmp_path / "state.json"
    blocked.mkdir()
    monkeypatch.setenv("HEALTH_STATE_PATH", str(blocked))
    source = tmp_path / "study_sync.db"
    source.write_bytes(b"not-a-database")
    occupied = tmp_path / "occupied"
    occupied.write_bytes(b"x")

    class Sink:
        def emit(self, event):
            return None

    code = _backup_cli().execute(str(source), str(occupied), Sink())
    captured = capsys.readouterr()
    assert code == 1
    assert captured.err == "study_sync backup failed\n"
    assert str(source) not in captured.err
    assert "delivered" not in captured.err
    undelivered = _backup_cli().execute(str(source), str(occupied), None)
    missed = capsys.readouterr()
    assert undelivered == 2
    assert missed.err == "study_sync backup failed\nstudy_sync alert was not delivered\n"


def test_retention_warning_is_kept_until_a_health_run_displays_it(tmp_path):
    config = _config(tmp_path)
    env = {"HEALTH_STATE_PATH": config.state_path}
    Path(config.sync_live_db).write_bytes(b"db")
    backup_dir = Path(config.sync_backup_dir)
    backup_dir.mkdir()
    (backup_dir / "study-sync-20260101-000000-000001.db").write_bytes(b"kept")
    health_monitor.note_sync_backup_event("retention_warning", env)
    health_monitor.note_sync_backup_event("published", env)
    first = _run(config, _probes(), {"telegram": Sink(), "email": Sink()}, mode="check")
    assert next(item for item in first.checks if item.name == "sync_backup").detail == "retention"
    second = _run(config, _probes(), {"telegram": Sink(), "email": Sink()}, mode="check")
    assert next(item for item in second.checks if item.name == "sync_backup").detail == "rpo-inactive"


def test_concurrent_health_and_notes_keep_both_records(tmp_path):
    config = _config(tmp_path)
    env = {"HEALTH_STATE_PATH": config.state_path}
    barrier = threading.Barrier(3)
    errors = []

    def backup_notes():
        barrier.wait()
        try:
            for _ in range(8):
                health_monitor.note_sync_backup_event("failed", env)
        except Exception as error:
            errors.append(error)

    def verify_notes():
        barrier.wait()
        try:
            for _ in range(8):
                health_monitor.note_sync_verify_result(
                    config.verify_result_path,
                    FAILED,
                    backup_name="study-sync-20260101-000000-000001.db",
                    backup_bytes=3,
                    backup_mtime_ns=9,
                )
        except Exception as error:
            errors.append(error)

    def checks():
        barrier.wait()
        try:
            for _ in range(4):
                _run(config, _probes(), {"telegram": Sink(), "email": Sink()}, mode="check")
        except Exception as error:
            errors.append(error)

    threads = [threading.Thread(target=target) for target in (backup_notes, verify_notes, checks)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    state = json.loads(Path(config.state_path).read_text(encoding="utf-8"))
    recorded = json.loads(Path(config.verify_result_path).read_text(encoding="utf-8"))
    assert state["sync_backup_notice"] == "failed"
    assert recorded["status"] == FAILED
    assert config.accounts_live_db not in json.dumps(recorded)


def test_rejected_provider_is_not_recorded_as_accepted_and_body_is_not_logged(tmp_path):
    config = _config(tmp_path)
    health_monitor.note_sync_verify_result(
        config.verify_result_path,
        SKIPPED,
        checked_at="2026-11-03T08:00:00Z",
    )
    secret = "provider-body-secret"
    email = Sink(status=503, body=secret)
    result = _run(
        config,
        _probes(),
        {"telegram": Sink(), "email": email},
        mode="check",
        secrets=[secret],
    )
    assert result.deliveries["email"] == PROVIDER_REJECTED
    assert secret not in "\n".join(result.logs)
    accepted = json.loads(Path(config.state_path).read_text(encoding="utf-8"))["accepted"]
    assert all(not key.endswith(":email") for key in accepted)


def test_both_rejections_keep_the_incident_until_both_channels_accept(tmp_path):
    config = _config(tmp_path)
    env = {"HEALTH_STATE_PATH": config.state_path}
    Path(config.sync_live_db).write_bytes(b"db")
    backup_dir = Path(config.sync_backup_dir)
    backup_dir.mkdir()
    (backup_dir / "study-sync-20260101-000000-000001.db").write_bytes(b"kept")
    health_monitor.note_sync_backup_event("retention_warning", env)
    health_monitor.note_sync_backup_event("published", env)
    rejected = _run(
        config,
        _probes(),
        {"telegram": Sink(status=503), "email": Sink(status=503)},
        mode="check",
    )
    assert next(item for item in rejected.checks if item.name == "sync_backup").detail == "retention"
    state = json.loads(Path(config.state_path).read_text(encoding="utf-8"))
    assert state["sync_backup_notice"] == "retention_warning"
    assert state["sync_backup_clear_after_report"] is True
    assert state.get("sync_backup_alert_accepted", {}).get("telegram") is not True
    assert state.get("sync_backup_alert_accepted", {}).get("email") is not True
    recovered = _run(config, _probes(), {"telegram": Sink(), "email": Sink()}, mode="check")
    assert recovered.deliveries["telegram"] == PROVIDER_ACCEPTED
    assert recovered.deliveries["email"] == PROVIDER_ACCEPTED
    cleared = json.loads(Path(config.state_path).read_text(encoding="utf-8"))
    assert cleared["sync_backup_notice"] == "published"
    follow = _run(config, _probes(), {"telegram": Sink(), "email": Sink()}, mode="check")
    assert next(item for item in follow.checks if item.name == "sync_backup").detail == "rpo-inactive"


def test_one_channel_acceptance_does_not_clear_or_suppress_the_other(tmp_path):
    config = _config(tmp_path)
    env = {"HEALTH_STATE_PATH": config.state_path}
    Path(config.sync_live_db).write_bytes(b"db")
    backup_dir = Path(config.sync_backup_dir)
    backup_dir.mkdir()
    (backup_dir / "study-sync-20260101-000000-000001.db").write_bytes(b"kept")
    health_monitor.note_sync_backup_event("failed", env)
    health_monitor.note_sync_backup_event("published", env)
    email = Sink(status=400)
    first = _run(config, _probes(), {"telegram": Sink(), "email": email}, mode="check")
    assert first.deliveries["telegram"] == PROVIDER_ACCEPTED
    assert first.deliveries["email"] == PROVIDER_REJECTED
    state = json.loads(Path(config.state_path).read_text(encoding="utf-8"))
    assert state["sync_backup_notice"] == "failed"
    assert state["sync_backup_alert_accepted"]["telegram"] is True
    assert state["sync_backup_alert_accepted"].get("email") is not True
    email.status = 200
    second = _run(config, _probes(), {"telegram": Sink(), "email": email}, mode="check")
    assert second.deliveries == {"email": PROVIDER_ACCEPTED}
    cleared = json.loads(Path(config.state_path).read_text(encoding="utf-8"))
    assert cleared["sync_backup_notice"] == "published"


def test_skipped_result_does_not_become_verified_without_a_restore(tmp_path):
    config = _config(tmp_path)
    health_monitor.note_sync_verify_result(config.verify_result_path, FAILED)
    failed = _run(config, _probes(), {"telegram": Sink(), "email": Sink()}, mode="check")
    assert next(item for item in failed.checks if item.name == "sync_verify").status == FAILED
    health_monitor.note_sync_verify_result(
        config.verify_result_path,
        SKIPPED,
        checked_at="2026-11-03T08:00:00Z",
    )
    still_failed = _run(config, _probes(), {"telegram": Sink(), "email": Sink()}, mode="check")
    assert next(item for item in still_failed.checks if item.name == "sync_verify").status == FAILED
    with pytest.raises(ValueError):
        health_monitor.note_sync_verify_result(
            config.verify_result_path,
            VERIFIED,
            backup_name="study-sync-20260101-000000-000001.db",
        )
    assert json.loads(Path(config.verify_result_path).read_text(encoding="utf-8"))["status"] == FAILED


def test_result_write_stops_when_the_path_is_a_symlink(tmp_path, monkeypatch):
    target = tmp_path / "result.json"
    target.write_text("original", encoding="utf-8")
    real_islink = os.path.islink

    def fake_islink(path):
        if os.path.abspath(path) == os.path.abspath(target):
            return True
        return real_islink(path)

    monkeypatch.setattr(os.path, "islink", fake_islink)
    with pytest.raises(OSError):
        health_monitor.note_sync_verify_result(str(target), SKIPPED)
    assert target.read_text(encoding="utf-8") == "original"


def test_result_file_refuses_a_symlink_and_is_not_world_readable(tmp_path):
    import stat

    config = _config(tmp_path)
    health_monitor.note_sync_verify_result(
        config.verify_result_path,
        SKIPPED,
        checked_at="2026-11-03T08:00:00Z",
    )
    if os.name == "posix":
        mode = stat.S_IMODE(os.stat(config.verify_result_path).st_mode)
        assert mode & 0o007 == 0
    target = tmp_path / "elsewhere.json"
    target.write_text('{"status":"VERIFIED"}', encoding="utf-8")
    link = tmp_path / "linked-result.json"
    try:
        os.symlink(target, link)
    except OSError:
        pytest.skip("symlinks are not available")
    with pytest.raises(OSError):
        health_monitor.note_sync_verify_result(str(link), SKIPPED)
    assert target.read_text(encoding="utf-8") == '{"status":"VERIFIED"}'


def test_handoff_rejects_injection_and_a_failed_send_is_not_acceptance():
    import socket
    import threading

    import health_handoff

    left, right = socket.socketpair()
    calls = []

    def post(text):
        calls.append(text)
        return HttpResponse(503, "secret-body", 0.0)

    def serve():
        health_handoff.serve_one(right, {"telegram": post, "email": post}, ["super-secret-token"])

    worker = threading.Thread(target=serve)
    worker.start()
    health_handoff.write_frame(
        left,
        {
            "v": 1,
            "channels": ["telegram"],
            "event": "check",
            "lines": [{"name": "sync_backup", "status": "FAILED", "detail": "backup-failed"}],
            "text": "click here",
            "path": "/etc/passwd",
        },
    )
    rejected = health_handoff.read_frame(left)
    worker.join()
    left.close()
    right.close()
    assert rejected["results"] == {}
    assert calls == []
    assert "super-secret-token" not in json.dumps(rejected)

    second_left, second_right = socket.socketpair()

    def serve_again():
        health_handoff.serve_one(
            second_right,
            {"telegram": post, "email": None},
            ["super-secret-token"],
            sleep=_quiet_sleep,
            monotonic=lambda: 0.0,
        )

    worker = threading.Thread(target=serve_again)
    worker.start()
    health_handoff.write_frame(
        second_left,
        {
            "v": 1,
            "channels": ["telegram", "email"],
            "event": "report",
            "report_date": "2026-11-03",
            "lines": [{"name": "sync_backup", "status": "FAILED", "detail": "backup-failed"}],
            "heartbeat": True,
        },
    )
    payload = health_handoff.read_frame(second_left)
    worker.join()
    second_left.close()
    second_right.close()
    assert payload["results"]["telegram"] == PROVIDER_REJECTED
    assert payload["results"]["email"] == NOT_SENT
    assert payload["heartbeat"] == "withheld"
    assert "secret-body" not in json.dumps(payload)
    assert "super-secret-token" not in json.dumps(payload)
    with pytest.raises(health_handoff.HandoffError):
        health_handoff.validate_request(
            {"v": 1, "channels": ["telegram"], "event": "check", "text": "free text"}
        )
    rendered = health_handoff.validate_request(
        {
            "v": 1,
            "channels": ["telegram"],
            "event": "backup-incident",
            "lines": [{"name": "sync_backup", "status": "FAILED", "detail": "backup-failed"}],
        }
    )
    assert rendered["text"].startswith("Language Guard backup incident")
    assert "free text" not in rendered["text"]


def test_leftover_lock_file_does_not_block_a_backup_note(tmp_path):
    config = _config(tmp_path)
    leftover = Path(config.state_path + ".lock")
    leftover.write_bytes(b"stale-from-a-crashed-process")
    health_monitor.note_sync_backup_event("failed", {"HEALTH_STATE_PATH": config.state_path})
    state = json.loads(Path(config.state_path).read_text(encoding="utf-8"))
    assert state["sync_backup_notice"] == "failed"
    assert state["sync_backup_incident"]["id"]


def test_held_lock_times_out_without_deleting_the_lock_file(tmp_path):
    config = _config(tmp_path)
    lock_path = config.state_path + ".lock"
    started = threading.Event()
    release = threading.Event()

    def hold_until_release():
        with health_monitor._lock(lock_path):
            started.set()
            release.wait(5)

    worker = threading.Thread(target=hold_until_release)
    worker.start()
    assert started.wait(5)
    with pytest.raises(TimeoutError):
        with health_monitor._lock(lock_path, timeout=0.2):
            pass
    assert Path(lock_path).is_file()
    release.set()
    worker.join()
    health_monitor.note_sync_backup_event("failed", {"HEALTH_STATE_PATH": config.state_path})
    assert json.loads(Path(config.state_path).read_text(encoding="utf-8"))["sync_backup_notice"] == "failed"


def test_slow_notification_still_records_a_backup_incident(tmp_path):
    config = _config(tmp_path)
    started = threading.Event()
    release = threading.Event()

    class Slow(Sink):
        def __call__(self, text):
            self.texts.append(text)
            started.set()
            assert release.wait(5)
            return HttpResponse(200, "ok", 0.0)

    worker = threading.Thread(
        target=_run,
        args=(config, _probes(), {"telegram": Slow(), "email": Slow()}),
        kwargs={"mode": "check"},
    )
    worker.start()
    assert started.wait(5)
    health_monitor.note_sync_backup_event("failed", {"HEALTH_STATE_PATH": config.state_path})
    release.set()
    worker.join()
    state = json.loads(Path(config.state_path).read_text(encoding="utf-8"))
    assert state["sync_backup_notice"] == "failed"
    assert state["sync_backup_incident"]["kind"] == "failed"
    assert state["sync_backup_incident"]["id"]
    assert state["sync_backup_alert_accepted"] == {}


def test_new_failure_notifies_when_another_check_is_already_failed(tmp_path):
    config = _config(tmp_path)
    env = {"HEALTH_STATE_PATH": config.state_path}
    Path(config.sync_live_db).write_bytes(b"db")
    backup_dir = Path(config.sync_backup_dir)
    backup_dir.mkdir()
    (backup_dir / "study-sync-20260101-000000-000001.db").write_bytes(b"kept")
    probes = _probes(disk=(100, 96))
    health_monitor.note_sync_backup_event("failed", env)
    senders = {"telegram": Sink(), "email": Sink()}
    first = _run(config, probes, senders, mode="check")
    assert first.deliveries["telegram"] == PROVIDER_ACCEPTED
    state = json.loads(Path(config.state_path).read_text(encoding="utf-8"))
    first_id = state["sync_backup_incident"]["id"]
    quiet = _run(config, probes, {"telegram": Sink(), "email": Sink()}, mode="check")
    assert quiet.deliveries == {}
    health_monitor.note_sync_backup_event("failed", env)
    again = json.loads(Path(config.state_path).read_text(encoding="utf-8"))
    assert again["sync_backup_incident"]["id"] != first_id
    assert again["sync_backup_alert_accepted"] == {}
    third = _run(config, probes, {"telegram": Sink(), "email": Sink()}, mode="check")
    assert third.deliveries["telegram"] == PROVIDER_ACCEPTED
    assert third.deliveries["email"] == PROVIDER_ACCEPTED


def test_snapshot_symlink_does_not_read_the_live_database(tmp_path, monkeypatch):
    live = tmp_path / "accounts.db"
    _db(live)
    before = live.read_bytes()
    calls = []
    real_connect = sqlite3.connect

    def spy(path, *args, **kwargs):
        calls.append(str(path))
        return real_connect(path, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", spy)
    link = tmp_path / "snapshot.db"
    try:
        os.symlink(live, link)
    except OSError:
        pytest.skip("symlinks are not available")
    with pytest.raises((OSError, RuntimeError)):
        health_monitor.snapshot_integrity(str(link), str(live))
    assert calls == []
    assert live.read_bytes() == before


def test_snapshot_hardlink_does_not_read_the_live_database(tmp_path, monkeypatch):
    live = tmp_path / "accounts.db"
    _db(live)
    before = live.read_bytes()
    alias = tmp_path / "hardlink.db"
    try:
        os.link(live, alias)
    except OSError:
        pytest.skip("hardlinks are not available")
    calls = []
    real_connect = sqlite3.connect

    def spy(path, *args, **kwargs):
        calls.append(str(path))
        return real_connect(path, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", spy)
    with pytest.raises(RuntimeError, match="live accounts"):
        health_monitor.snapshot_integrity(str(alias), str(live))
    assert calls == []
    assert live.read_bytes() == before


def test_rate_limit_rejects_without_acceptance_or_heartbeat():
    import socket

    import health_handoff

    ledger = health_handoff.AttemptLedger(limit=1, now=lambda: 1000.0)
    assert ledger.allow()
    left, right = socket.socketpair()
    calls = []
    pings = []

    def post(text):
        calls.append(text)
        return HttpResponse(200, "ok", 0.0)

    def serve():
        health_handoff.serve_one(
            right,
            {"telegram": post},
            [],
            ping=lambda: pings.append(True) or True,
            ledger=ledger,
        )

    worker = threading.Thread(target=serve)
    worker.start()
    health_handoff.write_frame(
        left,
        {
            "v": 1,
            "channels": ["telegram"],
            "event": "check",
            "lines": [{"name": "disk", "status": "FAILED", "detail": "used=99%"}],
        },
    )
    payload = health_handoff.read_frame(left)
    worker.join()
    left.close()
    right.close()
    assert payload == {"v": 1, "results": {}, "heartbeat": "not-sent"}
    assert calls == []
    assert pings == []


def test_os_lock_is_released_when_the_holder_process_exits(tmp_path):
    import subprocess
    import sys

    lock_path = tmp_path / "state.json.lock"
    ready = tmp_path / "ready"
    script = tmp_path / "hold_lock.py"
    script.write_text(
        "import sys, time\n"
        f"sys.path.insert(0, {str(ROOT / 'app')!r})\n"
        "import health_monitor\n"
        f"ready = {str(ready)!r}\n"
        f"lock_path = {str(lock_path)!r}\n"
        "with health_monitor._lock(lock_path):\n"
        "    open(ready, 'w', encoding='utf-8').write('held')\n"
        "    time.sleep(30)\n",
        encoding="utf-8",
    )
    process = subprocess.Popen([sys.executable, str(script)])
    try:
        for _ in range(100):
            if ready.exists():
                break
            time.sleep(0.05)
        else:
            process.kill()
            pytest.fail("holder did not acquire the lock")
        process.kill()
        process.wait(timeout=5)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
    with health_monitor._lock(str(lock_path), timeout=2):
        pass


def _record_backup(config, status, stamp, payload=b"snapshot-bytes!!"):
    backup_dir = Path(config.sync_backup_dir)
    backup_dir.mkdir(exist_ok=True)
    backup = backup_dir / "study-sync-20260101-000000-000001.db"
    backup.write_bytes(payload)
    info = backup.stat()
    digest = __import__("sync_restore_verify").file_sha256(str(backup))
    health_monitor.note_sync_verify_result(
        config.verify_result_path,
        status,
        backup_name=backup.name if status == VERIFIED else "",
        backup_bytes=info.st_size if status == VERIFIED else 0,
        backup_mtime_ns=info.st_mtime_ns if status == VERIFIED else 0,
        backup_sha256=digest if status == VERIFIED else "",
        checked_at=stamp,
    )
    return backup, info, digest


def test_result_reader_does_not_create_the_verifier_lock(tmp_path):
    config = _config(tmp_path)
    health_monitor.note_sync_verify_result(
        config.verify_result_path,
        SKIPPED,
        checked_at="2026-11-03T08:00:00Z",
    )
    lock = Path(config.verify_result_path + ".lock")
    lock.unlink()
    record = health_monitor._read_verify_result(config.verify_result_path)
    assert record["status"] == SKIPPED
    assert not lock.exists()
    Path(config.verify_result_path).write_text("{", encoding="utf-8")
    assert health_monitor._read_verify_result(config.verify_result_path) == {"status": "unreadable"}


def test_reader_does_not_need_the_directory_write_bit(tmp_path):
    """Mode 0550 blocks a non-root writer of the same UID.

    This is not a distinct-UID proof. Root bypasses the mode bits, and this
    host does not execute a second-UID read.
    """
    import sys

    if sys.platform == "win32" or not hasattr(os, "geteuid"):
        pytest.skip("deferred on Windows: directory write-bit result read was not executed")
    if os.geteuid() == 0:
        pytest.skip("root bypasses mode 0550; chmod is not a distinct-UID proof")
    directory = tmp_path / "verify"
    directory.mkdir()
    result = directory / "result.json"
    result.write_text(
        json.dumps(
            {
                "status": "VERIFIED",
                "checked_at": "2026-11-03T08:00:00Z",
                "backup_name": "study-sync-20260101-000000-000001.db",
                "backup_bytes": 1,
                "backup_mtime_ns": 1,
                "backup_sha256": "a" * 64,
            }
        ),
        encoding="utf-8",
    )
    os.chmod(result, 0o440)
    os.chmod(directory, 0o550)
    try:
        with pytest.raises(OSError):
            os.open(directory / "result.json.lock", os.O_CREAT | os.O_WRONLY, 0o600)
        record = health_monitor._read_verify_result(str(result))
        assert record["status"] == VERIFIED
        assert not (directory / "result.json.lock").exists()
    finally:
        os.chmod(directory, 0o750)
        os.chmod(result, 0o640)


def test_restore_verification_rejects_expired_future_and_replaced_results(tmp_path):
    config = _config(tmp_path)
    Path(config.sync_live_db).write_bytes(b"live")
    backup, info, digest = _record_backup(config, VERIFIED, "2020-01-01T00:00:00Z")
    expired = _run(config, _probes(), {"telegram": Sink(), "email": Sink()}, mode="check")
    expired_check = next(item for item in expired.checks if item.name == "sync_verify")
    assert expired_check.status == UNKNOWN
    assert expired_check.detail == "stale"
    _record_backup(config, VERIFIED, "2026-11-03T08:00:00Z")
    fresh = _run(config, _probes(), {"telegram": Sink(), "email": Sink()}, mode="check")
    assert next(item for item in fresh.checks if item.name == "sync_verify").status == VERIFIED
    _record_backup(config, VERIFIED, "2099-01-01T00:00:00Z")
    future = _run(config, _probes(), {"telegram": Sink(), "email": Sink()}, mode="check")
    future_check = next(item for item in future.checks if item.name == "sync_verify")
    assert future_check.status == UNKNOWN
    assert future_check.detail == "stale"
    _record_backup(config, VERIFIED, "2026-11-03T08:00:00Z")
    replacement = b"snapshot-bytes??"
    assert len(replacement) == len(b"snapshot-bytes!!")
    backup.write_bytes(replacement)
    os.utime(backup, ns=(info.st_mtime_ns, info.st_mtime_ns))
    replaced = _run(config, _probes(), {"telegram": Sink(), "email": Sink()}, mode="check")
    replaced_check = next(item for item in replaced.checks if item.name == "sync_verify")
    assert replaced_check.status == UNKNOWN
    assert replaced_check.detail == "stale"
    backup.write_bytes(b"snapshot-bytes!!")
    os.utime(backup, ns=(info.st_mtime_ns, info.st_mtime_ns))
    health_monitor.note_sync_verify_result(
        config.verify_result_path,
        VERIFIED,
        backup_name=backup.name,
        backup_bytes=info.st_size,
        backup_mtime_ns=info.st_mtime_ns,
        backup_sha256=digest,
        checked_at="2026-11-03T08:00:00Z",
    )
    later = _run(config, _probes(), {"telegram": Sink(), "email": Sink()}, mode="check")
    assert next(item for item in later.checks if item.name == "sync_verify").status == VERIFIED
    Path(config.verify_result_path).write_text(
        json.dumps({"status": "VERIFIED", "checked_at": "not-a-time", "backup_sha256": digest}),
        encoding="utf-8",
    )
    malformed = _run(config, _probes(), {"telegram": Sink(), "email": Sink()}, mode="check")
    malformed_check = next(item for item in malformed.checks if item.name == "sync_verify")
    assert malformed_check.status == UNKNOWN
    assert malformed_check.detail == "unreadable"


def test_slow_integrity_keeps_an_incident_noted_during_the_probe(tmp_path, monkeypatch):
    config = _config(tmp_path)
    env = {"HEALTH_STATE_PATH": config.state_path}

    def slow(path, live):
        health_monitor.note_sync_backup_event("failed", env)
        return VERIFIED

    monkeypatch.setattr(health_monitor, "snapshot_integrity", slow)
    result = _run(config, _probes(), {"telegram": Sink(), "email": Sink()}, mode="check")
    state = json.loads(Path(config.state_path).read_text(encoding="utf-8"))
    assert state["sync_backup_notice"] == "failed"
    assert state["sync_backup_incident"]["kind"] == "failed"
    assert state["sync_backup_incident"]["id"]
    assert state["sync_backup_alert_accepted"] == {"telegram": True, "email": True}
    backup = next(item for item in result.checks if item.name == "sync_backup")
    assert backup.status == FAILED
    assert backup.detail == "backup-failed"


def test_state_lock_refuses_a_reported_symlink(tmp_path, monkeypatch):
    lock = tmp_path / "state.json.lock"
    lock.write_text("kept", encoding="utf-8")
    real_islink = os.path.islink

    def fake_islink(path):
        if os.path.abspath(path) == os.path.abspath(lock):
            return True
        return real_islink(path)

    monkeypatch.setattr(os.path, "islink", fake_islink)
    for _ in range(2):
        with pytest.raises(OSError) as caught:
            with health_monitor._lock(str(lock), timeout=0.2):
                pass
        assert not isinstance(caught.value, TimeoutError)
    assert lock.read_text(encoding="utf-8") == "kept"


def test_state_lock_refuses_a_symlink(tmp_path):
    target = tmp_path / "elsewhere"
    target.write_text("kept", encoding="utf-8")
    lock = tmp_path / "state.json.lock"
    try:
        os.symlink(target, lock)
    except OSError:
        pytest.skip("deferred on Windows: state lock symlink")
    with pytest.raises(OSError):
        with health_monitor._lock(str(lock), timeout=0.2):
            pass
    assert target.read_text(encoding="utf-8") == "kept"


def _serve_frame(frame, ledger=None, post=None, ping=None, now=None):
    import socket

    import health_handoff

    left, right = socket.socketpair()
    calls = []
    pings = []

    def sender(text):
        calls.append(text)
        if post is None:
            return HttpResponse(200, "ok", 0.0)
        return post(text)

    def serve():
        health_handoff.serve_one(
            right,
            {"telegram": sender, "email": sender},
            [],
            ping=(lambda: pings.append(True) or True) if ping is None else ping,
            ledger=ledger,
            sleep=_quiet_sleep,
            monotonic=lambda: 0.0,
            now=now or (lambda: datetime(2026, 11, 3, 8, 0, tzinfo=timezone.utc)),
        )

    worker = threading.Thread(target=serve)
    worker.start()
    health_handoff.write_frame(left, frame)
    try:
        payload = health_handoff.read_frame(left)
    finally:
        worker.join()
        left.close()
        right.close()
    return payload, calls, pings


def test_empty_channel_check_cannot_ping(tmp_path):
    payload, calls, pings = _serve_frame(
        {"v": 1, "channels": [], "event": "check", "lines": [], "heartbeat": True}
    )
    assert payload == {"v": 1, "results": {}, "heartbeat": "not-sent"}
    assert calls == []
    assert pings == []


def test_heartbeat_follows_an_accepted_report_and_can_retry(tmp_path):
    import health_handoff

    ledger = health_handoff.AttemptLedger(
        path=str(tmp_path / "attempts.json"),
        now=lambda: 1000.0,
        limit=30,
    )
    failed, calls, pings = _serve_frame(
        {
            "v": 1,
            "channels": ["telegram", "email"],
            "event": "report",
            "report_date": "2026-11-03",
            "lines": [{"name": "disk", "status": "VERIFIED", "detail": "used=10%"}],
            "heartbeat": True,
        },
        ledger=ledger,
        post=lambda text: HttpResponse(400, "no", 0.0),
    )
    assert failed["results"] == {"telegram": PROVIDER_REJECTED, "email": PROVIDER_REJECTED}
    assert failed["heartbeat"] == "withheld"
    assert pings == []
    assert ledger.report_accepted("2026-11-03") is False
    accepted, calls, pings = _serve_frame(
        {
            "v": 1,
            "channels": ["telegram", "email"],
            "event": "report",
            "report_date": "2026-11-03",
            "lines": [{"name": "disk", "status": "VERIFIED", "detail": "used=10%"}],
            "heartbeat": True,
        },
        ledger=ledger,
        ping=lambda: False,
    )
    assert accepted["results"]["telegram"] == PROVIDER_ACCEPTED
    assert accepted["heartbeat"] == "ping-rejected"
    assert "received" not in accepted
    assert ledger.report_accepted("2026-11-03") is True
    retry, calls, pings = _serve_frame(
        {
            "v": 1,
            "channels": [],
            "event": "report",
            "report_date": "2026-11-03",
            "lines": [],
            "heartbeat": True,
        },
        ledger=ledger,
    )
    assert retry["results"] == {}
    assert retry["heartbeat"] == "ping-accepted"
    assert calls == []
    assert pings == [True]


def test_corrupt_ledger_refuses_without_reset_acceptance_or_heartbeat(tmp_path):
    import health_handoff

    path = tmp_path / "attempts.json"
    path.write_text("{", encoding="utf-8")
    ledger = health_handoff.AttemptLedger(path=str(path), now=lambda: 1000.0)
    assert ledger.allow() is False
    assert path.read_text(encoding="utf-8") == "{"
    payload, calls, pings = _serve_frame(
        {
            "v": 1,
            "channels": ["telegram"],
            "event": "report",
            "report_date": "2026-11-03",
            "lines": [{"name": "disk", "status": "VERIFIED", "detail": "used=10%"}],
            "heartbeat": True,
        },
        ledger=ledger,
    )
    assert payload == {"v": 1, "results": {}, "heartbeat": "not-sent"}
    assert calls == []
    assert pings == []
    assert path.read_text(encoding="utf-8") == "{"


def test_ledger_reservations_are_serialized_across_processes(tmp_path):
    import subprocess
    import sys

    path = tmp_path / "attempts.json"
    script = tmp_path / "reserve.py"
    script.write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(ROOT / 'app')!r})\n"
        "import health_handoff\n"
        f"ledger = health_handoff.AttemptLedger(path={str(path)!r}, limit=1, now=lambda: 1000.0)\n"
        "try:\n"
        "    result = ledger.allow(1)\n"
        "except Exception as exc:\n"
        "    result = type(exc).__name__\n"
        "sys.stdout.write('true' if result is True else 'false' if result is False else str(result))\n",
        encoding="utf-8",
    )
    first = subprocess.Popen([sys.executable, str(script)], stdout=subprocess.PIPE, text=True)
    second = subprocess.Popen([sys.executable, str(script)], stdout=subprocess.PIPE, text=True)
    first_out = first.communicate(timeout=20)[0]
    second_out = second.communicate(timeout=20)[0]
    assert first.returncode == 0
    assert second.returncode == 0
    assert sorted([first_out, second_out]) == ["false", "true"]
    assert "FileNotFoundError" not in first_out + second_out


def test_ledger_lock_is_released_when_the_holder_exits(tmp_path):
    import subprocess
    import sys

    import health_handoff

    path = tmp_path / "attempts.json"
    ready = tmp_path / "ready"
    script = tmp_path / "hold.py"
    script.write_text(
        "import sys, time\n"
        f"sys.path.insert(0, {str(ROOT / 'app')!r})\n"
        "import health_handoff\n"
        f"ready = {str(ready)!r}\n"
        f"lock_path = {str(path) + '.lock'!r}\n"
        "with health_handoff._ledger_lock(lock_path):\n"
        "    open(ready, 'w', encoding='utf-8').write('held')\n"
        "    time.sleep(30)\n",
        encoding="utf-8",
    )
    process = subprocess.Popen([sys.executable, str(script)])
    try:
        for _ in range(100):
            if ready.exists():
                break
            time.sleep(0.05)
        else:
            process.kill()
            pytest.fail("holder did not acquire the ledger lock")
        process.kill()
        process.wait(timeout=5)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
    ledger = health_handoff.AttemptLedger(path=str(path), limit=1, now=lambda: 1000.0)
    assert ledger.allow(1) is True


def test_freshness_keeps_two_wall_clock_hours_across_the_amsterdam_fall_back(tmp_path):
    record = {"checked_at": "2026-10-24T06:00:00Z"}
    config = _config(tmp_path)
    config.now = datetime(2026, 10, 25, 8, 30, tzinfo=timezone.utc)
    assert health_monitor._checked_at_current(config, record)
    config.now = datetime(2026, 10, 25, 9, 0, tzinfo=timezone.utc)
    assert health_monitor._checked_at_current(config, record)
    config.now = datetime(2026, 10, 25, 9, 0, 1, tzinfo=timezone.utc)
    assert health_monitor._checked_at_current(config, record) is False


def test_malformed_published_result_is_unreadable_and_a_missing_file_is_never_run(tmp_path):
    config = _config(tmp_path)
    missing = _run(config, _probes(), {"telegram": Sink(), "email": Sink()}, mode="check")
    assert next(item for item in missing.checks if item.name == "sync_verify").detail == "never-run"
    path = Path(config.verify_result_path)
    path.write_text("{", encoding="utf-8")
    broken = _run(config, _probes(), {"telegram": Sink(), "email": Sink()}, mode="check")
    assert next(item for item in broken.checks if item.name == "sync_verify").detail == "unreadable"
    path.write_text(
        json.dumps(
            {
                "status": "VERIFIED",
                "checked_at": "2026-11-03T08:00:00Z",
                "backup_name": "study-sync-20260101-000000-000001.db",
                "backup_bytes": "not-an-integer",
                "backup_mtime_ns": 1,
                "backup_sha256": "ab" * 32,
            }
        ),
        encoding="utf-8",
    )
    bad_number = _run(config, _probes(), {"telegram": Sink(), "email": Sink()}, mode="check")
    assert next(item for item in bad_number.checks if item.name == "sync_verify").detail == "unreadable"
    path.unlink()
    path.mkdir()
    directory = _run(config, _probes(), {"telegram": Sink(), "email": Sink()}, mode="check")
    assert next(item for item in directory.checks if item.name == "sync_verify").detail == "unreadable"
    path.rmdir()
    backup_dir = Path(config.sync_backup_dir)
    backup_dir.mkdir()
    backup = backup_dir / "study-sync-20260101-000000-000001.db"
    backup.write_bytes(b"snapshot-bytes!!")
    info = backup.stat()
    digest = __import__("sync_restore_verify").file_sha256(str(backup))
    health_monitor.note_sync_verify_result(
        str(path),
        VERIFIED,
        backup_name=backup.name,
        backup_bytes=info.st_size,
        backup_mtime_ns=info.st_mtime_ns,
        backup_sha256=digest,
        checked_at="2026-11-03T08:00:00Z",
    )
    Path(config.sync_live_db).write_bytes(b"live")
    valid = _run(config, _probes(), {"telegram": Sink(), "email": Sink()}, mode="check")
    assert next(item for item in valid.checks if item.name == "sync_verify").status == VERIFIED


def test_retention_incident_is_sent_and_settled_without_a_live_database(tmp_path):
    config = _config(tmp_path)
    env = {"HEALTH_STATE_PATH": config.state_path}
    health_monitor.note_sync_backup_event("retention_warning", env)
    health_monitor.note_sync_backup_event("published", env)
    email = Sink(status=400)
    first = _run(config, _probes(), {"telegram": Sink(), "email": email}, mode="check")
    backup = next(item for item in first.checks if item.name == "sync_backup")
    assert backup.detail == "retention"
    assert "retention" in first.text
    database = next(item for item in first.checks if item.name == "sync_database")
    assert database.status == SKIPPED
    state = json.loads(Path(config.state_path).read_text(encoding="utf-8"))
    incident_id = state["sync_backup_incident"]["id"]
    assert state["sync_backup_notice"] == "retention_warning"
    assert state["sync_backup_alert_accepted"] == {"telegram": True}
    email.status = 200
    second = _run(config, _probes(), {"telegram": Sink(), "email": email}, mode="check")
    assert second.deliveries == {"email": PROVIDER_ACCEPTED}
    settled = json.loads(Path(config.state_path).read_text(encoding="utf-8"))
    assert settled["sync_backup_notice"] == "published"
    assert settled["sync_backup_incident"]["id"] == incident_id
    assert "sync_backup_alert_accepted" not in settled


def test_witnessed_disappearance_stays_separate_when_no_incident_is_waiting(tmp_path):
    config = _config(tmp_path)
    Path(config.sync_live_db).write_bytes(b"db")
    _run(config, _probes(), {"telegram": Sink(), "email": Sink()}, mode="check")
    Path(config.sync_live_db).unlink()
    plain = _run(config, _probes(), {"telegram": Sink(), "email": Sink()}, mode="check")
    assert next(item for item in plain.checks if item.name == "sync_backup").detail == "disappeared"
    assert next(item for item in plain.checks if item.name == "sync_database").detail == "disappeared"
    health_monitor.note_sync_backup_event("retention_warning", {"HEALTH_STATE_PATH": config.state_path})
    noted = _run(config, _probes(), {"telegram": Sink(), "email": Sink()}, mode="check")
    assert next(item for item in noted.checks if item.name == "sync_backup").detail == "retention"
    assert next(item for item in noted.checks if item.name == "sync_database").detail == "disappeared"
    assert "retention" in noted.text


def test_newer_incident_during_send_does_not_inherit_acceptance(tmp_path):
    config = _config(tmp_path)
    env = {"HEALTH_STATE_PATH": config.state_path}
    health_monitor.note_sync_backup_event("retention_warning", env)
    started = threading.Event()
    release = threading.Event()
    texts = []

    class Slow(Sink):
        def __call__(self, text):
            texts.append(text)
            started.set()
            assert release.wait(5)
            return HttpResponse(200, "ok", 0.0)

    worker = threading.Thread(
        target=_run,
        args=(config, _probes(), {"telegram": Slow(), "email": Slow()}),
        kwargs={"mode": "check"},
    )
    worker.start()
    assert started.wait(5)
    health_monitor.note_sync_backup_event("failed", env)
    replacement = json.loads(Path(config.state_path).read_text(encoding="utf-8"))
    replacement_id = replacement["sync_backup_incident"]["id"]
    release.set()
    worker.join()
    assert any("retention" in text for text in texts)
    state = json.loads(Path(config.state_path).read_text(encoding="utf-8"))
    assert state["sync_backup_notice"] == "failed"
    assert state["sync_backup_incident"]["id"] == replacement_id
    assert state["sync_backup_alert_accepted"] == {}


def test_heartbeat_retry_is_bound_to_the_current_amsterdam_date(tmp_path):
    import health_handoff

    ledger = health_handoff.AttemptLedger(
        path=str(tmp_path / "attempts.json"),
        now=lambda: 1000.0,
        limit=40,
    )
    today = lambda: datetime(2026, 11, 3, 8, 0, tzinfo=timezone.utc)
    tomorrow = lambda: datetime(2026, 11, 4, 8, 0, tzinfo=timezone.utc)
    invalid, calls, pings = _serve_frame(
        {"v": 1, "channels": [], "event": "report", "report_date": "2020-02-31", "heartbeat": True},
        ledger=ledger,
        now=today,
    )
    assert invalid == {"v": 1, "results": {}, "heartbeat": "not-sent"}
    assert calls == []
    assert pings == []
    ledger.note_report("2020-01-01")
    old, calls, pings = _serve_frame(
        {"v": 1, "channels": [], "event": "report", "report_date": "2020-01-01", "heartbeat": True},
        ledger=ledger,
        now=today,
    )
    assert old["heartbeat"] == "withheld"
    assert calls == []
    assert pings == []
    assert ledger.report_accepted("2020-01-01") is False
    failed, calls, pings = _serve_frame(
        {
            "v": 1,
            "channels": ["telegram", "email"],
            "event": "report",
            "report_date": "2026-11-03",
            "lines": [{"name": "disk", "status": "VERIFIED", "detail": "used=10%"}],
            "heartbeat": True,
        },
        ledger=ledger,
        post=lambda text: HttpResponse(400, "no", 0.0),
        now=today,
    )
    assert failed["results"] == {"telegram": PROVIDER_REJECTED, "email": PROVIDER_REJECTED}
    assert failed["heartbeat"] == "withheld"
    assert pings == []
    assert ledger.report_accepted("2026-11-03") is False
    accepted, calls, pings = _serve_frame(
        {
            "v": 1,
            "channels": ["telegram", "email"],
            "event": "report",
            "report_date": "2026-11-03",
            "lines": [{"name": "disk", "status": "VERIFIED", "detail": "used=10%"}],
            "heartbeat": True,
        },
        ledger=ledger,
        ping=lambda: False,
        now=today,
    )
    assert accepted["heartbeat"] == "ping-rejected"
    assert ledger.report_accepted("2026-11-03") is True
    retry, calls, pings = _serve_frame(
        {"v": 1, "channels": [], "event": "report", "report_date": "2026-11-03", "heartbeat": True},
        ledger=ledger,
        now=today,
    )
    assert retry["heartbeat"] == "ping-accepted"
    assert calls == []
    assert pings == [True]
    next_day, calls, pings = _serve_frame(
        {"v": 1, "channels": [], "event": "report", "report_date": "2026-11-03", "heartbeat": True},
        ledger=ledger,
        now=tomorrow,
    )
    assert next_day["heartbeat"] == "withheld"
    assert calls == []
    assert pings == []
    assert ledger.report_accepted("2026-11-03") is False
    unused, calls, pings = _serve_frame(
        {"v": 1, "channels": [], "event": "report", "report_date": "2026-11-04", "heartbeat": True},
        ledger=ledger,
        now=tomorrow,
    )
    assert unused["heartbeat"] == "withheld"
    assert calls == []
    assert pings == []
