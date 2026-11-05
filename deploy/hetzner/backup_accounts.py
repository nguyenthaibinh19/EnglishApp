"""Sao lưu accounts.db đang mở, giữ 14 bản gần nhất."""

import os
import sqlite3
import stat
from datetime import datetime, timezone

APP_DIR = "/opt/language-guard"
BACKUP_DIR = "/var/backups/language-guard"
KEEP = 14


def _reserve_private_snapshot(path: str) -> None:
    """Create one empty regular file at mode 0600.

    ``O_EXCL`` leaves an existing timestamp path untouched. A reservation
    that is not a private regular file is removed because this call created it.
    """
    try:
        descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise
    try:
        info = os.fstat(descriptor)
        private = stat.S_ISREG(info.st_mode)
        if os.name == "posix":
            private = private and stat.S_IMODE(info.st_mode) & 0o077 == 0
        if not private:
            raise RuntimeError("accounts backup was not created with mode 0600")
    except Exception:
        try:
            os.close(descriptor)
        finally:
            os.remove(path)
        raise
    os.close(descriptor)


def backup_file(source: str, backup_dir: str, *, keep: int = KEEP) -> int:
    """Backup one accounts database. Same rules as the production entry point."""
    if not os.path.isfile(source):
        return 0
    os.makedirs(backup_dir, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    target = os.path.join(backup_dir, f"accounts-{stamp}.db")
    try:
        _reserve_private_snapshot(target)
    except FileExistsError:
        raise
    try:
        src = sqlite3.connect(source)
        try:
            dst = sqlite3.connect(target)
            try:
                src.backup(dst)
            finally:
                dst.close()
        finally:
            src.close()
    except Exception:
        os.remove(target)
        raise
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
