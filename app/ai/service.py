"""AI service: routing between account-server proxy and a concrete AIProvider."""

from __future__ import annotations

from typing import Optional

import config
import languages
from ai.base import (
    AIError,
    AIProvider,
    GradeRequest,
    GradeResult,
    ReadingRequest,
    VocabularyEnrichmentAIRequest,
    VocabularyEnrichmentAIResult,
    sanitize_enrichment_ai_payload,
)
from ai.openai_provider import OpenAIProvider

_service: Optional["AIService"] = None


def _study_language_from_profile(profile: Optional[dict]):
    if isinstance(profile, dict) and profile.get("code"):
        return languages.resolve_language(str(profile["code"]))
    return languages.resolve_language(config.active_code())


class AIService:
    """StudyGuard AI use cases. Inject any AIProvider (OpenAI, fake, future local)."""

    def __init__(self, provider: Optional[AIProvider] = None):
        self._provider = provider

    @property
    def provider(self) -> AIProvider:
        if self._provider is None:
            self._provider = OpenAIProvider()
        return self._provider

    def is_configured(self) -> bool:
        return config.ai_is_configured()

    def grade_answer(
        self,
        target_word: str,
        user_sentence: str,
        meaning: str = "",
        profile: dict = None,
        native_label: str = None,
        level: str = None,
        *,
        use_account_proxy: bool = True,
    ) -> GradeResult:
        # Desktop + token: proxy qua account server (key không vào exe).
        if use_account_proxy and config.uses_account_server() and profile is None:
            import account_client

            try:
                data = account_client.grade_sentence(target_word, user_sentence, meaning)
            except account_client.AccountError as error:
                raise AIError(str(error)) from error
            return GradeResult(
                is_correct_usage=bool(data.get("is_correct_usage")),
                score=float(data.get("score") or 0.0),
                feedback_vi=str(data.get("feedback_vi") or "").strip(),
                corrected_sentence=str(data.get("corrected_sentence") or "").strip(),
                suggested_sentence=str(data.get("suggested_sentence") or "").strip(),
            )

        request = GradeRequest(
            target_word=target_word,
            user_sentence=user_sentence,
            meaning=meaning or "",
            study_language=_study_language_from_profile(profile),
            native_label=native_label or config.native_label(),
            level=level or config.READING_LEVEL,
        )
        return self.provider.grade_answer(request)

    def generate_reading(
        self,
        entries: list,
        level: str = None,
        passage_words: int = None,
        profile: dict = None,
        native_label: str = None,
        *,
        use_account_proxy: bool = True,
    ) -> dict:
        if use_account_proxy and config.uses_account_server() and profile is None:
            import account_client

            try:
                return account_client.generate_reading(entries)
            except account_client.AccountError as error:
                raise AIError(str(error)) from error

        request = ReadingRequest(
            entries=list(entries or []),
            study_language=_study_language_from_profile(profile),
            native_label=native_label or config.native_label(),
            level=(level or config.READING_LEVEL),
            passage_words=passage_words or config.READING_PASSAGE_WORDS,
        )
        return self.provider.generate_reading(request)

    def enrich_vocabulary(
        self,
        word: str,
        meaning: str,
        part_of_speech: str = "",
        profile: dict = None,
        native_label: str = None,
        *,
        use_account_proxy: bool = True,
    ) -> VocabularyEnrichmentAIResult:
        """Propose enrichment only. Never writes vocab.json."""
        if use_account_proxy and config.uses_account_server() and profile is None:
            import account_client

            try:
                data = account_client.enrich_vocabulary(
                    word, meaning, part_of_speech=part_of_speech
                )
            except account_client.AccountError as error:
                raise AIError(str(error)) from error
            return sanitize_enrichment_ai_payload(data)

        request = VocabularyEnrichmentAIRequest(
            word=word,
            meaning=meaning or "",
            study_language=_study_language_from_profile(profile),
            native_label=native_label or config.native_label(),
            part_of_speech=part_of_speech or "",
        )
        return self.provider.enrich_vocabulary(request)


def get_service() -> AIService:
    global _service
    if _service is None:
        _service = AIService()
    return _service


def set_service(service: Optional[AIService]) -> None:
    """Test/DI hook. Pass None to restore default lazy construction."""
    global _service
    _service = service
