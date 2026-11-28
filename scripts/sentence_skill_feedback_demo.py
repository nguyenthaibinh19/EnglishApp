"""Phase 19.5B structured feedback + persistent sentence skill demo.

Isolated synthetic root only:

    set LG_DATA_DIR=D:\\EnglishApp\\.local\\19d5b-preview
    set LG_ADAPTIVE_STUDY=1
    set LOCK_SCREEN=0
    python scripts/sentence_skill_feedback_demo.py

No production AppData. No live AI. Vocabulary attempt/SRS/PracticeRecord/sync untouched.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(r"D:\EnglishApp\.local\19d5b-preview")
SHOTS = ROOT / "screenshots"
EVIDENCE = ROOT / "sentence-skill-evidence.json"

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
    if ROOT.resolve() != Path(r"D:\EnglishApp\.local\19d5b-preview").resolve():
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


def _open_app(*, grade_mode: str = "accept_valid", skill_store=None, skill_history=()):
    import tkinter as tk

    from sentence_practice import SentencePracticeSession
    from sentence_practice_app import SentencePracticeApp, build_demo_grade_service

    root = tk.Tk()
    root.withdraw()
    window = tk.Toplevel(root)
    session = SentencePracticeSession.from_language(
        "nl",
        "A1",
        skill_store=skill_store,
        skill_history=skill_history,
    )
    app = SentencePracticeApp(
        window,
        session,
        grade_service=build_demo_grade_service(grade_mode),
        locked=False,
    )
    _pump(window, 120)
    return root, window, app, session


def _assert_isolation() -> dict:
    lang = ROOT / "languages" / "nl"
    attempts = (lang / "attempts.jsonl").read_text(encoding="utf-8")
    progress = json.loads((lang / "progress.json").read_text(encoding="utf-8"))
    return {
        "attempts_empty": attempts == "",
        "progress_words_empty": progress.get("words") == {},
        "practice_db_absent": not (lang / "practice_records.db").exists(),
        "sentence_skill_db_present": (lang / "sentence_skill_records.db").exists(),
        "outbox_absent": not list(ROOT.glob("**/outbox*")),
    }


def _solve_word_bank(app) -> None:
    body = app.shell.exercise
    for token in ("Zij", "leest", "een", "boek", "."):
        body._pick(token)
        _pump(app.window, 20)


def run() -> dict:
    _env_prepare()
    _wipe_and_seed()
    _reload_config()

    from sentence_skill_store import (
        open_guest_sentence_skill_store,
        load_sentence_skill_history,
    )

    evidence = {
        "tag": "APP_19D5B_STRUCTURED_FEEDBACK_SENTENCE_SKILL_DEMO",
        "root": str(ROOT),
        "screenshots": [],
        "flow": [],
        "isolation": {},
        "restart": {},
        "skill_counts": {},
    }

    store = open_guest_sentence_skill_store(str(ROOT), "nl")
    root, window, app, session = _open_app(skill_store=store)
    try:
        # Climb to fill-blank quickly.
        _solve_word_bank(app)
        app._check()
        _pump(window, 80)
        if app._phase == "feedback":
            app._continue()
            _pump(window, 60)

        grab(window, SHOTS / "01-fill-blank.png")
        evidence["screenshots"].append("01-fill-blank.png")

        # Known conjugation error → structured feedback + segments.
        body = app.shell.exercise
        body.entry.delete(0, "end")
        body.entry.insert(0, "lezen")
        app._check()
        _pump(window, 120)
        grade = app._last_feedback.grade if app._last_feedback else None
        evidence["flow"].append(
            {
                "step": "conjugation_structured",
                "status": getattr(grade, "status", None),
                "error": getattr(grade, "error_hint", None),
                "original_segment": getattr(grade, "original_segment", None),
                "corrected_segment": getattr(grade, "corrected_segment", None),
                "structured": getattr(getattr(grade, "structured", None), "as_dict", lambda: None)(),
            }
        )
        grab(window, SHOTS / "02-conjugation-structured-feedback.png")
        evidence["screenshots"].append("02-conjugation-structured-feedback.png")
        app._toggle_grammar()
        _pump(window, 150)
        grab(window, SHOTS / "03-grammar-segments-and-rule.png")
        evidence["screenshots"].append("03-grammar-segments-and-rule.png")
        app._toggle_grammar()
        # Count before leave — leave/destroy closes the owned store.
        evidence["skill_counts"]["after_first_session"] = store.count()
        app._leave()
        evidence["flow"].append("safe_early_exit_after_conjugation")
    finally:
        try:
            window.destroy()
        except Exception:
            pass
        try:
            root.destroy()
        except Exception:
            pass

    # Restart — cross-session support selection from persisted evidence.
    store2 = open_guest_sentence_skill_store(str(ROOT), "nl")
    history2 = load_sentence_skill_history(store2, "nl")
    root, window, app, session = _open_app(skill_store=store2, skill_history=history2)
    try:
        card = session.current_card()
        evidence["restart"] = {
            "history_rows": len(history2),
            "selected_kind": card.exercise.kind if card else None,
            "selected_family": card.exercise.family_id if card else None,
            "selection_reason": getattr(session.selection_decision, "reason", None),
        }
        grab(window, SHOTS / "04-restart-scaffolding-selected.png")
        evidence["screenshots"].append("04-restart-scaffolding-selected.png")
        evidence["flow"].append("cross_session_support_selection")

        # Improved performance on scaffolding.
        if card and card.exercise.kind == "word_bank":
            _solve_word_bank(app)
            app._check()
            _pump(window, 100)
            grab(window, SHOTS / "05-improved-word-bank.png")
            evidence["screenshots"].append("05-improved-word-bank.png")
            if app._phase == "feedback":
                app._continue()
                _pump(window, 60)

        # Climb to independent for provisional AI acceptance.
        guard = 0
        while (
            session.current_card()
            and session.current_card().exercise.kind != "independent_writing"
            and guard < 10
        ):
            guard += 1
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
            _pump(window, 80)
            if app._phase == "feedback":
                app._continue()
                _pump(window, 50)

        body = app.shell.exercise
        body.entry.delete(0, "end")
        body.entry.insert(0, "Zij leest een boek vandaag")
        app._check()
        for _ in range(40):
            if not app._ai_pending and app._phase == "feedback":
                break
            _pump(window, 40)
        grade = app._last_feedback.grade if app._last_feedback else None
        evidence["flow"].append(
            {
                "step": "provisional_ai_accept",
                "status": getattr(grade, "status", None),
                "provisional": getattr(getattr(grade, "structured", None), "provisional", None),
            }
        )
        grab(window, SHOTS / "06-provisional-ai-accept.png")
        evidence["screenshots"].append("06-provisional-ai-accept.png")
        evidence["skill_counts"]["after_restart_session"] = store2.count()
        app._leave()
    finally:
        try:
            window.destroy()
        except Exception:
            pass
        try:
            root.destroy()
        except Exception:
            pass

    # Malformed provider path (no UI requirement beyond graceful degrade).
    from sentence_content import load_pack
    from sentence_grading import grade_with_ai_service
    from sentence_practice_app import build_demo_grade_service

    pack = load_pack("nl", "A1")
    independent = next(e for e in pack.exercises if e.kind == "independent_writing")
    malformed = grade_with_ai_service(
        build_demo_grade_service("malformed_structured"),
        independent,
        "Zij leest een boek vandaag",
    )
    invalid_rule = grade_with_ai_service(
        build_demo_grade_service("invalid_rule_ref"),
        independent,
        "Zij leest een boek vandaag",
    )
    evidence["flow"].append(
        {
            "step": "malformed_provider",
            "status": malformed.status,
            "structured_provisional": getattr(
                getattr(malformed, "structured", None), "provisional", None
            ),
        }
    )
    evidence["flow"].append(
        {
            "step": "invalid_grammar_rule_ref",
            "status": invalid_rule.status,
            "trusted_rule_id": getattr(
                getattr(invalid_rule, "structured", None), "grammar_rule_id", ""
            ),
        }
    )

    # Account vs guest isolation smoke (same root, separate files).
    from sentence_skill_record import (
        EVIDENCE_RELIABLE_LOCAL,
        OUTCOME_INCORRECT,
        build_sentence_skill_record,
    )
    from sentence_skill_store import open_account_sentence_skill_store

    account = open_account_sentence_skill_store(str(ROOT), 7)
    account.append(
        build_sentence_skill_record(
            session_id="acct",
            exercise_instance_id="ei-a",
            submission_id="sub-a",
            exercise_id="nl-a1-fb-zij-leest",
            family_id="nl-a1-family-lezen-boek",
            content_version="1",
            study_language="nl",
            cefr_level="A1",
            exercise_kind="fill_blank",
            support_level=1,
            outcome=OUTCOME_INCORRECT,
            grading_source="local",
            error_classification="conjugation",
            evidence_status=EVIDENCE_RELIABLE_LOCAL,
        )
    )
    guest = open_guest_sentence_skill_store(str(ROOT), "nl")
    evidence["isolation_accounts"] = {
        "guest_count": guest.count(),
        "account_count": account.count(),
        "guest_db": str(Path(guest.db_path).relative_to(ROOT)),
        "account_db": str(Path(account.db_path).relative_to(ROOT)),
    }
    guest.close()
    account.close()

    evidence["isolation"] = _assert_isolation()
    EVIDENCE.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    if not all(evidence["isolation"].values()):
        raise SystemExit("isolation check failed")
    if evidence["restart"].get("selected_kind") != "word_bank":
        raise SystemExit("cross-session scaffolding was not selected")
    return evidence


if __name__ == "__main__":
    run()
