"""Mistake Book v1 — truy vấn từ cần chú ý dựa trên AttemptHistory.

Quy tắc v1 (deterministic):
  Một từ xuất hiện trong Mistake Book khi lần thử *gần nhất* của từ đó
  có ``correct is False`` (chưa mastered: wrong / near / hint-assisted).

  Nếu lần thử gần nhất đã mastered (``correct is True``), từ biến mất khỏi
  danh sách cho đến khi lại có lần non-mastered.

  ``attention_count`` = tổng số lần non-mastered trong toàn bộ lịch sử từ đó
  (không chỉ kể từ lần mastery gần nhất).

Phase 13: nhóm theo ``vocab_id`` khi có; legacy unresolved → normalize(word).

Không import Tkinter. Không sửa attempts.jsonl.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

from attempt_history import AttemptHistory, LearningAttempt
from text_utils import entry_word, normalize
from vocab_identity import entry_id
from vocabulary_model import entry_meaning, normalize_entry_dict


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
    vocab_id: str = ""


def attention_status(verdict: str, hint_used: bool) -> str:
    """Map attempt fields → UI status key (no new classification)."""
    if hint_used and str(verdict) == "exact":
        return STATUS_HINT
    if str(verdict) == "near":
        return STATUS_NEAR
    return STATUS_WRONG


def _attempt_group_key(attempt: LearningAttempt) -> str:
    vid = str(attempt.vocab_id or "").strip()
    if vid:
        return f"id:{vid}"
    key = normalize(attempt.word)
    return f"word:{key}" if key else ""


def summarize_mistakes(
    attempts: Iterable[LearningAttempt],
    language_code: Optional[str] = None,
) -> List[MistakeSummary]:
    """Aggregate non-mastered attention items from an attempt sequence.

    Groups by vocab_id when present, else normalized ``word``.
    Filters by ``language_code`` when given.
    Sort: newest ``last_timestamp`` first, then higher ``attention_count``,
    then ``word`` ascending for stability.
    """
    groups: dict[str, list[LearningAttempt]] = {}
    for attempt in attempts:
        if language_code is not None and attempt.language_code != language_code:
            continue
        key = _attempt_group_key(attempt)
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
                vocab_id=str(latest.vocab_id or ""),
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

    Prefer stable ``vocab_id`` match. Legacy summaries without ID fall back to
    first normalized-word match (Phase 7 behavior).
    Skip summaries with no matching vocab entry (deleted words stay in history).
    Returns shallow-copied entry dicts including ``id`` when present.
    """
    by_id: dict[str, dict] = {}
    by_key: dict[str, dict] = {}
    for entry in vocab_entries or []:
        if not isinstance(entry, dict):
            continue
        if not entry_meaning(entry):
            continue
        vid = entry_id(entry)
        if vid and vid not in by_id:
            by_id[vid] = entry
        key = normalize(entry_word(entry))
        if key and key not in by_key:
            by_key[key] = entry

    resolved: List[dict] = []
    seen_ids: set[str] = set()
    seen_keys: set[str] = set()
    for summary in summaries or []:
        entry = None
        vid = str(getattr(summary, "vocab_id", "") or "").strip()
        if vid and vid in by_id:
            if vid in seen_ids:
                continue
            entry = by_id[vid]
            seen_ids.add(vid)
        else:
            key = normalize(summary.word)
            if not key or key in seen_keys:
                continue
            entry = by_key.get(key)
            if entry is None:
                continue
            seen_keys.add(key)
            # Also mark id so we don't practice the same row twice via mixed keys.
            eid = entry_id(entry)
            if eid:
                seen_ids.add(eid)

        if entry is None:
            continue
        copy = normalize_entry_dict(entry, assign_id=False)
        if copy is None:
            continue
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
    try:
        from datetime import datetime

        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        return 0.0
