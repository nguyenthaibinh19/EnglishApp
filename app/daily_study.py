"""Daily Study Planner — derived plan for one study language.

Answers: what should this learner study today?

Categories (not mutually exclusive):
  NEW              — no progress / seen == 0
  DUE              — seen > 0 and srs.is_due (legacy missing due_at counts as due)
  FUTURE           — seen > 0 and not due
  NEEDS ATTENTION  — Phase 6 Mistake Book (latest attempt non-mastered)

planned_vocab_count preserves current lock-session workload:
  min(vocab_total, QUIZ_TARGET_CORRECT)

Future words are never counted as due. Quiz fallback to future words is a
session-selection concern (Phase 8), not Daily Study reporting.

No Tkinter. No network. No persistence — recompute from domain state.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, List, Mapping, Optional, Sequence

from mistake_book import MistakeSummary, load_mistake_summaries
from srs import is_due, is_future, is_new, utc_now
from text_utils import entry_word, normalize
from vocab_identity import entry_id


@dataclass(frozen=True)
class DailyStudyPlan:
    language_code: str
    vocab_total: int
    due_review_count: int
    new_word_count: int
    future_review_count: int
    attention_word_count: int
    planned_vocab_count: int
    reading_enabled: bool


def build_daily_study_plan(
    language_code: str,
    vocab_entries: Sequence[dict],
    progress_words: Mapping[str, dict],
    mistake_summaries: Sequence[MistakeSummary],
    *,
    quiz_target: int,
    reading_enabled: bool,
    now: Optional[datetime] = None,
) -> DailyStudyPlan:
    """Pure planner: no I/O, no writes.

    ``progress_words`` is Progress.data['words'] (vocab_id keys after Phase 13;
    legacy normalized-word keys still work as fallback).
    """
    now = now or utc_now()
    due = 0
    new = 0
    future = 0
    seen_keys: set[str] = set()

    for entry in vocab_entries or ():
        if not isinstance(entry, dict):
            continue
        key = normalize(entry_word(entry))
        vid = entry_id(entry)
        identity = vid or key
        if not identity or identity in seen_keys:
            continue
        seen_keys.add(identity)
        stats = None
        if progress_words:
            if vid and vid in progress_words:
                stats = progress_words.get(vid)
            elif key:
                stats = progress_words.get(key)
        if is_new(stats):
            new += 1
        elif is_due(stats, now):
            due += 1
        elif is_future(stats, now):
            future += 1
        else:
            # Defensive: treat ambiguous as due (legacy-safe).
            due += 1

    vocab_total = len(seen_keys)
    attention = len(mistake_summaries or ())
    target = max(0, int(quiz_target))
    planned = min(vocab_total, target) if vocab_total > 0 and target > 0 else 0

    return DailyStudyPlan(
        language_code=str(language_code or ""),
        vocab_total=vocab_total,
        due_review_count=due,
        new_word_count=new,
        future_review_count=future,
        attention_word_count=attention,
        planned_vocab_count=planned,
        reading_enabled=bool(reading_enabled),
    )


def plan_for_language(
    language_code: str,
    *,
    now: Optional[datetime] = None,
    quiz_target: Optional[int] = None,
    reading_enabled: Optional[bool] = None,
    vocab_store: Any = None,
    progress: Any = None,
    attempts_filename: Optional[str] = None,
) -> DailyStudyPlan:
    """Convenience loader for one study language (reads local files only)."""
    import config
    from progress import Progress
    from vocab_store import VocabStore

    code = str(language_code or config.active_code()).strip().lower()
    store = vocab_store or VocabStore(config.vocab_path(code))
    prog = progress or Progress(config.progress_path(code))
    attempts_path = (
        attempts_filename
        if attempts_filename is not None
        else config.attempts_path(code)
    )
    summaries = load_mistake_summaries(attempts_path, language_code=code)
    target = config.QUIZ_TARGET_CORRECT if quiz_target is None else int(quiz_target)
    reading = (
        config.activity_enabled("reading")
        if reading_enabled is None
        else bool(reading_enabled)
    )
    return build_daily_study_plan(
        code,
        store.all(),
        prog.data.get("words") or {},
        summaries,
        quiz_target=target,
        reading_enabled=reading,
        now=now,
    )


def format_plan_preview_lines(plan: DailyStudyPlan, language_label: str) -> List[str]:
    """Localized preview lines for FreeHome (uses config.ui)."""
    import config

    lines = [
        config.ui("Học hôm nay", "Today's Study"),
        language_label,
        config.ui(
            f"{plan.due_review_count} từ đến hạn ôn",
            f"{plan.due_review_count} reviews due",
        ),
        config.ui(
            f"{plan.new_word_count} từ mới",
            f"{plan.new_word_count} new words",
        ),
        config.ui(
            f"{plan.attention_word_count} từ cần chú ý",
            f"{plan.attention_word_count} words need attention",
        ),
    ]
    if plan.due_review_count == 0 and plan.vocab_total > 0:
        lines.append(
            config.ui(
                f"Chưa có từ đến hạn — phiên học vẫn hỏi tối đa {plan.planned_vocab_count} câu.",
                f"Nothing due — session still asks up to {plan.planned_vocab_count} answers.",
            )
        )
    lines.append(
        config.ui(
            f"Đọc: {'bật' if plan.reading_enabled else 'tắt'}",
            f"Reading: {'enabled' if plan.reading_enabled else 'disabled'}",
        )
    )
    return lines
