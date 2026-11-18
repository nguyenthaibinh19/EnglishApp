"""Test-only helpers for C-APP-AI-001 App consumer conformance.

Does not implement LocalAIProvider. Does not change production routing.
Fixtures and helpers are privacy-safe synthetic data shaped for App validators.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping

from ai.base import AIError, GradeResult

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "c_app_ai_001"

# Cold grading was reported at 18.83s. Future local inference timeout must
# exceed that with margin; keep cloud OPENAI_TIMEOUT separate.
RECOMMENDED_LOCAL_AI_INFERENCE_TIMEOUT_SEC = 45.0
MINIMUM_LOCAL_AI_INFERENCE_TIMEOUT_SEC = 25.0

# Proposed env knobs for a future LocalAIProvider (not wired into config.py).
PROPOSED_TIMEOUT_ENV = "LOCAL_AI_INFERENCE_TIMEOUT"
PROPOSED_BASE_URL_ENV = "LOCAL_AI_BASE_URL"


def load_fixture(name: str) -> Any:
    path = FIXTURES / name
    return json.loads(path.read_text(encoding="utf-8"))


def validate_grade_wire_payload(data: Any) -> GradeResult:
    """Recommended App consumer validation for /api/v1/grade responses.

    Stronger than today's OpenAIProvider path, which coerces score with
    ``float(data.get("score") or 0.0)`` and does not reject NaN/inf/OOR.
    Future LocalAIProvider should use this (or equivalent) fail-closed check.
    """
    if not isinstance(data, dict):
        raise AIError("Local AI grade response must be a JSON object.")
    required = (
        "is_correct_usage",
        "score",
        "feedback_vi",
        "corrected_sentence",
        "suggested_sentence",
    )
    for key in required:
        if key not in data:
            raise AIError(f"Local AI grade response missing field: {key}")
    score_raw = data.get("score")
    try:
        score = float(score_raw)
    except (TypeError, ValueError) as exc:
        raise AIError("Local AI grade score must be a finite number.") from exc
    if not math.isfinite(score) or score < 0.0 or score > 1.0:
        raise AIError("Local AI grade score must be finite and within [0.0, 1.0].")
    feedback = str(data.get("feedback_vi") or "").strip()
    corrected = str(data.get("corrected_sentence") or "").strip()
    suggested = str(data.get("suggested_sentence") or "").strip()
    if not feedback or not corrected or not suggested:
        raise AIError("Local AI grade response has empty required text fields.")
    return GradeResult(
        is_correct_usage=bool(data.get("is_correct_usage")),
        score=score,
        feedback_vi=feedback,
        corrected_sentence=corrected,
        suggested_sentence=suggested,
    )


def map_local_ai_http_error(
    status: int,
    payload: Mapping[str, Any] | None = None,
    *,
    unavailable: bool = False,
) -> AIError:
    """Documented Local AI HTTP / runtime error → App AIError mapping.

    Sanitized messages only. Never includes tokens, Origin, Host, or raw bodies.
    """
    code = ""
    if isinstance(payload, Mapping):
        error = payload.get("error")
        if isinstance(error, Mapping):
            code = str(error.get("code") or "").strip()
    if unavailable or status == 503:
        return AIError("Local AI runtime is unavailable.")
    if status == 502:
        return AIError("Local AI returned an invalid or incomplete result.")
    if status == 401:
        return AIError("Local AI authorization failed.")
    if status == 403:
        return AIError("Local AI request was rejected by the loopback security policy.")
    if status == 413:
        return AIError("Local AI request payload is too large.")
    if status == 415:
        return AIError("Local AI request media type must be application/json.")
    if status == 422:
        return AIError("Local AI request failed validation.")
    if status == 400:
        return AIError("Local AI rejected a malformed request.")
    if status == 404:
        return AIError("Local AI endpoint was not found.")
    label = code or f"http_{status}"
    return AIError(f"Local AI request failed ({label}).")


def recommended_local_timeout_sec(configured: float | None = None) -> float:
    """Resolve a cold-start-safe inference timeout for a future local provider."""
    value = (
        RECOMMENDED_LOCAL_AI_INFERENCE_TIMEOUT_SEC
        if configured is None
        else float(configured)
    )
    if value < MINIMUM_LOCAL_AI_INFERENCE_TIMEOUT_SEC:
        raise ValueError(
            f"{PROPOSED_TIMEOUT_ENV} must be >= "
            f"{MINIMUM_LOCAL_AI_INFERENCE_TIMEOUT_SEC} seconds "
            f"(observed cold grade ~18.83s)."
        )
    return value
