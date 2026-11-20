"""FreeHome must refresh Cloud Sync labels after Sync 404 → unavailable."""

from __future__ import annotations

import tkinter as tk

import pytest

import account_session
from account_local_store import STATUS_PENDING, STATUS_UNAVAILABLE, AccountLocalStore
from account_panel import AccountPanel, AccountSyncStatusPoller
from account_sync_client import SyncClientError
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
        base = int(record.get("expected_revision") or 0)
        record["revision"] = base + 1
        record.setdefault("deleted", False)
        record.setdefault("payload", body.get("payload") or {})
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


@pytest.fixture
def tk_root():
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"Tk/Tcl unavailable: {exc}")
    root.withdraw()
    yield root
    try:
        root.destroy()
    except tk.TclError:
        pass


def _pump(root: tk.Tk, ms: int = 50) -> None:
    root.update()
    root.after(ms, root.quit)
    root.mainloop()


def test_poller_pending_then_unavailable_after_worker_404(tk_root, tmp_path, monkeypatch):
    store = AccountLocalStore(11, data_root=str(tmp_path))
    store.upsert_vocabulary(
        language_code="nl",
        vocab_id=new_vocab_id(),
        payload={"word": "huis", "meaning": "house"},
    )
    assert store.status().status == STATUS_PENDING

    panel = AccountPanel(tk_root, allow_logout=True)
    client = _FakeClient(error=SyncClientError("disabled", status=404))
    engine = AccountSyncEngine(store, client, poll_seconds=60.0)

    monkeypatch.setattr(account_session, "is_signed_in", lambda: True)
    monkeypatch.setattr(
        account_session, "account_display_name", lambda: "tester"
    )
    monkeypatch.setattr(
        account_session.config,
        "environment_identity",
        lambda: type(
            "I",
            (),
            {
                "runtime_environment": "production-rc",
                "rc_smoke": True,
                "network_writes_allowed": True,
                "identity_error": "",
            },
        )(),
    )
    monkeypatch.setattr(
        "account_sync_engine.active_engine",
        lambda: engine,
    )

    panel.refresh()
    assert "Pending" in panel.sync_label.cget("text")

    # Synthetic worker records Sync 404 → unavailable (no production network).
    engine.sync_once()
    assert store.server_sync_unavailable() is True
    assert store.status().status == STATUS_UNAVAILABLE

    poller = AccountSyncStatusPoller(
        tk_root, panel, initial_delay_ms=20, interval_ms=250
    )
    poller.start()
    _pump(tk_root, 80)
    text = panel.sync_label.cget("text")
    assert "unavailable" in text.lower()
    assert "Pending" not in text
    assert "Synced" not in text
    calls_before = client.calls
    _pump(tk_root, 300)
    # UI-only refresh must not trigger Sync HTTP.
    assert client.calls == calls_before
    poller.stop()
    store.close()


def test_poller_restart_does_not_duplicate_loops(tk_root):
    panel = AccountPanel(tk_root, allow_logout=True)
    refreshes = {"n": 0}
    original = panel.refresh

    def counting_refresh():
        refreshes["n"] += 1
        original()

    panel.refresh = counting_refresh  # type: ignore[method-assign]
    poller = AccountSyncStatusPoller(
        tk_root, panel, initial_delay_ms=10, interval_ms=40
    )
    poller.start()
    poller.start()  # replace loop; must not stack two schedulers
    _pump(tk_root, 120)
    first = refreshes["n"]
    assert first >= 1
    assert first <= 5
    poller.stop()
    after_stop = refreshes["n"]
    _pump(tk_root, 120)
    assert refreshes["n"] == after_stop


def test_poller_stops_on_destroy_and_account_switch_keeps_single_loop(
    tk_root, monkeypatch
):
    panel = AccountPanel(tk_root, allow_logout=True)
    poller = AccountSyncStatusPoller(
        tk_root, panel, initial_delay_ms=10, interval_ms=40
    )
    poller.start()
    assert poller.active
    # Account-switch style: refresh once without restarting a second poller.
    panel.refresh()
    assert poller._generation == 1
    poller.stop()
    assert not poller.active
    gen_after_stop = poller._generation
    _pump(tk_root, 80)
    assert poller._generation == gen_after_stop


