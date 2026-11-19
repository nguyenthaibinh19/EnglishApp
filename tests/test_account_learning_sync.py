"""Phase 18C.1 — account-isolated vocabulary + event-first progress sync."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

import account_server
import account_store
import sync_store
from account_local_store import (
    STATUS_CONFLICT,
    STATUS_OFFLINE,
    STATUS_PENDING,
    STATUS_SYNCED,
    AccountLocalStore,
    guest_language_dir,
)
from account_sync_client import AccountSyncClient
from account_sync_engine import AccountSyncEngine

VOCAB = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
VOCAB_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


def _payload(vocab_id: str = VOCAB, meaning: str = "house") -> dict:
    return {"id": vocab_id, "word": "huis", "meaning": meaning}


def _use_tmp_accounts(monkeypatch, folder: Path) -> None:
    def db_path(explicit=None):
        root = explicit or str(folder)
        return os.path.join(root, account_store.DB_FILE)

    monkeypatch.setattr(account_store, "db_path", db_path)


@pytest.fixture
def staging(tmp_path, monkeypatch):
    server_dir = tmp_path / "server"
    server_dir.mkdir()
    _use_tmp_accounts(monkeypatch, server_dir)
    monkeypatch.setenv("STUDY_SYNC_ENABLED", "1")
    monkeypatch.setenv("STUDY_SYNC_DIR", str(server_dir))
    account_store.add_user("alice", "secret-a")
    account_store.add_user("bob", "secret-b")
    token_a = account_store.login("alice", "secret-a")
    token_b = account_store.login("bob", "secret-b")
    user_a = account_store.user_for_token(token_a)
    user_b = account_store.user_for_token(token_b)
    server = ThreadingHTTPServer(("127.0.0.1", 0), account_server.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    ctx = {
        "tmp": tmp_path,
        "base": base,
        "token_a": token_a,
        "token_b": token_b,
        "user_a": int(user_a["id"]),
        "user_b": int(user_b["id"]),
        "server_dir": server_dir,
    }
    try:
        yield ctx
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _engine(store, base, token):
    return AccountSyncEngine(store, AccountSyncClient(base, token), poll_seconds=3600)


def test_schema_v3_progress_tables_and_accept(tmp_path):
    path = tmp_path / "sync.db"
    conn = sync_store.connect(str(path))
    assert sync_store.schema_version(conn) == 3
    event = {
        "event_id": "evt-1",
        "device_id": "dev-1",
        "language_code": "nl",
        "vocab_id": VOCAB,
        "verdict": "exact",
        "mastered": 1,
        "hint_used": 0,
        "occurred_at": "2026-11-19T10:00:00+00:00",
        "algorithm_id": "ladder-v2",
        "word_snapshot": "huis",
        "user_answer": "house",
        "expected_answer": "house",
        "prompt": "meaning?",
    }
    first = sync_store.accept_learning_attempt(conn, user_id=1, event=event)
    second = sync_store.accept_learning_attempt(conn, user_id=1, event=event)
    assert first.change_id == second.change_id
    assert first.progress_after.seen == 1
    assert first.progress_after.streak == 1
    assert first.progress_after.interval_days == 1
    pages = sync_store.list_progress_changes(conn, user_id=1, after_cursor=0)
    assert len(pages) == 1
    assert pages[0].event.user_answer == "house"

    conflict = dict(event)
    conflict["user_answer"] = "different"
    with pytest.raises(sync_store.SyncConflictError):
        sync_store.accept_learning_attempt(conn, user_id=1, event=conflict)
    conn.close()


def test_account_isolation_and_guest_preservation(staging):
    root_a = staging["tmp"] / "dev_a"
    root_b = staging["tmp"] / "dev_b"
    guest = Path(guest_language_dir("nl", str(root_a)))
    guest.mkdir(parents=True)
    guest_file = guest / "vocab.json"
    guest_file.write_text(
        json.dumps([{"id": VOCAB_B, "word": "guest", "meaning": "local-only"}]),
        encoding="utf-8",
    )

    store_a = AccountLocalStore(staging["user_a"], data_root=str(root_a))
    store_b = AccountLocalStore(staging["user_b"], data_root=str(root_b))
    eng_a = _engine(store_a, staging["base"], staging["token_a"])
    eng_b = _engine(store_b, staging["base"], staging["token_b"])

    store_a.upsert_vocabulary(language_code="nl", vocab_id=VOCAB, payload=_payload())
    eng_a.sync_once()
    eng_b.sync_once()

    assert any(item["id"] == VOCAB for item in store_a.list_vocabulary("nl"))
    assert store_b.list_vocabulary("nl") == []
    assert json.loads(guest_file.read_text(encoding="utf-8"))[0]["word"] == "guest"
    assert not any(item.get("word") == "guest" for item in store_a.list_vocabulary("nl"))
    eng_a.stop()
    eng_b.stop()


def test_two_device_vocab_and_progress_convergence(staging):
    root1 = staging["tmp"] / "phone"
    root2 = staging["tmp"] / "laptop"
    s1 = AccountLocalStore(staging["user_a"], data_root=str(root1))
    s2 = AccountLocalStore(staging["user_a"], data_root=str(root2))
    e1 = _engine(s1, staging["base"], staging["token_a"])
    e2 = _engine(s2, staging["base"], staging["token_a"])

    s1.upsert_vocabulary(language_code="nl", vocab_id=VOCAB, payload=_payload())
    assert e1.sync_once().status in {STATUS_SYNCED, STATUS_PENDING}
    e2.sync_once()
    assert any(item["id"] == VOCAB for item in s2.list_vocabulary("nl"))

    event_id = s1.record_learning_attempt(
        language_code="nl",
        vocab_id=VOCAB,
        verdict="exact",
        hint_used=False,
        word_snapshot="huis",
        user_answer="house",
        expected_answer="house",
        prompt="?",
    )
    e1.sync_once()
    e2.sync_once()
    assert any(a["event_id"] == event_id for a in s2.list_attempts("nl"))
    confirmed = s2.confirmed_progress("nl", VOCAB)
    assert confirmed is not None
    assert int(confirmed["seen"]) == 1
    assert int(confirmed["streak"]) == 1
    # Mistake book empty for exact-only history
    assert s2.mistake_book_entries("nl") == []

    # Offline then reconnect without duplicates
    s2.set_offline(True)
    offline_id = s2.record_learning_attempt(
        language_code="nl",
        vocab_id=VOCAB,
        verdict="wrong",
        hint_used=False,
        word_snapshot="huis",
        user_answer="home",
        expected_answer="house",
        prompt="?",
    )
    assert s2.status().status == STATUS_OFFLINE
    s2.set_offline(False)
    e2.sync_once()
    e1.sync_once()
    ids1 = sorted(a["event_id"] for a in s1.list_attempts("nl"))
    ids2 = sorted(a["event_id"] for a in s2.list_attempts("nl"))
    assert ids1 == ids2
    assert len(ids1) == 2
    assert offline_id in ids1
    assert e1.sync_once().status == STATUS_SYNCED
    assert e2.sync_once().status == STATUS_SYNCED

    # Restart preserves cursors
    before = s2.cursors()
    s2.close()
    reopened = AccountLocalStore(staging["user_a"], data_root=str(root2))
    assert reopened.cursors() == before
    e1.stop()
    e2.stop()
    reopened.close()


def test_idempotent_progress_retry_and_outbox_durability(staging):
    root = staging["tmp"] / "one"
    store = AccountLocalStore(staging["user_a"], data_root=str(root))
    engine = _engine(store, staging["base"], staging["token_a"])
    store.upsert_vocabulary(language_code="nl", vocab_id=VOCAB, payload=_payload())
    engine.sync_once()
    event_id = store.record_learning_attempt(
        language_code="nl",
        vocab_id=VOCAB,
        verdict="near",
        hint_used=False,
        word_snapshot="huis",
        user_answer="hause",
        expected_answer="house",
        prompt="?",
    )
    pending = store.pending_outbox()
    assert len(pending) == 1
    assert pending[0]["event_id"] == event_id
    engine.sync_once()
    # Second sync must not duplicate server rows.
    engine.sync_once()
    conn = sqlite3.connect(str(staging["server_dir"] / "study_sync.db"))
    count = conn.execute(
        "SELECT COUNT(*) FROM learning_attempts WHERE user_id = ? AND event_id = ?",
        (staging["user_a"], event_id),
    ).fetchone()[0]
    conn.close()
    assert count == 1
    assert store.status().status == STATUS_SYNCED
    mistakes = store.mistake_book_entries("nl")
    assert len(mistakes) == 1
    assert mistakes[0]["near"] == 1
    engine.stop()


def test_interrupted_transfer_leaves_pending_and_retries(staging):
    root = staging["tmp"] / "flaky"
    store = AccountLocalStore(staging["user_a"], data_root=str(root))
    client = AccountSyncClient(staging["base"], staging["token_a"])
    engine = AccountSyncEngine(store, client, poll_seconds=3600)
    store.upsert_vocabulary(language_code="nl", vocab_id=VOCAB, payload=_payload())

    # Break the client mid-flight by pointing at a closed port after local enqueue.
    store.record_learning_attempt(
        language_code="nl",
        vocab_id=VOCAB,
        verdict="wrong",
        hint_used=False,
        word_snapshot="huis",
        user_answer="x",
        expected_answer="house",
        prompt="?",
    )
    engine.client = AccountSyncClient("http://127.0.0.1:1", staging["token_a"], timeout=0.5)
    status = engine.sync_once()
    assert status.status == STATUS_OFFLINE
    assert store.pending_outbox()
    # Restore and retry
    engine.client = client
    store.set_offline(False)
    status = engine.sync_once()
    assert status.status in {STATUS_SYNCED, STATUS_PENDING}
    assert status.status == STATUS_SYNCED or engine.sync_once().status == STATUS_SYNCED
    engine.stop()


def test_progress_http_rejects_spoofed_user_id(staging):
    import urllib.request

    event = {
        "event_id": "evt-spoof",
        "device_id": "dev",
        "language_code": "nl",
        "vocab_id": VOCAB,
        "verdict": "exact",
        "mastered": 1,
        "hint_used": 0,
        "occurred_at": "2026-11-19T12:00:00+00:00",
        "algorithm_id": "ladder-v2",
        "word_snapshot": "huis",
        "user_answer": "house",
        "expected_answer": "house",
        "prompt": "?",
    }
    # Seed vocab for alice first via client
    store = AccountLocalStore(staging["user_a"], data_root=str(staging["tmp"] / "spoof"))
    eng = _engine(store, staging["base"], staging["token_a"])
    store.upsert_vocabulary(language_code="nl", vocab_id=VOCAB, payload=_payload())
    eng.sync_once()

    body = json.dumps({"event": event, "user_id": staging["user_b"]}).encode("utf-8")
    req = urllib.request.Request(
        staging["base"] + "/api/sync/progress/accept",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + staging["token_a"],
        },
    )
    with urllib.request.urlopen(req, timeout=5) as response:
        payload = json.loads(response.read().decode("utf-8"))
    assert payload["event"]["event_id"] == "evt-spoof"
    conn = sqlite3.connect(str(staging["server_dir"] / "study_sync.db"))
    owner = conn.execute(
        "SELECT user_id FROM learning_attempts WHERE event_id = ?",
        ("evt-spoof",),
    ).fetchone()[0]
    conn.close()
    assert owner == staging["user_a"]
    eng.stop()
