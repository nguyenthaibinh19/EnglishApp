"""Encrypt snapshot bytes to a public age recipient.

Stdout is written to a new file. age -o is not used. The private recovery
identity is not an input. If age fails, the exclusive ciphertext file stays.
This module does not delete it.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from dataclasses import dataclass

_HEADER = b"age-encryption.org/v1\n"


@dataclass(frozen=True)
class EncryptResult:
    status: str
    detail: str
    sha256: str
    argv: tuple


def find_age(explicit: str = "") -> str:
    if explicit:
        return explicit
    found = shutil.which("age")
    return found or ""


def recipient_rejected(recipient: str) -> bool:
    if not recipient or "\n" in recipient or "\r" in recipient or " " in recipient:
        return True
    if not recipient.startswith("age1pq1") or len(recipient) < 1500:
        return True
    if "AGE-SECRET" in recipient or recipient.startswith("-"):
        return True
    return False


def _stderr_class(stderr: bytes) -> str:
    if b"AGE-SECRET" in stderr:
        return "secret-in-stderr"
    text = stderr.decode("utf-8", errors="replace").lower()
    if "plugin" in text:
        return "plugin"
    if "recipient" in text or "malformed" in text or "invalid" in text:
        return "recipient"
    if "no such file" in text or "exec format" in text or "permission denied" in text:
        return "exec"
    if not text.strip():
        return "no-stderr"
    return "age-error"


def _output_problem(path: str) -> str:
    try:
        handle = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0))
    except OSError:
        return "unreadable-ciphertext"
    try:
        prefix = os.read(handle, len(_HEADER))
    finally:
        os.close(handle)
    if not prefix:
        return "empty-ciphertext"
    if prefix != _HEADER:
        return "bad-header"
    return ""


def encrypt_bytes(payload: bytes, dest: str, recipient: str, age_exe: str) -> EncryptResult:
    if recipient_rejected(recipient):
        return EncryptResult("FAILED", "recipient-rejected", "", ())
    if not payload:
        return EncryptResult("FAILED", "empty-payload", "", ())
    if os.path.lexists(dest):
        return EncryptResult("FAILED", "path-exists", "", ())
    if not age_exe or not os.path.isfile(age_exe):
        return EncryptResult("FAILED", "age-missing", "", ())
    argv = (age_exe, "-r", recipient)
    if any(flag in argv for flag in ("-i", "-d", "-o")):
        return EncryptResult("FAILED", "identity-in-command", "", argv)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
    try:
        handle = os.open(dest, flags, 0o600)
    except FileExistsError:
        return EncryptResult("FAILED", "path-exists", "", argv)
    except OSError:
        return EncryptResult("FAILED", "disk", "", argv)
    try:
        _fchmod(handle, 0o600)
        proc = subprocess.run(
            list(argv),
            input=payload,
            stdout=handle,
            stderr=subprocess.PIPE,
            cwd=os.path.dirname(age_exe) or None,
            check=False,
        )
    except OSError as exc:
        os.close(handle)
        return EncryptResult("FAILED", "age-exec:%s" % exc.errno, "", argv)
    os.close(handle)
    kind = _stderr_class(proc.stderr or b"")
    if kind == "secret-in-stderr":
        return EncryptResult("FAILED", "secret-in-stderr", "", argv)
    if proc.returncode != 0:
        return EncryptResult("FAILED", "age-failed:%s:rc=%s" % (kind, proc.returncode), "", argv)
    problem = _output_problem(dest)
    if problem:
        return EncryptResult("FAILED", problem, "", argv)
    return EncryptResult("ENCRYPTED", "sha256-recorded", _sha256(dest), argv)


def _fchmod(handle: int, mode: int) -> None:
    try:
        os.fchmod(handle, mode)
    except OSError:
        pass


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    handle = os.open(path, flags)
    try:
        while True:
            chunk = os.read(handle, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    finally:
        os.close(handle)
    return digest.hexdigest()
