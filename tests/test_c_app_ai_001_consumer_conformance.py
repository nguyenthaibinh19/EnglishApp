"""C-APP-AI-001 App consumer conformance (test-only; no LocalAIProvider).

Validates synthetic Local AI wire fixtures with real EnglishApp normalizers.
Does not call Ollama, does not change production routing, and does not merge.
"""

from __future__ import annotations

import pytest

import config
from ai.base import AIError, sanitize_enrichment_ai_payload
from ai.service import AIService
from listening_content import ListeningContentError, normalize_listening_item
from reading_schema import normalize_test
from tests.c_app_ai_001_support import (
    MINIMUM_LOCAL_AI_INFERENCE_TIMEOUT_SEC,
    RECOMMENDED_LOCAL_AI_INFERENCE_TIMEOUT_SEC,
    load_fixture,
    map_local_ai_http_error,
    recommended_local_timeout_sec,
    validate_grade_wire_payload,
)
from tests.test_ai_service import FakeProvider


# ---------------------------------------------------------------------------
# Positive: four capabilities against App validators
# ---------------------------------------------------------------------------


def test_grade_fixture_passes_consumer_validation():
    payload = load_fixture("grade_ok.json")
    result = validate_grade_wire_payload(payload)
    assert result.is_correct_usage is True
    assert 0.0 <= result.score <= 1.0
    assert result.feedback_vi
    assert result.corrected_sentence
    assert result.suggested_sentence


def test_reading_fixture_passes_normalize_test():
    payload = load_fixture("reading_ok.json")
    normalized = normalize_test(payload)
    assert normalized["passage"]
    assert normalized["groups"]
    kinds = {group["kind"] for group in normalized["groups"]}
    assert "choice" in kinds
    assert "matching" in kinds
    # Unsupported groups are skipped; fixture uses only supported types.
    assert all(group["kind"] in {"choice", "matching"} for group in normalized["groups"])


def test_listening_fixture_passes_normalize_listening_item():
    payload = load_fixture("listening_ok.json")
    item = normalize_listening_item(payload)
    assert item.answer == "at nine"
    assert "nine" in item.text.lower()


def test_enrich_fixture_passes_sanitize_enrichment_ai_payload():
    payload = load_fixture("enrich_ok.json")
    result = sanitize_enrichment_ai_payload(payload)
    assert result.part_of_speech == "noun"
    assert result.forms.get("plural") == "trains"
    assert result.examples
    assert "ipa" not in result.as_dict()


# ---------------------------------------------------------------------------
# Negative: malformed / unsafe Local AI outputs
# ---------------------------------------------------------------------------


def test_reading_unsupported_question_group_is_skipped_and_may_fail_closed():
    payload = load_fixture("reading_ok.json")
    payload = dict(payload)
    payload["question_groups"] = [
        {
            "type": "fill_in_the_blank",
            "questions": [{"prompt": "x", "answer": "y"}],
        }
    ]
    with pytest.raises(ValueError, match="nhóm câu hỏi"):
        normalize_test(payload)


def test_reading_malformed_answers_drop_invalid_choice_group():
    payload = load_fixture("reading_ok.json")
    payload = dict(payload)
    payload["question_groups"] = [
        {
            "type": "multiple_choice_single",
            "questions": [
                {
                    "prompt": "Missing answer and options",
                    "options": [],
                    "answer": "",
                }
            ],
        }
    ]
    with pytest.raises(ValueError, match="nhóm câu hỏi"):
        normalize_test(payload)


def test_listening_answer_leakage_rejected():
    payload = load_fixture("listening_ok.json")
    payload = dict(payload)
    payload["question"] = "Does the train leave at nine?"
    with pytest.raises(ListeningContentError, match="must not contain"):
        normalize_listening_item(payload)


def test_listening_ungrounded_answer_rejected():
    payload = load_fixture("listening_ok.json")
    payload = dict(payload)
    payload["answer"] = "tomorrow morning"
    with pytest.raises(ListeningContentError, match="phrase in the spoken text"):
        normalize_listening_item(payload)


@pytest.mark.parametrize(
    "score",
    [1.5, -0.1, float("nan"), float("inf"), "not-a-number", None],
)
def test_grade_invalid_scores_rejected_by_consumer_validator(score):
    payload = dict(load_fixture("grade_ok.json"))
    payload["score"] = score
    with pytest.raises(AIError):
        validate_grade_wire_payload(payload)


