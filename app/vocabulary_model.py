"""Canonical vocabulary lexical model (Phase 14 + Phase 15A enrichment).

Persisted fields (vocab.json list items):
  id, word, meaning,
  alternatives?, part_of_speech?, note?,
  examples?, pronunciation?, forms?

Legacy read (never overwrite a non-empty canonical value):
  meaning ← meaning | vi
  word ← word | nl | en
  alternatives ← alternatives | alt
  part_of_speech ← part_of_speech | mapped/preserved type
  examples ← examples | legacy example string

No top-level schema wrapper: field presence is the migration marker.
Stable Phase 13 ``id`` is never regenerated here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from text_utils import entry_word
from vocab_identity import entry_id, is_vocab_id, new_vocab_id

# Controlled POS values we actively recognize when migrating legacy ``type``.
# Unknown legacy values are preserved verbatim (lowercased/stripped) — not discarded.
CANONICAL_POS = frozenset(
    {"noun", "verb", "adjective", "adverb", "phrase", "other"}
)

_TYPE_TO_POS = {
    "noun": "noun",
    "n": "noun",
    "verb": "verb",
    "v": "verb",
    "ww": "verb",  # Dutch tag sometimes used informally
    "adjective": "adjective",
    "adj": "adjective",
    "adverb": "adverb",
    "adv": "adverb",
    "phrase": "phrase",
    "other": "other",
}

FORM_FIELDS = ("plural", "past", "past_participle", "comparative", "superlative")


@dataclass(frozen=True)
class VocabularyExample:
    text: str
    meaning: str = ""

    def to_storage_dict(self) -> dict:
        data = {"text": self.text}
        if self.meaning:
            data["meaning"] = self.meaning
        return data


@dataclass(frozen=True)
class PronunciationInfo:
    ipa: str = ""

    def to_storage_dict(self) -> Optional[dict]:
        if not self.ipa:
            return None
        return {"ipa": self.ipa}


@dataclass(frozen=True)
class GrammaticalForms:
    plural: str = ""
    past: str = ""
    past_participle: str = ""
    comparative: str = ""
    superlative: str = ""

    def to_storage_dict(self) -> Optional[dict]:
        data = {}
        for name in FORM_FIELDS:
            value = str(getattr(self, name) or "").strip()
            if value:
                data[name] = value
        return data or None

    def as_dict(self) -> Dict[str, str]:
        out = {}
        for name in FORM_FIELDS:
            value = str(getattr(self, name) or "").strip()
            if value:
                out[name] = value
        return out


@dataclass(frozen=True)
class VocabularyEntry:
    """Canonical in-memory vocabulary item."""

    id: str
    word: str
    meaning: str
    alternatives: Tuple[str, ...] = ()
    part_of_speech: str = ""
    forms: GrammaticalForms = field(default_factory=GrammaticalForms)
    pronunciation: PronunciationInfo = field(default_factory=PronunciationInfo)
    examples: Tuple[VocabularyExample, ...] = ()
    note: str = ""

    @property
    def example(self) -> str:
        """Compatibility: first example text, if any."""
        return self.examples[0].text if self.examples else ""

    def to_storage_dict(self) -> dict:
        return entry_to_storage_dict(self)


def entry_meaning(entry: Optional[dict]) -> str:
    """Native-language gloss. Canonical ``meaning`` wins over legacy ``vi``."""
    if not isinstance(entry, dict):
        return ""
    meaning = str(entry.get("meaning") or "").strip()
    if meaning:
        return meaning
    return str(entry.get("vi") or "").strip()


def entry_alternatives(entry: Optional[dict]) -> List[str]:
    """Normalized alternative answers as a list of non-empty strings."""
    if not isinstance(entry, dict):
        return []
    if "alternatives" in entry:
        return normalize_alternatives(entry.get("alternatives"))
    return normalize_alternatives(entry.get("alt"))


def entry_examples(entry: Optional[dict]) -> List[VocabularyExample]:
    """Canonical examples; legacy ``example`` string used only when examples absent."""
    if not isinstance(entry, dict):
        return []
    if "examples" in entry:
        return normalize_examples(entry.get("examples"))
    legacy = str(entry.get("example") or "").strip()
    if legacy:
        return [VocabularyExample(text=legacy)]
    return []


def entry_example(entry: Optional[dict]) -> str:
    """First example text (compat for quiz hint / single-string UI)."""
    examples = entry_examples(entry)
    return examples[0].text if examples else ""


def entry_example_texts(entry: Optional[dict]) -> List[str]:
    return [item.text for item in entry_examples(entry)]


def entry_pronunciation(entry: Optional[dict]) -> PronunciationInfo:
    if not isinstance(entry, dict):
        return PronunciationInfo()
    return normalize_pronunciation(entry.get("pronunciation"))


def entry_forms(entry: Optional[dict]) -> GrammaticalForms:
    if not isinstance(entry, dict):
        return GrammaticalForms()
    return normalize_forms(entry.get("forms"))


def entry_note(entry: Optional[dict]) -> str:
    if not isinstance(entry, dict):
        return ""
    return str(entry.get("note") or "").strip()


def entry_part_of_speech(entry: Optional[dict]) -> str:
    if not isinstance(entry, dict):
        return ""
    pos = str(entry.get("part_of_speech") or "").strip()
    if pos:
        return pos
    return normalize_part_of_speech(entry.get("type"))


def normalize_alternatives(value: Any) -> List[str]:
    """Deterministic alternatives list. Accepts list/tuple/str/None/other."""
    if value is None:
        return []
    if isinstance(value, str):
        pieces = [value]
    elif isinstance(value, (list, tuple)):
        pieces = list(value)
    else:
        pieces = [str(value)]
    out: List[str] = []
    seen = set()
    for piece in pieces:
        text = str(piece or "").strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def normalize_examples(value: Any) -> List[VocabularyExample]:
    """Normalize examples list. Preserves order; skips empty texts."""
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [VocabularyExample(text=text)] if text else []
    if not isinstance(value, (list, tuple)):
        return []
    out: List[VocabularyExample] = []
    for item in value:
        if isinstance(item, VocabularyExample):
            if item.text.strip():
                out.append(
                    VocabularyExample(
                        text=item.text.strip(),
                        meaning=str(item.meaning or "").strip(),
                    )
                )
            continue
        if isinstance(item, str):
            text = item.strip()
            if text:
                out.append(VocabularyExample(text=text))
            continue
        if isinstance(item, dict):
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            meaning = str(item.get("meaning") or "").strip()
            out.append(VocabularyExample(text=text, meaning=meaning))
    return out


def normalize_pronunciation(value: Any) -> PronunciationInfo:
    if not isinstance(value, dict):
        return PronunciationInfo()
    ipa = str(value.get("ipa") or "").strip()
    return PronunciationInfo(ipa=ipa)


def normalize_forms(value: Any) -> GrammaticalForms:
    if not isinstance(value, dict):
        return GrammaticalForms()
    kwargs = {}
    for name in FORM_FIELDS:
        kwargs[name] = str(value.get(name) or "").strip()
    return GrammaticalForms(**kwargs)


def normalize_part_of_speech(value: Any) -> str:
    """Map known legacy type labels; preserve unknown non-empty values."""
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    mapped = _TYPE_TO_POS.get(text.casefold())
    if mapped:
        return mapped
    # Preserve unknown legacy categories safely (do not discard).
    return text


def needs_schema_migration(raw: dict) -> bool:
    """True when persisted shape still uses legacy field names / missing meaning."""
    if not isinstance(raw, dict):
        return False
    if raw.get("vi") and not str(raw.get("meaning") or "").strip():
        return True
    if "alt" in raw and "alternatives" not in raw:
        return True
    if raw.get("type") and not str(raw.get("part_of_speech") or "").strip():
        return True
    if ("nl" in raw or "en" in raw) and "word" not in raw:
        return True
    # Legacy single example string → structured examples.
    if "example" in raw:
        return True
    # Empty pronunciation object should be cleaned on rewrite.
    pronunciation = raw.get("pronunciation")
    if isinstance(pronunciation, dict) and not str(pronunciation.get("ipa") or "").strip():
        return True
    # Written with both legacy+canonical leftover keys also cleaned on save.
    if "vi" in raw or "alt" in raw or "type" in raw:
        return True
    return False


def normalize_entry_dict(
    raw: dict,
    *,
    assign_id: bool = True,
) -> Optional[dict]:
    """Parse one raw JSON object into a canonical storage dict.

    Returns None when word or meaning is missing.
    Does not regenerate an existing valid id.
    """
    if not isinstance(raw, dict):
        return None
    word = str(entry_word(raw) or "").strip()
    meaning = entry_meaning(raw)
    if not word or not meaning:
        return None

    vid = entry_id(raw)
    if not vid and assign_id:
        vid = new_vocab_id()

    alternatives = entry_alternatives(raw)
    examples = entry_examples(raw)
    note = entry_note(raw)
    # Canonical POS wins; else migrate/preserve type.
    pos = str(raw.get("part_of_speech") or "").strip()
    if not pos:
        pos = normalize_part_of_speech(raw.get("type"))
    pronunciation = entry_pronunciation(raw)
    forms = entry_forms(raw)

    entry: Dict[str, Any] = {"word": word, "meaning": meaning}
    if vid:
        entry["id"] = vid
    if alternatives:
        entry["alternatives"] = alternatives
    if examples:
        entry["examples"] = [item.to_storage_dict() for item in examples]
    if note:
        entry["note"] = note
    if pos:
        entry["part_of_speech"] = pos
    pronunciation_data = pronunciation.to_storage_dict()
    if pronunciation_data:
        entry["pronunciation"] = pronunciation_data
    forms_data = forms.to_storage_dict()
    if forms_data:
        entry["forms"] = forms_data
    return entry


def entry_to_storage_dict(entry: VocabularyEntry) -> dict:
    data: Dict[str, Any] = {
        "id": entry.id,
        "word": entry.word,
        "meaning": entry.meaning,
    }
    if entry.alternatives:
        data["alternatives"] = list(entry.alternatives)
    if entry.part_of_speech:
        data["part_of_speech"] = entry.part_of_speech
    forms_data = entry.forms.to_storage_dict() if entry.forms else None
    if forms_data:
        data["forms"] = forms_data
    pronunciation_data = (
        entry.pronunciation.to_storage_dict() if entry.pronunciation else None
    )
    if pronunciation_data:
        data["pronunciation"] = pronunciation_data
    if entry.examples:
        data["examples"] = [item.to_storage_dict() for item in entry.examples]
    if entry.note:
        data["note"] = entry.note
    return data


def vocabulary_entry_from_dict(raw: dict) -> Optional[VocabularyEntry]:
    normalized = normalize_entry_dict(raw, assign_id=True)
    if not normalized:
        return None
    return VocabularyEntry(
        id=str(normalized.get("id") or ""),
        word=str(normalized["word"]),
        meaning=str(normalized["meaning"]),
        alternatives=tuple(normalized.get("alternatives") or ()),
        part_of_speech=str(normalized.get("part_of_speech") or ""),
        forms=normalize_forms(normalized.get("forms")),
        pronunciation=normalize_pronunciation(normalized.get("pronunciation")),
        examples=tuple(normalize_examples(normalized.get("examples"))),
        note=str(normalized.get("note") or ""),
    )


def normalize_vocab_list(
    items: Sequence[dict],
    *,
    assign_ids: bool = True,
) -> Tuple[List[dict], bool]:
    """Normalize a vocab.json list. Returns (entries, changed)."""
    result: List[dict] = []
    changed = False
    for item in items or ():
        if not isinstance(item, dict):
            continue
        if needs_schema_migration(item) or (
            assign_ids and not is_vocab_id(item.get("id"))
        ):
            changed = True
        normalized = normalize_entry_dict(item, assign_id=assign_ids)
        if normalized is None:
            continue
        # Detect any field/key differences vs a cleaned view of input.
        if not changed and normalized != _canonical_view(item):
            changed = True
        result.append(normalized)
    return result, changed


def _canonical_view(raw: dict) -> dict:
    """Best-effort canonical snapshot without assigning a new id."""
    return normalize_entry_dict(raw, assign_id=False) or {}


def wire_meaning_as_vi(entries: Iterable[dict]) -> List[dict]:
    """HTTP/AI wire shape still uses ``vi`` for meaning (API unchanged)."""
    out = []
    for item in entries or ():
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "word": str(entry_word(item) or "").strip(),
                "vi": entry_meaning(item),
            }
        )
    return out
