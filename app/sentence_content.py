"""Versioned sentence exercise and grammar content contract (Phase 19.5A / R1).

Reviewed accepted answers are content, not AI drafts. Arbitrary vocabulary
examples are not answer keys. The contract is language-aware for all seven
study languages; only Dutch A1 ships a curated pack in this wave.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

CONTENT_FORMAT_VERSION = 1

KIND_WORD_BANK = "word_bank"
KIND_FILL_BLANK = "fill_blank"
KIND_GUIDED_WRITING = "guided_writing"
KIND_INDEPENDENT_WRITING = "independent_writing"

SUPPORT_ASSISTED = "assisted"
SUPPORT_INDEPENDENT = "independent"

REVIEW_CURATED_AUTHOR = "curated_author"
REVIEW_PENDING_EXPERT = "pending_expert_validation"

ROLE_SUBJECT = "subject"
ROLE_VERB = "verb"
ROLE_OBJECT = "object"
ROLE_ARTICLE = "article"
ROLE_OTHER = "other"

SENTENCE_COMPONENT_COLORS = {
    ROLE_SUBJECT: "#2C654E",
    ROLE_VERB: "#1F4E79",
    ROLE_OBJECT: "#6B4E16",
    ROLE_ARTICLE: "#5C7268",
    ROLE_OTHER: "#5C7268",
}

LADDER: Tuple[str, ...] = (
    KIND_WORD_BANK,
    KIND_FILL_BLANK,
    KIND_GUIDED_WRITING,
    KIND_INDEPENDENT_WRITING,
)

# Map conservative error hints to preferred grammar rule ids when present.
ERROR_RULE_PREFERENCE = {
    "conjugation": ("present-conjugation", "conjugation"),
    "word_order": ("svo", "word-order", "word_order"),
    "article": ("articles", "article"),
}


@dataclass(frozen=True)
class SentenceComponent:
    role: str
    text: str


@dataclass(frozen=True)
class GrammarRule:
    """Curated foundational grammar content. Not learner data."""

    rule_id: str
    language_code: str
    cefr: str
    title_en: str
    title_vi: str
    beginner_en: str
    beginner_vi: str
    full_en: str
    full_vi: str
    examples: Tuple[str, ...] = ()
    provenance: str = ""
    review_status: str = REVIEW_CURATED_AUTHOR
    content_version: int = CONTENT_FORMAT_VERSION
    topics: Tuple[str, ...] = ()


@dataclass(frozen=True)
class SentenceExercise:
    """One reviewed sentence exercise. Multiple accepted answers are first-class."""

    exercise_id: str
    language_code: str
    cefr: str
    kind: str
    support_level: str
    prompt: str
    translation_en: str
    translation_vi: str
    accepted_answers: Tuple[str, ...]
    family_id: str = ""
    target_lemma: str = ""
    target_vocab_id: str = ""
    word_bank: Tuple[str, ...] = ()
    blank_sentence: str = ""
    grammar_template: str = ""
    grammar_rule_ids: Tuple[str, ...] = ()
    components: Tuple[SentenceComponent, ...] = ()
    provenance: str = ""
    review_status: str = REVIEW_CURATED_AUTHOR
    content_version: int = CONTENT_FORMAT_VERSION
    notes: str = ""
    learning_objective: str = ""

    def primary_answer(self) -> str:
        return self.accepted_answers[0] if self.accepted_answers else ""


@dataclass(frozen=True)
class SentencePack:
    pack_id: str
    language_code: str
    cefr: str
    title: str
    exercises: Tuple[SentenceExercise, ...]
    rules: Tuple[GrammarRule, ...]
    content_version: int = CONTENT_FORMAT_VERSION
    review_checklist: Tuple[str, ...] = ()
    provenance: str = ""

    def rule_map(self) -> dict:
        return {rule.rule_id: rule for rule in self.rules}

    def by_kind(self, kind: str) -> Tuple[SentenceExercise, ...]:
        return tuple(item for item in self.exercises if item.kind == kind)

    def by_family(self, family_id: str) -> Tuple[SentenceExercise, ...]:
        fid = str(family_id or "").strip()
        return tuple(item for item in self.exercises if item.family_id == fid)

    def families(self) -> Tuple[str, ...]:
        seen = []
        for item in self.exercises:
            if item.family_id and item.family_id not in seen:
                seen.append(item.family_id)
        return tuple(seen)


def validate_exercise(exercise: SentenceExercise) -> Optional[str]:
    if not str(exercise.exercise_id or "").strip():
        return "exercise needs a stable id"
    if exercise.content_version != CONTENT_FORMAT_VERSION:
        return f"unsupported sentence content version {exercise.content_version}"
    if exercise.kind not in LADDER:
        return f"unknown sentence kind {exercise.kind!r}"
    if not exercise.accepted_answers:
        return "reviewed accepted answers are required"
    if exercise.kind == KIND_WORD_BANK and not exercise.word_bank:
        return "word-bank exercises need tokens"
    if exercise.kind == KIND_FILL_BLANK and "___" not in (exercise.blank_sentence or ""):
        return "fill-blank exercises need a ___ marker"
    if exercise.kind == KIND_GUIDED_WRITING and not exercise.grammar_template:
        return "guided writing needs a grammar template"
    if exercise.support_level not in (SUPPORT_ASSISTED, SUPPORT_INDEPENDENT):
        return f"unknown support level {exercise.support_level!r}"
    if exercise.kind == KIND_INDEPENDENT_WRITING and exercise.support_level != SUPPORT_INDEPENDENT:
        return "independent writing must use independent support"
    if exercise.kind != KIND_INDEPENDENT_WRITING and exercise.support_level != SUPPORT_ASSISTED:
        return "assisted levels must use assisted support"
    return None


def validate_pack(pack: SentencePack) -> list:
    problems = []
    if pack.content_version != CONTENT_FORMAT_VERSION:
        problems.append(f"unsupported pack version {pack.content_version}")
    seen = set()
    for exercise in pack.exercises:
        problem = validate_exercise(exercise)
        if problem:
            problems.append(f"{exercise.exercise_id}: {problem}")
        if exercise.exercise_id in seen:
            problems.append(f"duplicate exercise id {exercise.exercise_id}")
        seen.add(exercise.exercise_id)
        for rule_id in exercise.grammar_rule_ids:
            if rule_id not in pack.rule_map():
                problems.append(f"{exercise.exercise_id}: missing grammar rule {rule_id}")
    kinds = {item.kind for item in pack.exercises}
    for kind in LADDER:
        if kind not in kinds:
            problems.append(f"pack is missing exercise kind {kind}")
    # At least one family must cover all four levels.
    complete = False
    for family_id in pack.families():
        family_kinds = {item.kind for item in pack.by_family(family_id)}
        if family_kinds == set(LADDER):
            complete = True
            break
    if not complete:
        problems.append("pack needs at least one exercise family covering all four levels")
    return problems


def load_pack(language_code: str, cefr: str = "A1") -> SentencePack:
    code = str(language_code or "").strip().lower()
    level = str(cefr or "A1").strip().upper()
    if code == "nl" and level == "A1":
        from sentence_packs.nl_a1 import NL_A1_PACK

        problems = validate_pack(NL_A1_PACK)
        if problems:
            raise ValueError("; ".join(problems))
        return NL_A1_PACK
    raise LookupError(
        f"No curated sentence pack for {code}/{level}. "
        "The contract supports all seven study languages; only Dutch A1 is shipped."
    )


def future_sentence_skill_record_contract() -> tuple[str, ...]:
    """Documented before any persistent sentence history is introduced."""
    return (
        "SentenceSkillRecord is a separate append-only local skill file, not PracticeRecord v1.",
        "Fields: skill_event_id, exercise_id, family_id, content_version, language_code, kind, "
        "support_level, outcome, graded_by (local|ai|none), error_class, occurred_at, "
        "policy_id, format_version.",
        "It must never call Progress.record, change SRS, clear Mistake Book attention, "
        "or enqueue a vocabulary progress outbox event.",
        "AI-graded provisional results stay provisional until a future review workflow "
        "promotes an answer into reviewed content.",
        "Cloud Sync for sentence skill events requires an additive sync design and is "
        "not authorized in Phase 19.5A.",
    )


def future_ai_feedback_contract_extensions() -> tuple[str, ...]:
    """Structured feedback beyond the existing GradeResult score/flags."""
    return (
        "Primary error class enum (spelling, vocabulary, conjugation, word_order, grammar).",
        "Optional corrected_segment distinct from full corrected_sentence.",
        "Optional grammar_rule_id pointer into curated content (never a free-form invented rule).",
        "Confidence / provisional flag so unavailable or uncertain AI feedback is not a "
        "definitive wrong answer.",
        "These require a versioned GradeResult extension; score alone must not invent classes.",
    )


def provisional_acceptance_progression_policy() -> str:
    """Provisional AI acceptance may advance the ladder but is not reviewed correctness."""
    return (
        "When independent writing outside the reviewed set receives provisional_accept "
        "from the AI adapter (valid GradeResult, is_correct_usage true, finite score "
        "in [0, 1], score >= 0.7), the session may advance one level. Session results "
        "record outcome=provisional_accept (not correct). Learner feedback must say the "
        "acceptance is provisional. Reviewed correct remains only for local accepted_answers."
    )
