"""Versioned SentenceSkillRecord — append-only App-local evidence (Phase 19.5B).

Does not persist raw learner sentences, raw AI responses, or corrected text.
Does not write PracticeRecord v1, vocabulary SRS, Progress, or sync-outbox.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Optional
from uuid import uuid4

RECORD_FORMAT_VERSION = 1
POLICY_FAMILY_SUPPORT_V1 = "sentence-skill-family-support-v1"
SUPPORTED_POLICIES = frozenset({POLICY_FAMILY_SUPPORT_V1})

SUPPORTED_CEFR = frozenset({"A1", "A2", "B1", "B2", "C1", "C2"})
SUPPORTED_KINDS = frozenset(
    {"word_bank", "fill_blank", "guided_writing", "independent_writing"}
)
KIND_SUPPORT_RANK = {
    "word_bank": 0,
    "fill_blank": 1,
    "guided_writing": 2,
    "independent_writing": 3,
}

ERROR_CLASSIFICATIONS = frozenset(
    {
        "none",
        "conjugation",
        "word_order",
        "article",
        "vocabulary",
        "grammar",
        "unknown",
        "unclassified",
    }
)

OUTCOME_REVIEWED_CORRECT = "reviewed_correct"
OUTCOME_INCORRECT = "incorrect"
OUTCOME_PROVISIONAL_ACCEPT = "provisional_accept"
OUTCOME_PROVISIONAL_CORRECT = "provisional_correct"
OUTCOME_UNAVAILABLE = "unavailable"

# Outcomes that may be appended (incomplete / ungraded / empty are not learner failures).
RECORDABLE_OUTCOMES = frozenset(
    {
        OUTCOME_REVIEWED_CORRECT,
        OUTCOME_INCORRECT,
        OUTCOME_PROVISIONAL_ACCEPT,
        OUTCOME_PROVISIONAL_CORRECT,
        OUTCOME_UNAVAILABLE,
    }
)

# Outcomes that may influence future family/support selection (reliable evidence only).
SELECTION_RELEVANT_OUTCOMES = frozenset(
    {
        OUTCOME_REVIEWED_CORRECT,
        OUTCOME_INCORRECT,
    }
)

EVIDENCE_REVIEWED = "reviewed"
EVIDENCE_RELIABLE_LOCAL = "reliable_local"
EVIDENCE_PROVISIONAL_AI = "provisional_ai"
EVIDENCE_NONE = "none"
EVIDENCE_STATUSES = frozenset(
    {
        EVIDENCE_REVIEWED,
        EVIDENCE_RELIABLE_LOCAL,
        EVIDENCE_PROVISIONAL_AI,
        EVIDENCE_NONE,
    }
)

SOURCE_LOCAL = "local"
SOURCE_AI = "ai"
SOURCE_NONE = "none"


class SentenceSkillRecordError(ValueError):
    """Record failed validation."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    text = str(value or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        raise SentenceSkillRecordError("occurred_at must be timezone-aware UTC")
    return dt.astimezone(timezone.utc)


@dataclass(frozen=True)
class SentenceSkillRecord:
    skill_event_id: str
    session_id: str
    exercise_instance_id: str
    submission_id: str
    exercise_id: str
    family_id: str
    content_version: str
    format_version: int
    study_language: str
    cefr_level: str
    exercise_kind: str
    support_level: int
    outcome: str
    grading_source: str
    error_classification: str
    evidence_status: str
    grammar_skill_refs: tuple[str, ...]
    occurred_at: str
    selection_policy_id: str

    def as_dict(self) -> dict:
        return {
            "skill_event_id": self.skill_event_id,
            "session_id": self.session_id,
            "exercise_instance_id": self.exercise_instance_id,
            "submission_id": self.submission_id,
            "exercise_id": self.exercise_id,
            "family_id": self.family_id,
            "content_version": self.content_version,
            "format_version": self.format_version,
            "study_language": self.study_language,
            "cefr_level": self.cefr_level,
            "exercise_kind": self.exercise_kind,
            "support_level": self.support_level,
            "outcome": self.outcome,
            "grading_source": self.grading_source,
            "error_classification": self.error_classification,
            "evidence_status": self.evidence_status,
            "grammar_skill_refs": list(self.grammar_skill_refs),
            "occurred_at": self.occurred_at,
            "selection_policy_id": self.selection_policy_id,
        }


