"""Listening activity foundation (Phase 17A + 17B provider seam).

Domain-only: content model, answer check, audio-provider seam, session controller.
No microphone. No network. No Progress/SRS mutation.
Production audio: Windows local TTS via ListeningAudioProvider (Phase 17B).
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
    """Audio seam for Listening. Implementations must not touch Tkinter."""

    @abstractmethod
    def play(self, text: str, language_code: str) -> None:
        """Play ``text`` in the given study language. May raise ListeningAudioError."""
        raise NotImplementedError

    def is_available(self) -> bool:
        """True when the backend itself can run (not per-language)."""
        return True

    def supports(self, language_code: str) -> bool:
        """True when this provider can speak the given study language."""
        return self.is_available()


class FakeListeningAudioProvider(ListeningAudioProvider):
    """Test/dev provider — records calls; does not produce real audio."""

    def __init__(self, *, fail: bool = False, supported: Optional[Sequence[str]] = None):
        self.fail = fail
        self.calls: List[Tuple[str, str]] = []
        self._supported = (
            None if supported is None else {str(code).lower() for code in supported}
        )

    def supports(self, language_code: str) -> bool:
        if self._supported is None:
            return True
        return str(language_code or "").lower() in self._supported

    def play(self, text: str, language_code: str) -> None:
        if not self.supports(language_code):
            raise ListeningAudioError(f"No voice for {language_code}.")
        self.calls.append((str(text), str(language_code)))
        if self.fail:
            raise ListeningAudioError("Fake listening audio failed.")


class NullListeningAudioProvider(ListeningAudioProvider):
    """Explicit unavailable provider."""

    def is_available(self) -> bool:
        return False

    def supports(self, language_code: str) -> bool:
        return False

    def play(self, text: str, language_code: str) -> None:
        raise ListeningAudioError("Listening audio is not available.")


def resolve_listening_audio_provider() -> Optional[ListeningAudioProvider]:
    """Production: Windows local TTS when the speech backend initializes.

    Non-Windows / discovery failure → None (Listening stays unavailable-safe).
    Tests inject FakeListeningAudioProvider explicitly.
    """
    try:
        from listening_windows_tts import try_create_windows_tts_provider

        return try_create_windows_tts_provider()
    except Exception:  # noqa: BLE001 - import/init must never break app startup
        return None


def sample_listening_items(
    language_code: str, *, native_code: str = None
) -> Tuple[ListeningItem, ...]:
    """Bundled study-language-first samples (AI fallback).

    Spoken text, question, and answer are in the study language.
    ``meaning`` follows ``native_code`` (vi|en); defaults to vi.
    """
    code = str(language_code or "").strip().lower()
    native = str(native_code or "vi").strip().lower()
    # (text, question, answer, alternatives, meaning_vi, meaning_en)
    catalog = {
        "nl": (
            "De trein vertrekt om negen uur vanaf het station.",
            "Hoe laat vertrekt de trein?",
            "om negen uur",
            ("negen uur", "om 9 uur"),
            "Tàu khởi hành lúc chín giờ từ nhà ga.",
            "The train leaves at nine from the station.",
        ),
        "en": (
            "The train leaves at nine from the station.",
            "What time does the train leave?",
            "at nine",
            ("nine", "at 9"),
            "Tàu khởi hành lúc chín giờ từ nhà ga.",
            "The train leaves at nine from the station.",
        ),
        "fr": (
            "Le train part à neuf heures de la gare.",
            "À quelle heure part le train?",
            "à neuf heures",
            ("neuf heures", "à 9 heures"),
            "Tàu khởi hành lúc chín giờ từ nhà ga.",
            "The train leaves at nine from the station.",
        ),
        "de": (
            "Der Zug fährt um neun Uhr vom Bahnhof ab.",
            "Wann fährt der Zug ab?",
            "um neun Uhr",
            ("neun Uhr", "um 9 Uhr"),
            "Tàu khởi hành lúc chín giờ từ nhà ga.",
            "The train leaves at nine from the station.",
        ),
        "es": (
            "El tren sale a las nueve desde la estación.",
            "¿A qué hora sale el tren?",
            "a las nueve",
            ("las nueve", "a las 9"),
            "Tàu khởi hành lúc chín giờ từ nhà ga.",
            "The train leaves at nine from the station.",
        ),
        "it": (
            "Il treno parte alle nove dalla stazione.",
            "A che ora parte il treno?",
            "alle nove",
            ("le nove", "alle 9"),
            "Tàu khởi hành lúc chín giờ từ nhà ga.",
            "The train leaves at nine from the station.",
        ),
        "pt": (
            "O comboio parte às nove da estação.",
            "A que horas parte o comboio?",
            "às nove",
            ("as nove", "às 9"),
            "Tàu khởi hành lúc chín giờ từ nhà ga.",
            "The train leaves at nine from the station.",
        ),
    }
    row = catalog.get(code)
    if row is None:
        return ()
    text, question, answer, alts, meaning_vi, meaning_en = row
    meaning = meaning_en if native == "en" else meaning_vi
    return (
        ListeningItem(
            text=text,
            question=question,
            answer=answer,
            alternatives=alts,
            meaning=meaning,
        ),
    )


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
    unavailable_reason: str = ""
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
            pool = (
                list(items)
                if items is not None
                else list(sample_listening_items(language_code))
            )
            chosen = pool[0] if pool else None
        if chosen is None:
            session = cls(
                language_code=language_code,
                item=ListeningItem(text="", question="", answer=""),
                audio_provider=provider,
            )
            session.unavailable = True
            session.unavailable_reason = "no_content"
            return session
        session = cls(language_code=language_code, item=chosen, audio_provider=provider)
        if provider is None or not provider.is_available():
            session.unavailable = True
            session.unavailable_reason = "no_provider"
            return session
        if not provider.supports(language_code):
            session.unavailable = True
            session.unavailable_reason = "no_voice"
            return session
        return session

    def play(self) -> None:
        if self.unavailable:
            raise ListeningAudioError(
                self.unavailable_reason_message()
                or "Listening audio is not available."
            )
        if self._playing:
            return
        if self.audio_provider is None or not self.audio_provider.is_available():
            self.unavailable = True
            self.unavailable_reason = "no_provider"
            raise ListeningAudioError("Listening audio is not available.")
        if not self.audio_provider.supports(self.language_code):
            self.unavailable = True
            self.unavailable_reason = "no_voice"
            raise ListeningAudioError(self.unavailable_reason_message())
        self._playing = True
        try:
            self.audio_provider.play(self.item.text, self.language_code)
            self.played = True
        except ListeningAudioError:
            # Failure must not mark played=True (state machine invariant).
            self.unavailable = True
            if not self.unavailable_reason:
                self.unavailable_reason = "play_failed"
            raise
        except Exception as error:  # noqa: BLE001
            self.unavailable = True
            self.unavailable_reason = "play_failed"
            raise ListeningAudioError(str(error)) from error
        finally:
            self._playing = False

    def unavailable_reason_message(self) -> str:
        if self.unavailable_reason == "no_voice" and self.audio_provider is not None:
            missing = getattr(self.audio_provider, "missing_voice_message", None)
            if callable(missing):
                return str(missing(self.language_code))
        return ""

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
