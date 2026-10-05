"""Canonical Listening content validation (Phase 17C).

AI/server/cache output is untrusted. One normalization boundary for all paths.
"""

from __future__ import annotations

from typing import Any, List, Mapping, Optional, Sequence, Tuple

from listening import ListeningItem

LISTENING_CONTENT_SCHEMA_VERSION = 1

_MAX_TEXT = 320
_MAX_QUESTION = 200
_MAX_ANSWER = 100
_MAX_MEANING = 320
_MAX_ALT = 5
_MAX_ALT_LEN = 100


class ListeningContentError(ValueError):
    """Invalid Listening content — must not reach ListeningSession."""


def fold_listening_text(value: str) -> str:
    """Case/whitespace fold for grounded-answer checks (not full vocab normalize)."""
    return " ".join(str(value or "").casefold().split())


def answer_grounded_in_text(answer: str, text: str) -> bool:
    """True when the expected answer appears as a phrase in the transcript."""
    needle = fold_listening_text(answer)
    haystack = fold_listening_text(text)
    return bool(needle) and needle in haystack


def question_leaks_answer(question: str, answer: str) -> bool:
    """True when the question already contains the answer phrase (trivial listening)."""
    needle = fold_listening_text(answer)
    haystack = fold_listening_text(question)
    return bool(needle) and needle in haystack


def _require_str(data: Mapping[str, Any], key: str, *, max_len: int) -> str:
    if key not in data:
        raise ListeningContentError(f"Missing Listening field: {key}")
    raw = data.get(key)
    # Required fields must be real strings — do not coerce int/float.
    if not isinstance(raw, str):
        raise ListeningContentError(f"Listening field {key} must be text.")
    text = raw.strip()
    if not text:
        raise ListeningContentError(f"Listening field {key} is empty.")
    if len(text) > max_len:
        raise ListeningContentError(f"Listening field {key} is too long.")
    return text


def _normalize_alternatives(raw: Any, *, answer: str, text: str) -> Tuple[str, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, (list, tuple)):
        raise ListeningContentError("Listening alternatives must be a list.")
    seen = {fold_listening_text(answer)}
    out: List[str] = []
    for item in raw:
        # Policy: non-string alternative entries are ignored (not coerced).
        if not isinstance(item, str):
            continue
        value = item.strip()
        if not value or len(value) > _MAX_ALT_LEN:
            continue
        key = fold_listening_text(value)
        if not key or key in seen:
            continue
        # Prefer grounded alternatives; skip ungrounded noise.
        if not answer_grounded_in_text(value, text):
            continue
        seen.add(key)
        out.append(value)
        if len(out) >= _MAX_ALT:
            break
    return tuple(out)


def normalize_listening_item(data: Any) -> ListeningItem:
    """Validate untrusted payload into a frozen ListeningItem.

    Rejects non-objects, missing fields, non-string required fields, oversized
    fields, and answers that are not grounded in the spoken transcript.
    Alternatives: list/tuple only; non-string entries ignored; max 5 grounded.
    """
    if not isinstance(data, dict):
        raise ListeningContentError("Listening content must be a JSON object.")

    text = _require_str(data, "text", max_len=_MAX_TEXT)
    question = _require_str(data, "question", max_len=_MAX_QUESTION)
    answer = _require_str(data, "answer", max_len=_MAX_ANSWER)
    meaning = _require_str(data, "meaning", max_len=_MAX_MEANING)

    if not answer_grounded_in_text(answer, text):
        raise ListeningContentError(
            "Listening answer must appear as a phrase in the spoken text."
        )
    if question_leaks_answer(question, answer):
        raise ListeningContentError(
            "Listening question must not contain the expected answer phrase."
        )

    alternatives = _normalize_alternatives(
        data.get("alternatives"), answer=answer, text=text
    )
    return ListeningItem(
        text=text,
        question=question,
        answer=answer,
        alternatives=alternatives,
        meaning=meaning,
    )


def listening_item_as_dict(item: ListeningItem) -> dict:
    """Canonical JSON shape for cache / account-server wire."""
    return {
        "text": item.text,
        "question": item.question,
        "answer": item.answer,
        "alternatives": list(item.alternatives or ()),
        "meaning": item.meaning,
        "schema_version": LISTENING_CONTENT_SCHEMA_VERSION,
    }