def new_skill_event_id() -> str:
    return str(uuid4())


def validate_sentence_skill_record(raw: Mapping[str, Any]) -> SentenceSkillRecord:
    if not isinstance(raw, Mapping):
        raise SentenceSkillRecordError("record must be an object")

    version_raw = raw.get("format_version")
    if isinstance(version_raw, bool) or not isinstance(version_raw, int):
        raise SentenceSkillRecordError("format_version must be an exact integer")
    format_version = version_raw
    if format_version != RECORD_FORMAT_VERSION:
        raise SentenceSkillRecordError(f"unsupported record format version {format_version}")

    outcome = str(raw.get("outcome") or "").strip()
    if outcome not in RECORDABLE_OUTCOMES:
        raise SentenceSkillRecordError(f"outcome {outcome!r} is not recordable")

    evidence = str(raw.get("evidence_status") or "").strip()
    if evidence not in EVIDENCE_STATUSES:
        raise SentenceSkillRecordError(f"unsupported evidence_status {evidence!r}")

    # Do not conflate provisional AI with reviewed correctness.
    if outcome in (OUTCOME_PROVISIONAL_ACCEPT, OUTCOME_PROVISIONAL_CORRECT):
        if evidence not in (EVIDENCE_PROVISIONAL_AI, EVIDENCE_NONE):
            raise SentenceSkillRecordError("provisional AI outcomes require provisional_ai/none evidence")
    if outcome == OUTCOME_REVIEWED_CORRECT and evidence == EVIDENCE_PROVISIONAL_AI:
        raise SentenceSkillRecordError("reviewed_correct cannot use provisional_ai evidence")
    if outcome == OUTCOME_INCORRECT and evidence == EVIDENCE_PROVISIONAL_AI:
        raise SentenceSkillRecordError("incorrect cannot use provisional_ai evidence")

    source = str(raw.get("grading_source") or "").strip()
    if source not in (SOURCE_LOCAL, SOURCE_AI, SOURCE_NONE):
        raise SentenceSkillRecordError(f"unsupported grading_source {source!r}")
    if outcome == OUTCOME_REVIEWED_CORRECT and source != SOURCE_LOCAL:
        raise SentenceSkillRecordError("reviewed_correct requires local grading_source")
    if outcome in (OUTCOME_PROVISIONAL_ACCEPT, OUTCOME_PROVISIONAL_CORRECT) and source != SOURCE_AI:
        raise SentenceSkillRecordError("provisional outcomes require ai grading_source")

    support_raw = raw.get("support_level")
    if isinstance(support_raw, bool) or not isinstance(support_raw, int):
        raise SentenceSkillRecordError("support_level must be an exact integer")
    support = support_raw
    if support < 0 or support > 3:
        raise SentenceSkillRecordError("support_level out of range")

    occurred_at = str(raw.get("occurred_at") or "").strip()
    parse_utc(occurred_at)  # validate

    refs_raw = raw.get("grammar_skill_refs") or ()
    if not isinstance(refs_raw, (list, tuple)):
        raise SentenceSkillRecordError("grammar_skill_refs must be a list")
    refs = tuple(str(item).strip() for item in refs_raw if str(item).strip())
    # Avoid assigning multiple failed skills from several rule refs on one sentence.
    if outcome == OUTCOME_INCORRECT and len(refs) > 1:
        refs = refs[:1]

    required = (
        "skill_event_id",
        "session_id",
        "exercise_instance_id",
        "submission_id",
        "exercise_id",
        "family_id",
        "content_version",
        "study_language",
        "cefr_level",
        "exercise_kind",
        "selection_policy_id",
    )
    values = {}
    for key in required:
        value = str(raw.get(key) or "").strip()
        if not value:
            raise SentenceSkillRecordError(f"{key} is required")
        values[key] = value

    study_language = values["study_language"].lower()
    try:
        from languages import is_supported_language

        if not is_supported_language(study_language):
            raise SentenceSkillRecordError(f"unsupported study_language {study_language!r}")
    except ImportError:
        pass
    values["study_language"] = study_language

    cefr = values["cefr_level"].upper()
    if cefr not in SUPPORTED_CEFR:
        raise SentenceSkillRecordError(f"unsupported cefr_level {cefr!r}")
    values["cefr_level"] = cefr

    kind = values["exercise_kind"]
    if kind not in SUPPORTED_KINDS:
        raise SentenceSkillRecordError(f"unsupported exercise_kind {kind!r}")
    if KIND_SUPPORT_RANK.get(kind) != support:
        raise SentenceSkillRecordError("support_level does not match exercise_kind")

    if values["selection_policy_id"] not in SUPPORTED_POLICIES:
        raise SentenceSkillRecordError(
            f"unsupported selection_policy_id {values['selection_policy_id']!r}"
        )

    error_classification = str(raw.get("error_classification") or "none").strip() or "none"
    if error_classification not in ERROR_CLASSIFICATIONS:
        raise SentenceSkillRecordError(
            f"unsupported error_classification {error_classification!r}"
        )
    # Unclassified local failure is not a confirmed specific grammar error — no rule refs.
    if error_classification in ("unclassified", "none", "unknown") and refs and outcome == OUTCOME_INCORRECT:
        if error_classification == "unclassified":
            refs = ()

    return SentenceSkillRecord(
        skill_event_id=values["skill_event_id"],
        session_id=values["session_id"],
        exercise_instance_id=values["exercise_instance_id"],
        submission_id=values["submission_id"],
        exercise_id=values["exercise_id"],
        family_id=values["family_id"],
        content_version=values["content_version"],
        format_version=format_version,
        study_language=values["study_language"],
        cefr_level=values["cefr_level"],
        exercise_kind=values["exercise_kind"],
        support_level=support,
        outcome=outcome,
        grading_source=source,
        error_classification=error_classification,
        evidence_status=evidence,
        grammar_skill_refs=refs,
        occurred_at=occurred_at,
        selection_policy_id=values["selection_policy_id"],
    )


