"""Playback arbitration, stale callbacks, and missing-voice guidance."""

from __future__ import annotations

import inspect
import threading
import time
from unittest.mock import MagicMock

import pytest

from listening import FakeListeningAudioProvider, ListeningAudioError, ListeningItem, ListeningSession
from speech_player import play_async, playback_busy, reset_playback_state
from voice_settings_app import VoiceSettingsApp, install_guidance


@pytest.fixture(autouse=True)
def _clear_playback():
    reset_playback_state()
    yield
    reset_playback_state()


class _Window:
    def __init__(self):
        self.callbacks = []
        self.exists = True

    def winfo_exists(self):
        return self.exists

    def after(self, _delay, callback):
        self.callbacks.append(callback)

    def flush(self):
        pending = list(self.callbacks)
        self.callbacks.clear()
        for callback in pending:
            callback()


class _BlockingProvider:
    def __init__(self):
        self.started = threading.Event()
        self.release = threading.Event()
        self.calls = []

    def play(self, text, language_code, *, rate=0, voice_name=None):
        self.calls.append((text, language_code, rate, voice_name))
        self.started.set()
        assert self.release.wait(2)


def _wait_until(predicate, timeout=2):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_one_gate_blocks_a_second_window():
    provider = _BlockingProvider()
    first = _Window()
    second = _Window()
    assert play_async(first, text="one", language_code="en", provider=provider, voice_name="David", rate=0)
    assert provider.started.wait(2)
    assert playback_busy()
    assert play_async(second, text="two", language_code="nl", provider=provider) is False
    provider.release.set()
    assert _wait_until(lambda: first.callbacks)
    first.flush()
    assert [call[0] for call in provider.calls] == ["one"]
    assert playback_busy() is False


def test_stale_scope_does_not_touch_the_next_exercise():
    provider = FakeListeningAudioProvider()
    window = _Window()
    seen = []
    current = {"card": 1}

    def scope():
        return current["card"] == 1

    assert play_async(
        window,
        text="bridge",
        language_code="en",
        rate=-4,
        voice_name="Zira",
        provider=provider,
        scope=scope,
        on_done=lambda: seen.append("done"),
        on_error=lambda _error: seen.append("error"),
    )
    current["card"] = 2
    assert _wait_until(lambda: window.callbacks)
    window.flush()
    assert seen == []
    assert provider.calls == [("bridge", "en")]
    assert provider.rates == [-4]
    assert provider.voice_names == ["Zira"]


def test_missing_voice_is_reported_to_the_same_exercise():
    class Missing:
        def play(self, text, language_code, *, rate=0, voice_name=None):
            raise ListeningAudioError("No Windows text-to-speech voice is installed for Dutch.")

    window = _Window()
    seen = []
    assert play_async(
        window,
        text="fiets",
        language_code="nl",
        provider=Missing(),
        scope=lambda: True,
        on_error=lambda error: seen.append(str(error)),
    )
    assert _wait_until(lambda: window.callbacks)
    window.flush()
    assert seen == ["No Windows text-to-speech voice is installed for Dutch."]


def test_closed_window_drops_the_callback():
    provider = FakeListeningAudioProvider()
    window = _Window()
    seen = []
    assert play_async(
        window,
        text="hola",
        language_code="es",
        provider=provider,
        on_done=lambda: seen.append("done"),
    )
    window.exists = False
    assert _wait_until(lambda: window.callbacks)
    window.flush()
    assert seen == []


def test_cached_catalog_does_not_discover():
    from listening_windows_tts import WindowsLocalTTSProvider

    calls = []

    def runner(*_args, **_kwargs):
        calls.append("ran")
        raise AssertionError("discovery ran")

    provider = WindowsLocalTTSProvider(runner=runner, platform="win32")
    assert provider.cached_voices_for("nl") is None
    assert calls == []
    refresh = inspect.getsource(VoiceSettingsApp._refresh)
    render = inspect.getsource(VoiceSettingsApp._render_catalog)
    failed = refresh[refresh.index("def failed") :]
    assert ".voices_for(" not in failed
    assert ".voices_for(" not in render


