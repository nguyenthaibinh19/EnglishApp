#!/usr/bin/env python3
"""Phase 18C.2 — two-profile signed-in learning sync demonstration.

Uses the same study_data facade the Tkinter Vocabulary / Quiz / Progress /
Mistake Book screens use. Runs isolated localhost staging with synthetic
accounts. Does not touch production or enable production STUDY_SYNC_ENABLED.

Usage (repository root, PYTHONPATH=app):

    python tools/demo_18c2_signed_in_gui_sync.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import threading
import uuid
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import account_server  # noqa: E402
import account_store  # noqa: E402
import config  # noqa: E402
from account_local_store import AccountLocalStore  # noqa: E402
from account_sync_client import AccountSyncClient  # noqa: E402
from account_sync_engine import AccountSyncEngine  # noqa: E402
from legacy_import_app import preview_guest_vocabulary  # noqa: E402
from study_data import open_study_data  # noqa: E402
from vocab_identity import new_vocab_id  # noqa: E402

LANGUAGE = "nl"
EVIDENCE = ROOT / "qa-evidence" / "phase18c2-gui-sync"


def _log(message: str) -> None:
    print(message, flush=True)


def _write_guest(root: Path, word: str = "guest") -> Path:
    folder = root / "languages" / LANGUAGE
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "vocab.json"
    path.write_text(
        json.dumps(
            [
                {
                    "id": str(uuid.uuid4()),
                    "word": word,
                    "meaning": "guest-only",
                }
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def _bind_device(monkey_settings: Path, data_root: Path, user_id: int, token: str, username: str):
    monkey_settings.write_text("{}", encoding="utf-8")
    config.SETTINGS_FILE = str(monkey_settings)
    config.data_dir = lambda: str(data_root)  # type: ignore
    config.save_account(username, token, user_id=user_id)
    config.reload()


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="lg-18c2-demo-"))
    server_dir = work / "server"
    device_a = work / "device_a"
    device_b = work / "device_b"
    device_b_account = work / "device_b_account_b"
    for path in (server_dir, device_a, device_b, device_b_account):
        path.mkdir(parents=True)

    guest_a = _write_guest(device_a, "gast")
    guest_b = _write_guest(device_b, "gast")

    os.environ["STUDY_SYNC_ENABLED"] = "1"
    os.environ["STUDY_SYNC_DIR"] = str(server_dir)
    os.environ["ACCOUNT_BIND"] = "127.0.0.1"

    original_db_path = account_store.db_path

    def db_path(explicit=None):
        root = explicit or str(server_dir)
        return os.path.join(root, account_store.DB_FILE)

    account_store.db_path = db_path
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
        _log(f"Staging server: {base}")
        _log(f"Work dir: {work}")

        # --- Device A signed in as account A: Vocabulary Manager path ---
        settings_a = device_a / "settings.json"
        _bind_device(settings_a, device_a, user_a, token_a, "alice")
        bundle_a = open_study_data(LANGUAGE, data_root=str(device_a))
        assert bundle_a.signed_in
        assert bundle_a.vocab.add("fiets", "bike")
        assert bundle_a.vocab.add("huis", "house")
        # Edit via Word Detail path
        idx = bundle_a.vocab.index_of("huis")
        assert idx is not None
        bundle_a.vocab.update(idx, "huis", "home")
        store_a = AccountLocalStore(user_a, data_root=str(device_a))
        engine_a = AccountSyncEngine(
            store_a, AccountSyncClient(base, token_a), poll_seconds=3600
        )
        snap = engine_a.sync_once()
        _log(f"Device A after vocab upload: {snap.status}")

        # Preferences
        from account_prefs import mark_preferences_dirty

        mark_preferences_dirty(store_a)
        snap = engine_a.sync_once()
        _log(f"Device A after prefs: {snap.status}")

        # Quiz / attempt path (same as QuizEngine → AccountAttemptHistory)
        vids = [e["id"] for e in bundle_a.vocab.all()]
        from attempt_history import LearningAttempt

        for vid, word in zip(vids, ["fiets", "huis"]):
            bundle_a.attempts.record(
                LearningAttempt(
                    timestamp="2026-11-19T15:00:00+00:00",
                    language_code=LANGUAGE,
                    word=word,
                    user_answer="bike" if word == "fiets" else "wrong",
                    expected_answer="bike" if word == "fiets" else "home",
                    correct=word == "fiets",
                    verdict="exact" if word == "fiets" else "wrong",
                    hint_used=False,
                    prompt="meaning?",
                    vocab_id=vid,
                )
            )
        snap = engine_a.sync_once()
        _log(f"Device A after quiz attempts: {snap.status} pending_progress={snap.pending_progress}")

        # --- Device B same account: pull without manual import ---
        settings_b = device_b / "settings.json"
        _bind_device(settings_b, device_b, user_a, token_a, "alice")
        store_b = AccountLocalStore(user_a, data_root=str(device_b))
        engine_b = AccountSyncEngine(
            store_b, AccountSyncClient(base, token_a), poll_seconds=3600
        )
        snap = engine_b.sync_once()
        bundle_b = open_study_data(LANGUAGE, data_root=str(device_b))
        words_b = sorted(e["word"] for e in bundle_b.vocab.all())
        _log(f"Device B vocabulary (GUI facade): {words_b}")
        assert "fiets" in words_b and "huis" in words_b
        meanings = {e["word"]: e.get("meaning") for e in bundle_b.vocab.all()}
        assert meanings.get("huis") == "home"
        attempts_b = bundle_b.attempts.load_attempts()
        _log(f"Device B attempts: {len(attempts_b)}")
        assert len(attempts_b) >= 2
        from mistake_book import summarize_mistakes

        mistakes = summarize_mistakes(attempts_b, language_code=LANGUAGE)
        _log(f"Device B Mistake Book rows: {len(mistakes)}")
        assert any(m.word == "huis" for m in mistakes)
        progress_summary = bundle_b.progress.summary()
        _log(f"Device B progress summary: {progress_summary}")

        # Offline study on A then reconnect
        engine_a.store.set_offline(True)
        bundle_a.vocab.add("boom", "tree")
        snap = engine_a.sync_once()  # may stay offline if we don't clear — client still works
        # Force online sync
        engine_a.store.set_offline(False)
        snap = engine_a.sync_once()
        engine_b.sync_once()
        bundle_b = open_study_data(LANGUAGE, data_root=str(device_b))
        assert any(e["word"] == "boom" for e in bundle_b.vocab.all())
        _log("Offline add on A converged to B.")

        # Account B isolation on third profile
        settings_bb = device_b_account / "settings.json"
        _bind_device(settings_bb, device_b_account, user_b, token_b, "bob")
        store_bb = AccountLocalStore(user_b, data_root=str(device_b_account))
        engine_bb = AccountSyncEngine(
            store_bb, AccountSyncClient(base, token_b), poll_seconds=3600
        )
        engine_bb.sync_once()
        bundle_bb = open_study_data(LANGUAGE, data_root=str(device_b_account))
        assert bundle_bb.vocab.count() == 0
        _log("Account B remains empty (isolated).")

        # Legacy import consent on Device A — guest file unchanged
        preview = preview_guest_vocabulary(LANGUAGE, data_root=str(device_a))
        assert preview["entry_count"] >= 1
        before = guest_a.read_text(encoding="utf-8")
        store_a.grant_legacy_consent(LANGUAGE, "guest", note="demo")
        result = store_a.import_guest_vocabulary(
            LANGUAGE, preview["entries"], require_consent=True
        )
        after = guest_a.read_text(encoding="utf-8")
        assert before == after
        _log(f"Legacy import: {result}; guest file unchanged={before == after}")

        # Conflict resolution: divergent concurrent edits → OUTBOX_CONFLICT on A
        vid = new_vocab_id()
        store_a.upsert_vocabulary(
            language_code=LANGUAGE,
            vocab_id=vid,
            payload={"id": vid, "word": "zon", "meaning": "base"},
        )
        engine_a.sync_once()
        engine_b.sync_once()
        store_a.upsert_vocabulary(
            language_code=LANGUAGE,
            vocab_id=vid,
            payload={"id": vid, "word": "zon", "meaning": "local-pending"},
        )
        store_b.upsert_vocabulary(
            language_code=LANGUAGE,
            vocab_id=vid,
            payload={"id": vid, "word": "zon", "meaning": "remote-accepted"},
        )
        engine_b.sync_once()
        engine_a.sync_once()
        conflicts = store_a.list_open_vocab_conflicts()
        _log(f"Open conflicts on A: {len(conflicts)}")
        assert conflicts, "expected vocabulary conflict for resolution UX"
        store_a.resolve_vocab_conflict(
            conflicts[0]["language_code"], conflicts[0]["vocab_id"], keep="server"
        )
        engine_a.sync_once()
        _log("Conflict resolved keeping server tip.")

        # Persist evidence
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        evidence = {
            "staging_base": base,
            "device_a_words": sorted(e["word"] for e in open_study_data(LANGUAGE, data_root=str(device_a)).vocab.all()),
            "device_b_words": sorted(e["word"] for e in open_study_data(LANGUAGE, data_root=str(device_b)).vocab.all()),
            "device_b_attempts": len(open_study_data(LANGUAGE, data_root=str(device_b)).attempts.load_attempts()),
            "account_b_words": sorted(
                e["word"]
                for e in open_study_data(LANGUAGE, data_root=str(device_b_account)).vocab.all()
            ),
            "guest_a_unchanged": before == after,
            "legacy_import": result,
            "progress_summary_b": progress_summary,
            "prefs_a": store_a.get_preferences(),
            "note": (
                "Evidence uses the same open_study_data() facade as Tkinter "
                "Vocabulary Manager, Quiz, Progress, and Mistake Book when signed in."
            ),
        }
        (EVIDENCE / "demo_18c2_results.json").write_text(
            json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        checklist = EVIDENCE / "DEMO_CHECKLIST.md"
        checklist.write_text(
            "\n".join(
                [
                    "# Phase 18C.2 GUI sync demo checklist",
                    "",
                    f"- Staging server: `{base}`",
                    f"- Work directory: `{work}`",
                    "- [x] Login account A on Device A (settings + AccountLocalStore)",
                    "- [x] Add/edit vocabulary via study_data VocabStore facade",
                    "- [x] Login account A on Device B — vocabulary appears without import",
                    "- [x] Quiz attempts on A → Mistake Book / progress on B",
                    "- [x] Offline add converges after reconnect",
                    "- [x] Account B isolated",
                    "- [x] Preferences seeded/synced (contract v1)",
                    "- [x] Legacy import requires consent; guest JSON unchanged",
                    "- [x] Conflict list/resolve API exercised",
                    "",
                    "Tkinter screens wired to `open_study_data()`: Vocabulary Library,",
                    "Quiz, Progress, Mistake Book, Daily Study, Reading/Listening add,",
                    "Home StudyMaster sync status + conflict/import dialogs.",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        _log(f"Evidence written to {EVIDENCE}")
        _log("APP_18C2_DEMO_OK")
        engine_a.stop(timeout=1)
        engine_b.stop(timeout=1)
        engine_bb.stop(timeout=1)
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        return 0
    finally:
        account_store.db_path = original_db_path


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        _log(f"DEMO FAILED: {error}")
        raise
