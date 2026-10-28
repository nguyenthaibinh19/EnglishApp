"""Backup study_sync.db with SQLite's online backup API.

The systemd unit that would run this script is a repository artifact only.
It is not installed. The accounts backup timer still runs backup_accounts.py
only. Backup of an existing file does not read STUDY_SYNC_ENABLED.

A missing source exits 0 and does not create the file or emit an alert.
Backup failure, including a filesystem or SQLite error before the copy
starts, prints a fixed line and exits 1 when the alert sink accepts the
event. A retention warning prints the ADR-020 sentence and exits 0 when
the sink accepts that event. If the event is not accepted, the process exits
2 after a fixed line. That is not a delivered page. Raw exception text is
not printed.
"""

import os
import sqlite3
import sys

APP_DIR = "/opt/language-guard"
SOURCE_DB = "/opt/language-guard/study_sync.db"
BACKUP_DIR = "/var/backups/language-guard/study-sync"

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
for _path in (os.path.join(_ROOT, "app"), _ROOT, APP_DIR):
    if os.path.isdir(_path) and _path not in sys.path:
        sys.path.insert(0, _path)

import sync_alert  # noqa: E402
import sync_backup  # noqa: E402

_FROM_ENV = object()


def execute(source: str, backup_dir: str, alert_sink=_FROM_ENV, environ=None) -> int:
    """Run one backup. ``alert_sink`` defaults to the process environment."""
    env = os.environ if environ is None else environ
    try:
        result = sync_backup.backup_database(source, backup_dir)
    except (sync_backup.SyncBackupError, OSError, sqlite3.Error):
        sys.stderr.write("study_sync backup failed\n")
        return _emit(
            sync_alert.EVENT_BACKUP_FAILED,
            success_exit=1,
            alert_sink=alert_sink,
            environ=env,
        )
    if result is not None and result.retention_warning:
        sys.stderr.write(result.retention_warning + "\n")
        return _emit(
            sync_alert.EVENT_RETENTION_WARNING,
            success_exit=0,
            alert_sink=alert_sink,
            environ=env,
        )
    return 0


def _emit(event_type: str, *, success_exit: int, alert_sink, environ) -> int:
    try:
        sink = sync_alert.load_sink(environ) if alert_sink is _FROM_ENV else alert_sink
        sync_alert.dispatch(sync_alert.make_event(event_type), sink)
    except sync_alert.SyncAlertError:
        sys.stderr.write(sync_alert.ALERT_NOT_DELIVERED + "\n")
        return 2
    return success_exit


def main() -> int:
    source = (os.environ.get("STUDY_SYNC_DB") or "").strip() or SOURCE_DB
    backup_dir = (os.environ.get("STUDY_SYNC_BACKUP_DIR") or "").strip() or BACKUP_DIR
    return execute(source, backup_dir)


if __name__ == "__main__":
    raise SystemExit(main())
