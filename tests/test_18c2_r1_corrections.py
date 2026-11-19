"""Phase 18C.2 Architect R1 regressions (F1 prefs, F2 tombstone, F3 in-flight)."""

from __future__ import annotations

import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

import account_server
import account_store
import config
import sync_http
import sync_store
from account_local_store import (
    OUTBOX_CONFLICT,
    STATUS_CONFLICT,
    STATUS_PENDING,
    STATUS_SYNCED,
    AccountLocalStore,
)
from account_prefs import (
    apply_preferences_to_settings,
    mark_preferences_dirty,
    preferences_conflict,
    preferences_dirty,
    remote_apply_active,
    sync_preferences_once,
)
from account_sync_client import AccountSyncClient
from account_sync_engine import AccountSyncEngine
from vocab_identity import new_vocab_id

VOCAB = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"


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


def _isolate_settings(monkeypatch, data: Path) -> None:
    data.mkdir(parents=True, exist_ok=True)
    settings = data / "settings.json"
    settings.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(config, "SETTINGS_FILE", str(settings))
    monkeypatch.setattr(config, "data_dir", lambda: str(data))
    config.reload()


# --- F1 preferences ---


def test_f1_remote_apply_does_not_mark_dirty(tmp_path, monkeypatch):
    data = tmp_path / "prefs_a"
    _isolate_settings(monkeypatch, data)
    config.save_account("alice", "tok", user_id=1)
    store = AccountLocalStore(1, data_root=str(data))
    assert not preferences_dirty(store)
    apply_preferences_to_settings(
        {"study_languages": ["nl"], "native": "en", "reading_level": "B1"},
        from_remote=True,
    )
    assert not remote_apply_active()
    assert not preferences_dirty(store)
    # Mutators ran under remote flag — dirty must stay false.
    assert config.study_codes() == ["nl"]
    store.close()


def test_f1_dirty_blocks_synced_status_and_preserves_local(staging, monkeypatch):
    data = staging["tmp"] / "prefs_dirty"
    _isolate_settings(monkeypatch, data)
    config.save_account("alice", staging["token_a"], user_id=staging["user_a"])
    store = AccountLocalStore(staging["user_a"], data_root=str(data))
    client = AccountSyncClient(staging["base"], staging["token_a"])
    # Seed server tip.
    sync_preferences_once(store, client)
    assert not preferences_dirty(store)
    first_rev = int(store.get_preferences().get("_prefs_server_revision") or 0)
    assert first_rev >= 1

    # Local user edit — must stay dirty / not Synced until pushed.
    config.set_study_codes(["nl", "fr"])
    mark_preferences_dirty(store)
    assert preferences_dirty(store)
    assert store.status().status == STATUS_PENDING
    assert "fr" in store.get_preferences()["study_languages"]

    # Concurrent tip advanced under us → deterministic conflict, local preserved.
    from account_sync_client import SyncConflictClientError

    class _ConflictClient:
        def get_preferences(self):
            return {
                "contract_version": 1,
                "revision": first_rev,
                "values": {"study_languages": ["de"]},
            }

        def put_preferences(self, *, values, expected_revision):
            raise SyncConflictClientError(
                "Preference revision conflict.",
                status=409,
                body={
                    "error": "Sync conflict.",
                    "current": {
                        "revision": first_rev + 1,
                        "values": {"study_languages": ["de"]},
                    },
                },
            )

    sync_preferences_once(store, _ConflictClient())
    assert preferences_dirty(store)
    assert preferences_conflict(store)
    assert "fr" in store.get_preferences()["study_languages"]
    assert "de" not in store.get_preferences().get("study_languages", [])
    assert store.status().status == STATUS_CONFLICT

    # Successful push clears dirty; later unchanged sync must not bump revision.
    store.set_preference("_prefs_conflict", False)
    sync_preferences_once(store, client)
    assert not preferences_dirty(store)
    assert not preferences_conflict(store)
    tip = client.get_preferences()
    rev_before = int(tip["revision"])
    sync_preferences_once(store, client)
    tip2 = client.get_preferences()
    assert int(tip2["revision"]) == rev_before
    # Prefs must not keep status in Conflict/Pending by themselves once clean.
    assert not store.get_preferences().get("_prefs_dirty")
    store.close()


