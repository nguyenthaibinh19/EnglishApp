"""Expandable Grammar Companion model for sentence feedback (19.5A R1).

Never shown on independent vocabulary recall cards. Continue stays available.
When no curated rule applies, ordinary feedback is enough — do not invent a rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

import config
from sentence_content import (
    ERROR_RULE_PREFERENCE,
    REVIEW_PENDING_EXPERT,
    SENTENCE_COMPONENT_COLORS,
    GrammarRule,
    SentenceComponent,
    SentenceExercise,
)


@dataclass(frozen=True)
class GrammarCompanionView:
    title: str
    beginner: str
    full: str
    corrected: str
    examples: Tuple[str, ...]
    components: Tuple[SentenceComponent, ...]
    rule_id: str = ""
    provenance: str = ""
    review_status: str = ""
    diagnosis_certain: bool = False
    guidance_only: bool = False

    @property
    def has_rule(self) -> bool:
        return bool(self.rule_id)


def select_rule(
    exercise: SentenceExercise,
    rules: Sequence[GrammarRule],
    *,
    error_hint: str = "",
    diagnosis_certain: bool = False,
) -> Tuple[Optional[GrammarRule], bool]:
    """Pick an applicable curated rule. Returns (rule, claims_diagnosis)."""
    if not rules:
        return None, False
    mapping = {rule.rule_id: rule for rule in rules}
    ordered = list(rules)

    if error_hint and diagnosis_certain:
        preferred = ERROR_RULE_PREFERENCE.get(error_hint, ())
        for rule in ordered:
            topics = tuple(rule.topics) + (rule.rule_id,)
            if any(token in topic for token in preferred for topic in topics):
                return rule, True
            if any(token in rule.rule_id for token in preferred):
                return rule, True
        # Fall through to exercise-linked rule without claiming diagnosis.
        for rule_id in exercise.grammar_rule_ids:
            if rule_id in mapping:
                return mapping[rule_id], False

    # Uncertain: relevant learning guidance from the exercise, no diagnosis claim.
    for rule_id in exercise.grammar_rule_ids:
        if rule_id in mapping:
            return mapping[rule_id], False
    return ordered[0], False


def build_companion(
    exercise: SentenceExercise,
    rules: Sequence[GrammarRule],
    *,
    corrected_sentence: str = "",
    error_hint: str = "",
    diagnosis_certain: bool = False,
    native: str = None,
    allow_ai_suggestion: bool = False,
) -> Optional[GrammarCompanionView]:
    """Build companion from curated content only.

    AI suggestions must not appear as validated rules or reviewed examples.
    Corrected text and components always refer to the same reviewed sentence.
    """
    rule, claims = select_rule(
        exercise,
        rules,
        error_hint=error_hint,
        diagnosis_certain=diagnosis_certain,
    )
    if rule is None:
        return None

    use_vi = (native or config.native_code() or "").strip().lower() == "vi"
    reviewed = exercise.primary_answer()
    # Never substitute an AI suggestion for the reviewed corrected display here.
    corrected = reviewed if not allow_ai_suggestion else (corrected_sentence or reviewed)
    if corrected_sentence and corrected_sentence.strip() == reviewed.strip():
        corrected = reviewed
    elif not allow_ai_suggestion:
        corrected = reviewed

    title = rule.title_vi if use_vi else rule.title_en
    beginner = rule.beginner_vi if use_vi else rule.beginner_en
    full = rule.full_vi if use_vi else rule.full_en
    guidance_only = not claims
    if guidance_only:
        prefix = config.ui(
            "Gợi ý học (chưa chẩn đoán lỗi cụ thể): ",
            "Learning guidance (not a specific error diagnosis): ",
        )
        beginner = prefix + beginner

    status_note = ""
    if rule.review_status == REVIEW_PENDING_EXPERT:
        status_note = config.ui(
            " (chưa có xác nhận chuyên gia ngôn ngữ)",
            " (pending expert linguistic validation)",
        )

    return GrammarCompanionView(
        title=title + status_note,
        beginner=beginner,
        full=full,
        corrected=corrected,
        examples=tuple(rule.examples[:2]),
        components=exercise.components,
        rule_id=rule.rule_id,
        provenance=rule.provenance,
        review_status=rule.review_status,
        diagnosis_certain=claims,
        guidance_only=guidance_only,
    )


def component_color(role: str) -> str:
    return SENTENCE_COMPONENT_COLORS.get(role, SENTENCE_COMPONENT_COLORS["other"])
