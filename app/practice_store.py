"""Isolated SQLite file for practice records.

This is not account_study.db. It has no outbox and no SRS tables.
The caller passes an explicit data root. Production AppData, protected RC
data, and recovery directories are refused for every runtime identity.
Nothing here imports guest rows into an account file.

Growth is one small row per submitted recognition or assisted exercise.
Rows are not updated and this phase does not delete them. A future account
or guest deletion must remove this file with that data root. A future
retention pass may drop old rows and must not rewrite the rows it keeps.
Stale rows stay stored; the start policy ignores them after 14 days.
"""

from __future__ import annotations

import os
import sqlite3
from typing import Optional, Sequence

from app_environment import (
    DATA_FOLDER,
    ENV_PRODUCTION,
    RC_DATA_FOLDER,
    RECOVERY_FOLDER,
    normalize_fs_path,
    paths_overlap,
    production_data_dir,
    production_install_dir,
)
from languages import is_supported_language
from practice_record import (
    FORMAT_VERSION,
    PracticeRecord,
    PracticeRecordError,
    validate_practice_record,
)

PRACTICE_DB_FILE = "practice_records.db"
SCHEMA_VERSION = 1

_COLUMNS = (
    "practice_event_id",
    "exercise_instance_id",
    "session_id",
    "vocab_id",
    "language_code",
    "actual_kind",
    "intended_kind",
    "support_level",
    "outcome",
    "error_class",
    "occurred_at",
    "policy_id",
    "format_version",
    "owner_scope",
)


class PracticeStoreError(RuntimeError):
    """The practice file could not be read or written."""


def refuse_practice_data_root(
    path: str,
    *,
    appdata: Optional[str] = None,
    localappdata: Optional[str] = None,
) -> Optional[str]:
    """Refuse empty roots and protected directories for every runtime identity."""
    raw = str(path or "").strip()
    if not raw:
        return "practice store needs an explicit directory"
    candidate = normalize_fs_path(raw)
    if not candidate:
        return "practice store needs an explicit directory"
    prod_data = production_data_dir(appdata=appdata)
    prod_install = production_install_dir(localappdata=localappdata)
    if paths_overlap(candidate, prod_data):
        return f"practice store refused production AppData: {prod_data}"
    if paths_overlap(candidate, prod_install):
        return f"practice store refused production install dir: {prod_install}"
    app_root = appdata if appdata is not None else (os.environ.get("APPDATA") or os.path.expanduser("~"))
    local_root = (
        localappdata
        if localappdata is not None
        else (os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or os.path.expanduser("~"))
    )
    rc_root = os.path.join(app_root, RC_DATA_FOLDER)
    recovery_root = os.path.join(local_root, RECOVERY_FOLDER)
    if paths_overlap(candidate, rc_root):
        return "practice store refused the protected RC AppData directory"
    if paths_overlap(candidate, recovery_root):
        return "practice store refused the recovery directory"
    base = os.path.basename(candidate.rstrip("\\/"))
    if os.path.normcase(base) == os.path.normcase(RC_DATA_FOLDER):
        return "practice store refused the protected RC folder name"
    if os.path.normcase(base) == os.path.normcase(RECOVERY_FOLDER):
        return "practice store refused the recovery folder name"
    if os.path.normcase(base) == os.path.normcase(DATA_FOLDER[ENV_PRODUCTION]):
        return f"practice store refused production folder name {base!r}"
    return None


def _resolved_under_root(path: str, root: str) -> bool:
    candidate = normalize_fs_path(path)
    base = normalize_fs_path(root)
    if not candidate or not base:
        return False
    left = os.path.normcase(candidate)
    right = os.path.normcase(base)
    if left == right:
        return False
    return left.startswith(right + os.sep)


