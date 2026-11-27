"""Adaptive preview window. This file exercises the real CustomTkinter card."""

from __future__ import annotations

import random
import threading
import tkinter as tk

import config
import pytest
import ui_foundation
import voice_prefs
from adaptive_vocabulary import (
    INDEPENDENT_RECALL,
    MISSING_LETTERS,
    AdaptiveSessionBridge,
    AdaptiveVocabularySession,
)
from adaptive_vocabulary_app import AdaptiveVocabularyApp, _voice_problem
from attempt_history import AttemptHistory
from daily_study import DailyStudyPlan
from progress import Progress
from listening import ListeningAudioError
from speech_player import reset_playback_state
from study_session import KIND_LISTENING, KIND_READING, build_study_session

FIETS = "11111111-1111-4111-8111-111111111111"
HUIS = "22222222-2222-4222-8222-222222222222"
BOEK = "33333333-3333-4333-8333-333333333333"
WATER = "44444444-4444-4444-8444-444444444444"


def word(vid, text, meaning, example=""):
    entry = {"id": vid, "word": text, "meaning": meaning}
    if example:
        entry["example"] = example
    return entry


def pool():
    return [
        word(FIETS, "de fiets", "bicycle", "Ik ga met de fiets."),
        word(HUIS, "het huis", "house"),
        word(BOEK, "het boek", "book"),
        word(WATER, "het water", "water"),
    ]

class _SilentVoice:
    def __init__(self):
        self.calls = []

    def play(self, text, language_code, rate=0, voice_name=None):
        self.calls.append((text, language_code, rate, voice_name))
        raise ListeningAudioError("No voice for this language on this PC. You can continue.")


def _during_mainloop(window, action, predicate, steps=40):
    """Run action while Tk is in mainloop so worker audio callbacks can land."""
    state = {"started": False, "ok": False}

    def tick(left):
        if not state["started"]:
            state["started"] = True
            action()
        try:
            state["ok"] = bool(predicate())
        except tk.TclError:
            state["ok"] = False
        if state["ok"] or left <= 0:
            window.quit()
            return
        window.after(30, lambda: tick(left - 1))

    window.after(0, lambda: tick(steps))
    window.mainloop()
    return state["ok"]


@pytest.fixture(scope="module")
def tk_root():
    root = tk.Tk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except tk.TclError:
        pass


def _close_window(window):
    try:
        if window.winfo_exists():
            window.destroy()
    except tk.TclError:
        pass


def _plan():
    return DailyStudyPlan(
        language_code="nl",
        vocab_total=1,
        due_review_count=0,
        new_word_count=1,
        future_review_count=0,
        attention_word_count=0,
        planned_vocab_count=1,
        reading_enabled=True,
        listening_enabled=True,
    )


def test_preview_leave_and_missing_voice_do_not_record(tmp_path, monkeypatch, tk_root):
    reset_playback_state()
    controller = AdaptiveVocabularySession(
        [pool()[0]],
        language_code="nl",
        pool=pool(),
        rng=random.Random(4),
    )
    study = build_study_session(_plan())
    bridge = AdaptiveSessionBridge(study, controller, locked=False)
    progress = Progress(str(tmp_path / "progress.json"))
    attempts = AttemptHistory(str(tmp_path / "attempts.jsonl"), language_code="nl")
    left = []
    voice = _SilentVoice()
    monkeypatch.setattr(voice_prefs, "selected_voice_name", lambda code: "Microsoft Frank" if code == "nl" else "")
    window = tk.Toplevel(tk_root)
    try:
        app = AdaptiveVocabularyApp(
            window,
            controller,
            bridge=bridge,
            progress=progress,
            attempts=attempts,
            on_completed=lambda: left.append("done"),
            on_leave=lambda: left.append("leave"),
            provider=voice,
            locked=False,
        )
        window.update()
        assert "de fiets" in app.shell.exercise.frame.winfo_children()[1].cget("text")
        assert _during_mainloop(
            window,
            lambda: app.shell.exercise.normal_button.invoke(),
            lambda: config.ui("Chưa có giọng", "No voice")
            in app.shell.exercise.voice_note.cget("text"),
        )
        assert app.shell.check_button.cget("state") == "normal"
        assert voice.calls[0][2] == 0
        assert voice.calls[0][3] == "Microsoft Frank"
        assert _during_mainloop(
            window,
            lambda: app.shell.exercise.slow_button.invoke(),
            lambda: len(voice.calls) >= 2
            and config.ui("Chưa có giọng", "No voice")
            in app.shell.exercise.voice_note.cget("text"),
        )
        assert voice.calls[1][2] == -4
        app._leave()
        tk_root.update()
    finally:
        _close_window(window)
        reset_playback_state()
    assert left == ["leave"]
    assert study.vocabulary_complete() is False
    assert study.status(KIND_READING) == "pending"
    assert study.status(KIND_LISTENING) == "pending"
    assert attempts.load_attempts() == []
    assert progress.data["words"] == {}