def test_guidance_follows_the_selected_language():
    expected = {
        "nl": "Dutch (Netherlands)",
        "en": "English (United States)",
        "fr": "French (France)",
        "de": "German (Germany)",
        "es": "Spanish (Spain)",
        "it": "Italian (Italy)",
        "pt": "Portuguese (Portugal)",
    }
    other = {
        "nl": "Spanish (Spain)",
        "en": "Dutch (Netherlands)",
        "fr": "German (Germany)",
        "de": "Spanish (Spain)",
        "es": "Dutch (Netherlands)",
        "it": "French (France)",
        "pt": "Italian (Italy)",
    }
    for code, pack in expected.items():
        text = install_guidance(code)
        assert pack in text
        assert other[code] not in text
    assert "English (United Kingdom)" in install_guidance("en")
    assert "Spanish (Mexico)" in install_guidance("es")
    assert "Portuguese (Brazil)" in install_guidance("pt")


def _listening_app(monkeypatch):
    from listening_app import ListeningApp

    monkeypatch.setattr("listening_app.ui_common.apply_theme", lambda *_a, **_k: None)
    monkeypatch.setattr("listening_app.ui_common.ScreenGuard", lambda *a, **k: MagicMock())
    monkeypatch.setattr(
        "listening_app.ttk.Frame",
        lambda *a, **k: MagicMock(pack=MagicMock(), winfo_children=lambda: []),
    )
    monkeypatch.setattr("listening_app.ttk.Label", lambda *a, **k: MagicMock(pack=MagicMock()))
    monkeypatch.setattr(
        "listening_app.ttk.Button",
        lambda *a, **k: MagicMock(pack=MagicMock(), state=MagicMock()),
    )
    monkeypatch.setattr(
        "listening_app.ttk.Entry",
        lambda *a, **k: MagicMock(pack=MagicMock(), focus_set=MagicMock()),
    )
    monkeypatch.setattr(
        "listening_app.prepare_clickable_text",
        lambda *a, **k: MagicMock(pack=MagicMock()),
    )
    monkeypatch.setattr("listening_app.tk.StringVar", lambda: MagicMock())
    window = MagicMock()
    window.winfo_exists.return_value = True
    provider = FakeListeningAudioProvider()
    app = ListeningApp(
        window,
        language_code="en",
        audio_provider=provider,
        item=ListeningItem(text="Hello", question="?", answer="hi"),
        locked=False,
    )
    return app, provider


def test_listening_respects_the_shared_gate(monkeypatch):
    app, provider = _listening_app(monkeypatch)
    monkeypatch.setattr("listening_app.reserve_playback", lambda: None)
    app._play(0)
    assert provider.calls == []
    assert app.session.played is False
    assert app.session.completed is False
    assert app.session.unavailable is False
    text = app.status.config.call_args.kwargs["text"]
    assert "still playing" in text or "đoạn khác" in text


def test_listening_callback_ignores_a_replaced_exercise(monkeypatch):
    app, _provider = _listening_app(monkeypatch)
    original = app.session.item
    assert app._same_exercise("en", app._load_generation, original)
    app._load_generation += 1
    assert app._same_exercise("en", app._load_generation - 1, original) is False
    app.session = ListeningSession.create(
        "en",
        item=ListeningItem(text="Other", question="?", answer="x"),
        audio_provider=FakeListeningAudioProvider(),
    )
    assert app._same_exercise("en", app._load_generation, original) is False


def test_study_surfaces_request_the_saved_voice():
    from listening_app import ListeningApp
    from quiz_app import VocabQuizApp
    from vocabulary_app import VocabularyLibraryApp, WordDetailApp

    sources = [
        inspect.getsource(ListeningApp._play),
        inspect.getsource(VocabularyLibraryApp._hear_selected),
        inspect.getsource(WordDetailApp._speak),
        inspect.getsource(VocabQuizApp._hear_answer),
    ]
    for source in sources:
        assert "selected_voice_name" in source
        assert "play_async" in source or "session.play" in source


def test_slow_playback_does_not_finish_the_listening_session():
    provider = FakeListeningAudioProvider()
    session = ListeningSession.create(
        "es",
        item=ListeningItem(text="Hola", question="?", answer="hola"),
        audio_provider=provider,
    )
    session.play(rate=-4, voice_name="Helena")
    session.play(rate=0, voice_name="Helena")
    assert provider.rates == [-4, 0]
    assert provider.voice_names == ["Helena", "Helena"]
    assert session.played is True
    assert session.completed is False
    session.submit("hola")
    session.finish()
    session.finish()
    assert session.completed is True
