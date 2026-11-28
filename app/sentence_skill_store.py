"""Isolated SQLite file for SentenceSkillRecord (Phase 19.5B).

Separate from practice_records.db and account_study.db. No outbox, no SRS.
No automatic retention deletion in this phase. No guest-to-account import.

Growth: one small metadata row per recordable sentence submission.
Future account/guest deletion must remove this file with that data root.
A future retention pass may drop old rows and must not rewrite kept rows.
"""

from __future__ import annotations

import json
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
from sentence_skill_record import (
    RECORD_FORMAT_VERSION,
    SentenceSkillRecord,
    SentenceSkillRecordError,
    parse_utc,
    validate_sentence_skill_record,
)

SENTENCE_SKILL_DB_FILE = "sentence_skill_records.db"
SCHEMA_VERSION = 1

_COLUMNS = (
    "skill_event_id",
    "session_id",
    "exercise_instance_id",
    "submission_id",
    "exercise_id",
    "family_id",
    "content_version",
    "format_version",
    "study_language",
    "cefr_level",
    "exercise_kind",
    "support_level",
    "outcome",
    "grading_source",
    "error_classification",
    "evidence_status",
    "grammar_skill_refs_json",
    "occurred_at",
    "selection_policy_id",
    "owner_scope",
)


class SentenceSkillStoreError(RuntimeError):
    """The sentence-skill file could not be read or written."""


def refuse_sentence_skill_data_root(
    path: str,
    *,
    appdata: Optional[str] = None,
    localappdata: Optional[str] = None,
) -> Optional[str]:
    """Refuse empty roots and protected directories for every runtime identity."""
    raw = str(path or "").strip()
    if not raw:
        return "sentence skill store needs an explicit directory"
    candidate = normalize_fs_path(raw)
    if not candidate:
        return "sentence skill store needs an explicit directory"
    prod_data = production_data_dir(appdata=appdata)
    prod_install = production_install_dir(localappdata=localappdata)
    if paths_overlap(candidate, prod_data):
        return f"sentence skill store refused production AppData: {prod_data}"
    if paths_overlap(candidate, prod_install):
        return f"sentence skill store refused production install dir: {prod_install}"
    app_root = appdata if appdata is not None else (os.environ.get("APPDATA") or os.path.expanduser("~"))
    local_root = (
        localappdata
        if localappdata is not None
        else (os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or os.path.expanduser("~"))
    )
    rc_root = os.path.join(app_root, RC_DATA_FOLDER)
    recovery_root = os.path.join(local_root, RECOVERY_FOLDER)
    if paths_overlap(candidate, rc_root):
        return "sentence skill store refused the protected RC AppData directory"
    if paths_overlap(candidate, recovery_root):
        return "sentence skill store refused the recovery directory"
    base = os.path.basename(candidate.rstrip("\\/"))
    if os.path.normcase(base) == os.path.normcase(RC_DATA_FOLDER):
        return "sentence skill store refused the protected RC folder name"
    if os.path.normcase(base) == os.path.normcase(RECOVERY_FOLDER):
        return "sentence skill store refused the recovery folder name"
    if os.path.normcase(base) == os.path.normcase(DATA_FOLDER[ENV_PRODUCTION]):
        return f"sentence skill store refused production folder name {base!r}"
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


