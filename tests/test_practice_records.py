"""Practice records use a real SQLite file. Nothing here touches production AppData."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
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
from app_environment import production_data_dir, validate_data_root_for_identity
from attempt_history import LearningAttempt
from practice_record import (
    FORMAT_VERSION,
    PracticeRecord,
    build_practice_record,
    practice_start_level,
    usable_practice,
)
from practice_store import PracticeStoreError, open_account_store, open_guest_store
from progress import Progress

FIETS = "11111111-1111-4111-8111-111111111111"
NOW = datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)


def word():
    return {"id": FIETS, "word": "de fiets", "meaning": "bicycle", "example": "Ik ga met de fiets."}


def attempt(*, correct, verdict, hint=False):
    return LearningAttempt(
        timestamp="2026-11-27T12:00:00+00:00",
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


def record(kind, outcome, *, when="2026-11-27T12:00:00+00:00", language="nl", version=FORMAT_VERSION):
    built = build_practice_record(
        practice_event_id=uuid.uuid4().hex,
        exercise_instance_id=uuid.uuid4().hex,
        session_id=uuid.uuid4().hex,
        vocab_id=FIETS,
        language_code=language,
        actual_kind=kind,
        intended_kind=kind,
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
        error_class="vocabulary",
        occurred_at=first.occurred_at,
        policy_id=first.policy_id,
        format_version=first.format_version,
    )
    with pytest.raises(PracticeStoreError):
        store.append(conflict)
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
        assert first_account.for_vocab(FIETS, "nl")[0].error_class == "spelling"
        assert second_account.for_vocab(FIETS, "nl") == []
        assert dutch.db_path != first_account.db_path
        assert "account_study.db" not in dutch.db_path
    finally:
        dutch.close()
        english.close()
        first_account.close()
        second_account.close()


def test_production_appdata_and_old_schema_are_refused(tmp_path):
    root = production_data_dir()
    assert validate_data_root_for_identity(root)
    with pytest.raises(PracticeStoreError):
        open_guest_store(root, "nl")
    store = open_guest_store(str(tmp_path), "nl")
    path = store.db_path
    store.close()
    connection = sqlite3.connect(path)
    connection.execute("UPDATE meta SET value = '2' WHERE key = 'schema_version'")
    connection.commit()
    connection.close()
    with pytest.raises(PracticeStoreError):
        open_guest_store(str(tmp_path), "nl")


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
    missed = attempt(correct=False, verdict="wrong")
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
