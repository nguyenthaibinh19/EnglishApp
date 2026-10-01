"""SRS v2 — long-term review due dates (simple interval ladder, not FSRS).

Separates:
  long-term: is this word due yet?  (due_at / interval_days)
  session:   which candidate is asked next?  (VocabScheduler weights + requeue)

Persisted on each word in progress.json as optional fields:
  due_at: ISO-8601 UTC
  interval_days: int

Missing fields (legacy progress) ⇒ treated as due (bootstrap without wipe).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

# Mastered streak → next interval (days). Cap at last rung.
INTERVAL_LADDER = (1, 3, 7, 14, 30)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def parse_utc(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return ensure_utc(parsed)


def to_utc_iso(value: datetime) -> str:
    return ensure_utc(value).isoformat(timespec="seconds")


def interval_for_streak(streak: int) -> int:
    """Map current mastered streak to the next review interval in days."""
    if streak <= 0:
        return 0
    index = min(int(streak), len(INTERVAL_LADDER)) - 1
    return INTERVAL_LADDER[index]


def is_due(stats: Optional[dict], now: Optional[datetime] = None) -> bool:
    """True if unseen, never scheduled, or due_at <= now."""
    now = ensure_utc(now or utc_now())
    if not stats:
        return True
    if int(stats.get("seen") or 0) == 0:
        return True
    due_at = parse_utc(stats.get("due_at"))
    if due_at is None:
        # Legacy / bootstrap: no explicit schedule yet → available.
        return True
    return due_at <= now


def is_new(stats: Optional[dict]) -> bool:
    """True when the word has never been learned (no record or seen == 0)."""
    if not stats:
        return True
    return int(stats.get("seen") or 0) == 0


def is_future(stats: Optional[dict], now: Optional[datetime] = None) -> bool:
    """Seen word with a future due_at (not due, not new)."""
    if is_new(stats):
        return False
    return not is_due(stats, now)


def apply_review_to_stats(
    stats: dict,
    *,
    mastered: bool,
    reviewed_at: Optional[datetime] = None,
) -> None:
    """Update SRS fields on an existing word stats dict.

    Call after counters/streak/`last_seen` have already been updated for this answer.
    ``mastered`` must match Progress.record(correct=...) / LearningAttempt.correct.
    """
    reviewed_at = ensure_utc(reviewed_at or utc_now())
    if mastered:
        streak = int(stats.get("streak") or 0)
        interval = interval_for_streak(streak)
        stats["interval_days"] = interval
        stats["due_at"] = to_utc_iso(reviewed_at + timedelta(days=interval))
    else:
        # Failure / near / hint: reset interval; due immediately for next session.
        stats["interval_days"] = 0
        stats["due_at"] = to_utc_iso(reviewed_at)


def due_priority_key(stats: Optional[dict], now: Optional[datetime] = None):
    """Sort key for fallback: soonest due first; missing/unseen first."""
    now = ensure_utc(now or utc_now())
    if not stats or int(stats.get("seen") or 0) == 0:
        return (0, now)
    due_at = parse_utc(stats.get("due_at"))
    if due_at is None:
        return (0, now)
    return (1, due_at)
