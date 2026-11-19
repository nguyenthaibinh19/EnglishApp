"""Server Sync 404 must not look like Pending/Synced; session lifecycle is safe."""

from __future__ import annotations

import time

import pytest

import account_session
import app_environment
from account_local_store import (
    STATUS_OFFLINE,
    STATUS_PENDING,
    STATUS_UNAVAILABLE,
    AccountLocalStore,
)
from account_sync_client import SyncClientError, SyncConflictClientError, SyncOfflineError
from account_sync_engine import AccountSyncEngine
from vocab_identity import new_vocab_id


class _FakeClient:
    def __init__(self, *, error: Exception | None = None):
        self.error = error
        self.calls = 0

    def vocabulary_changes(self, **_kwargs):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return {"changes": [], "next_cursor": 0, "has_more": False}

    def put_vocabulary(self, body):
        self.calls += 1
        if self.error is not None:
            raise self.error
        record = dict(body)
        base = int(record.get("expected_revision") or record.get("revision") or 0)
        record["revision"] = base + 1
        record.setdefault("deleted", False)
        if "payload" not in record:
            record["payload"] = {
                k: v
                for k, v in body.items()
                if k
                not in {
                    "language_code",
                    "vocab_id",
                    "revision",
                    "expected_revision",
                    "deleted",
                    "payload",
                }
            }
        return record

    def delete_vocabulary(self, body):
        return self.put_vocabulary(body)

    def accept_progress(self, event):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return {"event": event, "progress_after": {}}

    def progress_changes(self, **_kwargs):
        return {"changes": [], "next_cursor": 0, "has_more": False}

    def get_preferences(self):
        return {"values": {}, "revision": 0}

    def put_preferences(self, **_kwargs):
        return {"values": {}, "revision": 1}


def _wait_until(predicate, *, timeout: float = 5.0, interval: float = 0.02) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(interval)
    raise AssertionError(f"condition not met within {timeout}s")


@pytest.fixture
def store(tmp_path):
    s = AccountLocalStore(7, data_root=str(tmp_path))
    yield s
    try:
        s.close()
    except Exception:
        pass


def test_404_marks_server_sync_unavailable_keeps_outbox(store):
    store.upsert_vocabulary(
        language_code="nl",
        vocab_id=new_vocab_id(),
        payload={"word": "huis", "meaning": "house"},
    )
    pending_before = store.status().pending_vocab
    assert pending_before >= 1

    client = _FakeClient(error=SyncClientError("disabled", status=404))
    engine = AccountSyncEngine(store, client, poll_seconds=60.0)
    snap = engine.sync_once()

    assert snap.status == STATUS_UNAVAILABLE
    assert "not uploaded" in snap.detail.lower() or "locally" in snap.detail.lower()
    assert store.server_sync_unavailable() is True
    assert store.status().pending_vocab == pending_before
    assert snap.status != "Synced"
    assert snap.status != STATUS_PENDING


def test_unavailable_ui_label_not_pending_or_synced(store, monkeypatch):
    store.upsert_vocabulary(
        language_code="nl",
        vocab_id=new_vocab_id(),
        payload={"word": "fiets", "meaning": "bike"},
    )
    client = _FakeClient(error=SyncClientError("disabled", status=404))
    engine = AccountSyncEngine(store, client, poll_seconds=60.0)
    engine.sync_once()

    monkeypatch.setattr(account_session, "is_signed_in", lambda: True)
    monkeypatch.setattr(
        account_session.config,
        "environment_identity",
        lambda: type(
            "I",
            (),
            {"network_writes_allowed": True, "identity_error": ""},
        )(),
    )
    monkeypatch.setattr(
        "account_sync_engine.active_engine",
        lambda: engine,
    )
    label, detail = account_session.describe_cloud_sync()
    assert "unavailable" in label.lower()
    assert "pending" not in label.lower()
    assert "synced" not in label.lower()
    assert "not uploaded" in detail.lower() or "locally" in detail.lower()


