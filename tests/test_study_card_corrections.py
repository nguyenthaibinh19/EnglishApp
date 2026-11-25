"""Completion, sentence practice, session progress, and real key events.

Run this file in its own Python process. A second Tk() after another test
file has destroyed its root is a Tcl limitation on this machine, not a pass.
"""

from __future__ import annotations

import json

import tkinter as tk

import ai_teacher
import config
import ui_common
from attempt_history import AttemptHistory
from home_app import FreeHome
from quiz_app import VocabQuizApp
from vocab_store import VocabStore
from progress import Progress


def _isolate(monkeypatch, tmp_path):
    monkeypatch.setenv("LG_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LG_APP_ENVIRONMENT", "development")
    monkeypatch.setenv("ACCOUNT_SERVER_URL", "http://127.0.0.1:9")
    monkeypatch.delenv("LG_RC_SMOKE", raising=False)
    monkeypatch.delenv("STUDY_SYNC_ENABLED", raising=False)
    monkeypatch.delenv("ACCOUNT_TOKEN", raising=False)
    monkeypatch.setattr(config, "LOCK_SCREEN", False)


def _store(tmp_path, words):
    tmp_path.mkdir(parents=True, exist_ok=True)
    vocab = tmp_path / "vocab.json"
    vocab.write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
    return VocabStore(str(vocab))


def _open(root, tmp_path, *, target, finished, words=None):
    window = tk.Toplevel(root)
    app = VocabQuizApp(
        window,
        store=_store(tmp_path, words or [{"word": "fiets", "meaning": "bicycle"}]),
        progress=Progress(str(tmp_path / "progress.json")),
        on_completed=lambda: finished.append("done"),
        locked=False,
        allow_manage=False,
        target=target,
        language_code="nl",
    )
    app.engine.attempt_history = AttemptHistory(str(tmp_path / "attempts.jsonl"), language_code="nl")
    window.deiconify()
    window.geometry("560x520+3200+40")
    window.update()
    return window, app


def _answer(app, text):
    app.shell.exercise.entry.insert(0, text)
    app.shell.exercise.focus_answer()
    app.window.update()
    focused = app.window.focus_get()
    if focused is None:
        app.shell.exercise.entry._entry.focus_force()
        app.window.update()
        focused = app.window.focus_get()
    assert focused is not None
    focused.event_generate("<Return>")
    app.window.update()


def _reach_complete(root, tmp_path, finished):
    window, app = _open(root, tmp_path, target=1, finished=finished)
    _answer(app, "fiets")
    assert app._phase == "feedback"
    assert finished == []
    app.continue_button.invoke()
    app.window.update()
    assert app._phase == "complete"
    assert app.completed is True
    assert finished == []
    return window, app