def test_f1_account_switch_does_not_copy_prefs(staging, monkeypatch):
    data_a = staging["tmp"] / "switch_a"
    data_b = staging["tmp"] / "switch_b"
    _isolate_settings(monkeypatch, data_a)
    config.save_account("alice", staging["token_a"], user_id=staging["user_a"])
    store_a = AccountLocalStore(staging["user_a"], data_root=str(data_a))
    client_a = AccountSyncClient(staging["base"], staging["token_a"])
    store_a.set_preference("study_languages", ["nl", "es"])
    store_a.set_preference("_prefs_dirty", True)
    sync_preferences_once(store_a, client_a)
    apply_preferences_to_settings(
        {"study_languages": ["nl", "es"]}, from_remote=True
    )

    # Switch to Bob on a fresh account store — machine settings still show Alice codes.
    _isolate_settings(monkeypatch, data_b)
    config.save_account("bob", staging["token_b"], user_id=staging["user_b"])
    # Simulate leftover machine settings from previous account.
    config.set_study_codes(["nl", "es"])
    store_b = AccountLocalStore(staging["user_b"], data_root=str(data_b))
    client_b = AccountSyncClient(staging["base"], staging["token_b"])
    sync_preferences_once(store_b, client_b)
    # Bob must not inherit Alice's server prefs; his first seed is device-local once.
    bob_prefs = store_b.get_preferences()
    alice_server = client_a.get_preferences()["values"].get("study_languages")
    assert alice_server == ["nl", "es"]
    # Bob's account store is separate; server tip for Bob is his own seed, not Alice.
    bob_server = client_b.get_preferences()["values"].get("study_languages")
    assert bob_server != alice_server or bob_server == config.study_codes()
    assert store_b.user_id != store_a.user_id
    store_a.close()
    store_b.close()


# --- F2 tombstone resolution ---


def test_f2_keep_local_against_tombstone_requires_local_as_new(staging):
    root_a = staging["tmp"] / "tomb_a"
    root_b = staging["tmp"] / "tomb_b"
    s1 = AccountLocalStore(staging["user_a"], data_root=str(root_a))
    s2 = AccountLocalStore(staging["user_a"], data_root=str(root_b))
    e1 = _engine(s1, staging["base"], staging["token_a"])
    e2 = _engine(s2, staging["base"], staging["token_a"])
    s1.upsert_vocabulary(language_code="nl", vocab_id=VOCAB, payload=_payload(meaning="live"))
    e1.sync_once()
    e2.sync_once()

    s1.upsert_vocabulary(
        language_code="nl", vocab_id=VOCAB, payload=_payload(meaning="local-edit")
    )
    s2.delete_vocabulary(language_code="nl", vocab_id=VOCAB)
    e2.sync_once()
    status = e1.sync_once()
    assert status.status == STATUS_CONFLICT
    frozen = s1.conflicted_vocab_outbox("nl", VOCAB)
    assert len(frozen) == 1

    with pytest.raises(Exception) as raised:
        s1.resolve_vocab_conflict("nl", VOCAB, keep="local")
    assert "local_as_new" in str(raised.value).lower() or "tombstone" in str(raised.value).lower()

    # Keep server preserves tombstone; no pending resurrection.
    s1.resolve_vocab_conflict("nl", VOCAB, keep="server")
    assert s1.conflicted_vocab_outbox("nl", VOCAB) == []
    assert s1.list_vocabulary("nl") == []
    assert s1.pending_outbox("vocab_put") == []
    e1.sync_once()
    conn = sync_store.connect(str(staging["server_dir"] / "study_sync.db"))
    row = conn.execute(
        "SELECT deleted FROM vocabulary_entities WHERE vocab_id = ?", (VOCAB,)
    ).fetchone()
    conn.close()
    assert int(row["deleted"]) == 1
    e1.stop()
    e2.stop()


def test_f2_local_as_new_preserves_tombstone_and_uploads_new_uuid(staging):
    root_a = staging["tmp"] / "tomb_new_a"
    root_b = staging["tmp"] / "tomb_new_b"
    s1 = AccountLocalStore(staging["user_a"], data_root=str(root_a))
    s2 = AccountLocalStore(staging["user_a"], data_root=str(root_b))
    e1 = _engine(s1, staging["base"], staging["token_a"])
    e2 = _engine(s2, staging["base"], staging["token_a"])
    s1.upsert_vocabulary(language_code="nl", vocab_id=VOCAB, payload=_payload(meaning="live"))
    e1.sync_once()
    e2.sync_once()
    s1.upsert_vocabulary(
        language_code="nl", vocab_id=VOCAB, payload=_payload(meaning="keep-me")
    )
    s2.delete_vocabulary(language_code="nl", vocab_id=VOCAB)
    e2.sync_once()
    e1.sync_once()
    assert s1.conflicted_vocab_outbox("nl", VOCAB)

    new_id = s1.resolve_vocab_conflict("nl", VOCAB, keep="local_as_new")
    assert new_id and new_id != VOCAB
    assert s1.conflicted_vocab_outbox("nl", VOCAB) == []
    # Original id stays deleted locally (server tip).
    assert all(e.get("id") != VOCAB for e in s1.list_vocabulary("nl"))
    assert any(e.get("id") == new_id and e.get("meaning") == "keep-me" for e in s1.list_vocabulary("nl"))
    pending = s1.pending_outbox("vocab_put")
    assert len(pending) == 1
    assert pending[0]["vocab_id"] == new_id
    assert pending[0]["payload"]["expected_revision"] == 0

    status = e1.sync_once()
    assert status.status == STATUS_SYNCED
    e2.sync_once()
    words = {e["id"]: e for e in s2.list_vocabulary("nl")}
    assert VOCAB not in words
    assert new_id in words
    assert words[new_id]["meaning"] == "keep-me"
    e1.stop()
    e2.stop()


