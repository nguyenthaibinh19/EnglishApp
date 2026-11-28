"""Expandable Grammar Companion model for sentence feedback.

Never shown on independent vocabulary recall cards. Continue stays available.
When no validated rule exists, ordinary feedback is enough — do not invent a rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

import config
from sentence_content import (
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

    @property
    def has_rule(self) -> bool:
        return bool(self.rule_id)


def build_companion(
    exercise: SentenceExercise,
    rules: Sequence[GrammarRule],
    *,
    corrected_sentence: str = "",
    native: str = None,
) -> Optional[GrammarCompanionView]:
    if not rules:
        return None
    rule = rules[0]
    use_vi = (native or config.native_code() or "").strip().lower() == "vi"
    return GrammarCompanionView(
        title=rule.title_vi if use_vi else rule.title_en,
        beginner=rule.beginner_vi if use_vi else rule.beginner_en,
        full=rule.full_vi if use_vi else rule.full_en,
        corrected=corrected_sentence or exercise.primary_answer(),
        examples=tuple(rule.examples[:2]),
        components=exercise.components,
        rule_id=rule.rule_id,
        provenance=rule.provenance,
        review_status=rule.review_status,
    )


def component_color(role: str) -> str:
    return SENTENCE_COMPONENT_COLORS.get(role, SENTENCE_COMPONENT_COLORS["other"])
