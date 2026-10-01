"""AI provider package — StudyGuard use cases, not generic LLM plumbing."""

from ai.base import (
    AIError,
    AIProvider,
    GradeRequest,
    GradeResult,
    ReadingRequest,
)
from ai.service import AIService, get_service, set_service

__all__ = [
    "AIError",
    "AIProvider",
    "AIService",
    "GradeRequest",
    "GradeResult",
    "ReadingRequest",
    "get_service",
    "set_service",
]
