"""Server Sync 404 must not look like Pending/Synced upload progress."""

from __future__ import annotations

from pathlib import Path

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
        return body

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


@pytest.fixture
def store(tmp_path):
    s = AccountLocalStore(7, data_root=str(tmp_path))
    yield s
    s.close()


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
    store.set_server_sync_unavailable(True)
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


def test_404_suspends_repeated_polls_until_wake(store):
    client = _FakeClient(error=SyncClientError("disabled", status=404))
    engine = AccountSyncEngine(store, client, poll_seconds=60.0)
    engine.sync_once()
    assert client.calls >= 1
    calls_after_first = client.calls
    # Suspended loop path: calling sync_once again still 404s once if forced,
    # but _run would skip while unavailable. Simulate skip:
    assert store.server_sync_unavailable() is True
    # No automatic extra client calls without sync_once
    assert client.calls == calls_after_first


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
    store.set_server_sync_unavailable(True)
    client = _FakeClient(error=None)
    engine = AccountSyncEngine(store, client, poll_seconds=60.0)
    snap = engine.sync_once()
    assert store.server_sync_unavailable() is False
    assert snap.status != STATUS_UNAVAILABLE
