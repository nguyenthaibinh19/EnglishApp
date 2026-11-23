"""Per-account local SQLite store for signed-in study sync (Phase 18C.1).

Guest ``languages/{code}/`` files stay untouched. Login never copies machine-global
vocabulary or progress into an account database.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

import config
from srs import apply_review_to_stats, parse_utc, to_utc_iso, utc_now
from vocab_identity import is_vocab_id

DB_FILE = "account_study.db"
SCHEMA_VERSION = 1
ALGORITHM_LADDER_V2 = "ladder-v2"

LEGACY_DISP_IMPORTED = "imported"
LEGACY_DISP_SKIPPED = "skipped_no_vocab_id"
LEGACY_DISP_UNREADABLE = "unreadable"
LEGACY_DISP_CONFLICT = "source_conflict"
LEGACY_DISP_OVERLAP = "overlap_pending"
LEGACY_DISP_SKIPPED_OVERLAP = "skipped_overlap"
LEGACY_CONFLICT_KIND = "legacy_attempt"

STATUS_SYNCED = "Synced"
STATUS_PENDING = "Pending"
STATUS_OFFLINE = "Offline"
STATUS_CONFLICT = "Conflict"
STATUS_UNAVAILABLE = "Unavailable"

OUTBOX_PENDING = "pending"
OUTBOX_ACKED = "acked"
OUTBOX_SUPERSEDED = "superseded"
OUTBOX_CONFLICT = "conflict"
OUTBOX_KIND_VOCAB_PUT = "vocab_put"
OUTBOX_KIND_VOCAB_DELETE = "vocab_delete"
OUTBOX_KIND_PROGRESS = "progress"


class AccountLocalError(Exception):
    """Base local account-store error."""


class AccountLocalConflict(AccountLocalError):
    """Integrity conflict that blocks Synced."""


@dataclass(frozen=True)
class SyncStatusSnapshot:
    status: str
    detail: str
    vocab_cursor: int
    progress_cursor: int
    vocab_caught_up: bool
    progress_caught_up: bool
    pending_vocab: int
    pending_progress: int
    conflict: bool
    offline: bool


_thread_local = threading.local()


def account_dir(user_id: int, data_root: Optional[str] = None) -> str:
    root = data_root if data_root is not None else config.data_dir()
    return os.path.join(root, "accounts", str(int(user_id)))


def db_path(user_id: int, data_root: Optional[str] = None) -> str:
    return os.path.join(account_dir(user_id, data_root), DB_FILE)


def guest_language_dir(language_code: str, data_root: Optional[str] = None) -> str:
    """Machine-global guest path — never written by signed-in sync."""
    root = data_root if data_root is not None else config.data_dir()
    return os.path.join(root, "languages", str(language_code).strip().lower())


def connect(user_id: int, data_root: Optional[str] = None) -> sqlite3.Connection:
    path = db_path(user_id, data_root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    connection = sqlite3.connect(path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    init_schema(connection)
    return connection


def init_schema(connection: sqlite3.Connection) -> None:
    connection.execute("BEGIN IMMEDIATE")
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS vocabulary_entities (
                language_code TEXT NOT NULL,
                vocab_id TEXT NOT NULL,
                revision INTEGER NOT NULL,
                deleted INTEGER NOT NULL DEFAULT 0,
                payload_json TEXT,
                expected_revision INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (language_code, vocab_id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS learning_attempts (
                event_id TEXT PRIMARY KEY,
                device_id TEXT NOT NULL,
                language_code TEXT NOT NULL,
                vocab_id TEXT NOT NULL,
                verdict TEXT NOT NULL,
                mastered INTEGER NOT NULL,
                hint_used INTEGER NOT NULL,
                occurred_at TEXT NOT NULL,
                received_at TEXT,
                server_seq INTEGER,
                algorithm_id TEXT NOT NULL,
                word_snapshot TEXT NOT NULL,
                user_answer TEXT NOT NULL,
                expected_answer TEXT NOT NULL,
                prompt TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'local'
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS progress_confirmed (
                language_code TEXT NOT NULL,
                vocab_id TEXT NOT NULL,
                seen INTEGER NOT NULL,
                correct INTEGER NOT NULL,
                wrong INTEGER NOT NULL,
                streak INTEGER NOT NULL,
                interval_days INTEGER NOT NULL,
                due_at TEXT NOT NULL,
                state_version INTEGER NOT NULL,
                algorithm_id TEXT NOT NULL,
                last_event_id TEXT NOT NULL,
                last_server_seq INTEGER NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (language_code, vocab_id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS progress_provisional (
                language_code TEXT NOT NULL,
                vocab_id TEXT NOT NULL,
                seen INTEGER NOT NULL,
                correct INTEGER NOT NULL,
                wrong INTEGER NOT NULL,
                streak INTEGER NOT NULL,
                interval_days INTEGER NOT NULL,
                due_at TEXT NOT NULL,
                algorithm_id TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (language_code, vocab_id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS outbox (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,
                operation_id TEXT NOT NULL UNIQUE,
                event_id TEXT,
                language_code TEXT,
                vocab_id TEXT,
                payload_json TEXT NOT NULL,
                state TEXT NOT NULL,
                ack_state_version INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_activity (
                day_key TEXT NOT NULL,
                language_code TEXT NOT NULL,
                asked_json TEXT NOT NULL,
                correct_json TEXT NOT NULL,
                wrong_json TEXT NOT NULL,
                reading_done INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (day_key, language_code)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sync_conflicts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,
                detail TEXT NOT NULL,
                created_at TEXT NOT NULL,
                resolved INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS account_preferences (
                key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL,
                revision INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS legacy_import_consent (
                language_code TEXT NOT NULL,
                source_kind TEXT NOT NULL,
                consented_at TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (language_code, source_kind)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS legacy_attempt_consent (
                language_code TEXT NOT NULL,
                file_identity TEXT NOT NULL,
                consented_at TEXT NOT NULL,
                revoked INTEGER NOT NULL DEFAULT 0,
                note TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (language_code, file_identity)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS legacy_import_source (
                language_code TEXT NOT NULL,
                file_identity TEXT NOT NULL,
                canonical_path TEXT NOT NULL,
                high_water INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (language_code, file_identity)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS legacy_import_ledger (
                file_identity TEXT NOT NULL,
                offset INTEGER NOT NULL,
                line_sha256 TEXT NOT NULL,
                disposition TEXT NOT NULL,
                event_id TEXT,
                created_at TEXT NOT NULL,
                PRIMARY KEY (file_identity, offset)
            )
            """
        )
        _meta_set(connection, "schema_version", str(SCHEMA_VERSION))
        if not _meta_get(connection, "device_id"):
            _meta_set(connection, "device_id", str(uuid.uuid4()))
        for key, default in (
            ("vocab_cursor", "0"),
            ("progress_cursor", "0"),
            ("vocab_caught_up", "0"),
            ("progress_caught_up", "0"),
            ("offline", "0"),
        ):
            if _meta_get(connection, key) is None:
                _meta_set(connection, key, default)
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise


