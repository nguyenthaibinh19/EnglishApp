"""Account Cloud Sync persistence foundation (Phase 18A).

Isolated SQLite store (``study_sync.db``) for versioned vocabulary entities.
HTTP access is a separate, default-off adapter (``sync_http`` / ADR-019).
This module does not serve HTTP, upload desktop data, or touch production accounts.db.

Trusted server code passes authenticated ``user_id`` after session checks.
This module does not validate tokens.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

import languages
from vocab_identity import entry_id, is_vocab_id
from vocabulary_model import FORM_FIELDS, normalize_entry_dict

DB_FILE = "study_sync.db"
SCHEMA_VERSION = 3
DEFAULT_CHANGE_LIMIT = 100
MAX_CHANGE_LIMIT = 500
PROGRESS_CHANGE_LIMIT = 100
ALGORITHM_LADDER_V2 = "ladder-v2"

# Never persist these keys anywhere inside vocabulary payloads.
_FORBIDDEN_PAYLOAD_KEYS = frozenset(
    {
        "token",
        "access_token",
        "refresh_token",
        "session",
        "session_token",
        "password",
        "password_hash",
        "api_key",
        "apikey",
        "openai_api_key",
        "authorization",
        "secret",
        "bearer",
    }
)

# Sync allowlist: canonical fields + explicit legacy aliases. Unknown keys are rejected
# (do not silently drop client data while acknowledging persistence).
_ALLOWED_TOP_LEVEL_KEYS = frozenset(
    {
        "id",
        "word",
        "meaning",
        "vi",
        "nl",
        "en",
        "alternatives",
        "alt",
        "part_of_speech",
        "type",
        "examples",
        "example",
        "note",
        "pronunciation",
        "forms",
    }
)
_ALLOWED_EXAMPLE_KEYS = frozenset({"text", "meaning"})
_ALLOWED_PRONUNCIATION_KEYS = frozenset({"ipa"})
_ALLOWED_FORMS_KEYS = frozenset(FORM_FIELDS)


class SyncError(Exception):
    """Base sync-store error."""


class SyncValidationError(SyncError):
    """Invalid identity, language, payload, or operation arguments."""


class SyncSchemaError(SyncError):
    """Unsupported schema version or failed schema migration."""


class SyncConflictError(SyncError):
    """Revision mismatch, duplicate create, or tombstone resurrection attempt."""

    def __init__(self, message: str, *, current: Optional["VocabularySyncRecord"] = None):
        super().__init__(message)
        self.current = current


@dataclass(frozen=True)
class VocabularySyncRecord:
    user_id: int
    language_code: str
    vocab_id: str
    revision: int
    deleted: bool
    payload: Optional[Dict[str, Any]]
    change_cursor: int
    operation_id: str
    expected_revision: int


@dataclass(frozen=True)
class VocabularyChange:
    cursor: int
    user_id: int
    language_code: str
    vocab_id: str
    revision: int
    deleted: bool
    payload: Optional[Dict[str, Any]]
    operation_id: str
    expected_revision: int


@dataclass(frozen=True)
class LearningAttemptRecord:
    user_id: int
    event_id: str
    device_id: str
    language_code: str
    vocab_id: str
    verdict: str
    mastered: bool
    hint_used: bool
    occurred_at: str
    received_at: str
    server_seq: int
    algorithm_id: str
    word_snapshot: str
    user_answer: str
    expected_answer: str
    prompt: str


@dataclass(frozen=True)
class ProgressSnapshot:
    seen: int
    correct: int
    wrong: int
    streak: int
    interval_days: int
    due_at: str
    state_version: int
    algorithm_id: str
    last_event_id: str
    last_server_seq: int


@dataclass(frozen=True)
class ProgressAcceptResult:
    change_id: int
    server_seq: int
    event: LearningAttemptRecord
    progress_after: ProgressSnapshot


@dataclass(frozen=True)
class ProgressChange:
    change_id: int
    server_seq: int
    event: LearningAttemptRecord
    progress_after: ProgressSnapshot


def db_path(folder: str = None) -> str:
    """Path to ``study_sync.db`` under ``folder`` (default: this package directory)."""
    root = folder or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(root, DB_FILE)


def connect(path: str) -> sqlite3.Connection:
    """Open/create the sync DB at an explicit path and ensure schema."""
    if not path or not str(path).strip():
        raise SyncValidationError("Database path is required.")
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        init_schema(connection)
        return connection
    except Exception:
        try:
            connection.close()
        except Exception:
            pass
        raise


def init_schema(connection: sqlite3.Connection) -> None:
    """Create sync tables and migrate schema idempotently.

    - Fresh / v1 databases migrate through v2 to schema v3 in one write transaction.
    - v2 databases add ADR-022 progress tables and advance to v3.
    - ``expected_revision`` is backfilled as ``revision - 1`` (create → 0) on v2 path.
    - Schema version advances only after a successful migration.
    - Unsupported future schema versions are rejected **before** any modifying DDL.
    """
    # Read-only preflight — never CREATE/ALTER before this check.
    preflight = _read_existing_schema_version(connection)
    if preflight is not None and preflight > SCHEMA_VERSION:
        raise SyncSchemaError(
            f"Database schema version {preflight} is newer than supported "
            f"version {SCHEMA_VERSION}."
        )

    try:
        connection.execute("BEGIN IMMEDIATE")
        # Authoritative re-check under the write lock (concurrent migrators).
        stored = _read_existing_schema_version(connection)
        if stored is not None and stored > SCHEMA_VERSION:
            raise SyncSchemaError(
                f"Database schema version {stored} is newer than supported "
                f"version {SCHEMA_VERSION}."
            )

        if stored == SCHEMA_VERSION:
            _ensure_column(
                connection,
                "vocabulary_entities",
                "expected_revision",
                "INTEGER NOT NULL DEFAULT 0",
            )
            _ensure_column(
                connection,
                "vocabulary_changes",
                "expected_revision",
                "INTEGER NOT NULL DEFAULT 0",
            )
            _ensure_vocab_change_indexes(connection)
            _ensure_progress_schema(connection)
            connection.execute("COMMIT")
            return

        # Fresh (None) or older version → create base objects + migrate.
        _create_base_schema_objects(connection)
        if stored is None or stored < 2:
            _migrate_schema_to_v2(connection)
        else:
            _ensure_column(
                connection,
                "vocabulary_entities",
                "expected_revision",
                "INTEGER NOT NULL DEFAULT 0",
            )
            _ensure_column(
                connection,
                "vocabulary_changes",
                "expected_revision",
                "INTEGER NOT NULL DEFAULT 0",
            )
            _ensure_vocab_change_indexes(connection)
        _ensure_progress_schema(connection)
        connection.execute(
            "INSERT INTO sync_meta (key, value) VALUES ('schema_version', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (str(SCHEMA_VERSION),),
        )
        connection.execute("COMMIT")
    except Exception:
        try:
            connection.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise


def schema_version(connection: sqlite3.Connection) -> int:
    """Return the stored schema version, or ``0`` when ``sync_meta`` is absent.

    Works with default tuple rows and ``sqlite3.Row``. Raises
    ``SyncSchemaError`` when ``sync_meta`` exists but version metadata is
    missing or malformed (never treat corruption as version 0 / migrate).
    """
    existing = _read_existing_schema_version(connection)
    return 0 if existing is None else existing


def _table_exists(connection: sqlite3.Connection, name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (name,),
    ).fetchone()
    return row is not None


def _row_value(row: Any, *, index: int = 0, key: str = "value") -> Any:
    """Extract a cell from either a tuple row or ``sqlite3.Row``."""
    if row is None:
        return None
    keys = getattr(row, "keys", None)
    if callable(keys):
        try:
            available = list(keys())
            if key in available:
                return row[key]
        except Exception:
            pass
    try:
        return row[index]
    except Exception:
        try:
            return row[0]
        except Exception as error:
            raise SyncSchemaError(
                "Unable to read schema_version metadata cell."
            ) from error


def _read_existing_schema_version(connection: sqlite3.Connection) -> Optional[int]:
    """Return version int if ``sync_meta`` exists; ``None`` if the table is absent.

    Raises ``SyncSchemaError`` on missing/malformed version rows when meta exists.
    """
    if not _table_exists(connection, "sync_meta"):
        return None
    try:
        row = connection.execute(
            "SELECT value FROM sync_meta WHERE key = ?",
            ("schema_version",),
        ).fetchone()
    except sqlite3.Error as error:
        raise SyncSchemaError(
            "Unable to read schema_version metadata."
        ) from error
    if row is None:
        raise SyncSchemaError(
            "Malformed schema metadata: sync_meta exists but schema_version is missing."
        )
    raw = _row_value(row, index=0, key="value")
    text = "" if raw is None else str(raw).strip()
    if not text:
        raise SyncSchemaError("Malformed schema_version metadata.")
    try:
        version = int(text)
    except (TypeError, ValueError) as error:
        raise SyncSchemaError(
            f"Malformed schema_version metadata: {raw!r}"
        ) from error
    if version < 0:
        raise SyncSchemaError(
            f"Malformed schema_version metadata: {version}"
        )
    return version


def _create_base_schema_objects(connection: sqlite3.Connection) -> None:
    """Create v1 base tables/indexes if absent. Caller holds the write transaction."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS sync_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS vocabulary_entities (
            user_id INTEGER NOT NULL,
            language_code TEXT NOT NULL,
            vocab_id TEXT NOT NULL,
            revision INTEGER NOT NULL,
            deleted INTEGER NOT NULL DEFAULT 0,
            payload_json TEXT,
            change_cursor INTEGER NOT NULL,
            operation_id TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (user_id, language_code, vocab_id)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS vocabulary_changes (
            change_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            language_code TEXT NOT NULL,
            vocab_id TEXT NOT NULL,
            revision INTEGER NOT NULL,
            deleted INTEGER NOT NULL,
            payload_json TEXT,
            operation_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE (user_id, operation_id)
        )
        """
    )
    _ensure_vocab_change_indexes(connection)


def _ensure_vocab_change_indexes(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_vocab_changes_user_cursor
        ON vocabulary_changes (user_id, change_id)
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_vocab_changes_user_lang_cursor
        ON vocabulary_changes (user_id, language_code, change_id)
        """
    )


