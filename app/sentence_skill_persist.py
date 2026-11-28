"""Map graded sentence outcomes into SentenceSkillRecord appends (Phase 19.5B).

Does not persist raw learner sentences, raw AI responses, or corrected text.
Incomplete / empty / unlisted / ungraded-as-failure are not recorded as learner failures.
"""

from __future__ import annotations

from typing import Optional

from sentence_content import SentenceExercise
from sentence_grading import (
    STATUS_INCORRECT,
    STATUS_PROVISIONAL_ACCEPT,
    STATUS_PROVISIONAL_CORRECT,
    STATUS_REVIEWED_CORRECT,
    STATUS_UNAVAILABLE,
    STATUS_UNGRADED,
    SentenceGrade,
)
from sentence_skill_policy import support_rank_for_kind
from sentence_skill_record import (
    EVIDENCE_NONE,
    EVIDENCE_PROVISIONAL_AI,
    EVIDENCE_RELIABLE_LOCAL,
    EVIDENCE_REVIEWED,
    OUTCOME_INCORRECT,
    OUTCOME_PROVISIONAL_ACCEPT,
    OUTCOME_PROVISIONAL_CORRECT,
    OUTCOME_REVIEWED_CORRECT,
    OUTCOME_UNAVAILABLE,
    POLICY_FAMILY_SUPPORT_V1,
    SOURCE_AI,
    SOURCE_LOCAL,
    SOURCE_NONE,
    build_sentence_skill_record,
    outcome_is_recordable,
)
from sentence_skill_store import SentenceSkillStore, SentenceSkillStoreError


def evidence_for_grade(grade: SentenceGrade) -> str:
    if grade.status == STATUS_REVIEWED_CORRECT:
        return EVIDENCE_REVIEWED
    if grade.status == STATUS_INCORRECT and grade.diagnosis_certain and grade.graded_by == "local":
        return EVIDENCE_RELIABLE_LOCAL
    if grade.status == STATUS_INCORRECT and grade.graded_by == "local":
        return EVIDENCE_RELIABLE_LOCAL
    if grade.status in (STATUS_PROVISIONAL_ACCEPT, STATUS_PROVISIONAL_CORRECT):
        return EVIDENCE_PROVISIONAL_AI
    if grade.status in (STATUS_UNAVAILABLE, STATUS_UNGRADED):
        return EVIDENCE_NONE
    return EVIDENCE_NONE


def map_outcome(grade: SentenceGrade) -> Optional[str]:
    mapping = {
        STATUS_REVIEWED_CORRECT: OUTCOME_REVIEWED_CORRECT,
        STATUS_INCORRECT: OUTCOME_INCORRECT,
        STATUS_PROVISIONAL_ACCEPT: OUTCOME_PROVISIONAL_ACCEPT,
        STATUS_PROVISIONAL_CORRECT: OUTCOME_PROVISIONAL_CORRECT,
        STATUS_UNAVAILABLE: OUTCOME_UNAVAILABLE,
    }
    # Ungraded / incomplete / empty / unlisted are not learner failures — skip.
    return mapping.get(grade.status)


def grammar_refs_for_record(exercise: SentenceExercise, grade: SentenceGrade) -> tuple[str, ...]:
    """At most one skill ref on incorrect — only when diagnosis is certain and matched."""
    structured = getattr(grade, "structured", None)
    rule_id = ""
    if structured is not None:
        rule_id = str(getattr(structured, "grammar_rule_id", "") or "").strip()
        error_class = str(getattr(structured, "primary_error_class", "") or "")
        if error_class in ("unclassified", "unknown", ""):
            return ()
    if rule_id and rule_id in exercise.grammar_rule_ids:
        return (rule_id,)
    if grade.status == STATUS_INCORRECT and grade.diagnosis_certain and grade.error_hint:
        from sentence_content import ERROR_RULE_PREFERENCE

        preferred = ERROR_RULE_PREFERENCE.get(grade.error_hint, ())
        for rid in exercise.grammar_rule_ids:
            if any(token in rid for token in preferred):
                return (rid,)
        # Do not assign the first available rule merely because it exists.
    return ()


def persist_sentence_skill(
    store: Optional[SentenceSkillStore],
    *,
    session_id: str,
    exercise: SentenceExercise,
    grade: SentenceGrade,
    exercise_instance_id: str,
    submission_id: str,
) -> Optional[object]:
    """Append one skill event when the outcome is recordable. Honest on failure."""
    if store is None:
        return None
    outcome = map_outcome(grade)
    if outcome is None or not outcome_is_recordable(outcome):
        return None
    if not submission_id or not exercise_instance_id:
        return None

    source = SOURCE_LOCAL if grade.graded_by == "local" else (
        SOURCE_AI if grade.graded_by == "ai" else SOURCE_NONE
    )
    error_class = "none"
    if grade.status == STATUS_INCORRECT:
        error_class = grade.error_hint if grade.diagnosis_certain and grade.error_hint else "unclassified"
    structured = getattr(grade, "structured", None)
    if structured is not None:
        structured_class = str(getattr(structured, "primary_error_class", "") or "").strip()
        if structured_class:
            error_class = structured_class
    if not error_class:
        error_class = "none"

    record = build_sentence_skill_record(
        session_id=session_id,
        exercise_instance_id=exercise_instance_id,
        submission_id=submission_id,
        exercise_id=exercise.exercise_id,
        family_id=exercise.family_id or "unspecified",
        content_version=str(exercise.content_version),
        study_language=exercise.language_code,
        cefr_level=exercise.cefr,
        exercise_kind=exercise.kind,
        support_level=support_rank_for_kind(exercise.kind),
        outcome=outcome,
        grading_source=source,
        error_classification=error_class,
        evidence_status=evidence_for_grade(grade),
        grammar_skill_refs=grammar_refs_for_record(exercise, grade),
        selection_policy_id=POLICY_FAMILY_SUPPORT_V1,
    )
    try:
        return store.append(record)
    except SentenceSkillStoreError:
        raise
