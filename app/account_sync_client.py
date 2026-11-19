"""HTTP client for vocabulary + progress sync routes (Bearer session)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

import sync_http


class SyncClientError(RuntimeError):
    def __init__(self, message: str, *, status: Optional[int] = None, body: Any = None):
        super().__init__(message)
        self.status = status
        self.body = body


class SyncConflictClientError(SyncClientError):
    pass


class SyncOfflineError(SyncClientError):
    pass


class AccountSyncClient:
    """Thin wrapper around the sync HTTP API for one session token."""

    def __init__(self, base_url: str, token: str, *, timeout: float = 15.0):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def put_vocabulary(self, body: dict) -> dict:
        return self._post(sync_http.SYNC_PUT, body)

    def delete_vocabulary(self, body: dict) -> dict:
        return self._post(sync_http.SYNC_DELETE, body)

    def vocabulary_changes(
        self, *, after_cursor: int = 0, limit: int = 100, language_code: str = None
    ) -> dict:
        payload: Dict[str, Any] = {"after_cursor": after_cursor, "limit": limit}
        if language_code:
            payload["language_code"] = language_code
        return self._post(sync_http.SYNC_CHANGES, payload)

    def accept_progress(self, event: dict) -> dict:
        return self._post(sync_http.SYNC_PROGRESS_ACCEPT, {"event": event})

    def progress_changes(
        self, *, after_cursor: int = 0, limit: int = 100, language_code: str = None
    ) -> dict:
        payload: Dict[str, Any] = {"after_cursor": after_cursor, "limit": limit}
        if language_code:
            payload["language_code"] = language_code
        return self._post(sync_http.SYNC_PROGRESS_CHANGES, payload)

    def get_preferences(self) -> dict:
        return self._post(sync_http.SYNC_PREFERENCES_GET, {})

    def put_preferences(self, *, values: dict, expected_revision: int) -> dict:
        return self._post(
            sync_http.SYNC_PREFERENCES_PUT,
            {"values": values, "expected_revision": expected_revision},
        )

    def _post(self, path: str, payload: dict) -> dict:
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.base_url + path,
            data=data,
            method="POST",
        )
        request.add_header("Content-Type", "application/json")
        request.add_header("Authorization", "Bearer " + self.token)
        request.add_header("User-Agent", "LanguageGuard-Sync")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            raw = error.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = {"error": raw}
            if error.code == 409:
                raise SyncConflictClientError(
                    str(parsed.get("error") or "Sync conflict."),
                    status=409,
                    body=parsed,
                ) from error
            raise SyncClientError(
                str(parsed.get("error") or f"HTTP {error.code}"),
                status=error.code,
                body=parsed,
            ) from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise SyncOfflineError("Couldn't reach the sync server.") from error
        if not isinstance(body, dict):
            raise SyncClientError("Unexpected sync response.")
        return body