class PracticeStore:
    """One append-only file for one guest language or one account."""

    def __init__(self, db_path: str, *, data_root: str, owner_scope: str, language_code: str = ""):
        self._connection = None
        scope = str(owner_scope or "").strip().lower()
        if scope not in ("guest", "account"):
            raise PracticeStoreError("practice owner is not guest or account")
        raw_root = str(data_root or "").strip()
        raw_path = str(db_path or "").strip()
        if not raw_root or not raw_path:
            raise PracticeStoreError("practice store needs an explicit directory")
        problem = refuse_practice_data_root(raw_root)
        if problem:
            raise PracticeStoreError(problem)
        root = normalize_fs_path(raw_root)
        path = normalize_fs_path(raw_path)
        if not root or not path:
            raise PracticeStoreError("practice store needs an explicit directory")
        if os.path.basename(path).lower() == "account_study.db":
            raise PracticeStoreError("practice records do not use account_study.db")
        if not _resolved_under_root(path, root):
            raise PracticeStoreError("practice file is outside its data root")
        self.data_root = root
        self.db_path = path
        self.owner_scope = scope
        self.language_code = str(language_code or "").strip().lower()
        if scope == "guest":
            if not self.language_code or not is_supported_language(self.language_code):
                raise PracticeStoreError("guest practice store needs a supported study language")
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            self._connection = sqlite3.connect(path, check_same_thread=False)
            self._connection.row_factory = sqlite3.Row
            self._prepare()
        except PracticeStoreError:
            self._close_quietly()
            raise
        except sqlite3.Error as error:
            self._close_quietly()
            raise PracticeStoreError("practice store was not opened") from error
        except OSError as error:
            self._close_quietly()
            raise PracticeStoreError("practice store was not opened") from error

    def close(self) -> None:
        self._close_quietly()

    def append(self, record: PracticeRecord) -> PracticeRecord:
        """Insert one submission. The same exercise instance returns the stored row."""
        try:
            validate_practice_record(record)
        except PracticeRecordError as error:
            raise PracticeStoreError(str(error)) from error
        if self.owner_scope == "guest" and record.language_code != self.language_code:
            raise PracticeStoreError("guest practice language does not match this file")
        try:
            self._connection.execute("BEGIN IMMEDIATE")
        except sqlite3.Error as error:
            raise PracticeStoreError("practice record was not saved") from error
        try:
            existing = self._find_locked(record)
            if existing is not None:
                if _same_submission(existing, record):
                    self._connection.rollback()
                    return existing
                raise PracticeStoreError("exercise submission already recorded")
            self._connection.execute(
                f"""
                INSERT INTO practice_records ({", ".join(_COLUMNS)})
                VALUES ({", ".join("?" for _ in _COLUMNS)})
                """,
                _values(record, self.owner_scope),
            )
            self._connection.commit()
        except PracticeStoreError:
            try:
                self._connection.rollback()
            except sqlite3.Error:
                pass
            raise
        except sqlite3.Error as error:
            try:
                self._connection.rollback()
            except sqlite3.Error:
                pass
            raise PracticeStoreError("practice record was not saved") from error
        return record

    def for_vocab(self, vocab_id: str, language_code: str) -> list[PracticeRecord]:
        code = str(language_code or "").strip().lower()
        try:
            rows = self._connection.execute(
                """
                SELECT * FROM practice_records
                WHERE vocab_id = ? AND language_code = ?
                ORDER BY occurred_at, rowid
                """,
                (str(vocab_id or "").strip(), code),
            ).fetchall()
        except sqlite3.Error as error:
            raise PracticeStoreError("practice records could not be read") from error
        found = []
        for row in rows:
            try:
                record = _from_row(row)
                validate_practice_record(record)
            except (PracticeRecordError, KeyError, TypeError, ValueError):
                continue
            found.append(record)
        return found

    def count(self) -> int:
        try:
            return int(self._connection.execute("SELECT COUNT(*) FROM practice_records").fetchone()[0])
        except sqlite3.Error as error:
            raise PracticeStoreError("practice records could not be read") from error

    def _close_quietly(self) -> None:
        connection = self._connection
        self._connection = None
        if connection is None:
            return
        try:
            connection.close()
        except sqlite3.Error:
            pass

    def _prepare(self) -> None:
        try:
            self._connection.execute("BEGIN IMMEDIATE")
        except sqlite3.Error as error:
            raise PracticeStoreError("practice store was not opened") from error
        try:
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            current = self._connection.execute(
                "SELECT value FROM meta WHERE key = 'schema_version'"
            ).fetchone()
            if current is not None and int(current[0]) != SCHEMA_VERSION:
                raise PracticeStoreError("practice store version is not supported")
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS practice_records (
                    practice_event_id TEXT PRIMARY KEY,
                    exercise_instance_id TEXT NOT NULL UNIQUE,
                    session_id TEXT NOT NULL,
                    vocab_id TEXT NOT NULL,
                    language_code TEXT NOT NULL,
                    actual_kind TEXT NOT NULL,
                    intended_kind TEXT NOT NULL,
                    support_level TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    error_class TEXT NOT NULL DEFAULT '',
                    occurred_at TEXT NOT NULL,
                    policy_id TEXT NOT NULL,
                    format_version INTEGER NOT NULL,
                    owner_scope TEXT NOT NULL
                )
                """
            )
            self._connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_practice_vocab_lang
                ON practice_records (language_code, vocab_id, occurred_at)
                """
            )
            self._connection.execute(
                """
                INSERT INTO meta (key, value) VALUES ('schema_version', ?)
                ON CONFLICT(key) DO NOTHING
                """,
                (str(SCHEMA_VERSION),),
            )
            self._connection.execute(
                """
                INSERT INTO meta (key, value) VALUES ('format_version', ?)
                ON CONFLICT(key) DO NOTHING
                """,
                (str(FORMAT_VERSION),),
            )
            self._connection.commit()
        except PracticeStoreError:
            try:
                self._connection.rollback()
            except sqlite3.Error:
                pass
            raise
        except (sqlite3.Error, TypeError, ValueError) as error:
            try:
                self._connection.rollback()
            except sqlite3.Error:
                pass
            raise PracticeStoreError("practice store was not opened") from error

    def _find_locked(self, record: PracticeRecord) -> Optional[PracticeRecord]:
        row = self._connection.execute(
            """
            SELECT * FROM practice_records
            WHERE exercise_instance_id = ? OR practice_event_id = ?
            """,
            (record.exercise_instance_id, record.practice_event_id),
        ).fetchone()
        if row is None:
            return None
        try:
            found = _from_row(row)
            validate_practice_record(found)
        except (PracticeRecordError, KeyError, TypeError, ValueError) as error:
            raise PracticeStoreError("stored practice row is invalid") from error
        return found


