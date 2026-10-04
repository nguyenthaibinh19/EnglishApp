"""Study Session Runner v1 — domain orchestration."""

from __future__ import annotations

from daily_study import DailyStudyPlan
from study_session import (
    KIND_LISTENING,
    KIND_READING,
    KIND_VOCABULARY,
    STATUS_ACTIVE,
    STATUS_COMPLETED,
    STATUS_PENDING,
    STATUS_SKIPPED,
    STATUS_UNAVAILABLE,
    StudySessionError,
    build_study_session,
)


def _plan(
    *,
    code="nl",
    vocab_total=10,
    planned=5,
    reading=True,
    listening=False,
    due=0,
    new=0,
    future=0,
    attention=0,
) -> DailyStudyPlan:
    return DailyStudyPlan(
        language_code=code,
        vocab_total=vocab_total,
        due_review_count=due,
        new_word_count=new,
        future_review_count=future,
        attention_word_count=attention,
        planned_vocab_count=planned,
        reading_enabled=reading,
        listening_enabled=listening,
    )


def test_vocabulary_only_session():
    session = build_study_session(_plan(reading=False))
    kinds = [a.kind for a in session.activities()]
    assert kinds == [KIND_VOCABULARY]
    assert session.can_finish is False
    session.start(KIND_VOCABULARY)
    session.complete(KIND_VOCABULARY)
    assert session.can_finish is True
    assert session.next_activity() is None


def test_vocabulary_plus_reading_order():
    session = build_study_session(_plan(reading=True))
    kinds = [a.kind for a in session.activities()]
    assert kinds == [KIND_VOCABULARY, KIND_READING]
    assert session.next_activity().kind == KIND_VOCABULARY
    session.complete(KIND_VOCABULARY)
    assert session.next_activity().kind == KIND_READING


def test_vocabulary_reading_listening_order():
    session = build_study_session(_plan(reading=True, listening=True))
    assert [a.kind for a in session.activities()] == [
        KIND_VOCABULARY,
        KIND_READING,
        KIND_LISTENING,
    ]
    session.complete(KIND_VOCABULARY)
    session.complete(KIND_READING)
    assert session.next_activity().kind == KIND_LISTENING


def test_reading_disabled_plan():
    session = build_study_session(_plan(reading=False))
    assert not session.has_activity(KIND_READING)
    session.complete(KIND_VOCABULARY)
    assert session.can_finish is True


def test_vocabulary_required_cannot_be_skipped():
    session = build_study_session(_plan(reading=True))
    try:
        session.skip(KIND_VOCABULARY)
        assert False, "expected StudySessionError"
    except StudySessionError:
        pass
    assert session.status(KIND_VOCABULARY) == STATUS_PENDING


def test_optional_reading_can_be_skipped():
    session = build_study_session(_plan(reading=True))
    session.complete(KIND_VOCABULARY)
    session.skip(KIND_READING)
    assert session.status(KIND_READING) == STATUS_SKIPPED
    assert session.can_finish is True


def test_reading_unavailable_does_not_block_finish():
    session = build_study_session(_plan(reading=True))
    session.complete(KIND_VOCABULARY)
    session.mark_unavailable(KIND_READING)
    assert session.status(KIND_READING) == STATUS_UNAVAILABLE
    assert session.can_finish is True


def test_cannot_finish_before_required_vocab():
    session = build_study_session(_plan(reading=True))
    session.skip(KIND_READING)
    assert session.required_complete is False
    assert session.can_finish is False
    session.complete(KIND_VOCABULARY)
    assert session.can_finish is True


def test_zero_vocab_plan_finishable_with_reading():
    session = build_study_session(_plan(vocab_total=0, planned=0, reading=True))
    assert not session.has_activity(KIND_VOCABULARY)
    assert session.has_activity(KIND_READING)
    assert session.required_complete is True
    assert session.can_finish is False
    session.skip(KIND_READING)
    assert session.can_finish is True


def test_zero_vocab_no_reading_immediately_finishable():
    session = build_study_session(_plan(vocab_total=0, planned=0, reading=False))
    assert session.activities() == ()
    assert session.can_finish is True
    assert session.next_activity() is None


def test_ordering_deterministic():
    session = build_study_session(_plan(reading=True, planned=3))
    assert [a.kind for a in session.activities()] == [KIND_VOCABULARY, KIND_READING]


def test_illegal_complete_from_unavailable_rejected():
    session = build_study_session(_plan(reading=True))
    session.complete(KIND_VOCABULARY)
    session.mark_unavailable(KIND_READING)
    try:
        session.start(KIND_READING)
        assert False
    except StudySessionError:
        pass


def test_duplicate_complete_idempotent():
    session = build_study_session(_plan(reading=False))
    session.complete(KIND_VOCABULARY)
    session.complete(KIND_VOCABULARY)
    assert session.status(KIND_VOCABULARY) == STATUS_COMPLETED


def test_planned_vocab_count_carried():
    session = build_study_session(_plan(planned=3))
    assert session.planned_vocab_count == 3


def test_start_active_complete_flow():
    session = build_study_session(_plan(reading=True))
    session.start(KIND_VOCABULARY)
    assert session.status(KIND_VOCABULARY) == STATUS_ACTIVE
    session.complete(KIND_VOCABULARY)
    session.start(KIND_READING)
    session.complete(KIND_READING)
    assert session.can_finish is True


def test_set_optional_enabled_preserves_vocab():
    session = build_study_session(_plan(reading=False, planned=5))
    session.complete(KIND_VOCABULARY)
    session.set_optional_enabled(KIND_READING, True)
    assert session.vocabulary_complete() is True
    assert session.has_activity(KIND_READING)
    assert session.status(KIND_READING) == STATUS_PENDING
    session.set_optional_enabled(KIND_READING, False)
    assert not session.has_activity(KIND_READING)
    assert session.can_finish is True


def test_build_does_not_need_network_or_writes():
    # Pure construction from in-memory plan.
    plan = _plan(planned=2, reading=True)
    session = build_study_session(plan)
    assert session.language_code == "nl"
    assert session.plan is plan
