"""Verify the newest study_sync backup by restoring it to a new path.

Repository artifact only. No systemd unit runs this script. It does not
read STUDY_SYNC_ENABLED and it does not create a missing live database.

Exit 0 and the stdout line ``study_sync restore verification verified``
mean the newest backup was restored, checked, and the temporary copy was
removed. Exit 0 and ``study_sync restore verification skipped`` mean there
was no named backup and the live file is not present. That is not proof
the database never existed. Exit 1 and the stderr line
``study_sync restore verification failed`` mean the newest backup was not
proved recoverable. No older backup is tried. Paths and database contents
are not printed.
"""

import os
import sys

APP_DIR = "/opt/language-guard"
SOURCE_DB = "/opt/language-guard/study_sync.db"
BACKUP_DIR = "/var/backups/language-guard/study-sync"
VERIFY_ROOT = "/var/lib/language-guard/study-sync-verify"

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
for _path in (os.path.join(_ROOT, "app"), _ROOT, APP_DIR):
    if os.path.isdir(_path) and _path not in sys.path:
        sys.path.insert(0, _path)

import sync_restore_verify  # noqa: E402

LINE_VERIFIED = "study_sync restore verification verified"
LINE_SKIPPED = "study_sync restore verification skipped"
LINE_FAILED = "study_sync restore verification failed"


def execute(backup_dir: str, verify_root: str, live_db: str) -> int:
    """Run one verification. Callers pass explicit paths in tests."""
    try:
        result = sync_restore_verify.verify_latest_backup(backup_dir, verify_root, live_db)
    except Exception:
        sys.stderr.write(LINE_FAILED + "\n")
        return 1
    if result.status == sync_restore_verify.STATUS_VERIFIED:
        sys.stdout.write(LINE_VERIFIED + "\n")
        return 0
    if result.status == sync_restore_verify.STATUS_SKIPPED:
        sys.stdout.write(LINE_SKIPPED + "\n")
        return 0
    sys.stderr.write(LINE_FAILED + "\n")
    return 1


def main() -> int:
    backup_dir = (os.environ.get("STUDY_SYNC_BACKUP_DIR") or "").strip() or BACKUP_DIR
    verify_root = (os.environ.get("STUDY_SYNC_VERIFY_DIR") or "").strip() or VERIFY_ROOT
    live_db = (os.environ.get("STUDY_SYNC_DB") or "").strip() or SOURCE_DB
    return execute(backup_dir, verify_root, live_db)


if __name__ == "__main__":
    raise SystemExit(main())
