"""Sao lưu accounts.db đang mở, giữ 14 bản gần nhất."""

import os
import sqlite3
from datetime import datetime, timezone

APP_DIR = "/opt/language-guard"
BACKUP_DIR = "/var/backups/language-guard"
KEEP = 14


def backup_file(source: str, backup_dir: str, *, keep: int = KEEP) -> int:
    """Backup one accounts database. Same rules as the production entry point."""
    if not os.path.isfile(source):
        return 0
    os.makedirs(backup_dir, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    target = os.path.join(backup_dir, f"accounts-{stamp}.db")
    src = sqlite3.connect(source)
    dst = sqlite3.connect(target)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    names = sorted(
        name
        for name in os.listdir(backup_dir)
        if name.startswith("accounts-") and name.endswith(".db")
    )
    for name in names[:-keep]:
        os.remove(os.path.join(backup_dir, name))
    return 0


def main():
    return backup_file(os.path.join(APP_DIR, "accounts.db"), BACKUP_DIR)


if __name__ == "__main__":
    raise SystemExit(main())
