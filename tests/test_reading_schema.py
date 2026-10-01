"""Reading payload normalization — no AI calls."""

from reading_schema import count_questions, normalize_test


def test_normalize_skips_unsupported_and_counts():
    raw = {
        "title": "Op de markt",
        "passage": "Ik ga elke zaterdag naar de markt.\n\nDe markt is altijd druk.",
        "question_groups": [
            {
                "type": "multiple_choice_single",
                "instructions": "Chọn đáp án đúng.",
                "questions": [
                    {
                        "number": 1,
                        "prompt": "Wanneer gaat hij naar de markt?",
                        "options": [
                            {"key": "A", "text": "Op maandag"},
                            {"key": "B", "text": "Op zaterdag"},
                        ],
                        "answer": "B",
                        "explanation_vi": "Câu đầu tiên nói rõ 'elke zaterdag'.",
                    }
                ],
            },
            {
                "type": "true_false_notgiven",
                "questions": [{"number": 2, "prompt": "De markt is rustig.", "answer": "FALSE"}],
            },
            {
                "type": "vocab_matching",
                "prompts": [{"number": 3, "text": "druk"}],
                "options": [{"code": "A", "text": "bận rộn"}, {"code": "B", "text": "rẻ"}],
                "answers": ["A"],
            },
            {"type": "khong_ho_tro", "questions": []},
        ],
    }
    test = normalize_test(raw)
    assert len(test["groups"]) == 3
    assert count_questions(test) == 3
    assert len(test["groups"][1]["questions"][0]["options"]) == 3
    assert test["groups"][0]["questions"][0]["explanation"].startswith("Câu đầu")


def test_legacy_matching_heading():
    legacy = {
        "passage": "x",
        "question_groups": [
            {
                "type": "matching_heading",
                "sections": ["Section A", "Section B"],
                "headings": [
                    {"code": "i", "text": "Eerste"},
                    {"code": "ii", "text": "Tweede"},
                ],
                "answers": ["ii", "i"],
                "number_range": [5, 6],
            }
        ],
    }
    legacy_test = normalize_test(legacy)
    assert legacy_test["groups"][0]["kind"] == "matching"
    assert legacy_test["groups"][0]["prompts"][0]["number"] == 5
