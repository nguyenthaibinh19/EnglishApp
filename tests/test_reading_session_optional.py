"""Optional Reading StudySession wiring — per-language skip/unavailable (no AI)."""

from __future__ import annotations

import inspect

from daily_study import DailyStudyPlan
from main import StudyMasterApp
from reading_app import ReadingApp
from study_session import (
    KIND_LISTENING,
    KIND_READING,
    KIND_VOCABULARY,
    STATUS_SKIPPED,
    STATUS_UNAVAILABLE,
    build_study_session,
)


def _plan(code: str, *, reading=True, listening=False, planned=5) -> DailyStudyPlan:
    return DailyStudyPlan(
        language_code=code,
        vocab_total=10 if planned else 0,
        due_review_count=0,
        new_word_count=0,
        future_review_count=0,
        attention_word_count=0,
        planned_vocab_count=planned,
        reading_enabled=reading,
        listening_enabled=listening,
    )


def test_optional_reading_close_invokes_skip_callback():
    close_src = inspect.getsource(ReadingApp._on_close_attempt)
    assert "on_skip" in close_src
    assert "not self.required" in close_src
    open_src = inspect.getsource(StudyMasterApp.open_reading_section)
    assert "on_skip=self._skip_reading" in open_src
    # Optional Reading must not gate skip on global vocab-all-done.
    assert "on_skip=self._skip_reading if" not in open_src


def test_dutch_reading_skip_does_not_skip_german():
    nl = build_study_session(_plan("nl", reading=True))
    de = build_study_session(_plan("de", reading=True))
    nl.complete(KIND_VOCABULARY)
    de.complete(KIND_VOCABULARY)
    nl.skip(KIND_READING)
    assert nl.status(KIND_READING) == STATUS_SKIPPED
    assert nl.is_resolved(KIND_READING)
    assert not de.is_resolved(KIND_READING)
    assert de.status(KIND_READING) != STATUS_SKIPPED


def test_current_language_reading_unavailable_does_not_mutate_other():
    nl = build_study_session(_plan("nl", reading=True))
    de = build_study_session(_plan("de", reading=True))
    nl.complete(KIND_VOCABULARY)
    de.complete(KIND_VOCABULARY)
    nl.mark_unavailable(KIND_READING)
    assert nl.status(KIND_READING) == STATUS_UNAVAILABLE
    assert de.status(KIND_READING) != STATUS_UNAVAILABLE
    assert not de.is_resolved(KIND_READING)


def test_session_finishes_after_vocab_and_current_reading_skipped():
    session = build_study_session(_plan("nl", reading=True, listening=False))
    session.complete(KIND_VOCABULARY)
    assert session.can_finish is False
    session.skip(KIND_READING)
    assert session.can_finish is True


def test_skip_reading_is_per_language_in_studymaster():
    src = inspect.getsource(StudyMasterApp._skip_reading)
    assert "for code in config.study_codes()" not in src
    assert "active_code" in src
    assert "session.skip(KIND_READING)" in src
    # No legacy skip-all helper.
    assert not hasattr(StudyMasterApp, "_finish_without_reading")


def test_mark_reading_unavailable_is_per_language_in_studymaster():
    src = inspect.getsource(StudyMasterApp._mark_reading_unavailable)
    assert "for code in config.study_codes()" not in src
    assert "active_code" in src
    assert "mark_unavailable(KIND_READING)" in src


def test_listening_per_language_skip_unchanged():
    nl = build_study_session(_plan("nl", reading=False, listening=True, planned=0))
    de = build_study_session(_plan("de", reading=False, listening=True, planned=0))
    nl.skip(KIND_LISTENING)
    assert nl.is_resolved(KIND_LISTENING)
    assert not de.is_resolved(KIND_LISTENING)
    src = inspect.getsource(StudyMasterApp._skip_listening)
    assert "for code in config.study_codes()" not in src
    assert "active_code" in src
