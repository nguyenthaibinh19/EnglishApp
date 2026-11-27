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
PRACTICE_ROOT = Path(r"D:\EnglishApp\.local\19d4b-preview")

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

    from adaptive_vocabulary import INDEPENDENT_RECALL, AdaptiveSessionBridge, AdaptiveVocabularySession
    from daily_study import DailyStudyPlan
    from study_session import build_study_session
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
        level_overrides={FIETS: "multiple_choice"},
    )
    app = AdaptiveVocabularyApp(
        window,
        session,
        provider=SilentVoice(),
        locked=False,
    )
    window.update()
    card = session.current_card()
    app.shell.exercise._select(card.correct_index)
    app._check()
    window.update()
    grab(window, SHOTS / "choice-correct.png")
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
    plan = DailyStudyPlan(
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
    study = build_study_session(plan)
    bridge = AdaptiveSessionBridge(study, session, locked=False)
    app = AdaptiveVocabularyApp(
        window,
        session,
        bridge=bridge,
        progress=done_progress,
        attempts=done_attempts,
        provider=SilentVoice(),
        locked=False,
    )
    window.update()
    app.shell.exercise.entry.insert(0, "de fiets")
    app._check()
    window.update()
    grab(window, SHOTS / "correct-feedback.png")
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


def _persist(practice_store, result) -> None:
    if getattr(result, "practice", None) is not None:
        practice_store.append(result.practice)


def _submit_current(session):
    from adaptive_vocabulary import reconstruct_mask

    card = session.current_card()
    if card.kind == "multiple_choice":
        return session.submit(choice_index=card.correct_index)
    if card.kind == "missing_letters":
        fills = [card.reveal_word[index] for index, char in enumerate(card.mask) if char == "_"]
        return session.submit(reconstruct_mask(card.mask, fills))
    return session.submit(card.reveal_word)


def _public_record(record) -> dict:
    return {
        "practice_event_id": record.practice_event_id,
        "exercise_instance_id": record.exercise_instance_id,
        "session_id": record.session_id,
        "vocab_id": record.vocab_id,
        "language_code": record.language_code,
        "actual_kind": record.actual_kind,
        "intended_kind": record.intended_kind,
        "support_level": record.support_level,
        "outcome": record.outcome,
        "error_class": record.error_class,
        "occurred_at": record.occurred_at,
        "policy_id": record.policy_id,
        "format_version": record.format_version,
    }


def run_practice_demo(root: Path) -> dict:
    """Two synthetic restarts. The folder is wiped and rewritten with fake Dutch words."""
    import shutil

    from adaptive_vocabulary import (
        GUIDED_TYPING,
        MISSING_LETTERS,
        AdaptiveVocabularySession,
        apply_independent_write,
        starting_level,
    )
    from attempt_history import AttemptHistory, LearningAttempt
    from practice_record import practice_start_level
    from practice_store import open_guest_store
    from progress import Progress

    root = Path(root)
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    guest = open_guest_store(str(root), "nl")
    session = AdaptiveVocabularySession(
        ENTRIES[:1],
        language_code="nl",
        pool=ENTRIES,
        rng=random.Random(4),
    )
    assert session.current_card().kind == "introduction"
    _persist(guest, session.continue_card())
    _persist(guest, _submit_current(session))
    session.continue_card()
    assisted_kind = session.current_card().kind
    assisted = _submit_current(session)
    assert assisted.write is None and assisted.success is True
    _persist(guest, assisted)
    session.abandon()
    assert session.finished is False
    guest.close()

    guest = open_guest_store(str(root), "nl")
    saved = guest.for_vocab(FIETS, "nl")
    expected = practice_start_level("introduction", saved, allow_promote=True)
    restarted = AdaptiveVocabularySession(
        ENTRIES[:1],
        language_code="nl",
        pool=ENTRIES,
        rng=random.Random(4),
        practice_history=saved,
    )
    start_kind = restarted.current_card().kind
    progress = Progress(str(root / "progress.json"))
    attempts = AttemptHistory(str(root / "attempts.jsonl"), language_code="nl")
    guard = 8
    while restarted.current_card() and restarted.current_card().kind != "independent_recall" and guard:
        card = restarted.current_card()
        if card.kind == "introduction":
            restarted.continue_card()
        else:
            step = _submit_current(restarted)
            _persist(guest, step)
            restarted.continue_card()
        guard -= 1
    before_independent = guest.count()
    indie = restarted.submit(restarted.current_card().reveal_word)
    assert indie.practice is None and indie.write is not None and indie.write.mastered is True
    apply_independent_write(progress, attempts, indie.write, timestamp="2026-11-27T16:00:00+00:00")
    after_independent = guest.count()
    guest.close()

    prior = LearningAttempt(
        timestamp="2026-11-27T12:00:00+00:00",
        language_code="nl",
        word="de fiets",
        user_answer="nope",
        expected_answer="de fiets",
        correct=False,
        verdict="wrong",
        hint_used=False,
        prompt="bicycle",
        vocab_id=FIETS,
    )
    fail_dir = root / "failures"
    guest = open_guest_store(str(fail_dir), "nl")
    failing = AdaptiveVocabularySession(
        ENTRIES[:1],
        language_code="nl",
        pool=ENTRIES,
        attempts=[prior],
        rng=random.Random(4),
    )
    without_practice = starting_level(None, prior)
    assert failing.current_card().kind == GUIDED_TYPING
    _persist(guest, failing.submit("nope"))
    failing.continue_card()
    _persist(guest, failing.submit("nope"))
    failing.abandon()
    assert failing.finished is False
    guest.close()
    guest = open_guest_store(str(fail_dir), "nl")
    failures = guest.for_vocab(FIETS, "nl")
    supported = AdaptiveVocabularySession(
        ENTRIES[:1],
        language_code="nl",
        pool=ENTRIES,
        attempts=[prior],
        practice_history=failures,
        rng=random.Random(4),
    )
    guest.close()
    evidence = {
        "success_records": [_public_record(row) for row in saved],
        "assisted_kind": assisted_kind,
        "restart_kind": start_kind,
        "expected_restart_kind": expected,
        "independent_added_practice_rows": after_independent - before_independent,
        "attempt_count": len(attempts.load_attempts()),
        "attempt_mastered": attempts.load_attempts()[0].correct,
        "progress_words": list((progress.data.get("words") or {}).keys()),
        "account_study_db": any(root.rglob("account_study.db")),
        "failure_records": [_public_record(row) for row in failures],
        "start_without_practice": without_practice,
        "start_after_repeated_failures": supported.current_card().kind,
        "more_support_kind": MISSING_LETTERS,
    }
    (root / "practice-evidence.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return evidence


def preview() -> None:
    import tkinter as tk

    from adaptive_vocabulary import AdaptiveSessionBridge, AdaptiveVocabularySession, select_planned_entries
    from adaptive_vocabulary_app import PREVIEW_HEIGHT, PREVIEW_WIDTH, AdaptiveVocabularyApp
    from daily_study import DailyStudyPlan
    from practice_store import open_guest_store
    from study_session import build_study_session

    store, progress, attempts = prepare()
    practice = open_guest_store(str(PRACTICE_ROOT / "interactive"), "nl")
    rng = random.Random(4)
    planned = select_planned_entries(store, progress, 1, rng)
    history = []
    for entry in planned:
        history.extend(practice.for_vocab(entry["id"], "nl"))
    session = AdaptiveVocabularySession(
        planned,
        language_code="nl",
        pool=[store.get(index) for index in range(store.count())],
        progress_words=progress.data.get("words") or {},
        attempts=attempts.load_attempts(),
        practice_history=history,
        rng=rng,
    )
    print("restart starting exercise:", session.current_card().kind if session.current_card() else "none")
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
        practice_store=practice,
        locked=False,
    )
    root.mainloop()
    practice.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--screenshots", action="store_true")
    parser.add_argument("--practice-demo", action="store_true")
    args = parser.parse_args()
    if args.screenshots:
        capture()
    elif args.practice_demo:
        evidence = run_practice_demo(PRACTICE_ROOT / "demo")
        print("restart starting exercise:", evidence["restart_kind"])
        print("after repeated failures:", evidence["start_after_repeated_failures"])
        print("practice rows:", len(evidence["success_records"]))
        print("evidence:", PRACTICE_ROOT / "demo" / "practice-evidence.json")
    else:
        preview()
