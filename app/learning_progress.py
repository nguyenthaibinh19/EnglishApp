"""Learning Progress query — derived, read-only analytics (Phase 16).

Architecture:

    VocabStore + Progress + SRS + AttemptHistory + MistakeBook
            ↓
    LearningProgressSnapshot
            ↓
    Progress view-model / ProgressApp

No persistence of dashboard metrics. No learning-algorithm changes.
Reuses DailyStudyPlanner / srs / MistakeBook semantics — does not redefine them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, List, Mapping, Optional, Sequence, Tuple

from attempt_history import AttemptHistory, LearningAttempt
from daily_study import build_daily_study_plan
from mistake_book import MistakeSummary, summarize_mistakes
from srs import is_new, parse_utc, utc_now
from text_utils import entry_word, normalize
from vocab_identity import entry_id


@dataclass(frozen=True)
class DayActivity:
    """One local calendar day's attempt activity."""

    date: str  # YYYY-MM-DD (learner-local)
    attempt_count: int
    mastery_attempt_count: int


@dataclass(frozen=True)
class RecentAttemptItem:
    """Compact recent-answer row (historical word snapshot)."""

    word: str
    timestamp: str
    correct: bool
    hint_used: bool
    verdict: str
    vocab_id: str = ""
    prompt: str = ""


@dataclass(frozen=True)
class LearningProgressSnapshot:
    """Read-only progress analytics for one study language."""

    language_code: str
    vocab_total: int
    practiced_word_count: int
    new_word_count: int
    due_review_count: int
    future_review_count: int
    attention_word_count: int
    total_attempt_count: int
    mastery_attempt_count: int
    non_mastery_attempt_count: int
    mastery_attempt_rate: Optional[float]
    recent_days: Tuple[DayActivity, ...]
    recent_attempts: Tuple[RecentAttemptItem, ...]


def attempt_local_date(
    timestamp: str,
    *,
    local_tz=None,
) -> Optional[str]:
    """Map a UTC (or offset) ISO timestamp to a learner-local calendar day.

    Uses the system local timezone by default (same spirit as Progress.today_key
    which uses ``date.today()``). Injectable timezone for tests.
    """
    dt = parse_utc(timestamp)
    if dt is None:
        return None
    if local_tz is not None:
        local = dt.astimezone(local_tz)
    else:
        local = dt.astimezone()
    return local.date().isoformat()


def _progress_stats_for_entry(
    entry: dict,
    progress_words: Mapping[str, dict],
) -> Optional[dict]:
    if not progress_words:
        return None
    vid = entry_id(entry)
    if vid and vid in progress_words:
        return progress_words.get(vid)
    key = normalize(entry_word(entry))
    if key and key in progress_words:
        return progress_words.get(key)
    return None


def practiced_word_count(
    vocab_entries: Sequence[dict],
    progress_words: Mapping[str, dict],
) -> int:
    """Current vocab entries with Progress.seen > 0 (not new)."""
    count = 0
    seen_keys: set[str] = set()
    for entry in vocab_entries or ():
        if not isinstance(entry, dict):
            continue
        vid = entry_id(entry)
        key = normalize(entry_word(entry))
        identity = vid or key
        if not identity or identity in seen_keys:
            continue
        seen_keys.add(identity)
        if not is_new(_progress_stats_for_entry(entry, progress_words)):
            count += 1
    return count


def build_day_activity(
    attempts: Sequence[LearningAttempt],
    *,
    days: int = 7,
    today_local: Optional[date] = None,
    local_tz=None,
    language_code: Optional[str] = None,
) -> Tuple[DayActivity, ...]:
    """Group attempts into the last ``days`` local calendar days (oldest → newest).

    Includes zero-count days. Attempts with unparseable timestamps are skipped
    for daily grouping (still counted in totals separately).
    """
    days = max(1, int(days))
    today = today_local or date.today()
    window_start = today - timedelta(days=days - 1)
    buckets = {
        (window_start + timedelta(days=offset)).isoformat(): [0, 0]
        for offset in range(days)
    }
    for attempt in attempts or ():
        if language_code is not None and attempt.language_code != language_code:
            continue
        day_key = attempt_local_date(attempt.timestamp, local_tz=local_tz)
        if day_key is None or day_key not in buckets:
            continue
        buckets[day_key][0] += 1
        if attempt.correct:
            buckets[day_key][1] += 1
    return tuple(
        DayActivity(
            date=day_key,
            attempt_count=counts[0],
            mastery_attempt_count=counts[1],
        )
        for day_key, counts in buckets.items()
    )


