"""Progress dashboard presentation model — pure transforms over LearningProgressSnapshot.

No Tkinter. No SRS recalculation. No network.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from learning_progress import LearningProgressSnapshot, RecentAttemptItem


@dataclass(frozen=True)
class ProgressDayRow:
    date_label: str
    summary_label: str
    attempt_count: int
    mastery_attempt_count: int
    bar_ratio: float  # 0..1 relative to busiest day in the window


@dataclass(frozen=True)
class ProgressAttemptRow:
    word: str
    when_label: str
    result_label: str


@dataclass(frozen=True)
class ProgressViewModel:
    language_code: str
    language_label: str
    title: str
    # Overview
    total_label: str
    practiced_label: str
    new_label: str
    due_label: str
    future_label: str
    attention_label: str
    # Activity
    attempts_label: str
    mastery_answers_label: str
    mastery_rate_label: str
    # Recent
    recent_days_title: str
    recent_days: Tuple[ProgressDayRow, ...]
    recent_attempts_title: str
    recent_attempts: Tuple[ProgressAttemptRow, ...]
    # Empty-state flags
    empty_vocab: bool
    never_practiced: bool
    no_attempts: bool
    nothing_due: bool
    no_attention: bool
    overview_hint: str
    activity_hint: str
    can_change_language: bool


def _format_rate(rate: Optional[float]) -> str:
    import config

    if rate is None:
        return config.ui("Chưa có lần trả lời", "No answers yet")
    pct = int(round(rate * 100))
    return config.ui(
        f"{pct}% câu trả lời đạt chuẩn thuộc",
        f"{pct}% mastery-quality answers",
    )


def _result_label(item: RecentAttemptItem) -> str:
    import config
    from vocabulary_library import attempt_status_label
    from attempt_history import LearningAttempt

    # Reuse Word Detail attempt wording via a thin LearningAttempt adapter.
    attempt = LearningAttempt(
        timestamp=item.timestamp,
        language_code="",
        word=item.word,
        user_answer="",
        expected_answer="",
        correct=item.correct,
        verdict=item.verdict or "wrong",
        hint_used=item.hint_used,
        prompt=item.prompt,
        vocab_id=item.vocab_id,
    )
    return attempt_status_label(attempt)


def _when_label(timestamp: str) -> str:
    from srs import parse_utc

    dt = parse_utc(timestamp)
    if dt is None:
        return timestamp or "—"
    local = dt.astimezone()
    return local.strftime("%Y-%m-%d %H:%M")


def build_progress_view_model(
    snapshot: LearningProgressSnapshot,
    language_label: str,
    *,
    study_language_count: int = 1,
) -> ProgressViewModel:
    """Map LearningProgressSnapshot into localized Progress dashboard copy."""
    import config

    empty = int(snapshot.vocab_total or 0) <= 0
    practiced = int(snapshot.practiced_word_count or 0)
    never = (not empty) and practiced == 0
    no_attempts = int(snapshot.total_attempt_count or 0) == 0
    nothing_due = int(snapshot.due_review_count or 0) == 0
    no_attention = int(snapshot.attention_word_count or 0) == 0

    if empty:
        overview_hint = config.ui(
            "Kho từ đang trống. Hãy thêm từ để theo dõi tiến độ.",
            "Your vocabulary list is empty. Add words to track progress.",
        )
        total_label = config.ui("0 từ vựng", "0 vocabulary")
        practiced_label = config.ui("0 đã luyện", "0 practiced")
        new_label = config.ui("0 từ mới", "0 new")
        due_label = config.ui("Chưa có từ đến hạn", "Nothing due")
        future_label = config.ui("0 ôn sau", "0 future reviews")
        attention_label = config.ui("Không cần chú ý", "No words need attention")
    else:
        overview_hint = ""
        if never:
            overview_hint = config.ui(
                "Bạn đã có từ vựng nhưng chưa luyện lần nào.",
                "You have vocabulary but have not practiced yet.",
            )
        total_label = config.ui(
            f"{snapshot.vocab_total} từ vựng",
            f"{snapshot.vocab_total} vocabulary",
        )
        practiced_label = config.ui(
            f"{practiced} đã luyện",
            f"{practiced} practiced",
        )
        new_label = config.ui(
            f"{snapshot.new_word_count} từ mới",
            f"{snapshot.new_word_count} new",
        )
        if nothing_due:
            due_label = config.ui("Không có từ đến hạn", "Nothing due now")
        else:
            due_label = config.ui(
                f"{snapshot.due_review_count} đến hạn",
                f"{snapshot.due_review_count} due",
            )
        future_label = config.ui(
            f"{snapshot.future_review_count} ôn sau",
            f"{snapshot.future_review_count} future",
        )
        if no_attention:
            attention_label = config.ui("Không cần chú ý", "No words need attention")
        else:
            attention_label = config.ui(
                f"{snapshot.attention_word_count} cần chú ý",
                f"{snapshot.attention_word_count} need attention",
            )

    if no_attempts:
        activity_hint = config.ui(
            "Chưa có lần trả lời nào — không có tỉ lệ thất bại.",
            "No answers yet — there is no failure rate to show.",
        )
        attempts_label = config.ui("0 lần trả lời", "0 answers")
        mastery_answers_label = config.ui(
            "0 câu đạt chuẩn thuộc",
            "0 mastery-quality answers",
        )
    else:
        activity_hint = ""
        attempts_label = config.ui(
            f"{snapshot.total_attempt_count} lần trả lời",
            f"{snapshot.total_attempt_count} answers",
        )
        mastery_answers_label = config.ui(
            f"{snapshot.mastery_attempt_count} câu đạt chuẩn thuộc",
            f"{snapshot.mastery_attempt_count} mastery-quality answers",
        )

    peak = max((day.attempt_count for day in snapshot.recent_days), default=0)
    day_rows = []
    for day in snapshot.recent_days:
        ratio = (day.attempt_count / peak) if peak else 0.0
        day_rows.append(
            ProgressDayRow(
                date_label=day.date,
                summary_label=config.ui(
                    f"{day.attempt_count} lần · {day.mastery_attempt_count} đạt chuẩn",
                    f"{day.attempt_count} answers · {day.mastery_attempt_count} mastery-quality",
                ),
                attempt_count=day.attempt_count,
                mastery_attempt_count=day.mastery_attempt_count,
                bar_ratio=ratio,
            )
        )

    attempt_rows = tuple(
        ProgressAttemptRow(
            word=item.word,
            when_label=_when_label(item.timestamp),
            result_label=_result_label(item),
        )
        for item in snapshot.recent_attempts
    )

    return ProgressViewModel(
        language_code=snapshot.language_code,
        language_label=language_label,
        title=config.ui("Tiến độ", "Progress"),
        total_label=total_label,
        practiced_label=practiced_label,
        new_label=new_label,
        due_label=due_label,
        future_label=future_label,
        attention_label=attention_label,
        attempts_label=attempts_label,
        mastery_answers_label=mastery_answers_label,
        mastery_rate_label=_format_rate(snapshot.mastery_attempt_rate),
        recent_days_title=config.ui("7 ngày gần đây", "Last 7 days"),
        recent_days=tuple(day_rows),
        recent_attempts_title=config.ui("Câu trả lời gần đây", "Recent answers"),
        recent_attempts=attempt_rows,
        empty_vocab=empty,
        never_practiced=never,
        no_attempts=no_attempts,
        nothing_due=nothing_due,
        no_attention=no_attention,
        overview_hint=overview_hint,
        activity_hint=activity_hint,
        can_change_language=int(study_language_count) > 1,
    )
