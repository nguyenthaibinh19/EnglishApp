"""Sao lưu accounts.db đang mở, giữ 14 bản gần nhất."""

import os
import sqlite3
from datetime import datetime, timezone

APP_DIR = "/opt/language-guard"
BACKUP_DIR = "/var/backups/language-guard"
KEEP = 14


def main():
    source = os.path.join(APP_DIR, "accounts.db")
    if not os.path.isfile(source):
        return 0
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    target = os.path.join(BACKUP_DIR, f"accounts-{stamp}.db")
    src = sqlite3.connect(source)
    dst = sqlite3.connect(target)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    names = sorted(
        name for name in os.listdir(BACKUP_DIR) if name.startswith("accounts-") and name.endswith(".db")
    )
    for name in names[:-KEEP]:
        os.remove(os.path.join(BACKUP_DIR, name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
