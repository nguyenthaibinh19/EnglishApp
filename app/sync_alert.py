"""Alert events for study_sync backup incidents.

Payloads are three fields: event type, UTC timestamp, and status. A test sink
can record those fields. No production notification destination is built in.
A log file is not a production page.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping, Optional, Protocol

EVENT_BACKUP_FAILED = "sync_backup_failed"
EVENT_RETENTION_WARNING = "sync_backup_retention_warning"
STATUS_FAILED = "failed"
STATUS_WARNING = "warning"
ALERT_NOT_DELIVERED = "study_sync alert was not delivered"
TEST_SINK_NAME = "test"

_EVENTS = {
    EVENT_BACKUP_FAILED: STATUS_FAILED,
    EVENT_RETENTION_WARNING: STATUS_WARNING,
}
_PAYLOAD_KEYS = ("event_type", "timestamp", "status")


class SyncAlertError(Exception):
    """The alert was not accepted by a sink."""


@dataclass(frozen=True)
class SyncAlertEvent:
    """Safe status metadata. No paths, tokens, or exception text."""

    event_type: str
    timestamp: str
    status: str

    def as_dict(self) -> dict:
        payload = {
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "status": self.status,
        }
        if tuple(payload) != _PAYLOAD_KEYS:
            raise SyncAlertError(ALERT_NOT_DELIVERED)
        return payload


class AlertSink(Protocol):
    def emit(self, event: SyncAlertEvent) -> None:
        """Accept one event. Raise on any failure to accept it."""


class RecordingSink:
    """In-memory test sink. Holds delivered payloads and nothing else."""

    def __init__(self) -> None:
        self.events: list[dict] = []

    def emit(self, event: SyncAlertEvent) -> None:
        if not isinstance(event, SyncAlertEvent):
            raise SyncAlertError(ALERT_NOT_DELIVERED)
        self.events.append(event.as_dict())


class TestRecordSink:
    """File sink for a local test process.

    ``STUDY_SYNC_ALERT_SINK=test`` selects it. The file is a test double, not
    an operator page.
    """

    def __init__(self, path: str) -> None:
        if not path or not str(path).strip():
            raise SyncAlertError(ALERT_NOT_DELIVERED)
        self._path = str(path)

    def emit(self, event: SyncAlertEvent) -> None:
        if not isinstance(event, SyncAlertEvent):
            raise SyncAlertError(ALERT_NOT_DELIVERED)
        line = json.dumps(event.as_dict(), separators=(",", ":"))
        if set(json.loads(line)) != set(_PAYLOAD_KEYS):
            raise SyncAlertError(ALERT_NOT_DELIVERED)
        with open(self._path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")


def make_event(event_type: str, *, now: Optional[datetime] = None) -> SyncAlertEvent:
    """Build one allowed event. The status is fixed by the event type."""
    status = _EVENTS.get(event_type)
    if status is None:
        raise SyncAlertError(ALERT_NOT_DELIVERED)
    moment = now if now is not None else datetime.now(timezone.utc)
    if moment.tzinfo is None:
        raise SyncAlertError(ALERT_NOT_DELIVERED)
    timestamp = moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return SyncAlertEvent(event_type, timestamp, status)


def load_sink(environ: Mapping[str, str]) -> Optional[AlertSink]:
    """Return a sink, or None when delivery is not configured.

    Only the test sink name is recognized. Any other name fails closed so a
    webhook, address, or secret in the environment is not treated as delivered
    and is not copied into an error.
    """
    name = (environ.get("STUDY_SYNC_ALERT_SINK") or "").strip()
    if not name:
        return None
    if name == TEST_SINK_NAME:
        return TestRecordSink(environ.get("STUDY_SYNC_ALERT_RECORD") or "")
    raise SyncAlertError(ALERT_NOT_DELIVERED)


def dispatch(event: SyncAlertEvent, sink: Optional[AlertSink]) -> None:
    """Hand one event to ``sink``. None and any sink error are not delivery."""
    if sink is None:
        raise SyncAlertError(ALERT_NOT_DELIVERED)
    try:
        sink.emit(event)
    except SyncAlertError:
        raise
    except Exception as error:
        raise SyncAlertError(ALERT_NOT_DELIVERED) from error