def test_wrong_independent_answer_records_once_on_the_card(tmp_path, tk_root):
    controller = AdaptiveVocabularySession(
        [word(FIETS, "de fiets", "bicycle")],
        language_code="nl",
        pool=pool(),
        rng=random.Random(4),
        level_overrides={FIETS: INDEPENDENT_RECALL},
    )
    progress = Progress(str(tmp_path / "progress.json"))
    attempts = AttemptHistory(str(tmp_path / "attempts.jsonl"), language_code="nl")
    finished = []
    window = tk.Toplevel(tk_root)
    try:
        app = AdaptiveVocabularyApp(
            window,
            controller,
            progress=progress,
            attempts=attempts,
            on_completed=lambda: finished.append("done"),
            provider=_SilentVoice(),
        )
        window.update()
        assert config.ui("Tự nhớ", "Recall") in app.shell.exercise.kicker.cget("text")
        app.shell.exercise.entry.insert(0, "nope")
        app._check()
        window.update()
        assert "de fiets" in app.shell.feedback.cget("text")
        app._check()
        assert len(attempts.load_attempts()) == 1
        assert attempts.load_attempts()[0].correct is False
        assert app._applied_writes == 1
        app._continue()
        assert finished == []
    finally:
        _close_window(window)


class _Key:
    def __init__(self, keysym, char="", state=0):
        self.keysym = keysym
        self.char = char
        self.state = state


def _inner(entry):
    return getattr(entry, "_entry", entry)


def _answer_whole_word(app, window) -> None:
    card = app.session.current_card()
    exercise = app.shell.exercise
    inputs = getattr(exercise, "inputs", None)
    if inputs:
        fills = [card.reveal_word[index] for index, char in enumerate(card.mask) if char == "_"]
        exercise._on_key(_Key(fills[0], fills[0]), 0)
        exercise._on_key(_Key("BackSpace"), 0 if exercise.inputs[0].get() else 1)
        for entry, char in zip(exercise.inputs, fills):
            entry.delete(0, "end")
            entry.insert(0, char)
        inner = getattr(exercise.inputs[-1], "_entry", exercise.inputs[-1])
        inner.focus_set()
        inner.event_generate("<Return>")
    else:
        exercise.entry.insert(0, card.reveal_word)
        inner = getattr(exercise.entry, "_entry", exercise.entry)
        inner.focus_set()
        inner.event_generate("<Return>")
    window.update()


def test_empty_plan_does_not_show_successful_completion(tmp_path, tk_root):
    controller = AdaptiveVocabularySession([], language_code="nl", rng=random.Random(1))
    study = build_study_session(_plan())
    bridge = AdaptiveSessionBridge(study, controller, locked=False)
    finished = []
    window = tk.Toplevel(tk_root)
    try:
        app = AdaptiveVocabularyApp(
            window,
            controller,
            bridge=bridge,
            on_completed=lambda: finished.append("done"),
            on_leave=lambda: finished.append("leave"),
            provider=_SilentVoice(),
            locked=False,
        )
        window.update()
        assert app._phase == "empty"
        assert config.ui("Chưa có từ", "no planned words") in app.shell.feedback.cget("text")
        app.shell.continue_button.invoke()
        tk_root.update()
    finally:
        _close_window(window)
    assert finished == ["leave"]
    assert study.vocabulary_complete() is False


