"""Listening activity foundation (Phase 17A).

Domain-only: content model, answer check, audio-provider seam, session controller.
No production TTS. No microphone. No network. No Progress/SRS mutation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

from text_utils import match_answer


class ListeningError(RuntimeError):
    """Domain/UI-facing listening failure (not a ScreenGuard concern)."""


class ListeningAudioError(ListeningError):
    """Audio provider failed or is unavailable."""


@dataclass(frozen=True)
class ListeningItem:
    """Minimal listening comprehension item.

    ``text`` is spoken content (hidden until answered).
    ``question`` / ``answer`` are comprehension prompt + expected response.
    """

    text: str
    question: str
    answer: str
    alternatives: Tuple[str, ...] = ()
    meaning: str = ""


@dataclass(frozen=True)
class ListeningCheckResult:
    verdict: str  # exact | near | wrong
    correct: bool
    expected: str


class ListeningAudioProvider(ABC):
    """Minimal seam for Phase 17B TTS / local playback."""

    @abstractmethod
    def play(self, text: str, language_code: str) -> None:
        """Play ``text`` in the given study language. May raise ListeningAudioError."""
        raise NotImplementedError

    def is_available(self) -> bool:
        return True


class FakeListeningAudioProvider(ListeningAudioProvider):
    """Test/dev provider — records calls; does not produce real audio."""

    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.calls: List[Tuple[str, str]] = []

    def play(self, text: str, language_code: str) -> None:
        self.calls.append((str(text), str(language_code)))
        if self.fail:
            raise ListeningAudioError("Fake listening audio failed.")


class NullListeningAudioProvider(ListeningAudioProvider):
    """Explicit unavailable provider (no production TTS yet)."""

    def is_available(self) -> bool:
        return False

    def play(self, text: str, language_code: str) -> None:
        raise ListeningAudioError("Listening audio is not available.")


def resolve_listening_audio_provider() -> Optional[ListeningAudioProvider]:
    """Production: no TTS yet → None (Listening becomes unavailable if enabled).

    Tests / manual verification inject FakeListeningAudioProvider explicitly.
    """
    return None


def sample_listening_items(language_code: str) -> Tuple[ListeningItem, ...]:
    """Tiny bundled samples for supported study languages (architecture > volume)."""
    code = str(language_code or "").strip().lower()
    catalog = {
        "nl": ListeningItem(
            text="Ik woon in een klein huis.",
            question="Where do I live? / Tôi sống ở đâu?",
            answer="in a small house",
            alternatives=("in een klein huis", "a small house", "nhà nhỏ"),
            meaning="I live in a small house.",
        ),
        "en": ListeningItem(
            text="The train leaves at nine.",
            question="When does the train leave?",
            answer="at nine",
            alternatives=("nine", "9"),
            meaning="The train leaves at nine.",
        ),
        "fr": ListeningItem(
            text="Je vais au marché.",
            question="Where am I going?",
            answer="to the market",
            alternatives=("au marché", "marché", "the market"),
            meaning="I am going to the market.",
        ),
        "de": ListeningItem(
            text="Ich trinke Wasser.",
            question="What am I drinking?",
            answer="water",
            alternatives=("Wasser", "water"),
            meaning="I drink water.",
        ),
        "es": ListeningItem(
            text="Ella lee un libro.",
            question="What is she reading?",
            answer="a book",
            alternatives=("un libro", "libro", "book"),
            meaning="She is reading a book.",
        ),
        "it": ListeningItem(
            text="Lui mangia la pizza.",
            question="What is he eating?",
            answer="pizza",
            alternatives=("la pizza", "pizza"),
            meaning="He is eating pizza.",
        ),
        "pt": ListeningItem(
            text="Nós falamos português.",
            question="What language do we speak?",
            answer="Portuguese",
            alternatives=("português", "portuguese"),
            meaning="We speak Portuguese.",
        ),
    }
    item = catalog.get(code)
    return (item,) if item is not None else ()


def check_listening_answer(user_answer: str, item: ListeningItem) -> ListeningCheckResult:
    """Deterministic comprehension match via text_utils.match_answer.

    Reuses normalize / alternatives / light typo tolerance. Not vocabulary mastery.
    ``correct`` for activity feedback = exact or near (completion itself is separate).
    """
    entry = {
        "word": item.answer,
        "alternatives": list(item.alternatives or ()),
    }
    verdict, best = match_answer(user_answer, entry, typo_tolerance=1)
    return ListeningCheckResult(
        verdict=verdict,
        correct=verdict in ("exact", "near"),
        expected=str(best or item.answer),
    )


@dataclass
class ListeningSession:
    """One-item Listening activity controller (no Tkinter)."""

    language_code: str
    item: ListeningItem
    audio_provider: Optional[ListeningAudioProvider] = None
    played: bool = False
    answered: bool = False
    last_result: Optional[ListeningCheckResult] = None
    completed: bool = False
    unavailable: bool = False
    _playing: bool = field(default=False, repr=False)

    @classmethod
    def create(
        cls,
        language_code: str,
        *,
        item: Optional[ListeningItem] = None,
        audio_provider: Optional[ListeningAudioProvider] = None,
        items: Optional[Sequence[ListeningItem]] = None,
    ) -> "ListeningSession":
        provider = audio_provider
        if provider is None:
            provider = resolve_listening_audio_provider()
        chosen = item
        if chosen is None:
            pool = list(items) if items is not None else list(sample_listening_items(language_code))
            chosen = pool[0] if pool else None
        if chosen is None:
            session = cls(
                language_code=language_code,
                item=ListeningItem(text="", question="", answer=""),
                audio_provider=provider,
            )
            session.unavailable = True
            return session
        session = cls(language_code=language_code, item=chosen, audio_provider=provider)
        if provider is None or not provider.is_available():
            session.unavailable = True
        return session

    def play(self) -> None:
        if self.unavailable:
            raise ListeningAudioError("Listening audio is not available.")
        if self._playing:
            return
        if self.audio_provider is None or not self.audio_provider.is_available():
            self.unavailable = True
            raise ListeningAudioError("Listening audio is not available.")
        self._playing = True
        try:
            self.audio_provider.play(self.item.text, self.language_code)
            self.played = True
        except ListeningAudioError:
            self.unavailable = True
            raise
        except Exception as error:  # noqa: BLE001
            self.unavailable = True
            raise ListeningAudioError(str(error)) from error
        finally:
            self._playing = False

    def submit(self, user_answer: str) -> ListeningCheckResult:
        if self.unavailable:
            raise ListeningError("Listening is unavailable.")
        if not self.played:
            raise ListeningError("Listen before answering.")
        result = check_listening_answer(user_answer, self.item)
        self.last_result = result
        self.answered = True
        return result

    def finish(self) -> None:
        """Mark activity completed after the learner continues."""
        if self.unavailable:
            return
        if not self.answered:
            raise ListeningError("Answer before finishing.")
        self.completed = True
