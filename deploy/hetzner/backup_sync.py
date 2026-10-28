"""Backup study_sync.db with SQLite's online backup API.

Not installed on a timer. The accounts backup timer still runs backup_accounts.py
only. Set STUDY_SYNC_DB and STUDY_SYNC_BACKUP_DIR to point this at a local drill.
"""

import os
import sys

APP_DIR = "/opt/language-guard"
BACKUP_DIR = "/var/backups/language-guard"

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
for _path in (os.path.join(_ROOT, "app"), _ROOT, APP_DIR):
    if os.path.isdir(_path) and _path not in sys.path:
        sys.path.insert(0, _path)

import sync_backup  # noqa: E402


def main() -> int:
    source = (os.environ.get("STUDY_SYNC_DB") or "").strip() or os.path.join(
        APP_DIR, "study_sync.db"
    )
    backup_dir = (os.environ.get("STUDY_SYNC_BACKUP_DIR") or "").strip() or BACKUP_DIR
    try:
        result = sync_backup.backup_database(source, backup_dir)
    except sync_backup.SyncBackupError:
        sys.stderr.write("study_sync backup failed\n")
        return 1
    if result is not None and result.retention_warning:
        sys.stderr.write(result.retention_warning + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