def test_keyboard_walk_completes_once_without_early_writes(tmp_path, tk_root):
    controller = AdaptiveVocabularySession(
        [pool()[0]],
        language_code="nl",
        pool=pool(),
        rng=random.Random(4),
    )
    study = build_study_session(_plan())
    bridge = AdaptiveSessionBridge(study, controller, locked=False)
    progress = Progress(str(tmp_path / "progress.json"))
    attempts = AttemptHistory(str(tmp_path / "attempts.jsonl"), language_code="nl")
    voice = _SilentVoice()
    finished = []
    window = tk.Toplevel(tk_root)
    try:
        app = AdaptiveVocabularyApp(
            window,
            controller,
            bridge=bridge,
            progress=progress,
            attempts=attempts,
            on_completed=lambda: finished.append("done"),
            provider=voice,
            locked=False,
        )
        window.update()
        seen = []

        assert app.session.current_card().kind == "introduction"
        seen.append("introduction")
        app.shell.check_button.invoke()
        window.update()
        assert attempts.load_attempts() == []

        card = app.session.current_card()
        assert card.kind == "multiple_choice"
        seen.append(card.kind)
        window.focus_force()
        window.event_generate(str(card.correct_index + 1))
        window.update()
        assert app.shell.exercise.choice_index() == card.correct_index
        original = app.session.submit

        def submit_once(*args, **kwargs):
            app._check()
            return original(*args, **kwargs)

        app.session.submit = submit_once
        before = app.session.counters.recognition_successes
        app.shell.check_button.invoke()
        window.update()
        app.session.submit = original
        assert app.session.counters.recognition_successes == before + 1
        chosen = app.shell.exercise.buttons[card.correct_index]
        assert chosen.cget("fg_color") == ui_foundation.COLOR_SOFT_GREEN
        assert attempts.load_attempts() == []
        assert progress.data["words"] == {}
        app.shell.continue_button.invoke()
        window.update()

        card = app.session.current_card()
        assert card.kind == "missing_letters"
        seen.append(card.kind)
        guidance = app.shell.exercise.support.cget("text")
        assert config.ui("Điền các chữ", "Fill in the missing") in guidance
        _answer_whole_word(app, window)
        assert attempts.load_attempts() == []
        app.shell.continue_button.invoke()
        window.update()

        card = app.session.current_card()
        assert card.kind == "guided_typing"
        seen.append(card.kind)
        _answer_whole_word(app, window)
        assert attempts.load_attempts() == []
        assert progress.data["words"] == {}
        app.shell.continue_button.invoke()
        window.update()

        card = app.session.current_card()
        assert card.kind == "independent_recall"
        seen.append(card.kind)
        assert app.shell.hear_button.winfo_ismapped() == 0
        app._hear(0)
        window.update()
        assert voice.calls == []
        _answer_whole_word(app, window)
        assert "de fiets" in app.shell.feedback.cget("text")
        assert len(attempts.load_attempts()) == 1
        assert attempts.load_attempts()[0].correct is True
        assert app._applied_writes == 1
        app._check()
        assert app._applied_writes == 1
        app.shell.continue_button.invoke()
        window.update()
        assert app._phase == "complete"
        assert "1/1" in app.shell.counter.cget("text")
        assert app.shell.progress.get() == 1
        assert config.ui("Xong phần từ vựng", "vocabulary round is done") in app.shell.feedback.cget("text")
        assert config.ui("vẫn còn", "still waiting") in app.shell.feedback.cget("text")
        app.shell.continue_button.invoke()
        app._close_complete()
    finally:
        _close_window(window)
    assert seen == [
        "introduction",
        "multiple_choice",
        "missing_letters",
        "guided_typing",
        "independent_recall",
    ]
    assert finished == ["done"]
    assert bridge.completion_calls == 1
    assert study.vocabulary_complete() is True
    assert study.status(KIND_READING) == "pending"
    assert study.status(KIND_LISTENING) == "pending"


def test_stale_and_busy_voice_stay_on_the_current_card(tk_root):
    reset_playback_state()
    controller = AdaptiveVocabularySession(
        [pool()[0]],
        language_code="nl",
        pool=pool(),
        rng=random.Random(4),
    )
    gate = threading.Event()

    class _Hold:
        def __init__(self):
            self.calls = 0
            self.finished = threading.Event()

        def play(self, *_args, **_kwargs):
            try:
                self.calls += 1
                if self.calls == 1:
                    gate.wait(3)
                    raise ListeningAudioError("old card voice")
                raise ListeningAudioError("current card voice")
            finally:
                self.finished.set()

    voice = _Hold()
    window = tk.Toplevel(tk_root)
    seen = {}
    try:
        app = AdaptiveVocabularyApp(
            window,
            controller,
            provider=voice,
            locked=False,
        )
        window.update()

        def tick(phase, left):
            if phase == 0:
                app.shell.exercise.normal_button.invoke()
                app.shell.exercise.slow_button.invoke()
                seen["busy"] = app.shell.exercise.voice_note.cget("text")
                app.shell.check_button.invoke()
                gate.set()
                window.after(40, lambda: tick(1, left - 1))
                return
            if voice.finished.is_set() and phase == 1:
                window.after(40, lambda: tick(2, left - 1))
                return
            if phase == 2:
                seen["note"] = app.shell.exercise.voice_note.cget("text")
                seen["kind"] = app.session.current_card().kind
                window.quit()
                return
            if left <= 0:
                window.quit()
                return
            window.after(40, lambda: tick(phase, left - 1))

        window.after(0, lambda: tick(0, 40))
        window.mainloop()
    finally:
        gate.set()
        _close_window(window)
        reset_playback_state()
    assert config.ui("Đang phát một đoạn khác", "Another clip is still playing") in seen["busy"]
    assert seen["kind"] == "multiple_choice"
    assert "old card voice" not in seen["note"]


