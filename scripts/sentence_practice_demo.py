"""Phase 19.5A R1 Dutch A1 sentence practice demo + screenshots.

Isolated synthetic root only:

    set LG_DATA_DIR=D:\\EnglishApp\\.local\\19d5a-preview
    set LG_ADAPTIVE_STUDY=1
    set LOCK_SCREEN=0
    python scripts/sentence_practice_demo.py

No production AppData. No live AI. Vocabulary attempt/SRS/sync untouched.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(r"D:\EnglishApp\.local\19d5a-preview")
SHOTS = ROOT / "screenshots"
EVIDENCE = ROOT / "sentence-evidence.json"

APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def _env_prepare() -> None:
    os.environ["LG_DATA_DIR"] = str(ROOT)
    os.environ["LG_ADAPTIVE_STUDY"] = "1"
    os.environ["LOCK_SCREEN"] = "0"
    os.environ.pop("ACCOUNT_SERVER_URL", None)
    os.environ.pop("ACCOUNT_TOKEN", None)
    os.environ.pop("OPENAI_API_KEY", None)


def _wipe_and_seed() -> None:
    if ROOT.resolve() != Path(r"D:\EnglishApp\.local\19d5a-preview").resolve():
        raise SystemExit(f"refusing to wipe unexpected root: {ROOT}")
    if ROOT.exists():
        shutil.rmtree(ROOT)
    ROOT.mkdir(parents=True)
    SHOTS.mkdir(parents=True)
    settings = {
        "native": "en",
        "language": "nl",
        "study_languages": ["nl"],
        "activities": {"reading": False, "listening": False},
        "ui_language": "en",
    }
    (ROOT / "settings.json").write_text(
        json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lang = ROOT / "languages" / "nl"
    lang.mkdir(parents=True)
    (lang / "vocab.json").write_text("[]", encoding="utf-8")
    (lang / "progress.json").write_text(
        json.dumps({"words": {}}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (lang / "attempts.jsonl").write_text("", encoding="utf-8")


def _reload_config() -> None:
    import config

    config.SETTINGS_FILE = str(ROOT / "settings.json")
    config.reload()
    config.LOCK_SCREEN = False


def grab(window, path: Path) -> None:
    window.update_idletasks()
    window.update()
    try:
        window.lift()
        window.attributes("-topmost", True)
        window.focus_force()
    except Exception:
        pass
    window.update()
    time.sleep(0.2)
    from PIL import ImageGrab

    image = ImageGrab.grab(window=window.winfo_id())
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    print(f"shot {path.name} {image.size[0]}x{image.size[1]}")


def _pump(window, ms: int = 80) -> None:
    window.update_idletasks()
    window.update()
    time.sleep(ms / 1000.0)
    window.update()


def _open_app(grade_mode: str = "accept_valid"):
    import tkinter as tk

    from sentence_practice import SentencePracticeSession
    from sentence_practice_app import SentencePracticeApp, build_demo_grade_service

    root = tk.Tk()
    root.withdraw()
    window = tk.Toplevel(root)
    session = SentencePracticeSession.from_language("nl", "A1")
    app = SentencePracticeApp(
        window,
        session,
        grade_service=build_demo_grade_service(grade_mode),
        locked=False,
    )
    _pump(window, 120)
    return root, window, app, session


def _assert_no_vocab_writes() -> dict:
    lang = ROOT / "languages" / "nl"
    attempts = (lang / "attempts.jsonl").read_text(encoding="utf-8")
    progress = json.loads((lang / "progress.json").read_text(encoding="utf-8"))
    practice = (ROOT / "practice_records.db").exists()
    outbox = list(ROOT.glob("**/outbox*"))
    return {
        "attempts_empty": attempts == "",
        "progress_words_empty": progress.get("words") == {},
        "practice_db_absent": not practice,
        "outbox_absent": not outbox,
    }


def _solve_word_bank(app) -> None:
    body = app.shell.exercise
    order = ["Zij", "leest", "een", "boek", "."]
    for token in order:
        body._pick(token)
        _pump(app.window, 20)


def run() -> dict:
    _env_prepare()
    _wipe_and_seed()
    _reload_config()

    evidence = {
        "tag": "APP_19D5A_SENTENCE_PRACTICE_R1_DEMO",
        "root": str(ROOT),
        "screenshots": [],
        "flow": [],
        "isolation": {},
    }

    root, window, app, session = _open_app("accept_valid")
    try:
        grab(window, SHOTS / "01-word-bank.png")
        evidence["screenshots"].append("01-word-bank.png")

        # Incorrect word order
        body = app.shell.exercise
        for token in ("boek", "Zij", "leest", "een", "."):
            body._pick(token)
            _pump(window, 30)
        app._check()
        _pump(window, 120)
        grab(window, SHOTS / "02-incorrect-word-order.png")
        evidence["screenshots"].append("02-incorrect-word-order.png")
        evidence["flow"].append("incorrect_word_order")
        app._continue()
        _pump(window, 80)

        _solve_word_bank(app)
        grab(window, SHOTS / "03-word-bank-arranged.png")
        evidence["screenshots"].append("03-word-bank-arranged.png")
        app._check()
        _pump(window, 100)
        app._toggle_grammar()
        _pump(window, 150)
        grab(window, SHOTS / "04-grammar-companion-expanded.png")
        evidence["screenshots"].append("04-grammar-companion-expanded.png")
        evidence["flow"].append("grammar_companion_expanded")
        app._toggle_grammar()
        app._continue()
        _pump(window, 80)

        # Fill blank conjugation miss
        grab(window, SHOTS / "05-fill-blank.png")
        evidence["screenshots"].append("05-fill-blank.png")
        body = app.shell.exercise
        body.entry.delete(0, "end")
        body.entry.insert(0, "lezen")
        app._check()
        _pump(window, 120)
        grab(window, SHOTS / "06-conjugation-feedback.png")
        evidence["screenshots"].append("06-conjugation-feedback.png")
        evidence["flow"].append("conjugation_correction")
        app._toggle_grammar()
        _pump(window, 120)
        grab(window, SHOTS / "06b-conjugation-grammar.png")
        evidence["screenshots"].append("06b-conjugation-grammar.png")
        app._toggle_grammar()
        app._continue()
        _pump(window, 80)

        # Correct fill blank (may have stepped down — climb back)
        guard = 0
        while session.current_card() and session.current_card().exercise.kind != "guided_writing" and guard < 8:
            guard += 1
            body = app.shell.exercise
            kind = session.current_card().exercise.kind
            if kind == "word_bank":
                _solve_word_bank(app)
            elif kind == "fill_blank":
                body.entry.delete(0, "end")
                body.entry.insert(0, "leest")
            app._check()
            _pump(window, 80)
            if app._phase == "feedback":
                app._continue()
                _pump(window, 60)

        grab(window, SHOTS / "07-guided-writing.png")
        evidence["screenshots"].append("07-guided-writing.png")
        body = app.shell.exercise
        body.entry.delete(0, "end")
        body.entry.insert(0, "Ze leest een boek.")
        app._check()
        _pump(window, 80)
        app._continue()
        _pump(window, 80)

        grab(window, SHOTS / "08-independent-writing.png")
        evidence["screenshots"].append("08-independent-writing.png")
        body = app.shell.exercise
        body.entry.delete(0, "end")
        body.entry.insert(0, "Zij leest een boek vandaag")
        app._check()
        for _ in range(40):
            if not app._ai_pending and app._phase == "feedback":
                break
            _pump(window, 40)
        grab(window, SHOTS / "09-ai-provisional-outside-reviewed.png")
        evidence["screenshots"].append("09-ai-provisional-outside-reviewed.png")
        evidence["flow"].append("ai_provisional_accept")
        if app._phase == "feedback":
            app._continue()
            _pump(window, 100)

        if app._phase == "complete" or session.finished:
            if app._phase != "complete":
                app._show_complete()
                _pump(window, 80)
            grab(window, SHOTS / "10-complete.png")
            evidence["screenshots"].append("10-complete.png")
            evidence["flow"].append("four_levels_complete")
    finally:
        try:
            window.destroy()
        except Exception:
            pass
        try:
            root.destroy()
        except Exception:
            pass

    # AI unavailable
    root, window, app, session = _open_app("unavailable")
    try:
        while session.current_card() and session.current_card().exercise.kind != "independent_writing":
            body = app.shell.exercise
            kind = session.current_card().exercise.kind
            if kind == "word_bank":
                _solve_word_bank(app)
            elif kind == "fill_blank":
                body.entry.delete(0, "end")
                body.entry.insert(0, "leest")
            else:
                body.entry.delete(0, "end")
                body.entry.insert(0, "Zij leest een boek.")
            app._check()
            _pump(window, 60)
            if app._phase == "feedback":
                app._continue()
                _pump(window, 40)
        body = app.shell.exercise
        body.entry.delete(0, "end")
        body.entry.insert(0, "something novel")
        app._check()
        for _ in range(40):
            if not app._ai_pending and app._phase == "feedback":
                break
            _pump(window, 40)
        grab(window, SHOTS / "11-ai-unavailable.png")
        evidence["screenshots"].append("11-ai-unavailable.png")
        evidence["flow"].append("ai_unavailable_provisional")
        app._leave()
        evidence["flow"].append("safe_early_exit")
    finally:
        try:
            window.destroy()
        except Exception:
            pass
        try:
            root.destroy()
        except Exception:
            pass

    evidence["isolation"] = _assert_no_vocab_writes()
    EVIDENCE.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    if not all(evidence["isolation"].values()):
        raise SystemExit("isolation check failed")
    return evidence


if __name__ == "__main__":
    run()
