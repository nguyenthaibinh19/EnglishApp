"""Study Session Runner — domain orchestration from DailyStudyPlan.

Coordinates Vocabulary / Reading / Listening modules. No Tkinter. No network.

Activity order: vocabulary → reading → listening (when present).
Completion: all required activities completed; optional ones completed,
skipped, or unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from daily_study import DailyStudyPlan

KIND_VOCABULARY = "vocabulary"
KIND_READING = "reading"
KIND_LISTENING = "listening"

STATUS_PENDING = "pending"
STATUS_ACTIVE = "active"
STATUS_COMPLETED = "completed"
STATUS_SKIPPED = "skipped"
STATUS_UNAVAILABLE = "unavailable"

_RESOLVED_OPTIONAL = frozenset(
    {STATUS_COMPLETED, STATUS_SKIPPED, STATUS_UNAVAILABLE}
)
_STARTABLE = frozenset({STATUS_PENDING, STATUS_ACTIVE})


class StudySessionError(ValueError):
    """Illegal session state transition."""


@dataclass(frozen=True)
class StudyActivity:
    kind: str
    required: bool


def build_study_session(plan: DailyStudyPlan) -> "StudySession":
    """Create a session from a DailyStudyPlan (authoritative planning input)."""
    activities: List[StudyActivity] = []
    if int(plan.planned_vocab_count or 0) > 0:
        activities.append(StudyActivity(KIND_VOCABULARY, required=True))
    if plan.reading_enabled:
        activities.append(StudyActivity(KIND_READING, required=False))
    if getattr(plan, "listening_enabled", False):
        activities.append(StudyActivity(KIND_LISTENING, required=False))
    return StudySession(plan, activities)


class StudySession:
    """Runtime state for one language's study launch."""

    def __init__(self, plan: DailyStudyPlan, activities: Sequence[StudyActivity]):
        self.plan = plan
        self.language_code = plan.language_code
        self.planned_vocab_count = int(plan.planned_vocab_count or 0)
        self._activities: List[StudyActivity] = list(activities)
        self._by_kind: Dict[str, StudyActivity] = {a.kind: a for a in self._activities}
        self._statuses: Dict[str, str] = {a.kind: STATUS_PENDING for a in self._activities}
        self._active_kind: Optional[str] = None

    # ---------- queries ----------

    def activities(self) -> Tuple[StudyActivity, ...]:
        return tuple(self._activities)

    def has_activity(self, kind: str) -> bool:
        return kind in self._by_kind

    def status(self, kind: str) -> Optional[str]:
        return self._statuses.get(kind)

    def is_resolved(self, kind: str) -> bool:
        activity = self._by_kind.get(kind)
        if activity is None:
            return True
        status = self._statuses[kind]
        if activity.required:
            return status == STATUS_COMPLETED
        return status in _RESOLVED_OPTIONAL

    @property
    def required_complete(self) -> bool:
        return all(
            self.is_resolved(activity.kind)
            for activity in self._activities
            if activity.required
        )

    @property
    def can_finish(self) -> bool:
        return all(self.is_resolved(activity.kind) for activity in self._activities)

    def vocabulary_complete(self) -> bool:
        if not self.has_activity(KIND_VOCABULARY):
            return True
        return self._statuses[KIND_VOCABULARY] == STATUS_COMPLETED

    def next_activity(self) -> Optional[StudyActivity]:
        """First unfinished activity in fixed order (pending preferred)."""
        for activity in self._activities:
            status = self._statuses[activity.kind]
            if status in (STATUS_PENDING, STATUS_ACTIVE):
                return activity
        return None

    def summary_statuses(self) -> Dict[str, str]:
        return {kind: self._statuses[kind] for kind in self._statuses}

    # ---------- transitions ----------

    def start(self, kind: str) -> None:
        activity = self._require(kind)
        status = self._statuses[kind]
        if status == STATUS_ACTIVE:
            return
        if status != STATUS_PENDING:
            raise StudySessionError(
                f"cannot start {kind} from status {status!r}"
            )
        self._statuses[kind] = STATUS_ACTIVE
        self._active_kind = kind

    def complete(self, kind: str) -> None:
        self._require(kind)
        status = self._statuses[kind]
        if status == STATUS_COMPLETED:
            return  # idempotent
        if status not in _STARTABLE:
            raise StudySessionError(
                f"cannot complete {kind} from status {status!r}"
            )
        self._statuses[kind] = STATUS_COMPLETED
        if self._active_kind == kind:
            self._active_kind = None

    def skip(self, kind: str) -> None:
        activity = self._require(kind)
        if activity.required:
            raise StudySessionError(f"cannot skip required activity {kind!r}")
        status = self._statuses[kind]
        if status in (STATUS_SKIPPED, STATUS_COMPLETED, STATUS_UNAVAILABLE):
            return  # already resolved
        if status not in (STATUS_PENDING, STATUS_ACTIVE):
            raise StudySessionError(
                f"cannot skip {kind} from status {status!r}"
            )
        self._statuses[kind] = STATUS_SKIPPED
        if self._active_kind == kind:
            self._active_kind = None

    def mark_unavailable(self, kind: str) -> None:
        activity = self._require(kind)
        if activity.required:
            raise StudySessionError(
                f"cannot mark required activity {kind!r} unavailable"
            )
        status = self._statuses[kind]
        if status == STATUS_UNAVAILABLE:
            return
        if status == STATUS_COMPLETED:
            return
        if status not in (STATUS_PENDING, STATUS_ACTIVE, STATUS_SKIPPED):
            raise StudySessionError(
                f"cannot mark {kind} unavailable from status {status!r}"
            )
        self._statuses[kind] = STATUS_UNAVAILABLE
        if self._active_kind == kind:
            self._active_kind = None

    def set_optional_enabled(self, kind: str, enabled: bool) -> None:
        """Add/remove an optional activity without wiping other progress."""
        if kind == KIND_VOCABULARY:
            raise StudySessionError("vocabulary requirement is fixed by the plan")
        if enabled:
            if kind in self._by_kind:
                return
            activity = StudyActivity(kind, required=False)
            self._activities.append(activity)
            self._by_kind[kind] = activity
            self._statuses[kind] = STATUS_PENDING
            return
        # disabled → remove if present (does not affect vocabulary)
        if kind not in self._by_kind:
            return
        self._activities = [a for a in self._activities if a.kind != kind]
        self._by_kind.pop(kind, None)
        self._statuses.pop(kind, None)
        if self._active_kind == kind:
            self._active_kind = None

    def _require(self, kind: str) -> StudyActivity:
        activity = self._by_kind.get(kind)
        if activity is None:
            raise StudySessionError(f"unknown activity {kind!r}")
        return activity