def test_study_master_refresh_helper_still_reschedules(monkeypatch):
    """StudyMaster's existing after(5000) loop remains the refresh mechanism."""
    import main as main_mod

    scheduled = []

    class _Root:
        def after(self, ms, cb):
            scheduled.append((ms, cb))
            return f"job-{len(scheduled)}"

    class _Panel:
        def __init__(self):
            self.refreshed = 0

        def refresh(self):
            self.refreshed += 1

    class _Label:
        def __init__(self):
            self.text = ""

        def config(self, **kwargs):
            self.text = kwargs.get("text", self.text)

    app = main_mod.StudyMasterApp.__new__(main_mod.StudyMasterApp)
    app.root = _Root()
    app.sync_status_label = _Label()
    app.account_panel = _Panel()
    monkeypatch.setattr(
        app, "_cloud_sync_state", lambda: ("Pending", "Upload or download in progress")
    )
    app._refresh_sync_status()
    assert "Pending" in app.sync_status_label.text
    assert app.account_panel.refreshed == 1
    assert scheduled and scheduled[0][0] == 5000


def test_ui_refresh_does_not_call_sync_http(tk_root, tmp_path, monkeypatch):
    store = AccountLocalStore(12, data_root=str(tmp_path))
    client = _FakeClient(error=SyncClientError("disabled", status=404))
    engine = AccountSyncEngine(store, client, poll_seconds=60.0)
    engine.sync_once()
    calls = client.calls

    monkeypatch.setattr(account_session, "is_signed_in", lambda: True)
    monkeypatch.setattr(account_session, "account_display_name", lambda: "tester")
    monkeypatch.setattr(
        account_session.config,
        "environment_identity",
        lambda: type(
            "I",
            (),
            {
                "runtime_environment": "production-rc",
                "rc_smoke": True,
                "network_writes_allowed": True,
                "identity_error": "",
            },
        )(),
    )
    monkeypatch.setattr("account_sync_engine.active_engine", lambda: engine)

    panel = AccountPanel(tk_root)
    for _ in range(5):
        panel.refresh()
    assert client.calls == calls
    store.close()


def test_freehome_study_master_roundtrip_no_stale_root_destroy_or_poller(
    tk_root, monkeypatch
):
    """FreeHome → StudyMaster → FreeHome must not stack root Destroy handlers."""
    from home_app import FreeHome

    monkeypatch.setattr("home_app.plan_for_language", lambda _code: None)
    monkeypatch.setattr(
        "home_app.config.environment_identity",
        lambda: type(
            "I",
            (),
            {
                "display_title": lambda self, name: name,
                "runtime_environment": "production-rc",
                "rc_smoke": True,
            },
        )(),
    )

    class _DummyStudyMaster:
        def __init__(self, root, on_finished=None):
            self.root = root
            self.on_finished = on_finished

    monkeypatch.setattr(
        FreeHome, "_study_master_class", staticmethod(lambda: _DummyStudyMaster)
    )

    root_bind_calls = []
    real_bind = tk_root.bind

    def tracking_bind(sequence, func=None, add=None):
        if sequence == "<Destroy>":
            root_bind_calls.append((sequence, add))
        return real_bind(sequence, func, add)

    monkeypatch.setattr(tk_root, "bind", tracking_bind)

    homes = []
    for _ in range(3):
        home = FreeHome(tk_root)
        homes.append(home)
        assert home._sync_status_poller.active
        assert getattr(home, "_sync_panel_destroy_bind", None)
        # Account-switch style refresh must not start a second poll loop.
        before_gen = home._sync_status_poller._generation
        home._on_account_session_changed()
        assert home._sync_status_poller._generation == before_gen
        home._start_study()
        assert not home._sync_status_poller.active
        _pump(tk_root, 40)

    # Cleanup is bound to the panel frame, never stacked on the long-lived root.
    assert root_bind_calls == []
    # Exactly one live FreeHome poller after the last return (new FreeHome).
    final = FreeHome(tk_root)
    assert final._sync_status_poller.active
    assert final._sync_status_poller._generation == 1
    for prior in homes:
        assert not prior._sync_status_poller.active
    final._stop_sync_status_polling()
    assert not final._sync_status_poller.active
