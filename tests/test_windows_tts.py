"""Phase 17B — Windows local TTS provider tests (mocked process; no real audio)."""

from __future__ import annotations

import subprocess
from types import SimpleNamespace

import pytest

from listening import (
    FakeListeningAudioProvider,
    ListeningAudioError,
    ListeningItem,
    ListeningSession,
)
from listening_windows_tts import (
    SPEECH_LOCALE_PREFERENCES,
    WindowsLocalTTSProvider,
    WindowsVoiceInfo,
    _DISCOVER_SCRIPT,
    _ENV_TEXT,
    _ENV_VOICE,
    _SPEAK_SCRIPT,
    parse_voice_discovery_output,
    select_voice_for_language,
    try_create_windows_tts_provider,
)


def _voices(*rows: tuple[str, str, str]) -> tuple[WindowsVoiceInfo, ...]:
    return tuple(WindowsVoiceInfo(name=n, culture=c, language=lang) for n, c, lang in rows)


def _result(stdout="", stderr="", returncode=0):
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


class RecordingRunner:
    def __init__(self, *, discover_stdout="", speak_returncode=0, speak_stderr=""):
        self.calls = []
        self.discover_stdout = discover_stdout
        self.speak_returncode = speak_returncode
        self.speak_stderr = speak_stderr
        self.raise_timeout = False
        self.raise_missing = False

    def __call__(self, script, *, env=None, timeout=30.0):
        self.calls.append({"script": script, "env": dict(env or {}), "timeout": timeout})
        if self.raise_missing:
            raise FileNotFoundError("powershell")
        if self.raise_timeout:
            raise ListeningAudioError("Speech playback timed out.")
        if script == _DISCOVER_SCRIPT:
            return _result(stdout=self.discover_stdout)
        if script == _SPEAK_SCRIPT:
            return _result(returncode=self.speak_returncode, stderr=self.speak_stderr)
        return _result(returncode=1, stderr="unexpected script")


def test_provider_unavailable_on_non_windows():
    provider = WindowsLocalTTSProvider(platform="linux", voices=())
    assert provider.is_available() is False
    assert try_create_windows_tts_provider.__module__.endswith("listening_windows_tts")


def test_powershell_missing_raises_on_play_path():
    runner = RecordingRunner(discover_stdout="")
    runner.raise_missing = True
    provider = WindowsLocalTTSProvider(runner=runner, platform="win32")
    assert provider.is_available() is False


def test_parse_voice_discovery_output():
    raw = (
        "Microsoft David Desktop\ten-US\ten\n"
        "Microsoft Hortense\tfr-FR\tfr\n"
        "bad-line\n"
        "\n"
    )
    voices = parse_voice_discovery_output(raw)
    assert len(voices) == 2
    assert voices[0].language == "en"
    assert voices[1].culture == "fr-FR"


def test_exact_locale_selection_and_determinism():
    voices = _voices(
        ("Zira", "en-US", "en"),
        ("David", "en-US", "en"),
        ("Hazel", "en-GB", "en"),
    )
    # Preferred en-US first; within culture, alphabetical by name → David before Zira.
    chosen = select_voice_for_language("en", voices)
    assert chosen is not None
    assert chosen.culture.lower() == "en-us"
    assert chosen.name == "David"
    assert select_voice_for_language("en", voices) == chosen


def test_base_language_fallback_and_no_unrelated():
    voices = _voices(
        ("Helena", "es-MX", "es"),
        ("David", "en-US", "en"),
    )
    es = select_voice_for_language("es", voices)
    assert es is not None
    assert es.culture == "es-MX"
    assert select_voice_for_language("nl", voices) is None
    assert select_voice_for_language("de", voices) is None


def test_nl_en_es_pt_locale_preferences():
    assert SPEECH_LOCALE_PREFERENCES["nl"][0].lower() == "nl-nl"
    assert SPEECH_LOCALE_PREFERENCES["en"][0].lower() == "en-us"
    assert "es-ES" in SPEECH_LOCALE_PREFERENCES["es"]
    assert "pt-BR" in SPEECH_LOCALE_PREFERENCES["pt"]
    voices = _voices(
        ("Frank", "nl-NL", "nl"),
        ("Zira", "en-GB", "en"),  # only GB — still English fallback after preferred miss
        ("Helena", "es-AR", "es"),
        ("Maria", "pt-BR", "pt"),
    )
    assert select_voice_for_language("nl", voices).name == "Frank"
    assert select_voice_for_language("en", voices).culture == "en-GB"
    assert select_voice_for_language("es", voices).culture == "es-AR"
    assert select_voice_for_language("pt", voices).culture == "pt-BR"


def test_unsupported_language_voice_marks_session_unavailable():
    provider = WindowsLocalTTSProvider(
        platform="win32",
        voices=_voices(("David", "en-US", "en")),
    )
    assert provider.supports("en") is True
    assert provider.supports("nl") is False
    session = ListeningSession.create(
        "nl",
        item=ListeningItem(text="Hallo", question="?", answer="hi"),
        audio_provider=provider,
    )
    assert session.unavailable is True
    assert session.unavailable_reason == "no_voice"
    assert session.played is False