def test_current_openai_grade_path_coerces_out_of_range_score_mismatch(monkeypatch):
    """Documented wire mismatch: production OpenAI path does not fail-closed on score."""
    from ai.openai_provider import OpenAIProvider

    provider = OpenAIProvider(api_key="sk-test")
    monkeypatch.setattr(
        provider,
        "_chat_json",
        lambda *a, **k: {
            "is_correct_usage": True,
            "score": 9.9,
            "feedback_vi": "ok",
            "corrected_sentence": "x",
            "suggested_sentence": "y",
        },
    )
    from ai.base import GradeRequest
    import languages

    result = provider.grade_answer(
        GradeRequest(
            target_word="train",
            user_sentence="The train leaves.",
            meaning="tau",
            study_language=languages.resolve_language("en"),
            native_label="Vietnamese",
            level="A2",
        )
    )
    assert result.score == 9.9
    with pytest.raises(AIError):
        validate_grade_wire_payload(
            {
                "is_correct_usage": True,
                "score": 9.9,
                "feedback_vi": "ok",
                "corrected_sentence": "x",
                "suggested_sentence": "y",
            }
        )


def test_enrich_non_object_rejected():
    with pytest.raises(AIError, match="JSON object"):
        sanitize_enrichment_ai_payload(["not", "an", "object"])


def test_malformed_http_json_envelope_maps_to_aierror():
    err = map_local_ai_http_error(
        502,
        {"error": {"code": "local_ai_error", "message": "bad json", "status": 502}},
    )
    assert isinstance(err, AIError)
    assert "invalid" in str(err).lower() or "incomplete" in str(err).lower()
    assert "bad json" not in str(err)


def test_unavailable_local_runtime_maps_to_aierror():
    err = map_local_ai_http_error(503, unavailable=True)
    assert isinstance(err, AIError)
    assert "unavailable" in str(err).lower()


@pytest.mark.parametrize(
    "status,needle",
    [
        (401, "authorization"),
        (403, "security"),
        (413, "too large"),
        (415, "application/json"),
        (422, "validation"),
        (400, "malformed"),
    ],
)
def test_security_and_validation_http_statuses_map_to_aierror(status, needle):
    err = map_local_ai_http_error(status, {"error": {"code": "x", "status": status}})
    assert isinstance(err, AIError)
    assert needle in str(err).lower()


# ---------------------------------------------------------------------------
# Routing: account-proxy precedence bypasses injected provider
# ---------------------------------------------------------------------------


def test_account_proxy_bypasses_injected_provider_when_profile_is_none(monkeypatch):
    fake = FakeProvider()
    service = AIService(provider=fake)

    monkeypatch.setattr(config, "uses_account_server", lambda: True)

    calls = {"grade": 0}

    class FakeAccountClient:
        class AccountError(Exception):
            pass

        @staticmethod
        def grade_sentence(target_word, user_sentence, meaning=""):
            calls["grade"] += 1
            return {
                "is_correct_usage": True,
                "score": 0.5,
                "feedback_vi": "proxy",
                "corrected_sentence": user_sentence,
                "suggested_sentence": user_sentence,
            }

    import sys

    monkeypatch.setitem(sys.modules, "account_client", FakeAccountClient)

    result = service.grade_answer("train", "The train leaves.", "tau")
    assert result.feedback_vi == "proxy"
    assert calls["grade"] == 1
    assert fake.grade_calls == []

    # Smallest safe future routing change (documented by this assertion):
    # local mode must either set use_account_proxy=False or supply a non-None
    # profile so the injected LocalAIProvider is reachable.
    local = service.grade_answer(
        "train",
        "The train leaves.",
        "tau",
        profile={"code": "en"},
        use_account_proxy=False,
    )
    assert fake.grade_calls
    assert local.feedback_vi.startswith("ok:")


def test_fake_reading_without_question_groups_fails_app_normalize():
    """Existing FakeProvider reading shape is not App-normalizable (wire mismatch)."""
    from ai.base import ReadingRequest

    fake = FakeProvider()
    raw = fake.generate_reading(
        ReadingRequest(
            entries=[{"word": "train", "meaning": "tau"}],
            level="A2",
        )
    )
    assert raw.get("groups") == []
    with pytest.raises(ValueError):
        normalize_test(raw)


# ---------------------------------------------------------------------------
# Timeout recommendation
# ---------------------------------------------------------------------------


def test_recommended_timeout_exceeds_observed_cold_start():
    value = recommended_local_timeout_sec()
    assert value == RECOMMENDED_LOCAL_AI_INFERENCE_TIMEOUT_SEC
    assert value > 18.83
    assert value >= MINIMUM_LOCAL_AI_INFERENCE_TIMEOUT_SEC
    with pytest.raises(ValueError):
        recommended_local_timeout_sec(10.0)
    # Existing cloud timeout remains independently high enough.
    assert float(config.OPENAI_TIMEOUT) >= 18.83
