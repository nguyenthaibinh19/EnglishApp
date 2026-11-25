"""Presentation tokens and Today corrections. No SRS writes."""

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
        assert "streak" not in home.plan_support.cget("text").lower()
        assert home.environment_label.cget("text") == "DEVELOPMENT"
        assert home.environment_label.winfo_manager() == "pack"
        assert home.start_button.cget("text")
        assert "Settings" in home.settings_button.cget("text")
        assert "Add word" in home.add_word_button.cget("text")
        state = {"reading": False, "listening": False}
        monkeypatch.setattr("home_app.config.activity_enabled", lambda name: state[name])
        home._open_settings()
        assert home._settings_dialog is not None
        assert home.account_panel.frame.winfo_exists()
        assert home._conflict_button is not None
        assert home._listening_var.get() is False
        state["listening"] = True
        home._sync_settings_controls()
        assert home._listening_var.get() is True
        home.sync_chip.config(text="Cloud Sync · Conflict / Action required")
        home._sync_settings_controls()
        assert home._conflict_button.winfo_manager() == "pack"
        seen = {"n": 0}

        def counting(_code):
            seen["n"] += 1
            return plan

        monkeypatch.setattr("home_app.plan_for_language", counting)

        def refuse_network(*_args, **_kwargs):
            raise AssertionError("plan refresh must not open a network request")

        monkeypatch.setattr("urllib.request.urlopen", refuse_network)
        home._apply_sync_status("Synced", "local catch-up")
        assert seen["n"] >= 1
        poller = home._sync_status_poller
        home._on_account_session_changed()
        assert home._sync_status_poller is poller
        home._invalidate_owned_callbacks()
        frozen = seen["n"]
        home._apply_sync_status("Synced", "after destroy")
        assert seen["n"] == frozen
        calls = []
        home._owned_callbacks = True
        home._open_vocabulary = lambda: calls.append("words")
        home._add_words = lambda: calls.append("add")
        home._open_progress = lambda: calls.append("you")
        home._open_mistake_book = lambda: calls.append("mistakes")
        home.words_button.config(command=home._open_vocabulary)
        home.words_nav_button.config(command=home._open_vocabulary)
        home.add_word_button.config(command=home._add_words)
        home.progress_button.config(command=home._open_progress)
        home.you_button.config(command=home._open_progress)
        home.mistake_button.config(command=home._open_mistake_book)
        home.words_button.invoke()
        home.add_word_button.invoke()
        home.progress_button.invoke()
        home.you_button.invoke()
        home.mistake_button.invoke()
        assert calls == ["words", "add", "you", "you", "mistakes"]
    finally:
        home._stop_sync_status_polling()


def test_environment_badge_hides_production_and_marks_the_others():
    dev = type("I", (), {"runtime_environment": "development", "rc_smoke": False})()
    staging = type("I", (), {"runtime_environment": "staging", "rc_smoke": False})()
    production = type("I", (), {"runtime_environment": "production", "rc_smoke": False})()
    rc = type("I", (), {"runtime_environment": "production", "rc_smoke": True})()
    assert ui_foundation.environment_badge(dev) == "DEVELOPMENT"
    assert ui_foundation.environment_badge(staging) == "STAGING"
    assert ui_foundation.environment_badge(production) == ""
    assert ui_foundation.environment_badge(rc) == "RC TEST"


def test_sync_status_kinds_cover_required_states():
    assert ui_foundation.sync_status_kind("Offline") == "offline"
    assert ui_foundation.sync_status_kind("Pending") == "pending"
    assert ui_foundation.sync_status_kind("Conflict / Action required") == "conflict"
    assert ui_foundation.sync_status_kind("Server Sync unavailable") == "error"
    assert ui_foundation.sync_status_kind("Synced") == "synced"
    assert ui_foundation.sync_status_kind("Guest / Disabled") == "guest"


