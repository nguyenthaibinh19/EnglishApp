"""Practice records use a real SQLite file. Nothing here touches production AppData."""

from __future__ import annotations

import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from adaptive_vocabulary import (
    GUIDED_TYPING,
    INDEPENDENT_RECALL,
    INTRODUCTION,
    MISSING_LETTERS,
    AdaptiveVocabularySession,
    starting_level,
)
from app_environment import RC_DATA_FOLDER, RECOVERY_FOLDER, production_data_dir
from attempt_history import LearningAttempt
from practice_record import (
    ERROR_INCORRECT,
    ERROR_NEAR_MATCH,
    FORMAT_VERSION,
    PracticeRecord,
    PracticeRecordError,
    build_practice_record,
    practice_start_level,
    usable_practice,
    validate_practice_record,
)
from practice_store import (
    PracticeStoreError,
    open_account_store,
    open_guest_store,
    refuse_practice_data_root,
)
from progress import Progress

FIETS = "11111111-1111-4111-8111-111111111111"
NOW = datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)


def word():
    return {"id": FIETS, "word": "de fiets", "meaning": "bicycle", "example": "Ik ga met de fiets."}


def attempt(*, correct, verdict, hint=False, when="2026-11-27T12:00:00+00:00"):
    return LearningAttempt(
        timestamp=when,
        language_code="nl",
        word="de fiets",
        user_answer="de fiets" if correct else "nope",
        expected_answer="de fiets",
        correct=correct,
        verdict=verdict,
        hint_used=hint,
        prompt="bicycle",
        vocab_id=FIETS,
    )


def record(
    kind,
    outcome,
    *,
    when="2026-11-27T12:00:00+00:00",
    language="nl",
    version=FORMAT_VERSION,
    session_id=None,
    exercise_instance_id=None,
    intended=None,
):
    built = build_practice_record(
        practice_event_id=uuid.uuid4().hex,
        exercise_instance_id=exercise_instance_id or uuid.uuid4().hex,
        session_id=session_id or uuid.uuid4().hex,
        vocab_id=FIETS,
        language_code=language,
        actual_kind=kind,
        intended_kind=intended or kind,
        support_level="recognition" if kind in (INTRODUCTION, "multiple_choice") else "assisted",
        outcome=outcome,
        occurred_at=when,
    )
    if version == FORMAT_VERSION:
        return built
    return PracticeRecord(**{**built.__dict__, "format_version": version})


def test_store_is_append_only_idempotent_and_reopens(tmp_path):
    store = open_guest_store(str(tmp_path), "nl")
    first = record("multiple_choice", "exact")
    stored = store.append(first)
    again = PracticeRecord(
        practice_event_id=uuid.uuid4().hex,
        exercise_instance_id=first.exercise_instance_id,
        session_id=first.session_id,
        vocab_id=first.vocab_id,
        language_code=first.language_code,
        actual_kind=first.actual_kind,
        intended_kind=first.intended_kind,
        support_level=first.support_level,
        outcome=first.outcome,
        error_class=first.error_class,
        occurred_at=first.occurred_at,
        policy_id=first.policy_id,
        format_version=first.format_version,
    )
    replay = store.append(again)
    assert replay.practice_event_id == stored.practice_event_id
    assert store.count() == 1
    conflict = PracticeRecord(
        practice_event_id=uuid.uuid4().hex,
        exercise_instance_id=first.exercise_instance_id,
        session_id=first.session_id,
        vocab_id=first.vocab_id,
        language_code=first.language_code,
        actual_kind=first.actual_kind,
        intended_kind=first.intended_kind,
        support_level=first.support_level,
        outcome="wrong",
        error_class=ERROR_INCORRECT,
        occurred_at=first.occurred_at,
        policy_id=first.policy_id,
        format_version=first.format_version,
    )
    with pytest.raises(PracticeStoreError):
        store.append(conflict)
    other_session = PracticeRecord(**{**again.__dict__, "session_id": uuid.uuid4().hex})
    with pytest.raises(PracticeStoreError):
        store.append(other_session)
    other_intended = PracticeRecord(**{**again.__dict__, "intended_kind": GUIDED_TYPING})
    with pytest.raises(PracticeStoreError):
        store.append(other_intended)
    assert store.count() == 1
    path = store.db_path
    store.close()
    reopened = open_guest_store(str(tmp_path), "nl")
    try:
        rows = reopened.for_vocab(FIETS, "nl")
        assert len(rows) == 1
        assert rows[0].practice_event_id == first.practice_event_id
        columns = {
            item[1]
            for item in reopened._connection.execute("PRAGMA table_info(practice_records)")
        }
        assert "user_answer" not in columns
        assert not list(Path(tmp_path).rglob("account_study.db"))
    finally:
        reopened.close()
    assert Path(path).is_file()


