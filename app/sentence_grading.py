"""Local deterministic grading and AI adapter for sentence practice (19.5A R1).

Reviewed accepted answers are graded locally. Independent writing outside that
set may call the existing AIService boundary. AI feedback never becomes a
reviewed answer key. Unavailable or malformed AI results are ungraded.
"""

from __future__ import annotations

import math
import re
import threading
from collections import Counter
from dataclasses import dataclass
from typing import Callable, Optional, Sequence

from sentence_content import (
    KIND_FILL_BLANK,
    KIND_GUIDED_WRITING,
    KIND_INDEPENDENT_WRITING,
    KIND_WORD_BANK,
    SentenceExercise,
)

# Terminal punctuation kept for display/join; stripped for matching.
_MATCH_PUNCT_RE = re.compile(r"[.!?,;:¡¿\"'“”‘’]+")
_SPACE_RE = re.compile(r"\s+")
_LATIN_WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]+")

STATUS_REVIEWED_CORRECT = "reviewed_correct"
STATUS_INCORRECT = "incorrect"
STATUS_INCOMPLETE = "incomplete"
STATUS_UNLISTED = "unlisted"
STATUS_PROVISIONAL_ACCEPT = "provisional_accept"
STATUS_PROVISIONAL_CORRECT = "provisional_correct"
STATUS_UNAVAILABLE = "unavailable"
STATUS_UNGRADED = "ungraded"
STATUS_EMPTY = "empty"


def normalize_sentence(text: str, *, keep_case: bool = False) -> str:
    raw = str(text or "").strip()
    raw = _MATCH_PUNCT_RE.sub("", raw)
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


def join_tokens(tokens: Sequence[str]) -> str:
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


def word_bank_complete(exercise: SentenceExercise, tokens: Sequence[str]) -> bool:
    """True when selected tokens use the full bank multiplicity (punctuation optional)."""
    bank = [str(t) for t in exercise.word_bank]
    selected = [str(t) for t in tokens]
    if not selected:
        return False
    bank_words = [t for t in bank if t not in {".", "!", "?", ",", ";", ":"}]
    selected_words = [t for t in selected if t not in {".", "!", "?", ",", ";", ":"}]
    return Counter(selected_words) == Counter(bank_words)


def word_bank_multiplicity_ok(exercise: SentenceExercise, tokens: Sequence[str]) -> bool:
    """Reject selections that over-use a token beyond the bank."""
    bank_counts = Counter(str(t) for t in exercise.word_bank)
    selected_counts = Counter(str(t) for t in tokens)
    for token, count in selected_counts.items():
        if count > bank_counts.get(token, 0):
            return False
    return True


@dataclass(frozen=True)
class SentenceGrade:
    """Outcome of one submission. Never mutates vocabulary progress.

    GradeResult meaning/required fields are unchanged. Optional ``structured``
    is App-domain StructuredSentenceFeedback validated at the trust boundary.
    """

    status: str
    matched_local: bool
    graded_by: str  # local | ai | none
    feedback: str = ""
    corrected_sentence: str = ""
    error_hint: str = ""
    score: float = 0.0
    diagnosis_certain: bool = False
    structured: object = None  # Optional[StructuredSentenceFeedback]
    original_segment: str = ""
    corrected_segment: str = ""