def test_playback_failure_is_not_a_missing_voice(tk_root):
    reset_playback_state()
    missing = _voice_problem(ListeningAudioError("No voice for nl."))
    installed = _voice_problem(
        ListeningAudioError("No Windows text-to-speech voice is installed for Dutch.")
    )
    failed = _voice_problem(ListeningAudioError("Speech playback failed."))
    assert config.ui("Chưa có giọng", "No voice") in missing
    assert config.ui("Chưa có giọng", "No voice") in installed
    assert config.ui("Không phát được", "Playback did not finish") in failed
    assert config.ui("Chưa có giọng", "No voice") not in failed

    class _Broken:
        def play(self, *_args, **_kwargs):
            raise ListeningAudioError("Speech playback failed.")

    controller = AdaptiveVocabularySession(
        [pool()[0]],
        language_code="nl",
        pool=pool(),
        rng=random.Random(4),
    )
    window = tk.Toplevel(tk_root)
    try:
        app = AdaptiveVocabularyApp(window, controller, provider=_Broken(), locked=False)
        window.update()
        assert _during_mainloop(
            window,
            lambda: app.shell.exercise.normal_button.invoke(),
            lambda: config.ui("Không phát được", "Playback did not finish")
            in app.shell.exercise.voice_note.cget("text")
            and config.ui("Chưa có giọng", "No voice")
            not in app.shell.exercise.voice_note.cget("text"),
        )
    finally:
        _close_window(window)
        reset_playback_state()


def test_tab_leaves_the_final_missing_letter_field(tk_root):
    controller = AdaptiveVocabularySession(
        [pool()[0]],
        language_code="nl",
        pool=pool(),
        rng=random.Random(4),
        level_overrides={FIETS: MISSING_LETTERS},
    )
    window = tk.Toplevel(tk_root)
    try:
        app = AdaptiveVocabularyApp(window, controller, provider=_SilentVoice(), locked=False)
        window.deiconify()
        window.focus_force()
        window.update()
        exercise = app.shell.exercise
        inners = [_inner(item) for item in exercise.inputs]
        assert len(inners) >= 2
        inners[0].focus_set()
        window.update()
        assert exercise._on_key(_Key("Tab"), 0) == "break"
        window.update()
        assert window.focus_get() == inners[1]
        assert exercise._on_key(_Key("Tab", state=1), 1) == "break"
        window.update()
        assert window.focus_get() == inners[0]
        assert exercise._on_key(_Key("ISO_Left_Tab"), 0) is None
        last = len(inners) - 1
        inners[last].focus_set()
        window.update()
        assert exercise._on_key(_Key("Tab"), last) is None
        inners[last].event_generate("<Tab>")
        window.update()
        assert window.focus_get() not in inners
        inners[0].focus_set()
        window.update()
        inners[0].event_generate("<Shift-Tab>")
        window.update()
        assert window.focus_get() not in inners
    finally:
        _close_window(window)


def test_incomplete_missing_letters_stay_on_the_card(tmp_path, tk_root):
    controller = AdaptiveVocabularySession(
        [pool()[0]],
        language_code="nl",
        pool=pool(),
        rng=random.Random(4),
        level_overrides={FIETS: MISSING_LETTERS},
    )
    attempts = AttemptHistory(str(tmp_path / "attempts.jsonl"), language_code="nl")
    progress = Progress(str(tmp_path / "progress.json"))
    window = tk.Toplevel(tk_root)
    try:
        app = AdaptiveVocabularyApp(
            window,
            controller,
            progress=progress,
            attempts=attempts,
            provider=_SilentVoice(),
            locked=False,
        )
        window.update()
        exercise = app.shell.exercise
        assert exercise.kind == "missing_letters"
        for entry in exercise.inputs[:-1]:
            entry.insert(0, "e")
        assert exercise.answer_text() == ""
        app.shell.check_button.invoke()
        window.update()
        assert app._phase == "answer"
        assert config.ui("Hãy điền hết", "Fill every missing") in app.shell.feedback.cget("text")
        assert controller.level_of(FIETS) == MISSING_LETTERS
        assert controller.counters.assisted_successes == 0
        assert attempts.load_attempts() == []
        assert progress.data["words"] == {}
    finally:
        _close_window(window)


def test_long_missing_letter_mask_wraps_inside_the_card(tk_root):
    from study_presentation import MissingLettersExercise

    window = tk.Toplevel(tk_root)
    window.geometry("480x560")
    card = type("Card", (), {})()
    card.mask = "_" * 16
    card.kicker = "k"
    card.prompt = "a long meaning that stays on the card"
    card.guidance = ""
    try:
        exercise = MissingLettersExercise(window, card)
        exercise.frame.pack()
        window.update()
        parents = {item.master for item in exercise.inputs}
        assert len(exercise.inputs) == 16
        assert len(parents) >= 2
        assert exercise.frame.winfo_reqwidth() <= 480
    finally:
        _close_window(window)
