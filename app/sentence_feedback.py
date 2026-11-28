"""Versioned App-domain structured sentence feedback (Phase 19.5B).

This is not GradeResult and does not change the deployed /api/grade wire.
Learner answers and model output are untrusted until validated here.
Malformed field types are rejected — never silently coerced into acceptance.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

from sentence_content import SentenceExercise

FEEDBACK_FORMAT_VERSION = 1

STATUS_REVIEWED_CORRECT = "reviewed_correct"
STATUS_INCORRECT = "incorrect"
STATUS_PROVISIONAL_ACCEPT = "provisional_accept"
STATUS_PROVISIONAL_CORRECT = "provisional_correct"
STATUS_UNGRADED = "ungraded"
STATUS_UNAVAILABLE = "unavailable"

GRADING_STATUSES = frozenset(
    {
        STATUS_REVIEWED_CORRECT,
        STATUS_INCORRECT,
        STATUS_PROVISIONAL_ACCEPT,
        STATUS_PROVISIONAL_CORRECT,
        STATUS_UNGRADED,
        STATUS_UNAVAILABLE,
    }
)

SOURCE_LOCAL = "local"
SOURCE_AI = "ai"
SOURCE_NONE = "none"
GRADING_SOURCES = frozenset({SOURCE_LOCAL, SOURCE_AI, SOURCE_NONE})

ERROR_CONJUGATION = "conjugation"
ERROR_WORD_ORDER = "word_order"
ERROR_ARTICLE = "article"
ERROR_VOCABULARY = "vocabulary"
ERROR_GRAMMAR = "grammar"
ERROR_UNKNOWN = "unknown"
ERROR_UNCLASSIFIED = "unclassified"
ERROR_CLASSES = frozenset(
    {
        "",
        ERROR_CONJUGATION,
        ERROR_WORD_ORDER,
        ERROR_ARTICLE,
        ERROR_VOCABULARY,
        ERROR_GRAMMAR,
        ERROR_UNKNOWN,
        ERROR_UNCLASSIFIED,
    }
)

DEFINITE_ERROR_CLASSES = frozenset(
    {
        ERROR_CONJUGATION,
        ERROR_WORD_ORDER,
        ERROR_ARTICLE,
        ERROR_VOCABULARY,
        ERROR_GRAMMAR,
    }
)

MAX_SEGMENT_LEN = 120
MAX_SENTENCE_LEN = 240
MAX_EXPLANATION_LEN = 400
MAX_RULE_ID_LEN = 80
MAX_PROVENANCE_LEN = 120

_SPACE_RE = re.compile(r"\s+")


class StructuredFeedbackError(ValueError):
    """Feedback failed trust-boundary validation."""


@dataclass(frozen=True)
class StructuredSentenceFeedback:
    """Validated structured feedback. Never mutates content packs or vocabulary."""

    format_version: int
    grading_status: str
    grading_source: str
    provenance: str
    primary_error_class: str
    original_segment: str
    corrected_segment: str
    corrected_sentence: str
    grammar_rule_id: str
    explanation: str
    provisional: bool
    certainty: float  # 0..1; model confidence is not linguistic proof

    def as_dict(self) -> dict:
        return {
            "format_version": self.format_version,
            "grading_status": self.grading_status,
            "grading_source": self.grading_source,
            "provenance": self.provenance,
            "primary_error_class": self.primary_error_class,
            "original_segment": self.original_segment,
            "corrected_segment": self.corrected_segment,
            "corrected_sentence": self.corrected_sentence,
            "grammar_rule_id": self.grammar_rule_id,
            "explanation": self.explanation,
            "provisional": self.provisional,
            "certainty": self.certainty,
        }


def future_structured_feedback_transport_mapping() -> tuple[str, ...]:
    """Proposed future mapping onto GradeResult /api/grade — not deployed."""
    return (
        "Keep GradeResult.is_correct_usage / score / feedback_vi / corrected_sentence / "
        "suggested_sentence unchanged for v0.2.0 consumers.",
        "A future additive wire field (e.g. structured_feedback object) may carry "
        "format_version, primary_error_class, original_segment, corrected_segment, "
        "grammar_rule_id, provisional, and certainty.",
        "Absent structured_feedback, App builds provisional StructuredSentenceFeedback "
        "from GradeResult without inventing error classes from score alone.",
        "Deployed /api/grade request/response and C-APP-AI-001 v0.2.0 stay unchanged "
        "until a separate shared-contract revision is accepted.",
    )


def _require_exact_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise StructuredFeedbackError(f"{field} must be an exact integer")
    return value


def _require_bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise StructuredFeedbackError(f"{field} must be a boolean")
    return value


def _require_text(value: Any, field: str, limit: int) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise StructuredFeedbackError(f"{field} must be a string")
    return value.strip()[:limit]


def _normalize_space(text: str) -> str:
    return _SPACE_RE.sub(" ", str(text or "").strip())


def segment_in_answer(segment: str, answer: str) -> bool:
    """Require original_segment to appear in the submitted answer (one direction)."""
    left = _normalize_space(segment).casefold()
    right = _normalize_space(answer).casefold()
    if not left:
        return True
    if not right:
        return False
    return left in right


def segment_in_correction(segment: str, correction_context: str) -> bool:
    """Require corrected_segment to appear in the applicable correction context."""
    left = _normalize_space(segment).casefold()
    right = _normalize_space(correction_context).casefold()
    if not left:
        return True
    if not right:
        return False
    return left in right


def _enforce_source_status_semantics(
    *,
    status: str,
    source: str,
    provisional: bool,
    error_class: str,
) -> None:
    """Reject inconsistent grading source / status / provisional claims."""
    if source == SOURCE_AI:
        if status in (STATUS_REVIEWED_CORRECT, STATUS_INCORRECT):
            raise StructuredFeedbackError(
                "AI feedback cannot declare reviewed local correctness or definitive incorrect"
            )
        if status in (STATUS_PROVISIONAL_ACCEPT, STATUS_PROVISIONAL_CORRECT, STATUS_UNGRADED) and not provisional:
            raise StructuredFeedbackError("AI feedback must be marked provisional")
        if status == STATUS_UNAVAILABLE and not provisional:
            raise StructuredFeedbackError("unavailable AI feedback must be provisional")
        if not provisional and status != STATUS_UNAVAILABLE:
            raise StructuredFeedbackError("AI feedback cannot claim non-provisional authority")
    if source == SOURCE_LOCAL:
        if status in (STATUS_PROVISIONAL_ACCEPT, STATUS_PROVISIONAL_CORRECT):
            raise StructuredFeedbackError("local source cannot claim AI-provisional statuses")
        if status == STATUS_REVIEWED_CORRECT and provisional:
            raise StructuredFeedbackError("reviewed_correct cannot be provisional")
        if status == STATUS_INCORRECT and provisional:
            raise StructuredFeedbackError("local incorrect must not be marked provisional")
    if source == SOURCE_NONE and status not in (STATUS_UNAVAILABLE, STATUS_UNGRADED):
        raise StructuredFeedbackError("source none only allowed for unavailable/ungraded")
    if status == STATUS_PROVISIONAL_ACCEPT and error_class in DEFINITE_ERROR_CLASSES:
        raise StructuredFeedbackError(
            "provisional_accept cannot carry a definite primary error class"
        )
    if status == STATUS_REVIEWED_CORRECT and error_class in DEFINITE_ERROR_CLASSES:
        raise StructuredFeedbackError("reviewed_correct cannot carry a primary error class")


def validate_structured_feedback(
    raw: Any,
    *,
    learner_answer: str = "",
    exercise: Optional[SentenceExercise] = None,
    allowed_rule_ids: Sequence[str] = (),
    pack_rule_ids: Sequence[str] = (),
    expected_language: str = "",
    expected_content_version: Optional[int] = None,
) -> StructuredSentenceFeedback:
    """Validate untrusted structured feedback at the trust boundary."""
    if not isinstance(raw, Mapping):
        raise StructuredFeedbackError("structured feedback must be an object")

    version = _require_exact_int(raw.get("format_version"), "format_version")
    if version != FEEDBACK_FORMAT_VERSION:
        raise StructuredFeedbackError(f"unsupported feedback format version {version}")

    status_raw = raw.get("grading_status")
    if not isinstance(status_raw, str):
        raise StructuredFeedbackError("grading_status must be a string")
    status = status_raw.strip()
    if status not in GRADING_STATUSES:
        raise StructuredFeedbackError(f"unsupported grading_status {status!r}")

    source_raw = raw.get("grading_source")
    if not isinstance(source_raw, str):
        raise StructuredFeedbackError("grading_source must be a string")
    source = source_raw.strip()
    if source not in GRADING_SOURCES:
        raise StructuredFeedbackError(f"unsupported grading_source {source!r}")

    provisional = _require_bool(raw.get("provisional"), "provisional")

    certainty_raw = raw.get("certainty", 0.0)
    if isinstance(certainty_raw, bool) or not isinstance(certainty_raw, (int, float)):
        raise StructuredFeedbackError("certainty must be numeric")
    certainty = float(certainty_raw)
    if not math.isfinite(certainty) or certainty < 0.0 or certainty > 1.0:
        raise StructuredFeedbackError("certainty must be finite in [0, 1]")

    error_raw = raw.get("primary_error_class", "")
    if error_raw is None:
        error_raw = ""
    if not isinstance(error_raw, str):
        raise StructuredFeedbackError("primary_error_class must be a string")
    error_class = error_raw.strip()
    if error_class not in ERROR_CLASSES:
        raise StructuredFeedbackError(f"unsupported primary_error_class {error_class!r}")

    original = _require_text(raw.get("original_segment", ""), "original_segment", MAX_SEGMENT_LEN)
    corrected_seg = _require_text(
        raw.get("corrected_segment", ""), "corrected_segment", MAX_SEGMENT_LEN
    )
    corrected_sentence = _require_text(
        raw.get("corrected_sentence", ""), "corrected_sentence", MAX_SENTENCE_LEN
    )
    explanation = _require_text(raw.get("explanation", ""), "explanation", MAX_EXPLANATION_LEN)
    provenance = _require_text(raw.get("provenance", ""), "provenance", MAX_PROVENANCE_LEN)
    rule_id = _require_text(raw.get("grammar_rule_id", ""), "grammar_rule_id", MAX_RULE_ID_LEN)

    _enforce_source_status_semantics(
        status=status,
        source=source,
        provisional=provisional,
        error_class=error_class,
    )

    if original and learner_answer and not segment_in_answer(original, learner_answer):
        raise StructuredFeedbackError("original_segment does not correspond to the submitted answer")

    if corrected_seg:
        context = corrected_sentence
        if not context and exercise is not None:
            context = exercise.primary_answer()
        if context and not segment_in_correction(corrected_seg, context):
            raise StructuredFeedbackError(
                "corrected_segment does not correspond to the correction context"
            )

    # Never follow instructions embedded in text fields — treat as plain display text only.
    for field_name, value in (
        ("explanation", explanation),
        ("provenance", provenance),
        ("corrected_sentence", corrected_sentence),
    ):
        lowered = value.casefold()
        if "ignore previous" in lowered or "system prompt" in lowered:
            raise StructuredFeedbackError(f"{field_name} contains disallowed instruction-like content")

    if rule_id:
        allowed = {str(item).strip() for item in allowed_rule_ids if str(item).strip()}
        allowed |= {str(item).strip() for item in pack_rule_ids if str(item).strip()}
        if exercise is not None:
            allowed |= {str(item).strip() for item in exercise.grammar_rule_ids if str(item).strip()}
            if expected_language and exercise.language_code != expected_language:
                raise StructuredFeedbackError("exercise language does not match feedback context")
            if (
                expected_content_version is not None
                and int(exercise.content_version) != int(expected_content_version)
            ):
                raise StructuredFeedbackError("exercise content version does not match feedback context")
        if rule_id not in allowed:
            raise StructuredFeedbackError(f"grammar_rule_id {rule_id!r} is not trusted for this exercise")

    if not provenance:
        provenance = "local-deterministic" if source == SOURCE_LOCAL else (
            "none" if source == SOURCE_NONE else "ai"
        )

    return StructuredSentenceFeedback(
        format_version=version,
        grading_status=status,
        grading_source=source,
        provenance=provenance,
        primary_error_class=error_class,
        original_segment=original,
        corrected_segment=corrected_seg,
        corrected_sentence=corrected_sentence,
        grammar_rule_id=rule_id,
        explanation=explanation,
        provisional=provisional,
        certainty=certainty,
    )


def feedback_from_local_grade(
    *,
    status: str,
    error_hint: str,
    diagnosis_certain: bool,
    corrected_sentence: str,
    explanation: str,
    grammar_rule_id: str = "",
    original_segment: str = "",
    corrected_segment: str = "",
    learner_answer: str = "",
    exercise: Optional[SentenceExercise] = None,
) -> Optional[StructuredSentenceFeedback]:
    """Build validated local structured feedback. Returns None when ungradable."""
    if status in ("empty", "incomplete", "unlisted"):
        return None
    mapping = {
        "reviewed_correct": STATUS_REVIEWED_CORRECT,
        "incorrect": STATUS_INCORRECT,
        "unavailable": STATUS_UNAVAILABLE,
        "ungraded": STATUS_UNGRADED,
    }
    grading_status = mapping.get(status)
    if grading_status is None:
        # Local path never emits AI-provisional statuses.
        return None
    error_class = ""
    rule = ""
    if grading_status == STATUS_INCORRECT:
        if diagnosis_certain and error_hint in DEFINITE_ERROR_CLASSES:
            error_class = error_hint
            rule = grammar_rule_id
        else:
            error_class = ERROR_UNCLASSIFIED
            rule = ""  # never assign a rule for unclassified local failure
    provisional = grading_status in (STATUS_UNGRADED, STATUS_UNAVAILABLE)
    certainty = 1.0 if diagnosis_certain and not provisional else (0.0 if provisional else 0.7)
    payload = {
        "format_version": FEEDBACK_FORMAT_VERSION,
        "grading_status": grading_status,
        "grading_source": SOURCE_LOCAL if grading_status != STATUS_UNAVAILABLE else SOURCE_NONE,
        "provenance": "local-deterministic",
        "primary_error_class": error_class,
        "original_segment": original_segment,
        "corrected_segment": corrected_segment,
        "corrected_sentence": corrected_sentence,
        "grammar_rule_id": rule,
        "explanation": explanation,
        "provisional": provisional,
        "certainty": certainty,
    }
    try:
        return validate_structured_feedback(
            payload,
            learner_answer=learner_answer,
            exercise=exercise,
            allowed_rule_ids=tuple(exercise.grammar_rule_ids) if exercise else (),
            expected_language=exercise.language_code if exercise else "",
            expected_content_version=exercise.content_version if exercise else None,
        )
    except StructuredFeedbackError:
        return None


def feedback_from_grade_result(
    result,
    *,
    learner_answer: str,
    exercise: SentenceExercise,
    allowed_rule_ids: Sequence[str] = (),
) -> StructuredSentenceFeedback:
    """Degrade an existing GradeResult into structured feedback without inventing classes.

    Does not require provider abstract-method changes. Malformed fields → ungraded.
    """
    from sentence_grading import _validate_grade_result

    problem = _validate_grade_result(result)
    if problem:
        return StructuredSentenceFeedback(
            format_version=FEEDBACK_FORMAT_VERSION,
            grading_status=STATUS_UNGRADED,
            grading_source=SOURCE_AI,
            provenance="grade-result-malformed",
            primary_error_class=ERROR_UNKNOWN,
            original_segment="",
            corrected_segment="",
            corrected_sentence="",
            grammar_rule_id="",
            explanation="AI feedback was incomplete. This is not a definitive result.",
            provisional=True,
            certainty=0.0,
        )

    score = float(result.score)
    corrected = str(getattr(result, "corrected_sentence", "") or "").strip()[:MAX_SENTENCE_LEN]
    suggested = str(getattr(result, "suggested_sentence", "") or "").strip()[:MAX_SENTENCE_LEN]
    note = str(getattr(result, "feedback_vi", "") or "").strip()[:MAX_EXPLANATION_LEN]
    if bool(result.is_correct_usage) and score >= 0.7:
        status = STATUS_PROVISIONAL_ACCEPT
        explanation = note or "Looks usable (provisional)."
        corrected_out = corrected or learner_answer
        error_class = ERROR_UNCLASSIFIED
    else:
        status = STATUS_PROVISIONAL_CORRECT
        explanation = note or "Needs another try (provisional)."
        corrected_out = corrected or suggested or exercise.primary_answer()
        error_class = ERROR_UNKNOWN  # never invent conjugation/etc from score

    payload = {
        "format_version": FEEDBACK_FORMAT_VERSION,
        "grading_status": status,
        "grading_source": SOURCE_AI,
        "provenance": "grade-result-degraded",
        "primary_error_class": error_class,
        "original_segment": "",
        "corrected_segment": "",
        "corrected_sentence": corrected_out,
        "grammar_rule_id": "",
        "explanation": explanation,
        "provisional": True,
        "certainty": min(max(score, 0.0), 1.0),
    }
    return validate_structured_feedback(
        payload,
        learner_answer=learner_answer,
        exercise=exercise,
        allowed_rule_ids=allowed_rule_ids or exercise.grammar_rule_ids,
        expected_language=exercise.language_code,
        expected_content_version=exercise.content_version,
    )


def map_structured_to_sentence_grade(structured: StructuredSentenceFeedback, *, fallback_feedback: str = ""):
    """Compatibility mapping: one coherent grade from validated structured feedback."""
    from sentence_grading import SentenceGrade

    status_map = {
        STATUS_REVIEWED_CORRECT: "reviewed_correct",
        STATUS_INCORRECT: "incorrect",
        STATUS_PROVISIONAL_ACCEPT: "provisional_accept",
        STATUS_PROVISIONAL_CORRECT: "provisional_correct",
        STATUS_UNGRADED: "ungraded",
        STATUS_UNAVAILABLE: "unavailable",
    }
    return SentenceGrade(
        status=status_map.get(structured.grading_status, "ungraded"),
        matched_local=structured.grading_status == STATUS_REVIEWED_CORRECT,
        graded_by=structured.grading_source if structured.grading_source != SOURCE_NONE else "none",
        feedback=structured.explanation or fallback_feedback,
        corrected_sentence=structured.corrected_sentence,
        error_hint=structured.primary_error_class
        if structured.primary_error_class in DEFINITE_ERROR_CLASSES
        else "",
        score=structured.certainty,
        diagnosis_certain=(
            not structured.provisional
            and structured.primary_error_class in DEFINITE_ERROR_CLASSES
        ),
        structured=structured,
        original_segment=structured.original_segment,
        corrected_segment=structured.corrected_segment,
    )
