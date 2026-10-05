"""AI provider boundary: StudyGuard use cases only."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from languages import StudyLanguage

# Keep in sync with vocabulary_model FORM_FIELDS / CANONICAL_POS (validated again there).
_ENRICHMENT_FORM_KEYS = (
    "plural",
    "past",
    "past_participle",
    "comparative",
    "superlative",
)
_ENRICHMENT_POS = frozenset(
    {"noun", "verb", "adjective", "adverb", "phrase", "other"}
)
_MAX_ENRICHMENT_EXAMPLES = 2
_MAX_ENRICHMENT_FORM_LEN = 80
_MAX_ENRICHMENT_EXAMPLE_LEN = 240
_MAX_ENRICHMENT_POS_LEN = 40


class AIError(RuntimeError):
    """Lỗi AI đã diễn giải; UI/business không thấy SDK exception."""


@dataclass(frozen=True)
class GradeRequest:
    target_word: str
    user_sentence: str
    meaning: str = ""
    study_language: Optional[StudyLanguage] = None
    native_label: str = ""
    level: str = ""


@dataclass(frozen=True)
class GradeResult:
    is_correct_usage: bool
    score: float
    feedback_vi: str
    corrected_sentence: str
    suggested_sentence: str

    def as_dict(self) -> dict:
        return {
            "is_correct_usage": self.is_correct_usage,
            "score": self.score,
            "feedback_vi": self.feedback_vi,
            "corrected_sentence": self.corrected_sentence,
            "suggested_sentence": self.suggested_sentence,
        }


@dataclass
class ReadingRequest:
    entries: Sequence[Mapping[str, Any]] = field(default_factory=list)
    study_language: Optional[StudyLanguage] = None
    native_label: str = ""
    level: str = ""
    passage_words: int = 0


@dataclass(frozen=True)
class ListeningRequest:
    """AI Listening generation — StudyGuard supplies targets; AI only writes content."""

    entries: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    study_language: Optional[StudyLanguage] = None
    native_label: str = ""
    native_code: str = ""
    level: str = ""


@dataclass(frozen=True)
class VocabularyEnrichmentAIRequest:
    """Lexical-only enrichment request — no learning history."""

    word: str
    meaning: str
    study_language: Optional[StudyLanguage] = None
    native_label: str = ""
    part_of_speech: str = ""


@dataclass(frozen=True)
class VocabularyEnrichmentAIResult:
    """Validated AI enrichment payload (POS / forms / examples only; no IPA)."""

    part_of_speech: str = ""
    forms: Mapping[str, str] = field(default_factory=dict)
    examples: Tuple[Mapping[str, str], ...] = ()

    def as_dict(self) -> dict:
        data: Dict[str, Any] = {}
        if self.part_of_speech:
            data["part_of_speech"] = self.part_of_speech
        if self.forms:
            data["forms"] = dict(self.forms)
        if self.examples:
            examples: List[dict] = []
            for item in self.examples:
                row = {"text": item["text"]}
                if item.get("meaning"):
                    row["meaning"] = item["meaning"]
                examples.append(row)
            data["examples"] = examples
        return data

    def is_empty(self) -> bool:
        return not self.part_of_speech and not self.forms and not self.examples


def sanitize_enrichment_ai_payload(data: Any) -> VocabularyEnrichmentAIResult:
    """Validate untrusted model/API JSON into the Phase 15C enrichment contract.

    Rejects non-objects. Omits unsupported POS / unknown form keys / bad examples.
    Never passes through IPA or other out-of-scope fields.
    """
    if not isinstance(data, dict):
        raise AIError("AI enrichment response must be a JSON object.")

    pos = ""
    raw_pos = data.get("part_of_speech")
    if raw_pos is not None and not isinstance(raw_pos, (str, int, float)):
        raw_pos = None
    if raw_pos is not None:
        text = str(raw_pos).strip()[:_MAX_ENRICHMENT_POS_LEN]
        # Local import keeps AI base usable even if vocabulary_model is unavailable.
        try:
            from vocabulary_model import normalize_part_of_speech

            text = normalize_part_of_speech(text)
        except Exception:  # noqa: BLE001 - best-effort normalize
            text = text.strip().lower()
        if text in _ENRICHMENT_POS:
            pos = text

    forms: Dict[str, str] = {}
    raw_forms = data.get("forms")
    if isinstance(raw_forms, dict):
        for key in _ENRICHMENT_FORM_KEYS:
            if key not in raw_forms:
                continue
            value = raw_forms.get(key)
            if not isinstance(value, (str, int, float)):
                continue
            text = str(value).strip()[:_MAX_ENRICHMENT_FORM_LEN]
            if text:
                forms[key] = text

    examples: List[Dict[str, str]] = []
    raw_examples = data.get("examples")
    if isinstance(raw_examples, list):
        for item in raw_examples:
            if len(examples) >= _MAX_ENRICHMENT_EXAMPLES:
                break
            if isinstance(item, str):
                text = item.strip()[:_MAX_ENRICHMENT_EXAMPLE_LEN]
                if text:
                    examples.append({"text": text})
                continue
            if not isinstance(item, dict):
                continue
            text = str(item.get("text") or "").strip()[:_MAX_ENRICHMENT_EXAMPLE_LEN]
            if not text:
                continue
            meaning = str(item.get("meaning") or "").strip()[:_MAX_ENRICHMENT_EXAMPLE_LEN]
            row = {"text": text}
            if meaning:
                row["meaning"] = meaning
            examples.append(row)

    return VocabularyEnrichmentAIResult(
        part_of_speech=pos,
        forms=forms,
        examples=tuple(examples),
    )


class AIProvider(ABC):
    """Capability interface for StudyGuard — not a generic chat API."""

    @abstractmethod
    def grade_answer(self, request: GradeRequest) -> GradeResult:
        raise NotImplementedError

    @abstractmethod
    def generate_reading(self, request: ReadingRequest) -> dict:
        """Trả về dict bài đọc đã chuẩn hóa (schema hiện tại của app)."""
        raise NotImplementedError

    @abstractmethod
    def generate_listening(self, request: ListeningRequest):
        """Return a validated ListeningItem (study-language-first content)."""
        raise NotImplementedError

    @abstractmethod
    def enrich_vocabulary(
        self, request: VocabularyEnrichmentAIRequest
    ) -> VocabularyEnrichmentAIResult:
        """Propose POS / forms / examples only. Never mutates vocabulary storage."""
        raise NotImplementedError