def grade_locally(
    exercise: SentenceExercise,
    learner_answer: str = "",
    *,
    tokens: Sequence[str] = (),
) -> SentenceGrade:
    if exercise.kind == KIND_WORD_BANK and tokens is not None and tuple(tokens) != ():
        if not word_bank_multiplicity_ok(exercise, tokens):
            return SentenceGrade(
                status=STATUS_INCOMPLETE,
                matched_local=False,
                graded_by="none",
                feedback="",
                error_hint="",
            )
        if not word_bank_complete(exercise, tokens):
            return SentenceGrade(
                status=STATUS_INCOMPLETE,
                matched_local=False,
                graded_by="none",
                feedback="",
            )
        text = join_tokens(tokens)
    else:
        text = str(learner_answer or "").strip()

    if not text:
        return SentenceGrade(
            status=STATUS_EMPTY,
            matched_local=False,
            graded_by="none",
            feedback="",
        )

    if local_match(exercise, text):
        grade = SentenceGrade(
            status=STATUS_REVIEWED_CORRECT,
            matched_local=True,
            graded_by="local",
            feedback="",
            corrected_sentence=exercise.primary_answer(),
            score=1.0,
            diagnosis_certain=True,
        )
        return _with_structured(grade, exercise, text)

    # Word bank / fill blank: constrained → definite incorrect when complete.
    if exercise.kind in (KIND_WORD_BANK, KIND_FILL_BLANK):
        hint, certain = _conservative_local_hint(exercise, text)
        original_seg, corrected_seg = _local_segments(exercise, text, hint, certain)
        grade = SentenceGrade(
            status=STATUS_INCORRECT,
            matched_local=False,
            graded_by="local",
            feedback="",
            corrected_sentence=exercise.primary_answer(),
            error_hint=hint,
            score=0.0,
            diagnosis_certain=certain,
            original_segment=original_seg,
            corrected_segment=corrected_seg,
        )
        return _with_structured(grade, exercise, text)

    # Guided writing: only definite incorrect for evidenced template violations.
    # Other unlisted answers stay unlisted (not automatic linguistic wrong).
    if exercise.kind == KIND_GUIDED_WRITING:
        hint, certain = _conservative_local_hint(exercise, text)
        if certain and hint in ("article", "word_order", "conjugation"):
            original_seg, corrected_seg = _local_segments(exercise, text, hint, certain)
            grade = SentenceGrade(
                status=STATUS_INCORRECT,
                matched_local=False,
                graded_by="local",
                feedback="",
                corrected_sentence=exercise.primary_answer(),
                error_hint=hint,
                score=0.0,
                diagnosis_certain=True,
                original_segment=original_seg,
                corrected_segment=corrected_seg,
            )
            return _with_structured(grade, exercise, text)
        return SentenceGrade(
            status=STATUS_UNLISTED,
            matched_local=False,
            graded_by="none",
            feedback="",
            corrected_sentence="",
            score=0.0,
            diagnosis_certain=False,
        )

    # Independent writing outside reviewed set is unlisted — not definitive wrong.
    return SentenceGrade(
        status=STATUS_UNLISTED,
        matched_local=False,
        graded_by="none",
        feedback="",
        corrected_sentence="",
        score=0.0,
        diagnosis_certain=False,
    )


def _local_segments(
    exercise: SentenceExercise,
    learner: str,
    hint: str,
    certain: bool,
) -> tuple[str, str]:
    if not certain or not hint:
        return "", ""
    norm = normalize_sentence(learner)
    primary = normalize_sentence(exercise.primary_answer())
    left = norm.split()
    right = primary.split()
    if hint == "conjugation":
        expected_verb = ""
        for part in exercise.components:
            if part.role == "verb":
                expected_verb = part.text
                break
        if not expected_verb:
            return "", ""
        expected_norm = normalize_sentence(expected_verb)
        typed = ""
        if " " not in norm:
            typed = learner.strip()
        else:
            frame = [token for token in right if token != expected_norm]
            extras = [token for token in left if token not in frame]
            typed = extras[0] if extras else ""
        if typed and expected_verb:
            return typed[:120], expected_verb[:120]
        return "", ""
    if hint == "word_order" and left and right and Counter(left) == Counter(right):
        # Highlight first differing token pair when order differs.
        for a, b in zip(left, right):
            if a != b:
                return a[:120], b[:120]
        return "", ""
    if hint == "article":
        for part in exercise.components:
            if part.role == "article":
                return "", part.text[:120]
    return "", ""


