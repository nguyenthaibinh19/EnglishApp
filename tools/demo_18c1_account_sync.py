#!/usr/bin/env python3
"""Local two-device / two-account account learning sync demonstration (Phase 18C.1).

Runs an isolated localhost staging server with synthetic accounts A and B and two
independent client storage directories. Does not touch production databases or
enable production STUDY_SYNC_ENABLED.

Usage (from repository root, with PYTHONPATH=app):

    python tools/demo_18c1_account_sync.py

Manual verification checklist is printed at the end.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import threading
import time
import uuid
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import account_server  # noqa: E402
import account_store  # noqa: E402
from account_local_store import AccountLocalStore  # noqa: E402
from account_sync_client import AccountSyncClient  # noqa: E402
from account_sync_engine import AccountSyncEngine  # noqa: E402

VOCAB = "11111111-1111-4111-8111-111111111111"
LANGUAGE = "nl"


def _log(message: str) -> None:
    print(message, flush=True)


def _write_guest_vocab(root: Path) -> Path:
    guest = root / "languages" / LANGUAGE
    guest.mkdir(parents=True, exist_ok=True)
    path = guest / "vocab.json"
    path.write_text(
        json.dumps(
            [{"id": "99999999-9999-4999-8999-999999999999", "word": "guest", "meaning": "only-local"}],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="lg-18c1-demo-"))
    server_dir = work / "server"
    device_a_root = work / "device_a"
    device_b_root = work / "device_b"
    account_b_root = work / "account_b_device"
    for path in (server_dir, device_a_root, device_b_root, account_b_root):
        path.mkdir(parents=True)

    guest_a = _write_guest_vocab(device_a_root)
    guest_b = _write_guest_vocab(device_b_root)

    os.environ["STUDY_SYNC_ENABLED"] = "1"
    os.environ["STUDY_SYNC_DIR"] = str(server_dir)
    os.environ["ACCOUNT_BIND"] = "127.0.0.1"

    # Point accounts.db into the staging folder.
    original_db_path = account_store.db_path

    def staging_db_path(folder=None):
        return os.path.join(str(server_dir), account_store.DB_FILE)

    account_store.db_path = staging_db_path  # type: ignore[assignment]

    account_store.add_user("account_a", "secret-a")
    account_store.add_user("account_b", "secret-b")
    token_a = account_store.login("account_a", "secret-a")
    token_b = account_store.login("account_b", "secret-b")
    user_a = account_store.user_for_token(token_a)
    user_b = account_store.user_for_token(token_b)
    assert user_a and user_b

    server = ThreadingHTTPServer(("127.0.0.1", 0), account_server.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    base_url = f"http://127.0.0.1:{port}"
    _log(f"Staging server: {base_url}")
    _log(f"Work directory: {work}")

    evidence = {
        "base_url": base_url,
        "work_dir": str(work),
        "account_a_id": int(user_a["id"]),
        "account_b_id": int(user_b["id"]),
        "steps": [],
    }

    try:
        store_a1 = AccountLocalStore(int(user_a["id"]), data_root=str(device_a_root))
        store_a2 = AccountLocalStore(int(user_a["id"]), data_root=str(device_b_root))
        store_b = AccountLocalStore(int(user_b["id"]), data_root=str(account_b_root))
        engine_a1 = AccountSyncEngine(
            store_a1, AccountSyncClient(base_url, token_a), poll_seconds=3600
        )
        engine_a2 = AccountSyncEngine(
            store_a2, AccountSyncClient(base_url, token_a), poll_seconds=3600
        )
        engine_b = AccountSyncEngine(
            store_b, AccountSyncClient(base_url, token_b), poll_seconds=3600
        )

        # 1. Device A adds vocabulary.
        store_a1.upsert_vocabulary(
            language_code=LANGUAGE,
            vocab_id=VOCAB,
            payload={"id": VOCAB, "word": "huis", "meaning": "house"},
        )
        status = engine_a1.sync_once()
        evidence["steps"].append(
            {
                "step": 1,
                "name": "device_a_add_vocab",
                "status": status.status,
                "vocab": store_a1.list_vocabulary(LANGUAGE),
            }
        )
        _log(f"[1] Device A uploaded vocabulary → {status.status}")

        # 2. Device B (same account) receives it.
        status = engine_a2.sync_once()
        vocab_on_b = store_a2.list_vocabulary(LANGUAGE)
        evidence["steps"].append(
            {
                "step": 2,
                "name": "device_b_receives_vocab",
                "status": status.status,
                "vocab": vocab_on_b,
            }
        )
        assert any(item["id"] == VOCAB for item in vocab_on_b), "Device B missing vocabulary"
        _log(f"[2] Device B received vocabulary → {status.status}")

        # 3. Device A answers a quiz question.
        event_id = store_a1.record_learning_attempt(
            language_code=LANGUAGE,
            vocab_id=VOCAB,
            verdict="exact",
            hint_used=False,
            word_snapshot="huis",
            user_answer="house",
            expected_answer="house",
            prompt="What does huis mean?",
        )
        status = engine_a1.sync_once()
        evidence["steps"].append(
            {
                "step": 3,
                "name": "device_a_quiz",
                "event_id": event_id,
                "status": status.status,
                "confirmed": store_a1.confirmed_progress(LANGUAGE, VOCAB),
            }
        )
        _log(f"[3] Device A answered quiz (event {event_id}) → {status.status}")

        # 4. Device B receives history / progress / SRS / Mistake Book state.
        status = engine_a2.sync_once()
        attempts_b = store_a2.list_attempts(LANGUAGE)
        confirmed_b = store_a2.confirmed_progress(LANGUAGE, VOCAB)
        mistakes_b = store_a2.mistake_book_entries(LANGUAGE)
        evidence["steps"].append(
            {
                "step": 4,
                "name": "device_b_progress",
                "status": status.status,
                "attempts": attempts_b,
                "confirmed": confirmed_b,
                "mistakes": mistakes_b,
            }
        )
        assert any(item["event_id"] == event_id for item in attempts_b)
        assert confirmed_b and int(confirmed_b["seen"]) >= 1
        _log(
            f"[4] Device B progress seen={confirmed_b['seen']} streak={confirmed_b['streak']} "
            f"attempts={len(attempts_b)} → {status.status}"
        )

        # 5. Device B offline answer, then reconnect.
        store_a2.set_offline(True)
        offline_event = store_a2.record_learning_attempt(
            language_code=LANGUAGE,
            vocab_id=VOCAB,
            verdict="wrong",
            hint_used=False,
            word_snapshot="huis",
            user_answer="home",
            expected_answer="house",
            prompt="What does huis mean?",
        )
        assert store_a2.status().status in {"Offline", "Pending"}
        # Simulate reconnect.
        store_a2.set_offline(False)
        status = engine_a2.sync_once()
        status_a1 = engine_a1.sync_once()
        evidence["steps"].append(
            {
                "step": 5,
                "name": "offline_reconnect",
                "offline_event": offline_event,
                "device_b_status": status.status,
                "device_a_status": status_a1.status,
                "device_a_attempts": [a["event_id"] for a in store_a1.list_attempts(LANGUAGE)],
                "device_b_attempts": [a["event_id"] for a in store_a2.list_attempts(LANGUAGE)],
            }
        )
        assert offline_event in [a["event_id"] for a in store_a1.list_attempts(LANGUAGE)]
        _log(f"[5] Offline event synced both ways → A={status_a1.status} B={status.status}")

        # 6. Convergence without duplicated attempts.
        ids_a = sorted(a["event_id"] for a in store_a1.list_attempts(LANGUAGE))
        ids_b = sorted(a["event_id"] for a in store_a2.list_attempts(LANGUAGE))
        assert ids_a == ids_b
        assert len(ids_a) == len(set(ids_a))
        evidence["steps"].append({"step": 6, "name": "convergence", "event_ids": ids_a})
        _log(f"[6] Converged event ids: {ids_a}")

        # 7. Account B cannot see account A's data.
        engine_b.sync_once()
        assert store_b.list_vocabulary(LANGUAGE) == []
        assert store_b.list_attempts(LANGUAGE) == []
        evidence["steps"].append(
            {
                "step": 7,
                "name": "account_isolation",
                "account_b_vocab": store_b.list_vocabulary(LANGUAGE),
                "account_b_attempts": store_b.list_attempts(LANGUAGE),
            }
        )
        _log("[7] Account B isolated (empty vocab/attempts)")

        # 8. Restart preserves cursors.
        cursors_before = store_a2.cursors()
        store_a2.close()
        store_a2_reopened = AccountLocalStore(int(user_a["id"]), data_root=str(device_b_root))
        cursors_after = store_a2_reopened.cursors()
        assert cursors_before == cursors_after
        evidence["steps"].append(
            {
                "step": 8,
                "name": "restart_cursors",
                "before": cursors_before,
                "after": cursors_after,
            }
        )
        _log(f"[8] Restart preserved cursors: {cursors_after}")

        # Guest files untouched and never auto-uploaded.
        guest_payload = json.loads(guest_a.read_text(encoding="utf-8"))
        assert guest_payload[0]["word"] == "guest"
        assert not any(item.get("word") == "guest" for item in store_a1.list_vocabulary(LANGUAGE))
        evidence["guest_vocab_preserved"] = True
        evidence["guest_not_uploaded"] = True

        evidence_path = work / "APP_18C1_DEMO_EVIDENCE.json"
        evidence_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")
        _log("")
        _log("DEMO OK — all eight scenarios passed.")
        _log(f"Evidence: {evidence_path}")
        _log("")
        _log("Manual verification:")
        _log(f"  1. Inspect {device_a_root / 'accounts'}")
        _log(f"  2. Inspect {device_b_root / 'accounts'}")
        _log(f"  3. Confirm guest files still at {guest_a} and {guest_b}")
        _log(f"  4. Server study_sync.db at {server_dir / 'study_sync.db'}")
        _log("  5. Production STUDY_SYNC_ENABLED was not required outside this process.")

        engine_a1.stop()
        engine_a2.stop()
        engine_b.stop()
        store_a2_reopened.close()
        return 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        account_store.db_path = original_db_path  # type: ignore[assignment]
        # Keep work dir for inspection; comment next line to retain always.
        # shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
