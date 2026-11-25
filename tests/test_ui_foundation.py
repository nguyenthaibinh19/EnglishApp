"""Presentation tokens and future exercise chrome. No SRS writes."""

from __future__ import annotations

import tkinter as tk

import pytest

import ui_foundation


@pytest.fixture
def tk_root():
    root = tk.Tk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except tk.TclError:
        pass


def test_today_nav_uses_real_plan(tk_root, monkeypatch):
    from daily_study import DailyStudyPlan
    from home_app import FreeHome

    plan = DailyStudyPlan(
        language_code="nl",
        vocab_total=4,
        due_review_count=1,
        new_word_count=3,
        future_review_count=0,
        attention_word_count=0,
        planned_vocab_count=4,
        reading_enabled=False,
        listening_enabled=False,
    )
    monkeypatch.setattr("home_app.plan_for_language", lambda _code: plan)
    monkeypatch.setattr(
        "home_app.config.environment_identity",
        lambda: type(
            "I",
            (),
            {
                "display_title": lambda self, name: name,
                "runtime_environment": "development",
                "rc_smoke": False,
            },
        )(),
    )
    home = FreeHome(tk_root)
    try:
        assert "4" in home.plan_headline.cget("text")
        assert "1" in home.plan_support.cget("text")
        assert "minute" not in home.plan_support.cget("text").lower()
        home._show_you()
        assert home.you_page.winfo_manager() == "pack"
        home._show_settings()
        assert home.settings_page.winfo_manager() == "pack"
        assert home.account_panel.frame.winfo_exists()
        home._show_today()
        assert home.today_page.winfo_manager() == "pack"
        assert home.start_button.cget("text")
        chosen = []
        row = ui_foundation.choice_row(tk_root, ("one", "two"), chosen.append)
        row.pack()
        row.winfo_children()[0].invoke()
        assert chosen == ["one"]
        extra = ui_foundation.expandable(tk_root, "Why?", "A short rule.")
        extra.pack()
        next(child for child in extra.winfo_children() if child.winfo_class() == "Button").invoke()
        body = next(child for child in extra.winfo_children() if child.winfo_class() == "Label")
        assert body.winfo_manager() == "pack"
    finally:
        home._stop_sync_status_polling()


def test_sync_status_kinds_cover_required_states():
    assert ui_foundation.sync_status_kind("Offline") == "offline"
    assert ui_foundation.sync_status_kind("Pending") == "pending"
    assert ui_foundation.sync_status_kind("Conflict / Action required") == "conflict"
    assert ui_foundation.sync_status_kind("Server Sync unavailable") == "error"
    assert ui_foundation.sync_status_kind("Synced") == "synced"
    assert ui_foundation.sync_status_kind("Guest / Disabled") == "guest"


