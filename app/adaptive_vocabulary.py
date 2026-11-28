"""Adaptive vocabulary ladder. Pure session state. No Tkinter and no SRS writes.

Exercise difficulty moves inside one session. The SRS ladder still decides when
a word is due. Recognition and assisted submissions can return a practice
event. This module does not store that event and does not write SRS. Only a
submitted independent recall returns a write for the existing attempt path.

Policy id ``adaptive-vocab-session-v1`` is not an SRS algorithm id.
"""

from __future__ import annotations

import random
import uuid
from collections import deque
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Deque, Dict, Iterable, List, Optional, Sequence

import config
from srs import is_due, is_new, utc_now
from text_utils import accepted_forms, display_word, entry_word, match_answer, normalize
from vocabulary_model import entry_example, entry_meaning
from vocab_identity import entry_id

from practice_record import POLICY_ID, parse_practice_time, practice_start_level

STEP_DOWN_FAILURES = 2
# Soft cap used only to prefer another planned word. It never removes a word.
PRESENTATION_CAP = 48
# Compact study content width. The window minimum is 480; this stays inside it.
STUDY_CONTENT_WIDTH = 420
MAX_MASK_ROWS = 4
# Blank, fixed glyph, and space gap, in pixels, matching the card widgets.
_MASK_METRICS = {
    "missing_letters": (40, 22, 12),
    "guided_typing": (26, 24, 14),
}

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

SUPPORT = {
    INTRODUCTION: "recognition",
    MULTIPLE_CHOICE: "recognition",
    MISSING_LETTERS: "assisted",
    GUIDED_TYPING: "assisted",
    INDEPENDENT_RECALL: "independent",
}

def _kicker(kind: str) -> str:
    labels = {
        INTRODUCTION: ("Làm quen", "Introduction"),
        MULTIPLE_CHOICE: ("Chọn từ", "Choose"),
        MISSING_LETTERS: ("Điền chữ", "Fill the letters"),
        GUIDED_TYPING: ("Gõ từ", "Type the word"),
        INDEPENDENT_RECALL: ("Tự nhớ", "Recall"),
    }
    vi, en = labels[kind]
    return config.ui(vi, en)


@dataclass(frozen=True)
class ExerciseCard:
    kind: str
    intended_kind: str
    support_level: str
    vocab_id: str
    language_code: str
    kicker: str
    prompt: str
    show_word: str = ""
    show_meaning: str = ""
    show_example: str = ""
    choices: tuple[str, ...] = ()
    correct_index: int = -1
    mask: str = ""
    guidance: str = ""
    reveal_word: str = ""
    accepted_answers: tuple[str, ...] = ()
    exercise_instance_id: str = ""


@dataclass(frozen=True)
class IndependentWrite:
    """One authoritative independent submission. Hint stays false.

    Assistance never becomes this record. A near verdict is session-correct
    and mastered is false.
    """

    vocab_id: str
    language_code: str
    word: str
    user_answer: str
    expected_answer: str
    prompt: str
    verdict: str
    mastered: bool
    hint_used: bool = False


@dataclass(frozen=True)
class SubmitResult:
    status: str
    success: Optional[bool] = None
    verdict: str = ""
    tone: str = ""
    feedback: str = ""
    write: Optional[IndependentWrite] = None
    completed_word: bool = False
    session_finished: bool = False
    practice: object = None


@dataclass(frozen=True)
class SpeechPlan:
    allowed: bool
    text: str = ""
    reason: str = ""


@dataclass
class _WordState:
    vocab_id: str
    level: int
    consecutive_failures: int = 0
    assist_depth: int = 1
    completed: bool = False
    presentations: int = 0


@dataclass
class _Pending:
    vocab_id: str
    action: str
    write: Optional[IndependentWrite] = None


@dataclass
class SessionCounters:
    planned: int = 0
    words_completed: int = 0
    independent_answered: int = 0
    independent_session_correct: int = 0
    independent_mastered: int = 0
    recognition_successes: int = 0
    assisted_successes: int = 0


def speech_for_card(card: Optional[ExerciseCard], phase: str) -> SpeechPlan:
    """Hearing the answer is allowed on introduction and after a checked card."""
    if card is None:
        return SpeechPlan(False, reason="no card")
    if phase == "answer" and card.kind == INTRODUCTION and card.show_word:
        return SpeechPlan(True, text=card.show_word)
    if phase == "feedback" and card.reveal_word:
        return SpeechPlan(True, text=card.reveal_word)
    if phase == "answer":
        return SpeechPlan(False, reason="answer stays hidden until check")
    return SpeechPlan(False, reason="nothing to speak")