def test_account_guest_and_language_files_stay_separate(tmp_path):
    dutch = open_guest_store(str(tmp_path), "nl")
    english = open_guest_store(str(tmp_path), "en")
    first_account = open_account_store(str(tmp_path), 7)
    second_account = open_account_store(str(tmp_path), 8)
    try:
        dutch.append(record("introduction", "acknowledged"))
        with pytest.raises(PracticeStoreError):
            dutch.append(record("introduction", "acknowledged", language="en"))
        english.append(record("multiple_choice", "exact", language="en"))
        first_account.append(record("guided_typing", "near"))
        assert dutch.for_vocab(FIETS, "en") == []
        assert len(english.for_vocab(FIETS, "en")) == 1
        assert first_account.for_vocab(FIETS, "nl")[0].error_class == ERROR_NEAR_MATCH
        assert second_account.for_vocab(FIETS, "nl") == []
        assert dutch.db_path != first_account.db_path
        assert "account_study.db" not in dutch.db_path
    finally:
        dutch.close()
        english.close()
        first_account.close()
        second_account.close()


def test_production_rc_recovery_and_old_schema_are_refused(tmp_path, monkeypatch):
    root = production_data_dir()
    assert refuse_practice_data_root(root)
    with pytest.raises(PracticeStoreError):
        open_guest_store(root, "nl")
    with pytest.raises(PracticeStoreError):
        open_guest_store("", "nl")
    with pytest.raises(PracticeStoreError):
        open_guest_store("   ", "nl")
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    rc = tmp_path / "roaming" / RC_DATA_FOLDER
    recovery = tmp_path / "local" / RECOVERY_FOLDER
    rc.mkdir(parents=True)
    recovery.mkdir(parents=True)
    assert refuse_practice_data_root(str(rc))
    assert refuse_practice_data_root(str(recovery))
    with pytest.raises(PracticeStoreError):
        open_guest_store(str(rc), "nl")
    with pytest.raises(PracticeStoreError):
        open_guest_store(str(recovery), "nl")
    store = open_guest_store(str(tmp_path / "safe"), "nl")
    path = store.db_path
    store.close()
    connection = sqlite3.connect(path)
    connection.execute("UPDATE meta SET value = '2' WHERE key = 'schema_version'")
    connection.commit()
    connection.close()
    with pytest.raises(PracticeStoreError):
        open_guest_store(str(tmp_path / "safe"), "nl")


