"""Vocabulary Library — read aggregation over VocabStore + Progress + SRS + Attempts.

No Tkinter. No network. Does not mutate vocab/progress/attempts.
Phase 13: domain identity is vocab_id; store_index remains for safe list edits.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from attempt_history import AttemptHistory, LearningAttempt
from mistake_book import MistakeSummary, summarize_mistakes
from srs import is_due, is_new, parse_utc, utc_now
from text_utils import entry_word, fold_accents, normalize, strip_tags
from vocab_identity import entry_id
from vocabulary_model import (
    VocabularyExample,
    entry_alternatives,
    entry_example,
    entry_example_texts,
    entry_examples,
    entry_forms,
    entry_meaning,
    entry_part_of_speech,
    entry_pronunciation,
)


RECENT_ATTEMPT_LIMIT = 8

FILTER_ALL = "all"
FILTER_DUE = "due"
FILTER_ATTENTION = "attention"
FILTER_NEW = "new"


@dataclass(frozen=True)
class VocabularyListItem:
    store_index: int
    vocab_id: str
    word: str
    prompt: str
    normalized_key: str
    seen: int
    streak: int
    is_new: bool
    is_due: bool
    needs_attention: bool
    attention_count: int


@dataclass(frozen=True)
class VocabularyDetail:
    store_index: int
    vocab_id: str
    language_code: str
    word: str
    prompt: str
    alt: Tuple[str, ...]
    example: str
    seen: int
    mastered_count: int
    non_mastered_count: int
    streak: int
    mastery_rate: Optional[float]
    interval_days: Optional[int]
    due_at: Optional[str]
    is_new: bool
    is_due: bool
    needs_attention: bool
    attention_count: int
    recent_attempts: Tuple[LearningAttempt, ...]
    part_of_speech: str = ""
    examples: Tuple[VocabularyExample, ...] = ()
    pronunciation_ipa: str = ""
    forms: Tuple[Tuple[str, str], ...] = ()


def _stats_for(
    progress_words: Mapping[str, dict],
    *,
    vocab_id: str = "",
    normalized_key: str = "",
) -> dict:
    if not progress_words:
        return {}
    if vocab_id and vocab_id in progress_words:
        return progress_words.get(vocab_id) or {}
    if normalized_key and normalized_key in progress_words:
        return progress_words.get(normalized_key) or {}
    return {}


def _attention_maps(
    mistake_summaries: Sequence[MistakeSummary],
) -> Tuple[Dict[str, int], Dict[str, int]]:
    by_id: Dict[str, int] = {}
    by_word: Dict[str, int] = {}
    for summary in mistake_summaries or ():
        vid = str(getattr(summary, "vocab_id", "") or "").strip()
        if vid:
            by_id[vid] = int(summary.attention_count or 0)
        key = normalize(summary.word)
        if key:
            by_word[key] = int(summary.attention_count or 0)
    return by_id, by_word


def build_vocabulary_items(
    vocab_entries: Sequence[dict],
    progress_words: Mapping[str, dict],
    mistake_summaries: Sequence[MistakeSummary],
    *,
    now: Optional[datetime] = None,
) -> List[VocabularyListItem]:
    """Build list models for current vocabulary only (not orphan history words)."""
    now = now or utc_now()
    attention_by_id, attention_by_word = _attention_maps(mistake_summaries)

    items: List[VocabularyListItem] = []
    for index, entry in enumerate(vocab_entries or ()):
        if not isinstance(entry, dict):
            continue
        word = strip_tags(entry_word(entry))
        prompt = entry_meaning(entry)
        if not word or not prompt:
            continue
        key = normalize(entry_word(entry))
        vid = entry_id(entry)
        stats = _stats_for(progress_words, vocab_id=vid, normalized_key=key)
        seen = int(stats.get("seen") or 0)
        streak = int(stats.get("streak") or 0)
        new = is_new(stats)
        due = (not new) and is_due(stats, now)
        if vid and vid in attention_by_id:
            needs = True
            attention_count = attention_by_id[vid]
        else:
            needs = key in attention_by_word
            attention_count = attention_by_word.get(key, 0)
        items.append(
            VocabularyListItem(
                store_index=index,
                vocab_id=vid,
                word=word,
                prompt=prompt,
                normalized_key=key,
                seen=seen,
                streak=streak,
                is_new=new,
                is_due=due,
                needs_attention=needs,
                attention_count=attention_count,
            )
        )

    items.sort(key=lambda item: (item.normalized_key, item.store_index))
    return items


def filter_vocabulary_items(
    items: Sequence[VocabularyListItem],
    *,
    query: str = "",
    filter_key: str = FILTER_ALL,
    vocab_entries: Optional[Sequence[dict]] = None,
) -> List[VocabularyListItem]:
    """Search + optional simple filter. Does not mutate inputs."""
    needle = fold_accents(normalize(query or ""))
    filter_key = (filter_key or FILTER_ALL).strip().lower()

    result: List[VocabularyListItem] = []
    for item in items:
        if filter_key == FILTER_DUE and not item.is_due:
            continue
        if filter_key == FILTER_ATTENTION and not item.needs_attention:
            continue
        if filter_key == FILTER_NEW and not item.is_new:
            continue
        if needle:
            entry = None
            if vocab_entries is not None and 0 <= item.store_index < len(vocab_entries):
                entry = vocab_entries[item.store_index]
            if not _matches_search(item, entry, needle):
                continue
        result.append(item)
    return result


def _matches_search(item: VocabularyListItem, entry: Optional[dict], needle: str) -> bool:
    fields = [item.word, item.prompt]
    if entry:
        fields.append(entry_word(entry))
        fields.append(" ".join(entry_alternatives(entry)))
        fields.extend(entry_example_texts(entry))
    return any(needle in fold_accents(normalize(str(field))) for field in fields)


def recent_attempts_for_word(
    attempts: Sequence[LearningAttempt],
    word: str,
    *,
    vocab_id: str = "",
    language_code: Optional[str] = None,
    limit: int = RECENT_ATTEMPT_LIMIT,
) -> List[LearningAttempt]:
    vid = str(vocab_id or "").strip()
    key = normalize(word)
    matched = []
    for attempt in attempts:
        if language_code is not None and attempt.language_code != language_code:
            continue
        if vid and attempt.vocab_id:
            if attempt.vocab_id == vid:
                matched.append(attempt)
            continue
        if key and normalize(attempt.word) == key:
            matched.append(attempt)
    if limit <= 0:
        return []
    return matched[-limit:][::-1]  # newest first


def build_vocabulary_detail(
    entry: dict,
    store_index: int,
    *,
    language_code: str,
    progress_words: Mapping[str, dict],
    attempts: Sequence[LearningAttempt],
    mistake_summaries: Sequence[MistakeSummary],
    now: Optional[datetime] = None,
    recent_limit: int = RECENT_ATTEMPT_LIMIT,
) -> VocabularyDetail:
    now = now or utc_now()
    word = strip_tags(entry_word(entry))
    key = normalize(entry_word(entry))
    vid = entry_id(entry)
    stats = _stats_for(progress_words, vocab_id=vid, normalized_key=key)
    seen = int(stats.get("seen") or 0)
    mastered = int(stats.get("correct") or 0)
    wrong = int(stats.get("wrong") or 0)
    streak = int(stats.get("streak") or 0)
    new = is_new(stats)
    due = (not new) and is_due(stats, now)
    interval = stats.get("interval_days")
    due_at = stats.get("due_at")
    attention_by_id, attention_by_word = _attention_maps(mistake_summaries)
    if vid and vid in attention_by_id:
        needs = True
        attention_count = attention_by_id[vid]
    else:
        needs = key in attention_by_word
        attention_count = attention_by_word.get(key, 0)
    alt = tuple(entry_alternatives(entry))
    examples = tuple(entry_examples(entry))
    pronunciation = entry_pronunciation(entry)
    forms = tuple(entry_forms(entry).as_dict().items())
    rate = (mastered / seen) if seen else None
    recent = recent_attempts_for_word(
        attempts,
        word,
        vocab_id=vid,
        language_code=language_code,
        limit=recent_limit,
    )
    return VocabularyDetail(
        store_index=store_index,
        vocab_id=vid,
        language_code=language_code,
        word=word,
        prompt=entry_meaning(entry),
        alt=alt,
        example=entry_example(entry),
        seen=seen,
        mastered_count=mastered,
        non_mastered_count=wrong,
        streak=streak,
        mastery_rate=rate,
        interval_days=int(interval) if interval is not None else None,
        due_at=str(due_at) if due_at else None,
        is_new=new,
        is_due=due,
        needs_attention=needs,
        attention_count=attention_count,
        recent_attempts=tuple(recent),
        part_of_speech=entry_part_of_speech(entry),
        examples=examples,
        pronunciation_ipa=pronunciation.ipa,
        forms=forms,
    )


def load_vocabulary_library(
    language_code: str,
    *,
    now: Optional[datetime] = None,
    vocab_store: Any = None,
    progress: Any = None,
    attempts_filename: Optional[str] = None,
) -> Tuple[List[VocabularyListItem], Any, Any, List[LearningAttempt], List[MistakeSummary]]:
    """Convenience loader. Returns items + live store/progress for edit operations."""
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
    attempts = AttemptHistory(attempts_path, language_code=code).load_attempts()
    summaries = summarize_mistakes(attempts, language_code=code)
    items = build_vocabulary_items(
        store.all(),
        prog.data.get("words") or {},
        summaries,
        now=now,
    )
    return items, store, prog, attempts, summaries


# ---------- presentation helpers (no Tk) ----------

def due_status_label(detail_or_item, *, now: Optional[datetime] = None) -> str:
    import config

    if getattr(detail_or_item, "is_new", False):
        return config.ui("Chưa học", "Not studied yet")
    if getattr(detail_or_item, "is_due", False):
        return config.ui("Đến hạn ôn", "Due now")
    due_at = getattr(detail_or_item, "due_at", None)
    parsed = parse_utc(due_at) if due_at else None
    if parsed is not None:
        return config.ui(
            f"Ôn tiếp: {parsed.date().isoformat()}",
            f"Next review: {parsed.date().isoformat()}",
        )
    return config.ui("Chưa lên lịch SRS", "Not scheduled yet")


def attention_status_label(needs_attention: bool, attention_count: int = 0) -> str:
    import config

    if not needs_attention:
        return config.ui("Không cần chú ý", "No attention needed")
    if attention_count > 0:
        return config.ui(
            f"Cần chú ý · {attention_count} lần",
            f"Needs attention · {attention_count}×",
        )
    return config.ui("Cần chú ý", "Needs attention")


def mastery_rate_label(rate: Optional[float], seen: int) -> str:
    import config

    if not seen or rate is None:
        return config.ui("Chưa có thống kê thuộc", "No mastery stats yet")
    pct = int(round(rate * 100))
    return config.ui(
        f"Thuộc (exact, không gợi ý): {pct}%",
        f"Mastered (exact, no hint): {pct}%",
    )


def attempt_status_label(attempt: LearningAttempt) -> str:
    import config

    if attempt.correct:
        return config.ui("Thuộc", "Mastered")
    if attempt.hint_used and attempt.verdict == "exact":
        return config.ui("Có gợi ý", "Used a hint")
    if attempt.verdict == "near":
        return config.ui("Gần đúng", "Almost correct")
    return config.ui("Sai", "Wrong")


def format_list_subtitle(item: VocabularyListItem) -> str:
    import config

    parts = []
    if item.is_new:
        parts.append(config.ui("mới", "new"))
    else:
        parts.append(config.ui(f"chuỗi {item.streak}", f"streak {item.streak}"))
        if item.is_due:
            parts.append(config.ui("đến hạn", "due"))
    if item.needs_attention:
        parts.append(config.ui("cần chú ý", "needs attention"))
    return " · ".join(parts)
