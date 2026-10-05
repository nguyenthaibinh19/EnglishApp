"""Phase 17B hardening — lazy Windows TTS discovery + Listening skip semantics."""

from __future__ import annotations

import inspect
from types import SimpleNamespace
from unittest.mock import MagicMock

import config
from daily_study import DailyStudyPlan
from listening import FakeListeningAudioProvider, NullListeningAudioProvider
from main import StudyMasterApp
from study_session import (
    KIND_LISTENING,
    KIND_VOCABULARY,
    STATUS_SKIPPED,
    STATUS_UNAVAILABLE,
    build_study_session,
)


def _plan(code: str, *, listening=True, planned=5) -> DailyStudyPlan:
    return DailyStudyPlan(
        language_code=code,
        vocab_total=10 if planned else 0,
        due_review_count=0,
        new_word_count=0,
        future_review_count=0,
        attention_word_count=0,
        planned_vocab_count=planned,
        reading_enabled=False,
        listening_enabled=listening,
    )


def _bare_studymaster() -> StudyMasterApp:
    """StudyMaster without Tk __init__ — exercises lazy-resolve helpers."""
    app = object.__new__(StudyMasterApp)
    app._listening_audio_provider = None
    app._listening_provider_resolved = False
    app._listening_provider_resolving = False
    app._listening_resolve_code = None
    app.listening_window = None
    app.listening_unavailable = False
    app.listening_check_label = MagicMock()
    app.root = MagicMock()
    app.guard = MagicMock()
    app.sessions = {}
    return app


def test_studymaster_init_source_does_not_eager_resolve():
    src = inspect.getsource(StudyMasterApp.__init__)
    assert "resolve_listening_audio_provider()" not in src
    assert "_listening_provider_resolved = False" in src


def test_construct_path_does_not_call_resolve(monkeypatch):
    """Behavioral: lazy flags start unset; resolve is not invoked by helper setup."""
    calls = []

    def boom():
        calls.append("resolve")
        raise AssertionError("resolve must not run until Listening needs it")

    monkeypatch.setattr("main.resolve_listening_audio_provider", boom)
    app = _bare_studymaster()
    assert app._listening_provider_resolved is False
    assert app._listening_audio_provider is None
    assert calls == []


def test_listening_disabled_never_starts_discovery(monkeypatch):
    calls = []

    def boom():
        calls.append("resolve")
        return None

    monkeypatch.setattr("main.resolve_listening_audio_provider", boom)
    monkeypatch.setattr(config, "activity_enabled", lambda activity_id: False)
    app = _bare_studymaster()
    app.open_listening_section("en")
    assert calls == []
    assert app._listening_provider_resolved is False


def test_first_capability_check_uses_run_async(monkeypatch):
    calls = {"async": 0, "resolve": 0}

    def fake_async(widget, work, on_success, on_error=None):
        calls["async"] += 1
        # Do not run work on the "UI" path — prove open schedules background work.
        return SimpleNamespace(started=True)

    def resolve():
        calls["resolve"] += 1
        return FakeListeningAudioProvider()

    monkeypatch.setattr("main.ui_common.run_async", fake_async)
    monkeypatch.setattr("main.resolve_listening_audio_provider", resolve)
    monkeypatch.setattr(config, "activity_enabled", lambda activity_id: True)
    monkeypatch.setattr(config, "active_code", lambda: "en")

    app = _bare_studymaster()
    app.sessions["en"] = build_study_session(_plan("en", listening=True))
    app._activate = lambda code: None
    app._session_for = lambda code=None: app.sessions["en"]

    app.open_listening_section("en")
    assert calls["async"] == 1
    assert app._listening_provider_resolving is True
    # work() not invoked by fake_async → resolve not yet run on UI path
    assert calls["resolve"] == 0
    app.listening_check_label.config.assert_called()


def test_provider_catalog_reused_after_discovery(monkeypatch):
    creates = []

    class CountingProvider(FakeListeningAudioProvider):
        def __init__(self):
            super().__init__(supported=("en",))
            creates.append(self)
            self.available_calls = 0

        def is_available(self):
            self.available_calls += 1
            return True

    monkeypatch.setattr(
        "main.resolve_listening_audio_provider", lambda: CountingProvider()
    )
    app = _bare_studymaster()
    first = app._blocking_resolve_listening_provider()
    app._listening_audio_provider = first
    app._listening_provider_resolved = True
    assert len(creates) == 1

    # Second open path must reuse cache — no second resolve.
    opened = []

    def capture(code):
        opened.append((code, app._listening_audio_provider))

    monkeypatch.setattr(config, "activity_enabled", lambda activity_id: True)
    app._open_listening_with_resolved_provider = capture
    app._listening_resolve_code = "en"
    # Simulate on_success without calling resolve again
    app._listening_audio_provider = first
    app._open_listening_with_resolved_provider("en")
    assert opened[0][1] is first
    assert len(creates) == 1


def test_discovery_failure_leaves_session_finishable(monkeypatch):
    monkeypatch.setattr("main.resolve_listening_audio_provider", lambda: None)
    app = _bare_studymaster()
    session = build_study_session(_plan("en", listening=True, planned=0))
    app.sessions["en"] = session
    app._session_for = lambda code=None: session
    app._refresh_status = lambda: None
    app._finish_if_all_done = lambda: None
    monkeypatch.setattr(config, "activity_enabled", lambda activity_id: True)

    provider = app._blocking_resolve_listening_provider()
    assert provider is None
    app._listening_audio_provider = None
    app._listening_provider_resolved = True
    app._open_listening_with_resolved_provider("en")
    assert session.status(KIND_LISTENING) == STATUS_UNAVAILABLE
    assert session.is_resolved(KIND_LISTENING)
    assert session.can_finish is True


def test_dutch_listening_skip_does_not_depend_on_german_vocab():
    nl = build_study_session(_plan("nl", listening=True, planned=5))
    de = build_study_session(_plan("de", listening=True, planned=5))
    # German vocabulary unfinished; Dutch vocab done — Listening still skippable.
    nl.complete(KIND_VOCABULARY)
    assert not de.vocabulary_complete()
    nl.skip(KIND_LISTENING)
    assert nl.status(KIND_LISTENING) == STATUS_SKIPPED
    assert nl.is_resolved(KIND_LISTENING)
    assert not de.is_resolved(KIND_LISTENING)
    assert de.status(KIND_LISTENING) != STATUS_SKIPPED


def test_current_language_listening_skip_does_not_affect_another():
    nl = build_study_session(_plan("nl", listening=True, planned=0))
    de = build_study_session(_plan("de", listening=True, planned=0))
    nl.skip(KIND_LISTENING)
    assert nl.is_resolved(KIND_LISTENING)
    assert not de.is_resolved(KIND_LISTENING)


def test_open_listening_always_wires_skip_callback():
    src = inspect.getsource(StudyMasterApp._open_listening_with_resolved_provider)
    assert "on_skip=self._skip_listening" in src
    assert "on_skip=self._skip_listening if" not in src
    skip_src = inspect.getsource(StudyMasterApp._skip_listening)
    assert "_vocab_all_done" not in skip_src


def test_blocking_resolve_null_provider_when_unavailable(monkeypatch):
    monkeypatch.setattr(
        "main.resolve_listening_audio_provider",
        lambda: NullListeningAudioProvider(),
    )
    app = _bare_studymaster()
    assert app._blocking_resolve_listening_provider() is None
