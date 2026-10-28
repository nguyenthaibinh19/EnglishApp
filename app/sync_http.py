"""Feature-gated vocabulary sync HTTP adapter (Phase 18B.1).

Contract: ``.ai/decisions/ADR-019-vocabulary-sync-http.md``.

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
SYNC_PATHS = frozenset({SYNC_PUT, SYNC_DELETE, SYNC_CHANGES})

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
        return 200, _changes_page(connection, user_id=user_id, **prepared)
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
    _require_shape(body, allowed=_CHANGES_KEYS, required=frozenset())
    prepared: Dict[str, Any] = {}
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


def _public_current(current: Optional[sync_store.VocabularySyncRecord]):
    if current is None:
        return None
    return {
        "language_code": current.language_code,
        "vocab_id": current.vocab_id,
        "revision": current.revision,
        "deleted": current.deleted,
        "change_cursor": current.change_cursor,
        "expected_revision": current.expected_revision,
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
