"""Phase 17C — ListeningApp async content + lookup wiring (fakes, no Tk display)."""

from __future__ import annotations

import inspect
from types import SimpleNamespace
from unittest.mock import MagicMock

from listening import FakeListeningAudioProvider, ListeningItem
from listening_app import ListeningApp
from word_lookup_overlay import open_word_action_overlay


def test_listening_app_uses_run_async_for_content(monkeypatch):
    calls = {"async": 0}

    def fake_async(widget, work, on_success, on_error=None):
        calls["async"] += 1
        return SimpleNamespace(ok=True)

    monkeypatch.setattr("listening_app.ui_common.run_async", fake_async)
    monkeypatch.setattr("listening_app.ui_common.apply_theme", lambda *_a, **_k: None)
    monkeypatch.setattr(
        "listening_app.ui_common.ScreenGuard",
        lambda *a, **k: MagicMock(confirm_emergency_exit=lambda: False),
    )

    window = MagicMock()
    window.winfo_exists.return_value = True
    # Minimal pack/geometry surface
    for name in ("configure", "title", "geometry", "bind"):
        setattr(window, name, MagicMock())

    # Avoid real ttk packing by short-circuiting after loading schedule:
    # Construct with content_loader deferred — __init__ will call run_async.
    frame_children = []

    class FakeFrame:
        def __init__(self, *a, **k):
            pass

        def pack(self, **k):
            return None

        def winfo_children(self):
            return list(frame_children)

    monkeypatch.setattr("listening_app.ttk.Frame", FakeFrame)
    monkeypatch.setattr("listening_app.ttk.Label", lambda *a, **k: MagicMock(pack=MagicMock()))
    monkeypatch.setattr("listening_app.ttk.Button", lambda *a, **k: MagicMock(pack=MagicMock()))

    app = ListeningApp(
        window,
        language_code="en",
        audio_provider=FakeListeningAudioProvider(),
        content_loader=lambda: (_ for _ in ()).throw(AssertionError("sync")),
        locked=False,
    )
    assert calls["async"] == 1
    assert app.session is None  # still loading


def test_prebuilt_item_skips_async_loader(monkeypatch):
    monkeypatch.setattr("listening_app.ui_common.apply_theme", lambda *_a, **_k: None)
    monkeypatch.setattr(
        "listening_app.ui_common.ScreenGuard",
        lambda *a, **k: MagicMock(),
    )
    monkeypatch.setattr("listening_app.ttk.Frame", lambda *a, **k: MagicMock(pack=MagicMock(), winfo_children=lambda: []))
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
    item = ListeningItem(
        text="The train leaves at nine.",
        question="What time does the train leave?",
        answer="at nine",
        alternatives=("nine",),
        meaning="Meaning.",
    )
    app = ListeningApp(
        window,
        language_code="en",
        audio_provider=FakeListeningAudioProvider(),
        item=item,
        locked=False,
    )
    assert app.session is not None
    assert app.session.item.answer == "at nine"
    assert app.session.unavailable is False


def test_late_callback_ignores_closed_window(monkeypatch):
    monkeypatch.setattr("listening_app.ui_common.apply_theme", lambda *_a, **_k: None)
    monkeypatch.setattr(
        "listening_app.ui_common.ScreenGuard",
        lambda *a, **k: MagicMock(),
    )
    monkeypatch.setattr("listening_app.ttk.Frame", lambda *a, **k: MagicMock(pack=MagicMock(), winfo_children=lambda: []))
    monkeypatch.setattr("listening_app.ttk.Label", lambda *a, **k: MagicMock(pack=MagicMock()))
    monkeypatch.setattr("listening_app.ttk.Button", lambda *a, **k: MagicMock(pack=MagicMock()))

    captured = {}

    def fake_async(widget, work, on_success, on_error=None):
        captured["on_success"] = on_success
        return SimpleNamespace()

    monkeypatch.setattr("listening_app.ui_common.run_async", fake_async)
    window = MagicMock()
    window.winfo_exists.return_value = True
    app = ListeningApp(
        window,
        language_code="en",
        audio_provider=FakeListeningAudioProvider(),
        locked=False,
    )
    app._closed = True
    item = ListeningItem(
        text="The train leaves at nine.",
        question="What time does the train leave?",
        answer="at nine",
        meaning="Meaning.",
    )
    captured["on_success"](item)
    assert app.session is None


def test_word_overlay_does_not_pause_screenguard(monkeypatch):
    src = inspect.getsource(open_word_action_overlay)
    assert "pause_enforcement" not in src
    assert "Toplevel" not in src
    assert "fullscreen" not in src.lower()


def test_check_reveals_transcript_not_before(monkeypatch):
    src = inspect.getsource(ListeningApp._build_exercise)
    assert "session.item.text" not in src or "question" in src
    # Transcript content is only inserted in _check.
    check_src = inspect.getsource(ListeningApp._check)
    assert "session.item.text" in check_src
    assert "session.item.meaning" in check_src
    build_src = inspect.getsource(ListeningApp._build_exercise)
    assert "self.session.item.question" in build_src