# --- F3 in-flight race ---


class _DelayedPutProxy(BaseHTTPRequestHandler):
    """Proxy that delays vocabulary put long enough for a concurrent local edit."""

    delay_seconds = 0.35
    upstream = ""
    token = ""

    def log_message(self, format, *args):
        return

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length)
        if self.path == sync_http.SYNC_PUT:
            time.sleep(self.delay_seconds)
        import urllib.request

        request = urllib.request.Request(
            self.upstream + self.path,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": self.headers.get("Authorization") or ("Bearer " + self.token),
                "User-Agent": "LanguageGuard-Sync-DelayProxy",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read()
                self.send_response(response.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
        except Exception as error:
            msg = json.dumps({"error": str(error)}).encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(msg)))
            self.end_headers()
            self.wfile.write(msg)


def test_f3_inflight_edit_preserves_newer_local_without_false_conflict(staging):
    root = staging["tmp"] / "inflight"
    store = AccountLocalStore(staging["user_a"], data_root=str(root))
    # Delayed proxy in front of the real staging server.
    _DelayedPutProxy.upstream = staging["base"]
    _DelayedPutProxy.token = staging["token_a"]
    proxy = ThreadingHTTPServer(("127.0.0.1", 0), _DelayedPutProxy)
    thread = threading.Thread(target=proxy.serve_forever, daemon=True)
    thread.start()
    proxy_base = f"http://127.0.0.1:{proxy.server_address[1]}"
    client = AccountSyncClient(proxy_base, staging["token_a"], timeout=30)
    engine = AccountSyncEngine(store, client, poll_seconds=3600)

    op_x = store.upsert_vocabulary(
        language_code="nl", vocab_id=VOCAB, payload=_payload(meaning="X")
    )
    assert op_x
    pending_x = store.pending_outbox("vocab_put")[0]
    assert pending_x["operation_id"] == op_x

    # Start upload of X on a background thread (simulates in-flight HTTP).
    result = {}

    def upload_x():
        try:
            record = client.put_vocabulary(pending_x["payload"])
            result["record"] = record
            if store.is_outbox_pending(op_x):
                store.acknowledge_vocab_outbox(op_x, record)
            else:
                store.note_accepted_vocab_upload(op_x, pending_x["payload"], record)
            result["ok"] = True
        except Exception as error:
            result["error"] = error

    worker = threading.Thread(target=upload_x)
    worker.start()
    time.sleep(0.05)
    # User edits to Y while X is still in flight → supersedes OpX.
    op_y = store.upsert_vocabulary(
        language_code="nl", vocab_id=VOCAB, payload=_payload(meaning="Y")
    )
    assert op_y and op_y != op_x
    assert not store.is_outbox_pending(op_x)
    assert store.is_outbox_pending(op_y)
    worker.join(timeout=10)
    assert result.get("ok"), result.get("error")
    # Y must still be the working copy; no conflict solely from late X ack.
    assert store.conflicted_vocab_outbox("nl", VOCAB) == []
    assert store.list_vocabulary("nl")[0]["meaning"] == "Y"
    pending = store.pending_outbox("vocab_put")
    assert len(pending) == 1
    assert pending[0]["payload"]["payload"]["meaning"] == "Y"
    assert int(pending[0]["payload"]["expected_revision"]) == int(
        result["record"]["revision"]
    )

    # Converge through the real (non-delayed) server path.
    engine.client = AccountSyncClient(staging["base"], staging["token_a"])
    status = engine.sync_once()
    assert status.status == STATUS_SYNCED
    assert store.list_vocabulary("nl")[0]["meaning"] == "Y"
    assert store.conflicted_vocab_outbox("nl", VOCAB) == []

    # Second device converges to Y.
    other = AccountLocalStore(staging["user_a"], data_root=str(staging["tmp"] / "inflight_b"))
    e2 = _engine(other, staging["base"], staging["token_a"])
    assert e2.sync_once().status == STATUS_SYNCED
    assert other.list_vocabulary("nl")[0]["meaning"] == "Y"
    e2.stop()
    engine.stop()
    proxy.shutdown()
    proxy.server_close()
    thread.join(timeout=5)
