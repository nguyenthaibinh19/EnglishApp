"""Conservative cross-session sentence exercise selection (Phase 19.5B).

Deterministic initial policy (no mastery formula):

1. Consider only selection-relevant, reviewed/reliable-local evidence within
   RECENCY_DAYS, matching study language and content version.
2. Exclude provisional AI, unsupported/invalid rows, and future-dated timestamps.
3. For each family, the most recent reliable incorrect at support rank S motivates
   scaffolding at max(0, S-1) unless a later reviewed correct at the same or
   harder support rank (compatible family/skill) resolves that difficulty.
4. An easier-level assisted/reviewed success does NOT clear harder-level difficulty.
5. Fallback: empty family → default pack order.

Provisional AI evidence never drives family/support selection.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, Sequence

from sentence_content import (
    KIND_FILL_BLANK,
    KIND_GUIDED_WRITING,
    KIND_INDEPENDENT_WRITING,
    KIND_WORD_BANK,
    LADDER,
    SentenceExercise,
)
from sentence_skill_record import (
    EVIDENCE_PROVISIONAL_AI,
    EVIDENCE_RELIABLE_LOCAL,
    EVIDENCE_REVIEWED,
    OUTCOME_INCORRECT,
    OUTCOME_REVIEWED_CORRECT,
    POLICY_FAMILY_SUPPORT_V1,
    SentenceSkillRecord,
    outcome_affects_selection,
    parse_utc,
)

# Ignore selection-relevant rows older than this for cold start fallback.
RECENCY_DAYS = 14

_KIND_TO_SUPPORT_RANK = {
    KIND_WORD_BANK: 0,
    KIND_FILL_BLANK: 1,
    KIND_GUIDED_WRITING: 2,
    KIND_INDEPENDENT_WRITING: 3,
}


@dataclass(frozen=True)
class SentenceSelectionDecision:
    policy_id: str
    family_id: str
    preferred_kind: str
    preferred_support_rank: int
    reason: str
    motivating_event_id: str = ""


def evidence_usable_for_selection(record: SentenceSkillRecord) -> bool:
    if not outcome_affects_selection(record.outcome):
        return False
    if record.evidence_status == EVIDENCE_PROVISIONAL_AI:
        return False
    if record.evidence_status not in (EVIDENCE_REVIEWED, EVIDENCE_RELIABLE_LOCAL):
        return False
    return True


def support_rank_for_kind(kind: str) -> int:
    return int(_KIND_TO_SUPPORT_RANK.get(str(kind or "").strip(), 0))


def kind_for_support_rank(rank: int) -> str:
    clamped = max(0, min(int(rank), len(LADDER) - 1))
    return LADDER[clamped]


def _within_recency(record: SentenceSkillRecord, *, now: Optional[datetime] = None) -> bool:
    moment = now or datetime.now(timezone.utc)
    try:
        occurred = parse_utc(record.occurred_at)
    except Exception:
        return False
    if occurred > moment + timedelta(minutes=5):
        # Future-dated evidence is excluded from adaptation.
        return False
    return occurred >= moment - timedelta(days=RECENCY_DAYS)


def _skill_compatible(incorrect: SentenceSkillRecord, success: SentenceSkillRecord) -> bool:
    if incorrect.family_id != success.family_id:
        return False
    left = set(incorrect.grammar_skill_refs)
    right = set(success.grammar_skill_refs)
    if left and right and left.isdisjoint(right):
        return False
    return True


def _difficulty_resolved(
    incorrect: SentenceSkillRecord,
    history_newest_first: Sequence[SentenceSkillRecord],
) -> bool:
    """True when a later reviewed correct at same/harder support clears this incorrect."""
    incorrect_time = parse_utc(incorrect.occurred_at)
    for row in history_newest_first:
        if row.skill_event_id == incorrect.skill_event_id:
            continue
        if row.outcome != OUTCOME_REVIEWED_CORRECT:
            continue
        if row.evidence_status != EVIDENCE_REVIEWED:
            continue
        if not _skill_compatible(incorrect, row):
            continue
        if parse_utc(row.occurred_at) <= incorrect_time:
            continue
        # Easier success must not clear harder difficulty.
        if int(row.support_level) < int(incorrect.support_level):
            continue
        return True
    return False


def select_from_sentence_skill_history(
    history: Sequence[SentenceSkillRecord],
    exercises: Sequence[SentenceExercise],
    *,
    study_language: str,
    content_version: str = "",
    now: Optional[datetime] = None,
) -> SentenceSelectionDecision:
    """Pick related family scaffolding for an unresolved reliable struggle."""
    code = str(study_language or "").strip().lower()
    usable = [
        row
        for row in history
        if row.study_language == code
        and evidence_usable_for_selection(row)
        and _within_recency(row, now=now)
        and (not content_version or row.content_version == content_version)
    ]
    usable.sort(key=lambda row: (parse_utc(row.occurred_at), row.skill_event_id), reverse=True)

    seen_families: set[str] = set()
    for row in usable:
        family = str(row.family_id or "").strip()
        if not family or family in seen_families:
            continue
        if row.outcome != OUTCOME_INCORRECT:
            # Do not treat a recent easy success as "family cleared".
            continue
        seen_families.add(family)
        if _difficulty_resolved(row, usable):
            continue
        preferred_rank = max(0, int(row.support_level) - 1)
        preferred_kind = kind_for_support_rank(preferred_rank)
        if _family_has_match(exercises, family, preferred_kind):
            return SentenceSelectionDecision(
                policy_id=POLICY_FAMILY_SUPPORT_V1,
                family_id=family,
                preferred_kind=preferred_kind,
                preferred_support_rank=preferred_rank,
                reason="recent reliable incorrect → related scaffolding",
                motivating_event_id=row.skill_event_id,
            )
        soft = _first_family_exercise(exercises, family, max_rank=preferred_rank)
        if soft is not None:
            return SentenceSelectionDecision(
                policy_id=POLICY_FAMILY_SUPPORT_V1,
                family_id=family,
                preferred_kind=soft.kind,
                preferred_support_rank=support_rank_for_kind(soft.kind),
                reason="recent reliable incorrect → family fallback item",
                motivating_event_id=row.skill_event_id,
            )

    return SentenceSelectionDecision(
        policy_id=POLICY_FAMILY_SUPPORT_V1,
        family_id="",
        preferred_kind="",
        preferred_support_rank=-1,
        reason="no selection-relevant evidence; default pack order",
    )


def deterministic_initial_policy_notes() -> tuple[str, ...]:
    return (
        "Policy id: sentence-skill-family-support-v1.",
        "Recency window: 14 days; future-dated rows excluded.",
        "Provisional AI and non-selection outcomes never drive adaptation.",
        "Harder-level incorrect remains until same/harder reviewed correct resolves it.",
        "Easier assisted/reviewed success does not clear harder difficulty.",
        "No numeric mastery formula.",
    )


def _family_has_match(
    exercises: Sequence[SentenceExercise],
    family_id: str,
    kind: str,
) -> bool:
    return any(item.family_id == family_id and item.kind == kind for item in exercises)


def _first_family_exercise(
    exercises: Sequence[SentenceExercise],
    family_id: str,
    *,
    max_rank: Optional[int] = None,
) -> Optional[SentenceExercise]:
    members = [item for item in exercises if item.family_id == family_id]
    if max_rank is not None:
        members = [item for item in members if support_rank_for_kind(item.kind) <= max_rank]
    if not members:
        members = [item for item in exercises if item.family_id == family_id]
    if not members:
        return None
    members.sort(key=lambda item: support_rank_for_kind(item.kind))
    return members[0]


def pick_exercise_for_decision(
    exercises: Sequence[SentenceExercise],
    decision: SentenceSelectionDecision,
) -> Optional[SentenceExercise]:
    if not decision.family_id:
        return None
    for item in exercises:
        if item.family_id == decision.family_id and (
            not decision.preferred_kind or item.kind == decision.preferred_kind
        ):
            return item
    return _first_family_exercise(exercises, decision.family_id)