def build_sentence_skill_record(
    *,
    session_id: str,
    exercise_instance_id: str,
    submission_id: str,
    exercise_id: str,
    family_id: str,
    content_version: str,
    study_language: str,
    cefr_level: str,
    exercise_kind: str,
    support_level: int,
    outcome: str,
    grading_source: str,
    error_classification: str,
    evidence_status: str,
    grammar_skill_refs: tuple[str, ...] = (),
    selection_policy_id: str = POLICY_FAMILY_SUPPORT_V1,
    skill_event_id: Optional[str] = None,
    occurred_at: Optional[str] = None,
) -> SentenceSkillRecord:
    payload = {
        "skill_event_id": skill_event_id or new_skill_event_id(),
        "session_id": session_id,
        "exercise_instance_id": exercise_instance_id,
        "submission_id": submission_id,
        "exercise_id": exercise_id,
        "family_id": family_id,
        "content_version": content_version,
        "format_version": RECORD_FORMAT_VERSION,
        "study_language": study_language,
        "cefr_level": cefr_level,
        "exercise_kind": exercise_kind,
        "support_level": support_level,
        "outcome": outcome,
        "grading_source": grading_source,
        "error_classification": error_classification or "none",
        "evidence_status": evidence_status,
        "grammar_skill_refs": list(grammar_skill_refs),
        "occurred_at": occurred_at or _utc_now_iso(),
        "selection_policy_id": selection_policy_id,
    }
    return validate_sentence_skill_record(payload)


def outcome_is_recordable(outcome: str) -> bool:
    return str(outcome or "").strip() in RECORDABLE_OUTCOMES


def outcome_affects_selection(outcome: str) -> bool:
    return str(outcome or "").strip() in SELECTION_RELEVANT_OUTCOMES
