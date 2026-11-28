"""Progressive sentence practice engine (Phase 19.5A R1).

Four levels: word bank → fill blank → guided writing → independent writing.
Success advances. Failure steps down one level within the exercise family.
Session-memory results only — no vocabulary LearningAttempt, Progress, SRS,
Mistake Book, or outbox writes.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence, Set, Tuple

import config
from sentence_content import (
    KIND_FILL_BLANK,
    KIND_GUIDED_WRITING,
    KIND_INDEPENDENT_WRITING,
    KIND_WORD_BANK,
    LADDER,
    GrammarRule,
    SentenceExercise,
    SentencePack,
    load_pack,
    provisional_acceptance_progression_policy,
)
from sentence_grading import (
    STATUS_EMPTY,
    STATUS_INCOMPLETE,
    STATUS_INCORRECT,
    STATUS_PROVISIONAL_ACCEPT,
    STATUS_PROVISIONAL_CORRECT,
    STATUS_REVIEWED_CORRECT,
    STATUS_UNGRADED,
    STATUS_UNLISTED,
    STATUS_UNAVAILABLE,
    SentenceGrade,
    grade_locally,
    join_tokens,
)

MAX_FAILURES_PER_LEVEL = 2

# Outcomes that count as "achieved this level" for progress.
_LEVEL_ACHIEVED = frozenset({STATUS_REVIEWED_CORRECT, STATUS_PROVISIONAL_ACCEPT})


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class SentenceCard:
    exercise: SentenceExercise
    level_index: int
    attempt_on_level: int
    instance_id: str


@dataclass(frozen=True)
class SentenceSessionResult:
    """In-memory sentence result. Not a LearningAttempt or PracticeRecord."""

    result_id: str
    exercise_id: str
    family_id: str
    kind: str
    support_level: str
    outcome: str
    graded_by: str
    learner_answer: str
    error_hint: str
    occurred_at: str
    language_code: str
    content_version: int
    instance_id: str = ""
    submission_id: str = ""


@dataclass
class SentenceSubmitResult:
    status: str  # feedback | empty | incomplete | waiting_ai | stale
    grade: Optional[SentenceGrade] = None
    card: Optional[SentenceCard] = None
    submitted_exercise: Optional[SentenceExercise] = None
    advanced: bool = False
    stepped_down: bool = False
    session_finished: bool = False
    feedback: str = ""
    tone: str = "bad"
    submission_id: str = ""
    instance_id: str = ""


@dataclass
class SentencePracticeSession:
    """One optional sentence round. Separate from required vocabulary completion."""

    pack: SentencePack
    session_id: str = ""
    start_kind: str = KIND_WORD_BANK
    binding_id: str = ""
    language_code: str = ""
    finished: bool = False
    abandoned: bool = False
    missing_content: bool = False
    results: List[SentenceSessionResult] = field(default_factory=list)

    def __post_init__(self):
        self.session_id = self.session_id or uuid.uuid4().hex
        self.binding_id = self.binding_id or uuid.uuid4().hex
        self.language_code = self.language_code or self.pack.language_code
        self._level = LADDER.index(self.start_kind) if self.start_kind in LADDER else 0
        self._failures: Dict[str, int] = {kind: 0 for kind in LADDER}
        self._used_exercise_ids: Set[str] = set()
        self._achieved_levels: Set[int] = set()
        self._active_family: str = ""
        self._card: Optional[SentenceCard] = None
        self._completion_taken = False
        self._open_submission_id: str = ""
        self._pending_instance_id: str = ""
        if not self.pack.exercises:
            self.missing_content = True
            self.finished = False
            self._card = None
            return
        self._rebuild_card()
        if self._card is None and not self.abandoned:
            self.missing_content = True

    @classmethod
    def from_language(cls, language_code: str = "nl", cefr: str = "A1", **kwargs):
        return cls(load_pack(language_code, cefr), **kwargs)

    def current_card(self) -> Optional[SentenceCard]:
        return None if self.finished or self.abandoned or self.missing_content else self._card

    def levels_achieved(self) -> int:
        return len(self._achieved_levels)

    def progress_pair(self) -> Tuple[int, int]:
        """Distinct achieved levels / ladder length. Never exceeds 4/4 via repeats."""
        return min(self.levels_achieved(), len(LADDER)), len(LADDER)

    def rules_for(self, exercise: SentenceExercise) -> Tuple[GrammarRule, ...]:
        mapping = self.pack.rule_map()
        return tuple(mapping[rid] for rid in exercise.grammar_rule_ids if rid in mapping)

    def begin_submission(self) -> Optional[str]:
        """Bind a submission to the current card instance. None if not answerable."""
        card = self.current_card()
        if card is None or self._open_submission_id:
            return None
        self._open_submission_id = uuid.uuid4().hex
        self._pending_instance_id = card.instance_id
        return self._open_submission_id

    def clear_submission(self, submission_id: str = "") -> None:
        if submission_id and submission_id != self._open_submission_id:
            return
        self._open_submission_id = ""
        self._pending_instance_id = ""

    def submission_current(self, submission_id: str, instance_id: str = "") -> bool:
        if not submission_id or submission_id != self._open_submission_id:
            return False
        card = self._card
        if card is None:
            return False
        if instance_id and instance_id != card.instance_id:
            return False
        if self._pending_instance_id and card.instance_id != self._pending_instance_id:
            return False
        return True

    def _pick_exercise(self, kind: str, *, prefer_family: str = "") -> Optional[SentenceExercise]:
        family = prefer_family or self._active_family
        pool = list(self.pack.by_kind(kind))
        if not pool:
            return None

        def unused(items: Sequence[SentenceExercise]) -> List[SentenceExercise]:
            return [item for item in items if item.exercise_id not in self._used_exercise_ids]

        if family:
            related = [item for item in pool if item.family_id == family]
            related_unused = unused(related)
            if related_unused:
                return related_unused[0]
            if related:
                return related[0]
        unused_any = unused(pool)
        if unused_any:
            return unused_any[0]
        return pool[0]

    def _rebuild_card(self) -> None:
        if self.finished or self.abandoned or self.missing_content:
            self._card = None
            return
        kind = LADDER[self._level]
        exercise = self._pick_exercise(kind, prefer_family=self._active_family)
        if exercise is None:
            self.missing_content = True
            self._card = None
            return
        if exercise.family_id:
            self._active_family = exercise.family_id
        self._card = SentenceCard(
            exercise=exercise,
            level_index=self._level,
            attempt_on_level=self._failures[kind],
            instance_id=uuid.uuid4().hex,
        )

    def abandon(self) -> None:
        self.abandoned = True
        self._card = None
        self.clear_submission()

    def take_completion(self) -> bool:
        """True only for a real successful finish — not abandon or missing content."""
        if self.abandoned or self.missing_content or self._completion_taken:
            return False
        if not self.finished:
            return False
        if self.levels_achieved() < len(LADDER):
            return False
        self._completion_taken = True
        return True

    def submit_local(
        self,
        answer: str = "",
        *,
        tokens: Sequence[str] = (),
        submission_id: str = "",
        instance_id: str = "",
    ) -> SentenceSubmitResult:
        if self.finished or self.abandoned or self.missing_content or self._card is None:
            return SentenceSubmitResult(status="empty", session_finished=self.finished)
        if submission_id and not self.submission_current(submission_id, instance_id):
            return SentenceSubmitResult(status="stale", tone="near")
        exercise = self._card.exercise
        submitted = exercise
        grade = grade_locally(exercise, answer, tokens=tokens)
        if grade.status in (STATUS_EMPTY, STATUS_INCOMPLETE):
            self.clear_submission(submission_id)
            return SentenceSubmitResult(
                status="incomplete" if grade.status == STATUS_INCOMPLETE else "empty",
                grade=grade,
                card=self._card,
                submitted_exercise=submitted,
                tone="empty",
                submission_id=submission_id,
                instance_id=self._card.instance_id,
                feedback=_incomplete_feedback() if grade.status == STATUS_INCOMPLETE else "",
            )
        if grade.status == STATUS_UNLISTED:
            # Caller should route to AI; do not record a failure.
            return SentenceSubmitResult(
                status="waiting_ai",
                grade=grade,
                card=self._card,
                submitted_exercise=submitted,
                tone="near",
                submission_id=submission_id or self._open_submission_id,
                instance_id=self._card.instance_id,
            )
        return self._apply_grade(
            grade,
            join_tokens(tokens) if tokens else str(answer or "").strip(),
            submitted_exercise=submitted,
            submission_id=submission_id or self._open_submission_id,
            instance_id=self._card.instance_id,
        )

    def apply_external_grade(
        self,
        grade: SentenceGrade,
        learner_answer: str,
        *,
        submission_id: str = "",
        instance_id: str = "",
    ) -> SentenceSubmitResult:
        """Apply an AI / async grade. Stale bindings are ignored."""
        if self.finished or self.abandoned or self.missing_content or self._card is None:
            return SentenceSubmitResult(status="stale", session_finished=self.finished)
        if submission_id and not self.submission_current(submission_id, instance_id):
            return SentenceSubmitResult(status="stale", tone="near")
        submitted = self._card.exercise
        if grade.status in (STATUS_UNAVAILABLE, STATUS_UNGRADED):
            self.clear_submission(submission_id)
            # Unavailable AI is not a learner failure — no failure count / step-down.
            note = grade.feedback or config.ui(
                "Chưa chấm được. Đây không phải lỗi của bạn. Tiến độ từ vựng không đổi.",
                "Grading is unavailable. This is not counted as a failure. Vocabulary progress is unchanged.",
            )
            return SentenceSubmitResult(
                status="feedback",
                grade=grade,
                card=self._card,
                submitted_exercise=submitted,
                feedback=note,
                tone="near",
                submission_id=submission_id,
                instance_id=self._card.instance_id,
            )
        if grade.status == STATUS_PROVISIONAL_CORRECT:
            self.clear_submission(submission_id)
            return SentenceSubmitResult(
                status="feedback",
                grade=grade,
                card=self._card,
                submitted_exercise=submitted,
                feedback=_provisional_correct_feedback(grade),
                tone="near",
                submission_id=submission_id,
                instance_id=self._card.instance_id,
            )
        if grade.status == STATUS_PROVISIONAL_ACCEPT:
            # May advance; remains provisional in session results (not reviewed_correct).
            _ = provisional_acceptance_progression_policy()
            return self._apply_grade(
                grade,
                learner_answer,
                submitted_exercise=submitted,
                submission_id=submission_id,
                instance_id=self._card.instance_id,
            )
        return self._apply_grade(
            grade,
            learner_answer,
            submitted_exercise=submitted,
            submission_id=submission_id,
            instance_id=self._card.instance_id,
        )

    def _apply_grade(
        self,
        grade: SentenceGrade,
        learner_answer: str,
        *,
        submitted_exercise: SentenceExercise,
        submission_id: str = "",
        instance_id: str = "",
    ) -> SentenceSubmitResult:
        exercise = submitted_exercise
        kind = exercise.kind
        level_index = self._level
        self.results.append(
            SentenceSessionResult(
                result_id=uuid.uuid4().hex,
                exercise_id=exercise.exercise_id,
                family_id=exercise.family_id,
                kind=kind,
                support_level=exercise.support_level,
                outcome=grade.status,
                graded_by=grade.graded_by,
                learner_answer=learner_answer,
                error_hint=grade.error_hint,
                occurred_at=utc_now_iso(),
                language_code=self.language_code,
                content_version=exercise.content_version,
                instance_id=instance_id,
                submission_id=submission_id,
            )
        )
        self.clear_submission(submission_id)

        if grade.status in _LEVEL_ACHIEVED:
            self._used_exercise_ids.add(exercise.exercise_id)
            self._failures[kind] = 0
            self._achieved_levels.add(level_index)
            if exercise.family_id:
                self._active_family = exercise.family_id
            advanced = False
            finished = False
            if self.levels_achieved() >= len(LADDER) and level_index >= len(LADDER) - 1:
                self.finished = True
                finished = True
                self._card = None
            elif level_index >= len(LADDER) - 1:
                # Top level achieved — finish only when all levels achieved.
                if self.levels_achieved() >= len(LADDER):
                    self.finished = True
                    finished = True
                    self._card = None
                else:
                    # Should not happen if ladder is climbed sequentially.
                    self._rebuild_card()
            else:
                self._level += 1
                advanced = True
                self._rebuild_card()
            return SentenceSubmitResult(
                status="feedback",
                grade=grade,
                card=self._card,
                submitted_exercise=exercise,
                advanced=advanced,
                session_finished=finished,
                feedback=_success_feedback(exercise, grade),
                tone="ok" if grade.status == STATUS_REVIEWED_CORRECT else "near",
                submission_id=submission_id,
                instance_id=instance_id,
            )

        # Incorrect: step down after repeated failure; prefer related family item.
        self._failures[kind] = int(self._failures.get(kind, 0) or 0) + 1
        if exercise.family_id:
            self._active_family = exercise.family_id
        stepped = False
        if self._failures[kind] >= MAX_FAILURES_PER_LEVEL and self._level > 0:
            self._level -= 1
            self._failures[LADDER[self._level]] = 0
            stepped = True
            self._rebuild_card()
        else:
            self._used_exercise_ids.add(exercise.exercise_id)
            self._rebuild_card()
        return SentenceSubmitResult(
            status="feedback",
            grade=grade,
            card=self._card,
            submitted_exercise=exercise,
            stepped_down=stepped,
            feedback=_failure_feedback(exercise, grade, stepped_down=stepped),
            tone="bad",
            submission_id=submission_id,
            instance_id=instance_id,
        )

    def continue_after_feedback(self) -> SentenceSubmitResult:
        if self.finished:
            return SentenceSubmitResult(status="feedback", session_finished=True)
        if self.abandoned or self.missing_content:
            return SentenceSubmitResult(status="empty")
        if self._card is None:
            self._rebuild_card()
        return SentenceSubmitResult(
            status="feedback",
            card=self._card,
            session_finished=self.finished,
        )

    def offer_easier_related(self) -> SentenceSubmitResult:
        """Explicit learner recovery: step down one related level without a failure count.

        Used when independent/guided writing is unlisted, provisionally corrected,
        unavailable, or ungraded. Does not count as a learner failure.
        """
        if self.finished or self.abandoned or self.missing_content:
            return SentenceSubmitResult(status="empty", session_finished=self.finished)
        self.clear_submission()
        if self._level <= 0:
            self._rebuild_card()
            return SentenceSubmitResult(
                status="feedback",
                card=self._card,
                feedback=config.ui(
                    "Đang ở mức dễ nhất trong gia đình bài này.",
                    "You are already on the easiest related step.",
                ),
                tone="near",
            )
        current = self._card.exercise if self._card else None
        if current and current.family_id:
            self._active_family = current.family_id
        self._level -= 1
        self._failures[LADDER[self._level]] = 0
        self._rebuild_card()
        return SentenceSubmitResult(
            status="feedback",
            card=self._card,
            stepped_down=True,
            feedback=config.ui(
                "Thử bài dễ hơn cùng mục tiêu học.",
                "Try an easier related exercise for the same learning goal.",
            ),
            tone="near",
        )


def _incomplete_feedback() -> str:
    return config.ui(
        "Hãy dùng đủ các từ trong ngân hàng từ.",
        "Use all of the word-bank tokens first.",
    )


def _success_feedback(exercise: SentenceExercise, grade: SentenceGrade) -> str:
    if grade.status == STATUS_PROVISIONAL_ACCEPT:
        return config.ui(
            "Tạm chấp nhận (chưa phải đáp án đã duyệt). Tiếp tục được.",
            "Provisionally accepted (not a reviewed answer). You can continue.",
        )
    return {
        KIND_WORD_BANK: config.ui("Đúng câu rồi.", "That's the sentence."),
        KIND_FILL_BLANK: config.ui("Đúng dạng rồi.", "That's the right form."),
        KIND_GUIDED_WRITING: config.ui(
            "Hay — khớp với mẫu.",
            "Nice — that matches the pattern.",
        ),
        KIND_INDEPENDENT_WRITING: config.ui(
            "Câu ổn.",
            "That's a solid sentence.",
        ),
    }.get(exercise.kind, config.ui("Đúng rồi.", "That's it."))


def _provisional_correct_feedback(grade: SentenceGrade) -> str:
    base = grade.feedback or config.ui(
        "Gợi ý tạm thời — chưa chấm sai chắc chắn.",
        "Provisional suggestion — not a definitive wrong mark.",
    )
    if grade.corrected_sentence:
        return config.ui(
            f"{base} Gợi ý: {grade.corrected_sentence}",
            f"{base} Suggestion: {grade.corrected_sentence}",
        )
    return base


def _failure_feedback(
    exercise: SentenceExercise, grade: SentenceGrade, *, stepped_down: bool
) -> str:
    hint = grade.error_hint or ""
    if hint == "conjugation" and grade.diagnosis_certain:
        line = config.ui(
            "Động từ cần dạng hiện tại.",
            "The verb needs the present form.",
        )
    elif hint == "word_order" and grade.diagnosis_certain:
        line = config.ui(
            "Đủ từ rồi, nhưng thứ tự chưa đúng.",
            "The words are right, but the order is not.",
        )
    elif hint == "article" and grade.diagnosis_certain:
        line = config.ui(
            "Kiểm tra mạo từ (de/het/een).",
            "Check the article (de/het/een).",
        )
    else:
        line = config.ui("Chưa đúng.", "Not quite.")
    if stepped_down:
        labels = {
            KIND_WORD_BANK: config.ui(
                "Thử sắp xếp các từ.",
                "Try arranging the words.",
            ),
            KIND_FILL_BLANK: config.ui(
                "Thử điền chỗ trống.",
                "Try the fill-in-the-blank.",
            ),
            KIND_GUIDED_WRITING: config.ui(
                "Thử câu có mẫu.",
                "Try the guided sentence.",
            ),
        }
        idx = LADDER.index(exercise.kind) if exercise.kind in LADDER else 0
        easier = LADDER[max(0, idx - 1)]
        return f"{line} {labels.get(easier, config.ui('Thử bước dễ hơn.', 'Try an easier step.'))}"
    corrected = grade.corrected_sentence or exercise.primary_answer()
    return config.ui(
        f"{line} Một đáp án đã duyệt: {corrected}",
        f"{line} One reviewed answer is: {corrected}",
    )
