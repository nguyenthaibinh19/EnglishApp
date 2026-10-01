"""AI provider boundary: StudyGuard use cases only."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence

from languages import StudyLanguage


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


class AIProvider(ABC):
    """Capability interface for StudyGuard — not a generic chat API."""

    @abstractmethod
    def grade_answer(self, request: GradeRequest) -> GradeResult:
        raise NotImplementedError

    @abstractmethod
    def generate_reading(self, request: ReadingRequest) -> dict:
        """Trả về dict bài đọc đã chuẩn hóa (schema hiện tại của app)."""
        raise NotImplementedError
