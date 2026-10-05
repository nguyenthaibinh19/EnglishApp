"""AI service/provider boundary with a fake provider — no network."""

import ai_teacher
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
from ai.service import AIService, set_service


class FakeProvider(AIProvider):
    def __init__(self):
        self.grade_calls = []
        self.reading_calls = []
        self.listening_calls = []
        self.enrich_calls = []

    def grade_answer(self, request: GradeRequest) -> GradeResult:
        self.grade_calls.append(request)
        return GradeResult(
            is_correct_usage=True,
            score=0.9,
            feedback_vi=f"ok:{request.study_language.code}",
            corrected_sentence=request.user_sentence,
            suggested_sentence="sample",
        )

    def generate_reading(self, request: ReadingRequest) -> dict:
        self.reading_calls.append(request)
        return {
            "title": "Fake",
            "level": request.level,
            "passage": "Hallo.",
            "source": "ai",
            "target_words": ["hallo"],
            "groups": [],
        }

    def generate_listening(self, request: ListeningRequest):
        from listening import ListeningItem

        self.listening_calls.append(request)
        return ListeningItem(
            text="The train leaves at nine.",
            question="What time does the train leave?",
            answer="at nine",
            alternatives=("nine",),
            meaning="Meaning in native language.",
        )

    def enrich_vocabulary(
        self, request: VocabularyEnrichmentAIRequest
    ) -> VocabularyEnrichmentAIResult:
        self.enrich_calls.append(request)
        return VocabularyEnrichmentAIResult(
            part_of_speech="noun",
            forms={"plural": f"{request.word}s"},
            examples=(
                {
                    "text": f"Example with {request.word}.",
                    "meaning": request.meaning,
                },
            ),
        )


def test_grading_and_reading_via_fake_provider():
    fake = FakeProvider()
    set_service(AIService(provider=fake))
    try:
        graded = ai_teacher.check_sentence(
            "fiets",
            "Ik heb een fiets.",
            "xe đạp",
            profile={
                "code": "nl",
                "name_en": "Dutch",
                "name_vi": "tiếng Hà Lan",
                "articles": (),
                "elisions": (),
            },
            native_label="Tiếng Việt",
            level="A2",
        )
        assert graded["is_correct_usage"] is True
        assert graded["feedback_vi"].startswith("ok:")
        assert fake.grade_calls[0].study_language.code == "nl"
        assert fake.grade_calls[0].user_sentence == "Ik heb een fiets."

        reading = ai_teacher.generate_reading(
            [{"word": "hallo", "vi": "xin chào"}],
            profile={"code": "de"},
            native_label="English",
            level="A2",
            passage_words=80,
        )
        assert reading.get("source") == "ai"
        assert fake.reading_calls[0].study_language.code == "de"
        assert ai_teacher.AITeacherError is AIError
    finally:
        set_service(None)
