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

# Known Local AI HTTP statuses with fixed learner-safe messages.
# Unknown statuses/codes must never be echoed into AIError text.
_KNOWN_HTTP_STATUS_MESSAGES = {
    400: "Local AI rejected a malformed request.",
    401: "Local AI authorization failed.",
    403: "Local AI request was rejected by the loopback security policy.",
    404: "Local AI endpoint was not found.",
    413: "Local AI request payload is too large.",
    415: "Local AI request media type must be application/json.",
    422: "Local AI request failed validation.",
    502: "Local AI returned an invalid or incomplete result.",
    503: "Local AI runtime is unavailable.",
}


def load_fixture(name: str) -> Any:
    path = FIXTURES / name
    return json.loads(path.read_text(encoding="utf-8"))


def _require_nonempty_str(data: Mapping[str, Any], key: str) -> str:
    if key not in data:
        raise AIError(f"Local AI grade response missing field: {key}")
    raw = data.get(key)
    if not isinstance(raw, str):
        raise AIError(f"Local AI grade field {key} must be text.")
    text = raw.strip()
    if not text:
        raise AIError(f"Local AI grade field {key} is empty.")
    return text


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

    usage = data.get("is_correct_usage")
    if not isinstance(usage, bool):
        raise AIError("Local AI grade is_correct_usage must be a boolean.")

    score_raw = data.get("score")
    # bool is a subclass of int; reject before numeric coercion.
    if isinstance(score_raw, bool) or score_raw is None:
        raise AIError("Local AI grade score must be a finite number.")
    if isinstance(score_raw, str):
        raise AIError("Local AI grade score must be a finite number.")
    try:
        score = float(score_raw)
    except (TypeError, ValueError) as exc:
        raise AIError("Local AI grade score must be a finite number.") from exc
    if not math.isfinite(score) or score < 0.0 or score > 1.0:
        raise AIError("Local AI grade score must be finite and within [0.0, 1.0].")

    feedback = _require_nonempty_str(data, "feedback_vi")
    corrected = _require_nonempty_str(data, "corrected_sentence")
    suggested = _require_nonempty_str(data, "suggested_sentence")
    return GradeResult(
        is_correct_usage=usage,
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

    Sanitized messages only. Never includes tokens, Origin, Host, raw bodies,
    or untrusted/unknown error codes.
    """
    del payload  # Payload codes/messages are untrusted; do not echo them.
    if unavailable or status == 503:
        return AIError(_KNOWN_HTTP_STATUS_MESSAGES[503])
    message = _KNOWN_HTTP_STATUS_MESSAGES.get(int(status))
    if message is None:
        return AIError("Local AI request failed.")
    return AIError(message)


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
