#!/usr/bin/env python3
"""Fixed off-box report lines for a future 18B.8 monitoring integration.

Not wired into health_report.py. Emits only closed phrases. Never prints
tokens, paths with secrets, or free-form attempt detail that could leak
credentials. Offline and fail-closed: missing/incomplete state becomes
NOT CONFIGURED or the matching failure phrase.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Keep this module importable without installing offbox on PYTHONPATH.
_HERE = Path(__file__).resolve().parent
_OFFBOX = _HERE / "offbox"
if str(_OFFBOX) not in sys.path:
    sys.path.insert(0, str(_OFFBOX))

import monitoring  # noqa: E402
import provenance  # noqa: E402

DRIVE_NOT_CONFIGURED = "Google Drive: NOT CONFIGURED"
DRIVE_VERIFIED = "Google Drive: VERIFIED"
DRIVE_FAILED = "Google Drive: FAILED"
DRIVE_UNKNOWN = "Google Drive: UNKNOWN"
LAST_ATTEMPT_ABSENT = "Off-box last attempt: ABSENT"
RESTORE_NOT_RUN = "Off-box restore drill: NOT RUN"
CLOUD_SYNC_OFF = "Cloud Sync: OFF"


def _latest_record(attempt_dir: str) -> dict:
    names = []
    for name in os.listdir(attempt_dir):
        if len(name) > 3 and name[2] == "-" and name[:2].isdigit() and name.endswith(".json"):
            names.append(name)
    if not names:
        return {}
    path = os.path.join(attempt_dir, sorted(names)[-1])
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def drive_line(view: dict, record: dict | None = None) -> str:
    state = str(view.get("state", ""))
    transport = str(view.get("transport", ""))
    if state in {"", "ABSENT"}:
        return DRIVE_NOT_CONFIGURED
    record = record or {}
    eligible = False
    try:
        eligible = bool(provenance.production_eligible(record))
    except Exception:
        eligible = False
    if eligible:
        return DRIVE_VERIFIED
    if state == "FAILED":
        return DRIVE_FAILED
    if state in {"UNKNOWN", "ENCRYPTED", "VERIFYING", "VERIFIED"}:
        # Local encrypt, fake/localhost, or incomplete https evidence is not SUCCESS.
        return DRIVE_NOT_CONFIGURED if transport in {"", "fake", "localhost"} else DRIVE_UNKNOWN
    return DRIVE_NOT_CONFIGURED


def last_attempt_line(view: dict) -> str:
    state = str(view.get("state", ""))
    if state in {"", "ABSENT"}:
        return LAST_ATTEMPT_ABSENT
    # Closed vocabulary only.
    allowed = {
        "ENCRYPTED",
        "FAILED",
        "UNKNOWN",
        "VERIFIED",
        "ABSENT",
    }
    label = state if state in allowed else "UNKNOWN"
    return f"Off-box last attempt: {label}"


def restore_line(view: dict) -> str:
    if bool(view.get("restore_drill", False)):
        return "Off-box restore drill: RECORDED"
    return RESTORE_NOT_RUN


def cloud_sync_line() -> str:
    return CLOUD_SYNC_OFF


def render_lines(attempt_dir: str | None) -> list[str]:
    record: dict = {}
    if not attempt_dir or not os.path.isdir(attempt_dir):
        view = {
            "state": "ABSENT",
            "detail": "no-state",
            "download_verified": False,
            "restore_drill": False,
            "transport": "",
        }
    else:
        view = monitoring.latest_view(attempt_dir)
        try:
            record = _latest_record(attempt_dir)
        except (OSError, json.JSONDecodeError, UnicodeError):
            record = {}
    return [
        drive_line(view, record),
        last_attempt_line(view),
        restore_line(view),
        cloud_sync_line(),
    ]


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    attempt_dir = args[0] if args else os.environ.get("LG_STATE_DIR", "")
    for line in render_lines(attempt_dir or None):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
