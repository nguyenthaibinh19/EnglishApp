"""Isolated adaptive vocabulary preview.

Uses synthetic Dutch words under D:\\EnglishApp\\.local\\19d4a-preview.
It does not open the installed app data and it does not turn on screen lock.

    python scripts/adaptive_vocabulary_preview.py
    python scripts/adaptive_vocabulary_preview.py --screenshots
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

ROOT = Path(r"D:\EnglishApp\.local\19d4a-preview")
SHOTS = Path(r"D:\EnglishApp\.local\19d4a-screenshots")

FIETS = "11111111-1111-4111-8111-111111111111"
HUIS = "22222222-2222-4222-8222-222222222222"
BOEK = "33333333-3333-4333-8333-333333333333"
WATER = "44444444-4444-4444-8444-444444444444"

ENTRIES = [
    {
        "id": FIETS,
        "word": "de fiets",
        "meaning": "bicycle",
        "example": "Ik ga met de fiets.",
    },
    {"id": HUIS, "word": "het huis", "meaning": "house"},
    {"id": BOEK, "word": "het boek", "meaning": "book"},
    {"id": WATER, "word": "het water", "meaning": "water"},
]


class SilentVoice:
    """Screenshot stand-in. Playback reports a missing voice and never synthesizes."""

    def play(self, *_args, **_kwargs):
        from listening import ListeningAudioError

        raise ListeningAudioError("No voice for this language on this PC. You can continue.")


def prepare():
    ROOT.mkdir(parents=True, exist_ok=True)
    vocab_path = ROOT / "vocab.json"
    vocab_path.write_text(json.dumps(ENTRIES, ensure_ascii=False, indent=2), encoding="utf-8")
    from attempt_history import AttemptHistory
    from progress import Progress
    from vocab_store import VocabStore

    store = VocabStore(str(vocab_path))
    progress = Progress(str(ROOT / "progress.json"))
    attempts = AttemptHistory(str(ROOT / "attempts.jsonl"), language_code="nl")
    return store, progress, attempts


def grab(window, path: Path) -> None:
    window.update_idletasks()
    window.update()
    window.lift()
    try:
        window.attributes("-topmost", True)
        window.focus_force()
    except Exception:
        pass
    window.update()
    from PIL import ImageGrab

    image = ImageGrab.grab(window=window.winfo_id())
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    print(
        f"{path.name} bitmap {image.size[0]}x{image.size[1]} "
        f"window {window.winfo_width()}x{window.winfo_height()}"
    )


def capture() -> None:
    import tkinter as tk

    from adaptive_vocabulary import INDEPENDENT_RECALL, AdaptiveVocabularySession
    from adaptive_vocabulary_app import PREVIEW_HEIGHT, PREVIEW_WIDTH, AdaptiveVocabularyApp

    _store, progress, attempts = prepare()
    root = tk.Tk()
    root.withdraw()
    kinds = [
        ("introduction", None),
        ("multiple-choice", "multiple_choice"),
        ("missing-letters", "missing_letters"),
        ("guided-typing", "guided_typing"),
        ("independent-recall", INDEPENDENT_RECALL),
    ]
    for name, level in kinds:
        window = tk.Toplevel(root)
        window.geometry(f"{PREVIEW_WIDTH}x{PREVIEW_HEIGHT}+80+40")
        overrides = {FIETS: level} if level else None
        session = AdaptiveVocabularySession(
            ENTRIES[:1],
            language_code="nl",
            pool=ENTRIES,
            rng=random.Random(4),
            level_overrides=overrides,
        )
        app = AdaptiveVocabularyApp(
            window,
            session,
            progress=progress,
            attempts=attempts,
            provider=SilentVoice(),
            locked=False,
        )
        window.update()
        if name == "introduction":
            def tick(left):
                if left == 30:
                    app.shell.exercise.normal_button.invoke()
                note = app.shell.exercise.voice_note.cget("text")
                if "You can continue" in note or "tiếp tục" in note.lower() or left <= 0:
                    window.quit()
                    return
                window.after(40, lambda: tick(left - 1))

            window.after(0, lambda: tick(30))
            window.mainloop()
        grab(window, SHOTS / f"{name}.png")
        window.destroy()

    window = tk.Toplevel(root)
    window.geometry(f"{PREVIEW_WIDTH}x{PREVIEW_HEIGHT}+80+40")
    session = AdaptiveVocabularySession(
        ENTRIES[:1],
        language_code="nl",
        pool=ENTRIES,
        rng=random.Random(4),
        level_overrides={FIETS: INDEPENDENT_RECALL},
    )
    fresh = type(progress)(str(ROOT / "feedback-progress.json"))
    fresh_attempts = type(attempts)(str(ROOT / "feedback-attempts.jsonl"), language_code="nl")
    app = AdaptiveVocabularyApp(
        window,
        session,
        progress=fresh,
        attempts=fresh_attempts,
        provider=SilentVoice(),
        locked=False,
    )
    window.update()
    app.shell.exercise.entry.insert(0, "nope")
    app._check()
    window.update()
    grab(window, SHOTS / "independent-incorrect.png")
    window.destroy()

    window = tk.Toplevel(root)
    window.geometry(f"{PREVIEW_WIDTH}x{PREVIEW_HEIGHT}+80+40")
    session = AdaptiveVocabularySession(
        ENTRIES[:1],
        language_code="nl",
        pool=ENTRIES,
        rng=random.Random(4),
        level_overrides={FIETS: INDEPENDENT_RECALL},
    )
    done_progress = type(progress)(str(ROOT / "completion-progress.json"))
    done_attempts = type(attempts)(str(ROOT / "completion-attempts.jsonl"), language_code="nl")
    app = AdaptiveVocabularyApp(
        window,
        session,
        progress=done_progress,
        attempts=done_attempts,
        provider=SilentVoice(),
        locked=False,
    )
    window.update()
    app.shell.exercise.entry.insert(0, "de fiets")
    app._check()
    window.update()
    app.shell.continue_button.invoke()
    window.update()
    grab(window, SHOTS / "completion.png")
    print(
        f"requested {PREVIEW_WIDTH}x{PREVIEW_HEIGHT} "
        f"actual {window.winfo_width()}x{window.winfo_height()} "
        f"minimum 480x560"
    )
    window.destroy()
    root.destroy()


def preview() -> None:
    import tkinter as tk

    from adaptive_vocabulary import AdaptiveSessionBridge, AdaptiveVocabularySession, select_planned_entries
    from adaptive_vocabulary_app import PREVIEW_HEIGHT, PREVIEW_WIDTH, AdaptiveVocabularyApp
    from daily_study import DailyStudyPlan
    from study_session import build_study_session

    store, progress, attempts = prepare()
    rng = random.Random(4)
    planned = select_planned_entries(store, progress, 1, rng)
    session = AdaptiveVocabularySession(
        planned,
        language_code="nl",
        pool=[store.get(index) for index in range(store.count())],
        progress_words=progress.data.get("words") or {},
        attempts=attempts.load_attempts(),
        rng=rng,
    )
    plan = DailyStudyPlan(
        language_code="nl",
        vocab_total=store.count(),
        due_review_count=0,
        new_word_count=store.count(),
        future_review_count=0,
        attention_word_count=0,
        planned_vocab_count=len(planned),
        reading_enabled=True,
        listening_enabled=True,
    )
    study = build_study_session(plan)
    bridge = AdaptiveSessionBridge(study, session, locked=False)
    root = tk.Tk()
    root.geometry(f"{PREVIEW_WIDTH}x{PREVIEW_HEIGHT}+80+40")

    def finished():
        print("vocabulary complete:", study.vocabulary_complete())
        print("reading still pending:", study.status("reading"))

    AdaptiveVocabularyApp(
        root,
        session,
        bridge=bridge,
        progress=progress,
        attempts=attempts,
        on_completed=finished,
        provider=None,
        locked=False,
    )
    root.mainloop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--screenshots", action="store_true")
    args = parser.parse_args()
    if args.screenshots:
        capture()
    else:
        preview()