def _with_structured(grade: SentenceGrade, exercise: SentenceExercise, learner_answer: str) -> SentenceGrade:
    from sentence_feedback import feedback_from_local_grade

    rule_id = ""
    if grade.diagnosis_certain and exercise.grammar_rule_ids:
        # Prefer a single rule matching the error; never invent unrelated refs.
        from sentence_content import ERROR_RULE_PREFERENCE

        preferred = ERROR_RULE_PREFERENCE.get(grade.error_hint, ())
        for rid in exercise.grammar_rule_ids:
            if any(token in rid for token in preferred):
                rule_id = rid
                break
        if not rule_id and grade.error_hint:
            rule_id = exercise.grammar_rule_ids[0] if len(exercise.grammar_rule_ids) == 1 else ""

    structured = feedback_from_local_grade(
        status=grade.status,
        error_hint=grade.error_hint,
        diagnosis_certain=grade.diagnosis_certain,
        corrected_sentence=grade.corrected_sentence,
        explanation=grade.feedback,
        grammar_rule_id=rule_id,
        original_segment=grade.original_segment,
        corrected_segment=grade.corrected_segment,
        learner_answer=learner_answer,
        exercise=exercise,
    )
    if structured is None:
        return grade
    return SentenceGrade(
        status=grade.status,
        matched_local=grade.matched_local,
        graded_by=grade.graded_by,
        feedback=grade.feedback,
        corrected_sentence=grade.corrected_sentence,
        error_hint=grade.error_hint,
        score=grade.score,
        diagnosis_certain=grade.diagnosis_certain,
        structured=structured,
        original_segment=grade.original_segment,
        corrected_segment=grade.corrected_segment,
    )


def _related_verb_form(typed: str, expected: str) -> bool:
    """True when the typed token looks like a related finite/infinitive of expected."""
    if not typed or not expected:
        return False
    if typed == expected:
        return True
    if typed + "t" == expected or typed == expected[:-1]:
        return True
    # Infinitive -en vs finite -t/-d with a shared onset (Dutch A1 stems).
    if typed.endswith("en") and expected.endswith(("t", "d")) and len(typed) >= 4:
        if typed[:2] == expected[:2]:
            return True
        stem = typed[:-2]
        core = expected[:-1]
        if len(stem) >= 2 and (
            core.startswith(stem[:2])
            or stem.startswith(core[:2])
            or expected.startswith(stem[:2])
        ):
            return True
    # Shared prefix of at least 3 letters with a short length delta.
    shared = 0
    for a, b in zip(typed, expected):
        if a != b:
            break
        shared += 1
    return shared >= 3 and abs(len(typed) - len(expected)) <= 3


def _conservative_local_hint(exercise: SentenceExercise, learner: str) -> tuple[str, bool]:
    """Return (hint, certain). Prefer empty/uncertain over over-claiming."""
    norm = normalize_sentence(learner)
    primary = normalize_sentence(exercise.primary_answer())
    left = norm.split()
    right = primary.split()

    if exercise.kind == KIND_WORD_BANK:
        # Complete bank uses the same tokens; wrong order is evidenced.
        if Counter(left) == Counter(right):
            return "word_order", True
        return "word_order", True

    if exercise.kind == KIND_FILL_BLANK:
        blank = exercise.blank_sentence or ""
        if "___" not in blank:
            return "", False
        expected_verb = None
        for part in exercise.components:
            if part.role == "verb":
                expected_verb = normalize_sentence(part.text)
                break
        if not expected_verb:
            return "", False
        typed = norm
        if " " not in typed:
            if typed == expected_verb:
                return "", True
            # Only claim conjugation when the token is related to the expected verb.
            if _related_verb_form(typed, expected_verb):
                return "conjugation", True
            return "", False
        # Full-sentence: conjugation only if frame matches and a related wrong verb appears.
        if expected_verb not in left:
            frame_tokens = [token for token in right if token != expected_verb]
            if all(token in left for token in frame_tokens):
                extras = [token for token in left if token not in frame_tokens]
                if extras and any(_related_verb_form(token, expected_verb) for token in extras):
                    return "conjugation", True
        return "", False

    # Guided writing: article omission / pure reorder only when evidenced.
    if exercise.kind == KIND_GUIDED_WRITING:
        articles = {
            normalize_sentence(part.text)
            for part in exercise.components
            if part.role == "article"
        }
        if articles and not (articles & set(left)) and Counter(left) != Counter(right):
            if set(left) | articles == set(right) or set(left) == set(right) - articles:
                return "article", True
        if left and right and Counter(left) == Counter(right):
            return "word_order", True
        return "", False

    return "", False