def _ensure_progress_schema(connection: sqlite3.Connection) -> None:
    """Create ADR-022 schema-v3 progress tables/indexes if absent."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS learning_attempts (
            user_id INTEGER NOT NULL,
            event_id TEXT NOT NULL,
            device_id TEXT NOT NULL,
            language_code TEXT NOT NULL,
            vocab_id TEXT NOT NULL,
            verdict TEXT NOT NULL,
            mastered INTEGER NOT NULL,
            hint_used INTEGER NOT NULL,
            occurred_at TEXT NOT NULL,
            received_at TEXT NOT NULL,
            server_seq INTEGER NOT NULL,
            algorithm_id TEXT NOT NULL,
            word_snapshot TEXT NOT NULL,
            user_answer TEXT NOT NULL,
            expected_answer TEXT NOT NULL,
            prompt TEXT NOT NULL,
            PRIMARY KEY (user_id, event_id)
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_learning_attempts_user_seq
        ON learning_attempts (user_id, server_seq)
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_learning_attempts_user_lang_vocab_seq
        ON learning_attempts (user_id, language_code, vocab_id, server_seq)
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS user_progress (
            user_id INTEGER NOT NULL,
            language_code TEXT NOT NULL,
            vocab_id TEXT NOT NULL,
            seen INTEGER NOT NULL,
            correct INTEGER NOT NULL,
            wrong INTEGER NOT NULL,
            streak INTEGER NOT NULL,
            interval_days INTEGER NOT NULL,
            due_at TEXT NOT NULL,
            last_event_id TEXT NOT NULL,
            last_server_seq INTEGER NOT NULL,
            algorithm_id TEXT NOT NULL,
            state_version INTEGER NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (user_id, language_code, vocab_id)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS progress_changes (
            change_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            event_id TEXT NOT NULL,
            server_seq INTEGER NOT NULL,
            seen INTEGER NOT NULL,
            correct INTEGER NOT NULL,
            wrong INTEGER NOT NULL,
            streak INTEGER NOT NULL,
            interval_days INTEGER NOT NULL,
            due_at TEXT NOT NULL,
            state_version INTEGER NOT NULL,
            algorithm_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE (user_id, event_id)
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_progress_changes_user_cursor
        ON progress_changes (user_id, change_id)
        """
    )