def open_guest_store(data_root: str, language_code: str) -> PracticeStore:
    code = str(language_code or "").strip().lower()
    if not str(data_root or "").strip():
        raise PracticeStoreError("practice store needs an explicit directory")
    root = normalize_fs_path(data_root)
    path = os.path.join(root, "languages", code, PRACTICE_DB_FILE)
    return PracticeStore(path, data_root=root, owner_scope="guest", language_code=code)


def open_account_store(data_root: str, user_id: int) -> PracticeStore:
    if not str(data_root or "").strip():
        raise PracticeStoreError("practice store needs an explicit directory")
    root = normalize_fs_path(data_root)
    path = os.path.join(root, "accounts", str(int(user_id)), PRACTICE_DB_FILE)
    return PracticeStore(path, data_root=root, owner_scope="account")


def _values(record: PracticeRecord, owner_scope: str) -> tuple:
    return (
        record.practice_event_id,
        record.exercise_instance_id,
        record.session_id,
        record.vocab_id,
        record.language_code,
        record.actual_kind,
        record.intended_kind,
        record.support_level,
        record.outcome,
        record.error_class,
        record.occurred_at,
        record.policy_id,
        record.format_version,
        owner_scope,
    )


def _from_row(row: sqlite3.Row) -> PracticeRecord:
    return PracticeRecord(
        practice_event_id=row["practice_event_id"],
        exercise_instance_id=row["exercise_instance_id"],
        session_id=row["session_id"],
        vocab_id=row["vocab_id"],
        language_code=row["language_code"],
        actual_kind=row["actual_kind"],
        intended_kind=row["intended_kind"],
        support_level=row["support_level"],
        outcome=row["outcome"],
        error_class=row["error_class"],
        occurred_at=row["occurred_at"],
        policy_id=row["policy_id"],
        format_version=int(row["format_version"]),
    )


def _same_submission(stored: PracticeRecord, incoming: PracticeRecord) -> bool:
    return (
        stored.exercise_instance_id == incoming.exercise_instance_id
        and stored.session_id == incoming.session_id
        and stored.vocab_id == incoming.vocab_id
        and stored.language_code == incoming.language_code
        and stored.actual_kind == incoming.actual_kind
        and stored.intended_kind == incoming.intended_kind
        and stored.outcome == incoming.outcome
        and stored.support_level == incoming.support_level
        and stored.error_class == incoming.error_class
    )


def load_history(store: PracticeStore, vocab_ids: Sequence[str], language_code: str) -> list[PracticeRecord]:
    found = []
    for vocab_id in vocab_ids:
        found.extend(store.for_vocab(vocab_id, language_code))
    return found
