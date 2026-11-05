"""One bounded request from the health collector to the notifier.

The collector does not receive provider secrets. The notifier renders the
provider message from a fixed event and check lines. Client-supplied prose
is rejected. One connection carries one request. A rate ledger limits how
many provider attempts a caller can cause.

Callers are authenticated by the socket group ``lg-notify-client``. The
account server is not in that group. A rejected request does not record
provider acceptance and does not ping the heartbeat.
"""

from __future__ import annotations

import json
import os
import re
import socket
import sys
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import health_notify

VERSION = 1
MAX_FRAME = 8192
MAX_LINES = 12
MAX_DETAIL = 80
ATTEMPT_WINDOW_SECONDS = 1800
ATTEMPT_LIMIT = 12
CHANNELS = ("telegram", "email")
EVENTS = ("check", "report", "backup-incident", "recovery")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_AMSTERDAM = ZoneInfo("Europe/Amsterdam")
CHECK_NAMES = (
    "account_service",
    "public_health",
    "accounts_backup_age",
    "accounts_integrity",
    "disk",
    "sync_flag",
    "sync_database",
    "sync_backup",
    "sync_verify",
)
HEARTBEAT_VALUES = ("not-sent", "withheld", "ping-accepted", "ping-rejected")
RESULT_VALUES = (
    health_notify.PROVIDER_ACCEPTED,
    health_notify.PROVIDER_REJECTED,
    health_notify.NOT_SENT,
)


class HandoffError(ValueError):
    """The request or response was rejected before any provider call."""


@dataclass
class HandoffResult:
    results: dict
    heartbeat: str = "not-sent"
    logs: list[str] = field(default_factory=list)