def _migrate_schema_to_v2(connection: sqlite3.Connection) -> None:
    """Add expected_revision and backfill from revision history.

    By construction every successful write uses ``expected_revision = revision - 1``
    (create: revision 1 → expected 0). Re-running the formula is idempotent for
    already-correct v2 rows.
    """
    _ensure_column(
        connection,
        "vocabulary_entities",
        "expected_revision",
        "INTEGER NOT NULL DEFAULT 0",
    )
    _ensure_column(
        connection,
        "vocabulary_changes",
        "expected_revision",
        "INTEGER NOT NULL DEFAULT 0",
    )
    # Reconstruct original expected_revision from revision (always revision-1 for
    # valid writes). WHERE keeps already-correct v2 values untouched.
    connection.execute(
        """
        UPDATE vocabulary_changes
        SET expected_revision = CASE
            WHEN revision > 0 THEN revision - 1
            ELSE 0
        END
        WHERE expected_revision != CASE
            WHEN revision > 0 THEN revision - 1
            ELSE 0
        END
        """
    )
    connection.execute(
        """
        UPDATE vocabulary_entities
        SET expected_revision = CASE
            WHEN revision > 0 THEN revision - 1
            ELSE 0
        END
        WHERE expected_revision != CASE
            WHEN revision > 0 THEN revision - 1
            ELSE 0
        END
        """
    )


def put_vocabulary(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    language_code: str,
    vocab_id: str,
    payload: dict,
    expected_revision: int,
    operation_id: str,
) -> VocabularySyncRecord:
    """Create or update a vocabulary entity under optimistic concurrency.

    ``expected_revision`` must be ``0`` for create, or the current revision for update.
    Replaying the same ``operation_id`` with the same mutation
    (entity, delete flag, canonical payload, expected_revision) is idempotent.
    Any mismatch is a conflict.
    """
    user_id = _require_user_id(user_id)
    language_code = _require_language(language_code)
    vocab_id = _require_vocab_id(vocab_id)
    operation_id = _require_operation_id(operation_id)
    expected_revision = _require_non_negative_int(expected_revision, "expected_revision")
    canonical = _validate_vocabulary_payload(payload, vocab_id=vocab_id)

    try:
        connection.execute("BEGIN IMMEDIATE")
        existing_op = _lookup_operation(connection, user_id, operation_id)
        if existing_op is not None:
            _assert_operation_replay_matches(
                existing_op,
                language_code=language_code,
                vocab_id=vocab_id,
                deleted=False,
                payload=canonical,
                expected_revision=expected_revision,
            )
            connection.execute("COMMIT")
            return existing_op

        current = get_vocabulary(
            connection,
            user_id=user_id,
            language_code=language_code,
            vocab_id=vocab_id,
        )
        if current is not None and current.deleted:
            raise SyncConflictError(
                "Vocabulary entity is deleted; resurrection is not allowed.",
                current=current,
            )
        if current is None:
            if expected_revision != 0:
                raise SyncConflictError(
                    "Vocabulary entity does not exist; expected_revision must be 0 to create.",
                    current=None,
                )
            new_revision = 1
        else:
            if expected_revision != current.revision:
                raise SyncConflictError(
                    "Stale vocabulary revision.",
                    current=current,
                )
            if expected_revision == 0:
                raise SyncConflictError(
                    "Vocabulary entity already exists.",
                    current=current,
                )
            new_revision = current.revision + 1

        record = _write_vocabulary_rows(
            connection,
            user_id=user_id,
            language_code=language_code,
            vocab_id=vocab_id,
            revision=new_revision,
            deleted=False,
            payload=canonical,
            operation_id=operation_id,
            expected_revision=expected_revision,
        )
        connection.execute("COMMIT")
        return record
    except Exception:
        try:
            connection.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise


def delete_vocabulary(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    language_code: str,
    vocab_id: str,
    expected_revision: int,
    operation_id: str,
) -> VocabularySyncRecord:
    """Tombstone a vocabulary entity. Requires matching ``expected_revision``."""
    user_id = _require_user_id(user_id)
    language_code = _require_language(language_code)
    vocab_id = _require_vocab_id(vocab_id)
    operation_id = _require_operation_id(operation_id)
    expected_revision = _require_non_negative_int(expected_revision, "expected_revision")
    if expected_revision < 1:
        raise SyncValidationError("expected_revision must be >= 1 for delete.")

    try:
        connection.execute("BEGIN IMMEDIATE")
        existing_op = _lookup_operation(connection, user_id, operation_id)
        if existing_op is not None:
            _assert_operation_replay_matches(
                existing_op,
                language_code=language_code,
                vocab_id=vocab_id,
                deleted=True,
                payload=None,
                expected_revision=expected_revision,
            )
            connection.execute("COMMIT")
            return existing_op

        current = get_vocabulary(
            connection,
            user_id=user_id,
            language_code=language_code,
            vocab_id=vocab_id,
        )
        if current is None:
            raise SyncConflictError("Vocabulary entity does not exist.", current=None)
        if current.deleted:
            raise SyncConflictError(
                "Vocabulary entity is already deleted.",
                current=current,
            )
        if expected_revision != current.revision:
            raise SyncConflictError("Stale vocabulary revision.", current=current)

        record = _write_vocabulary_rows(
            connection,
            user_id=user_id,
            language_code=language_code,
            vocab_id=vocab_id,
            revision=current.revision + 1,
            deleted=True,
            payload=current.payload,
            operation_id=operation_id,
            expected_revision=expected_revision,
        )
        connection.execute("COMMIT")
        return record
    except Exception:
        try:
            connection.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise


