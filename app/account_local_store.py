"""Per-account local SQLite store for signed-in study sync (Phase 18C.1).

Guest ``languages/{code}/`` files stay untouched. Login never copies machine-global
vocabulary or progress into an account database.
"""

from __future__ import annotations

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

STATUS_SYNCED = "Synced"
STATUS_PENDING = "Pending"
STATUS_OFFLINE = "Offline"
STATUS_CONFLICT = "Conflict"

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

    def status(self) -> SyncStatusSnapshot:
        with self._lock:
            pending_vocab = self._count_pending(
                (OUTBOX_KIND_VOCAB_PUT, OUTBOX_KIND_VOCAB_DELETE)
            )
            pending_progress = self._count_pending((OUTBOX_KIND_PROGRESS,))
            conflict = self._has_open_conflict()
            offline = _meta_get(self._conn, "offline") == "1"
            vocab_caught = _meta_get(self._conn, "vocab_caught_up") == "1"
            progress_caught = _meta_get(self._conn, "progress_caught_up") == "1"
            vocab_cursor = int(_meta_get(self._conn, "vocab_cursor") or "0")
            progress_cursor = int(_meta_get(self._conn, "progress_cursor") or "0")
            if conflict:
                status, detail = STATUS_CONFLICT, "Conflict / Action required"
            elif offline:
                status, detail = STATUS_OFFLINE, "Server unreachable"
            elif pending_vocab or pending_progress or not vocab_caught or not progress_caught:
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
                conflict=conflict,
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
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

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

        uncovered = self._conn.execute(
            """
            SELECT a.*
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
        for attempt in uncovered:
            mastered = bool(int(attempt["mastered"]))
            stats["seen"] += 1
            if mastered:
                stats["correct"] += 1
                stats["streak"] += 1
            else:
                stats["wrong"] += 1
                stats["streak"] = 0
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
