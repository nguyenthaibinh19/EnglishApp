"""Phase 17A — Listening foundation (no real audio / network)."""

from __future__ import annotations

from daily_study import DailyStudyPlan, build_daily_study_plan
from listening import (
    FakeListeningAudioProvider,
    ListeningAudioError,
    ListeningItem,
    ListeningSession,
    NullListeningAudioProvider,
    check_listening_answer,
    resolve_listening_audio_provider,
    sample_listening_items,
)
from study_session import (
    KIND_LISTENING,
    KIND_READING,
    KIND_VOCABULARY,
    STATUS_UNAVAILABLE,
    build_study_session,
)


def _item() -> ListeningItem:
    return ListeningItem(
        text="Ik woon in een klein huis.",
        question="Where?",
        answer="in a small house",
        alternatives=("in een klein huis",),
        meaning="I live in a small house.",
    )


def _plan(*, planned=5, reading=False, listening=False, vocab_total=10) -> DailyStudyPlan:
    return DailyStudyPlan(
        language_code="nl",
        vocab_total=vocab_total,
        due_review_count=0,
        new_word_count=0,
        future_review_count=0,
        attention_word_count=0,
        planned_vocab_count=planned,
        reading_enabled=reading,
        listening_enabled=listening,
    )


def test_listening_item_model():
    item = _item()
    assert item.text
    assert item.question
    assert item.answer
    assert "in een klein huis" in item.alternatives


def test_normalized_correct_and_incorrect_answers():
    item = _item()
    ok = check_listening_answer("In a small house", item)
    assert ok.correct is True
    assert ok.verdict in ("exact", "near")
    bad = check_listening_answer("in the car", item)
    assert bad.correct is False
    assert bad.verdict == "wrong"


def test_domain_completion_and_play_language():
    fake = FakeListeningAudioProvider()
    session = ListeningSession.create("nl", item=_item(), audio_provider=fake)
    assert session.unavailable is False
    session.play()
    assert fake.calls == [("Ik woon in een klein huis.", "nl")]
    assert session.played is True
    result = session.submit("in a small house")
    assert result.correct is True
    session.finish()
    assert session.completed is True


def test_fake_provider_and_null_unavailable():
    assert resolve_listening_audio_provider() is None
    null = NullListeningAudioProvider()
    assert null.is_available() is False
    session = ListeningSession.create("en", audio_provider=null)
    assert session.unavailable is True
    try:
        session.play()
        assert False
    except ListeningAudioError:
        pass


def test_audio_failure_marks_unavailable():
    fake = FakeListeningAudioProvider(fail=True)
    session = ListeningSession.create("de", item=_item(), audio_provider=fake)
    try:
        session.play()
        assert False
    except ListeningAudioError:
        pass
    assert session.unavailable is True


def test_sample_items_language_aware_not_dutch_only():
    assert sample_listening_items("fr")[0].text
    assert sample_listening_items("pt")[0].text
    assert sample_listening_items("zz") == ()


def test_listening_disabled_no_activity():
    session = build_study_session(_plan(listening=False, reading=True))
    assert not session.has_activity(KIND_LISTENING)
    assert [a.kind for a in session.activities()] == [KIND_VOCABULARY, KIND_READING]


def test_listening_enabled_optional_order():
    session = build_study_session(_plan(listening=True, reading=True))
    assert [a.kind for a in session.activities()] == [
        KIND_VOCABULARY,
        KIND_READING,
        KIND_LISTENING,
    ]
    assert session._by_kind[KIND_LISTENING].required is False


def test_listening_complete_skip_unavailable_resolve_session():
    session = build_study_session(_plan(listening=True, reading=False))
    session.complete(KIND_VOCABULARY)
    assert session.can_finish is False
    session.complete(KIND_LISTENING)
    assert session.can_finish is True

    session = build_study_session(_plan(listening=True, reading=False))
    session.complete(KIND_VOCABULARY)
    session.skip(KIND_LISTENING)
    assert session.can_finish is True

    session = build_study_session(_plan(listening=True, reading=False))
    session.complete(KIND_VOCABULARY)
    session.mark_unavailable(KIND_LISTENING)
    assert session.status(KIND_LISTENING) == STATUS_UNAVAILABLE
    assert session.can_finish is True


def test_vocabulary_still_required_with_listening():
    session = build_study_session(_plan(listening=True))
    session.skip(KIND_LISTENING)
    assert session.can_finish is False
    session.complete(KIND_VOCABULARY)
    assert session.can_finish is True


def test_empty_vocab_listening_only():
    session = build_study_session(
        _plan(planned=0, vocab_total=0, reading=False, listening=True)
    )
    assert not session.has_activity(KIND_VOCABULARY)
    assert session.has_activity(KIND_LISTENING)
    assert session.required_complete is True
    session.mark_unavailable(KIND_LISTENING)
    assert session.can_finish is True


def test_daily_study_listening_flag():
    on = build_daily_study_plan(
        "nl", [], {}, [], quiz_target=5, reading_enabled=False, listening_enabled=True
    )
    off = build_daily_study_plan(
        "nl", [], {}, [], quiz_target=5, reading_enabled=True, listening_enabled=False
    )
    assert on.listening_enabled is True
    assert off.listening_enabled is False
    assert build_study_session(on).has_activity(KIND_LISTENING)
    assert not build_study_session(off).has_activity(KIND_LISTENING)


def test_no_progress_srs_mutation_on_listening_check():
    # Pure domain path — no Progress/Attempt files involved.
    item = _item()
    before = (item.text, item.answer)
    check_listening_answer("wrong", item)
    assert (item.text, item.answer) == before