def mask_target(word: str, rng: random.Random) -> Optional[str]:
    """Hide some letters. Spaces and punctuation stay. None when nothing meaningful remains."""
    chars = list(word or "")
    letters = [index for index, char in enumerate(chars) if char.isalpha()]
    if len(letters) < 2:
        return None
    hide_count = min(max(1, len(letters) // 2), len(letters) - 1)
    hidden = set(rng.sample(letters, hide_count))
    masked = "".join("_" if index in hidden else char for index, char in enumerate(chars))
    if "_" not in masked:
        return None
    return masked


def guided_reveal_count(word: str, depth: int) -> int:
    """How many leading characters to show. Never the whole word when it is longer than one."""
    text = word or ""
    level = min(max(int(depth), 1), 3)
    if len(text) > 1:
        return min(level, len(text) - 1)
    return 0


def guided_pattern(word: str, depth: int) -> str:
    """Prefix plus the word shape. Unrevealed letters are underscores. Spaces stay visible."""
    text = word or ""
    reveal = guided_reveal_count(text, depth)
    chars = []
    for index, char in enumerate(text):
        if index < reveal or not char.isalpha():
            chars.append(char)
        else:
            chars.append("_")
    return "".join(chars)


def guided_guidance(word: str, depth: int) -> str:
    """Short learner line. The pattern carries the prefix. Policy levels stay off the card."""
    del word, depth
    return config.ui("Gõ cả từ.", "Type the whole word.")


def reconstruct_mask(mask: str, fills: Sequence[str]) -> str:
    """Put one learner character into each blank. Fixed characters, spaces and marks stay."""
    pieces = []
    cursor = 0
    supplied = list(fills or ())
    for char in mask or "":
        if char != "_":
            pieces.append(char)
            continue
        piece = ""
        if cursor < len(supplied):
            raw = str(supplied[cursor] or "")
            piece = raw[:1]
        cursor += 1
        pieces.append(piece)
    return "".join(pieces)


def split_mask_rows(mask: str, kind: str, width: int = STUDY_CONTENT_WIDTH) -> list[str]:
    """Wrap a mask into rows that stay inside the compact study card."""
    metrics = _MASK_METRICS.get(kind)
    if metrics is None:
        return [mask] if mask else []
    box, fixed, gap = metrics
    rows: list[str] = []
    current: list[str] = []
    used = 0
    for char in mask or "":
        if char == " ":
            cell = gap
        elif char == "_":
            cell = box
        else:
            cell = fixed
        if current and used + cell > width:
            rows.append("".join(current))
            current = []
            used = 0
            if char == " ":
                continue
        current.append(char)
        used += cell
    if current:
        rows.append("".join(current))
    return rows


def mask_usable(mask: str, kind: str) -> bool:
    """False when wrapping still needs more rows than the compact card can show."""
    if not mask or kind not in _MASK_METRICS:
        return False
    return len(split_mask_rows(mask, kind)) <= MAX_MASK_ROWS


def missing_letters_ready(mask: str, answer: str) -> bool:
    """True when every blank is one letter and every fixed character is still in place."""
    pattern = mask or ""
    text = answer or ""
    if "_" not in pattern or len(text) != len(pattern):
        return False
    for pattern_char, typed in zip(pattern, text):
        if pattern_char == "_":
            if not typed.isalpha():
                return False
        elif typed != pattern_char:
            return False
    return True


def _forms(entry: dict, language_code: str) -> set[str]:
    return accepted_forms(entry, language_code=language_code)


def generate_multiple_choice(
    entry: dict,
    pool: Sequence[dict],
    rng: random.Random,
    language_code: str,
) -> Optional[ExerciseCard]:
    meaning = entry_meaning(entry)
    if not normalize(meaning):
        return None
    correct = display_word(entry) or entry_word(entry)
    correct_forms = _forms(entry, language_code)
    if not correct_forms:
        return None
    for other in pool:
        if other is entry:
            continue
        if entry_id(other) and entry_id(other) == entry_id(entry):
            continue
        if normalize(entry_meaning(other)) == normalize(meaning):
            return None
        if _forms(other, language_code) & correct_forms:
            return None
    distractors: List[str] = []
    seen = set(correct_forms)
    order = list(pool)
    rng.shuffle(order)
    for other in order:
        if entry_id(other) == entry_id(entry):
            continue
        label = display_word(other) or entry_word(other)
        forms = _forms(other, language_code)
        if not label or not forms or forms & seen or forms & correct_forms:
            continue
        if normalize(entry_meaning(other)) == normalize(meaning):
            continue
        distractors.append(label)
        seen |= forms
        if len(distractors) == 3:
            break
    if len(distractors) < 2:
        return None
    labels = distractors + [correct]
    rng.shuffle(labels)
    return _card(
        entry,
        language_code,
        MULTIPLE_CHOICE,
        MULTIPLE_CHOICE,
        prompt=meaning,
        choices=tuple(labels),
        correct_index=labels.index(correct),
            guidance=config.ui("Chọn từ đúng.", "Choose the word."),
        reveal_word=correct,
    )


def _card(entry, language_code, kind, intended, **kwargs) -> ExerciseCard:
    return ExerciseCard(
        kind=kind,
        intended_kind=intended,
        support_level=SUPPORT[kind],
        vocab_id=entry_id(entry),
        language_code=language_code,
        kicker=_kicker(kind),
        reveal_word=kwargs.pop("reveal_word", display_word(entry) or entry_word(entry)),
        accepted_answers=tuple(sorted(_forms(entry, language_code))),
        **kwargs,
    )


def build_exercise(
    entry: dict,
    pool: Sequence[dict],
    rng: random.Random,
    language_code: str,
    kind: str,
    assist_depth: int = 1,
) -> ExerciseCard:
    """Build ``kind`` or the nearest valid exercise. The intended step stays on the card."""
    order = [kind]
    for candidate in (MISSING_LETTERS, GUIDED_TYPING, MULTIPLE_CHOICE, INTRODUCTION):
        if candidate not in order and candidate != INDEPENDENT_RECALL:
            order.append(candidate)
    if kind == INDEPENDENT_RECALL:
        order = [INDEPENDENT_RECALL]
    for candidate in order:
        card = _build_exact(entry, pool, rng, language_code, candidate, assist_depth, kind)
        if card is not None:
            return card
    return _build_exact(entry, pool, rng, language_code, INTRODUCTION, assist_depth, kind)


def _build_exact(entry, pool, rng, language_code, kind, assist_depth, intended) -> Optional[ExerciseCard]:
    word = display_word(entry) or entry_word(entry)
    meaning = entry_meaning(entry)
    if kind == INTRODUCTION:
        example = entry_example(entry)
        return _card(
            entry,
            language_code,
            INTRODUCTION,
            intended,
            prompt=meaning,
            show_word=word,
            show_meaning=meaning,
            show_example=example,
            guidance="",
            reveal_word=word,
        )
    if kind == MULTIPLE_CHOICE:
        card = generate_multiple_choice(entry, pool, rng, language_code)
        if card is None:
            return None
        return ExerciseCard(
            kind=card.kind,
            intended_kind=intended,
            support_level=card.support_level,
            vocab_id=card.vocab_id,
            language_code=card.language_code,
            kicker=card.kicker,
            prompt=card.prompt,
            choices=card.choices,
            correct_index=card.correct_index,
            guidance=card.guidance,
            reveal_word=card.reveal_word,
            accepted_answers=card.accepted_answers,
        )
    if kind == MISSING_LETTERS:
        masked = mask_target(word, rng)
        if masked is None or not mask_usable(masked, MISSING_LETTERS):
            return None
        return _card(
            entry,
            language_code,
            MISSING_LETTERS,
            intended,
            prompt=meaning,
            mask=masked,
            guidance=config.ui("Điền các chữ còn thiếu.", "Fill in the missing letters."),
            reveal_word=word,
        )
    if kind == GUIDED_TYPING:
        if len(word) < 2:
            return None
        pattern = guided_pattern(word, assist_depth)
        if not mask_usable(pattern, GUIDED_TYPING):
            return None
        return _card(
            entry,
            language_code,
            GUIDED_TYPING,
            intended,
            prompt=meaning,
            mask=pattern,
            guidance=guided_guidance(word, assist_depth),
            reveal_word=word,
        )
    if kind == INDEPENDENT_RECALL:
        return _card(
            entry,
            language_code,
            INDEPENDENT_RECALL,
            intended,
            prompt=meaning,
            guidance=config.ui("Tự nhớ từ này.", "Recall this word."),
            reveal_word=word,
            show_example="",
        )
    return None


def starting_level(
    stats: Optional[dict],
    latest_attempt,
    *,
    now: Optional[datetime] = None,
    practice=(),
) -> str:
    """New words start at introduction. A non-mastered latest attempt starts one step easier.

    Recent practice can change that start. An exact unaided attempt stays at
    independent recall. Assisted success never promotes a non-mastered word
    to independent recall. Two recent practice failures can start one step easier.
    Practice that is older than, or equal to, the latest independent attempt
    does not override that attempt.
    """
    now = now or utc_now()
    base = _base_starting_level(stats, latest_attempt, now=now)
    if base == INDEPENDENT_RECALL:
        return base
    after = None
    if latest_attempt is not None:
        after = parse_practice_time(getattr(latest_attempt, "timestamp", "") or "")
    return practice_start_level(
        base,
        practice,
        allow_promote=base == INTRODUCTION,
        now=now,
        after=after,
    )


def _base_starting_level(stats, latest_attempt, *, now: datetime) -> str:
    if latest_attempt is None and is_new(stats):
        return INTRODUCTION
    mastered = _attempt_mastered(latest_attempt)
    if latest_attempt is None and stats and not is_new(stats):
        mastered = int(stats.get("streak") or 0) > 0
    if not mastered:
        return GUIDED_TYPING
    if is_due(stats, now):
        return INDEPENDENT_RECALL
    return INDEPENDENT_RECALL


def _attempt_mastered(attempt) -> bool:
    if attempt is None:
        return False
    return bool(attempt.correct) and attempt.verdict == "exact" and not attempt.hint_used


def latest_attempt_for(attempts: Iterable, vocab_id: str, language_code: str):
    found = None
    for attempt in attempts or ():
        if str(getattr(attempt, "vocab_id", "") or "") != vocab_id:
            continue
        code = str(getattr(attempt, "language_code", "") or "")
        if code and code != language_code:
            continue
        found = attempt
    return found


class AdaptiveVocabularySession:
    """One unlocked preview or future session. State is keyed by language and vocabulary id."""

    def __init__(
        self,
        entries: Sequence[dict],
        *,
        language_code: str,
        pool: Sequence[dict] = None,
        progress_words: Optional[dict] = None,
        attempts: Iterable = (),
        rng: Optional[random.Random] = None,
        now: Optional[datetime] = None,
        session_id: str = "",
        step_down_after: int = STEP_DOWN_FAILURES,
        level_overrides: Optional[dict] = None,
        practice_history=(),
    ):
        self.session_id = session_id or uuid.uuid4().hex
        self.language_code = str(language_code or "").strip().lower()
        self.rng = rng or random.Random()
        self.now = now or utc_now()
        self.step_down_after = max(1, int(step_down_after))
        self.pool = list(pool if pool is not None else entries)
        self.progress_words = progress_words or {}
        self.abandoned = False
        self._completion_taken = False
        self._entries: Dict[str, dict] = {}
        self._states: Dict[str, _WordState] = {}
        self._order: Deque[str] = deque()
        self._pending: Optional[_Pending] = None
        self._card: Optional[ExerciseCard] = None
        self.counters = SessionCounters()
        overrides = level_overrides or {}
        history: Dict[str, list] = {}
        for record in practice_history or ():
            if str(getattr(record, "language_code", "") or "") != self.language_code:
                continue
            history.setdefault(str(getattr(record, "vocab_id", "") or ""), []).append(record)
        seen = set()
        for entry in entries or ():
            if not isinstance(entry, dict):
                continue
            vid = entry_id(entry)
            if not vid or vid in seen:
                continue
            seen.add(vid)
            self._entries[vid] = entry
            latest = latest_attempt_for(attempts, vid, self.language_code)
            stats = self.progress_words.get(vid)
            kind = overrides.get(vid) or starting_level(
                stats,
                latest,
                now=self.now,
                practice=history.get(vid, ()),
            )
            if kind not in LADDER:
                kind = INTRODUCTION
            self._states[vid] = _WordState(vocab_id=vid, level=LADDER.index(kind))
            self._order.append(vid)
        self.counters.planned = len(self._order)
        self._rebuild()

    @property
    def finished(self) -> bool:
        return self.counters.planned > 0 and self.counters.words_completed >= self.counters.planned

    def current_card(self) -> Optional[ExerciseCard]:
        return self._card

    def state_key(self, vocab_id: str) -> tuple:
        return (self.session_id, self.language_code, vocab_id)

    def level_of(self, vocab_id: str) -> Optional[str]:
        state = self._states.get(vocab_id)
        if state is None:
            return None
        return LADDER[state.level]

    def abandon(self) -> None:
        self.abandoned = True

    def take_completion(self) -> bool:
        """True once, and only after every planned word has an independent session success."""
        if self.abandoned or not self.finished or self._completion_taken:
            return False
        self._completion_taken = True
        return True

    def submit(self, answer: str = "", choice_index: Optional[int] = None) -> SubmitResult:
        if self._pending is not None or self._card is None or self.abandoned:
            return SubmitResult("ignored")
        card = self._card
        if card.kind == INTRODUCTION:
            return SubmitResult("ignored")
        if card.kind == MULTIPLE_CHOICE:
            if choice_index is None:
                return SubmitResult(
                    "empty",
                    tone="empty",
                    feedback=config.ui("Hãy chọn một đáp án trước.", "Choose an answer first."),
                )
            return self._grade_choice(card, choice_index)
        text = str(answer or "").strip()
        if card.kind == MISSING_LETTERS and not missing_letters_ready(card.mask or "", text):
            return SubmitResult(
                "empty",
                tone="empty",
                feedback=config.ui(
                    "Hãy điền hết các chữ còn thiếu.",
                    "Fill every missing letter.",
                ),
            )
        if not text:
            return SubmitResult(
                "empty",
                tone="empty",
                feedback=config.ui("Hãy nhập câu trả lời trước.", "Type an answer first."),
            )
        return self._grade_text(card, text)

    def continue_card(self) -> SubmitResult:
        if self.abandoned:
            return SubmitResult("ignored")
        if self._pending is not None:
            result = self._apply_pending()
            return result
        card = self._card
        if card is not None and card.kind == INTRODUCTION:
            return self._queue_success(card, verdict="", tone="ok", feedback="")
        return SubmitResult("ignored")

    def request_assistance(self) -> SubmitResult:
        """Leave independent recall for guided typing. This is not an answer and not an attempt."""
        if self._pending is not None or self._card is None or self.abandoned:
            return SubmitResult("ignored")
        if self._card.kind != INDEPENDENT_RECALL:
            return SubmitResult("ignored")
        state = self._states[self._card.vocab_id]
        state.level = LADDER.index(GUIDED_TYPING)
        state.consecutive_failures = 0
        state.assist_depth = 1
        self._rebuild()
        return SubmitResult(
            "help",
            feedback=config.ui(
                "Luyện có hỗ trợ. Câu trả lời này không còn là nhớ độc lập.",
                "Assisted practice. This answer will not be independent.",
            ),
        )

    def _grade_choice(self, card: ExerciseCard, choice_index: int) -> SubmitResult:
        if choice_index < 0 or choice_index >= len(card.choices):
            return SubmitResult(
                "empty",
                tone="empty",
                feedback=config.ui("Hãy chọn một đáp án trước.", "Choose an answer first."),
            )
        if choice_index == card.correct_index:
            return self._queue_success(
                card,
                verdict="exact",
                tone="ok",
                feedback=config.ui(
                    f"Đúng rồi. Từ là {card.reveal_word}.",
                    f"That's it. The word is {card.reveal_word}.",
                ),
            )
        return self._queue_failure(
            card,
            verdict="wrong",
            feedback=config.ui(
                f"Chưa đúng. Từ là {card.reveal_word}.",
                f"Not quite. The word is {card.reveal_word}.",
            ),
        )

    def _grade_text(self, card: ExerciseCard, answer: str) -> SubmitResult:
        entry = self._entries[card.vocab_id]
        verdict, _matched = match_answer(
            answer,
            entry,
            config.TYPO_TOLERANCE,
            language_code=self.language_code,
        )
        if card.kind == INDEPENDENT_RECALL:
            return self._grade_independent(card, entry, answer, verdict)
        if verdict == "exact":
            return self._queue_success(
                card,
                verdict=verdict,
                tone="ok",
                feedback=config.ui(
                    f"Đúng rồi. Từ là {card.reveal_word}.",
                    f"That's it. The word is {card.reveal_word}.",
                ),
            )
        if verdict == "near":
            return self._queue_failure(
                card,
                verdict=verdict,
                tone="near",
                feedback=config.ui(
                    f"Rất gần. Từ là {card.reveal_word}.",
                    f"Very close. The word is {card.reveal_word}.",
                ),
            )
        return self._queue_failure(
            card,
            verdict="wrong",
            feedback=config.ui(
                f"Chưa đúng. Từ là {card.reveal_word}.",
                f"Not quite. The word is {card.reveal_word}.",
            ),
        )

    def _grade_independent(self, card, entry, answer, verdict) -> SubmitResult:
        mastered = verdict == "exact"
        write = IndependentWrite(
            vocab_id=card.vocab_id,
            language_code=self.language_code,
            word=entry_word(entry),
            user_answer=answer,
            expected_answer=card.reveal_word,
            prompt=entry_meaning(entry),
            verdict=verdict if verdict in ("exact", "near", "wrong") else "wrong",
            mastered=mastered,
            hint_used=False,
        )
        self.counters.independent_answered += 1
        if verdict in ("exact", "near"):
            self.counters.independent_session_correct += 1
            if mastered:
                self.counters.independent_mastered += 1
                feedback = config.ui(
                    f"Đúng rồi. Từ là {card.reveal_word}. Bạn đã tự nhớ ra.",
                    f"That's it. The word is {card.reveal_word}. You recalled it on your own.",
                )
                tone = "ok"
                action = "complete"
            else:
                feedback = config.ui(
                    f"Rất gần. Từ là {card.reveal_word}. Đây chưa phải lần tự nhớ chính xác.",
                    f"Very close. The word is {card.reveal_word}. This is not an exact recall yet.",
                )
                tone = "near"
                action = "complete"
        else:
            meaning = entry_meaning(entry)
            feedback = config.ui(
                f"Chưa đúng. Từ là {card.reveal_word}. Nghĩa là {meaning}.",
                f"Not quite. The word is {card.reveal_word}. It means {meaning}.",
            )
            tone = "bad"
            action = "fail"
        self._pending = _Pending(card.vocab_id, action, write)
        return SubmitResult(
            "feedback",
            success=action == "complete",
            verdict=write.verdict,
            tone=tone,
            feedback=feedback,
            write=write,
            completed_word=action == "complete",
            session_finished=False,
        )

    def _queue_success(self, card, *, verdict, tone, feedback) -> SubmitResult:
        if card.support_level == "recognition":
            self.counters.recognition_successes += 1
        elif card.support_level == "assisted":
            self.counters.assisted_successes += 1
        action = "advance"
        state = self._states[card.vocab_id]
        if LADDER[state.level] == INDEPENDENT_RECALL:
            action = "complete"
        self._pending = _Pending(card.vocab_id, action, None)
        outcome = "acknowledged" if card.kind == INTRODUCTION else (verdict or "exact")
        practice = self._practice_event(card, outcome)
        if card.kind == INTRODUCTION:
            self._apply_pending()
            return SubmitResult(
                "advanced",
                success=True,
                session_finished=self.finished,
                practice=practice,
            )
        return SubmitResult(
            "feedback",
            success=True,
            verdict=verdict,
            tone=tone,
            feedback=feedback,
            practice=practice,
        )

    def _queue_failure(self, card, *, verdict, feedback, tone: str = "bad") -> SubmitResult:
        self._pending = _Pending(card.vocab_id, "fail", None)
        outcome = verdict if verdict in ("near", "wrong") else "wrong"
        return SubmitResult(
            "feedback",
            success=False,
            verdict=verdict,
            tone=tone,
            feedback=feedback,
            practice=self._practice_event(card, outcome),
        )

    def _practice_event(self, card, outcome: str):
        """Recognition and assisted submissions only. Independent recall stays an attempt."""
        if card.support_level == "independent" or not card.exercise_instance_id:
            return None
        from attempt_history import utc_now_iso
        from practice_record import build_practice_record

        return build_practice_record(
            practice_event_id=uuid.uuid4().hex,
            exercise_instance_id=card.exercise_instance_id,
            session_id=self.session_id,
            vocab_id=card.vocab_id,
            language_code=self.language_code,
            actual_kind=card.kind,
            intended_kind=card.intended_kind,
            support_level=card.support_level,
            outcome=outcome,
            occurred_at=utc_now_iso(),
        )

    def _apply_pending(self) -> SubmitResult:
        pending = self._pending
        self._pending = None
        if pending is None:
            return SubmitResult("ignored")
        state = self._states[pending.vocab_id]
        finished_now = False
        if pending.action == "complete":
            if not state.completed:
                state.completed = True
                self.counters.words_completed += 1
            self._order = deque(vid for vid in self._order if vid != pending.vocab_id)
            finished_now = self.finished
        elif pending.action == "advance":
            if state.level < len(LADDER) - 1:
                state.level += 1
            state.consecutive_failures = 0
            state.assist_depth = 1
            self._rotate(pending.vocab_id)
        elif pending.action == "fail":
            state.consecutive_failures += 1
            if LADDER[state.level] == GUIDED_TYPING:
                state.assist_depth += 1
            if state.consecutive_failures >= self.step_down_after and state.level > 0:
                state.level -= 1
                state.consecutive_failures = 0
                state.assist_depth = 1
            self._rotate(pending.vocab_id)
        self._rebuild()
        return SubmitResult("advanced", success=pending.action != "fail", session_finished=finished_now)

    def _rotate(self, vocab_id: str) -> None:
        if len(self._order) > 1 and self._order[0] == vocab_id:
            self._order.rotate(-1)

    def _prefer_word_under_cap(self) -> None:
        """One bounded pass. If every remaining word is at the cap, keep the front word."""
        total = len(self._order)
        if total <= 1:
            return
        if not any(self._states[vid].presentations < PRESENTATION_CAP for vid in self._order):
            return
        for _ in range(total - 1):
            if self._states[self._order[0]].presentations < PRESENTATION_CAP:
                return
            self._order.rotate(-1)

    def _rebuild(self) -> None:
        if not self._order:
            self._card = None
            return
        self._prefer_word_under_cap()
        vid = self._order[0]
        state = self._states[vid]
        state.presentations += 1
        kind = LADDER[state.level]
        card = build_exercise(
            self._entries[vid],
            self.pool,
            self.rng,
            self.language_code,
            kind,
            state.assist_depth,
        )
        self._card = replace(card, exercise_instance_id=uuid.uuid4().hex)


def apply_independent_write(progress, attempts, write: IndependentWrite, *, timestamp: str) -> None:
    """The existing attempt and progress path. Call this once per returned write."""
    from attempt_history import LearningAttempt

    progress.record(write.word, correct=write.mastered, vocab_id=write.vocab_id or None)
    attempts.record(
        LearningAttempt(
            timestamp=timestamp,
            language_code=write.language_code,
            word=write.word,
            user_answer=write.user_answer,
            expected_answer=write.expected_answer,
            correct=write.mastered,
            verdict=write.verdict,
            hint_used=False,
            prompt=write.prompt,
            vocab_id=write.vocab_id,
        )
    )


class AdaptivePreviewRefused(RuntimeError):
    """Locked study stays on the legacy quiz."""


class AdaptiveSessionBridge:
    """Vocabulary completion for one unlocked adaptive session.

    Leave does not mark the study activity complete. The completion call runs
    once, after every planned word has an independent session success.
    """

    def __init__(self, study_session, controller: AdaptiveVocabularySession, *, locked: bool):
        if locked:
            raise AdaptivePreviewRefused("Locked sessions stay on the legacy quiz.")
        from study_session import KIND_VOCABULARY, STATUS_PENDING

        self.study_session = study_session
        self.controller = controller
        self.completion_calls = 0
        self.kind = KIND_VOCABULARY
        if (
            study_session.has_activity(KIND_VOCABULARY)
            and study_session.status(KIND_VOCABULARY) == STATUS_PENDING
        ):
            study_session.start(KIND_VOCABULARY)

    def leave(self) -> None:
        self.controller.abandon()

    def note_finished(self) -> bool:
        if not self.controller.take_completion():
            return False
        if self.completion_calls:
            return False
        self.completion_calls += 1
        self.study_session.complete(self.kind)
        return True


def select_planned_entries(store, progress, limit: int, rng: random.Random, now=None) -> list:
    """Due and new words first, using the existing due filter. Does not write progress."""
    from scheduler import due_candidate_indices

    indices = due_candidate_indices(store, progress, now=now)
    ordered = list(indices)
    rng.shuffle(ordered)
    chosen = []
    for index in ordered:
        if len(chosen) >= max(0, int(limit)):
            break
        entry = store.get(index)
        if entry is not None:
            chosen.append(entry)
    return chosen