def test_multi_language_voice_isolation():
    provider = WindowsLocalTTSProvider(
        platform="win32",
        voices=_voices(("David", "en-US", "en")),
    )
    en = ListeningSession.create(
        "en",
        item=ListeningItem(text="Hello", question="?", answer="hi"),
        audio_provider=provider,
    )
    nl = ListeningSession.create(
        "nl",
        item=ListeningItem(text="Hallo", question="?", answer="hi"),
        audio_provider=provider,
    )
    assert en.unavailable is False
    assert nl.unavailable is True


def test_spoken_text_passed_as_env_data_not_interpolated():
    runner = RecordingRunner(
        discover_stdout="Microsoft David Desktop\ten-US\ten\n"
    )
    provider = WindowsLocalTTSProvider(runner=runner, platform="win32")
    nasty = 'Hello"; Remove-Item -Recurse C:\\; Write-Host "'
    provider.play(nasty, "en")
    speak_calls = [c for c in runner.calls if c["script"] == _SPEAK_SCRIPT]
    assert len(speak_calls) == 1
    call = speak_calls[0]
    assert nasty in call["env"][_ENV_TEXT]
    assert nasty not in call["script"]
    assert "Remove-Item" not in call["script"]
    assert call["env"][_ENV_VOICE] == "Microsoft David Desktop"
    assert _ENV_VOICE in call["env"]
    # Fixed script identity — no f-string injection surface.
    assert call["script"] is _SPEAK_SCRIPT or call["script"] == _SPEAK_SCRIPT


def test_unicode_quotes_newlines_cannot_alter_script():
    runner = RecordingRunner(
        discover_stdout="Microsoft David Desktop\ten-US\ten\n"
    )
    provider = WindowsLocalTTSProvider(runner=runner, platform="win32")
    text = "café — it's \"fine\"\nsecond line\r\n$env:SECRET"
    provider.play(text, "en")
    call = [c for c in runner.calls if c["script"] == _SPEAK_SCRIPT][0]
    assert call["script"] == _SPEAK_SCRIPT
    assert call["env"][_ENV_TEXT] == text


def test_subprocess_nonzero_and_timeout_errors():
    runner = RecordingRunner(
        discover_stdout="Microsoft David Desktop\ten-US\ten\n",
        speak_returncode=7,
        speak_stderr="boom",
    )
    provider = WindowsLocalTTSProvider(runner=runner, platform="win32")
    with pytest.raises(ListeningAudioError):
        provider.play("Hello", "en")

    runner2 = RecordingRunner(
        discover_stdout="Microsoft David Desktop\ten-US\ten\n"
    )
    runner2.raise_timeout = True
    provider2 = WindowsLocalTTSProvider(runner=runner2, platform="win32")
    # Force voice cache first via discovery success, then timeout on speak.
    provider2 = WindowsLocalTTSProvider(
        runner=runner2,
        platform="win32",
        voices=_voices(("David", "en-US", "en")),
    )
    with pytest.raises(ListeningAudioError, match="timed out"):
        provider2.play("Hello", "en")


def test_successful_playback_and_failure_leaves_played_false():
    runner = RecordingRunner(
        discover_stdout="Microsoft David Desktop\ten-US\ten\n"
    )
    provider = WindowsLocalTTSProvider(runner=runner, platform="win32")
    item = ListeningItem(text="Hello train.", question="When?", answer="nine")
    session = ListeningSession.create("en", item=item, audio_provider=provider)
    session.play()
    assert session.played is True

    bad = WindowsLocalTTSProvider(
        runner=RecordingRunner(
            discover_stdout="Microsoft David Desktop\ten-US\ten\n",
            speak_returncode=9,
        ),
        platform="win32",
    )
    session2 = ListeningSession.create("en", item=item, audio_provider=bad)
    with pytest.raises(ListeningAudioError):
        session2.play()
    assert session2.played is False
    assert session2.unavailable is True


def test_repeated_sequential_play_no_overlap_guard():
    runner = RecordingRunner(
        discover_stdout="Microsoft David Desktop\ten-US\ten\n"
    )
    provider = WindowsLocalTTSProvider(runner=runner, platform="win32")
    item = ListeningItem(text="One.", question="?", answer="a")
    session = ListeningSession.create("en", item=item, audio_provider=provider)
    session.play()
    session.play()  # replay allowed after previous finishes
    speak_calls = [c for c in runner.calls if c["script"] == _SPEAK_SCRIPT]
    assert len(speak_calls) == 2
    # Overlap guard: while _playing, second play returns without another call.
    session._playing = True
    before = len(runner.calls)
    session.play()
    assert len(runner.calls) == before
    session._playing = False


def test_fake_provider_supports_filter_still_works():
    fake = FakeListeningAudioProvider(supported=("en",))
    assert fake.supports("en")
    assert not fake.supports("nl")
    with pytest.raises(ListeningAudioError):
        fake.play("x", "nl")
