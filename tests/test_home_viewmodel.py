"""Home dashboard view-model — presentation only."""

from __future__ import annotations

from daily_study import DailyStudyPlan
from home_viewmodel import build_home_view_model, greeting_for_local_hour


def _plan(**kwargs) -> DailyStudyPlan:
    base = dict(
        language_code="nl",
        vocab_total=10,
        due_review_count=8,
        new_word_count=5,
        future_review_count=0,
        attention_word_count=3,
        planned_vocab_count=5,
        reading_enabled=True,
        listening_enabled=False,
    )
    base.update(kwargs)
    return DailyStudyPlan(**base)


def test_greeting_hours():
    assert "morning" in greeting_for_local_hour(8).lower() or "sáng" in greeting_for_local_hour(8).lower()
    assert "afternoon" in greeting_for_local_hour(14).lower() or "chiều" in greeting_for_local_hour(14).lower()
    assert "evening" in greeting_for_local_hour(20).lower() or "tối" in greeting_for_local_hour(20).lower()


def test_normal_metrics():
    vm = build_home_view_model(_plan(), "Dutch", study_language_count=1, hour=10)
    assert "8" in vm.due_label
    assert "5" in vm.new_label
    assert "3" in vm.attention_label
    assert "5" in vm.vocab_plan_label
    assert vm.due_is_zero is False
    assert vm.empty_vocab is False
    assert "Enabled" in vm.reading_label or "bật" in vm.reading_label.lower()
    assert "Disabled" in vm.listening_label or "tắt" in vm.listening_label.lower()
    assert vm.can_change_language is False


def test_zero_due_wording_not_false_due():
    vm = build_home_view_model(
        _plan(due_review_count=0, planned_vocab_count=5),
        "Dutch",
        hour=10,
    )
    assert vm.due_is_zero is True
    assert "5 reviews due" not in vm.due_label.lower()
    assert "5 từ đến hạn" not in vm.due_label.lower()
    low = vm.due_label.lower()
    assert "nothing" in low or "không" in low or "no " in low
    assert "5" in vm.vocab_plan_label


def test_zero_attention():
    vm = build_home_view_model(_plan(attention_word_count=0), "Dutch", hour=10)
    assert vm.attention_is_zero is True
    assert "0" not in vm.attention_label or "attention" in vm.attention_label.lower() or "chú ý" in vm.attention_label.lower()
    low = vm.attention_label.lower()
    assert "no" in low or "không" in low


def test_empty_vocab():
    vm = build_home_view_model(
        _plan(
            vocab_total=0,
            due_review_count=0,
            new_word_count=0,
            attention_word_count=0,
            planned_vocab_count=0,
        ),
        "Dutch",
        hour=10,
    )
    assert vm.empty_vocab is True
    assert vm.planned_vocab_count == 0


def test_reading_disabled():
    vm = build_home_view_model(_plan(reading_enabled=False), "French", hour=10)
    assert "Disabled" in vm.reading_label or "tắt" in vm.reading_label.lower()


def test_listening_enabled_label():
    vm = build_home_view_model(
        _plan(listening_enabled=True), "Dutch", hour=10
    )
    assert "Enabled" in vm.listening_label or "bật" in vm.listening_label.lower()


def test_multi_language_change_flag():
    vm = build_home_view_model(_plan(), "Dutch", study_language_count=2, hour=10)
    assert vm.can_change_language is True
    assert vm.language_label == "Dutch"


def test_primary_action_localized():
    vm = build_home_view_model(_plan(), "Dutch", hour=10)
    assert vm.primary_action_label
    assert "study" in vm.primary_action_label.lower() or "học" in vm.primary_action_label.lower()
