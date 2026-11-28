"""Phase 19.4C integrated Adaptive Study demo through FreeHome → StudyMaster.

Isolated synthetic root only:

    set LG_DATA_DIR=D:\\EnglishApp\\.local\\19d4c-preview
    set LG_ADAPTIVE_STUDY=1
    set LOCK_SCREEN=0
    python scripts/adaptive_study_integration_demo.py

Does not touch production AppData. Primary path is Home Adaptive Study (dev).
"""

from __future__ import annotations

import json
import os
import random
import shutil
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(r"D:\EnglishApp\.local\19d4c-preview")
SHOTS = ROOT / "screenshots"
EVIDENCE = ROOT / "integration-evidence.json"

APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

FIETS = "11111111-1111-4111-8111-111111111111"
HUIS = "22222222-2222-4222-8222-222222222222"
BOEK = "33333333-3333-4333-8333-333333333333"

ENTRIES = [
    {
        "id": FIETS,
        "word": "de fiets",
        "meaning": "bicycle",
        "example": "Ik ga met de fiets.",
    },
    {"id": HUIS, "word": "het huis", "meaning": "house"},
    {"id": BOEK, "word": "het boek", "meaning": "book"},
]


class SilentVoice:
    def play(self, *_args, **_kwargs):
        from listening import ListeningAudioError

        raise ListeningAudioError("No voice for this language on this PC. You can continue.")


def _env_prepare() -> None:
    os.environ["LG_DATA_DIR"] = str(ROOT)
    os.environ["LG_ADAPTIVE_STUDY"] = "1"
    os.environ["LOCK_SCREEN"] = "0"
    os.environ["QUIZ_TARGET_CORRECT"] = "2"
    os.environ.pop("ACCOUNT_SERVER_URL", None)
    os.environ.pop("ACCOUNT_TOKEN", None)


