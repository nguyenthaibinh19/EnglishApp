"""Two-profile Account UX scenarios against a synthetic localhost backend.

Scenario A = account isolation (A then B). Scenario B = same-account sync
across two data roots. Does not contact production or enable VPS sync.
"""

from __future__ import annotations

import json
import os
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

import account_session
import account_store
import config
from account_local_store import AccountLocalStore
from account_sync_client import AccountSyncClient
from account_sync_engine import AccountSyncEngine, stop_active
from vocab_identity import new_vocab_id


def _free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


@pytest.fixture
def sync_lab(tmp_path, monkeypatch):
    """Localhost account+sync server with STUDY_SYNC_ENABLED=1 (lab only)."""
    import account_server
    import sync_http

    server_dir = tmp_path / "server"
    server_dir.mkdir()
    sync_dir = server_dir / "sync"
    sync_dir.mkdir()

    monkeypatch.setenv("STUDY_SYNC_ENABLED", "1")
    monkeypatch.setenv("STUDY_SYNC_DIR", str(sync_dir))
    monkeypatch.setenv("LG_APP_ENVIRONMENT", "development")
    monkeypatch.setattr(config, "SETTINGS_FILE", str(tmp_path / "unused-settings.json"))

    original_db_path = account_store.db_path

    def lab_db_path(folder=None):
        root = folder or str(server_dir)
        return os.path.join(root, account_store.DB_FILE)

    monkeypatch.setattr(account_store, "db_path", lab_db_path)
    account_store.add_user("alice", "alicepass")
    account_store.add_user("bob", "bobpass")
    token_alice = account_store.login("alice", "alicepass")
    token_bob = account_store.login("bob", "bobpass")
    alice_id = int(account_store.user_for_token(token_alice)["id"])
    bob_id = int(account_store.user_for_token(token_bob)["id"])

    port = _free_port()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), account_server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    monkeypatch.setattr(config, "ACCOUNT_SERVER_URL", base)

    device1 = tmp_path / "device1"
    device2 = tmp_path / "device2"
    device1.mkdir()
    device2.mkdir()

    yield {
        "base": base,
        "accounts_dir": str(server_dir),
        "alice_id": alice_id,
        "bob_id": bob_id,
        "device1": str(device1),
        "device2": str(device2),
    }
    httpd.shutdown()
    httpd.server_close()
    stop_active()
    monkeypatch.setattr(account_store, "db_path", original_db_path)


def _login_settings(path: Path, username: str, token: str, user_id: int):
    path.write_text(
        json.dumps(
            {
                "account_username": username,
                "account_token": token,
                "account_user_id": user_id,
                "environment": "development",
                "language": "nl",
                "native": "en",
                "study_languages": ["nl"],
            }
        ),
        encoding="utf-8",
    )


def test_scenario_a_account_isolation_no_leakage(sync_lab, monkeypatch):
    """Scenario A: switch A → B hides A's private vocab; A restored on return."""
    import account_client

    base = sync_lab["base"]
    device = Path(sync_lab["device1"])
    monkeypatch.setenv("LG_DATA_DIR", str(device))
    config.SETTINGS_FILE = str(device / "settings.json")

    token_a = account_store.login("alice", "alicepass")
    _login_settings(device / "settings.json", "alice", token_a, sync_lab["alice_id"])
    config.reload()
    monkeypatch.setattr(config, "ACCOUNT_TOKEN", token_a)
    monkeypatch.setattr(config, "account_token", lambda: token_a)
    monkeypatch.setattr(config, "account_user_id", lambda: sync_lab["alice_id"])

    store_a = AccountLocalStore(sync_lab["alice_id"], data_root=str(device))
    vid = new_vocab_id()
    store_a.upsert_vocabulary(
        language_code="nl",
        vocab_id=vid,
        payload={"word": "appel", "meaning": "apple"},
    )
    words_a = {e.get("word") for e in store_a.list_vocabulary("nl")}
    assert "appel" in words_a
    store_a.close()

    # Switch to Bob — stop engine, clear session, bind Bob store.
    stop_active()
    token_b = account_store.login("bob", "bobpass")
    _login_settings(device / "settings.json", "bob", token_b, sync_lab["bob_id"])
    config.reload()
    monkeypatch.setattr(config, "ACCOUNT_TOKEN", token_b)
    monkeypatch.setattr(config, "account_token", lambda: token_b)
    monkeypatch.setattr(config, "account_user_id", lambda: sync_lab["bob_id"])

    store_b = AccountLocalStore(sync_lab["bob_id"], data_root=str(device))
    words_b = {e.get("word") for e in store_b.list_vocabulary("nl")}
    assert "appel" not in words_b
    store_b.upsert_vocabulary(
        language_code="nl",
        vocab_id=new_vocab_id(),
        payload={"word": "boom", "meaning": "tree"},
    )
    store_b.close()

    # Back to Alice — local state preserved (logout never deletes account DB).
    stop_active()
    _login_settings(device / "settings.json", "alice", token_a, sync_lab["alice_id"])
    monkeypatch.setattr(config, "ACCOUNT_TOKEN", token_a)
    monkeypatch.setattr(config, "account_token", lambda: token_a)
    monkeypatch.setattr(config, "account_user_id", lambda: sync_lab["alice_id"])
    store_a2 = AccountLocalStore(sync_lab["alice_id"], data_root=str(device))
    words_a2 = {e.get("word") for e in store_a2.list_vocabulary("nl")}
    assert "appel" in words_a2
    assert "boom" not in words_a2
    store_a2.close()
    # Alice DB and Bob DB are separate paths under accounts/{id}/
    assert (device / "accounts" / str(sync_lab["alice_id"])).is_dir()
    assert (device / "accounts" / str(sync_lab["bob_id"])).is_dir()


