"""Synthetic restore check. It does not change download_verified.

The decrypted image stays in memory. A private identity is an argument of the
test entrypoint only. Its text is not logged.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from dataclasses import dataclass

sys.dont_write_bytecode = True

_HEADER = b"age-encryption.org/v1\n"


@dataclass(frozen=True)
class RestoreResult:
    ok: bool
    detail: str
    integrity: str
    marker: int


def synthetic_restore(ciphertext: bytes, age_exe: str, identity_path: str, marker: str) -> RestoreResult:
    if not ciphertext.startswith(_HEADER):
        return RestoreResult(False, "bad-header", "", 0)
    if b"SQLite format 3" in ciphertext[:32]:
        return RestoreResult(False, "plaintext-refused", "", 0)
    if not age_exe or not identity_path or os.path.islink(identity_path):
        return RestoreResult(False, "restore-unconfigured", "", 0)
    try:
        proc = subprocess.run(
            [age_exe, "-d", "-i", identity_path],
            input=ciphertext,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError:
        return RestoreResult(False, "age-exec", "", 0)
    if b"AGE-SECRET" in proc.stderr:
        return RestoreResult(False, "secret-in-stderr", "", 0)
    if proc.returncode != 0:
        return RestoreResult(False, "age-failed", "", 0)
    image = proc.stdout
    if not image.startswith(b"SQLite format 3"):
        return RestoreResult(False, "not-sqlite", "", 0)
    connection = sqlite3.connect(":memory:")
    try:
        connection.deserialize(image)
        row = connection.execute("PRAGMA integrity_check").fetchone()
        found = connection.execute("SELECT COUNT(*) FROM items WHERE payload = ?", (marker,)).fetchone()
    except sqlite3.Error:
        return RestoreResult(False, "sqlite-error", "", 0)
    finally:
        connection.close()
    integrity = row[0] if row else ""
    count = int(found[0]) if found else 0
    if integrity != "ok" or count != 1:
        return RestoreResult(False, "restore-mismatch", integrity, count)
    return RestoreResult(True, "integrity-ok", integrity, count)


def record_separate(attempt_dir: str, result: RestoreResult) -> str:
    """Write a side record. Numbered upload states are not rewritten."""
    body = {
        "detail": result.detail,
        "download_verified_untouched": True,
        "integrity": result.integrity,
        "marker": result.marker,
        "restore_drill": result.ok,
    }
    path = os.path.join(attempt_dir, "restore-check.json")
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
    handle = os.open(path, flags, 0o600)
    try:
        os.write(handle, json.dumps(body, sort_keys=True).encode("utf-8") + b"\n")
    finally:
        os.close(handle)
    return path
