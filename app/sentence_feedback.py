"""Versioned App-domain structured sentence feedback (Phase 19.5B).

This is not GradeResult and does not change the deployed /api/grade wire.
Learner answers and model output are untrusted until validated here.
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

MAX_SEGMENT_LEN = 120
MAX_SENTENCE_LEN = 240
MAX_EXPLANATION_LEN = 400
MAX_RULE_ID_LEN = 80

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


def _clip(text: str, limit: int) -> str:
    return str(text or "").strip()[:limit]


def _normalize_space(text: str) -> str:
    return _SPACE_RE.sub(" ", str(text or "").strip())


def segment_in_answer(segment: str, answer: str) -> bool:
    """Require original_segment to correspond to the submitted answer (casefold)."""
    left = _normalize_space(segment).casefold()
    right = _normalize_space(answer).casefold()
    if not left:
        return True
    if not right:
        return False
    return left in right or right in left


def validate_structured_feedback(
    raw: Any,
    *,
    learner_answer: str = "",
    exercise: Optional[SentenceExercise] = None,
    allowed_rule_ids: Sequence[str] = (),
) -> StructuredSentenceFeedback:
    """Validate untrusted structured feedback at the trust boundary."""
    if not isinstance(raw, Mapping):
        raise StructuredFeedbackError("structured feedback must be an object")

    try:
        version = int(raw.get("format_version"))
    except (TypeError, ValueError):
        raise StructuredFeedbackError("format_version must be an integer") from None
    if version != FEEDBACK_FORMAT_VERSION:
        raise StructuredFeedbackError(f"unsupported feedback format version {version}")

    status = str(raw.get("grading_status") or "").strip()
    if status not in GRADING_STATUSES:
        raise StructuredFeedbackError(f"unsupported grading_status {status!r}")

    source = str(raw.get("grading_source") or "").strip()
    if source not in GRADING_SOURCES:
        raise StructuredFeedbackError(f"unsupported grading_source {source!r}")

    provisional = raw.get("provisional")
    if not isinstance(provisional, bool):
        raise StructuredFeedbackError("provisional must be a boolean")

    certainty_raw = raw.get("certainty", 0.0)
    try:
        certainty = float(certainty_raw)
    except (TypeError, ValueError):
        raise StructuredFeedbackError("certainty must be numeric") from None
    if not math.isfinite(certainty) or certainty < 0.0 or certainty > 1.0:
        raise StructuredFeedbackError("certainty must be finite in [0, 1]")

    error_class = str(raw.get("primary_error_class") or "").strip()
    if error_class not in ERROR_CLASSES:
        raise StructuredFeedbackError(f"unsupported primary_error_class {error_class!r}")

    original = _clip(raw.get("original_segment", ""), MAX_SEGMENT_LEN)
    corrected_seg = _clip(raw.get("corrected_segment", ""), MAX_SEGMENT_LEN)
    corrected_sentence = _clip(raw.get("corrected_sentence", ""), MAX_SENTENCE_LEN)
    explanation = _clip(raw.get("explanation", ""), MAX_EXPLANATION_LEN)
    provenance = _clip(raw.get("provenance", ""), MAX_EXPLANATION_LEN)
    rule_id = _clip(raw.get("grammar_rule_id", ""), MAX_RULE_ID_LEN)

    if original and learner_answer and not segment_in_answer(original, learner_answer):
        raise StructuredFeedbackError("original_segment does not correspond to the submitted answer")

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
        if exercise is not None:
            allowed |= {str(item).strip() for item in exercise.grammar_rule_ids if str(item).strip()}
        if rule_id not in allowed:
            raise StructuredFeedbackError(f"grammar_rule_id {rule_id!r} is not trusted for this exercise")

    # Score alone must never invent a class — reject contradictory AI inventing classes
    # when status is provisional accept with a non-empty definite class without provisional.
    if status == STATUS_PROVISIONAL_ACCEPT and error_class in (
        ERROR_CONJUGATION,
        ERROR_WORD_ORDER,
        ERROR_ARTICLE,
        ERROR_VOCABULARY,
        ERROR_GRAMMAR,
    ):
        # Acceptable only as unclassified/unknown for acceptance; clear the class.
        error_class = ERROR_UNCLASSIFIED

    return StructuredSentenceFeedback(
        format_version=version,
        grading_status=status,
        grading_source=source,
        provenance=provenance or ("local" if source == SOURCE_LOCAL else "ai"),
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
        "provisional_accept": STATUS_PROVISIONAL_ACCEPT,
        "provisional_correct": STATUS_PROVISIONAL_CORRECT,
        "unavailable": STATUS_UNAVAILABLE,
        "ungraded": STATUS_UNGRADED,
    }
    grading_status = mapping.get(status)
    if grading_status is None:
        return None
    error_class = ""
    if grading_status == STATUS_INCORRECT:
        if diagnosis_certain and error_hint in ERROR_CLASSES:
            error_class = error_hint
        else:
            error_class = ERROR_UNCLASSIFIED
    provisional = grading_status in (
        STATUS_PROVISIONAL_ACCEPT,
        STATUS_PROVISIONAL_CORRECT,
        STATUS_UNGRADED,
        STATUS_UNAVAILABLE,
    )
    certainty = 1.0 if diagnosis_certain and not provisional else (0.55 if provisional else 0.7)
    payload = {
        "format_version": FEEDBACK_FORMAT_VERSION,
        "grading_status": grading_status,
        "grading_source": SOURCE_LOCAL if grading_status != STATUS_UNAVAILABLE else SOURCE_NONE,
        "provenance": "local-deterministic",
        "primary_error_class": error_class,
        "original_segment": original_segment,
        "corrected_segment": corrected_segment,
        "corrected_sentence": corrected_sentence,
        "grammar_rule_id": grammar_rule_id if diagnosis_certain else "",
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
    )