def test_scenario_b_same_account_sync_two_devices(sync_lab, monkeypatch):
    """Scenario B: Alice on device1 uploads; device2 downloads the same tip."""
    device1 = Path(sync_lab["device1"])
    device2 = Path(sync_lab["device2"])
    token = account_store.login("alice", "alicepass")
    alice_id = sync_lab["alice_id"]
    base = sync_lab["base"]

    store1 = AccountLocalStore(alice_id, data_root=str(device1))
    client1 = AccountSyncClient(base, token)
    engine1 = AccountSyncEngine(store1, client1, poll_seconds=60.0)
    vid = new_vocab_id()
    store1.upsert_vocabulary(
        language_code="nl",
        vocab_id=vid,
        payload={"word": "huis", "meaning": "house"},
    )
    snap1 = engine1.sync_once()
    assert snap1.pending_vocab == 0 or snap1.vocab_caught_up or snap1.status in {
        "synced",
        "pending",
        "offline",
    }
    # Force push cycle until empty or conflict
    for _ in range(5):
        snap1 = engine1.sync_once()
        if snap1.pending_vocab == 0 and not snap1.conflict:
            break
    assert snap1.pending_vocab == 0, snap1
    engine1.stop()

    store2 = AccountLocalStore(alice_id, data_root=str(device2))
    client2 = AccountSyncClient(base, token)
    engine2 = AccountSyncEngine(store2, client2, poll_seconds=60.0)
    snap2 = engine2.sync_once()
    words2 = {e.get("word") for e in store2.list_vocabulary("nl")}
    assert "huis" in words2
    # No duplicate ids
    ids = [e.get("id") for e in store2.list_vocabulary("nl")]
    assert ids.count(vid) == 1
    engine2.stop()

    # Offline write on device2 then converge
    store2 = AccountLocalStore(alice_id, data_root=str(device2))
    client2 = AccountSyncClient(base, token)
    engine2 = AccountSyncEngine(store2, client2, poll_seconds=60.0)
    vid2 = new_vocab_id()
    store2.upsert_vocabulary(
        language_code="nl",
        vocab_id=vid2,
        payload={"word": "fiets", "meaning": "bike"},
    )
    for _ in range(5):
        snap = engine2.sync_once()
        if snap.pending_vocab == 0 and not snap.conflict:
            break
    engine2.stop()

    store1 = AccountLocalStore(alice_id, data_root=str(device1))
    engine1 = AccountSyncEngine(store1, AccountSyncClient(base, token), poll_seconds=60.0)
    engine1.sync_once()
    words1 = {e.get("word") for e in store1.list_vocabulary("nl")}
    assert "fiets" in words1
    engine1.stop()


def test_logout_keeps_local_account_db(sync_lab, monkeypatch):
    device = Path(sync_lab["device1"])
    monkeypatch.setenv("LG_DATA_DIR", str(device))
    token = account_store.login("alice", "alicepass")
    _login_settings(device / "settings.json", "alice", token, sync_lab["alice_id"])
    monkeypatch.setattr(config, "SETTINGS_FILE", str(device / "settings.json"))
    config.reload()
    monkeypatch.setattr(config, "ACCOUNT_TOKEN", token)
    monkeypatch.setattr(config, "account_token", lambda: token)
    monkeypatch.setattr(config, "account_user_id", lambda: sync_lab["alice_id"])

    store = AccountLocalStore(sync_lab["alice_id"], data_root=str(device))
    store.upsert_vocabulary(
        language_code="nl",
        vocab_id=new_vocab_id(),
        payload={"word": "keepme", "meaning": "keep"},
    )
    db = Path(store.path)
    store.close()
    assert db.is_file()
    account_session.logout_session()
    assert db.is_file()
    settings = json.loads((device / "settings.json").read_text(encoding="utf-8"))
    assert not settings.get("account_token")


def test_describe_cloud_sync_guest_and_signed_disabled(monkeypatch):
    monkeypatch.setattr(account_session, "is_signed_in", lambda: False)
    label, detail = account_session.describe_cloud_sync()
    assert "Guest" in label or "Disabled" in label
    assert "Synced" not in label

    monkeypatch.setattr(account_session, "is_signed_in", lambda: True)
    monkeypatch.setattr(config, "environment_identity", lambda: type("I", (), {
        "network_writes_allowed": True,
        "identity_error": "",
        "runtime_environment": "development",
    })())
    from account_sync_engine import stop_active

    stop_active()
    label, detail = account_session.describe_cloud_sync()
    assert "Server Sync disabled" in label or label == "Unavailable"