def get_vocabulary(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    language_code: str,
    vocab_id: str,
) -> Optional[VocabularySyncRecord]:
    """Return the current entity row (including tombstones), or None."""
    user_id = _require_user_id(user_id)
    language_code = _require_language(language_code)
    vocab_id = _require_vocab_id(vocab_id)
    row = connection.execute(
        """
        SELECT user_id, language_code, vocab_id, revision, deleted,
               payload_json, change_cursor, operation_id, expected_revision
        FROM vocabulary_entities
        WHERE user_id = ? AND language_code = ? AND vocab_id = ?
        """,
        (user_id, language_code, vocab_id),
    ).fetchone()
    if row is None:
        return None
    return _record_from_row(row)


def list_vocabulary_changes(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    language_code: str = None,
    after_cursor: int = 0,
    limit: int = DEFAULT_CHANGE_LIMIT,
) -> List[VocabularyChange]:
    """Return changes for ``user_id`` with ``change_id > after_cursor``, ascending.

    Optional ``language_code`` filter. ``limit`` is clamped to ``MAX_CHANGE_LIMIT``.
    """
    user_id = _require_user_id(user_id)
    after_cursor = _require_non_negative_int(after_cursor, "after_cursor")
    limit = _clamp_limit(limit)
    params: List[Any] = [user_id, after_cursor]
    lang_sql = ""
    if language_code is not None:
        language_code = _require_language(language_code)
        lang_sql = "AND language_code = ?"
        params.append(language_code)
    params.append(limit)
    rows = connection.execute(
        f"""
        SELECT change_id, user_id, language_code, vocab_id, revision, deleted,
               payload_json, operation_id, expected_revision
        FROM vocabulary_changes
        WHERE user_id = ? AND change_id > ? {lang_sql}
        ORDER BY change_id ASC
        LIMIT ?
        """,
        params,
    ).fetchall()
    return [_change_from_row(row) for row in rows]


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _ensure_column(
    connection: sqlite3.Connection, table: str, column: str, decl: str
) -> None:
    rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    names = {str(row[1]) for row in rows}
    if column not in names:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


