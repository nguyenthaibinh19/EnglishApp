"""Feature-gated vocabulary + progress sync HTTP adapter.

Contract: ADR-019 (vocabulary) and ADR-022 (progress ingest / changes).

The account server calls :func:`handle_request`. This module does not listen
on a port and does not authenticate by itself beyond reading the Bearer token
through ``account_store.user_for_token``.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from typing import Any, Dict, Optional, Tuple

import account_store
import sync_store

SYNC_PUT = "/api/sync/vocabulary/put"
SYNC_DELETE = "/api/sync/vocabulary/delete"
SYNC_CHANGES = "/api/sync/vocabulary/changes"
SYNC_PROGRESS_ACCEPT = "/api/sync/progress/accept"
SYNC_PROGRESS_CHANGES = "/api/sync/progress/changes"
SYNC_PREFERENCES_GET = "/api/sync/preferences/get"
SYNC_PREFERENCES_PUT = "/api/sync/preferences/put"
SYNC_PATHS = frozenset(
    {
        SYNC_PUT,
        SYNC_DELETE,
        SYNC_CHANGES,
        SYNC_PROGRESS_ACCEPT,
        SYNC_PROGRESS_CHANGES,
        SYNC_PREFERENCES_GET,
        SYNC_PREFERENCES_PUT,
    }
)

SYNC_MAX_BODY = 32_768

_DISABLED = {"error": "Không có chức năng này."}
_INVALID = {"error": "Invalid sync request."}
_UNAUTHORIZED = {"error": "Authentication required."}
_TOO_LARGE = {"error": "Sync request is too large."}
_UNAVAILABLE = {"error": "Sync store unavailable."}

_PUT_KEYS = frozenset(
    {
        "language_code",
        "vocab_id",
        "payload",
        "expected_revision",
        "operation_id",
        "user_id",
    }
)
_PUT_REQUIRED = frozenset(
    {"language_code", "vocab_id", "payload", "expected_revision", "operation_id"}
)
_DELETE_KEYS = frozenset(
    {"language_code", "vocab_id", "expected_revision", "operation_id", "user_id"}
)
_DELETE_REQUIRED = frozenset(
    {"language_code", "vocab_id", "expected_revision", "operation_id"}
)
_CHANGES_KEYS = frozenset({"after_cursor", "limit", "language_code", "user_id"})
_PROGRESS_ACCEPT_KEYS = frozenset({"event", "user_id"})
_PROGRESS_ACCEPT_REQUIRED = frozenset({"event"})
_PROGRESS_CHANGES_KEYS = frozenset({"after_cursor", "limit", "language_code", "user_id"})
_PREFERENCES_GET_KEYS = frozenset({"user_id"})
_PREFERENCES_PUT_KEYS = frozenset({"values", "expected_revision", "user_id"})
_PREFERENCES_PUT_REQUIRED = frozenset({"values", "expected_revision"})


def sync_enabled() -> bool:
    """True only when ``STUDY_SYNC_ENABLED`` is exactly ``1``."""
    return _env("STUDY_SYNC_ENABLED") == "1"


def sync_db_path() -> str:
    """Path that *would* be opened. Does not create the file.

    ``STUDY_SYNC_DIR`` overrides the directory. Otherwise the sync module
    directory is used. This does not move ``accounts.db``.
    """
    explicit = _env("STUDY_SYNC_DIR")
    if explicit:
        return sync_store.db_path(explicit)
    return sync_store.db_path()


def handle_request(path: str, headers, rfile) -> Tuple[int, Dict[str, Any]]:
    """Serve one sync POST. Never includes exception text in the body."""
    route = path or ""
    if route not in SYNC_PATHS:
        return 404, dict(_DISABLED)
    if not sync_enabled():
        return 404, dict(_DISABLED)

    try:
        length = int(headers.get("Content-Length") or 0)
    except (TypeError, ValueError):
        return 400, dict(_INVALID)
    if length > SYNC_MAX_BODY:
        return 413, dict(_TOO_LARGE)
    if length <= 0:
        return 400, dict(_INVALID)

    token = _bearer(headers.get("Authorization") or "")
    try:
        user = account_store.user_for_token(token)
    except Exception as error:
        _log_failure(error)
        return 500, dict(_UNAVAILABLE)
    if not user or "id" not in user:
        return 401, dict(_UNAUTHORIZED)
    try:
        user_id = user["id"]
    except Exception as error:
        _log_failure(error)
        return 500, dict(_UNAVAILABLE)

    try:
        raw = rfile.read(length)
        payload = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeError, AttributeError):
        return 400, dict(_INVALID)
    if not isinstance(payload, dict):
        return 400, dict(_INVALID)

    body = dict(payload)
    body.pop("user_id", None)

    try:
        prepared = _prepare(route, body)
    except sync_store.SyncValidationError:
        return 400, dict(_INVALID)

    connection = None
    try:
        connection = sync_store.connect(sync_db_path())
        if route == SYNC_PUT:
            record = sync_store.put_vocabulary(connection, user_id=user_id, **prepared)
            return 200, _public_record(record)
        if route == SYNC_DELETE:
            record = sync_store.delete_vocabulary(
                connection, user_id=user_id, **prepared
            )
            return 200, _public_record(record)
        if route == SYNC_CHANGES:
            return 200, _changes_page(connection, user_id=user_id, **prepared)
        if route == SYNC_PROGRESS_ACCEPT:
            result = sync_store.accept_learning_attempt(
                connection, user_id=user_id, event=prepared["event"]
            )
            return 200, _public_progress_accept(result)
        if route == SYNC_PREFERENCES_GET:
            return 200, sync_store.get_user_preferences(connection, user_id)
        if route == SYNC_PREFERENCES_PUT:
            return 200, sync_store.put_user_preferences(
                connection,
                user_id=user_id,
                values=prepared["values"],
                expected_revision=prepared["expected_revision"],
            )
        return 200, _progress_changes_page(connection, user_id=user_id, **prepared)
    except sync_store.SyncValidationError:
        return 400, dict(_INVALID)
    except sync_store.SyncConflictError as error:
        return 409, {
            "error": "Sync conflict.",
            "current": _public_current(error.current),
        }
    except Exception as error:
        _log_failure(error)
        return 500, dict(_UNAVAILABLE)
    finally:
        if connection is not None:
            try:
                connection.close()
            except sqlite3.Error:
                pass


def _prepare(route: str, body: Dict[str, Any]) -> Dict[str, Any]:
    if route == SYNC_PUT:
        _require_shape(body, allowed=_PUT_KEYS, required=_PUT_REQUIRED)
        if not isinstance(body["payload"], dict):
            raise sync_store.SyncValidationError("payload must be an object.")
        _require_text(body["language_code"], "language_code")
        _require_text(body["vocab_id"], "vocab_id")
        _require_text(body["operation_id"], "operation_id")
        return {
            "language_code": body["language_code"],
            "vocab_id": body["vocab_id"],
            "payload": body["payload"],
            "expected_revision": body["expected_revision"],
            "operation_id": body["operation_id"],
        }
    if route == SYNC_DELETE:
        _require_shape(body, allowed=_DELETE_KEYS, required=_DELETE_REQUIRED)
        _require_text(body["language_code"], "language_code")
        _require_text(body["vocab_id"], "vocab_id")
        _require_text(body["operation_id"], "operation_id")
        return {
            "language_code": body["language_code"],
            "vocab_id": body["vocab_id"],
            "expected_revision": body["expected_revision"],
            "operation_id": body["operation_id"],
        }
    if route == SYNC_PROGRESS_ACCEPT:
        _require_shape(
            body, allowed=_PROGRESS_ACCEPT_KEYS, required=_PROGRESS_ACCEPT_REQUIRED
        )
        if not isinstance(body["event"], dict):
            raise sync_store.SyncValidationError("event must be an object.")
        return {"event": body["event"]}
    if route == SYNC_PROGRESS_CHANGES:
        _require_shape(body, allowed=_PROGRESS_CHANGES_KEYS, required=frozenset())
        prepared: Dict[str, Any] = {}
        if "after_cursor" in body:
            prepared["after_cursor"] = body["after_cursor"]
        if "limit" in body:
            limit = body["limit"]
            if isinstance(limit, bool) or not isinstance(limit, int):
                raise sync_store.SyncValidationError("limit must be an integer.")
            if limit < 1 or limit > sync_store.PROGRESS_CHANGE_LIMIT:
                raise sync_store.SyncValidationError(
                    "limit is outside the allowed page size."
                )
            prepared["limit"] = limit
        if "language_code" in body:
            _require_text(body["language_code"], "language_code")
            prepared["language_code"] = body["language_code"]
        return prepared
    if route == SYNC_PREFERENCES_GET:
        _require_shape(body, allowed=_PREFERENCES_GET_KEYS, required=frozenset())
        return {}
    if route == SYNC_PREFERENCES_PUT:
        _require_shape(
            body, allowed=_PREFERENCES_PUT_KEYS, required=_PREFERENCES_PUT_REQUIRED
        )
        if not isinstance(body["values"], dict):
            raise sync_store.SyncValidationError("values must be an object.")
        return {
            "values": body["values"],
            "expected_revision": body["expected_revision"],
        }
    _require_shape(body, allowed=_CHANGES_KEYS, required=frozenset())
    prepared = {}
    if "after_cursor" in body:
        prepared["after_cursor"] = body["after_cursor"]
    if "limit" in body:
        limit = body["limit"]
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise sync_store.SyncValidationError("limit must be an integer.")
        if limit < 1 or limit > sync_store.MAX_CHANGE_LIMIT:
            raise sync_store.SyncValidationError("limit is outside the allowed page size.")
        prepared["limit"] = limit
    if "language_code" in body:
        _require_text(body["language_code"], "language_code")
        prepared["language_code"] = body["language_code"]
    return prepared


def _changes_page(connection, *, user_id: int, **prepared) -> Dict[str, Any]:
    after_cursor = prepared.get("after_cursor", 0)
    limit = prepared.get("limit", sync_store.DEFAULT_CHANGE_LIMIT)
    language_code = prepared.get("language_code")
    changes = sync_store.list_vocabulary_changes(
        connection,
        user_id=user_id,
        language_code=language_code,
        after_cursor=after_cursor,
        limit=limit,
    )
    has_more = False
    if len(changes) == limit:
        probe_after = changes[-1].cursor
        probe = sync_store.list_vocabulary_changes(
            connection,
            user_id=user_id,
            language_code=language_code,
            after_cursor=probe_after,
            limit=1,
        )
        has_more = bool(probe)
    next_cursor = changes[-1].cursor if changes else after_cursor
    return {
        "changes": [_public_change(item) for item in changes],
        "next_cursor": next_cursor,
        "has_more": has_more,
        "limit": limit,
    }


def _progress_changes_page(connection, *, user_id: int, **prepared) -> Dict[str, Any]:
    after_cursor = prepared.get("after_cursor", 0)
    limit = prepared.get("limit", sync_store.PROGRESS_CHANGE_LIMIT)
    language_code = prepared.get("language_code")
    changes = sync_store.list_progress_changes(
        connection,
        user_id=user_id,
        language_code=language_code,
        after_cursor=after_cursor,
        limit=limit,
    )
    has_more = False
    if len(changes) == limit:
        probe = sync_store.list_progress_changes(
            connection,
            user_id=user_id,
            language_code=language_code,
            after_cursor=changes[-1].change_id,
            limit=1,
        )
        has_more = bool(probe)
    next_cursor = changes[-1].change_id if changes else after_cursor
    return {
        "changes": [_public_progress_change(item) for item in changes],
        "next_cursor": next_cursor,
        "has_more": has_more,
        "limit": limit,
    }


def _require_text(value: Any, name: str) -> None:
    if not isinstance(value, str):
        raise sync_store.SyncValidationError(f"{name} must be a string.")


def _require_shape(body: Dict[str, Any], *, allowed: frozenset, required: frozenset) -> None:
    unknown = set(body) - allowed
    if unknown:
        raise sync_store.SyncValidationError("Unexpected sync fields.")
    missing = required - set(body)
    if missing:
        raise sync_store.SyncValidationError("Missing sync fields.")


def _public_record(record: sync_store.VocabularySyncRecord) -> Dict[str, Any]:
    return {
        "language_code": record.language_code,
        "vocab_id": record.vocab_id,
        "revision": record.revision,
        "deleted": record.deleted,
        "payload": record.payload,
        "change_cursor": record.change_cursor,
        "operation_id": record.operation_id,
        "expected_revision": record.expected_revision,
    }


def _public_change(change: sync_store.VocabularyChange) -> Dict[str, Any]:
    return {
        "cursor": change.cursor,
        "language_code": change.language_code,
        "vocab_id": change.vocab_id,
        "revision": change.revision,
        "deleted": change.deleted,
        "payload": change.payload,
        "operation_id": change.operation_id,
        "expected_revision": change.expected_revision,
    }


def _public_current(current):
    if current is None:
        return None
    if isinstance(current, dict):
        return {
            key: current[key]
            for key in ("revision", "values", "language_code", "vocab_id", "deleted")
            if key in current
        }
    return {
        "language_code": current.language_code,
        "vocab_id": current.vocab_id,
        "revision": current.revision,
        "deleted": current.deleted,
        "change_cursor": current.change_cursor,
        "expected_revision": current.expected_revision,
    }


def _public_attempt(event: sync_store.LearningAttemptRecord) -> Dict[str, Any]:
    return {
        "event_id": event.event_id,
        "device_id": event.device_id,
        "language_code": event.language_code,
        "vocab_id": event.vocab_id,
        "verdict": event.verdict,
        "mastered": 1 if event.mastered else 0,
        "hint_used": 1 if event.hint_used else 0,
        "occurred_at": event.occurred_at,
        "received_at": event.received_at,
        "server_seq": event.server_seq,
        "algorithm_id": event.algorithm_id,
        "word_snapshot": event.word_snapshot,
        "user_answer": event.user_answer,
        "expected_answer": event.expected_answer,
        "prompt": event.prompt,
    }


def _public_progress_snapshot(snapshot: sync_store.ProgressSnapshot) -> Dict[str, Any]:
    return {
        "seen": snapshot.seen,
        "correct": snapshot.correct,
        "wrong": snapshot.wrong,
        "streak": snapshot.streak,
        "interval_days": snapshot.interval_days,
        "due_at": snapshot.due_at,
        "state_version": snapshot.state_version,
        "algorithm_id": snapshot.algorithm_id,
        "last_event_id": snapshot.last_event_id,
        "last_server_seq": snapshot.last_server_seq,
    }


def _public_progress_accept(result: sync_store.ProgressAcceptResult) -> Dict[str, Any]:
    return {
        "change_id": result.change_id,
        "server_seq": result.server_seq,
        "event": _public_attempt(result.event),
        "progress_after": _public_progress_snapshot(result.progress_after),
    }


def _public_progress_change(change: sync_store.ProgressChange) -> Dict[str, Any]:
    return {
        "change_id": change.change_id,
        "server_seq": change.server_seq,
        "event": _public_attempt(change.event),
        "progress_after": _public_progress_snapshot(change.progress_after),
    }


def _bearer(header: str) -> str:
    value = (header or "").strip()
    if value.lower().startswith("bearer "):
        return value[7:].strip()
    return ""


def _env(name: str) -> str:
    import os

    return (os.getenv(name) or "").strip()


def _log_failure(error: BaseException) -> None:
    sys.stderr.write("[sync] request failed: %s\n" % type(error).__name__)
