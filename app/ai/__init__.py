"""AI provider package — StudyGuard use cases, not generic LLM plumbing."""

from ai.base import (
    AIError,
    AIProvider,
    GradeRequest,
    GradeResult,
    ListeningRequest,
    ReadingRequest,
    VocabularyEnrichmentAIRequest,
    VocabularyEnrichmentAIResult,
)
from ai.service import AIService, get_service, set_service

__all__ = [
    "AIError",
    "AIProvider",
    "AIService",
    "GradeRequest",
    "GradeResult",
    "ListeningRequest",
    "ReadingRequest",
    "VocabularyEnrichmentAIRequest",
    "VocabularyEnrichmentAIResult",
    "get_service",
    "set_service",
]