class FakeSentenceGradeProvider:
    """Simulated development grading provider. No network. Not live AI.

    Supports an optional structured-feedback capability via duck typing.
    Old providers are not required to implement a new abstract method.
    """

    SIMULATED_LABEL = (
        "Simulated development grading — not a live AI call."
    )

    def __init__(self, *, mode: str = "accept_valid", structured: bool = True):
        self.mode = mode
        self.calls = []
        self.structured_calls = []
        self.simulated = True
        self.supports_structured_feedback = bool(structured)

    def grade_answer(self, request):
        from ai.base import GradeResult

        self.calls.append(request)
        text = str(request.user_sentence or "").strip()
        study = getattr(request, "study_language", None)
        study_code = ""
        if study is not None:
            study_code = str(getattr(study, "code", study) or "").strip().lower()

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
        if self.mode == "malformed_bool":
            # Intentionally invalid boolean-like payload via wrong type on score path.
            return GradeResult(
                is_correct_usage="yes",  # type: ignore[arg-type]
                score=0.9,
                feedback_vi="bad",
                corrected_sentence="",
                suggested_sentence="",
            )
        if self.mode == "malformed_structured":
            # GradeResult itself is valid; structured payload (if requested) is bad.
            return GradeResult(
                is_correct_usage=True,
                score=0.9,
                feedback_vi="Provisional (simulated) note only.",
                corrected_sentence=text,
                suggested_sentence="Zij leest een boek.",
            )

        # Never accept English for a Dutch exercise.
        if study_code in ("nl", "dutch") or _looks_dutch_target(request):
            if _looks_english_sentence(text) and not _looks_dutch_sentence(text):
                return GradeResult(
                    is_correct_usage=False,
                    score=0.15,
                    feedback_vi="Provisional (simulated): write the sentence in Dutch.",
                    corrected_sentence="Zij leest een boek.",
                    suggested_sentence="Zij leest een boek.",
                )

        valid_extra = normalize_sentence("Zij leest een boek vandaag")
        ok = normalize_sentence(text) == valid_extra
        if self.mode == "reject":
            ok = False
        if self.mode == "correct":
            ok = False
            return GradeResult(
                is_correct_usage=False,
                score=0.35,
                feedback_vi="Provisional (simulated): try the present form.",
                corrected_sentence="Zij leest een boek.",
                suggested_sentence="Zij leest een boek.",
            )
        if self.mode == "invalid_rule_ref":
            ok = False
            return GradeResult(
                is_correct_usage=False,
                score=0.4,
                feedback_vi="Provisional (simulated): try again.",
                corrected_sentence="Zij leest een boek.",
                suggested_sentence="Zij leest een boek.",
            )
        return GradeResult(
            is_correct_usage=ok,
            score=0.88 if ok else 0.25,
            feedback_vi=(
                "Provisional (simulated) note only."
                if ok
                else "Provisional (simulated): try again."
            ),
            corrected_sentence=text if ok else "Zij leest een boek.",
            suggested_sentence="Zij leest een boek.",
        )

    def structured_sentence_feedback(self, request, *, exercise=None):
        """Optional capability. Not part of AIProvider ABC."""
        from sentence_feedback import (
            ERROR_UNKNOWN,
            ERROR_UNCLASSIFIED,
            FEEDBACK_FORMAT_VERSION,
            SOURCE_AI,
            STATUS_PROVISIONAL_ACCEPT,
            STATUS_PROVISIONAL_CORRECT,
            STATUS_UNGRADED,
        )

        self.structured_calls.append(request)
        if not self.supports_structured_feedback:
            raise AttributeError("structured feedback unsupported")
        if self.mode == "malformed_structured":
            return {
                "format_version": FEEDBACK_FORMAT_VERSION,
                "grading_status": STATUS_PROVISIONAL_ACCEPT,
                "grading_source": SOURCE_AI,
                "provenance": "fake-malformed",
                "primary_error_class": ERROR_UNCLASSIFIED,
                "original_segment": "",
                "corrected_segment": "",
                "corrected_sentence": "",
                "grammar_rule_id": "",
                "explanation": "ok",
                "provisional": "yes",  # invalid — must not coerce
                "certainty": 0.9,
            }
        if self.mode == "invalid_rule_ref":
            return {
                "format_version": FEEDBACK_FORMAT_VERSION,
                "grading_status": STATUS_PROVISIONAL_CORRECT,
                "grading_source": SOURCE_AI,
                "provenance": "fake-invalid-rule",
                "primary_error_class": ERROR_UNKNOWN,
                "original_segment": "",
                "corrected_segment": "",
                "corrected_sentence": "Zij leest een boek.",
                "grammar_rule_id": "totally-unrelated-future-perfect",
                "explanation": "Provisional (simulated): invents an untrusted rule.",
                "provisional": True,
                "certainty": 0.4,
            }

        result = self.grade_answer(request)
        problem = _validate_grade_result(result)
        if problem:
            return {
                "format_version": FEEDBACK_FORMAT_VERSION,
                "grading_status": STATUS_UNGRADED,
                "grading_source": SOURCE_AI,
                "provenance": "fake-ungraded",
                "primary_error_class": ERROR_UNKNOWN,
                "original_segment": "",
                "corrected_segment": "",
                "corrected_sentence": "",
                "grammar_rule_id": "",
                "explanation": "AI feedback was incomplete. This is not a definitive result.",
                "provisional": True,
                "certainty": 0.0,
            }
        text = str(request.user_sentence or "").strip()
        ok = bool(result.is_correct_usage) and float(result.score) >= 0.7
        return {
            "format_version": FEEDBACK_FORMAT_VERSION,
            "grading_status": STATUS_PROVISIONAL_ACCEPT if ok else STATUS_PROVISIONAL_CORRECT,
            "grading_source": SOURCE_AI,
            "provenance": "fake-structured",
            "primary_error_class": ERROR_UNCLASSIFIED if ok else ERROR_UNKNOWN,
            "original_segment": "",
            "corrected_segment": "",
            "corrected_sentence": str(result.corrected_sentence or "")[:240],
            "grammar_rule_id": "",
            "explanation": str(result.feedback_vi or "")[:400],
            "provisional": True,
            "certainty": min(max(float(result.score), 0.0), 1.0),
            "_learner_echo": text,  # ignored by validator
        }


