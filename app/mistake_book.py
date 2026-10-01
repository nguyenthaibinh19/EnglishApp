"""Mistake Book v1 — truy vấn từ cần chú ý dựa trên AttemptHistory.

Quy tắc v1 (deterministic):
  Một từ xuất hiện trong Mistake Book khi lần thử *gần nhất* của từ đó
  có ``correct is False`` (chưa mastered: wrong / near / hint-assisted).

  Nếu lần thử gần nhất đã mastered (``correct is True``), từ biến mất khỏi
  danh sách cho đến khi lại có lần non-mastered.

  ``attention_count`` = tổng số lần non-mastered trong toàn bộ lịch sử từ đó
  (không chỉ kể từ lần mastery gần nhất).

Không import Tkinter. Không sửa attempts.jsonl.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

from attempt_history import AttemptHistory, LearningAttempt
from text_utils import entry_word, normalize


# Status keys derived only from existing verdict / hint_used.
STATUS_WRONG = "wrong"
STATUS_NEAR = "near"
STATUS_HINT = "hint"


@dataclass(frozen=True)
class MistakeSummary:
    word: str
    prompt: str
    attention_count: int
    last_user_answer: str
    expected_answer: str
    last_verdict: str
    last_hint_used: bool
    last_timestamp: str
    language_code: str = ""


def attention_status(verdict: str, hint_used: bool) -> str:
    """Map attempt fields → UI status key (no new classification)."""
    if hint_used and str(verdict) == "exact":
        return STATUS_HINT
    if str(verdict) == "near":
        return STATUS_NEAR
    return STATUS_WRONG


def summarize_mistakes(
    attempts: Iterable[LearningAttempt],
    language_code: Optional[str] = None,
) -> List[MistakeSummary]:
    """Aggregate non-mastered attention items from an attempt sequence.

    Groups by normalized ``word``. Filters by ``language_code`` when given.
    Sort: newest ``last_timestamp`` first, then higher ``attention_count``,
    then ``word`` ascending for stability.
    """
    # Preserve insertion order within each group via list append.
    groups: dict[str, list[LearningAttempt]] = {}
    for attempt in attempts:
        if language_code is not None and attempt.language_code != language_code:
            continue
        key = normalize(attempt.word)
        if not key:
            continue
        groups.setdefault(key, []).append(attempt)

    summaries: List[MistakeSummary] = []
    for _key, items in groups.items():
        latest = items[-1]
        if latest.correct:
            continue
        attention_count = sum(1 for item in items if not item.correct)
        summaries.append(
            MistakeSummary(
                word=latest.word,
                prompt=latest.prompt,
                attention_count=attention_count,
                last_user_answer=latest.user_answer,
                expected_answer=latest.expected_answer,
                last_verdict=latest.verdict,
                last_hint_used=bool(latest.hint_used),
                last_timestamp=latest.timestamp,
                language_code=latest.language_code,
            )
        )

    summaries.sort(
        key=lambda s: (-_timestamp_sort_key(s.last_timestamp), -s.attention_count, s.word)
    )
    return summaries


def load_mistake_summaries(
    filename: Optional[str] = None,
    language_code: Optional[str] = None,
) -> List[MistakeSummary]:
    """Load attempts from disk (missing file → empty) and summarize."""
    history = AttemptHistory(filename, language_code=language_code)
    code = language_code if language_code is not None else history.language_code
    return summarize_mistakes(history.load_attempts(), language_code=code)


def resolve_practice_entries(
    summaries: Iterable[MistakeSummary],
    vocab_entries: Iterable[dict],
) -> List[dict]:
    """Map Mistake Book rows → full vocab entries for the current language.

    - Prefer the first VocabStore row whose normalized word matches (same as
      ``VocabStore.index_of`` — duplicate headwords are a known limitation).
    - Skip summaries with no matching vocab entry (deleted words stay in history).
    - Returns shallow-copied entry dicts; does not invent incomplete entries.
    """
    by_key: dict[str, dict] = {}
    for entry in vocab_entries or []:
        if not isinstance(entry, dict):
            continue
        key = normalize(entry_word(entry))
        if not key or key in by_key:
            continue  # first match wins for duplicates
        if not entry.get("vi"):
            continue
        by_key[key] = entry

    resolved: List[dict] = []
    seen: set[str] = set()
    for summary in summaries or []:
        key = normalize(summary.word)
        if not key or key in seen:
            continue
        entry = by_key.get(key)
        if entry is None:
            continue
        seen.add(key)
        copy = {"word": str(entry_word(entry)).strip(), "vi": str(entry["vi"]).strip()}
        for field in ("alt", "example", "note", "type"):
            if entry.get(field):
                copy[field] = entry[field]
        resolved.append(copy)
    return resolved


def practice_target(entry_count: int, quiz_target: Optional[int] = None) -> int:
    """Session target for Practice Mistakes.

    QuizEngine counts total session-correct answers (exact/near), not unique words.
    Cap at subset size so a tiny mistake list finishes without forcing many
    re-answers of the same item by default.
    """
    import config

    base = int(quiz_target if quiz_target is not None else config.QUIZ_TARGET_CORRECT)
    if entry_count <= 0 or base <= 0:
        return 0
    return max(1, min(base, int(entry_count)))


def _timestamp_sort_key(value: str) -> float:
    """ISO timestamps sort lexicographically when well-formed; empty → 0."""
    text = str(value or "").strip()
    if not text:
        return 0.0
    # Prefer lexical ISO-8601 ordering (UTC offsets included).
    # Map to ordinal-ish float via char codes only if needed — lexical is enough
    # when all timestamps use the same Phase 5 format.
    try:
        from datetime import datetime

        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        return 0.0