def test_completion_sentence_progress_and_keys(tmp_path, monkeypatch):
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setattr(config, "FORCE_SENTENCE_ON_WRONG", True)
    monkeypatch.setattr(ai_teacher, "is_configured", lambda: False)

    root = tk.Tk()
    root.withdraw()
    try:
        finished = []
        window, app = _reach_complete(root, tmp_path / "click", finished)
        app.continue_button.invoke()
        try:
            app.continue_button.invoke()
        except tk.TclError:
            pass
        assert finished == ["done"]
        assert not window.winfo_exists()

        finished = []
        window, app = _reach_complete(root, tmp_path / "enter", finished)
        app.continue_button.focus_set()
        window.update()
        window.focus_get().event_generate("<Return>")
        window.update()
        assert finished == ["done"]
        assert not window.winfo_exists()

        finished = []
        window, app = _reach_complete(root, tmp_path / "space", finished)
        app.continue_button.focus_set()
        window.update()
        window.focus_get().event_generate("<space>")
        window.update()
        assert finished == ["done"]
        assert not window.winfo_exists()

        finished = []
        window, app = _reach_complete(root, tmp_path / "close", finished)
        window.tk.call(window.protocol("WM_DELETE_WINDOW"))
        window.update()
        assert finished == ["done"]
        assert not window.winfo_exists()

        finished = []
        window, app = _open(root, tmp_path / "leave", target=2, finished=finished)
        app.leave_button.invoke()
        window.update()
        assert finished == []
        assert app.completed is False
        assert not window.winfo_exists()

        finished = []
        window, app = _open(
            root,
            tmp_path / "progress",
            target=2,
            finished=finished,
            words=[
                {"word": "fiets", "meaning": "bicycle"},
                {"word": "huis", "meaning": "house"},
            ],
        )
        assert "0/2" in app.shell.counter.cget("text")
        assert app.shell.progress.get() == 0
        assert "master" not in app.shell.counter.cget("text").lower()
        _answer(app, "nope")
        assert app._phase == "feedback"
        assert len(app.engine.attempt_history.load_attempts()) == 1
        assert "0/2" in app.shell.counter.cget("text")
        app.continue_button.focus_set()
        window.update()
        window.focus_get().event_generate("<Return>")
        window.update()
        assert len(app.engine.attempt_history.load_attempts()) == 1
        assert app._phase == "answer"
        assert "0/2" in app.shell.counter.cget("text")

        app._show_hint()
        app.shell.exercise.entry.insert(0, app.engine.current_entry["word"])
        app.check_button.invoke()
        window.update()
        hinted = app.engine.attempt_history.load_attempts()[-1]
        assert hinted.hint_used is True
        assert hinted.correct is False
        assert "1/2" in app.shell.counter.cget("text")
        assert abs(app.shell.progress.get() - 0.5) < 0.01
        window.destroy()

        monkeypatch.setattr(ai_teacher, "is_configured", lambda: True)
        ai_calls = []

        def fake_async(widget, work, on_success, on_error=None):
            ai_calls.append(work)
            on_success({
                "is_correct_usage": False,
                "score": 0.4,
                "feedback_vi": "Use the verb.",
                "corrected_sentence": "Ik heb een fiets.",
                "suggested_sentence": "",
            })

        monkeypatch.setattr(ui_common, "run_async", fake_async)
        finished = []
        window, app = _open(root, tmp_path / "forced", target=2, finished=finished)
        assert app.shell.sentence_button.winfo_manager() == ""
        assert app.check_button.winfo_manager() == "pack"
        _answer(app, "nope")
        assert app.shell.sentence_button.winfo_manager() == "pack"
        assert app.check_button.winfo_manager() == ""
        app.continue_button.invoke()
        window.update()
        assert app.practice_mode == "forced"
        assert app.practice_view.winfo_ismapped()
        assert app._phase == "practice"
        skip = app.back_button.cget("text").lower()
        assert "skip" in skip or "bỏ qua" in skip
        app.back_button.invoke()
        window.update()
        assert app._phase == "answer"
        assert app.quiz_view.winfo_ismapped()
        assert ai_calls == []
        assert finished == []

        _answer(app, "nope")
        app.shell.sentence_button.invoke()
        window.update()
        assert app.practice_mode == "free"
        back = app.back_button.cget("text").lower()
        assert "quiz" in back or "làm bài" in back
        app.practice_input.insert("1.0", "Ik heb een fiets.")
        app.grade_button.invoke()
        window.update()
        assert ai_calls
        assert "Use the verb." in app.practice_result.get("1.0", "end")
        app.back_button.invoke()
        window.update()
        assert app._phase == "answer"
        assert finished == []

        def fake_error(widget, work, on_success, on_error=None):
            on_error(RuntimeError("offline"))

        monkeypatch.setattr(ui_common, "run_async", fake_error)
        _answer(app, "nope")
        app.shell.sentence_button.invoke()
        app.practice_input.insert("1.0", "Ik heb een fiets.")
        app.grade_button.invoke()
        window.update()
        assert "offline" in app.practice_result.get("1.0", "end")
        app.back_button.invoke()
        window.update()
        assert app._phase == "answer"
        window.destroy()

        finished = []
        window, app = _open(root, tmp_path / "near", target=2, finished=finished)
        _answer(app, "fiet")
        assert app._last_verdict == "near"
        assert "1/2" in app.shell.counter.cget("text")
        hinted = app.engine.attempt_history.load_attempts()[-1]
        assert hinted.correct is False
        app.continue_button.invoke()
        window.update()
        assert app._phase == "answer"
        assert app.practice_view is None or not app.practice_view.winfo_ismapped()
        window.destroy()

        finished = []
        window, app = _open(root, tmp_path / "tab", target=2, finished=finished)
        window.deiconify()
        window.geometry("560x520+3200+40")
        window.update()
        app.shell.exercise.focus_answer()
        window.update()
        seen = []
        focused = window.focus_get()
        for _ in range(6):
            focused.event_generate("<Tab>")
            window.update()
            focused = window.focus_get()
            seen.append(focused)
        labels = {app.hint_button._text_label, app.check_button._text_label, app.leave_button._text_label}
        assert labels.issubset(set(seen))
        for button in (app.hint_button, app.check_button, app.leave_button):
            button._text_label.focus_set()
            window.update()
            assert int(button.cget("border_width")) == 2

        before = len(app.engine.attempt_history.load_attempts())
        trace = []
        app.check_button.configure(state="disabled", command=lambda: trace.append("check"))
        window.update()
        assert str(app.check_button.cget("state")) == "disabled"
        app.check_button._text_label.focus_set()
        window.update()
        assert window.focus_get() is app.check_button._text_label
        window.focus_get().event_generate("<Return>")
        window.focus_get().event_generate("<space>")
        window.update()
        app.check_button.invoke()
        window.update()
        assert trace == []
        assert len(app.engine.attempt_history.load_attempts()) == before
        assert window.winfo_exists()

        home = FreeHome(root)
        seen_home = {}

        class Sentinel:
            def __init__(self, root, on_finished=None):
                seen_home["callback"] = on_finished

        home._study_master_class = lambda: Sentinel
        home._start_study()
        assert callable(seen_home["callback"])
        home._on_study_finished()
        restored = root.winfo_children()
        assert restored
        home._stop_sync_status_polling()
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass
