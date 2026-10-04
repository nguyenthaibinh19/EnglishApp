"""Phase 16 — Progress dashboard view-model (no Tkinter)."""

from __future__ import annotations

from learning_progress import DayActivity, LearningProgressSnapshot, RecentAttemptItem
from progress_viewmodel import build_progress_view_model


def _snap(**kwargs) -> LearningProgressSnapshot:
    base = dict(
        language_code="nl",
        vocab_total=10,
        practiced_word_count=6,
        new_word_count=4,
        due_review_count=3,
        future_review_count=3,
        attention_word_count=2,
        total_attempt_count=20,
        mastery_attempt_count=12,
        non_mastery_attempt_count=8,
        mastery_attempt_rate=0.6,
        recent_days=(
            DayActivity(date="2026-09-30", attempt_count=2, mastery_attempt_count=1),
            DayActivity(date="2026-10-01", attempt_count=4, mastery_attempt_count=3),
        ),
        recent_attempts=(
            RecentAttemptItem(
                word="huis",
                timestamp="2026-10-01T12:00:00+00:00",
                correct=True,
                hint_used=False,
                verdict="exact",
            ),
        ),
    )
    base.update(kwargs)
    return LearningProgressSnapshot(**base)


def test_normal_overview_and_activity_labels():
    vm = build_progress_view_model(_snap(), "Dutch", study_language_count=2)
    assert "10" in vm.total_label
    assert "6" in vm.practiced_label
    assert "4" in vm.new_label
    assert "3" in vm.due_label
    assert "3" in vm.future_label
    assert "2" in vm.attention_label
    assert "20" in vm.attempts_label
    assert "12" in vm.mastery_answers_label
    assert "60%" in vm.mastery_rate_label or "60" in vm.mastery_rate_label
    assert vm.empty_vocab is False
    assert vm.no_attempts is False
    assert vm.can_change_language is True
    assert len(vm.recent_days) == 2
    assert vm.recent_days[1].bar_ratio == 1.0
    assert len(vm.recent_attempts) == 1


def test_empty_vocab_wording():
    vm = build_progress_view_model(
        _snap(
            vocab_total=0,
            practiced_word_count=0,
            new_word_count=0,
            due_review_count=0,
            future_review_count=0,
            attention_word_count=0,
            total_attempt_count=0,
            mastery_attempt_count=0,
            non_mastery_attempt_count=0,
            mastery_attempt_rate=None,
            recent_days=(),
            recent_attempts=(),
        ),
        "Dutch",
    )
    assert vm.empty_vocab is True
    assert vm.overview_hint
    low = vm.due_label.lower()
    assert "nothing" in low or "chưa" in low or "không" in low


def test_unpracticed_vocab_no_failure_rate():
    vm = build_progress_view_model(
        _snap(
            vocab_total=5,
            practiced_word_count=0,
            new_word_count=5,
            due_review_count=0,
            future_review_count=0,
            attention_word_count=0,
            total_attempt_count=0,
            mastery_attempt_count=0,
            non_mastery_attempt_count=0,
            mastery_attempt_rate=None,
            recent_days=(),
            recent_attempts=(),
        ),
        "Dutch",
    )
    assert vm.never_practiced is True
    assert vm.no_attempts is True
    assert "0%" not in vm.mastery_rate_label
    assert vm.activity_hint
    low = vm.mastery_rate_label.lower()
    assert "no" in low or "chưa" in low


def test_nothing_due_and_no_attention_wording():
    vm = build_progress_view_model(
        _snap(due_review_count=0, attention_word_count=0),
        "Dutch",
    )
    assert vm.nothing_due is True
    assert vm.no_attention is True
    assert "0 due" not in vm.due_label.lower()
    due_low = vm.due_label.lower()
    assert "nothing" in due_low or "không" in due_low
    att_low = vm.attention_label.lower()
    assert "no" in att_low or "không" in att_low


def test_mastery_quality_label_not_words_mastered():
    vm = build_progress_view_model(_snap(), "Dutch")
    joined = f"{vm.mastery_answers_label} {vm.mastery_rate_label}".lower()
    assert "mastery-quality" in joined or "chuẩn thuộc" in joined
    assert "words mastered" not in joined
    assert "từ đã thuộc" not in joined
