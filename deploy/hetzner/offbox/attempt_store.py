"""Immutable attempt directories. An existing attempt is not rewritten."""

from __future__ import annotations

import json
import os
import re
import time

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")


def new_attempt_id() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-%d-%s" % (os.getpid(), os.urandom(4).hex())


def safe_id(attempt_id: str) -> bool:
    if not attempt_id or attempt_id in {".", ".."}:
        return False
    return _ID.fullmatch(attempt_id) is not None


def reserve(root: str, attempt_id: str) -> str:
    if not safe_id(attempt_id):
        raise ValueError("attempt-id")
    path = os.path.join(root, attempt_id)
    os.mkdir(path, 0o700)
    _chmod(path, 0o700)
    return path


def write_state(attempt_dir: str, state: str, detail: str, extra: dict | None = None) -> str:
    payload = {"detail": detail, "state": state}
    if extra:
        payload.update(extra)
    body = json.dumps(payload, sort_keys=True).encode("utf-8") + b"\n"
    name = "%02d-%s.json" % (_next_index(attempt_dir), state.lower())
    path = os.path.join(attempt_dir, name)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
    handle = os.open(path, flags, 0o600)
    try:
        _fchmod(handle, 0o600)
        os.write(handle, body)
    finally:
        os.close(handle)
    return path


def _chmod(path: str, mode: int) -> None:
    try:
        os.chmod(path, mode)
    except OSError:
        pass


def _fchmod(handle: int, mode: int) -> None:
    try:
        os.fchmod(handle, mode)
    except OSError:
        pass


def _next_index(attempt_dir: str) -> int:
    numbers = []
    for name in os.listdir(attempt_dir):
        if len(name) > 3 and name[2] == "-" and name[:2].isdigit():
            numbers.append(int(name[:2]))
    return (max(numbers) + 1) if numbers else 1