def _looks_dutch_target(request) -> bool:
    meaning = str(getattr(request, "meaning", "") or "")
    word = str(getattr(request, "target_word", "") or "")
    return word in ("lezen", "drinken", "kopen") or "book" in meaning.lower()


def _looks_english_sentence(text: str) -> bool:
    norm = normalize_sentence(text)
    english_markers = ("she reads", "i buy", "a book", "the book", "i drink")
    return any(marker in norm for marker in english_markers)


def _looks_dutch_sentence(text: str) -> bool:
    norm = normalize_sentence(text)
    dutch_markers = ("zij ", "ze ", "ik ", "hij ", "een ", "het ", "de ")
    return any(norm.startswith(m.strip()) or f" {m.strip()} " in f" {norm} " for m in dutch_markers)


def _validate_grade_result(result) -> Optional[str]:
    """Return a problem string if GradeResult fields are malformed."""
    flag = getattr(result, "is_correct_usage", None)
    if not isinstance(flag, bool):
        return "is_correct_usage must be a boolean"
    score = getattr(result, "score", None)
    try:
        value = float(score)
    except (TypeError, ValueError):
        return "score must be numeric"
    if not math.isfinite(value):
        return "score must be finite"
    if value < 0.0 or value > 1.0:
        return "score must be in [0, 1]"
    return None


