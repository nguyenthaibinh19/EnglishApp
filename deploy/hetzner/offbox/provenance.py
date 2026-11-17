"""Separate a fake or localhost result from a future production backup.

Older records have no transport field. They are not production evidence.
A restore drill is not download verification.
"""

from __future__ import annotations


def production_eligible(record: dict) -> bool:
    file_id = str(record.get("drive_file_id", ""))
    return (
        record.get("transport") == "https"
        and record.get("state") == "VERIFIED"
        and record.get("download_verified") is True
        and record.get("detail") == "downloaded-sha256"
        and bool(file_id)
        and "/" not in file_id
    )


def restore_eligible(record: dict) -> bool:
    return production_eligible(record) and record.get("restore_drill") is True