def build_learning_progress(
    language_code: str,
    vocab_entries: Sequence[dict],
    progress_words: Mapping[str, dict],
    attempts: Sequence[LearningAttempt],
    mistake_summaries: Sequence[MistakeSummary],
    *,
    now: Optional[datetime] = None,
    quiz_target: int = 0,
    reading_enabled: bool = False,
    activity_days: int = 7,
    recent_attempt_limit: int = 8,
    today_local: Optional[date] = None,
    local_tz=None,
) -> LearningProgressSnapshot:
    """Pure query: no I/O, no writes.

    Current-vocabulary metrics use VocabStore entries only.
    Attempt analytics use AttemptHistory events for this language (including
    legacy/orphan records) — they do not invent current vocab rows.
    NEW/DUE/FUTURE/ATTENTION come from DailyStudyPlanner / MistakeBook.
    """
    plan = build_daily_study_plan(
        language_code,
        vocab_entries,
        progress_words,
        mistake_summaries,
        quiz_target=quiz_target,
        reading_enabled=reading_enabled,
        now=now or utc_now(),
    )
    practiced = practiced_word_count(vocab_entries, progress_words)

    lang = str(language_code or "")
    # Prefer explicit language match; empty language_code on legacy rows in a
    # per-language file still counts (file is already language-scoped).
    if lang:
        scoped = [
            a
            for a in (attempts or ())
            if (not a.language_code) or a.language_code == lang
        ]
    else:
        scoped = list(attempts or ())

    total = len(scoped)
    mastery = sum(1 for a in scoped if a.correct)
    non_mastery = total - mastery
    rate = (mastery / total) if total else None

    recent_days = build_day_activity(
        scoped,
        days=activity_days,
        today_local=today_local,
        local_tz=local_tz,
        language_code=None,  # already scoped
    )

    limit = max(0, int(recent_attempt_limit))
    recent_src = scoped[-limit:] if limit else []
    recent_items = tuple(
        RecentAttemptItem(
            word=item.word,
            timestamp=item.timestamp,
            correct=bool(item.correct),
            hint_used=bool(item.hint_used),
            verdict=str(item.verdict or ""),
            vocab_id=str(item.vocab_id or ""),
            prompt=str(item.prompt or ""),
        )
        for item in reversed(recent_src)
    )

    return LearningProgressSnapshot(
        language_code=plan.language_code,
        vocab_total=plan.vocab_total,
        practiced_word_count=practiced,
        new_word_count=plan.new_word_count,
        due_review_count=plan.due_review_count,
        future_review_count=plan.future_review_count,
        attention_word_count=plan.attention_word_count,
        total_attempt_count=total,
        mastery_attempt_count=mastery,
        non_mastery_attempt_count=non_mastery,
        mastery_attempt_rate=rate,
        recent_days=recent_days,
        recent_attempts=recent_items,
    )


def load_learning_progress(
    language_code: str,
    *,
    now: Optional[datetime] = None,
    activity_days: int = 7,
    recent_attempt_limit: int = 8,
    today_local: Optional[date] = None,
    local_tz=None,
    vocab_store: Any = None,
    progress: Any = None,
    attempts: Optional[Sequence[LearningAttempt]] = None,
    mistake_summaries: Optional[Sequence[MistakeSummary]] = None,
) -> LearningProgressSnapshot:
    """Load local files once and build a snapshot (no network, no writes)."""
    import config
    from progress import Progress
    from vocab_store import VocabStore

    code = str(language_code or config.active_code()).strip().lower()
    store = vocab_store or VocabStore(config.vocab_path(code))
    prog = progress or Progress(config.progress_path(code))

    if attempts is None:
        history = AttemptHistory(
            config.attempts_path(code), language_code=code
        )
        attempts = history.load_attempts()
    if mistake_summaries is None:
        mistake_summaries = summarize_mistakes(attempts, language_code=code)

    return build_learning_progress(
        code,
        store.all(),
        prog.data.get("words") or {},
        attempts,
        mistake_summaries,
        now=now,
        quiz_target=0,
        reading_enabled=False,
        activity_days=activity_days,
        recent_attempt_limit=recent_attempt_limit,
        today_local=today_local,
        local_tz=local_tz,
    )