def _write_vocabulary_rows(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    language_code: str,
    vocab_id: str,
    revision: int,
    deleted: bool,
    payload: Optional[Dict[str, Any]],
    operation_id: str,
    expected_revision: int,
) -> VocabularySyncRecord:
    """Insert change + upsert entity. Caller must already hold a write transaction."""
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    payload_json = (
        None if payload is None else json.dumps(payload, ensure_ascii=False, sort_keys=True)
    )
    cursor = connection.execute(
        """
        INSERT INTO vocabulary_changes (
            user_id, language_code, vocab_id, revision, deleted,
            payload_json, operation_id, expected_revision, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            language_code,
            vocab_id,
            revision,
            1 if deleted else 0,
            payload_json,
            operation_id,
            expected_revision,
            stamp,
        ),
    )
    change_id = int(cursor.lastrowid)
    connection.execute(
        """
        INSERT INTO vocabulary_entities (
            user_id, language_code, vocab_id, revision, deleted,
            payload_json, change_cursor, operation_id, expected_revision, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, language_code, vocab_id) DO UPDATE SET
            revision = excluded.revision,
            deleted = excluded.deleted,
            payload_json = excluded.payload_json,
            change_cursor = excluded.change_cursor,
            operation_id = excluded.operation_id,
            expected_revision = excluded.expected_revision,
            updated_at = excluded.updated_at
        """,
        (
            user_id,
            language_code,
            vocab_id,
            revision,
            1 if deleted else 0,
            payload_json,
            change_id,
            operation_id,
            expected_revision,
            stamp,
        ),
    )
    return VocabularySyncRecord(
        user_id=user_id,
        language_code=language_code,
        vocab_id=vocab_id,
        revision=revision,
        deleted=deleted,
        payload=payload,
        change_cursor=change_id,
        operation_id=operation_id,
        expected_revision=expected_revision,
    )


def _payload_fingerprint(payload: Optional[Dict[str, Any]]) -> str:
    if payload is None:
        return ""
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _assert_operation_replay_matches(
    existing: VocabularySyncRecord,
    *,
    language_code: str,
    vocab_id: str,
    deleted: bool,
    payload: Optional[Dict[str, Any]],
    expected_revision: int,
) -> None:
    """Same operation_id must replay the same mutation; otherwise conflict."""
    if existing.expected_revision != expected_revision:
        raise SyncConflictError(
            "operation_id already used with a different expected_revision.",
            current=existing,
        )
    if (
        existing.language_code != language_code
        or existing.vocab_id != vocab_id
        or existing.deleted != deleted
    ):
        raise SyncConflictError(
            "operation_id already used for a different vocabulary mutation.",
            current=existing,
        )
    if not deleted:
        if _payload_fingerprint(existing.payload) != _payload_fingerprint(payload):
            raise SyncConflictError(
                "operation_id already used with a different payload.",
                current=existing,
            )


def _lookup_operation(
    connection: sqlite3.Connection, user_id: int, operation_id: str
) -> Optional[VocabularySyncRecord]:
    row = connection.execute(
        """
        SELECT c.user_id, c.language_code, c.vocab_id, c.revision, c.deleted,
               c.payload_json, c.change_id AS change_cursor, c.operation_id,
               c.expected_revision
        FROM vocabulary_changes c
        WHERE c.user_id = ? AND c.operation_id = ?
        """,
        (user_id, operation_id),
    ).fetchone()
    if row is None:
        return None
    return _record_from_row(row)


def _validate_vocabulary_payload(payload: dict, *, vocab_id: str) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise SyncValidationError("Vocabulary payload must be an object.")

    _reject_forbidden_keys(payload, path="payload")
    unknown = sorted(set(payload.keys()) - _ALLOWED_TOP_LEVEL_KEYS)
    if unknown:
        raise SyncValidationError(
            f"Unsupported vocabulary payload fields: {unknown}"
        )

    if "pronunciation" in payload and payload["pronunciation"] is not None:
        _validate_object_keys(
            payload["pronunciation"],
            allowed=_ALLOWED_PRONUNCIATION_KEYS,
            path="pronunciation",
        )
    if "forms" in payload and payload["forms"] is not None:
        _validate_object_keys(
            payload["forms"],
            allowed=_ALLOWED_FORMS_KEYS,
            path="forms",
        )
    if "examples" in payload and payload["examples"] is not None:
        examples = payload["examples"]
        if isinstance(examples, str):
            pass  # legacy single-string examples handled by normalize_entry_dict
        elif isinstance(examples, (list, tuple)):
            for index, item in enumerate(examples):
                if isinstance(item, str):
                    continue
                if not isinstance(item, dict):
                    raise SyncValidationError(
                        f"examples[{index}] must be an object or string."
                    )
                _validate_object_keys(
                    item,
                    allowed=_ALLOWED_EXAMPLE_KEYS,
                    path=f"examples[{index}]",
                )
        else:
            raise SyncValidationError("examples must be a list or string.")

    raw = dict(payload)
    if "id" not in raw:
        raw["id"] = vocab_id
    canonical = normalize_entry_dict(raw, assign_id=False)
    if canonical is None:
        raise SyncValidationError(
            "Vocabulary payload must include a non-empty word and meaning."
        )
    payload_id = entry_id(canonical)
    if not payload_id:
        raise SyncValidationError("Vocabulary payload must include a valid UUID id.")
    if payload_id != vocab_id:
        raise SyncValidationError(
            "Vocabulary payload id must match the entity vocab_id."
        )
    # Persist canonical form only (legacy aliases normalized away).
    return canonical


def _validate_object_keys(value: Any, *, allowed: Set[str], path: str) -> None:
    if not isinstance(value, dict):
        raise SyncValidationError(f"{path} must be an object.")
    _reject_forbidden_keys(value, path=path)
    unknown = sorted(set(value.keys()) - allowed)
    if unknown:
        raise SyncValidationError(f"Unsupported fields under {path}: {unknown}")


def _reject_forbidden_keys(value: Any, *, path: str) -> None:
    """Recursively reject sensitive keys in dicts and list elements."""
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key).strip().lower()
            if key_text in _FORBIDDEN_PAYLOAD_KEYS:
                raise SyncValidationError(
                    f"Vocabulary payload must not contain secrets at {path}.{key}"
                )
            _reject_forbidden_keys(child, path=f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _reject_forbidden_keys(child, path=f"{path}[{index}]")


def _require_user_id(user_id: Any) -> int:
    value = _require_strict_int(user_id, "user_id")
    if value < 1:
        raise SyncValidationError("user_id must be a positive integer.")
    return value


def _require_language(language_code: Any) -> str:
    code = str(language_code or "").strip().lower()
    if not languages.is_supported_language(code):
        raise SyncValidationError(f"Unsupported study language: {language_code!r}")
    return code


def _require_vocab_id(vocab_id: Any) -> str:
    text = str(vocab_id or "").strip()
    if not is_vocab_id(text):
        raise SyncValidationError(f"Invalid vocabulary UUID: {vocab_id!r}")
    return text


def _require_operation_id(operation_id: Any) -> str:
    text = str(operation_id or "").strip()
    if not text or len(text) > 128:
        raise SyncValidationError("operation_id must be 1..128 characters.")
    return text


def _require_strict_int(value: Any, name: str) -> int:
    """Accept only real ints — reject bool and float."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise SyncValidationError(f"{name} must be an integer.")
    return value


def _require_non_negative_int(value: Any, name: str) -> int:
    number = _require_strict_int(value, name)
    if number < 0:
        raise SyncValidationError(f"{name} must be >= 0.")
    return number


def _clamp_limit(limit: Any) -> int:
    value = _require_strict_int(limit, "limit")
    if value < 1:
        raise SyncValidationError("limit must be >= 1.")
    return min(value, MAX_CHANGE_LIMIT)


def _loads_payload(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    if raw is None or raw == "":
        return None
    data = json.loads(raw)
    if data is None:
        return None
    if not isinstance(data, dict):
        raise SyncValidationError("Stored payload is not an object.")
    return data


def _record_from_row(row: sqlite3.Row) -> VocabularySyncRecord:
    keys = set(row.keys())
    expected = int(row["expected_revision"]) if "expected_revision" in keys else 0
    return VocabularySyncRecord(
        user_id=int(row["user_id"]),
        language_code=str(row["language_code"]),
        vocab_id=str(row["vocab_id"]),
        revision=int(row["revision"]),
        deleted=bool(int(row["deleted"])),
        payload=_loads_payload(row["payload_json"]),
        change_cursor=int(row["change_cursor"]),
        operation_id=str(row["operation_id"]),
        expected_revision=expected,
    )


def _change_from_row(row: sqlite3.Row) -> VocabularyChange:
    keys = set(row.keys())
    expected = int(row["expected_revision"]) if "expected_revision" in keys else 0
    return VocabularyChange(
        cursor=int(row["change_id"]),
        user_id=int(row["user_id"]),
        language_code=str(row["language_code"]),
        vocab_id=str(row["vocab_id"]),
        revision=int(row["revision"]),
        deleted=bool(int(row["deleted"])),
        payload=_loads_payload(row["payload_json"]),
        operation_id=str(row["operation_id"]),
        expected_revision=expected,
    )


_PROGRESS_EVENT_KEYS = frozenset(
    {
        "event_id",
        "device_id",
        "language_code",
        "vocab_id",
        "verdict",
        "mastered",
        "hint_used",
        "occurred_at",
        "algorithm_id",
        "word_snapshot",
        "user_answer",
        "expected_answer",
        "prompt",
    }
)
_VERDICTS = frozenset({"exact", "near", "wrong"})
_TEXT_FIELDS = ("word_snapshot", "user_answer", "expected_answer", "prompt")
_MAX_ATTEMPT_TEXT = 500


def accept_learning_attempt(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    event: dict,
) -> ProgressAcceptResult:
    """Accept one learning attempt under ADR-022 rules (idempotent by event_id)."""
    user_id = _require_user_id(user_id)
    prepared = _validate_progress_event(event)

    try:
        connection.execute("BEGIN IMMEDIATE")
        existing = _lookup_learning_attempt(
            connection, user_id=user_id, event_id=prepared["event_id"]
        )
        if existing is not None:
            _assert_attempt_replay_matches(existing, prepared)
            change = _lookup_progress_change(
                connection, user_id=user_id, event_id=prepared["event_id"]
            )
            if change is None:
                raise SyncSchemaError(
                    "Accepted attempt is missing its progress_changes journal row."
                )
            connection.execute("COMMIT")
            return change

        from srs import apply_review_to_stats, to_utc_iso, utc_now

        received_at_dt = utc_now()
        received_at = to_utc_iso(received_at_dt)
        next_seq_row = connection.execute(
            "SELECT COALESCE(MAX(server_seq), 0) + 1 FROM learning_attempts WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        server_seq = int(next_seq_row[0])

        connection.execute(
            """
            INSERT INTO learning_attempts (
                user_id, event_id, device_id, language_code, vocab_id,
                verdict, mastered, hint_used, occurred_at, received_at,
                server_seq, algorithm_id, word_snapshot, user_answer,
                expected_answer, prompt
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                prepared["event_id"],
                prepared["device_id"],
                prepared["language_code"],
                prepared["vocab_id"],
                prepared["verdict"],
                1 if prepared["mastered"] else 0,
                1 if prepared["hint_used"] else 0,
                prepared["occurred_at"],
                received_at,
                server_seq,
                prepared["algorithm_id"],
                prepared["word_snapshot"],
                prepared["user_answer"],
                prepared["expected_answer"],
                prepared["prompt"],
            ),
        )

        progress_row = connection.execute(
            """
            SELECT seen, correct, wrong, streak, interval_days, due_at,
                   last_event_id, last_server_seq, algorithm_id, state_version
            FROM user_progress
            WHERE user_id = ? AND language_code = ? AND vocab_id = ?
            """,
            (user_id, prepared["language_code"], prepared["vocab_id"]),
        ).fetchone()
        if progress_row is None:
            stats = {
                "seen": 0,
                "correct": 0,
                "wrong": 0,
                "streak": 0,
                "interval_days": 0,
                "due_at": received_at,
            }
            state_version = 0
        else:
            stats = {
                "seen": int(progress_row["seen"]),
                "correct": int(progress_row["correct"]),
                "wrong": int(progress_row["wrong"]),
                "streak": int(progress_row["streak"]),
                "interval_days": int(progress_row["interval_days"]),
                "due_at": str(progress_row["due_at"]),
            }
            state_version = int(progress_row["state_version"])

        stats["seen"] += 1
        mastered = bool(prepared["mastered"])
        if mastered:
            stats["correct"] += 1
            stats["streak"] += 1
        else:
            stats["wrong"] += 1
            stats["streak"] = 0
        apply_review_to_stats(stats, mastered=mastered, reviewed_at=received_at_dt)
        state_version += 1
        updated_at = received_at

        connection.execute(
            """
            INSERT INTO user_progress (
                user_id, language_code, vocab_id, seen, correct, wrong, streak,
                interval_days, due_at, last_event_id, last_server_seq,
                algorithm_id, state_version, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, language_code, vocab_id) DO UPDATE SET
                seen = excluded.seen,
                correct = excluded.correct,
                wrong = excluded.wrong,
                streak = excluded.streak,
                interval_days = excluded.interval_days,
                due_at = excluded.due_at,
                last_event_id = excluded.last_event_id,
                last_server_seq = excluded.last_server_seq,
                algorithm_id = excluded.algorithm_id,
                state_version = excluded.state_version,
                updated_at = excluded.updated_at
            """,
            (
                user_id,
                prepared["language_code"],
                prepared["vocab_id"],
                int(stats["seen"]),
                int(stats["correct"]),
                int(stats["wrong"]),
                int(stats["streak"]),
                int(stats["interval_days"]),
                str(stats["due_at"]),
                prepared["event_id"],
                server_seq,
                prepared["algorithm_id"],
                state_version,
                updated_at,
            ),
        )

        cursor = connection.execute(
            """
            INSERT INTO progress_changes (
                user_id, event_id, server_seq, seen, correct, wrong, streak,
                interval_days, due_at, state_version, algorithm_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                prepared["event_id"],
                server_seq,
                int(stats["seen"]),
                int(stats["correct"]),
                int(stats["wrong"]),
                int(stats["streak"]),
                int(stats["interval_days"]),
                str(stats["due_at"]),
                state_version,
                prepared["algorithm_id"],
                updated_at,
            ),
        )
        change_id = int(cursor.lastrowid)
        attempt = LearningAttemptRecord(
            user_id=user_id,
            event_id=prepared["event_id"],
            device_id=prepared["device_id"],
            language_code=prepared["language_code"],
            vocab_id=prepared["vocab_id"],
            verdict=prepared["verdict"],
            mastered=mastered,
            hint_used=bool(prepared["hint_used"]),
            occurred_at=prepared["occurred_at"],
            received_at=received_at,
            server_seq=server_seq,
            algorithm_id=prepared["algorithm_id"],
            word_snapshot=prepared["word_snapshot"],
            user_answer=prepared["user_answer"],
            expected_answer=prepared["expected_answer"],
            prompt=prepared["prompt"],
        )
        snapshot = ProgressSnapshot(
            seen=int(stats["seen"]),
            correct=int(stats["correct"]),
            wrong=int(stats["wrong"]),
            streak=int(stats["streak"]),
            interval_days=int(stats["interval_days"]),
            due_at=str(stats["due_at"]),
            state_version=state_version,
            algorithm_id=prepared["algorithm_id"],
            last_event_id=prepared["event_id"],
            last_server_seq=server_seq,
        )
        connection.execute("COMMIT")
        return ProgressAcceptResult(
            change_id=change_id,
            server_seq=server_seq,
            event=attempt,
            progress_after=snapshot,
        )
    except Exception:
        try:
            connection.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise


def list_progress_changes(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    after_cursor: int = 0,
    limit: int = PROGRESS_CHANGE_LIMIT,
    language_code: Optional[str] = None,
) -> List[ProgressChange]:
    """Page progress_changes for one account, ordered by change_id ascending."""
    user_id = _require_user_id(user_id)
    after_cursor = _require_non_negative_int(after_cursor, "after_cursor")
    limit = _clamp_progress_limit(limit)
    params: List[Any] = [user_id, after_cursor]
    language_filter = ""
    if language_code is not None:
        code = _require_language(language_code)
        language_filter = " AND a.language_code = ?"
        params.append(code)
    params.append(limit)
    rows = connection.execute(
        f"""
        SELECT
            c.change_id, c.server_seq, c.seen, c.correct, c.wrong, c.streak,
            c.interval_days, c.due_at, c.state_version, c.algorithm_id,
            a.user_id, a.event_id, a.device_id, a.language_code, a.vocab_id,
            a.verdict, a.mastered, a.hint_used, a.occurred_at, a.received_at,
            a.server_seq AS event_server_seq, a.algorithm_id AS event_algorithm_id,
            a.word_snapshot, a.user_answer, a.expected_answer, a.prompt
        FROM progress_changes c
        JOIN learning_attempts a
          ON a.user_id = c.user_id AND a.event_id = c.event_id
        WHERE c.user_id = ? AND c.change_id > ?{language_filter}
        ORDER BY c.change_id ASC
        LIMIT ?
        """,
        params,
    ).fetchall()
    return [_progress_change_from_row(row) for row in rows]


def _clamp_progress_limit(limit: Any) -> int:
    value = _require_strict_int(limit, "limit")
    if value < 1:
        raise SyncValidationError("limit must be >= 1.")
    return min(value, PROGRESS_CHANGE_LIMIT)


def _validate_progress_event(event: Any) -> Dict[str, Any]:
    if not isinstance(event, dict):
        raise SyncValidationError("Progress event must be an object.")
    _reject_forbidden_keys(event, path="event")
    unknown = sorted(set(event.keys()) - _PROGRESS_EVENT_KEYS)
    if unknown:
        raise SyncValidationError(f"Unsupported progress event fields: {unknown}")
    missing = sorted(_PROGRESS_EVENT_KEYS - set(event.keys()))
    if missing:
        raise SyncValidationError(f"Missing progress event fields: {missing}")
    if "user_id" in event:
        raise SyncValidationError("user_id is not allowed in progress event bodies.")

    event_id = _require_event_id(event["event_id"])
    device_id = _require_event_id(event["device_id"], name="device_id")
    language_code = _require_language(event["language_code"])
    vocab_id = _require_vocab_id(event["vocab_id"])
    verdict = str(event["verdict"] or "").strip().lower()
    if verdict not in _VERDICTS:
        raise SyncValidationError("verdict must be exact, near, or wrong.")
    mastered = _require_bool_int(event["mastered"], "mastered")
    hint_used = _require_bool_int(event["hint_used"], "hint_used")
    if mastered and (verdict != "exact" or hint_used):
        raise SyncValidationError(
            "mastered may be true only when verdict is exact and hint_used is false."
        )
    algorithm_id = str(event["algorithm_id"] or "").strip()
    if algorithm_id != ALGORITHM_LADDER_V2:
        raise SyncValidationError(
            f"Unsupported algorithm_id: {algorithm_id!r} (only {ALGORITHM_LADDER_V2})."
        )
    occurred_at = _require_iso_timestamp(event["occurred_at"], "occurred_at")
    texts = {
        name: _require_bounded_text(event[name], name, allow_empty=(name != "expected_answer"))
        for name in _TEXT_FIELDS
    }
    # New quiz events require non-empty expected_answer (ADR-022).
    if not str(texts["expected_answer"]).strip():
        raise SyncValidationError("expected_answer must be non-empty for new events.")
    return {
        "event_id": event_id,
        "device_id": device_id,
        "language_code": language_code,
        "vocab_id": vocab_id,
        "verdict": verdict,
        "mastered": mastered,
        "hint_used": hint_used,
        "occurred_at": occurred_at,
        "algorithm_id": algorithm_id,
        **texts,
    }


def _require_event_id(value: Any, name: str = "event_id") -> str:
    text = str(value or "").strip()
    if not text or len(text) > 128:
        raise SyncValidationError(f"{name} must be 1..128 characters.")
    return text


def _require_bool_int(value: Any, name: str) -> bool:
    if isinstance(value, bool):
        raise SyncValidationError(f"{name} must be an integer 0 or 1.")
    if not isinstance(value, int) or value not in (0, 1):
        raise SyncValidationError(f"{name} must be an integer 0 or 1.")
    return bool(value)


def _require_bounded_text(value: Any, name: str, *, allow_empty: bool) -> str:
    if not isinstance(value, str):
        raise SyncValidationError(f"{name} must be a string.")
    if len(value) > _MAX_ATTEMPT_TEXT:
        raise SyncValidationError(f"{name} exceeds {_MAX_ATTEMPT_TEXT} characters.")
    if not allow_empty and not value.strip():
        raise SyncValidationError(f"{name} must be non-empty.")
    return value


def _require_iso_timestamp(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SyncValidationError(f"{name} must be an ISO-8601 timestamp string.")
    from srs import parse_utc

    parsed = parse_utc(value)
    if parsed is None:
        raise SyncValidationError(f"{name} must be a valid ISO-8601 timestamp.")
    from srs import to_utc_iso

    return to_utc_iso(parsed)


def _lookup_learning_attempt(
    connection: sqlite3.Connection, *, user_id: int, event_id: str
) -> Optional[LearningAttemptRecord]:
    row = connection.execute(
        """
        SELECT user_id, event_id, device_id, language_code, vocab_id, verdict,
               mastered, hint_used, occurred_at, received_at, server_seq,
               algorithm_id, word_snapshot, user_answer, expected_answer, prompt
        FROM learning_attempts
        WHERE user_id = ? AND event_id = ?
        """,
        (user_id, event_id),
    ).fetchone()
    if row is None:
        return None
    return _attempt_from_row(row)


def _lookup_progress_change(
    connection: sqlite3.Connection, *, user_id: int, event_id: str
) -> Optional[ProgressAcceptResult]:
    row = connection.execute(
        """
        SELECT
            c.change_id, c.server_seq, c.seen, c.correct, c.wrong, c.streak,
            c.interval_days, c.due_at, c.state_version, c.algorithm_id,
            a.user_id, a.event_id, a.device_id, a.language_code, a.vocab_id,
            a.verdict, a.mastered, a.hint_used, a.occurred_at, a.received_at,
            a.server_seq AS event_server_seq, a.algorithm_id AS event_algorithm_id,
            a.word_snapshot, a.user_answer, a.expected_answer, a.prompt
        FROM progress_changes c
        JOIN learning_attempts a
          ON a.user_id = c.user_id AND a.event_id = c.event_id
        WHERE c.user_id = ? AND c.event_id = ?
        """,
        (user_id, event_id),
    ).fetchone()
    if row is None:
        return None
    change = _progress_change_from_row(row)
    return ProgressAcceptResult(
        change_id=change.change_id,
        server_seq=change.server_seq,
        event=change.event,
        progress_after=change.progress_after,
    )


def _assert_attempt_replay_matches(
    existing: LearningAttemptRecord, prepared: Dict[str, Any]
) -> None:
    if (
        existing.device_id != prepared["device_id"]
        or existing.language_code != prepared["language_code"]
        or existing.vocab_id != prepared["vocab_id"]
        or existing.verdict != prepared["verdict"]
        or existing.mastered != bool(prepared["mastered"])
        or existing.hint_used != bool(prepared["hint_used"])
        or existing.occurred_at != prepared["occurred_at"]
        or existing.algorithm_id != prepared["algorithm_id"]
        or existing.word_snapshot != prepared["word_snapshot"]
        or existing.user_answer != prepared["user_answer"]
        or existing.expected_answer != prepared["expected_answer"]
        or existing.prompt != prepared["prompt"]
    ):
        raise SyncConflictError(
            "event_id already used with a different attempt body.",
            current=None,
        )


def _attempt_from_row(row: sqlite3.Row) -> LearningAttemptRecord:
    return LearningAttemptRecord(
        user_id=int(row["user_id"]),
        event_id=str(row["event_id"]),
        device_id=str(row["device_id"]),
        language_code=str(row["language_code"]),
        vocab_id=str(row["vocab_id"]),
        verdict=str(row["verdict"]),
        mastered=bool(int(row["mastered"])),
        hint_used=bool(int(row["hint_used"])),
        occurred_at=str(row["occurred_at"]),
        received_at=str(row["received_at"]),
        server_seq=int(row["server_seq"]),
        algorithm_id=str(row["algorithm_id"]),
        word_snapshot=str(row["word_snapshot"]),
        user_answer=str(row["user_answer"]),
        expected_answer=str(row["expected_answer"]),
        prompt=str(row["prompt"]),
    )


def _progress_change_from_row(row: sqlite3.Row) -> ProgressChange:
    event = LearningAttemptRecord(
        user_id=int(row["user_id"]),
        event_id=str(row["event_id"]),
        device_id=str(row["device_id"]),
        language_code=str(row["language_code"]),
        vocab_id=str(row["vocab_id"]),
        verdict=str(row["verdict"]),
        mastered=bool(int(row["mastered"])),
        hint_used=bool(int(row["hint_used"])),
        occurred_at=str(row["occurred_at"]),
        received_at=str(row["received_at"]),
        server_seq=int(row["event_server_seq"]),
        algorithm_id=str(row["event_algorithm_id"]),
        word_snapshot=str(row["word_snapshot"]),
        user_answer=str(row["user_answer"]),
        expected_answer=str(row["expected_answer"]),
        prompt=str(row["prompt"]),
    )
    snapshot = ProgressSnapshot(
        seen=int(row["seen"]),
        correct=int(row["correct"]),
        wrong=int(row["wrong"]),
        streak=int(row["streak"]),
        interval_days=int(row["interval_days"]),
        due_at=str(row["due_at"]),
        state_version=int(row["state_version"]),
        algorithm_id=str(row["algorithm_id"]),
        last_event_id=str(row["event_id"]),
        last_server_seq=int(row["server_seq"]),
    )
    return ProgressChange(
        change_id=int(row["change_id"]),
        server_seq=int(row["server_seq"]),
        event=event,
        progress_after=snapshot,
    )