def test_invalid_stored_rows_are_skipped_without_changing_history(tmp_path):
    store = open_guest_store(str(tmp_path), "nl")
    good = record("multiple_choice", "exact")
    store.append(good)
    store._connection.execute(
        """
        INSERT INTO practice_records (
            practice_event_id, exercise_instance_id, session_id, vocab_id, language_code,
            actual_kind, intended_kind, support_level, outcome, error_class, occurred_at,
            policy_id, format_version, owner_scope
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            uuid.uuid4().hex,
            uuid.uuid4().hex,
            uuid.uuid4().hex,
            FIETS,
            "nl",
            "multiple_choice",
            "multiple_choice",
            "assisted",
            "exact",
            "",
            "2026-11-27T12:05:00+00:00",
            "adaptive-vocab-session-v1",
            1,
            "guest",
        ),
    )
    store._connection.commit()
    rows = store.for_vocab(FIETS, "nl")
    assert [item.practice_event_id for item in rows] == [good.practice_event_id]
    assert store.count() == 2
    store.close()


def test_contract_rejects_mismatched_support_language_and_identity():
    with pytest.raises(PracticeRecordError):
        build_practice_record(
            practice_event_id=uuid.uuid4().hex,
            exercise_instance_id=uuid.uuid4().hex,
            session_id=uuid.uuid4().hex,
            vocab_id=FIETS,
            language_code="nl",
            actual_kind="multiple_choice",
            intended_kind="multiple_choice",
            support_level="assisted",
            outcome="exact",
            occurred_at="2026-11-27T12:00:00+00:00",
        )
    with pytest.raises(PracticeRecordError):
        build_practice_record(
            practice_event_id=uuid.uuid4().hex,
            exercise_instance_id=uuid.uuid4().hex,
            session_id=uuid.uuid4().hex,
            vocab_id=FIETS,
            language_code="xx",
            actual_kind="introduction",
            intended_kind="introduction",
            support_level="recognition",
            outcome="acknowledged",
            occurred_at="2026-11-27T12:00:00+00:00",
        )
    with pytest.raises(PracticeRecordError):
        build_practice_record(
            practice_event_id=uuid.uuid4().hex,
            exercise_instance_id=uuid.uuid4().hex,
            session_id=uuid.uuid4().hex,
            vocab_id="not-a-uuid",
            language_code="nl",
            actual_kind="introduction",
            intended_kind="introduction",
            support_level="recognition",
            outcome="acknowledged",
            occurred_at="2026-11-27T12:00:00+00:00",
        )
    near = record(GUIDED_TYPING, "near")
    wrong = record(GUIDED_TYPING, "wrong")
    assert near.error_class == ERROR_NEAR_MATCH
    assert wrong.error_class == ERROR_INCORRECT
    with pytest.raises(PracticeRecordError):
        validate_practice_record(PracticeRecord(**{**wrong.__dict__, "error_class": "vocabulary"}))


def test_older_practice_cannot_override_newer_independent_evidence():
    older_failures = [
        record(GUIDED_TYPING, "wrong", when="2026-11-27T11:00:00+00:00"),
        record(GUIDED_TYPING, "wrong", when="2026-11-27T11:01:00+00:00"),
    ]
    newer_attempt = attempt(correct=False, verdict="wrong", when="2026-11-27T12:00:00+00:00")
    assert starting_level(None, newer_attempt, now=NOW, practice=older_failures) == GUIDED_TYPING
    equal_time = [
        record(GUIDED_TYPING, "wrong", when="2026-11-27T12:00:00+00:00"),
        record(GUIDED_TYPING, "wrong", when="2026-11-27T12:00:00+00:00"),
    ]
    assert starting_level(None, newer_attempt, now=NOW, practice=equal_time) == GUIDED_TYPING
    newer_failures = [
        record(GUIDED_TYPING, "wrong", when="2026-11-27T12:01:00+00:00"),
        record(GUIDED_TYPING, "wrong", when="2026-11-27T12:02:00+00:00"),
    ]
    assert starting_level(None, newer_attempt, now=NOW, practice=newer_failures) == MISSING_LETTERS
    first = record("multiple_choice", "exact", when="2026-11-27T12:00:00+00:00")
    second = record(MISSING_LETTERS, "exact", when="2026-11-27T12:00:00+00:00")
    same_stamp = usable_practice([first, second], now=NOW)
    assert [item.practice_event_id for item in same_stamp] == [
        first.practice_event_id,
        second.practice_event_id,
    ]
    assert practice_start_level(
        INTRODUCTION,
        [first, second],
        allow_promote=True,
        now=NOW,
    ) == GUIDED_TYPING


def test_recent_practice_changes_the_start_and_ignores_stale_rows():
    fresh = [
        record("introduction", "acknowledged", when="2026-11-27T12:00:00+00:00"),
        record("multiple_choice", "exact", when="2026-11-27T12:01:00+00:00"),
        record(MISSING_LETTERS, "exact", when="2026-11-27T12:02:00+00:00"),
    ]
    assert starting_level(None, None, now=NOW, practice=fresh) == GUIDED_TYPING
    stale = record(MISSING_LETTERS, "exact", when="2026-10-01T00:00:00+00:00")
    unsupported = record("multiple_choice", "exact", version=99)
    assert usable_practice([stale, unsupported], now=NOW) == []
    assert starting_level(None, None, now=NOW, practice=[stale, unsupported]) == INTRODUCTION
    mastered = attempt(correct=True, verdict="exact")
    assert starting_level(None, mastered, now=NOW, practice=fresh) == INDEPENDENT_RECALL
    missed = attempt(correct=False, verdict="wrong", when="2026-11-27T11:00:00+00:00")
    assert starting_level(None, missed, now=NOW, practice=fresh) == GUIDED_TYPING
    failures = [
        record(GUIDED_TYPING, "wrong", when="2026-11-27T12:03:00+00:00"),
        record(GUIDED_TYPING, "wrong", when="2026-11-27T12:04:00+00:00"),
    ]
    assert practice_start_level(GUIDED_TYPING, failures, allow_promote=False, now=NOW) == MISSING_LETTERS
    session = AdaptiveVocabularySession(
        [word()],
        language_code="nl",
        rng=__import__("random").Random(4),
        attempts=[missed],
        practice_history=failures,
        now=NOW,
    )
    assert session.current_card().kind == MISSING_LETTERS
    assert session.current_card().kind != INDEPENDENT_RECALL


def test_practice_submission_does_not_write_progress(tmp_path):
    progress = Progress(str(tmp_path / "progress.json"))
    store = open_guest_store(str(tmp_path), "nl")
    session = AdaptiveVocabularySession([word()], language_code="nl", rng=__import__("random").Random(4))
    try:
        intro = session.continue_card()
        assert intro.practice.outcome == "acknowledged"
        assert intro.write is None
        store.append(intro.practice)
        card = session.current_card()
        from adaptive_vocabulary import reconstruct_mask

        if card.kind == "multiple_choice":
            choice = session.submit(choice_index=card.correct_index)
        elif card.kind == "missing_letters":
            fills = [card.reveal_word[index] for index, char in enumerate(card.mask) if char == "_"]
            choice = session.submit(reconstruct_mask(card.mask, fills))
        else:
            choice = session.submit(card.reveal_word)
        assert choice.practice is not None
        assert choice.practice.outcome == "exact"
        assert choice.write is None
        store.append(choice.practice)
        assert progress.data["words"] == {}
        assert not list(Path(tmp_path).rglob("account_study.db"))
    finally:
        store.close()