def _real_date(value: str) -> bool:
    """True for a real ``YYYY-MM-DD`` calendar date. ``2020-02-31`` is false."""
    if not isinstance(value, str) or _DATE.match(value) is None:
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def _civil_date(moment: datetime) -> str:
    """Europe/Amsterdam civil date. Naive values are treated as UTC."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(_AMSTERDAM).date().isoformat()


def validate_request(payload: dict) -> dict:
    """Accept one structured event. Reject free text, paths, and extra fields.

    A heartbeat is valid only on a daily ``report`` that names its civil date.
    ``check``, ``recovery``, and ``backup-incident`` cannot request a ping.
    """
    if not isinstance(payload, dict):
        raise HandoffError("request")
    if set(payload) - {"v", "channels", "event", "lines", "heartbeat", "report_date"}:
        raise HandoffError("request")
    if payload.get("v") != VERSION:
        raise HandoffError("request")
    channels = payload.get("channels")
    heartbeat = payload.get("heartbeat", False)
    if not isinstance(channels, list) or len(channels) > len(CHANNELS):
        raise HandoffError("request")
    if len(set(channels)) != len(channels):
        raise HandoffError("request")
    if any(channel not in CHANNELS for channel in channels):
        raise HandoffError("request")
    if not isinstance(heartbeat, bool):
        raise HandoffError("request")
    event = payload.get("event")
    if event not in EVENTS:
        raise HandoffError("request")
    report_date = payload.get("report_date", "")
    if not isinstance(report_date, str) or (report_date and not _real_date(report_date)):
        raise HandoffError("request")
    if event == "report":
        if not _real_date(report_date):
            raise HandoffError("request")
    elif report_date or heartbeat:
        raise HandoffError("request")
    if not channels and not heartbeat:
        raise HandoffError("request")
    lines = _clean_lines(payload.get("lines", []))
    if channels and not lines:
        raise HandoffError("request")
    return {
        "channels": list(channels),
        "event": event,
        "lines": lines,
        "text": render_message(event, lines),
        "heartbeat": heartbeat,
        "report_date": report_date,
    }


def render_message(event: str, lines: list) -> str:
    """Build the provider body. The caller does not choose this wording."""
    title = {
        "check": "Language Guard health check",
        "report": "Language Guard daily report",
        "backup-incident": "Language Guard backup incident",
        "recovery": "Language Guard recovery",
    }[event]
    body = [title]
    for line in lines:
        body.append(f"{line['name']} {line['status']} {line['detail']}".rstrip())
    return "\n".join(body)


class AttemptLedger:
    """Reserve provider attempts, including each channel's retry budget.

    One request reserves ``channels * health_notify.MAX_ATTEMPTS`` credits
    before any provider call. Unused retries are not refunded. A schema
    rejection and a heartbeat-only retry each reserve one credit against the
    same bound. The bound is not a count of connections.

    A corrupt or unreadable ledger refuses the reservation and is left
    unchanged. Refusal happens before any provider call or heartbeat ping.
    The ledger remembers the civil date of a provider-accepted daily report
    so a later ping can retry without a new send. Only the current
    Europe/Amsterdam date is kept. An older date cannot authorize a ping.
    """

    def __init__(self, path: str = "", now=None, window: int = ATTEMPT_WINDOW_SECONDS, limit: int = ATTEMPT_LIMIT):
        self.path = path
        self.now = time.time if now is None else now
        self.window = window
        self.limit = limit
        self._memory = {"attempts": [], "reports": []}

    def allow(self, count: int = 1) -> bool:
        if count < 1:
            return False
        try:
            with self._locked():
                payload = self._read()
                if payload is None:
                    return False
                moment = float(self.now())
                stamps = [stamp for stamp in payload["attempts"] if moment - stamp < self.window]
                if len(stamps) + count > self.limit:
                    payload["attempts"] = stamps
                    self._write(payload)
                    return False
                stamps.extend([moment] * count)
                payload["attempts"] = stamps
                self._write(payload)
                return True
        except (OSError, TimeoutError, TypeError, ValueError):
            return False

    def note_report(self, report_date: str) -> None:
        """Remember one provider-accepted report date. A ping is not acceptance."""
        if not _real_date(report_date):
            return
        try:
            with self._locked():
                payload = self._read()
                if payload is None:
                    return
                payload["reports"] = [report_date]
                self._write(payload)
        except (OSError, TimeoutError, TypeError, ValueError):
            return

    def retain_current(self, today: str) -> None:
        """Drop every stored report date other than the current civil date."""
        if not _real_date(today):
            return
        try:
            with self._locked():
                payload = self._read()
                if payload is None:
                    return
                payload["reports"] = [item for item in payload["reports"] if item == today]
                self._write(payload)
        except (OSError, TimeoutError, TypeError, ValueError):
            return

    def report_accepted(self, report_date: str) -> bool:
        if not _real_date(report_date):
            return False
        try:
            with self._locked():
                payload = self._read()
                if payload is None:
                    return False
                return report_date in payload["reports"]
        except (OSError, TimeoutError, TypeError, ValueError):
            return False

    @contextmanager
    def _locked(self):
        if not self.path:
            yield
            return
        with _ledger_lock(self.path + ".lock"):
            yield

    def _read(self) -> dict | None:
        if not self.path:
            return {
                "attempts": list(self._memory["attempts"]),
                "reports": list(self._memory["reports"]),
            }
        if not os.path.isfile(self.path):
            return {"attempts": [], "reports": []}
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError, UnicodeError):
            return None
        if not isinstance(payload, dict):
            return None
        attempts = payload.get("attempts")
        reports = payload.get("reports")
        if not isinstance(attempts, list) or not isinstance(reports, list):
            return None
        if any(not isinstance(item, (int, float)) for item in attempts):
            return None
        if any(not _real_date(item) for item in reports):
            return None
        return {"attempts": [float(item) for item in attempts], "reports": list(reports)}

    def _write(self, payload: dict) -> None:
        self._memory = {
            "attempts": list(payload["attempts"]),
            "reports": list(payload["reports"]),
        }
        if not self.path:
            return
        directory = os.path.dirname(self.path) or "."
        os.makedirs(directory, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".attempts-", dir=directory)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        except Exception:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise


def serve_one(
    connection,
    senders: dict,
    secrets: list,
    ping=None,
    sleep=None,
    monotonic=None,
    ledger: AttemptLedger | None = None,
    now=None,
) -> None:
    """Handle one connection. A rejected request is not provider acceptance.

    A heartbeat ping follows a provider-accepted report for the current
    Europe/Amsterdam civil date, or a later retry of that same date after
    the ping itself failed. An older date does not authorize a ping. The
    ping is not proof a person received the message. ``check`` and
    ``recovery`` cannot ping. Ledger refusal writes ``not-sent`` and does
    not call a provider.
    """
    try:
        request = validate_request(read_frame(connection))
    except (HandoffError, OSError, json.JSONDecodeError, UnicodeError):
        if ledger is not None:
            ledger.allow(1)
        _write_quiet(connection, {"v": VERSION, "results": {}, "heartbeat": "not-sent"})
        return
    slots = len(request["channels"]) * health_notify.MAX_ATTEMPTS
    if slots < 1:
        slots = 1
    if ledger is not None and not ledger.allow(slots):
        _write_quiet(connection, {"v": VERSION, "results": {}, "heartbeat": "not-sent"})
        return
    today = _civil_date(datetime.now(timezone.utc) if now is None else now())
    if ledger is not None and request["event"] == "report":
        ledger.retain_current(today)
    current_report = request["event"] == "report" and request["report_date"] == today
    results = {}
    for channel in request["channels"]:
        outcome = health_notify.deliver(
            channel,
            senders.get(channel),
            request["text"],
            secrets=list(secrets or []),
            sleep=sleep or time.sleep,
            monotonic=monotonic or time.monotonic,
        )
        results[channel] = outcome.result if outcome.result in RESULT_VALUES else health_notify.NOT_SENT
    accepted = any(value == health_notify.PROVIDER_ACCEPTED for value in results.values())
    if accepted and current_report and ledger is not None:
        ledger.note_report(today)
    granted = False
    if request["heartbeat"] and current_report:
        if accepted:
            granted = True
        elif not request["channels"] and ledger is not None and ledger.report_accepted(today):
            granted = True
    heartbeat = "not-sent"
    if request["heartbeat"] and not granted:
        heartbeat = "withheld"
    elif granted:
        if ping is None:
            heartbeat = "not-sent"
        else:
            try:
                heartbeat = "ping-accepted" if ping() else "ping-rejected"
            except Exception:
                heartbeat = "ping-rejected"
    write_frame(connection, {"v": VERSION, "results": results, "heartbeat": heartbeat})


def transact(
    path: str,
    channels: list,
    event: str,
    lines: list,
    *,
    heartbeat: bool = False,
    report_date: str = "",
    timeout: float = 20.0,
) -> HandoffResult:
    """Send one request. A transport failure is ``NOT_SENT``, not acceptance."""
    request = validate_request(
        {
            "v": VERSION,
            "channels": list(channels),
            "event": event,
            "lines": list(lines),
            "heartbeat": bool(heartbeat),
            "report_date": report_date,
        }
    )
    connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        connection.settimeout(timeout)
        connection.connect(path)
        wire = {
            "v": VERSION,
            "channels": request["channels"],
            "event": request["event"],
            "lines": request["lines"],
            "heartbeat": request["heartbeat"],
        }
        if request["report_date"]:
            wire["report_date"] = request["report_date"]
        write_frame(connection, wire)
        payload = read_frame(connection)
    except (OSError, HandoffError, json.JSONDecodeError, UnicodeError):
        return _not_sent(request["channels"])
    finally:
        connection.close()
    return _parse_response(request["channels"], payload)


def write_frame(connection, payload: dict) -> None:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    if len(raw) > MAX_FRAME:
        raise HandoffError("frame")
    connection.sendall(len(raw).to_bytes(4, "big") + raw)


def read_frame(connection) -> dict:
    header = _read_exact(connection, 4)
    length = int.from_bytes(header, "big")
    if length <= 0 or length > MAX_FRAME:
        raise HandoffError("frame")
    raw = _read_exact(connection, length)
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise HandoffError("frame")
    return payload


def _parse_response(channels: list, payload: dict) -> HandoffResult:
    if not isinstance(payload, dict) or payload.get("v") != VERSION:
        return _not_sent(channels)
    raw_results = payload.get("results")
    if not isinstance(raw_results, dict):
        return _not_sent(channels)
    results = {}
    logs = []
    for channel in channels:
        value = raw_results.get(channel, health_notify.NOT_SENT)
        if value not in RESULT_VALUES:
            value = health_notify.NOT_SENT
        results[channel] = value
        logs.append(f"channel={channel} result={value}")
    heartbeat = payload.get("heartbeat", "not-sent")
    if heartbeat not in HEARTBEAT_VALUES:
        heartbeat = "not-sent"
    return HandoffResult(results, heartbeat, logs)


def _clean_lines(lines) -> list:
    if not isinstance(lines, list) or len(lines) > MAX_LINES:
        raise HandoffError("request")
    cleaned = []
    for line in lines:
        if not isinstance(line, dict) or set(line) - {"name", "status", "detail"}:
            raise HandoffError("request")
        name = line.get("name")
        status = line.get("status")
        detail = line.get("detail", "")
        if name not in CHECK_NAMES or status not in {
            "VERIFIED",
            "SKIPPED",
            "NOT INSTALLED",
            "UNKNOWN",
            "WARNING",
            "FAILED",
            "OK",
        }:
            raise HandoffError("request")
        if not isinstance(detail, str) or len(detail) > MAX_DETAIL or any(ord(char) < 32 for char in detail):
            raise HandoffError("request")
        cleaned.append({"name": name, "status": status, "detail": detail})
    return cleaned


def _not_sent(channels: list) -> HandoffResult:
    results = {channel: health_notify.NOT_SENT for channel in channels}
    logs = [f"channel={channel} result={health_notify.NOT_SENT}" for channel in channels]
    return HandoffResult(results, "not-sent", logs)


def _write_quiet(connection, payload: dict) -> None:
    try:
        write_frame(connection, payload)
    except (OSError, HandoffError):
        return


@contextmanager
def _ledger_lock(path: str, timeout: float = 5.0):
    """Exclusive lock released by the operating system when the process exits."""
    if os.path.islink(path):
        raise OSError("ledger lock")
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_BINARY", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    try:
        if os.fstat(descriptor).st_size == 0:
            os.write(descriptor, b"\0")
        os.lseek(descriptor, 0, os.SEEK_SET)
        deadline = time.monotonic() + timeout
        if sys.platform == "win32":
            import msvcrt

            while True:
                try:
                    os.lseek(descriptor, 0, os.SEEK_SET)
                    msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError("ledger lock")
                    time.sleep(0.01)
            try:
                yield
            finally:
                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            while True:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError("ledger lock")
                    time.sleep(0.01)
            try:
                yield
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)


def _read_exact(connection, count: int) -> bytes:
    chunks = []
    remaining = count
    while remaining:
        piece = connection.recv(remaining)
        if not piece:
            raise HandoffError("frame")
        chunks.append(piece)
        remaining -= len(piece)
    return b"".join(chunks)
