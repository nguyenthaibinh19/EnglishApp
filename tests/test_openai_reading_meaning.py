"""Direct-dev OpenAI Reading prompt uses canonical vocabulary meaning — no network."""

from __future__ import annotations

from ai.base import ReadingRequest
from ai.openai_provider import OpenAIProvider
from languages import get_language


def _valid_reading_payload() -> dict:
    return {
        "title": "Test",
        "level": "A2",
        "passage": "Ik woon in een klein huis.",
        "translation_vi": "I live in a small house.",
        "glossary": [],
        "question_groups": [
            {
                "type": "multiple_choice_single",
                "instructions": "Choose.",
                "questions": [
                    {
                        "number": 1,
                        "prompt": "Where?",
                        "options": [
                            {"key": "A", "text": "huis"},
                            {"key": "B", "text": "auto"},
                        ],
                        "answer": "A",
                        "explanation_vi": "ok",
                    }
                ],
            }
        ],
    }


def test_generate_reading_uses_canonical_meaning_not_missing_vi():
    provider = OpenAIProvider()
    captured = {}

    def fake_chat(system_prompt, user_prompt, temperature=0.5):
        captured["user"] = user_prompt
        return _valid_reading_payload()

    provider._chat_json = fake_chat  # type: ignore[method-assign]
    result = provider.generate_reading(
        ReadingRequest(
            entries=[{"word": "het huis", "meaning": "the house"}],
            study_language=get_language("nl"),
            native_label="English",
            level="A2",
            passage_words=80,
        )
    )
    assert "the house" in captured["user"]
    assert "het huis" in captured["user"]
    # Must not look like an empty gloss after '=' when only meaning is present.
    assert "= the house" in captured["user"]
    assert result["source"] == "ai"


def test_generate_reading_falls_back_to_legacy_vi():
    provider = OpenAIProvider()
    captured = {}

    def fake_chat(system_prompt, user_prompt, temperature=0.5):
        captured["user"] = user_prompt
        return _valid_reading_payload()

    provider._chat_json = fake_chat  # type: ignore[method-assign]
    provider.generate_reading(
        ReadingRequest(
            entries=[{"word": "fiets", "vi": "bicycle"}],
            study_language=get_language("nl"),
            native_label="English",
            level="A2",
            passage_words=80,
        )
    )
    assert "bicycle" in captured["user"]