def _wipe_and_seed_guest() -> None:
    # Only the isolated demo root. Never touch production AppData or sibling folders.
    if ROOT.resolve() != Path(r"D:\EnglishApp\.local\19d4c-preview").resolve():
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
    (lang / "vocab.json").write_text(
        json.dumps(ENTRIES, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (lang / "progress.json").write_text(
        json.dumps({"words": {}}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (lang / "attempts.jsonl").write_text("", encoding="utf-8")


def _reload_config() -> None:
    import config

    config.SETTINGS_FILE = str(ROOT / "settings.json")
    config.reload()
    config.QUIZ_TARGET_CORRECT = 2
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
    time.sleep(0.15)
    from PIL import ImageGrab

    image = ImageGrab.grab(window=window.winfo_id())
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    print(
        f"{path.name} bitmap {image.size[0]}x{image.size[1]} "
        f"window {window.winfo_width()}x{window.winfo_height()}"
    )


def _attach_adaptive_handle(study_master) -> None:
    import adaptive_vocabulary_app as mod

    original = mod.AdaptiveVocabularyApp.__init__

    def wrapped(self, *args, **kwargs):
        original(self, *args, **kwargs)
        study_master._adaptive_app = self
        if getattr(self, "provider", None) is None:
            self.provider = SilentVoice()

    mod.AdaptiveVocabularyApp.__init__ = wrapped
    study_master._adaptive_patch = original


def _restore_adaptive_patch(study_master) -> None:
    import adaptive_vocabulary_app as mod

    original = getattr(study_master, "_adaptive_patch", None)
    if original is not None:
        mod.AdaptiveVocabularyApp.__init__ = original


def _submit_ui(app) -> None:
    from adaptive_vocabulary import reconstruct_mask

    card = app.session.current_card()
    if card is None:
        return
    if card.kind == "introduction":
        # Introduction uses the Check button relabeled Continue.
        app._check()
        return
    if card.kind == "multiple_choice":
        app._select_choice(card.correct_index)
        app._check()
        return
    if card.kind == "missing_letters":
        fills = [card.reveal_word[i] for i, ch in enumerate(card.mask) if ch == "_"]
        text = reconstruct_mask(card.mask, fills)
        entry = getattr(app.shell.exercise, "entry", None)
        if entry is not None:
            entry.delete(0, "end")
            entry.insert(0, text)
        else:
            for box, char in zip(getattr(app.shell.exercise, "inputs", ()), fills):
                box.delete(0, "end")
                box.insert(0, char)
        app._check()
        return
    app.shell.exercise.entry.delete(0, "end")
    app.shell.exercise.entry.insert(0, card.reveal_word)
    app._check()


def _advance_feedback(app) -> None:
    if app._phase == "feedback":
        app.shell.continue_button.invoke()


def _drive(app, root, *, leave_early: bool = False, max_steps: int = 48) -> dict:
    stats = {
        "recognition_or_assisted": 0,
        "independent": 0,
        "practice_saved": 0,
        "writes": 0,
        "left_early": False,
        "completed": False,
        "kinds_seen": [],
    }
    for _ in range(max_steps):
        root.update()
        if app._phase in ("complete", "closed", "empty"):
            break
        card = app.session.current_card()
        if card is None:
            break
        kind = card.kind
        stats["kinds_seen"].append(kind)
        if (
            leave_early
            and kind == "independent_recall"
            and stats["recognition_or_assisted"] > 0
        ):
            app._leave()
            stats["left_early"] = True
            root.update()
            break
        before_writes = app._applied_writes
        before_practice = app.practice_saved
        _submit_ui(app)
        root.update()
        if app._phase == "feedback":
            if app._applied_writes > before_writes:
                stats["independent"] += 1
            elif app.practice_saved > before_practice:
                stats["recognition_or_assisted"] += 1
            _advance_feedback(app)
            root.update()
        if app._phase == "complete":
            stats["completed"] = True
            break
    stats["practice_saved"] = app.practice_saved
    stats["writes"] = app._applied_writes
    if app._phase == "complete":
        app._close_complete()
        root.update()
        stats["completed"] = True
    return stats


def _count_outbox(data_root: Path, user_id: int) -> int:
    db = data_root / "accounts" / str(user_id) / "account_study.db"
    if not db.exists():
        return 0
    conn = sqlite3.connect(str(db))
    try:
        row = conn.execute("SELECT COUNT(*) FROM outbox").fetchone()
        return int(row[0] if row else 0)
    finally:
        conn.close()


def _count_practice(data_root: Path, *, guest_lang: str = "", user_id: int = 0) -> int:
    if user_id:
        path = data_root / "accounts" / str(user_id) / "practice_records.db"
    else:
        path = data_root / "languages" / guest_lang / "practice_records.db"
    if not path.exists():
        return 0
    conn = sqlite3.connect(str(path))
    try:
        row = conn.execute("SELECT COUNT(*) FROM practice_records").fetchone()
        return int(row[0] if row else 0)
    finally:
        conn.close()


def _attempts_count(path: Path) -> int:
    if not path.exists():
        return 0
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return 0
    return sum(1 for line in text.splitlines() if line.strip())


def _seed_account(data_root: Path, user_id: int) -> None:
    from account_local_store import AccountLocalStore

    store = AccountLocalStore(user_id, data_root=str(data_root))
    for entry in ENTRIES:
        store.upsert_vocabulary(
            language_code="nl",
            vocab_id=entry["id"],
            payload=dict(entry),
        )
    store.close()


def _account_isolation_demo(data_root: Path) -> dict:
    import config
    from adaptive_study import (
        attach_bridge,
        build_integrated_session,
        capture_identity,
        open_practice_store,
    )
    from adaptive_vocabulary import apply_independent_write
    from attempt_history import utc_now_iso
    from daily_study import plan_for_language
    from practice_store import open_account_store
    from study_data import open_study_data
    from study_session import build_study_session

    _seed_account(data_root, 101)
    _seed_account(data_root, 202)

    results = {}
    for user_id in (101, 202):
        config.save_account(f"synth_{user_id}", f"token-{user_id}", user_id=user_id)
        bundle = open_study_data("nl", data_root=str(data_root))
        identity = capture_identity("nl", data_root=str(data_root))
        store = open_practice_store(identity)
        plan = plan_for_language("nl")
        session = build_study_session(plan)
        built = build_integrated_session(
            bundle,
            planned_count=1,
            practice_store=store,
            rng=random.Random(user_id),
        )
        assert built.ok and built.session is not None
        controller = built.session
        bridge = attach_bridge(session, controller, locked=False)
        assisted_practice = 0
        outbox_before = _count_outbox(data_root, user_id)
        guard = 12
        while (
            controller.current_card()
            and controller.current_card().kind != "independent_recall"
            and guard
        ):
            card = controller.current_card()
            if card.kind == "introduction":
                controller.continue_card()
            elif card.kind == "multiple_choice":
                result = controller.submit(choice_index=card.correct_index)
                if result.practice is not None:
                    store.append(result.practice)
                    assisted_practice += 1
                controller.continue_card()
            else:
                result = controller.submit(card.reveal_word)
                if result.practice is not None:
                    store.append(result.practice)
                    assisted_practice += 1
                controller.continue_card()
            guard -= 1
        outbox_after_assisted = _count_outbox(data_root, user_id)
        indie = controller.submit(controller.current_card().reveal_word)
        assert indie.write is not None
        apply_independent_write(
            bundle.progress, bundle.attempts, indie.write, timestamp=utc_now_iso()
        )
        outbox_after_indie = _count_outbox(data_root, user_id)
        practice_count = store.count()
        store.close()
        bridge.note_finished()
        results[str(user_id)] = {
            "assisted_practice_rows": assisted_practice,
            "practice_total": practice_count,
            "outbox_before": outbox_before,
            "outbox_after_assisted": outbox_after_assisted,
            "outbox_after_independent": outbox_after_indie,
            "assisted_added_outbox": outbox_after_assisted - outbox_before,
            "independent_added_outbox": outbox_after_indie - outbox_after_assisted,
            "identity_user": identity.user_id,
            "practice_db": str(
                data_root / "accounts" / str(user_id) / "practice_records.db"
            ),
        }
    config.clear_account()
    a = open_account_store(str(data_root), 101)
    b = open_account_store(str(data_root), 202)
    results["isolation"] = {
        "account_101_rows": a.count(),
        "account_202_rows": b.count(),
        "guest_rows": _count_practice(data_root, guest_lang="nl"),
        "separate_files": True,
    }
    a.close()
    b.close()
    return results


def run_home_workflow_demo() -> dict:
    import tkinter as tk

    import config
    import dictionary
    from home_app import FreeHome
    from practice_store import open_guest_store

    _env_prepare()
    _wipe_and_seed_guest()
    _reload_config()

    # Demo must not download dictionaries or poll a live sync host.
    dictionary.is_ready = lambda *_a, **_k: True  # type: ignore[assignment]

    evidence = {
        "data_root": str(ROOT),
        "lock_screen": bool(config.LOCK_SCREEN),
        "quiz_target": int(config.QUIZ_TARGET_CORRECT),
        "frozen": bool(config.is_frozen()),
        "route": {},
        "leave_early": {},
        "complete_round": {},
        "restart": {},
        "accounts": {},
        "screenshots": [],
    }

    print("opening FreeHome", flush=True)
    root = tk.Tk()
    home = FreeHome(root)
    root.update()
    assert home.adaptive_button is not None, "Adaptive Study (dev) missing on FreeHome"
    grab(root, SHOTS / "01-home.png")
    evidence["screenshots"].append("01-home.png")

    print("launching Adaptive Study via Home", flush=True)
    home._start_adaptive_study()
    root.update()

    study = getattr(root, "_study_master", None)
    assert study is not None, "StudyMaster was not launched from FreeHome"
    # Cancel deferred dictionary work and auto-open; open adaptive explicitly.
    try:
        for after_id in list(root.tk.call("after", "info")):
            try:
                root.after_cancel(after_id)
            except Exception:
                pass
    except Exception:
        pass
    study._ensure_missing_dictionaries = lambda: None  # type: ignore[method-assign]
    evidence["route"] = {
        "prefer_adaptive": bool(study.prefer_adaptive),
        "legacy_vocab_method": "open_vocab_section",
        "adaptive_method": "open_adaptive_vocab_section",
        "home_entry": "FreeHome._start_adaptive_study",
    }
    grab(root, SHOTS / "02-studymaster.png")
    evidence["screenshots"].append("02-studymaster.png")

    _attach_adaptive_handle(study)
    try:
        if study.vocab_window is None or not study.vocab_window.winfo_exists():
            study.open_adaptive_vocab_section("nl")
            root.update()
        app = getattr(study, "_adaptive_app", None)
        assert app is not None, "AdaptiveVocabularyApp not opened via StudyMaster"
        grab(app.window, SHOTS / "03-adaptive-open.png")
        evidence["screenshots"].append("03-adaptive-open.png")

        # Leave early after recognition/assisted so practice persists.
        leave = _drive(app, root, leave_early=True)
        evidence["leave_early"] = leave
        evidence["leave_early"]["vocab_complete"] = study._session_for("nl").vocabulary_complete()
        evidence["leave_early"]["guest_practice_rows"] = _count_practice(ROOT, guest_lang="nl")
        evidence["leave_early"]["attempts_lines"] = _attempts_count(
            ROOT / "languages" / "nl" / "attempts.jsonl"
        )

        # Continue / complete a full adaptive round.
        study.open_adaptive_vocab_section("nl")
        root.update()
        app2 = study._adaptive_app
        grab(app2.window, SHOTS / "04-adaptive-resume.png")
        evidence["screenshots"].append("04-adaptive-resume.png")
        done = _drive(app2, root, leave_early=False)
        evidence["complete_round"] = done
        evidence["complete_round"]["vocab_complete"] = study._session_for(
            "nl"
        ).vocabulary_complete()
        evidence["complete_round"]["guest_practice_rows"] = _count_practice(
            ROOT, guest_lang="nl"
        )
        evidence["complete_round"]["attempts_lines"] = _attempts_count(
            ROOT / "languages" / "nl" / "attempts.jsonl"
        )
        if app2.window.winfo_exists():
            grab(app2.window, SHOTS / "05-adaptive-complete.png")
            evidence["screenshots"].append("05-adaptive-complete.png")
        else:
            grab(root, SHOTS / "05-studymaster-after-complete.png")
            evidence["screenshots"].append("05-studymaster-after-complete.png")
    finally:
        _restore_adaptive_patch(study)

    guest = open_guest_store(str(ROOT), "nl")
    history = guest.for_vocab(FIETS, "nl")
    guest.close()
    from adaptive_vocabulary import AdaptiveVocabularySession
    from practice_record import practice_start_level

    restart_session = AdaptiveVocabularySession(
        [ENTRIES[0]],
        language_code="nl",
        pool=ENTRIES,
        practice_history=history,
        rng=random.Random(4),
    )
    evidence["restart"] = {
        "practice_rows_for_fiets": len(history),
        "start_kind": restart_session.current_card().kind
        if restart_session.current_card()
        else None,
        "expected_kind": practice_start_level("introduction", history, allow_promote=True)
        if history
        else None,
    }

    evidence["accounts"] = _account_isolation_demo(ROOT)

    try:
        grab(root, SHOTS / "06-studymaster-final.png")
        evidence["screenshots"].append("06-studymaster-final.png")
    except Exception as error:
        evidence["final_shot_error"] = str(error)

    EVIDENCE.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    try:
        root.destroy()
    except Exception:
        pass
    return evidence


def main() -> int:
    evidence = run_home_workflow_demo()
    print(f"Wrote {EVIDENCE}")
    print(f"Screenshots under {SHOTS}")
    assert evidence["route"]["prefer_adaptive"] is True
    assert evidence["leave_early"].get("left_early") is True
    assert evidence["leave_early"].get("vocab_complete") is False
    assert evidence["leave_early"].get("guest_practice_rows", 0) >= 1
    assert evidence["complete_round"].get("writes", 0) >= 1
    assert evidence["complete_round"].get("vocab_complete") is True
    assert evidence["accounts"]["101"]["assisted_added_outbox"] == 0
    assert evidence["accounts"]["101"]["independent_added_outbox"] >= 1
    assert evidence["accounts"]["202"]["assisted_added_outbox"] == 0
    assert Path(evidence["accounts"]["101"]["practice_db"]).exists()
    assert Path(evidence["accounts"]["202"]["practice_db"]).exists()
    assert evidence["accounts"]["101"]["practice_db"] != evidence["accounts"]["202"][
        "practice_db"
    ]
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