def grade_with_ai_service(service, exercise: SentenceExercise, learner_answer: str) -> SentenceGrade:
    """Synchronous AI grade through the existing service. No account proxy by default.

    Tries optional structured-feedback capability first; otherwise degrades from
    GradeResult. Unsupported capability degrades gracefully. Never changes
    GradeResult required fields or deployed /api/grade.
    """
    from ai.base import AIError, GradeRequest
    from languages import get_language
    from sentence_feedback import (
        StructuredFeedbackError,
        feedback_from_grade_result,
        validate_structured_feedback,
    )

    provider = getattr(service, "provider", None)
    structured = None
    if provider is not None and getattr(provider, "supports_structured_feedback", False):
        builder = getattr(provider, "structured_sentence_feedback", None)
        if callable(builder):
            try:
                request = GradeRequest(
                    target_word=exercise.target_lemma or exercise.prompt,
                    user_sentence=learner_answer,
                    meaning=exercise.translation_en or exercise.prompt,
                    study_language=get_language(exercise.language_code),
                    level=exercise.cefr,
                )
                raw = builder(request, exercise=exercise)
                structured = validate_structured_feedback(
                    raw,
                    learner_answer=learner_answer,
                    exercise=exercise,
                    allowed_rule_ids=exercise.grammar_rule_ids,
                )
            except StructuredFeedbackError:
                structured = None  # degrade — never invent trusted explanations
            except Exception:
                structured = None

    try:
        result = service.grade_answer(
            target_word=exercise.target_lemma or exercise.prompt,
            user_sentence=learner_answer,
            meaning=exercise.translation_en or exercise.prompt,
            profile={"code": exercise.language_code},
            level=exercise.cefr,
            use_account_proxy=False,
        )
    except AIError as error:
        return SentenceGrade(
            status=STATUS_UNAVAILABLE,
            matched_local=False,
            graded_by="ai",
            feedback=str(error),
        )
    except Exception as error:  # noqa: BLE001 — boundary
        return SentenceGrade(
            status=STATUS_UNAVAILABLE,
            matched_local=False,
            graded_by="ai",
            feedback=str(error),
        )

    problem = _validate_grade_result(result)
    if problem:
        return SentenceGrade(
            status=STATUS_UNGRADED,
            matched_local=False,
            graded_by="ai",
            feedback="AI feedback was incomplete. This is not a definitive result.",
            corrected_sentence="",
            score=0.0,
            structured=structured,
        )

    score = float(result.score)
    corrected = str(getattr(result, "corrected_sentence", "") or "").strip()
    suggested = str(getattr(result, "suggested_sentence", "") or "").strip()
    note = str(getattr(result, "feedback_vi", "") or "").strip()

    if structured is None:
        try:
            structured = feedback_from_grade_result(
                result,
                learner_answer=learner_answer,
                exercise=exercise,
            )
        except StructuredFeedbackError:
            structured = None

    # Never invent a grammar error class from score alone.
    if result.is_correct_usage and score >= 0.7:
        return SentenceGrade(
            status=STATUS_PROVISIONAL_ACCEPT,
            matched_local=False,
            graded_by="ai",
            feedback=note or "Looks usable (provisional).",
            corrected_sentence=corrected or learner_answer,
            score=score,
            diagnosis_certain=False,
            structured=structured,
        )

    return SentenceGrade(
        status=STATUS_PROVISIONAL_CORRECT,
        matched_local=False,
        graded_by="ai",
        feedback=note or "Needs another try (provisional).",
        corrected_sentence=corrected or suggested or exercise.primary_answer(),
        error_hint="",
        score=score,
        diagnosis_certain=False,
        structured=structured,
    )


def grade_async(
    window,
    *,
    service,
    exercise: SentenceExercise,
    learner_answer: str,
    on_done: Callable[[SentenceGrade], None],
    still_current: Optional[Callable[[], bool]] = None,
    submission_id: str = "",
) -> None:
    """Grade via AIService and deliver on the Tk thread when the binding is current."""

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
                    status=STATUS_UNAVAILABLE,
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
