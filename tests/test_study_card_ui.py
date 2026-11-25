"""Study card: one attempt, explicit Continue, and an unlocked leave."""

from __future__ import annotations

import json

import tkinter as tk

import config
import ui_common
from attempt_history import AttemptHistory
from home_app import FreeHome
from progress import Progress
from quiz_app import VocabQuizApp
from study_presentation import FUTURE_EXERCISE_KINDS
from vocab_store import VocabStore


class _Guard:
    def __init__(self, window, enabled=None, on_close_attempt=None, on_unlocked_close=None):
        self.enabled = True
        self.window = window
        self.on_close_attempt = on_close_attempt
        self.on_unlocked_close = on_unlocked_close
        window.protocol("WM_DELETE_WINDOW", on_close_attempt or (lambda: None))
        self.messages = []

    def show_error(self, title, message):
        self.messages.append((title, message))

    def show_info(self, title, message):
        self.messages.append((title, message))

    def allows_unlocked_leave(self):
        return False

    def confirm_emergency_exit(self):
        return False


def _texts(widget) -> str:
    found = []

    def walk(node):
        try:
            found.append(str(node.cget("text")))
        except Exception:
            pass
        for child in node.winfo_children():
            try:
                managed = bool(child.winfo_manager())
            except Exception:
                managed = True
            if managed:
                walk(child)

    walk(widget)
    return "\n".join(found)


def test_study_card_waits_and_records_once(tmp_path, monkeypatch):
    monkeypatch.setenv("LG_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LG_APP_ENVIRONMENT", "development")
    monkeypatch.setenv("ACCOUNT_SERVER_URL", "http://127.0.0.1:9")
    monkeypatch.delenv("LG_RC_SMOKE", raising=False)
    monkeypatch.delenv("STUDY_SYNC_ENABLED", raising=False)
    monkeypatch.setattr(config, "LOCK_SCREEN", False)
    monkeypatch.setattr(config, "FORCE_SENTENCE_ON_WRONG", False)

    vocab = tmp_path / "vocab.json"
    vocab.write_text(
        json.dumps([{"word": "fiets", "meaning": "bicycle"}], ensure_ascii=False),
        encoding="utf-8",
    )
    store = VocabStore(str(vocab))
    progress = Progress(str(tmp_path / "progress.json"))
    attempts = AttemptHistory(str(tmp_path / "attempts.jsonl"), language_code="nl")

    root = tk.Tk()
    root.withdraw()
    try:
        locked_window = tk.Toplevel(root)
        real_guard = ui_common.ScreenGuard
        monkeypatch.setattr(ui_common, "ScreenGuard", _Guard)
        locked = VocabQuizApp(
            locked_window,
            store=store,
            progress=progress,
            locked=True,
            allow_manage=False,
            target=1,
            language_code="nl",
        )
        assert locked.guard.enabled is True
        assert locked.emergency_button.winfo_manager() == "pack"
        assert locked.leave_button.winfo_manager() == ""
        locked.completed = False
        locked.required = True
        locked._on_close_attempt()
        assert locked.completed is False
        assert locked_window.winfo_exists()
        locked_window.destroy()
        monkeypatch.setattr(ui_common, "ScreenGuard", real_guard)

        finished = []
        window = tk.Toplevel(root)
        app = VocabQuizApp(
            window,
            store=store,
            progress=progress,
            on_completed=lambda: finished.append("done"),
            locked=False,
            allow_manage=False,
            target=2,
            language_code="nl",
        )
        app.engine.attempt_history = attempts
        window.update()
        visible = _texts(app.shell.host).lower()
        assert "manage vocabulary" not in visible
        assert "write a sentence" not in visible
        assert "go to reading" not in visible
        for kind in FUTURE_EXERCISE_KINDS:
            assert kind.replace("_", " ") not in visible
        assert "0/2" in app.shell.counter.cget("text")
        assert app.shell.sentence_button.winfo_manager() == ""

        app._submit()
        assert attempts.load_attempts() == []
        assert app._phase == "answer"

        app.shell.exercise.entry.insert(0, "nope")
        app._on_window_return()
        assert len(attempts.load_attempts()) == 1
        assert "0/2" in app.shell.counter.cget("text")
        assert "fiets" in app.feedback_label.cget("text")
        assert app._pending_after_id is None
        app._on_window_return()
        assert len(attempts.load_attempts()) == 1

        app.hint_button.focus_set()
        window.update()
        focused = window.focus_get()
        focused.event_generate("<Return>")
        window.update()
        assert len(attempts.load_attempts()) == 1

        app._continue()
        app._continue()
        assert app._phase == "answer"
        assert len(attempts.load_attempts()) == 1

        app._show_hint()
        assert app.engine.hint_used is True
        assert app.shell.exercise.support.cget("text")
        app.shell.exercise.entry.insert(0, "fiets")
        app._submit()
        assert len(attempts.load_attempts()) == 2
        assert "1/2" in app.shell.counter.cget("text")
        assert app.hint_button.cget("state") == "disabled"
        app.hint_button.invoke()
        assert len(attempts.load_attempts()) == 2
        assert "fiets" in app.feedback_label.cget("text")

        app._continue()
        app.shell.exercise.entry.insert(0, "fiets")
        app._submit()
        app._on_window_return()
        assert app._phase == "complete"
        assert app.completed is True
        assert finished == []
        assert len(attempts.load_attempts()) == 3
        hinted = attempts.load_attempts()[1]
        assert hinted.hint_used is True
        assert hinted.correct is False
        assert hinted.verdict == "exact"
        assert "2/2" in app.shell.counter.cget("text")
        app._on_window_return()
        assert finished == ["done"]
        assert not window.winfo_exists()

        home = FreeHome(root)
        assert home._study_master_class().__name__ == "StudyMasterApp"
        seen = {}

        class Sentinel:
            def __init__(self, root, on_finished=None):
                seen["callback"] = on_finished

        home._study_master_class = lambda: Sentinel
        home._start_study()
        assert callable(seen["callback"])
        home._on_study_finished()
        restored = _texts(root)
        assert "Hôm nay" in restored or "Today" in restored
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass
