"""Append-only practice events for recognition and assisted vocabulary.

A practice record is not a LearningAttempt and it is not an SRS review.
Independent recall keeps the existing attempt path. This module does not
open a database and does not call Progress.record.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, Sequence, Union

from languages import is_supported_language
from vocab_identity import is_vocab_id

FORMAT_VERSION = 1
POLICY_ID = "adaptive-vocab-session-v1"
EVIDENCE_DAYS = 14

INTRODUCTION = "introduction"
MULTIPLE_CHOICE = "multiple_choice"
MISSING_LETTERS = "missing_letters"
GUIDED_TYPING = "guided_typing"
INDEPENDENT_RECALL = "independent_recall"

LADDER: tuple[str, ...] = (
    INTRODUCTION,
    MULTIPLE_CHOICE,
    MISSING_LETTERS,
    GUIDED_TYPING,
    INDEPENDENT_RECALL,
)

PRACTICE_KINDS = (INTRODUCTION, MULTIPLE_CHOICE, MISSING_LETTERS, GUIDED_TYPING)
OUTCOMES = ("acknowledged", "exact", "near", "wrong")
SUCCESS_OUTCOMES = ("acknowledged", "exact")
FAILURE_OUTCOMES = ("near", "wrong")
# Conservative labels. A wrong answer is not diagnosed as a linguistic class.
ERROR_NEAR_MATCH = "near_match"
ERROR_INCORRECT = "incorrect_answer"
ERROR_CLASSES = ("", ERROR_NEAR_MATCH, ERROR_INCORRECT)
SUPPORT_LEVELS = ("recognition", "assisted")
SUPPORT_FOR_KIND = {
    INTRODUCTION: "recognition",
    MULTIPLE_CHOICE: "recognition",
    MISSING_LETTERS: "assisted",
    GUIDED_TYPING: "assisted",
}
REPEATED_FAILURES = 2


class PracticeRecordError(ValueError):
    """The event is not a valid practice record."""


@dataclass(frozen=True)
class PracticeRecord:
    """One submitted recognition or assisted exercise. No learner answer text."""

    practice_event_id: str
    exercise_instance_id: str
    session_id: str
    vocab_id: str
    language_code: str
    actual_kind: str
    intended_kind: str
    support_level: str
    outcome: str
    error_class: str
    occurred_at: str
    policy_id: str
    format_version: int


def _event_uuid(value: str) -> bool:
    try:
        uuid.UUID(str(value or "").strip())
    except (ValueError, TypeError, AttributeError):
        return False
    return True


def observable_error(kind: str, outcome: str) -> str:
    """Conservative observable categories only.

    A near answer is a near match. A wrong answer is an incorrect answer.
    Spelling, conjugation, word order, and grammar are not inferred.
    """
    del kind
    if outcome in ("acknowledged", "exact"):
        return ""
    if outcome == "near":
        return ERROR_NEAR_MATCH
    if outcome == "wrong":
        return ERROR_INCORRECT
    return ""


def build_practice_record(
    *,
    practice_event_id: str,
    exercise_instance_id: str,
    session_id: str,
    vocab_id: str,
    language_code: str,
    actual_kind: str,
    intended_kind: str,
    support_level: str,
    outcome: str,
    occurred_at: str,
) -> PracticeRecord:
    record = PracticeRecord(
        practice_event_id=str(practice_event_id or "").strip(),
        exercise_instance_id=str(exercise_instance_id or "").strip(),
        session_id=str(session_id or "").strip(),
        vocab_id=str(vocab_id or "").strip(),
        language_code=str(language_code or "").strip().lower(),
        actual_kind=str(actual_kind or "").strip(),
        intended_kind=str(intended_kind or "").strip(),
        support_level=str(support_level or "").strip(),
        outcome=str(outcome or "").strip(),
        error_class=observable_error(actual_kind, outcome),
        occurred_at=str(occurred_at or "").strip(),
        policy_id=POLICY_ID,
        format_version=FORMAT_VERSION,
    )
    validate_practice_record(record)
    return record


def validate_practice_record(record: PracticeRecord) -> None:
    if not isinstance(record, PracticeRecord):
        raise PracticeRecordError("practice record is missing")
    for name in ("practice_event_id", "exercise_instance_id", "session_id"):
        if not _event_uuid(getattr(record, name)):
            raise PracticeRecordError(f"{name} is not a UUID")
    if not is_vocab_id(record.vocab_id):
        raise PracticeRecordError("vocab_id is not a stable vocabulary UUID")
    if not is_supported_language(record.language_code):
        raise PracticeRecordError("study language is not supported")
    if record.actual_kind not in PRACTICE_KINDS:
        raise PracticeRecordError("actual exercise kind is not a practice exercise")
    if record.intended_kind not in LADDER:
        raise PracticeRecordError("intended exercise kind is not valid")
    if record.support_level not in SUPPORT_LEVELS:
        raise PracticeRecordError("support level is not recognition or assisted")
    if record.support_level != SUPPORT_FOR_KIND[record.actual_kind]:
        raise PracticeRecordError("support level does not match the exercise kind")
    if record.outcome not in OUTCOMES:
        raise PracticeRecordError("outcome is not valid")
    if record.outcome == "acknowledged" and record.actual_kind != INTRODUCTION:
        raise PracticeRecordError("only introduction is acknowledged")
    if record.actual_kind == INTRODUCTION and record.outcome != "acknowledged":
        raise PracticeRecordError("introduction is recorded as an acknowledgement")
    if record.actual_kind != INTRODUCTION and record.outcome == "acknowledged":
        raise PracticeRecordError("graded exercises are not acknowledgements")
    if record.error_class not in ERROR_CLASSES:
        raise PracticeRecordError("error class is not observable")
    if record.error_class != observable_error(record.actual_kind, record.outcome):
        raise PracticeRecordError("error class does not match the outcome")
    if record.policy_id != POLICY_ID:
        raise PracticeRecordError("policy id is not the adaptive session policy")
    if record.format_version != FORMAT_VERSION:
        raise PracticeRecordError("practice record version is not supported")
    if parse_practice_time(record.occurred_at) is None:
        raise PracticeRecordError("occurrence time is not UTC")


def parse_practice_time(value: Union[str, datetime, None]) -> Optional[datetime]:
    """Parse a timezone-aware UTC instant. Naive values are refused."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return None
        return value.astimezone(timezone.utc)
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def usable_practice(
    records: Sequence[PracticeRecord],
    *,
    now: Optional[datetime] = None,
    after: Optional[Union[str, datetime]] = None,
) -> list[PracticeRecord]:
    """Drop missing, stale, invalid, and unsupported records. Order is oldest first.

    When ``after`` is set, only practice strictly newer than that UTC instant is kept.
    Equal timestamps keep the caller's order, which for the store is append order.
    """
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    moment = moment.astimezone(timezone.utc)
    cutoff = moment - timedelta(days=EVIDENCE_DAYS)
    floor = parse_practice_time(after)
    kept = []
    for record in records or ():
        if not isinstance(record, PracticeRecord):
            continue
        if record.format_version != FORMAT_VERSION:
            continue
        try:
            validate_practice_record(record)
        except PracticeRecordError:
            continue
        occurred = parse_practice_time(record.occurred_at)
        if occurred is None or occurred < cutoff or occurred > moment + timedelta(minutes=5):
            continue
        if floor is not None and occurred <= floor:
            continue
        kept.append(record)
    # Stable sort: equal UTC times keep their incoming order (store uses rowid).
    kept.sort(key=lambda item: parse_practice_time(item.occurred_at) or datetime.min.replace(tzinfo=timezone.utc))
    return kept


def _lower(kind: str) -> str:
    index = LADDER.index(kind)
    return LADDER[max(0, index - 1)]


def _after_success(kind: str) -> str:
    """One step harder, and never independent recall from practice alone."""
    index = min(LADDER.index(kind) + 1, LADDER.index(GUIDED_TYPING))
    return LADDER[index]


def practice_start_level(
    base: str,
    records: Sequence[PracticeRecord],
    *,
    allow_promote: bool,
    now: Optional[datetime] = None,
    after: Optional[Union[str, datetime]] = None,
) -> str:
    """Conservative start. Repeated failures add support. Success cannot grant mastery."""
    if base not in LADDER:
        return INTRODUCTION
    usable = usable_practice(records, now=now, after=after)
    if not usable:
        return base
    failures = 0
    failed_kind = ""
    for record in reversed(usable):
        if record.outcome in FAILURE_OUTCOMES:
            failures += 1
            if not failed_kind:
                failed_kind = record.actual_kind
            continue
        break
    if failures >= REPEATED_FAILURES and failed_kind:
        easier = _lower(failed_kind)
        if allow_promote:
            return easier
        return LADDER[min(LADDER.index(base), LADDER.index(easier))]
    if not allow_promote:
        return base
    for record in reversed(usable):
        if record.outcome in SUCCESS_OUTCOMES:
            return _after_success(record.actual_kind)
    return base
