"""Adaptive preview window. This file exercises the real CustomTkinter card."""

from __future__ import annotations

import random
import tkinter as tk

from adaptive_vocabulary import (
    INDEPENDENT_RECALL,
    AdaptiveSessionBridge,
    AdaptiveVocabularySession,
)
from adaptive_vocabulary_app import AdaptiveVocabularyApp
from attempt_history import AttemptHistory
from daily_study import DailyStudyPlan
from progress import Progress
from study_session import build_study_session

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
    def supports(self, _language):
        return False

    def play(self, *_args, **_kwargs):
        raise AssertionError("missing voice must not synthesize")


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
        listening_enabled=False,
    )


def test_preview_leave_and_missing_voice_do_not_record(tmp_path):
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
    root = tk.Tk()
    root.withdraw()
    window = tk.Toplevel(root)
    try:
        app = AdaptiveVocabularyApp(
            window,
            controller,
            bridge=bridge,
            progress=progress,
            attempts=attempts,
            on_completed=lambda: left.append("done"),
            on_leave=lambda: left.append("leave"),
            provider=_SilentVoice(),
            locked=False,
        )
        window.update()
        assert "de fiets" in app.shell.exercise.frame.winfo_children()[1].cget("text")
        app.shell.exercise.normal_button.invoke()
        window.update()
        assert "You can continue" in app.shell.exercise.voice_note.cget("text")
        assert app.shell.check_button.cget("state") == "normal"
        app._leave()
        window.update()
    finally:
        root.destroy()
    assert left == ["leave"]
    assert study.vocabulary_complete() is False
    assert attempts.load_attempts() == []
    assert progress.data["words"] == {}


def test_wrong_independent_answer_records_once_on_the_card(tmp_path):
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
    root = tk.Tk()
    root.withdraw()
    window = tk.Toplevel(root)
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
        assert "Independent recall" in app.shell.exercise.kicker.cget("text")
        app.shell.exercise.entry.insert(0, "nope")
        app._check()
        window.update()
        assert "The word is" in app.shell.feedback.cget("text")
        app._check()
        assert len(attempts.load_attempts()) == 1
        assert attempts.load_attempts()[0].correct is False
        assert app._applied_writes == 1
        app._continue()
        assert finished == []
    finally:
        root.destroy()
