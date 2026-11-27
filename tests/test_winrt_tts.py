"""WinRT voices stay in-language and out of the PowerShell source."""

from __future__ import annotations

import inspect

from listening import ListeningAudioError
from listening_speech import WindowsSpeechProvider, resolve_saved_voice
from listening_windows_tts import WindowsLocalTTSProvider, WindowsVoiceInfo, _SPEAK_SCRIPT as _SAPI_SCRIPT
from listening_winrt_tts import (
    _SPEAK_SCRIPT,
    WindowsWinRTProvider,
    parse_winrt_discovery_output,
    winrt_speed_millis,
)
from voice_settings_app import VoiceSettingsApp


def _voice(name, culture, language, provider="sapi", voice_id=""):
    return WindowsVoiceInfo(
        name=name,
        culture=culture,
        language=language,
        gender="Female",
        provider=provider,
        voice_id=voice_id,
    )


HELENA = _voice("Microsoft Helena Desktop", "es-ES", "es")
DAVID = _voice("Microsoft David Desktop", "en-US", "en", voice_id="david")
FRANK = _voice("Microsoft Frank", "nl-NL", "nl", provider="winrt", voice_id="frank-id")
HELIA = _voice("Microsoft Helia", "pt-PT", "pt", provider="winrt", voice_id="helia-id")
LAURA = _voice("Microsoft Laura", "es-ES", "es", provider="winrt", voice_id="laura-id")


class RecordingRunner:
    def __init__(self):
        self.calls = []

    def __call__(self, script, *, env=None, timeout=30.0):
        self.calls.append({"script": script, "env": dict(env or {}), "timeout": timeout})

        class Result:
            returncode = 0
            stdout = ""
            stderr = ""

        return Result()


def _provider():
    winrt_runner = RecordingRunner()
    sapi_runner = RecordingRunner()
    sapi = WindowsLocalTTSProvider(
        platform="win32",
        voices=(HELENA, DAVID),
        runner=sapi_runner,
    )
    winrt = WindowsWinRTProvider(
        platform="win32",
        voices=(FRANK, HELIA, LAURA),
        runner=winrt_runner,
    )
    provider = WindowsSpeechProvider(sapi=sapi, winrt=winrt, platform="win32")
    return provider, sapi_runner, winrt_runner


def test_system_speech_is_preferred_until_the_learner_picks_winrt():
    provider, sapi_runner, winrt_runner = _provider()
    assert provider.resolve_voice("es").name == "Microsoft Helena Desktop"
    assert provider.resolve_voice("es", "Microsoft Helena Desktop").provider == "sapi"
    chosen = provider.resolve_voice("es", "winrt:laura-id")
    assert chosen is LAURA
    assert provider.resolve_voice("nl").provider == "winrt"
    assert provider.resolve_voice("nl", "Microsoft David Desktop").language == "nl"
    assert provider.resolve_voice("fr") is None
    provider.play("Buenos días", "es", voice_name="Microsoft Helena Desktop")
    assert winrt_runner.calls == []
    assert sapi_runner.calls[0]["script"] is _SAPI_SCRIPT
    assert "Buenos" not in sapi_runner.calls[0]["script"]
    assert sapi_runner.calls[0]["env"]["STUDYGUARD_TTS_VOICE"] == "Microsoft Helena Desktop"


def test_winrt_playback_keeps_text_and_voice_out_of_the_script():
    provider, sapi_runner, runner = _provider()
    provider.play("Goedemorgen", "nl", rate=-4, voice_name="winrt:frank-id")
    assert sapi_runner.calls == []
    call = runner.calls[0]
    assert call["script"] is _SPEAK_SCRIPT
    assert call["env"]["STUDYGUARD_TTS_VOICE"] == "frank-id"
    assert call["env"]["STUDYGUARD_TTS_TEXT"] == "Goedemorgen"
    assert call["env"]["STUDYGUARD_TTS_SPEED"] == "800"
    assert "Goedemorgen" not in call["script"]
    assert "frank-id" not in call["script"]
    assert "IAsyncOperation``1" in call["script"]


def test_saved_system_speech_name_still_resolves():
    voices = (HELENA, DAVID, FRANK, HELIA, LAURA)
    assert resolve_saved_voice("es", voices, "Microsoft Helena Desktop") is HELENA
    assert resolve_saved_voice("en", voices, "") is DAVID
    assert resolve_saved_voice("nl", voices, "winrt:frank-id") is FRANK
    assert resolve_saved_voice("pt", voices, "") is HELIA


def test_speed_bounds_reject_a_boolean():
    assert winrt_speed_millis(0) == "1000"
    assert winrt_speed_millis(-4) == "800"
    assert winrt_speed_millis(-10) == "500"
    assert winrt_speed_millis(10) == "1500"
    try:
        winrt_speed_millis(True)
    except ListeningAudioError:
        pass
    else:
        raise AssertionError("bool rate was accepted")


def test_winrt_parser_keeps_the_voice_id():
    voices = parse_winrt_discovery_output(
        "frank-id\tMicrosoft Frank\tnl-NL\tMale\n"
        "helia-id\tMicrosoft Helia\tpt-PT\tFemale\n"
    )
    assert voices[0].token() == "winrt:frank-id"
    assert voices[0].language == "nl"
    assert voices[1].language == "pt"


def test_preview_recovers_when_another_window_releases_audio():
    source = inspect.getsource(VoiceSettingsApp._preview)
    assert "_arm_playback_watch" in source
    watch = inspect.getsource(VoiceSettingsApp._arm_playback_watch)
    assert "playback_busy" in watch
