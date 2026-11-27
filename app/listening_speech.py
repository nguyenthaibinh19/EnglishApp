"""One local catalog for System.Speech and Windows.Media.SpeechSynthesis.

System.Speech wins when it already has a voice for the language. A WinRT voice
is used only for that same language when System.Speech has none, or when the
learner explicitly selected it. Another language is never selected.
"""

from __future__ import annotations

import sys
from typing import Optional, Sequence, Tuple

from listening import ListeningAudioError, ListeningAudioProvider
from listening_windows_tts import (
    NORMAL_RATE,
    WindowsLocalTTSProvider,
    WindowsVoiceInfo,
    select_voice_for_language,
    voices_for_language,
)
from listening_winrt_tts import WindowsWinRTProvider


def preference_matches(voice: WindowsVoiceInfo, saved: str) -> bool:
    token = str(saved or "").strip()
    if not token:
        return False
    if token == voice.token():
        return True
    return voice.provider != "winrt" and token == voice.name


def resolve_saved_voice(
    language_code: str,
    voices: Sequence[WindowsVoiceInfo],
    saved: Optional[str] = None,
) -> Optional[WindowsVoiceInfo]:
    """Pick the voice playback will use. The pool is already one language."""
    pool = voices_for_language(language_code, voices)
    requested = str(saved or "").strip()
    if requested:
        for voice in pool:
            if preference_matches(voice, requested):
                return voice
    return _preferred_voice(language_code, pool)


def _preferred_voice(
    language_code: str,
    pool: Sequence[WindowsVoiceInfo],
) -> Optional[WindowsVoiceInfo]:
    sapi = [voice for voice in pool if voice.provider != "winrt"]
    if sapi:
        return select_voice_for_language(language_code, sapi)
    return select_voice_for_language(language_code, pool)


class WindowsSpeechProvider(ListeningAudioProvider):
    """Local offline speech. No cloud provider and no extra Python package."""

    def __init__(self, sapi=None, winrt=None, platform: Optional[str] = None):
        self._sapi = sapi if sapi is not None else WindowsLocalTTSProvider()
        self._winrt = winrt if winrt is not None else WindowsWinRTProvider()
        self._platform = sys.platform if platform is None else platform
        self._voices: Optional[Tuple[WindowsVoiceInfo, ...]] = None
        self._sapi_ok = False
        self._winrt_ok = False

    def is_available(self) -> bool:
        if self._platform != "win32":
            return False
        try:
            self._ensure_voices()
        except ListeningAudioError:
            return False
        return self._sapi_ok or self._winrt_ok

    def supports(self, language_code: str) -> bool:
        if not self.is_available():
            return False
        return self.resolve_voice(language_code) is not None

    def resolve_voice(
        self,
        language_code: str,
        voice_name: Optional[str] = None,
    ) -> Optional[WindowsVoiceInfo]:
        try:
            voices = self._ensure_voices()
        except ListeningAudioError:
            return None
        return resolve_saved_voice(language_code, voices, voice_name)

    def voices_for(self, language_code: str) -> Tuple[WindowsVoiceInfo, ...]:
        return voices_for_language(language_code, self._ensure_voices())

    def cached_voices_for(self, language_code: str) -> Optional[Tuple[WindowsVoiceInfo, ...]]:
        if self._voices is None:
            return None
        return voices_for_language(language_code, self._voices)

    def refresh(self) -> Tuple[WindowsVoiceInfo, ...]:
        self._voices = None
        sapi_voices: Tuple[WindowsVoiceInfo, ...] = ()
        winrt_voices: Tuple[WindowsVoiceInfo, ...] = ()
        self._sapi_ok = False
        self._winrt_ok = False
        try:
            sapi_voices = tuple(self._sapi.refresh())
            self._sapi_ok = True
        except ListeningAudioError:
            sapi_voices = ()
        try:
            winrt_voices = tuple(self._winrt.refresh())
            self._winrt_ok = True
        except ListeningAudioError:
            winrt_voices = ()
        self._voices = sapi_voices + winrt_voices
        return self._voices

    def play(
        self,
        text: str,
        language_code: str,
        *,
        rate: int = NORMAL_RATE,
        voice_name: Optional[str] = None,
    ) -> None:
        voice = self.resolve_voice(language_code, voice_name=voice_name)
        if voice is None:
            raise ListeningAudioError(self._sapi.missing_voice_message(language_code))
        if voice.provider == "winrt":
            self._winrt.play(text, voice.voice_id, rate)
            return
        self._sapi.play(text, language_code, rate=rate, voice_name=voice.name)

    def _ensure_voices(self) -> Tuple[WindowsVoiceInfo, ...]:
        if self._voices is not None:
            return self._voices
        if self._platform != "win32":
            raise ListeningAudioError("Windows speech is only available on Windows.")
        sapi_voices: Tuple[WindowsVoiceInfo, ...] = ()
        winrt_voices: Tuple[WindowsVoiceInfo, ...] = ()
        try:
            sapi_voices = tuple(self._sapi.discovered_voices())
            self._sapi_ok = True
        except ListeningAudioError:
            self._sapi_ok = False
        try:
            winrt_voices = tuple(self._winrt.discover())
            self._winrt_ok = True
        except ListeningAudioError:
            self._winrt_ok = False
        if not self._sapi_ok and not self._winrt_ok:
            raise ListeningAudioError("Windows speech is not available.")
        self._voices = sapi_voices + winrt_voices
        return self._voices