class SentenceSkillStore:
    """One append-only file for one guest language or one account."""

    def __init__(self, db_path: str, *, data_root: str, owner_scope: str, study_language: str = ""):
        self._connection = None
        scope = str(owner_scope or "").strip().lower()
        if scope not in ("guest", "account"):
            raise SentenceSkillStoreError("sentence skill owner is not guest or account")
        raw_root = str(data_root or "").strip()
        raw_path = str(db_path or "").strip()
        if not raw_root or not raw_path:
            raise SentenceSkillStoreError("sentence skill store needs an explicit directory")
        problem = refuse_sentence_skill_data_root(raw_root)
        if problem:
            raise SentenceSkillStoreError(problem)
        root = normalize_fs_path(raw_root)
        path = normalize_fs_path(raw_path)
        if not root or not path:
            raise SentenceSkillStoreError("sentence skill store needs an explicit directory")
        if os.path.basename(path).lower() in ("account_study.db", "practice_records.db"):
            raise SentenceSkillStoreError("sentence skill records use their own file")
        if not _resolved_under_root(path, root):
            raise SentenceSkillStoreError("sentence skill file is outside its data root")
        self.data_root = root
        self.db_path = path
        self.owner_scope = scope
        self.study_language = str(study_language or "").strip().lower()
        if scope == "guest":
            if not self.study_language or not is_supported_language(self.study_language):
                raise SentenceSkillStoreError("guest sentence skill store needs a supported study language")
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            self._connection = sqlite3.connect(path, check_same_thread=False)
            self._connection.row_factory = sqlite3.Row
            self._prepare()
        except SentenceSkillStoreError:
            self._close_quietly()
            raise
        except sqlite3.Error as error:
            self._close_quietly()
            raise SentenceSkillStoreError("sentence skill store was not opened") from error
        except OSError as error:
            self._close_quietly()
            raise SentenceSkillStoreError("sentence skill store was not opened") from error

    def close(self) -> None:
        self._close_quietly()

    def append(self, record: SentenceSkillRecord) -> SentenceSkillRecord:
        """Insert one skill event. Same submission_id returns the stored row (idempotent)."""
        try:
            validate_sentence_skill_record(record.as_dict())
        except SentenceSkillRecordError as error:
            raise SentenceSkillStoreError(str(error)) from error
        if self.owner_scope == "guest" and record.study_language != self.study_language:
            raise SentenceSkillStoreError("guest sentence skill language does not match this file")
        try:
            self._connection.execute("BEGIN IMMEDIATE")
        except sqlite3.Error as error:
            raise SentenceSkillStoreError("sentence skill record was not saved") from error
        try:
            existing = self._find_locked(record)
            if existing is not None:
                if _same_submission(existing, record):
                    self._connection.rollback()
                    return existing
                raise SentenceSkillStoreError("contradictory sentence skill replay rejected")
            self._connection.execute(
                f"""
                INSERT INTO sentence_skill_records ({", ".join(_COLUMNS)})
                VALUES ({", ".join("?" for _ in _COLUMNS)})
                """,
                _values(record, self.owner_scope),
            )
            self._connection.commit()
        except SentenceSkillStoreError:
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
            raise SentenceSkillStoreError("sentence skill record was not saved") from error
        return record

    def for_language(self, study_language: str) -> list[SentenceSkillRecord]:
        code = str(study_language or "").strip().lower()
        try:
            rows = self._connection.execute(
                """
                SELECT * FROM sentence_skill_records
                WHERE study_language = ?
                ORDER BY occurred_at, rowid
                """,
                (code,),
            ).fetchall()
        except sqlite3.Error as error:
            raise SentenceSkillStoreError("sentence skill records could not be read") from error
        found = []
        for row in rows:
            try:
                record = _from_row(row)
                validate_sentence_skill_record(record.as_dict())
                parse_utc(record.occurred_at)
            except (SentenceSkillRecordError, KeyError, TypeError, ValueError):
                continue
            found.append(record)
        # Stable UTC ordering even if ISO lexical order is ambiguous.
        found.sort(key=lambda item: (parse_utc(item.occurred_at), item.skill_event_id))
        return found

    def count(self) -> int:
        try:
            return int(self._connection.execute("SELECT COUNT(*) FROM sentence_skill_records").fetchone()[0])
        except sqlite3.Error as error:
            raise SentenceSkillStoreError("sentence skill records could not be read") from error

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
            raise SentenceSkillStoreError("sentence skill store was not opened") from error
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
                raise SentenceSkillStoreError("sentence skill store version is not supported")
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS sentence_skill_records (
                    skill_event_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    exercise_instance_id TEXT NOT NULL,
                    submission_id TEXT NOT NULL UNIQUE,
                    exercise_id TEXT NOT NULL,
                    family_id TEXT NOT NULL,
                    content_version TEXT NOT NULL,
                    format_version INTEGER NOT NULL,
                    study_language TEXT NOT NULL,
                    cefr_level TEXT NOT NULL,
                    exercise_kind TEXT NOT NULL,
                    support_level INTEGER NOT NULL,
                    outcome TEXT NOT NULL,
                    grading_source TEXT NOT NULL,
                    error_classification TEXT NOT NULL,
                    evidence_status TEXT NOT NULL,
                    grammar_skill_refs_json TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    selection_policy_id TEXT NOT NULL,
                    owner_scope TEXT NOT NULL
                )
                """
            )
            self._connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_sentence_skill_lang_time
                ON sentence_skill_records (study_language, occurred_at)
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
                (str(RECORD_FORMAT_VERSION),),
            )
            self._connection.commit()
        except SentenceSkillStoreError:
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
            raise SentenceSkillStoreError("sentence skill store was not opened") from error

    def _find_locked(self, record: SentenceSkillRecord) -> Optional[SentenceSkillRecord]:
        row = self._connection.execute(
            """
            SELECT * FROM sentence_skill_records
            WHERE submission_id = ? OR skill_event_id = ?
            """,
            (record.submission_id, record.skill_event_id),
        ).fetchone()
        if row is None:
            return None
        try:
            found = _from_row(row)
            validate_sentence_skill_record(found.as_dict())
        except (SentenceSkillRecordError, KeyError, TypeError, ValueError) as error:
            raise SentenceSkillStoreError("stored sentence skill row is invalid") from error
        return found


def open_guest_sentence_skill_store(data_root: str, study_language: str) -> SentenceSkillStore:
    code = str(study_language or "").strip().lower()
    if not str(data_root or "").strip():
        raise SentenceSkillStoreError("sentence skill store needs an explicit directory")
    root = normalize_fs_path(data_root)
    path = os.path.join(root, "languages", code, SENTENCE_SKILL_DB_FILE)
    return SentenceSkillStore(path, data_root=root, owner_scope="guest", study_language=code)


def open_account_sentence_skill_store(data_root: str, user_id: int) -> SentenceSkillStore:
    if not str(data_root or "").strip():
        raise SentenceSkillStoreError("sentence skill store needs an explicit directory")
    root = normalize_fs_path(data_root)
    path = os.path.join(root, "accounts", str(int(user_id)), SENTENCE_SKILL_DB_FILE)
    return SentenceSkillStore(path, data_root=root, owner_scope="account")


def _values(record: SentenceSkillRecord, owner_scope: str) -> tuple:
    return (
        record.skill_event_id,
        record.session_id,
        record.exercise_instance_id,
        record.submission_id,
        record.exercise_id,
        record.family_id,
        record.content_version,
        record.format_version,
        record.study_language,
        record.cefr_level,
        record.exercise_kind,
        record.support_level,
        record.outcome,
        record.grading_source,
        record.error_classification,
        record.evidence_status,
        json.dumps(list(record.grammar_skill_refs), ensure_ascii=True),
        record.occurred_at,
        record.selection_policy_id,
        owner_scope,
    )


def _from_row(row: sqlite3.Row) -> SentenceSkillRecord:
    refs_raw = row["grammar_skill_refs_json"]
    try:
        refs = tuple(json.loads(refs_raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        refs = ()
    return SentenceSkillRecord(
        skill_event_id=row["skill_event_id"],
        session_id=row["session_id"],
        exercise_instance_id=row["exercise_instance_id"],
        submission_id=row["submission_id"],
        exercise_id=row["exercise_id"],
        family_id=row["family_id"],
        content_version=row["content_version"],
        format_version=int(row["format_version"]),
        study_language=row["study_language"],
        cefr_level=row["cefr_level"],
        exercise_kind=row["exercise_kind"],
        support_level=int(row["support_level"]),
        outcome=row["outcome"],
        grading_source=row["grading_source"],
        error_classification=row["error_classification"],
        evidence_status=row["evidence_status"],
        grammar_skill_refs=tuple(str(item) for item in refs),
        occurred_at=row["occurred_at"],
        selection_policy_id=row["selection_policy_id"],
    )


def _same_submission(stored: SentenceSkillRecord, incoming: SentenceSkillRecord) -> bool:
    return (
        stored.submission_id == incoming.submission_id
        and stored.session_id == incoming.session_id
        and stored.exercise_instance_id == incoming.exercise_instance_id
        and stored.exercise_id == incoming.exercise_id
        and stored.family_id == incoming.family_id
        and stored.study_language == incoming.study_language
        and stored.outcome == incoming.outcome
        and stored.support_level == incoming.support_level
        and stored.error_classification == incoming.error_classification
        and stored.evidence_status == incoming.evidence_status
        and stored.grading_source == incoming.grading_source
    )


def load_sentence_skill_history(
    store: SentenceSkillStore,
    study_language: str,
) -> list[SentenceSkillRecord]:
    return store.for_language(study_language)