class AccountLocalStore:
    """Durable per-account study store used by the sync engine and demo."""

    def __init__(self, user_id: int, data_root: Optional[str] = None):
        self.user_id = int(user_id)
        self.data_root = data_root
        self._lock = threading.RLock()
        self._conn = connect(self.user_id, data_root)

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except sqlite3.Error:
                pass

    @property
    def path(self) -> str:
        return db_path(self.user_id, self.data_root)

    def device_id(self) -> str:
        with self._lock:
            return _meta_get(self._conn, "device_id") or ""

    def set_offline(self, offline: bool) -> None:
        with self._lock:
            _meta_set(self._conn, "offline", "1" if offline else "0")
            self._conn.commit()

    def set_server_sync_unavailable(self, unavailable: bool) -> None:
        """Record Sync-route availability for UI/status within the active session.

        Outbox rows stay pending — this is not Synced and not a completed upload.
        ``AccountSyncEngine`` clears this flag when a new engine/session starts so a
        future authorized Sync pilot can probe once; a still-disabled server returns
        to unavailable without a retry loop.
        """
        with self._lock:
            _meta_set(
                self._conn,
                "server_sync_unavailable",
                "1" if unavailable else "0",
            )
            self._conn.commit()

    def server_sync_unavailable(self) -> bool:
        with self._lock:
            return _meta_get(self._conn, "server_sync_unavailable") == "1"

    def status(self) -> SyncStatusSnapshot:
        with self._lock:
            pending_vocab = self._count_pending(
                (OUTBOX_KIND_VOCAB_PUT, OUTBOX_KIND_VOCAB_DELETE)
            )
            pending_progress = self._count_pending((OUTBOX_KIND_PROGRESS,))
            conflict = self._has_open_conflict()
            offline = _meta_get(self._conn, "offline") == "1"
            unavailable = _meta_get(self._conn, "server_sync_unavailable") == "1"
            vocab_caught = _meta_get(self._conn, "vocab_caught_up") == "1"
            progress_caught = _meta_get(self._conn, "progress_caught_up") == "1"
            vocab_cursor = int(_meta_get(self._conn, "vocab_cursor") or "0")
            progress_cursor = int(_meta_get(self._conn, "progress_cursor") or "0")
            prefs = {}
            for row in self._conn.execute(
                "SELECT key, value_json FROM account_preferences "
                "WHERE key IN ('_prefs_dirty', '_prefs_conflict')"
            ).fetchall():
                try:
                    prefs[str(row["key"])] = json.loads(row["value_json"])
                except json.JSONDecodeError:
                    continue
            prefs_dirty = bool(prefs.get("_prefs_dirty"))
            prefs_conflict = bool(prefs.get("_prefs_conflict"))
            if conflict or prefs_conflict:
                status, detail = STATUS_CONFLICT, "Conflict / Action required"
            elif unavailable:
                # Distinct from Pending/Synced — production Sync flag may be OFF (404).
                status, detail = (
                    STATUS_UNAVAILABLE,
                    "Data saved locally; not uploaded",
                )
            elif offline:
                status, detail = STATUS_OFFLINE, "Server unreachable"
            elif (
                pending_vocab
                or pending_progress
                or prefs_dirty
                or not vocab_caught
                or not progress_caught
            ):
                status, detail = STATUS_PENDING, "Upload or download in progress"
            else:
                status, detail = STATUS_SYNCED, "Caught up"
            return SyncStatusSnapshot(
                status=status,
                detail=detail,
                vocab_cursor=vocab_cursor,
                progress_cursor=progress_cursor,
                vocab_caught_up=vocab_caught,
                progress_caught_up=progress_caught,
                pending_vocab=pending_vocab,
                pending_progress=pending_progress,
                conflict=conflict or prefs_conflict,
                offline=offline,
            )

    # --- Vocabulary ---

    def upsert_vocabulary(
        self,
        *,
        language_code: str,
        vocab_id: str,
        payload: dict,
        expected_revision: Optional[int] = None,
    ) -> Optional[str]:
        """Persist a local vocabulary mutation and coalesce the upload outbox.

        ``revision`` on the entity remains the last known *server* revision until
        acknowledgement or download. Repeated offline edits supersede prior pending
        ops and upload once against that base revision (ADR-018/019).
        Returns the pending operation_id, or ``None`` when no upload is required.
        """
        language_code = language_code.strip().lower()
        if not is_vocab_id(vocab_id):
            raise AccountLocalError("Invalid vocabulary UUID.")
        body = dict(payload)
        body["id"] = vocab_id
        stamp = to_utc_iso(utc_now())
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._conn.execute(
                    "SELECT revision, deleted, payload_json FROM vocabulary_entities "
                    "WHERE language_code = ? AND vocab_id = ?",
                    (language_code, vocab_id),
                ).fetchone()
                server_revision = self._server_base_revision_unlocked(row)
                if expected_revision is None:
                    expected_revision = server_revision
                elif int(expected_revision) != server_revision:
                    raise AccountLocalConflict(
                        "expected_revision does not match the last known server revision."
                    )
                payload_json = json.dumps(body, ensure_ascii=False, sort_keys=True)
                self._conn.execute(
                    """
                    INSERT INTO vocabulary_entities (
                        language_code, vocab_id, revision, deleted, payload_json,
                        expected_revision, updated_at
                    ) VALUES (?, ?, ?, 0, ?, ?, ?)
                    ON CONFLICT(language_code, vocab_id) DO UPDATE SET
                        payload_json = excluded.payload_json,
                        expected_revision = excluded.expected_revision,
                        deleted = 0,
                        updated_at = excluded.updated_at
                    """,
                    (
                        language_code,
                        vocab_id,
                        server_revision,
                        payload_json,
                        expected_revision,
                        stamp,
                    ),
                )
                self._supersede_pending_vocab_unlocked(language_code, vocab_id, stamp)
                operation_id = str(uuid.uuid4())
                self._enqueue_outbox(
                    kind=OUTBOX_KIND_VOCAB_PUT,
                    operation_id=operation_id,
                    language_code=language_code,
                    vocab_id=vocab_id,
                    payload={
                        "language_code": language_code,
                        "vocab_id": vocab_id,
                        "payload": body,
                        "expected_revision": expected_revision,
                        "operation_id": operation_id,
                    },
                    stamp=stamp,
                )
                _meta_set(self._conn, "vocab_caught_up", "0")
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise
        return operation_id

    def delete_vocabulary(
        self, *, language_code: str, vocab_id: str, expected_revision: Optional[int] = None
    ) -> Optional[str]:
        """Tombstone locally and coalesce delete upload against the server base revision.

        If the entity was never acknowledged on the server (base revision 0), cancel
        pending puts and leave a local tombstone with no upload — the server never
        received the create.
        """
        language_code = language_code.strip().lower()
        stamp = to_utc_iso(utc_now())
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._conn.execute(
                    "SELECT revision, deleted, payload_json FROM vocabulary_entities "
                    "WHERE language_code = ? AND vocab_id = ?",
                    (language_code, vocab_id),
                ).fetchone()
                if row is None or int(row["deleted"]):
                    raise AccountLocalError("Vocabulary entry not found.")
                server_revision = self._server_base_revision_unlocked(row)
                if expected_revision is None:
                    expected_revision = server_revision
                elif int(expected_revision) != server_revision:
                    raise AccountLocalConflict(
                        "expected_revision does not match the last known server revision."
                    )
                self._conn.execute(
                    """
                    UPDATE vocabulary_entities
                    SET deleted = 1, expected_revision = ?, updated_at = ?
                    WHERE language_code = ? AND vocab_id = ?
                    """,
                    (expected_revision, stamp, language_code, vocab_id),
                )
                self._supersede_pending_vocab_unlocked(language_code, vocab_id, stamp)
                operation_id = None
                if server_revision > 0:
                    operation_id = str(uuid.uuid4())
                    self._enqueue_outbox(
                        kind=OUTBOX_KIND_VOCAB_DELETE,
                        operation_id=operation_id,
                        language_code=language_code,
                        vocab_id=vocab_id,
                        payload={
                            "language_code": language_code,
                            "vocab_id": vocab_id,
                            "expected_revision": expected_revision,
                            "operation_id": operation_id,
                        },
                        stamp=stamp,
                    )
                    _meta_set(self._conn, "vocab_caught_up", "0")
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise
        return operation_id

    def list_vocabulary(self, language_code: str) -> List[Dict[str, Any]]:
        language_code = language_code.strip().lower()
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT vocab_id, revision, payload_json
                FROM vocabulary_entities
                WHERE language_code = ? AND deleted = 0
                ORDER BY vocab_id
                """,
                (language_code,),
            ).fetchall()
        out = []
        for row in rows:
            payload = json.loads(row["payload_json"] or "{}")
            payload["id"] = row["vocab_id"]
            payload["_revision"] = int(row["revision"])
            out.append(payload)
        return out

    def apply_vocab_server_record(self, record: dict) -> None:
        """Apply an acknowledged put/delete or downloaded change to local entities."""
        language_code = str(record["language_code"]).strip().lower()
        vocab_id = str(record["vocab_id"])
        revision = int(record["revision"])
        deleted = bool(record.get("deleted"))
        payload = record.get("payload")
        expected_revision = int(record.get("expected_revision") or max(revision - 1, 0))
        stamp = to_utc_iso(utc_now())
        payload_json = (
            None
            if deleted or payload is None
            else json.dumps(payload, ensure_ascii=False, sort_keys=True)
        )
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO vocabulary_entities (
                    language_code, vocab_id, revision, deleted, payload_json,
                    expected_revision, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(language_code, vocab_id) DO UPDATE SET
                    revision = excluded.revision,
                    deleted = excluded.deleted,
                    payload_json = excluded.payload_json,
                    expected_revision = excluded.expected_revision,
                    updated_at = excluded.updated_at
                """,
                (
                    language_code,
                    vocab_id,
                    revision,
                    1 if deleted else 0,
                    payload_json,
                    expected_revision,
                    stamp,
                ),
            )
            self._conn.commit()

    def apply_vocab_changes_page(
        self, changes: List[dict], *, next_cursor: int, has_more: bool
    ) -> None:
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                cursor = int(_meta_get(self._conn, "vocab_cursor") or "0")
                last = cursor
                for item in changes:
                    change_cursor = int(item.get("cursor") or item.get("change_cursor") or 0)
                    if change_cursor <= cursor:
                        continue
                    if change_cursor <= last and last != cursor:
                        raise AccountLocalConflict("Vocabulary change page order invalid.")
                    self._apply_remote_vocab_change_unlocked(item)
                    last = change_cursor
                if changes:
                    _meta_set(self._conn, "vocab_cursor", str(last))
                elif next_cursor == cursor:
                    pass
                _meta_set(self._conn, "vocab_caught_up", "0" if has_more else "1")
                if not changes and not has_more:
                    _meta_set(self._conn, "vocab_caught_up", "1")
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def acknowledge_vocab_outbox(self, operation_id: str, record: dict) -> None:
        """Ack one upload. Preserve any newer local mutation and re-queue it."""
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                self._acknowledge_vocab_outbox_unlocked(operation_id, record)
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def note_accepted_vocab_upload(
        self, operation_id: str, uploaded_payload: dict, record: dict
    ) -> None:
        """Consume a late HTTP acceptance after the local op was superseded.

        Advances the server revision watermark and rebases any newer pending
        mutation for the same vocab_id so Y is not lost and a false conflict is
        not introduced solely because X's acknowledgement arrived late.
        """
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                stamp = to_utc_iso(utc_now())
                language_code = str(record["language_code"]).strip().lower()
                vocab_id = str(record["vocab_id"])
                # Mark the historical operation row if still visible.
                self._conn.execute(
                    """
                    UPDATE outbox SET state = ?, updated_at = ?
                    WHERE operation_id = ? AND state IN (?, ?)
                    """,
                    (
                        OUTBOX_ACKED,
                        stamp,
                        operation_id,
                        OUTBOX_PENDING,
                        OUTBOX_SUPERSEDED,
                    ),
                )
                local = self._conn.execute(
                    "SELECT revision, deleted, payload_json FROM vocabulary_entities "
                    "WHERE language_code = ? AND vocab_id = ?",
                    (language_code, vocab_id),
                ).fetchone()
                pending = self._pending_vocab_unlocked(language_code, vocab_id)
                # Outbox put payloads include "payload"; delete payloads do not.
                uploaded_delete = "payload" not in uploaded_payload
                uploaded_body = uploaded_payload.get("payload")
                remote_fp = _payload_fingerprint(record.get("payload"))
                uploaded_fp = _payload_fingerprint(uploaded_body)
                acceptance_matches_upload = bool(record.get("deleted")) == uploaded_delete and (
                    uploaded_delete or remote_fp == uploaded_fp
                )
                if not acceptance_matches_upload:
                    # Unexpected: do not clobber local state from a mismatched late ack.
                    self._conn.execute("COMMIT")
                    return

                base = int(record["revision"])
                if pending is None and local is not None:
                    # No newer local intent — adopt the accepted tip.
                    self._apply_vocab_entity_unlocked(record)
                    self._conn.execute("COMMIT")
                    return

                # Newer local intent exists (Y). Keep Y; only advance watermark + rebase.
                if local is not None:
                    self._conn.execute(
                        """
                        UPDATE vocabulary_entities
                        SET revision = ?, expected_revision = ?, updated_at = ?
                        WHERE language_code = ? AND vocab_id = ?
                        """,
                        (base, base, stamp, language_code, vocab_id),
                    )
                if pending is not None:
                    pending_payload = json.loads(pending["payload_json"])
                    pending_payload["expected_revision"] = base
                    self._conn.execute(
                        """
                        UPDATE outbox
                        SET payload_json = ?, updated_at = ?
                        WHERE id = ? AND state = ?
                        """,
                        (
                            json.dumps(
                                pending_payload, ensure_ascii=False, sort_keys=True
                            ),
                            stamp,
                            int(pending["id"]),
                            OUTBOX_PENDING,
                        ),
                    )
                    _meta_set(self._conn, "vocab_caught_up", "0")
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def _acknowledge_vocab_outbox_unlocked(self, operation_id: str, record: dict) -> None:
        stamp = to_utc_iso(utc_now())
        language_code = str(record["language_code"]).strip().lower()
        vocab_id = str(record["vocab_id"])
        local = self._conn.execute(
            "SELECT revision, deleted, payload_json FROM vocabulary_entities "
            "WHERE language_code = ? AND vocab_id = ?",
            (language_code, vocab_id),
        ).fetchone()
        local_deleted = bool(local and int(local["deleted"]))
        local_payload = None
        if local and local["payload_json"]:
            local_payload = json.loads(local["payload_json"])

        dirty_after_ack = False
        if local is not None:
            if local_deleted != bool(record.get("deleted")):
                dirty_after_ack = True
            elif not local_deleted:
                dirty_after_ack = _payload_fingerprint(
                    local_payload
                ) != _payload_fingerprint(record.get("payload"))

        if dirty_after_ack and local is not None:
            # Keep the latest local mutation; only advance server revision.
            self._conn.execute(
                """
                UPDATE vocabulary_entities
                SET revision = ?, expected_revision = ?, updated_at = ?
                WHERE language_code = ? AND vocab_id = ?
                """,
                (
                    int(record["revision"]),
                    int(record["revision"]),
                    stamp,
                    language_code,
                    vocab_id,
                ),
            )
        else:
            self._apply_vocab_entity_unlocked(record)

        self._conn.execute(
            """
            UPDATE outbox SET state = ?, updated_at = ?
            WHERE operation_id = ? AND state = ?
            """,
            (OUTBOX_ACKED, stamp, operation_id, OUTBOX_PENDING),
        )

        if dirty_after_ack and local is not None:
            self._supersede_pending_vocab_unlocked(language_code, vocab_id, stamp)
            base = int(record["revision"])
            if local_deleted:
                if base > 0:
                    new_op = str(uuid.uuid4())
                    self._enqueue_outbox(
                        kind=OUTBOX_KIND_VOCAB_DELETE,
                        operation_id=new_op,
                        language_code=language_code,
                        vocab_id=vocab_id,
                        payload={
                            "language_code": language_code,
                            "vocab_id": vocab_id,
                            "expected_revision": base,
                            "operation_id": new_op,
                        },
                        stamp=stamp,
                    )
                    _meta_set(self._conn, "vocab_caught_up", "0")
            else:
                new_op = str(uuid.uuid4())
                body = dict(local_payload or {})
                body["id"] = vocab_id
                self._enqueue_outbox(
                    kind=OUTBOX_KIND_VOCAB_PUT,
                    operation_id=new_op,
                    language_code=language_code,
                    vocab_id=vocab_id,
                    payload={
                        "language_code": language_code,
                        "vocab_id": vocab_id,
                        "payload": body,
                        "expected_revision": base,
                        "operation_id": new_op,
                    },
                    stamp=stamp,
                )
                _meta_set(self._conn, "vocab_caught_up", "0")

    # --- Progress / attempts ---

    def record_learning_attempt(
        self,
        *,
        language_code: str,
        vocab_id: str,
        verdict: str,
        hint_used: bool,
        word_snapshot: str,
        user_answer: str,
        expected_answer: str,
        prompt: str,
        occurred_at: Optional[str] = None,
        event_id: Optional[str] = None,
    ) -> str:
        """Commit attempt + outbox + provisional + day bucket in one transaction.

        Outbox is inserted before provisional rebuild so offline answers appear in
        provisional seen/correct/wrong/streak/SRS immediately.
        """
        language_code = language_code.strip().lower()
        if not is_vocab_id(vocab_id):
            raise AccountLocalError("Invalid vocabulary UUID.")
        verdict = str(verdict).strip().lower()
        if verdict not in {"exact", "near", "wrong"}:
            raise AccountLocalError("Invalid verdict.")
        mastered = verdict == "exact" and not hint_used
        stamp = occurred_at or to_utc_iso(utc_now())
        event_id = event_id or str(uuid.uuid4())
        device_id = self.device_id()
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                self._conn.execute(
                    """
                    INSERT INTO learning_attempts (
                        event_id, device_id, language_code, vocab_id, verdict,
                        mastered, hint_used, occurred_at, algorithm_id,
                        word_snapshot, user_answer, expected_answer, prompt, source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'local')
                    """,
                    (
                        event_id,
                        device_id,
                        language_code,
                        vocab_id,
                        verdict,
                        1 if mastered else 0,
                        1 if hint_used else 0,
                        stamp,
                        ALGORITHM_LADDER_V2,
                        word_snapshot,
                        user_answer,
                        expected_answer,
                        prompt,
                    ),
                )
                outbox_payload = {
                    "event_id": event_id,
                    "device_id": device_id,
                    "language_code": language_code,
                    "vocab_id": vocab_id,
                    "verdict": verdict,
                    "mastered": 1 if mastered else 0,
                    "hint_used": 1 if hint_used else 0,
                    "occurred_at": stamp,
                    "algorithm_id": ALGORITHM_LADDER_V2,
                    "word_snapshot": word_snapshot,
                    "user_answer": user_answer,
                    "expected_answer": expected_answer,
                    "prompt": prompt,
                }
                self._enqueue_outbox(
                    kind=OUTBOX_KIND_PROGRESS,
                    operation_id=event_id,
                    event_id=event_id,
                    language_code=language_code,
                    vocab_id=vocab_id,
                    payload=outbox_payload,
                    stamp=stamp,
                )
                self._rebuild_provisional_unlocked(language_code, vocab_id)
                self._touch_day_unlocked(language_code, vocab_id, mastered=mastered)
                _meta_set(self._conn, "progress_caught_up", "0")
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise
        return event_id

    def list_attempts(self, language_code: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            if language_code:
                rows = self._conn.execute(
                    "SELECT * FROM learning_attempts WHERE language_code = ? "
                    "ORDER BY occurred_at, event_id",
                    (language_code.strip().lower(),),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM learning_attempts ORDER BY occurred_at, event_id"
                ).fetchall()
        return [dict(row) for row in rows]

    def confirmed_progress(self, language_code: str, vocab_id: str) -> Optional[dict]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM progress_confirmed WHERE language_code = ? AND vocab_id = ?",
                (language_code.strip().lower(), vocab_id),
            ).fetchone()
        return dict(row) if row else None

    def provisional_progress(self, language_code: str, vocab_id: str) -> Optional[dict]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM progress_provisional WHERE language_code = ? AND vocab_id = ?",
                (language_code.strip().lower(), vocab_id),
            ).fetchone()
        return dict(row) if row else None

    def mistake_book_entries(self, language_code: str) -> List[Dict[str, Any]]:
        """Reconstruct Mistake Book candidates from synced/local attempts."""
        attempts = self.list_attempts(language_code)
        by_vocab: Dict[str, Dict[str, Any]] = {}
        for item in attempts:
            vid = str(item["vocab_id"])
            bucket = by_vocab.setdefault(
                vid,
                {
                    "vocab_id": vid,
                    "word": item["word_snapshot"],
                    "wrong": 0,
                    "near": 0,
                    "exact": 0,
                    "last_verdict": item["verdict"],
                    "last_user_answer": item["user_answer"],
                    "last_expected_answer": item["expected_answer"],
                    "last_prompt": item["prompt"],
                },
            )
            verdict = item["verdict"]
            if verdict in bucket:
                bucket[verdict] += 1
            bucket["word"] = item["word_snapshot"]
            bucket["last_verdict"] = verdict
            bucket["last_user_answer"] = item["user_answer"]
            bucket["last_expected_answer"] = item["expected_answer"]
            bucket["last_prompt"] = item["prompt"]
        return [
            entry
            for entry in by_vocab.values()
            if entry["wrong"] > 0 or entry["near"] > 0
        ]

    def account_day_buckets(self, language_code: str) -> Dict[str, dict]:
        """Account-wide day activity keyed by UTC calendar day of ``occurred_at``.

        Semantics (18C.2):
          - Bucket by the attempt's ``occurred_at`` (device study time), never by
            ``received_at`` (upload time). An offline Day-1 answer uploaded on
            Day-3 stays on Day-1.
          - Days are UTC calendar dates (``YYYY-MM-DD``). Midnight boundaries use
            the UTC instant of ``occurred_at`` after ``parse_utc``.
          - Each ``event_id`` counts once (sync must not double-count).
          - Distinct ``vocab_id`` lists per day still dedupe display counters.
          - Clock skew: a future/past ``occurred_at`` is trusted for *activity*
            display only. ADR-022 SRS fold / ``due_at`` remain anchored to server
            ``received_at`` and are not changed here.
          - ``reading_done`` from ``daily_activity`` is device-local and is not a
            cross-device synchronized claim.

        Does not sum guest ``progress.json`` counters.
        """
        language_code = language_code.strip().lower()
        days: Dict[str, dict] = {}
        seen_events = set()
        for item in self.list_attempts(language_code):
            event_id = str(item.get("event_id") or "")
            if event_id:
                if event_id in seen_events:
                    continue
                seen_events.add(event_id)
            # Prefer occurred_at so offline study stays on the study day.
            stamp = str(item.get("occurred_at") or item.get("received_at") or "")
            parsed = parse_utc(stamp)
            if parsed is None:
                continue
            day_key = parsed.date().isoformat()
            bucket = days.setdefault(
                day_key,
                {"asked": [], "correct": [], "wrong": [], "reading_done": False},
            )
            vid = str(item.get("vocab_id") or "")
            if not vid:
                continue
            if vid not in bucket["asked"]:
                bucket["asked"].append(vid)
            mastered = bool(int(item.get("mastered") or 0))
            target = "correct" if mastered else "wrong"
            if vid not in bucket[target]:
                bucket[target].append(vid)
            if mastered and vid in bucket["wrong"]:
                bucket["wrong"].remove(vid)
        with self._lock:
            rows = self._conn.execute(
                "SELECT day_key, reading_done FROM daily_activity WHERE language_code = ?",
                (language_code,),
            ).fetchall()
        for row in rows:
            day_key = str(row["day_key"])
            bucket = days.setdefault(
                day_key,
                {"asked": [], "correct": [], "wrong": [], "reading_done": False},
            )
            if int(row["reading_done"] or 0):
                bucket["reading_done"] = True
        return days

    def mark_reading_done(
        self, language_code: str, score: int = None, total: int = None
    ) -> None:
        """Mark reading complete for this device only (not cross-device synced).

        Uses the UTC calendar day key so signed-in Today() aligns with attempt
        buckets; the flag itself remains local to this account store / device.
        """
        language_code = language_code.strip().lower()
        day_key = utc_now().date().isoformat()
        with self._lock:
            row = self._conn.execute(
                "SELECT asked_json, correct_json, wrong_json FROM daily_activity "
                "WHERE day_key = ? AND language_code = ?",
                (day_key, language_code),
            ).fetchone()
            asked = json.loads(row["asked_json"]) if row else []
            correct = json.loads(row["correct_json"]) if row else []
            wrong = json.loads(row["wrong_json"]) if row else []
            self._conn.execute(
                """
                INSERT INTO daily_activity (
                    day_key, language_code, asked_json, correct_json, wrong_json, reading_done
                ) VALUES (?, ?, ?, ?, ?, 1)
                ON CONFLICT(day_key, language_code) DO UPDATE SET reading_done = 1
                """,
                (
                    day_key,
                    language_code,
                    json.dumps(asked),
                    json.dumps(correct),
                    json.dumps(wrong),
                ),
            )
            self._conn.commit()

    def get_preferences(self) -> Dict[str, Any]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT key, value_json FROM account_preferences"
            ).fetchall()
        out = {}
        for row in rows:
            try:
                out[str(row["key"])] = json.loads(row["value_json"])
            except json.JSONDecodeError:
                continue
        return out

    def set_preference(self, key: str, value: Any) -> None:
        key = str(key or "").strip()
        if not key:
            raise AccountLocalError("Preference key required.")
        stamp = to_utc_iso(utc_now())
        with self._lock:
            row = self._conn.execute(
                "SELECT revision FROM account_preferences WHERE key = ?", (key,)
            ).fetchone()
            revision = int(row["revision"]) + 1 if row else 1
            self._conn.execute(
                """
                INSERT INTO account_preferences (key, value_json, revision, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value_json = excluded.value_json,
                    revision = excluded.revision,
                    updated_at = excluded.updated_at
                """,
                (key, json.dumps(value, ensure_ascii=False, sort_keys=True), revision, stamp),
            )
            self._conn.commit()

    def resolve_vocab_conflict(
        self, language_code: str, vocab_id: str, *, keep: str
    ) -> Optional[str]:
        """Resolve a frozen vocabulary conflict.

        ``keep``:
          - ``server`` — discard local frozen intent; keep remote tip (including tombstone).
          - ``local`` — re-queue local intent against the live remote tip (not allowed
            when the remote tip is a tombstone; that would be an illegal resurrection).
          - ``local_as_new`` — keep the remote tombstone / tip, and save the frozen local
            PUT body as a brand-new vocabulary UUID (explicit alternative to resurrection).

        Returns the new vocab_id when ``local_as_new`` creates one; otherwise ``None``.
        """
        language_code = language_code.strip().lower()
        keep = str(keep or "").strip().lower()
        if keep not in {"local", "server", "local_as_new"}:
            raise AccountLocalError(
                "keep must be 'local', 'server', or 'local_as_new'."
            )
        stamp = to_utc_iso(utc_now())
        created_id: Optional[str] = None
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                frozen = self._conn.execute(
                    """
                    SELECT * FROM outbox
                    WHERE state = ? AND language_code = ? AND vocab_id = ?
                      AND kind IN (?, ?)
                    ORDER BY id DESC LIMIT 1
                    """,
                    (
                        OUTBOX_CONFLICT,
                        language_code,
                        vocab_id,
                        OUTBOX_KIND_VOCAB_PUT,
                        OUTBOX_KIND_VOCAB_DELETE,
                    ),
                ).fetchone()
                if frozen is None:
                    raise AccountLocalError("No vocabulary conflict to resolve.")
                entity = self._conn.execute(
                    "SELECT * FROM vocabulary_entities "
                    "WHERE language_code = ? AND vocab_id = ?",
                    (language_code, vocab_id),
                ).fetchone()
                server_revision = int(entity["revision"]) if entity else 0
                server_deleted = bool(entity and int(entity["deleted"]))
                payload = json.loads(frozen["payload_json"])

                if keep == "server":
                    # Preserve remote tip exactly (including tombstone). Discard local.
                    self._conn.execute(
                        "UPDATE outbox SET state = ?, updated_at = ? WHERE id = ?",
                        (OUTBOX_ACKED, stamp, int(frozen["id"])),
                    )
                elif keep == "local_as_new":
                    if frozen["kind"] != OUTBOX_KIND_VOCAB_PUT:
                        raise AccountLocalError(
                            "local_as_new only applies to a frozen vocabulary edit, "
                            "not a delete."
                        )
                    body = dict(payload.get("payload") or {})
                    new_id = str(uuid.uuid4())
                    body["id"] = new_id
                    self._conn.execute(
                        "UPDATE outbox SET state = ?, updated_at = ? WHERE id = ?",
                        (OUTBOX_ACKED, stamp, int(frozen["id"])),
                    )
                    # Original UUID remains whatever the server tip is (tombstone or live).
                    # Enqueue a create for the new id against expected_revision 0.
                    payload_json = json.dumps(body, ensure_ascii=False, sort_keys=True)
                    self._conn.execute(
                        """
                        INSERT INTO vocabulary_entities (
                            language_code, vocab_id, revision, deleted, payload_json,
                            expected_revision, updated_at
                        ) VALUES (?, ?, 0, 0, ?, 0, ?)
                        """,
                        (language_code, new_id, payload_json, stamp),
                    )
                    new_op = str(uuid.uuid4())
                    self._enqueue_outbox(
                        kind=OUTBOX_KIND_VOCAB_PUT,
                        operation_id=new_op,
                        language_code=language_code,
                        vocab_id=new_id,
                        payload={
                            "language_code": language_code,
                            "vocab_id": new_id,
                            "payload": body,
                            "expected_revision": 0,
                            "operation_id": new_op,
                        },
                        stamp=stamp,
                    )
                    _meta_set(self._conn, "vocab_caught_up", "0")
                    created_id = new_id
                else:
                    # keep == local
                    if server_deleted and frozen["kind"] == OUTBOX_KIND_VOCAB_PUT:
                        raise AccountLocalError(
                            "Cannot keep local edit against a remote tombstone "
                            "(resurrection forbidden). Use keep='local_as_new'."
                        )
                    payload["expected_revision"] = server_revision
                    payload["operation_id"] = str(uuid.uuid4())
                    if frozen["kind"] == OUTBOX_KIND_VOCAB_DELETE:
                        self._conn.execute(
                            "UPDATE outbox SET state = ?, updated_at = ? WHERE id = ?",
                            (OUTBOX_ACKED, stamp, int(frozen["id"])),
                        )
                        if server_revision > 0 and not server_deleted:
                            self._enqueue_outbox(
                                kind=OUTBOX_KIND_VOCAB_DELETE,
                                operation_id=payload["operation_id"],
                                language_code=language_code,
                                vocab_id=vocab_id,
                                payload={
                                    "language_code": language_code,
                                    "vocab_id": vocab_id,
                                    "expected_revision": server_revision,
                                    "operation_id": payload["operation_id"],
                                },
                                stamp=stamp,
                            )
                            if entity is not None:
                                self._conn.execute(
                                    "UPDATE vocabulary_entities SET deleted = 1, "
                                    "expected_revision = ?, updated_at = ? "
                                    "WHERE language_code = ? AND vocab_id = ?",
                                    (server_revision, stamp, language_code, vocab_id),
                                )
                            _meta_set(self._conn, "vocab_caught_up", "0")
                    else:
                        body = payload.get("payload") or {}
                        body["id"] = vocab_id
                        self._conn.execute(
                            "UPDATE outbox SET state = ?, updated_at = ? WHERE id = ?",
                            (OUTBOX_ACKED, stamp, int(frozen["id"])),
                        )
                        self._enqueue_outbox(
                            kind=OUTBOX_KIND_VOCAB_PUT,
                            operation_id=payload["operation_id"],
                            language_code=language_code,
                            vocab_id=vocab_id,
                            payload={
                                "language_code": language_code,
                                "vocab_id": vocab_id,
                                "payload": body,
                                "expected_revision": server_revision,
                                "operation_id": payload["operation_id"],
                            },
                            stamp=stamp,
                        )
                        payload_json = json.dumps(
                            body, ensure_ascii=False, sort_keys=True
                        )
                        self._conn.execute(
                            """
                            INSERT INTO vocabulary_entities (
                                language_code, vocab_id, revision, deleted, payload_json,
                                expected_revision, updated_at
                            ) VALUES (?, ?, ?, 0, ?, ?, ?)
                            ON CONFLICT(language_code, vocab_id) DO UPDATE SET
                                deleted = 0,
                                payload_json = excluded.payload_json,
                                expected_revision = excluded.expected_revision,
                                updated_at = excluded.updated_at
                            """,
                            (
                                language_code,
                                vocab_id,
                                server_revision,
                                payload_json,
                                server_revision,
                                stamp,
                            ),
                        )
                        _meta_set(self._conn, "vocab_caught_up", "0")
                detail_match = f"%{vocab_id}%"
                self._conn.execute(
                    "UPDATE sync_conflicts SET resolved = 1 "
                    "WHERE resolved = 0 AND kind = ? AND detail LIKE ?",
                    ("vocabulary", detail_match),
                )
                remaining = self._conn.execute(
                    "SELECT 1 FROM outbox WHERE state = ? AND kind IN (?, ?) LIMIT 1",
                    (OUTBOX_CONFLICT, OUTBOX_KIND_VOCAB_PUT, OUTBOX_KIND_VOCAB_DELETE),
                ).fetchone()
                if remaining is None:
                    self._conn.execute(
                        "UPDATE sync_conflicts SET resolved = 1 "
                        "WHERE resolved = 0 AND kind = ?",
                        ("vocabulary",),
                    )
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise
        return created_id

    def has_legacy_consent(self, language_code: str, source_kind: str = "guest") -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM legacy_import_consent "
                "WHERE language_code = ? AND source_kind = ?",
                (language_code.strip().lower(), source_kind),
            ).fetchone()
        return row is not None

    def grant_legacy_consent(
        self, language_code: str, source_kind: str = "guest", note: str = ""
    ) -> None:
        stamp = to_utc_iso(utc_now())
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO legacy_import_consent (
                    language_code, source_kind, consented_at, note
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(language_code, source_kind) DO UPDATE SET
                    consented_at = excluded.consented_at,
                    note = excluded.note
                """,
                (language_code.strip().lower(), source_kind, stamp, note),
            )
            self._conn.commit()

    def import_guest_vocabulary(
        self, language_code: str, entries: List[dict], *, require_consent: bool = True
    ) -> dict:
        """Import guest vocab entries into the account store (explicit consent).

        Does not rewrite guest JSON files. Skips ids already present.
        """
        language_code = language_code.strip().lower()
        if require_consent and not self.has_legacy_consent(language_code, "guest"):
            raise AccountLocalError("Legacy import requires explicit consent.")
        imported = 0
        skipped = 0
        for raw in entries or []:
            if not isinstance(raw, dict):
                skipped += 1
                continue
            from vocabulary_model import normalize_entry_dict
            from vocab_identity import entry_id as _eid

            entry = normalize_entry_dict(dict(raw), assign_id=True)
            if entry is None:
                skipped += 1
                continue
            vid = _eid(entry)
            if not vid:
                skipped += 1
                continue
            existing = [
                e for e in self.list_vocabulary(language_code) if e.get("id") == vid
            ]
            if existing:
                skipped += 1
                continue
            self.upsert_vocabulary(
                language_code=language_code, vocab_id=vid, payload=entry
            )
            imported += 1
        return {"imported": imported, "skipped": skipped}

    def grant_attempt_import_consent(
        self, language_code: str, file_identity: str, note: str = ""
    ) -> None:
        """Consent binds one account to one attempt-file identity.

        Vocabulary consent does not satisfy this. Granting consent does not
        enqueue attempts.
        """
        language_code = language_code.strip().lower()
        identity = str(file_identity or "").strip()
        if not language_code or not identity:
            raise AccountLocalError("Attempt import consent needs a file identity.")
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO legacy_attempt_consent (
                    language_code, file_identity, consented_at, revoked, note
                ) VALUES (?, ?, ?, 0, ?)
                ON CONFLICT(language_code, file_identity) DO UPDATE SET
                    consented_at = excluded.consented_at,
                    revoked = 0,
                    note = excluded.note
                """,
                (language_code, identity, to_utc_iso(utc_now()), note or ""),
            )
            self._resolve_legacy_conflict_unlocked(
                f"replacement {language_code}"
            )
            self._conn.commit()

    def revoke_attempt_import_consent(
        self, language_code: str, file_identity: str
    ) -> None:
        language_code = language_code.strip().lower()
        identity = str(file_identity or "").strip()
        with self._lock:
            self._conn.execute(
                """
                UPDATE legacy_attempt_consent
                SET revoked = 1
                WHERE language_code = ? AND file_identity = ?
                """,
                (language_code, identity),
            )
            self._conn.commit()

    def has_attempt_import_consent(
        self, language_code: str, file_identity: str
    ) -> bool:
        language_code = language_code.strip().lower()
        identity = str(file_identity or "").strip()
        with self._lock:
            row = self._conn.execute(
                """
                SELECT revoked FROM legacy_attempt_consent
                WHERE language_code = ? AND file_identity = ?
                """,
                (language_code, identity),
            ).fetchone()
        return bool(row) and int(row["revoked"] or 0) == 0

    def legacy_attempt_sources(self, language_code: str) -> List[dict]:
        language_code = language_code.strip().lower()
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT language_code, file_identity, canonical_path, high_water
                FROM legacy_import_source
                WHERE language_code = ?
                ORDER BY file_identity
                """,
                (language_code,),
            ).fetchall()
        return [dict(row) for row in rows]

    def legacy_attempt_ledger(self, file_identity: Optional[str] = None) -> List[dict]:
        with self._lock:
            if file_identity:
                rows = self._conn.execute(
                    """
                    SELECT file_identity, offset, line_sha256, disposition,
                           event_id, created_at
                    FROM legacy_import_ledger
                    WHERE file_identity = ?
                    ORDER BY offset
                    """,
                    (str(file_identity),),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    """
                    SELECT file_identity, offset, line_sha256, disposition,
                           event_id, created_at
                    FROM legacy_import_ledger
                    ORDER BY file_identity, offset
                    """
                ).fetchall()
        return [dict(row) for row in rows]

    def note_legacy_attempt_conflict(self, detail: str) -> None:
        """Record one open attempt-import conflict. Detail is a short code."""
        text = " ".join(str(detail or "").split())[:180]
        if not text:
            return
        with self._lock:
            self._note_legacy_conflict_unlocked(text)
            self._conn.commit()

    def resolve_legacy_attempt_conflict(self, detail: str) -> None:
        text = " ".join(str(detail or "").split())[:180]
        with self._lock:
            self._resolve_legacy_conflict_unlocked(text)
            self._conn.commit()

    def commit_legacy_attempt_line(
        self,
        *,
        language_code: str,
        canonical_path: str,
        file_identity: str,
        offset: int,
        line_sha256: str,
        next_high_water: int,
        disposition: str,
        event: Optional[dict] = None,
        move_high_water: bool = True,
    ) -> Optional[str]:
        """Commit one ledger decision with its event and outbox row, or neither.

        Returns the event id when a new attempt is stored. A same-offset hash
        mismatch becomes source_conflict and does not move the high-water mark.
        """
        language_code = language_code.strip().lower()
        identity = str(file_identity)
        offset = int(offset)
        digest = str(line_sha256)
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                existing = self._conn.execute(
                    """
                    SELECT line_sha256, disposition, event_id
                    FROM legacy_import_ledger
                    WHERE file_identity = ? AND offset = ?
                    """,
                    (identity, offset),
                ).fetchone()
                event_id: Optional[str] = None
                if existing is not None and str(existing["line_sha256"]) != digest:
                    self._conn.execute(
                        """
                        UPDATE legacy_import_ledger
                        SET disposition = ?
                        WHERE file_identity = ? AND offset = ?
                        """,
                        (LEGACY_DISP_CONFLICT, identity, offset),
                    )
                    self._note_legacy_conflict_unlocked(
                        f"source_conflict {language_code}"
                    )
                    if getattr(self, "_legacy_import_fail_before_commit", False):
                        raise AccountLocalError("legacy import failpoint")
                    self._conn.execute("COMMIT")
                    return None
                if existing is not None:
                    event_id = existing["event_id"]
                    if getattr(self, "_legacy_import_fail_before_commit", False):
                        raise AccountLocalError("legacy import failpoint")
                    self._conn.execute("COMMIT")
                    return event_id
                if disposition == LEGACY_DISP_IMPORTED:
                    if not isinstance(event, dict):
                        raise AccountLocalError("Imported attempt is missing its event.")
                    event_id = str(event.get("event_id") or uuid.uuid4())
                    event = dict(event)
                    event["event_id"] = event_id
                    self._insert_legacy_attempt_unlocked(event)
                self._conn.execute(
                    """
                    INSERT INTO legacy_import_ledger (
                        file_identity, offset, line_sha256, disposition,
                        event_id, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        identity,
                        offset,
                        digest,
                        disposition,
                        event_id,
                        to_utc_iso(utc_now()),
                    ),
                )
                self._conn.execute(
                    """
                    INSERT INTO legacy_import_source (
                        language_code, file_identity, canonical_path, high_water
                    ) VALUES (?, ?, ?, ?)
                    ON CONFLICT(language_code, file_identity) DO UPDATE SET
                        canonical_path = excluded.canonical_path,
                        high_water = CASE
                            WHEN ? THEN excluded.high_water
                            ELSE legacy_import_source.high_water
                        END
                    """,
                    (
                        language_code,
                        identity,
                        canonical_path,
                        int(next_high_water) if move_high_water else 0,
                        1 if move_high_water else 0,
                    ),
                )
                if getattr(self, "_legacy_import_fail_before_commit", False):
                    raise AccountLocalError("legacy import failpoint")
                self._conn.execute("COMMIT")
                return event_id
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def reconcile_legacy_overlap_line(
        self,
        *,
        language_code: str,
        file_identity: str,
        offset: int,
        line_sha256: str,
        choice: str,
        event: Optional[dict] = None,
        next_high_water: Optional[int] = None,
    ) -> Optional[str]:
        """Apply an explicit overlap choice. Skip writes no outbox event."""
        if choice not in {"skip", "distinct"}:
            raise AccountLocalError("Overlap choice must be skip or distinct.")
        language_code = language_code.strip().lower()
        identity = str(file_identity)
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                existing = self._conn.execute(
                    """
                    SELECT line_sha256, disposition, event_id
                    FROM legacy_import_ledger
                    WHERE file_identity = ? AND offset = ?
                    """,
                    (identity, int(offset)),
                ).fetchone()
                if existing is None:
                    raise AccountLocalError("Overlap line is not in the ledger.")
                if str(existing["line_sha256"]) != str(line_sha256):
                    self._conn.execute(
                        """
                        UPDATE legacy_import_ledger
                        SET disposition = ?
                        WHERE file_identity = ? AND offset = ?
                        """,
                        (LEGACY_DISP_CONFLICT, identity, int(offset)),
                    )
                    self._note_legacy_conflict_unlocked(
                        f"source_conflict {language_code}"
                    )
                    self._conn.execute("COMMIT")
                    return None
                if str(existing["disposition"]) != LEGACY_DISP_OVERLAP:
                    if getattr(self, "_legacy_import_fail_before_commit", False):
                        raise AccountLocalError("legacy import failpoint")
                    self._conn.execute("COMMIT")
                    return existing["event_id"]
                event_id = None
                if choice == "distinct" and isinstance(event, dict):
                    event_id = str(event.get("event_id") or uuid.uuid4())
                    event = dict(event)
                    event["event_id"] = event_id
                    self._insert_legacy_attempt_unlocked(event)
                    disposition = LEGACY_DISP_IMPORTED
                else:
                    disposition = LEGACY_DISP_SKIPPED_OVERLAP
                self._conn.execute(
                    """
                    UPDATE legacy_import_ledger
                    SET disposition = ?, event_id = ?
                    WHERE file_identity = ? AND offset = ?
                    """,
                    (disposition, event_id, identity, int(offset)),
                )
                if next_high_water is not None:
                    self._conn.execute(
                        """
                        UPDATE legacy_import_source
                        SET high_water = ?
                        WHERE language_code = ? AND file_identity = ?
                          AND high_water < ?
                        """,
                        (
                            int(next_high_water),
                            language_code,
                            identity,
                            int(next_high_water),
                        ),
                    )
                if getattr(self, "_legacy_import_fail_before_commit", False):
                    raise AccountLocalError("legacy import failpoint")
                self._conn.execute("COMMIT")
                return event_id
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def legacy_attempt_high_water(
        self, language_code: str, file_identity: str
    ) -> int:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT high_water FROM legacy_import_source
                WHERE language_code = ? AND file_identity = ?
                """,
                (language_code.strip().lower(), str(file_identity)),
            ).fetchone()
        return int(row["high_water"]) if row else 0

    def legacy_hash_on_other_identity(self, line_sha256: str, file_identity: str) -> bool:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT 1 FROM legacy_import_ledger
                WHERE line_sha256 = ? AND file_identity != ?
                LIMIT 1
                """,
                (str(line_sha256), str(file_identity)),
            ).fetchone()
        return row is not None

    def _insert_legacy_attempt_unlocked(self, event: dict) -> None:
        hint_used = bool(event.get("hint_used"))
        verdict = str(event["verdict"])
        mastered = verdict == "exact" and not hint_used
        stamp = to_utc_iso(utc_now())
        self._conn.execute(
            """
            INSERT INTO learning_attempts (
                event_id, device_id, language_code, vocab_id, verdict,
                mastered, hint_used, occurred_at, algorithm_id,
                word_snapshot, user_answer, expected_answer, prompt, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'legacy_import')
            """,
            (
                event["event_id"],
                event.get("device_id") or self.device_id(),
                event["language_code"],
                event["vocab_id"],
                verdict,
                1 if mastered else 0,
                1 if hint_used else 0,
                event["occurred_at"],
                ALGORITHM_LADDER_V2,
                event.get("word_snapshot") or "",
                event.get("user_answer") or "",
                event.get("expected_answer") or "",
                event.get("prompt") or "",
            ),
        )
        payload = {
            "event_id": event["event_id"],
            "device_id": event.get("device_id") or self.device_id(),
            "language_code": event["language_code"],
            "vocab_id": event["vocab_id"],
            "verdict": verdict,
            "mastered": 1 if mastered else 0,
            "hint_used": 1 if hint_used else 0,
            "occurred_at": event["occurred_at"],
            "algorithm_id": ALGORITHM_LADDER_V2,
            "word_snapshot": event.get("word_snapshot") or "",
            "user_answer": event.get("user_answer") or "",
            "expected_answer": event.get("expected_answer") or "",
            "prompt": event.get("prompt") or "",
        }
        self._enqueue_outbox(
            kind=OUTBOX_KIND_PROGRESS,
            operation_id=event["event_id"],
            event_id=event["event_id"],
            language_code=event["language_code"],
            vocab_id=event["vocab_id"],
            payload=payload,
            stamp=stamp,
        )
        self._rebuild_provisional_unlocked(event["language_code"], event["vocab_id"])
        _meta_set(self._conn, "progress_caught_up", "0")

    def _note_legacy_conflict_unlocked(self, detail: str) -> None:
        row = self._conn.execute(
            """
            SELECT id FROM sync_conflicts
            WHERE kind = ? AND detail = ? AND resolved = 0
            LIMIT 1
            """,
            (LEGACY_CONFLICT_KIND, detail),
        ).fetchone()
        if row is None:
            self._record_conflict_unlocked(LEGACY_CONFLICT_KIND, detail)

    def _resolve_legacy_conflict_unlocked(self, detail: str) -> None:
        self._conn.execute(
            """
            UPDATE sync_conflicts
            SET resolved = 1
            WHERE kind = ? AND detail = ? AND resolved = 0
            """,
            (LEGACY_CONFLICT_KIND, detail),
        )

    def acknowledge_progress_upload(self, event_id: str, body: dict) -> None:
        """Mark outbox acked and apply progress_after without moving the download cursor."""
        progress_after = body.get("progress_after") or {}
        event = body.get("event") or {}
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                self._upsert_attempt_from_server_unlocked(event)
                self._apply_confirmed_snapshot_unlocked(progress_after, event=event)
                row = self._conn.execute(
                    "SELECT ack_state_version FROM outbox WHERE event_id = ?",
                    (event_id,),
                ).fetchone()
                ack_version = int(progress_after.get("state_version") or 0)
                self._conn.execute(
                    """
                    UPDATE outbox
                    SET state = ?, ack_state_version = ?, updated_at = ?
                    WHERE event_id = ? AND kind = ?
                    """,
                    (
                        OUTBOX_ACKED,
                        ack_version,
                        to_utc_iso(utc_now()),
                        event_id,
                        OUTBOX_KIND_PROGRESS,
                    ),
                )
                language_code = str(event.get("language_code") or "").strip().lower()
                vocab_id = str(event.get("vocab_id") or "")
                if language_code and vocab_id:
                    self._rebuild_provisional_unlocked(language_code, vocab_id)
                # Intentionally do NOT advance progress_cursor here (ADR-022).
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def apply_progress_changes_page(
        self, changes: List[dict], *, next_cursor: int, has_more: bool
    ) -> None:
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                cursor = int(_meta_get(self._conn, "progress_cursor") or "0")
                if not changes:
                    if not has_more and next_cursor == cursor:
                        _meta_set(self._conn, "progress_caught_up", "1")
                    self._conn.execute("COMMIT")
                    return

                previous = cursor
                touched: List[Tuple[str, str]] = []
                for item in changes:
                    change_id = int(item["change_id"])
                    if change_id <= previous:
                        raise AccountLocalConflict(
                            "Progress change_id must be strictly increasing."
                        )
                    previous = change_id
                    event = item.get("event") or {}
                    progress_after = item.get("progress_after") or {}
                    event_id = str(event.get("event_id") or "")
                    existing = self._conn.execute(
                        "SELECT * FROM learning_attempts WHERE event_id = ?",
                        (event_id,),
                    ).fetchone()
                    if existing is not None:
                        if not _attempt_body_matches(existing, event):
                            self._record_conflict_unlocked(
                                "progress_event",
                                f"event_id body mismatch: {event_id}",
                            )
                            raise AccountLocalConflict("Progress event body conflict.")
                    else:
                        self._upsert_attempt_from_server_unlocked(event)
                    self._apply_confirmed_snapshot_unlocked(progress_after, event=event)
                    touched.append(
                        (
                            str(event.get("language_code") or "").strip().lower(),
                            str(event.get("vocab_id") or ""),
                        )
                    )

                for language_code, vocab_id in touched:
                    if language_code and vocab_id:
                        self._rebuild_provisional_unlocked(language_code, vocab_id)
                _meta_set(self._conn, "progress_cursor", str(previous))
                _meta_set(self._conn, "progress_caught_up", "0" if has_more else "1")
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def pending_outbox(self, kind: Optional[str] = None) -> List[dict]:
        with self._lock:
            if kind:
                rows = self._conn.execute(
                    """
                    SELECT * FROM outbox
                    WHERE state = ? AND kind = ?
                    ORDER BY id ASC
                    """,
                    (OUTBOX_PENDING, kind),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    """
                    SELECT * FROM outbox
                    WHERE state = ?
                    ORDER BY id ASC
                    """,
                    (OUTBOX_PENDING,),
                ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(row["payload_json"])
            result.append(item)
        return result

    def is_outbox_pending(self, operation_id: str) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM outbox WHERE operation_id = ? AND state = ?",
                (operation_id, OUTBOX_PENDING),
            ).fetchone()
        return row is not None

    def conflicted_vocab_outbox(self, language_code: str, vocab_id: str) -> List[dict]:
        """Local mutations frozen for 18C.2 resolution (not uploaded)."""
        language_code = language_code.strip().lower()
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM outbox
                WHERE state = ?
                  AND language_code = ?
                  AND vocab_id = ?
                  AND kind IN (?, ?)
                ORDER BY id ASC
                """,
                (
                    OUTBOX_CONFLICT,
                    language_code,
                    vocab_id,
                    OUTBOX_KIND_VOCAB_PUT,
                    OUTBOX_KIND_VOCAB_DELETE,
                ),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(row["payload_json"])
            result.append(item)
        return result

    def list_open_vocab_conflicts(self) -> List[dict]:
        """Local vs server vocabulary versions waiting for explicit resolution."""
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM outbox
                WHERE state = ? AND kind IN (?, ?)
                ORDER BY id ASC
                """,
                (OUTBOX_CONFLICT, OUTBOX_KIND_VOCAB_PUT, OUTBOX_KIND_VOCAB_DELETE),
            ).fetchall()
        out = []
        for row in rows:
            language_code = str(row["language_code"] or "")
            vocab_id = str(row["vocab_id"] or "")
            local_payload = json.loads(row["payload_json"])
            server_entry = None
            server_deleted = False
            server_revision = 0
            with self._lock:
                entity = self._conn.execute(
                    "SELECT * FROM vocabulary_entities "
                    "WHERE language_code = ? AND vocab_id = ?",
                    (language_code, vocab_id),
                ).fetchone()
            if entity is not None:
                server_revision = int(entity["revision"] or 0)
                server_deleted = bool(int(entity["deleted"] or 0))
                if entity["payload_json"] and not server_deleted:
                    try:
                        server_entry = json.loads(entity["payload_json"])
                    except json.JSONDecodeError:
                        server_entry = None
            local_body = local_payload.get("payload") if row["kind"] == OUTBOX_KIND_VOCAB_PUT else None
            out.append(
                {
                    "outbox_id": int(row["id"]),
                    "kind": str(row["kind"]),
                    "language_code": language_code,
                    "vocab_id": vocab_id,
                    "local_operation": "delete"
                    if row["kind"] == OUTBOX_KIND_VOCAB_DELETE
                    else "put",
                    "local_entry": local_body,
                    "server_entry": server_entry,
                    "server_revision": server_revision,
                    "server_deleted": server_deleted,
                    "updated_at": str(row["updated_at"] or ""),
                }
            )
        return out

    def mark_conflict(self, kind: str, detail: str) -> None:
        with self._lock:
            self._record_conflict_unlocked(kind, detail)
            self._conn.commit()

    def cursors(self) -> Dict[str, int]:
        with self._lock:
            return {
                "vocab_cursor": int(_meta_get(self._conn, "vocab_cursor") or "0"),
                "progress_cursor": int(_meta_get(self._conn, "progress_cursor") or "0"),
            }

    # --- internals ---

    def _count_pending(self, kinds: Tuple[str, ...]) -> int:
        placeholders = ",".join("?" for _ in kinds)
        row = self._conn.execute(
            f"SELECT COUNT(*) AS n FROM outbox WHERE state = ? AND kind IN ({placeholders})",
            (OUTBOX_PENDING, *kinds),
        ).fetchone()
        return int(row["n"])

    def _has_open_conflict(self) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM sync_conflicts WHERE resolved = 0 LIMIT 1"
        ).fetchone()
        return row is not None

    def _enqueue_outbox(
        self,
        *,
        kind: str,
        operation_id: str,
        payload: dict,
        stamp: str,
        language_code: Optional[str] = None,
        vocab_id: Optional[str] = None,
        event_id: Optional[str] = None,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO outbox (
                kind, operation_id, event_id, language_code, vocab_id,
                payload_json, state, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                kind,
                operation_id,
                event_id,
                language_code,
                vocab_id,
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
                OUTBOX_PENDING,
                stamp,
                stamp,
            ),
        )

    def _server_base_revision_unlocked(self, row: Optional[sqlite3.Row]) -> int:
        """Last known server revision. Tombstoned or missing → 0 (create base)."""
        if row is None:
            return 0
        if int(row["deleted"]):
            return 0
        return int(row["revision"] or 0)

    def _supersede_pending_vocab_unlocked(
        self, language_code: str, vocab_id: str, stamp: str
    ) -> None:
        self._conn.execute(
            """
            UPDATE outbox
            SET state = ?, updated_at = ?
            WHERE state = ?
              AND language_code = ?
              AND vocab_id = ?
              AND kind IN (?, ?)
            """,
            (
                OUTBOX_SUPERSEDED,
                stamp,
                OUTBOX_PENDING,
                language_code,
                vocab_id,
                OUTBOX_KIND_VOCAB_PUT,
                OUTBOX_KIND_VOCAB_DELETE,
            ),
        )

    def _pending_vocab_unlocked(
        self, language_code: str, vocab_id: str
    ) -> Optional[sqlite3.Row]:
        return self._conn.execute(
            """
            SELECT * FROM outbox
            WHERE state = ?
              AND language_code = ?
              AND vocab_id = ?
              AND kind IN (?, ?)
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                OUTBOX_PENDING,
                language_code,
                vocab_id,
                OUTBOX_KIND_VOCAB_PUT,
                OUTBOX_KIND_VOCAB_DELETE,
            ),
        ).fetchone()

    def _apply_remote_vocab_change_unlocked(self, record: dict) -> None:
        """Apply a downloaded change; divergent pending locals become explicit conflicts.

        ADR-018: never silently last-write-wins over another device's accepted edit.
        Matching remote content idempotently clears the pending op (lost-ack safe).
        Divergent remote content applies the server-accepted row, freezes the local
        mutation in ``outbox`` state ``conflict`` (not uploaded), and records a
        blocking conflict for 18C.2 resolution UI.
        """
        language_code = str(record["language_code"]).strip().lower()
        vocab_id = str(record["vocab_id"])
        stamp = to_utc_iso(utc_now())
        pending = self._pending_vocab_unlocked(language_code, vocab_id)
        if pending is None:
            self._apply_vocab_entity_unlocked(record)
            return

        pending_payload = json.loads(pending["payload_json"])
        pending_deleted = pending["kind"] == OUTBOX_KIND_VOCAB_DELETE
        remote_deleted = bool(record.get("deleted"))
        remote_payload = record.get("payload")

        same_intent = pending_deleted == remote_deleted and (
            pending_deleted
            or _payload_fingerprint(pending_payload.get("payload"))
            == _payload_fingerprint(remote_payload)
        )
        if same_intent:
            # Same intended change (including lost HTTP ack) — adopt server row.
            self._apply_vocab_entity_unlocked(record)
            self._conn.execute(
                "UPDATE outbox SET state = ?, updated_at = ? WHERE id = ?",
                (OUTBOX_ACKED, stamp, int(pending["id"])),
            )
            return

        base_revision = int(pending_payload.get("expected_revision") or 0)
        remote_revision = int(record["revision"])
        if remote_revision <= base_revision:
            # Catch-up of our edit base / older history — not a concurrent tip.
            # Keep the pending mutation uploadable; do not clobber local intent.
            self._preserve_pending_vocab_working_copy_unlocked(
                language_code=language_code,
                vocab_id=vocab_id,
                pending=pending,
                pending_payload=pending_payload,
                pending_deleted=pending_deleted,
                remote_revision=remote_revision,
                stamp=stamp,
            )
            return

        # Newer divergent remote tip: adopt server-accepted entity; freeze local
        # mutation. Do not rewrite expected_revision; do not leave the op uploadable.
        self._apply_vocab_entity_unlocked(record)
        self._conn.execute(
            "UPDATE outbox SET state = ?, updated_at = ? WHERE id = ? AND state = ?",
            (OUTBOX_CONFLICT, stamp, int(pending["id"]), OUTBOX_PENDING),
        )
        detail = (
            f"vocabulary conflict {language_code}/{vocab_id}: "
            f"local pending {'delete' if pending_deleted else 'put'} vs "
            f"remote revision {remote_revision}"
            f"{' (tombstone)' if remote_deleted else ''}"
        )
        self._record_conflict_unlocked("vocabulary", detail)

    def _preserve_pending_vocab_working_copy_unlocked(
        self,
        *,
        language_code: str,
        vocab_id: str,
        pending: sqlite3.Row,
        pending_payload: dict,
        pending_deleted: bool,
        remote_revision: int,
        stamp: str,
    ) -> None:
        """Adopt a remote revision watermark without discarding a pending local edit."""
        existing = self._conn.execute(
            "SELECT revision FROM vocabulary_entities "
            "WHERE language_code = ? AND vocab_id = ?",
            (language_code, vocab_id),
        ).fetchone()
        revision = max(int(existing["revision"]) if existing else 0, int(remote_revision))
        payload_json = None
        if not pending_deleted:
            body = dict(pending_payload.get("payload") or {})
            body["id"] = vocab_id
            payload_json = json.dumps(body, ensure_ascii=False, sort_keys=True)
        base = int(pending_payload.get("expected_revision") or 0)
        self._conn.execute(
            """
            INSERT INTO vocabulary_entities (
                language_code, vocab_id, revision, deleted, payload_json,
                expected_revision, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(language_code, vocab_id) DO UPDATE SET
                revision = excluded.revision,
                deleted = excluded.deleted,
                payload_json = excluded.payload_json,
                expected_revision = excluded.expected_revision,
                updated_at = excluded.updated_at
            """,
            (
                language_code,
                vocab_id,
                revision,
                1 if pending_deleted else 0,
                payload_json,
                base,
                stamp,
            ),
        )
        # pending outbox row unchanged (still uploadable; expected_revision untouched).

    def _apply_vocab_entity_unlocked(self, record: dict) -> None:
        language_code = str(record["language_code"]).strip().lower()
        vocab_id = str(record["vocab_id"])
        revision = int(record["revision"])
        deleted = bool(record.get("deleted"))
        payload = record.get("payload")
        expected_revision = int(record.get("expected_revision") or max(revision - 1, 0))
        payload_json = (
            None
            if deleted or payload is None
            else json.dumps(payload, ensure_ascii=False, sort_keys=True)
        )
        self._conn.execute(
            """
            INSERT INTO vocabulary_entities (
                language_code, vocab_id, revision, deleted, payload_json,
                expected_revision, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(language_code, vocab_id) DO UPDATE SET
                revision = excluded.revision,
                deleted = excluded.deleted,
                payload_json = excluded.payload_json,
                expected_revision = excluded.expected_revision,
                updated_at = excluded.updated_at
            """,
            (
                language_code,
                vocab_id,
                revision,
                1 if deleted else 0,
                payload_json,
                expected_revision,
                to_utc_iso(utc_now()),
            ),
        )

    def _upsert_attempt_from_server_unlocked(self, event: dict) -> None:
        if not event:
            return
        event_id = str(event["event_id"])
        self._conn.execute(
            """
            INSERT INTO learning_attempts (
                event_id, device_id, language_code, vocab_id, verdict,
                mastered, hint_used, occurred_at, received_at, server_seq,
                algorithm_id, word_snapshot, user_answer, expected_answer,
                prompt, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'server')
            ON CONFLICT(event_id) DO UPDATE SET
                received_at = COALESCE(excluded.received_at, learning_attempts.received_at),
                server_seq = COALESCE(excluded.server_seq, learning_attempts.server_seq),
                source = 'server'
            """,
            (
                event_id,
                str(event["device_id"]),
                str(event["language_code"]).strip().lower(),
                str(event["vocab_id"]),
                str(event["verdict"]),
                int(event.get("mastered") or 0),
                int(event.get("hint_used") or 0),
                str(event["occurred_at"]),
                event.get("received_at"),
                event.get("server_seq"),
                str(event.get("algorithm_id") or ALGORITHM_LADDER_V2),
                str(event.get("word_snapshot") or ""),
                str(event.get("user_answer") or ""),
                str(event.get("expected_answer") or ""),
                str(event.get("prompt") or ""),
            ),
        )

    def _apply_confirmed_snapshot_unlocked(
        self, snapshot: dict, *, event: dict
    ) -> None:
        if not snapshot:
            return
        language_code = str(event.get("language_code") or "").strip().lower()
        vocab_id = str(event.get("vocab_id") or "")
        if not language_code or not vocab_id:
            return
        incoming_version = int(snapshot.get("state_version") or 0)
        existing = self._conn.execute(
            "SELECT * FROM progress_confirmed WHERE language_code = ? AND vocab_id = ?",
            (language_code, vocab_id),
        ).fetchone()
        if existing is None or incoming_version > int(existing["state_version"]):
            self._conn.execute(
                """
                INSERT INTO progress_confirmed (
                    language_code, vocab_id, seen, correct, wrong, streak,
                    interval_days, due_at, state_version, algorithm_id,
                    last_event_id, last_server_seq, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(language_code, vocab_id) DO UPDATE SET
                    seen = excluded.seen,
                    correct = excluded.correct,
                    wrong = excluded.wrong,
                    streak = excluded.streak,
                    interval_days = excluded.interval_days,
                    due_at = excluded.due_at,
                    state_version = excluded.state_version,
                    algorithm_id = excluded.algorithm_id,
                    last_event_id = excluded.last_event_id,
                    last_server_seq = excluded.last_server_seq,
                    updated_at = excluded.updated_at
                """,
                (
                    language_code,
                    vocab_id,
                    int(snapshot.get("seen") or 0),
                    int(snapshot.get("correct") or 0),
                    int(snapshot.get("wrong") or 0),
                    int(snapshot.get("streak") or 0),
                    int(snapshot.get("interval_days") or 0),
                    str(snapshot.get("due_at") or ""),
                    incoming_version,
                    str(snapshot.get("algorithm_id") or ALGORITHM_LADDER_V2),
                    str(snapshot.get("last_event_id") or event.get("event_id") or ""),
                    int(snapshot.get("last_server_seq") or event.get("server_seq") or 0),
                    to_utc_iso(utc_now()),
                ),
            )
            return
        if incoming_version < int(existing["state_version"]):
            return
        # Equal version: content must match.
        for field in ("seen", "correct", "wrong", "streak", "interval_days"):
            if int(existing[field]) != int(snapshot.get(field) or 0):
                self._record_conflict_unlocked(
                    "progress_snapshot",
                    f"state_version {incoming_version} content mismatch",
                )
                raise AccountLocalConflict("Equal state_version with different content.")
        if str(existing["due_at"]) != str(snapshot.get("due_at") or ""):
            self._record_conflict_unlocked(
                "progress_snapshot",
                f"state_version {incoming_version} due_at mismatch",
            )
            raise AccountLocalConflict("Equal state_version with different due_at.")
        if str(existing["last_event_id"]) != str(
            snapshot.get("last_event_id") or event.get("event_id") or ""
        ):
            self._record_conflict_unlocked(
                "progress_snapshot",
                f"state_version {incoming_version} last_event_id mismatch",
            )
            raise AccountLocalConflict("Equal state_version with different last_event_id.")

    def _rebuild_provisional_unlocked(self, language_code: str, vocab_id: str) -> None:
        confirmed = self._conn.execute(
            "SELECT * FROM progress_confirmed WHERE language_code = ? AND vocab_id = ?",
            (language_code, vocab_id),
        ).fetchone()
        if confirmed is None:
            stats = {
                "seen": 0,
                "correct": 0,
                "wrong": 0,
                "streak": 0,
                "interval_days": 0,
                "due_at": to_utc_iso(utc_now()),
            }
            confirmed_version = 0
        else:
            stats = {
                "seen": int(confirmed["seen"]),
                "correct": int(confirmed["correct"]),
                "wrong": int(confirmed["wrong"]),
                "streak": int(confirmed["streak"]),
                "interval_days": int(confirmed["interval_days"]),
                "due_at": str(confirmed["due_at"]),
            }
            confirmed_version = int(confirmed["state_version"])

        uncovered = list(
            self._conn.execute(
                """
                SELECT a.*, o.id AS outbox_id, o.created_at AS outbox_created_at
                FROM learning_attempts a
                JOIN outbox o ON o.event_id = a.event_id AND o.kind = ?
                WHERE a.language_code = ? AND a.vocab_id = ?
                  AND (
                        o.state = ?
                     OR o.ack_state_version IS NULL
                     OR o.ack_state_version < ?
                  )
                ORDER BY a.occurred_at ASC, a.event_id ASC
                """,
                (
                    OUTBOX_KIND_PROGRESS,
                    language_code,
                    vocab_id,
                    OUTBOX_PENDING,
                    confirmed_version,
                ),
            ).fetchall()
        )
        legacy_ids = {
            str(row["event_id"])
            for row in self._conn.execute(
                """
                SELECT event_id FROM legacy_import_ledger
                WHERE event_id IS NOT NULL
                """
            )
            if row["event_id"]
        }
        def _legacy_pending(row) -> bool:
            # The ledger row is inserted after this rebuild on the import
            # path, so the attempt source is the signal during that
            # transaction. After acknowledgement the source becomes server
            # and the ledger id keeps the same scheduling rule.
            return (
                str(row["source"] or "") == "legacy_import"
                or str(row["event_id"]) in legacy_ids
            )

        # Live study stays ordered by occurred_at and uses that device clock
        # as the stand-in for received_at. A guest import keeps occurred_at as
        # evidence, but the pending fold follows outbox order and the enqueue
        # clock. Upload uses that same outbox order, and the server anchors
        # due_at to received_at rather than the guest timestamp.
        if any(_legacy_pending(row) for row in uncovered):
            uncovered.sort(key=lambda row: int(row["outbox_id"]))
        for attempt in uncovered:
            mastered = bool(int(attempt["mastered"]))
            stats["seen"] += 1
            if mastered:
                stats["correct"] += 1
                stats["streak"] += 1
            else:
                stats["wrong"] += 1
                stats["streak"] = 0
            if _legacy_pending(attempt):
                reviewed_at = parse_utc(attempt["outbox_created_at"]) or utc_now()
            else:
                reviewed_at = parse_utc(attempt["occurred_at"]) or utc_now()
            apply_review_to_stats(stats, mastered=mastered, reviewed_at=reviewed_at)

        self._conn.execute(
            """
            INSERT INTO progress_provisional (
                language_code, vocab_id, seen, correct, wrong, streak,
                interval_days, due_at, algorithm_id, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(language_code, vocab_id) DO UPDATE SET
                seen = excluded.seen,
                correct = excluded.correct,
                wrong = excluded.wrong,
                streak = excluded.streak,
                interval_days = excluded.interval_days,
                due_at = excluded.due_at,
                algorithm_id = excluded.algorithm_id,
                updated_at = excluded.updated_at
            """,
            (
                language_code,
                vocab_id,
                int(stats["seen"]),
                int(stats["correct"]),
                int(stats["wrong"]),
                int(stats["streak"]),
                int(stats["interval_days"]),
                str(stats["due_at"]),
                ALGORITHM_LADDER_V2,
                to_utc_iso(utc_now()),
            ),
        )

    def _touch_day_unlocked(
        self, language_code: str, vocab_id: str, *, mastered: bool
    ) -> None:
        day_key = date.today().isoformat()
        row = self._conn.execute(
            "SELECT asked_json, correct_json, wrong_json, reading_done "
            "FROM daily_activity WHERE day_key = ? AND language_code = ?",
            (day_key, language_code),
        ).fetchone()
        if row is None:
            asked, correct, wrong, reading_done = [], [], [], 0
        else:
            asked = json.loads(row["asked_json"] or "[]")
            correct = json.loads(row["correct_json"] or "[]")
            wrong = json.loads(row["wrong_json"] or "[]")
            reading_done = int(row["reading_done"] or 0)
        if vocab_id not in asked:
            asked.append(vocab_id)
        bucket = correct if mastered else wrong
        if vocab_id not in bucket:
            bucket.append(vocab_id)
        if mastered and vocab_id in wrong:
            wrong.remove(vocab_id)
        self._conn.execute(
            """
            INSERT INTO daily_activity (
                day_key, language_code, asked_json, correct_json, wrong_json, reading_done
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(day_key, language_code) DO UPDATE SET
                asked_json = excluded.asked_json,
                correct_json = excluded.correct_json,
                wrong_json = excluded.wrong_json
            """,
            (
                day_key,
                language_code,
                json.dumps(asked),
                json.dumps(correct),
                json.dumps(wrong),
                reading_done,
            ),
        )

    def _record_conflict_unlocked(self, kind: str, detail: str) -> None:
        self._conn.execute(
            """
            INSERT INTO sync_conflicts (kind, detail, created_at, resolved)
            VALUES (?, ?, ?, 0)
            """,
            (kind, detail, to_utc_iso(utc_now())),
        )


def _payload_fingerprint(payload: Optional[dict]) -> str:
    if payload is None:
        return ""
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _meta_get(connection: sqlite3.Connection, key: str) -> Optional[str]:
    row = connection.execute(
        "SELECT value FROM meta WHERE key = ?", (key,)
    ).fetchone()
    if row is None:
        return None
    return str(row["value"] if isinstance(row, sqlite3.Row) else row[0])


def _meta_set(connection: sqlite3.Connection, key: str, value: str) -> None:
    connection.execute(
        """
        INSERT INTO meta (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key, value),
    )


def _attempt_body_matches(existing: sqlite3.Row, event: dict) -> bool:
    checks = (
        ("device_id", "device_id"),
        ("language_code", "language_code"),
        ("vocab_id", "vocab_id"),
        ("verdict", "verdict"),
        ("word_snapshot", "word_snapshot"),
        ("user_answer", "user_answer"),
        ("expected_answer", "expected_answer"),
        ("prompt", "prompt"),
        ("occurred_at", "occurred_at"),
    )
    for column, key in checks:
        if str(existing[column]) != str(event.get(key) or ""):
            return False
    if int(existing["mastered"]) != int(event.get("mastered") or 0):
        return False
    if int(existing["hint_used"]) != int(event.get("hint_used") or 0):
        return False
    return True
