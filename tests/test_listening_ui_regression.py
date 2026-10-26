"""Phase 17C Listening UI regression — theme colors, widgets, safe Play."""

from __future__ import annotations

import inspect
from types import SimpleNamespace
from unittest.mock import MagicMock

import ui_common
from listening import FakeListeningAudioProvider, ListeningItem
from listening_app import ListeningApp
from word_lookup_overlay import open_word_action_overlay, prepare_clickable_text


SAMPLE = ListeningItem(
    text="The train leaves at nine.",
    question="What time does the train leave?",
    answer="at nine",
    alternatives=("nine",),
    meaning="Xe lửa khởi hành lúc chín giờ.",
)


def _patch_listening_shell(monkeypatch, *, boom_clickable=False):
    monkeypatch.setattr("listening_app.ui_common.apply_theme", lambda *_a, **_k: None)
    monkeypatch.setattr(
        "listening_app.ui_common.ScreenGuard",
        lambda *a, **k: MagicMock(confirm_emergency_exit=lambda: False),
    )
    monkeypatch.setattr(
        "listening_app.ttk.Frame",
        lambda *a, **k: MagicMock(pack=MagicMock(), winfo_children=lambda: []),
    )
    monkeypatch.setattr(
        "listening_app.ttk.Label", lambda *a, **k: MagicMock(pack=MagicMock())
    )
    monkeypatch.setattr(
        "listening_app.ttk.Button",
        lambda *a, **k: MagicMock(pack=MagicMock(), state=MagicMock()),
    )
    monkeypatch.setattr(
        "listening_app.ttk.Entry",
        lambda *a, **k: MagicMock(pack=MagicMock(), focus_set=MagicMock()),
    )
    monkeypatch.setattr("listening_app.tk.StringVar", lambda: MagicMock())

    if boom_clickable:

        def boom(*_a, **_k):
            raise AttributeError("module 'ui_common' has no attribute 'COLOR_TEXT'")

        monkeypatch.setattr("listening_app.prepare_clickable_text", boom)
    else:
        monkeypatch.setattr(
            "listening_app.prepare_clickable_text",
            lambda *a, **k: MagicMock(
                pack=MagicMock(),
                get=MagicMock(return_value=SAMPLE.question),
            ),
        )

    window = MagicMock()
    window.winfo_exists.return_value = True
    for name in ("configure", "title", "geometry", "bind"):
        setattr(window, name, MagicMock())
    return window


def test_prepare_clickable_text_avoids_missing_theme_attrs():
    assert not hasattr(ui_common, "COLOR_TEXT")
    for name in ("COLOR_CARD", "COLOR_BORDER", "COLOR_MUTED", "FONT_BODY"):
        assert hasattr(ui_common, name)

    src = inspect.getsource(prepare_clickable_text)
    # Must not reference the nonexistent theme attribute as a runtime lookup.
    assert "ui_common.COLOR_TEXT" not in src
    assert "foreground or" in src

    created = {}

    class FakeText:
        def __init__(self, parent, **kwargs):
            created["kwargs"] = kwargs

        def insert(self, *_a):
            return None

        def configure(self, **_k):
            return None

        def bind(self, *_a, **_k):
            return None

    class FakeStyle:
        def lookup(self, *_a, **_k):
            return "#ffffff"

    monkeypatch_tk = MagicMock()
    # Patch via module under test
    import word_lookup_overlay as overlay

    original_text = overlay.tk.Text
    original_style = overlay.ttk.Style
    overlay.tk.Text = FakeText
    overlay.ttk.Style = FakeStyle
    try:
        widget = prepare_clickable_text(MagicMock(), SAMPLE.question)
        assert isinstance(widget, FakeText)
        assert created["kwargs"]["foreground"] == "#1a1a1a"
        assert created["kwargs"]["font"] == ui_common.FONT_BODY
    finally:
        overlay.tk.Text = original_text
        overlay.ttk.Style = original_style


def test_listening_exercise_renders_essential_widgets(monkeypatch):
    window = _patch_listening_shell(monkeypatch)
    app = ListeningApp(
        window,
        language_code="en",
        audio_provider=FakeListeningAudioProvider(),
        item=SAMPLE,
        locked=False,
    )
    assert app.session is not None
    assert app.session.unavailable is False
    for attr in (
        "play_button",
        "question_text",
        "answer_entry",
        "status",
        "check_button",
        "continue_button",
        "transcript_frame",
    ):
        assert hasattr(app, attr), attr
    assert app.transcript_text is None
    assert app.meaning_label is None


def test_play_after_init_failure_no_attribute_error(monkeypatch):
    window = _patch_listening_shell(monkeypatch, boom_clickable=True)
    app = ListeningApp(
        window,
        language_code="en",
        audio_provider=FakeListeningAudioProvider(),
        item=SAMPLE,
        locked=False,
    )
    assert app.session.unavailable is True
    assert getattr(app, "status", None) is None
    assert getattr(app, "play_button", None) is None
    # Must not raise AttributeError on Play after a failed build.
    app._play()
    assert app._play_busy is False


def test_run_async_prints_callback_exceptions(monkeypatch):
    widget = MagicMock()
    widget.winfo_exists.return_value = True

    def after(_ms, fn):
        fn()

    widget.after.side_effect = after
    printed = []

    import traceback

    monkeypatch.setattr(
        traceback, "print_exc", lambda: printed.append("callback-error")
    )

    def boom(_value):
        raise AttributeError("missing status")

    # Must not raise out of run_async delivery — errors are printed, not swallowed silently.
    ui_common.run_async(widget, lambda: True, boom)
    assert printed == ["callback-error"]


def test_word_overlay_source_keeps_screenguard_safe():
    src = inspect.getsource(open_word_action_overlay)
    assert "pause_enforcement" not in src
    assert "Toplevel" not in src
    assert "fullscreen" not in src.lower()


def test_check_reveals_transcript_only_after_play_and_answer(monkeypatch):
    window = _patch_listening_shell(monkeypatch)
    captured_texts = []

    def fake_clickable(parent, content, **kwargs):
        widget = MagicMock(pack=MagicMock())
        widget.get = MagicMock(return_value=content)
        captured_texts.append(content)
        return widget

    monkeypatch.setattr("listening_app.prepare_clickable_text", fake_clickable)
    app = ListeningApp(
        window,
        language_code="en",
        audio_provider=FakeListeningAudioProvider(),
        item=SAMPLE,
        locked=False,
    )
    assert SAMPLE.question in captured_texts
    assert SAMPLE.text not in captured_texts

    app.session.played = True
    app.answer_var = SimpleNamespace(get=lambda: "at nine")
    app._check()
    assert app.session.answered is True
    assert SAMPLE.text in captured_texts
