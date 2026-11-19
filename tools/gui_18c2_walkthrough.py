#!/usr/bin/env python3
"""Phase 18C.2 R1 — real Tkinter two-profile GUI walkthrough (synthetic staging).

Launches actual Vocabulary / Quiz / Mistake Book / Progress screens against two
isolated data roots and a localhost staging server. Captures window screenshots
when possible.

Usage (repo root, PYTHONPATH=app):

    python tools/gui_18c2_walkthrough.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
import traceback
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

EVIDENCE = ROOT / "qa-evidence" / "phase18c2-gui-sync" / "gui-walkthrough"


def _log(msg: str) -> None:
    print(msg, flush=True)


def _screenshot(window, path: Path) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        window.update_idletasks()
        window.update()
        x = window.winfo_rootx()
        y = window.winfo_rooty()
        w = window.winfo_width()
        h = window.winfo_height()
        try:
            from PIL import ImageGrab

            image = ImageGrab.grab(bbox=(x, y, x + w, y + h))
            image.save(path)
            return True
        except Exception:
            # Fallback: widget dump as text evidence (not a fabricated screenshot).
            path.with_suffix(".txt").write_text(
                f"window={window.title()}\ngeometry={w}x{h}+{x}+{y}\n",
                encoding="utf-8",
            )
            return False
    except Exception as error:
        path.with_suffix(".err.txt").write_text(str(error), encoding="utf-8")
        return False


def main() -> int:
    import tkinter as tk

    import account_server
    import account_store
    import config
    from account_local_store import AccountLocalStore
    from account_sync_client import AccountSyncClient
    from account_sync_engine import AccountSyncEngine, stop_active
    from learning_progress import load_learning_progress
    from mistake_book import load_mistake_summaries
    from mistake_book_app import MistakeBookApp
    from progress_app import ProgressApp
    from quiz_app import VocabQuizApp
    from study_data import open_study_data
    from vocabulary_app import VocabularyLibraryApp

    work = Path(tempfile.mkdtemp(prefix="lg-18c2-gui-"))
    server_dir = work / "server"
    device_a = work / "device_a"
    device_b = work / "device_b"
    for path in (server_dir, device_a, device_b, EVIDENCE):
        path.mkdir(parents=True, exist_ok=True)

    os.environ["STUDY_SYNC_ENABLED"] = "1"
    os.environ["STUDY_SYNC_DIR"] = str(server_dir)
    original_db_path = account_store.db_path

    def db_path(explicit=None):
        return os.path.join(explicit or str(server_dir), account_store.DB_FILE)

    account_store.db_path = db_path
    notes = []
    shots = []

    try:
        account_store.add_user("alice", "secret-a")
        account_store.add_user("bob", "secret-b")
        token_a = account_store.login("alice", "secret-a")
        token_b = account_store.login("bob", "secret-b")
        user_a = int(account_store.user_for_token(token_a)["id"])
        user_b = int(account_store.user_for_token(token_b)["id"])

        server = ThreadingHTTPServer(("127.0.0.1", 0), account_server.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_address[1]}"
        notes.append(f"staging={base}")
        notes.append(f"work={work}")

        def bind(device_root: Path, user_id: int, token: str, username: str):
            stop_active()
            device_root.mkdir(parents=True, exist_ok=True)
            settings = device_root / "settings.json"
            settings.write_text("{}", encoding="utf-8")
            config.SETTINGS_FILE = str(settings)
            config.data_dir = lambda: str(device_root)  # type: ignore
            config.ACCOUNT_SERVER_URL = base
            config.save_account(username, token, user_id=user_id)
            config.set_study_codes(["nl"])
            config.set_language("nl")
            config.reload()
            store = AccountLocalStore(user_id, data_root=str(device_root))
            engine = AccountSyncEngine(
                store, AccountSyncClient(base, token), poll_seconds=3600
            )
            return store, engine

        root = tk.Tk()
        root.title("18C.2 GUI walkthrough host")
        root.geometry("200x80+40+40")

        # --- Device A: Vocabulary screen ---
        store_a, engine_a = bind(device_a, user_a, token_a, "alice")
        win_a = tk.Toplevel(root)
        win_a.title("Device A — Vocabulary")
        win_a.geometry("640x560+80+80")
        vocab_a = VocabularyLibraryApp(win_a, language_code="nl")
        root.update()
        # Drive the same save path as the Add-word dialog.
        assert vocab_a.store is not None
        assert vocab_a.store.add("fiets", "bike")
        assert vocab_a.store.add("huis", "house")
        idx = vocab_a.store.index_of("huis")
        assert idx is not None
        assert vocab_a.store.update(idx, "huis", "home")
        vocab_a.reload()
        root.update()
        shot = EVIDENCE / "01_device_a_vocabulary.png"
        shots.append(("vocab_a", _screenshot(win_a, shot), str(shot)))
        notes.append(f"device_a_words={[e['word'] for e in vocab_a.store.all()]}")
        engine_a.sync_once()

        # Quiz on Device A
        win_quiz = tk.Toplevel(root)
        win_quiz.title("Device A — Quiz")
        win_quiz.geometry("640x520+740+80")
        quiz = VocabQuizApp(
            win_quiz,
            language_code="nl",
            target=1,
            required=False,
            locked=False,
            allow_manage=False,
        )
        root.update()
        # Answer the current prompt using the engine's expected word.
        current = quiz.engine.current_entry
        assert current is not None, "Quiz screen opened with no current entry"
        expected = str(current.get("word") or "")
        # Deliberate wrong answer first so Mistake Book has a row after sync.
        quiz.answer_var.set("definitely-wrong")
        quiz._submit()
        root.update()
        time.sleep(2.6)
        root.update()
        if not quiz.engine.finished and quiz.engine.current_entry is not None:
            quiz.answer_entry.state(["!disabled"])
            quiz.submit_button.state(["!disabled"])
            quiz.answer_var.set(str(quiz.engine.current_entry.get("word") or expected))
            quiz._submit()
            root.update()
            time.sleep(0.7)
            root.update()
        shot = EVIDENCE / "02_device_a_quiz.png"
        shots.append(("quiz_a", _screenshot(win_quiz, shot), str(shot)))
        store_a, engine_a = bind(device_a, user_a, token_a, "alice")
        engine_a.sync_once()
        notes.append(
            "device_a_attempts="
            f"{len(open_study_data('nl', data_root=str(device_a)).attempts.load_attempts())}"
        )

        # --- Device B same account ---
        store_b, engine_b = bind(device_b, user_a, token_a, "alice")
        engine_b.sync_once()
        win_b = tk.Toplevel(root)
        win_b.title("Device B — Vocabulary")
        win_b.geometry("640x560+80+420")
        vocab_b = VocabularyLibraryApp(win_b, language_code="nl")
        root.update()
        words_b = [e["word"] for e in vocab_b.store.all()]
        notes.append(f"device_b_words={words_b}")
        assert "fiets" in words_b and "huis" in words_b
        shot = EVIDENCE / "03_device_b_vocabulary.png"
        shots.append(("vocab_b", _screenshot(win_b, shot), str(shot)))

        win_mistakes = tk.Toplevel(root)
        win_mistakes.title("Device B — Mistake Book")
        win_mistakes.geometry("560x420+740+420")
        MistakeBookApp(win_mistakes, language_code="nl")
        root.update()
        mistakes = load_mistake_summaries(language_code="nl")
        notes.append(f"device_b_mistakes={len(mistakes)}")
        shot = EVIDENCE / "04_device_b_mistake_book.png"
        shots.append(("mistakes_b", _screenshot(win_mistakes, shot), str(shot)))

        win_progress = tk.Toplevel(root)
        win_progress.title("Device B — Progress")
        win_progress.geometry("560x420+740+700")
        ProgressApp(win_progress, language_code="nl")
        root.update()
        snap = load_learning_progress("nl")
        notes.append(
            f"device_b_progress_total={getattr(snap, 'vocab_total', None)} "
            f"attempts={len(getattr(snap, 'recent_attempts', []) or [])}"
        )
        shot = EVIDENCE / "05_device_b_progress.png"
        shots.append(("progress_b", _screenshot(win_progress, shot), str(shot)))

        # Offline edit on A then reconnect
        store_a.set_offline(True)
        bind(device_a, user_a, token_a, "alice")  # rebind settings to A
        bundle_a = open_study_data("nl", data_root=str(device_a))
        assert bundle_a.vocab.add("boom", "tree")
        store_a.set_offline(False)
        engine_a = AccountSyncEngine(
            store_a, AccountSyncClient(base, token_a), poll_seconds=3600
        )
        engine_a.sync_once()
        bind(device_b, user_a, token_a, "alice")
        engine_b = AccountSyncEngine(
            store_b, AccountSyncClient(base, token_a), poll_seconds=3600
        )
        engine_b.sync_once()
        words_b2 = [e["word"] for e in open_study_data("nl", data_root=str(device_b)).vocab.all()]
        notes.append(f"after_offline_converge={words_b2}")
        assert "boom" in words_b2

        # Logout / switch to account B on device A profile — isolation
        stop_active()
        config.clear_account()
        store_bob, engine_bob = bind(device_a / "bob_profile", user_b, token_b, "bob")
        engine_bob.sync_once()
        bob_words = open_study_data("nl", data_root=str(device_a / "bob_profile")).vocab.all()
        notes.append(f"account_b_words={[e['word'] for e in bob_words]}")
        assert bob_words == []

        report = {
            "status": "GUI_WALKTHROUGH_OK",
            "notes": notes,
            "screenshots": [
                {"name": name, "captured": captured, "path": path}
                for name, captured, path in shots
            ],
            "png_captured": sum(1 for _, captured, _ in shots if captured),
        }
        (EVIDENCE / "WALKTHROUGH_REPORT.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        (EVIDENCE / "WALKTHROUGH_NOTES.md").write_text(
            "\n".join(
                [
                    "# 18C.2 real Tkinter GUI walkthrough",
                    "",
                    *[f"- {line}" for line in notes],
                    "",
                    f"PNG screenshots captured: {report['png_captured']}/{len(shots)}",
                    "",
                    "Windows exercised: VocabularyLibraryApp, VocabQuizApp, MistakeBookApp, ProgressApp",
                    "on two isolated data roots with synthetic staging accounts.",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        _log(json.dumps(report, indent=2))
        _log("APP_18C2_GUI_WALKTHROUGH_OK")
        try:
            root.destroy()
        except Exception:
            pass
        engine_a.stop(timeout=1)
        engine_b.stop(timeout=1)
        engine_bob.stop(timeout=1)
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        return 0
    except Exception as error:
        _log("APP_18C2_GUI_WALKTHROUGH_BLOCKED")
        _log(str(error))
        traceback.print_exc()
        (EVIDENCE / "WALKTHROUGH_BLOCKED.txt").write_text(
            traceback.format_exc(), encoding="utf-8"
        )
        return 1
    finally:
        account_store.db_path = original_db_path
        try:
            stop_active()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
