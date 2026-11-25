"""Settings account panel follows the one poller. Conflict dialogs do not survive a switch."""

from __future__ import annotations

import tkinter as tk

import pytest


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


def test_visible_settings_panel_follows_poller_without_a_second_hook(tk_root, monkeypatch):
    from daily_study import DailyStudyPlan
    from home_app import FreeHome

    plan = DailyStudyPlan(
        language_code="nl",
        vocab_total=1,
        due_review_count=0,
        new_word_count=1,
        future_review_count=0,
        attention_word_count=0,
        planned_vocab_count=1,
        reading_enabled=False,
        listening_enabled=False,
    )
    monkeypatch.setattr("home_app.plan_for_language", lambda _code: plan)
    monkeypatch.setattr(
        "home_app.config.environment_identity",
        lambda: type("I", (), {"runtime_environment": "development", "rc_smoke": False})(),
    )
    state = {"signed_in": False, "name": "Ada", "sync": ("Guest / Disabled", "local")}
    monkeypatch.setattr(
        "account_panel.account_session.is_signed_in", lambda: state["signed_in"]
    )
    monkeypatch.setattr(
        "account_panel.account_session.account_display_name", lambda: state["name"]
    )
    monkeypatch.setattr(
        "account_panel.account_session.describe_cloud_sync",
        lambda: state["sync"],
    )
    monkeypatch.setattr(
        "account_panel.config.environment_identity",
        lambda: type("I", (), {"runtime_environment": "development", "rc_smoke": False})(),
    )

    home = FreeHome(tk_root)
    try:
        poller = home._sync_status_poller
        hooks = {"n": 0}
        original = home._apply_sync_status

        def counting(label, detail):
            hooks["n"] += 1
            assert hooks["n"] < 4
            original(label, detail)

        home.account_panel.on_refreshed = counting
        home._open_settings()
        visible = home._settings_account_panel
        assert visible is not home.account_panel
        assert visible.on_refreshed is None
        assert home._sync_status_poller is poller

        hooks["n"] = 0
        state["sync"] = ("Pending", "waiting")
        home.account_panel.refresh()
        assert hooks["n"] == 1
        assert "Pending" in visible.sync_label.cget("text")
        assert "Guest" in visible.status_label.cget("text")

        state["signed_in"] = True
        state["sync"] = ("Synced", "caught up")
        home.account_panel.refresh()
        assert hooks["n"] == 2
        assert "Ada" in visible.status_label.cget("text")
        assert "Synced" in visible.sync_label.cget("text")
        assert home._sync_status_poller is poller

        vocab = home._open_vocab_conflicts()
        prefs = home._open_prefs_conflicts()
        assert vocab.winfo_exists()
        assert prefs.winfo_exists()
        assert "Sync conflicts" in vocab.title() or "Xung đột đồng bộ" in vocab.title()
        assert "Preference conflict" in prefs.title() or "Xung đột tùy chọn" in prefs.title()
        home._on_account_session_changed()
        assert not vocab.winfo_exists()
        assert not prefs.winfo_exists()
        assert home._vocab_conflict_window is None
        assert home._prefs_conflict_window is None
        assert home._sync_status_poller is poller

        from prefs_conflict_app import PrefsConflictApp
        from sync_conflict_app import SyncConflictApp

        monkeypatch.setattr("study_data.is_signed_in", lambda: True)
        monkeypatch.setattr("study_data.active_account_store", lambda: None)
        monkeypatch.setattr("config.account_user_id", lambda: "account-b")
        vocab_choice = SyncConflictApp(tk.Toplevel(tk_root))
        vocab_choice._shown_account_key = "account-a"
        vocab_choice._resolve({"language_code": "nl", "vocab_id": "old"}, "local")
        assert vocab_choice._shown_account_key == "account-b"
        prefs_choice = PrefsConflictApp(tk.Toplevel(tk_root))
        prefs_choice._shown_account_key = "account-a"
        prefs_choice._resolve("local")
        assert prefs_choice._shown_account_key == "account-b"
    finally:
        home._stop_sync_status_polling()