def test_worker_loop_404_suspends_then_new_session_probes_once(tmp_path):
    """Controlled worker-loop: no 404 retry storm; new engine may probe once."""
    data_root = str(tmp_path)
    store = AccountLocalStore(7, data_root=data_root)
    store.upsert_vocabulary(
        language_code="nl",
        vocab_id=new_vocab_id(),
        payload={"word": "boek", "meaning": "book"},
    )
    pending_before = store.status().pending_vocab
    assert pending_before >= 1

    client = _FakeClient(error=SyncClientError("disabled", status=404))
    engine = AccountSyncEngine(store, client, poll_seconds=0.1)
    engine.start()
    try:
        _wait_until(lambda: store.server_sync_unavailable() and client.calls >= 1)
        calls_after_404 = client.calls
        assert store.status().status == STATUS_UNAVAILABLE
        assert store.status().pending_vocab == pending_before

        # Ordinary local notifications must not re-hit Sync HTTP this session.
        for _ in range(8):
            engine.notify()
            time.sleep(0.05)
        time.sleep(0.35)
        assert client.calls == calls_after_404
        assert store.server_sync_unavailable() is True
        assert store.status().pending_vocab == pending_before
    finally:
        engine.stop()

    # New engine/session with the same account store: one fresh capability attempt.
    store2 = AccountLocalStore(7, data_root=data_root)
    assert store2.status().pending_vocab == pending_before
    # Prior session left unavailable=1; new engine must clear for a probe.
    assert store2.server_sync_unavailable() is True
    client2 = _FakeClient(error=SyncClientError("disabled", status=404))
    engine2 = AccountSyncEngine(store2, client2, poll_seconds=0.1)
    assert store2.server_sync_unavailable() is False
    engine2.start()
    try:
        _wait_until(lambda: store2.server_sync_unavailable() and client2.calls >= 1)
        calls2 = client2.calls
        time.sleep(0.35)
        for _ in range(5):
            engine2.notify()
            time.sleep(0.05)
        time.sleep(0.2)
        assert client2.calls == calls2
        assert store2.status().status == STATUS_UNAVAILABLE
        assert store2.status().pending_vocab == pending_before
    finally:
        engine2.stop()

    # New session where mocked Sync succeeds: clear unavailable; outbox can progress.
    store3 = AccountLocalStore(7, data_root=data_root)
    assert store3.status().pending_vocab == pending_before
    client3 = _FakeClient(error=None)
    engine3 = AccountSyncEngine(store3, client3, poll_seconds=0.1)
    engine3.start()
    try:
        _wait_until(
            lambda: (not store3.server_sync_unavailable())
            and client3.calls >= 1
            and store3.status().pending_vocab == 0
        )
        assert store3.server_sync_unavailable() is False
        snap = store3.status()
        assert snap.status != STATUS_UNAVAILABLE
        assert snap.pending_vocab == 0
        # Synced only when catch-up is confirmed — never invent it on 404.
        if snap.status == "Synced":
            assert snap.vocab_caught_up and snap.progress_caught_up
    finally:
        engine3.stop()


def test_new_engine_clears_persisted_unavailable_for_probe(store):
    store.set_server_sync_unavailable(True)
    client = _FakeClient(error=SyncClientError("disabled", status=404))
    engine = AccountSyncEngine(store, client, poll_seconds=60.0)
    assert store.server_sync_unavailable() is False
    snap = engine.sync_once()
    assert snap.status == STATUS_UNAVAILABLE
    assert store.server_sync_unavailable() is True


def test_offline_and_auth_remain_distinct(store):
    offline_client = _FakeClient(error=SyncOfflineError("down", status=None))
    engine = AccountSyncEngine(store, offline_client, poll_seconds=60.0)
    snap = engine.sync_once()
    assert snap.status == STATUS_OFFLINE
    assert store.server_sync_unavailable() is False

    store.set_offline(False)
    auth_client = _FakeClient(error=SyncClientError("auth", status=401))
    engine = AccountSyncEngine(store, auth_client, poll_seconds=60.0)
    snap = engine.sync_once()
    assert snap.status != STATUS_UNAVAILABLE
    assert snap.conflict or "conflict" in snap.status.lower() or snap.status != STATUS_PENDING


def test_conflict_409_not_treated_as_unavailable(store):
    client = _FakeClient(
        error=SyncConflictClientError("conflict", status=409, body={"error": "x"})
    )
    engine = AccountSyncEngine(store, client, poll_seconds=60.0)
    snap = engine.sync_once()
    assert store.server_sync_unavailable() is False
    assert snap.status != STATUS_UNAVAILABLE


def test_cloud_sync_ui_state_unavailable_mapping():
    label, detail = app_environment.cloud_sync_ui_state(
        signed_in=True,
        engine_running=True,
        engine_status="Unavailable",
        engine_detail="Data saved locally; not uploaded",
    )
    assert label == "Server Sync unavailable"
    assert "not uploaded" in detail.lower()


def test_successful_cycle_clears_unavailable(store):
    client = _FakeClient(error=None)
    engine = AccountSyncEngine(store, client, poll_seconds=60.0)
    store.set_server_sync_unavailable(True)
    snap = engine.sync_once()
    assert store.server_sync_unavailable() is False
    assert snap.status != STATUS_UNAVAILABLE
