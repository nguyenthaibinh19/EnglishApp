"""Progressive sentence practice engine (Phase 19.5A).

Four levels: word bank → fill blank → guided writing → independent writing.
Success advances. Failure steps down one level. Session-memory results only —
no vocabulary LearningAttempt, Progress, SRS, Mistake Book, or outbox writes.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence, Tuple

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
)
from sentence_grading import SentenceGrade, grade_locally

MAX_FAILURES_PER_LEVEL = 2


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class SentenceCard:
    exercise: SentenceExercise
    level_index: int
    attempt_on_level: int


@dataclass(frozen=True)
class SentenceSessionResult:
    """In-memory sentence result. Not a LearningAttempt or PracticeRecord."""

    result_id: str
    exercise_id: str
    kind: str
    support_level: str
    outcome: str
    graded_by: str
    learner_answer: str
    error_hint: str
    occurred_at: str
    language_code: str
    content_version: int


@dataclass
class SentenceSubmitResult:
    status: str  # feedback | empty | waiting_ai
    grade: Optional[SentenceGrade] = None
    card: Optional[SentenceCard] = None
    advanced: bool = False
    stepped_down: bool = False
    session_finished: bool = False
    feedback: str = ""
    tone: str = "bad"


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
    results: List[SentenceSessionResult] = field(default_factory=list)

    def __post_init__(self):
        self.session_id = self.session_id or uuid.uuid4().hex
        self.binding_id = self.binding_id or uuid.uuid4().hex
        self.language_code = self.language_code or self.pack.language_code
        self._level = LADDER.index(self.start_kind) if self.start_kind in LADDER else 0
        self._failures: Dict[str, int] = {kind: 0 for kind in LADDER}
        self._used_exercise_ids: set = set()
        self._card: Optional[SentenceCard] = None
        self._completion_taken = False
        self._rebuild_card()

    @classmethod
    def from_language(cls, language_code: str = "nl", cefr: str = "A1", **kwargs):
        return cls(load_pack(language_code, cefr), **kwargs)

    def current_card(self) -> Optional[SentenceCard]:
        return None if self.finished or self.abandoned else self._card

    def rules_for(self, exercise: SentenceExercise) -> Tuple[GrammarRule, ...]:
        mapping = self.pack.rule_map()
        return tuple(mapping[rid] for rid in exercise.grammar_rule_ids if rid in mapping)

    def _pick_exercise(self, kind: str) -> Optional[SentenceExercise]:
        candidates = [
            item
            for item in self.pack.by_kind(kind)
            if item.exercise_id not in self._used_exercise_ids
        ]
        if not candidates:
            candidates = list(self.pack.by_kind(kind))
        if not candidates:
            return None
        return candidates[0]

    def _rebuild_card(self) -> None:
        if self.finished or self.abandoned:
            self._card = None
            return
        kind = LADDER[self._level]
        exercise = self._pick_exercise(kind)
        if exercise is None:
            self.finished = True
            self._card = None
            return
        self._card = SentenceCard(
            exercise=exercise,
            level_index=self._level,
            attempt_on_level=self._failures[kind],
        )

    def abandon(self) -> None:
        self.abandoned = True
        self._card = None

    def take_completion(self) -> bool:
        if not self.finished or self.abandoned or self._completion_taken:
            return False
        self._completion_taken = True
        return True

    def submit_local(self, answer: str = "", *, tokens: Sequence[str] = ()) -> SentenceSubmitResult:
        if self.finished or self.abandoned or self._card is None:
            return SentenceSubmitResult(status="empty", session_finished=self.finished)
        exercise = self._card.exercise
        text = " ".join(str(t) for t in tokens).strip() if tokens else str(answer or "").strip()
        # Re-join word-bank punctuation cleanly.
        if tokens:
            text = _join_tokens(tokens)
        grade = grade_locally(exercise, text)
        if grade.status == "empty":
            return SentenceSubmitResult(status="empty", grade=grade, card=self._card, tone="empty")
        return self._apply_grade(grade, text)

    def apply_external_grade(self, grade: SentenceGrade, learner_answer: str) -> SentenceSubmitResult:
        """Apply an AI / async grade. Provisional correct advances; unavailable does not fail."""
        if self.finished or self.abandoned or self._card is None:
            return SentenceSubmitResult(status="empty", session_finished=self.finished)
        if grade.status == "unavailable":
            return SentenceSubmitResult(
                status="feedback",
                grade=grade,
                card=self._card,
                feedback=grade.feedback
                or "Grading is unavailable. Your vocabulary progress is unchanged.",
                tone="near",
            )
        if grade.status == "provisional":
            # Strong provisional accept may advance the ladder, but never becomes a
            # reviewed answer key. Weak/uncertain provisional is not a definitive wrong.
            if grade.score >= 0.7 and not grade.error_hint:
                promoted = SentenceGrade(
                    status="correct",
                    matched_local=False,
                    graded_by=grade.graded_by,
                    feedback=grade.feedback,
                    corrected_sentence=grade.corrected_sentence,
                    score=grade.score,
                )
                return self._apply_grade(promoted, learner_answer)
            return SentenceSubmitResult(
                status="feedback",
                grade=grade,
                card=self._card,
                feedback=grade.feedback
                or "This answer is provisional. It is not a definitive wrong mark.",
                tone="near",
            )
        return self._apply_grade(grade, learner_answer)

    def _apply_grade(self, grade: SentenceGrade, learner_answer: str) -> SentenceSubmitResult:
        exercise = self._card.exercise
        kind = exercise.kind
        self.results.append(
            SentenceSessionResult(
                result_id=uuid.uuid4().hex,
                exercise_id=exercise.exercise_id,
                kind=kind,
                support_level=exercise.support_level,
                outcome=grade.status,
                graded_by=grade.graded_by,
                learner_answer=learner_answer,
                error_hint=grade.error_hint,
                occurred_at=utc_now_iso(),
                language_code=self.language_code,
                content_version=exercise.content_version,
            )
        )
        if grade.status == "correct":
            self._used_exercise_ids.add(exercise.exercise_id)
            self._failures[kind] = 0
            advanced = False
            finished = False
            if self._level >= len(LADDER) - 1:
                self.finished = True
                finished = True
                self._card = None
            else:
                self._level += 1
                advanced = True
                self._rebuild_card()
            return SentenceSubmitResult(
                status="feedback",
                grade=grade,
                card=self._card,
                advanced=advanced,
                session_finished=finished,
                feedback=_success_feedback(exercise),
                tone="ok",
            )

        # Incorrect: step down after repeated failure; never infinite loop.
        self._failures[kind] = int(self._failures.get(kind, 0) or 0) + 1
        stepped = False
        if self._failures[kind] >= MAX_FAILURES_PER_LEVEL and self._level > 0:
            self._level -= 1
            self._failures[LADDER[self._level]] = 0
            stepped = True
            self._rebuild_card()
        else:
            # Stay on level with a different unused item when possible.
            self._used_exercise_ids.add(exercise.exercise_id)
            self._rebuild_card()
            if self._card and self._card.exercise.exercise_id == exercise.exercise_id:
                # Only one item — keep it but reset attempt counter soft-cap by stepping message.
                pass
        return SentenceSubmitResult(
            status="feedback",
            grade=grade,
            card=self._card,
            stepped_down=stepped,
            feedback=_failure_feedback(exercise, grade, stepped_down=stepped),
            tone="bad",
        )

    def continue_after_feedback(self) -> SentenceSubmitResult:
        if self.finished:
            return SentenceSubmitResult(status="feedback", session_finished=True)
        if self._card is None:
            self._rebuild_card()
        return SentenceSubmitResult(
            status="feedback",
            card=self._card,
            session_finished=self.finished,
        )


def _join_tokens(tokens: Sequence[str]) -> str:
    parts = [str(t) for t in tokens if str(t).strip() != ""]
    if not parts:
        return ""
    out = parts[0]
    for token in parts[1:]:
        if token in {".", "!", "?", ",", ";", ":"}:
            out += token
        else:
            out += " " + token
    return out.strip()


def _success_feedback(exercise: SentenceExercise) -> str:
    return {
        KIND_WORD_BANK: "That's the sentence.",
        KIND_FILL_BLANK: "That's the right form.",
        KIND_GUIDED_WRITING: "Nice — that matches the pattern.",
        KIND_INDEPENDENT_WRITING: "That's a solid sentence.",
    }.get(exercise.kind, "That's it.")


def _failure_feedback(exercise: SentenceExercise, grade: SentenceGrade, *, stepped_down: bool) -> str:
    hint = grade.error_hint or ""
    if hint == "conjugation":
        line = "The verb needs the present form."
    elif hint == "word_order":
        line = "The words are right, but the order is not."
    elif hint == "vocabulary":
        line = "That wording does not match the prompt."
    else:
        line = "Not quite."
    if stepped_down:
        labels = {
            KIND_WORD_BANK: "Try arranging the words.",
            KIND_FILL_BLANK: "Try the fill-in-the-blank.",
            KIND_GUIDED_WRITING: "Try the guided sentence.",
        }
        idx = LADDER.index(exercise.kind) if exercise.kind in LADDER else 0
        easier = LADDER[max(0, idx - 1)]
        return f"{line} {labels.get(easier, 'Try an easier step.')}"
    corrected = grade.corrected_sentence or exercise.primary_answer()
    return f"{line} One reviewed answer is: {corrected}"
