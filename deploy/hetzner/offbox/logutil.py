"""One-line status logs. Values that look like secrets are not written."""

from __future__ import annotations

import sys

CAPTURE: list[str] = []
_MARKERS = (
    "AGE-SECRET",
    "ya29.",
    "BEGIN PRIVATE",
    "BEGIN OPENSSH",
    "SQLite format 3",
    "fake-refresh-not-a-real-token",
    "fake-access-token",
    "Bearer ",
    "upload_id=",
    "https://",
    "refresh_token",
    "GOCSPX-",
)


def sanitize(value: object) -> str:
    text = str(value).replace("\r", " ").replace("\n", " ")
    for marker in _MARKERS:
        if marker in text:
            return "redacted"
    if len(text) > 160:
        return "redacted-long"
    return text


def log_event(event: str, **fields: object) -> None:
    parts = ["event=" + sanitize(event)]
    for key in sorted(fields):
        parts.append(sanitize(key) + "=" + sanitize(fields[key]))
    line = " ".join(parts)
    CAPTURE.append(line)
    sys.stderr.write(line + "\n")
    sys.stderr.flush()
