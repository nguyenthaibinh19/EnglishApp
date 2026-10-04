"""Home dashboard presentation model — pure transforms over DailyStudyPlan.

No Tkinter. No SRS recalculation. No network.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from daily_study import DailyStudyPlan


@dataclass(frozen=True)
class HomeViewModel:
    language_code: str
    language_label: str
    greeting: str
    due_label: str
    new_label: str
    attention_label: str
    vocab_plan_label: str
    reading_label: str
    listening_label: str
    primary_action_label: str
    empty_vocab: bool
    due_is_zero: bool
    attention_is_zero: bool
    planned_vocab_count: int
    can_change_language: bool


def greeting_for_local_hour(hour: Optional[int] = None) -> str:
    """Local greeting; hour injectable for tests."""
    import config

    if hour is None:
        hour = datetime.now().hour
    hour = int(hour) % 24
    if 5 <= hour < 12:
        return config.ui("Chào buổi sáng", "Good morning")
    if 12 <= hour < 18:
        return config.ui("Chào buổi chiều", "Good afternoon")
    return config.ui("Chào buổi tối", "Good evening")


def build_home_view_model(
    plan: DailyStudyPlan,
    language_label: str,
    *,
    study_language_count: int = 1,
    hour: Optional[int] = None,
) -> HomeViewModel:
    """Map a DailyStudyPlan into localized dashboard copy."""
    import config

    empty = int(plan.vocab_total or 0) <= 0
    due_zero = int(plan.due_review_count or 0) == 0
    attention_zero = int(plan.attention_word_count or 0) == 0

    if empty:
        due_label = config.ui("Chưa có từ vựng", "No vocabulary yet")
        new_label = config.ui("Hãy thêm từ để bắt đầu", "Add words to get started")
        attention_label = config.ui("Chưa có từ cần chú ý", "No words need attention")
        vocab_plan_label = config.ui(
            "Từ vựng · chưa có mục tiêu",
            "Vocabulary · no items planned",
        )
    else:
        if due_zero:
            due_label = config.ui("Không có từ đến hạn", "Nothing due")
        else:
            due_label = config.ui(
                f"{plan.due_review_count} đến hạn",
                f"{plan.due_review_count} due",
            )
        new_label = config.ui(
            f"{plan.new_word_count} từ mới",
            f"{plan.new_word_count} new",
        )
        if attention_zero:
            attention_label = config.ui("Không cần chú ý", "No words need attention")
        else:
            attention_label = config.ui(
                f"{plan.attention_word_count} cần chú ý",
                f"{plan.attention_word_count} need attention",
            )
        vocab_plan_label = config.ui(
            f"Từ vựng · {plan.planned_vocab_count} mục",
            f"Vocabulary · {plan.planned_vocab_count} items",
        )

    reading_label = config.ui(
        f"Đọc · {'bật' if plan.reading_enabled else 'tắt'}",
        f"Reading · {'Enabled' if plan.reading_enabled else 'Disabled'}",
    )
    listening_enabled = bool(getattr(plan, "listening_enabled", False))
    listening_label = config.ui(
        f"Nghe · {'bật' if listening_enabled else 'tắt'}",
        f"Listening · {'Enabled' if listening_enabled else 'Disabled'}",
    )

    return HomeViewModel(
        language_code=plan.language_code,
        language_label=language_label,
        greeting=greeting_for_local_hour(hour),
        due_label=due_label,
        new_label=new_label,
        attention_label=attention_label,
        vocab_plan_label=vocab_plan_label,
        reading_label=reading_label,
        listening_label=listening_label,
        primary_action_label=config.ui("Bắt đầu học hôm nay", "Start today's study"),
        empty_vocab=empty,
        due_is_zero=due_zero,
        attention_is_zero=attention_zero,
        planned_vocab_count=int(plan.planned_vocab_count or 0),
        can_change_language=int(study_language_count) > 1,
    )
