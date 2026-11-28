"""Local deterministic grading and AI adapter for sentence practice.

Reviewed accepted answers are graded locally. Independent writing outside that
set may call the existing AIService boundary. AI feedback never becomes a
reviewed answer key. Unavailable or malformed AI results are provisional.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from typing import Callable, Optional, Sequence

from sentence_content import SentenceExercise

_PUNCT_RE = re.compile(r"[.!?,;:¡¿\"'“”‘’]+")
_SPACE_RE = re.compile(r"\s+")


def normalize_sentence(text: str, *, keep_case: bool = False) -> str:
    raw = str(text or "").strip()
    raw = _PUNCT_RE.sub("", raw)
    raw = _SPACE_RE.sub(" ", raw).strip()
    if not keep_case:
        raw = raw.casefold()
    return raw


def answers_match(learner: str, accepted: Sequence[str]) -> bool:
    left = normalize_sentence(learner)
    if not left:
        return False
    return any(left == normalize_sentence(item) for item in accepted or ())


def local_match(exercise: SentenceExercise, learner_answer: str) -> bool:
    return answers_match(learner_answer, exercise.accepted_answers)


@dataclass(frozen=True)
class SentenceGrade:
    """Outcome of one submission. Never mutates vocabulary progress."""

    status: str  # correct | incorrect | provisional | unavailable | empty
    matched_local: bool
    graded_by: str  # local | ai | none
    feedback: str = ""
    corrected_sentence: str = ""
    error_hint: str = ""
    score: float = 0.0


def grade_locally(exercise: SentenceExercise, learner_answer: str) -> SentenceGrade:
    text = str(learner_answer or "").strip()
    if not text:
        return SentenceGrade(
            status="empty",
            matched_local=False,
            graded_by="none",
            feedback="",
        )
    if local_match(exercise, text):
        return SentenceGrade(
            status="correct",
            matched_local=True,
            graded_by="local",
            feedback="",
            corrected_sentence=exercise.primary_answer(),
            score=1.0,
        )
    return SentenceGrade(
        status="incorrect",
        matched_local=False,
        graded_by="local",
        feedback="",
        corrected_sentence=exercise.primary_answer(),
        error_hint=_guess_local_hint(exercise, text),
        score=0.0,
    )


def _guess_local_hint(exercise: SentenceExercise, learner: str) -> str:
    """Conservative local hint only — not a full linguistic classifier."""
    from sentence_content import KIND_FILL_BLANK, KIND_WORD_BANK

    norm = normalize_sentence(learner)
    primary = normalize_sentence(exercise.primary_answer())
    if exercise.kind == KIND_WORD_BANK:
        return "word_order"
    if exercise.kind == KIND_FILL_BLANK:
        if "drink" in norm and "drinkt" in primary and "drinkt" not in norm:
            return "conjugation"
        return "conjugation"
    # Token overlap without full match → likely order or small form issue.
    left = set(norm.split())
    right = set(primary.split())
    if left and right and left == right:
        return "word_order"
    if left & right:
        return "grammar"
    return "vocabulary"


class FakeSentenceGradeProvider:
    """Deterministic provider for demos and tests. No network."""

    def __init__(self, *, mode: str = "accept_valid"):
        self.mode = mode
        self.calls = []

    def grade_answer(self, request):
        from ai.base import GradeResult

        self.calls.append(request)
        text = str(request.user_sentence or "").strip()
        if self.mode == "unavailable":
            from ai.base import AIError

            raise AIError("Sentence grading is unavailable.")
        if self.mode == "malformed":
            return GradeResult(
                is_correct_usage=False,
                score=float("nan"),
                feedback_vi="",
                corrected_sentence="",
                suggested_sentence="",
            )
        # Accept a known valid variant outside the reviewed set for the demo.
        valid_extra = normalize_sentence("Ik koop een fiets vandaag")
        ok = normalize_sentence(text) == valid_extra or normalize_sentence(text) == normalize_sentence(
            "I buy a bike"
        )
        if self.mode == "reject":
            ok = False
        return GradeResult(
            is_correct_usage=ok,
            score=0.88 if ok else 0.2,
            feedback_vi="Provisional AI note only." if ok else "Provisional: try again.",
            corrected_sentence="Ik koop een fiets." if not ok else text,
            suggested_sentence="Ik koop een fiets.",
        )


def grade_with_ai_service(service, exercise: SentenceExercise, learner_answer: str) -> SentenceGrade:
    """Synchronous AI grade through the existing service. No account proxy by default."""
    from ai.base import AIError

    try:
        result = service.grade_answer(
            target_word=exercise.target_lemma or exercise.prompt,
            user_sentence=learner_answer,
            meaning=exercise.translation_en or exercise.prompt,
            use_account_proxy=False,
        )
    except AIError as error:
        return SentenceGrade(
            status="unavailable",
            matched_local=False,
            graded_by="ai",
            feedback=str(error),
        )
    except Exception as error:  # noqa: BLE001 — boundary
        return SentenceGrade(
            status="unavailable",
            matched_local=False,
            graded_by="ai",
            feedback=str(error),
        )
    score = float(getattr(result, "score", 0.0) or 0.0)
    if score != score:  # NaN
        return SentenceGrade(
            status="provisional",
            matched_local=False,
            graded_by="ai",
            feedback="AI feedback was incomplete. This is not a definitive result.",
            corrected_sentence=str(getattr(result, "corrected_sentence", "") or ""),
            score=0.0,
        )
    # Score alone is not a linguistic class. Treat as provisional correctness only.
    if bool(getattr(result, "is_correct_usage", False)) and score >= 0.7:
        return SentenceGrade(
            status="provisional",
            matched_local=False,
            graded_by="ai",
            feedback=str(getattr(result, "feedback_vi", "") or "Looks usable (provisional)."),
            corrected_sentence=str(getattr(result, "corrected_sentence", "") or ""),
            score=score,
        )
    return SentenceGrade(
        status="provisional",
        matched_local=False,
        graded_by="ai",
        feedback=str(getattr(result, "feedback_vi", "") or "Needs another try (provisional)."),
        corrected_sentence=str(
            getattr(result, "corrected_sentence", "")
            or getattr(result, "suggested_sentence", "")
            or exercise.primary_answer()
        ),
        error_hint="grammar",
        score=score,
    )


def grade_async(
    window,
    *,
    service,
    exercise: SentenceExercise,
    learner_answer: str,
    on_done: Callable[[SentenceGrade], None],
    still_current: Optional[Callable[[], bool]] = None,
) -> None:
    """Grade via AIService and deliver on the Tk thread when the binding is current.

    Fake / deterministic providers run synchronously (no worker thread) so demos
    and tests are not blocked by Tk cross-thread `after` scheduling. Real
    network providers still use a background thread; results are queued and
    polled from the main loop.
    """

    provider = getattr(service, "provider", None)
    if isinstance(provider, FakeSentenceGradeProvider):
        grade = grade_with_ai_service(service, exercise, learner_answer)

        def deliver_sync():
            if callable(still_current) and not still_current():
                return
            on_done(grade)

        try:
            window.after(1, deliver_sync)
        except Exception:
            deliver_sync()
        return

    box: list = []

    def work():
        box.append(grade_with_ai_service(service, exercise, learner_answer))

    threading.Thread(target=work, daemon=True).start()

    def poll(remaining: int = 200):
        if callable(still_current) and not still_current():
            return
        if box:
            on_done(box[0])
            return
        if remaining <= 0:
            on_done(
                SentenceGrade(
                    status="unavailable",
                    matched_local=False,
                    graded_by="ai",
                    feedback="Grading timed out. This is not a definitive wrong answer.",
                )
            )
            return
        try:
            window.after(50, lambda: poll(remaining - 1))
        except Exception:
            pass
