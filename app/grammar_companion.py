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
    original_segment: str = ""
    corrected_segment: str = ""
    provisional: bool = False
    model_suggestion: bool = False
    explanation: str = ""
    primary_error_class: str = ""

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
    structured=None,
) -> Optional[GrammarCompanionView]:
    """Build companion from curated content only.

    AI suggestions must not appear as validated rules or reviewed examples.
    Corrected text and components always refer to the same reviewed sentence.
    Structured feedback may supply segment highlights and provisional notes.
    """
    original_segment = ""
    corrected_segment = ""
    provisional = False
    model_suggestion = False
    explanation = ""
    primary_error_class = ""
    structured_rule_id = ""

    if structured is not None:
        original_segment = str(getattr(structured, "original_segment", "") or "")
        corrected_segment = str(getattr(structured, "corrected_segment", "") or "")
        provisional = bool(getattr(structured, "provisional", False))
        explanation = str(getattr(structured, "explanation", "") or "")
        primary_error_class = str(getattr(structured, "primary_error_class", "") or "")
        structured_rule_id = str(getattr(structured, "grammar_rule_id", "") or "")
        source = str(getattr(structured, "grading_source", "") or "")
        model_suggestion = source == "ai" or provisional
        if structured_rule_id and not any(rule.rule_id == structured_rule_id for rule in rules):
            # Untrusted / unrelated reference — general guidance only.
            structured_rule_id = ""
            diagnosis_certain = False
        if primary_error_class and not error_hint and diagnosis_certain and not provisional:
            error_hint = primary_error_class

    mapping = {rule.rule_id: rule for rule in rules}
    rule = None
    claims = False
    if structured_rule_id and structured_rule_id in mapping and diagnosis_certain and not provisional:
        # Selected rule must correspond to the validated feedback reference.
        rule = mapping[structured_rule_id]
        claims = True
    else:
        rule, claims = select_rule(
            exercise,
            rules,
            error_hint=error_hint,
            diagnosis_certain=diagnosis_certain and not provisional,
        )
        if structured_rule_id and rule is not None and rule.rule_id != structured_rule_id:
            # Prefer the validated feedback reference when it exists in the pack.
            if structured_rule_id in mapping:
                rule = mapping[structured_rule_id]
                claims = diagnosis_certain and not provisional
    if rule is None and not explanation and not original_segment:
        return None

    use_vi = (native or config.native_code() or "").strip().lower() == "vi"
    reviewed = exercise.primary_answer()
    # Reviewed reference sentence stays reviewed; AI proposals are labeled separately.
    if model_suggestion and allow_ai_suggestion:
        corrected = corrected_sentence or ""
    else:
        corrected = reviewed

    # Do not present an arbitrary model correction beside unrelated reviewed components.
    components = () if model_suggestion else exercise.components
    examples = ()

    if rule is not None and not model_suggestion:
        title = rule.title_vi if use_vi else rule.title_en
        beginner = rule.beginner_vi if use_vi else rule.beginner_en
        full = rule.full_vi if use_vi else rule.full_en
        examples = tuple(rule.examples[:2])
        rule_id = rule.rule_id
        provenance = rule.provenance
        review_status = rule.review_status
    elif rule is not None and model_suggestion:
        # Curated rule text may still guide, but examples stay reviewed-only and
        # the correction line is the model proposal.
        title = rule.title_vi if use_vi else rule.title_en
        beginner = rule.beginner_vi if use_vi else rule.beginner_en
        full = rule.full_vi if use_vi else rule.full_en
        examples = tuple(rule.examples[:2])
        rule_id = rule.rule_id
        provenance = rule.provenance
        review_status = rule.review_status
        claims = False
    else:
        title = config.ui("Gợi ý chung", "General guidance")
        beginner = explanation or config.ui(
            "Chưa có quy tắc khớp đã xác nhận. Hãy thử lại với mẫu đã duyệt.",
            "No matching validated rule. Try again with a reviewed pattern.",
        )
        full = ""
        rule_id = ""
        provenance = "general-guidance"
        review_status = ""

    guidance_only = not claims or rule is None or model_suggestion
    if guidance_only and rule is not None and not model_suggestion:
        prefix = config.ui(
            "Gợi ý học (chưa chẩn đoán lỗi cụ thể): ",
            "Learning guidance (not a specific error diagnosis): ",
        )
        beginner = prefix + beginner
    if provisional:
        provisional_note = config.ui(
            "Chẩn đoán tạm thời (chưa xác nhận). ",
            "Provisional diagnosis (not confirmed). ",
        )
        beginner = provisional_note + beginner
        if explanation and explanation not in beginner:
            beginner = f"{beginner} {explanation}".strip()

    status_note = ""
    if rule is not None and rule.review_status == REVIEW_PENDING_EXPERT:
        status_note = config.ui(
            " (chưa có xác nhận chuyên gia ngôn ngữ)",
            " (pending expert linguistic validation)",
        )

    return GrammarCompanionView(
        title=title + status_note,
        beginner=beginner,
        full=full,
        corrected=corrected,
        examples=examples,
        components=components,
        rule_id=rule_id,
        provenance=provenance,
        review_status=review_status,
        diagnosis_certain=claims and not provisional and not model_suggestion,
        guidance_only=guidance_only,
        original_segment=original_segment,
        corrected_segment=corrected_segment if not model_suggestion else "",
        provisional=provisional,
        model_suggestion=model_suggestion,
        explanation=explanation,
        primary_error_class=primary_error_class,
    )


def component_color(role: str) -> str:
    return SENTENCE_COMPONENT_COLORS.get(role, SENTENCE_COMPONENT_COLORS["other"])
