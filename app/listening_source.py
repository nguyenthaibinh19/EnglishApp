"""Listening content source: target selection, AI generation, cache, fallback.

UI-independent. No Progress/SRS/AttemptHistory writes. No audio generation.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from typing import Any, Callable, List, Mapping, Optional, Sequence

import ai_teacher
import config
from listening import ListeningItem, sample_listening_items
from listening_content import (
    LISTENING_CONTENT_SCHEMA_VERSION,
    ListeningContentError,
    listening_item_as_dict,
    normalize_listening_item,
)
from mistake_book import MistakeSummary, resolve_practice_entries
from progress import today_key
from text_utils import entry_word, normalize
from vocab_identity import entry_id
from vocabulary_model import entry_meaning, normalize_entry_dict


class NoListeningAvailable(RuntimeError):
    """No valid cache, AI result, or bundled sample for this language."""


def select_listening_targets(
    store,
    progress,
    *,
    language_code: str,
    mistake_summaries: Optional[Sequence[MistakeSummary]] = None,
    count: Optional[int] = None,
) -> List[dict]:
    """Deterministic target vocabulary for Listening (StudyGuard chooses, not AI).

    Priority:
      A. vocabulary practiced today
      B. current actionable Mistake Book entries
      C. weakest practiced vocabulary
      D. remaining current vocabulary as stable fill

    Returns up to ``count`` canonical VocabularyEntry dicts (read-only).
    """
    limit = int(count if count is not None else config.LISTENING_WORD_COUNT)
    if limit <= 0 or store.count() == 0:
        return []

    chosen: List[dict] = []
    seen_ids: set[str] = set()
    seen_words: set[str] = set()

    def _canonical(entry: Mapping[str, Any]) -> Optional[dict]:
        copy = normalize_entry_dict(entry, assign_id=False)
        if copy is None:
            return None
        word = normalize(entry_word(copy))
        if not word:
            return None
        return copy

    def take(entries: Sequence[Mapping[str, Any]]) -> bool:
        for entry in entries:
            copy = _canonical(entry)
            if copy is None:
                continue
            vid = entry_id(copy) or ""
            word_key = normalize(entry_word(copy))
            if vid and vid in seen_ids:
                continue
            if word_key in seen_words:
                continue
            if vid:
                seen_ids.add(vid)
            seen_words.add(word_key)
            chosen.append(copy)
            if len(chosen) >= limit:
                return True
        return False

    # A) Studied today (progress day keys: vocab_id or legacy word).
    take(store.entries_for_keys(progress.words_studied_today()))
    if len(chosen) >= limit:
        return chosen[:limit]

    # B) Actionable Mistake Book (orphan/deleted rows already excluded).
    if mistake_summaries:
        take(resolve_practice_entries(mistake_summaries, store.all()))
        if len(chosen) >= limit:
            return chosen[:limit]

    # C) Weakest practiced vocabulary.
    take(store.entries_for_keys(progress.weakest_words(limit * 4)))
    if len(chosen) >= limit:
        return chosen[:limit]

    # D) Stable fill: remaining vocab ordered by word then id.
    pool = list(store.all())
    pool.sort(
        key=lambda e: (
            normalize(entry_word(e)),
            entry_id(e) or "",
        )
    )
    take(pool)
    return chosen[:limit]


def _target_identity(entries: Sequence[Mapping[str, Any]]) -> str:
    parts = []
    for entry in entries:
        vid = entry_id(entry) or ""
        word = normalize(entry_word(entry))
        meaning = normalize(entry_meaning(entry))
        parts.append(f"{vid}:{word}:{meaning}")
    return "|".join(sorted(parts))


def listening_cache_key(
    *,
    language_code: str,
    native_code: str,
    level: str,
    entries: Sequence[Mapping[str, Any]],
    day: Optional[str] = None,
) -> str:
    """Cache filename distinguishing language/native/level/targets/day/schema."""
    day_key = day or today_key()
    raw = "|".join(
        [
            str(language_code or "").strip().lower(),
            str(native_code or "").strip().lower(),
            str(level or "").strip().upper(),
            _target_identity(entries),
            day_key,
            f"v{LISTENING_CONTENT_SCHEMA_VERSION}",
        ]
    )
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    return f"listening_{day_key}_{digest}.json"


def load_listening_cache(
    *,
    language_code: str,
    native_code: str,
    level: str,
    entries: Sequence[Mapping[str, Any]],
) -> Optional[ListeningItem]:
    path = os.path.join(
        config.cache_dir(language_code),
        listening_cache_key(
            language_code=language_code,
            native_code=native_code,
            level=level,
            entries=entries,
        ),
    )
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return normalize_listening_item(data)
    except (OSError, json.JSONDecodeError, ListeningContentError, TypeError, ValueError):
        return None


def save_listening_cache(
    item: ListeningItem,
    *,
    language_code: str,
    native_code: str,
    level: str,
    entries: Sequence[Mapping[str, Any]],
) -> None:
    directory = config.cache_dir(language_code)
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(
        directory,
        listening_cache_key(
            language_code=language_code,
            native_code=native_code,
            level=level,
            entries=entries,
        ),
    )
    payload = listening_item_as_dict(item)
    try:
        fd, tmp = tempfile.mkstemp(prefix="listening_", suffix=".json", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except OSError as error:
        print("Không lưu được cache Listening:", error)


def bundled_listening_item(
    language_code: str, *, native_code: str = None
) -> Optional[ListeningItem]:
    """Study-language-first bundled sample for the requested language."""
    items = sample_listening_items(language_code, native_code=native_code)
    return items[0] if items else None


def build_listening_item(
    store,
    progress,
    *,
    language_code: str,
    native_code: str = None,
    native_label: str = None,
    level: str = None,
    mistake_summaries: Optional[Sequence[MistakeSummary]] = None,
    force_new: bool = False,
    generate: Optional[Callable[..., ListeningItem]] = None,
) -> ListeningItem:
    """Resolve one ListeningItem: cache → AI → bundled sample.

    Blocking — call via ui_common.run_async from Tk. Never writes Progress/SRS.
    """
    code = str(language_code or "").strip().lower()
    native = str(native_code or config.native_code()).strip().lower()
    label = native_label or config.native_label()
    cefr = str(level or config.READING_LEVEL).strip().upper()
    entries = select_listening_targets(
        store,
        progress,
        language_code=code,
        mistake_summaries=mistake_summaries,
    )

    if entries and not force_new:
        cached = load_listening_cache(
            language_code=code,
            native_code=native,
            level=cefr,
            entries=entries,
        )
        if cached is not None:
            return cached

    generate_fn = generate
    if generate_fn is None and entries and ai_teacher.is_configured():

        def generate_fn(target_entries, **kwargs):
            return ai_teacher.generate_listening(
                target_entries,
                language_code=kwargs.get("language_code", code),
                native_code=kwargs.get("native_code", native),
                native_label=kwargs.get("native_label", label),
                level=kwargs.get("level", cefr),
            )

    if entries and generate_fn is not None:
        try:
            item = generate_fn(
                entries,
                language_code=code,
                native_code=native,
                native_label=label,
                level=cefr,
            )
            if not isinstance(item, ListeningItem):
                item = normalize_listening_item(item)
            save_listening_cache(
                item,
                language_code=code,
                native_code=native,
                level=cefr,
                entries=entries,
            )
            return item
        except Exception as error:  # noqa: BLE001 - AI/network/validation → fallback
            print(f"[Listening] AI content failed ({error}); trying bundled sample.")

    sample = bundled_listening_item(code, native_code=native)
    if sample is not None:
        return sample

    raise NoListeningAvailable(
        "No Listening content is available for this language."
    )
