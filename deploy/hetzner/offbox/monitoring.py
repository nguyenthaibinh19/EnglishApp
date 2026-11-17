"""A secret-free view of the latest attempt state for a future monitor."""

from __future__ import annotations

import json
import os
import sys

sys.dont_write_bytecode = True

_HIDDEN = ("session_uri", "authorization", "refresh", "access_token", "bearer")


def latest_view(attempt_dir: str) -> dict:
    names = []
    for name in os.listdir(attempt_dir):
        if len(name) > 3 and name[2] == "-" and name[:2].isdigit() and name.endswith(".json"):
            names.append(name)
    if not names:
        return {"state": "ABSENT", "detail": "no-state", "download_verified": False, "restore_drill": False, "transport": ""}
    path = os.path.join(attempt_dir, sorted(names)[-1])
    payload = json.loads(_read(path).decode("utf-8"))
    view = {
        "detail": str(payload.get("detail", "")),
        "download_verified": bool(payload.get("download_verified", False)),
        "restore_drill": bool(payload.get("restore_drill", False)),
        "state": str(payload.get("state", "")),
        "transport": str(payload.get("transport", "")),
    }
    for key in _HIDDEN:
        if key in view["detail"].lower():
            view["detail"] = "redacted"
    return view


def _read(path: str) -> bytes:
    handle = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0))
    try:
        return os.read(handle, 65536)
    finally:
        os.close(handle)
