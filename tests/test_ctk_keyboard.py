"""Enter and Space respect a disabled CustomTkinter control."""

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

import config
from ctk_keyboard import bind_activation, control_is_enabled
from home_app import FreeHome


def test_disabled_home_control_ignores_enter_and_space(tmp_path, monkeypatch):
    monkeypatch.setenv("LG_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LG_APP_ENVIRONMENT", "development")
    monkeypatch.setenv("ACCOUNT_SERVER_URL", "http://127.0.0.1:9")
    monkeypatch.setattr(config, "LOCK_SCREEN", False)
    ctk.set_widget_scaling(1.0)

    root = tk.Tk()
    root.geometry("560x600+3200+40")
    try:
        home = FreeHome(root)
        root.update()
        hits = []
        home.change_lang_button.configure(state="disabled", command=lambda: hits.append("change"))
        assert control_is_enabled(home.change_lang_button) is False
        home.change_lang_button.focus_set()
        root.update()
        focused = root.focus_get()
        focused.event_generate("<Return>")
        focused.event_generate("<space>")
        root.update()
        home.change_lang_button.invoke()
        assert hits == []

        home.start_button.configure(command=lambda: hits.append("start"))
        home.start_button.focus_set()
        root.update()
        root.focus_get().event_generate("<Return>")
        root.update()
        assert hits == ["start"]

        ctk.set_widget_scaling(1.5)
        probe = ctk.CTkButton(root, text="Scale", command=lambda: hits.append("scale"))
        bind_activation(probe)
        probe.invoke()
        assert hits[-1] == "scale"
        ctk.set_widget_scaling(1.0)
        home._stop_sync_status_polling()
    finally:
        ctk.set_widget_scaling(1.0)
        try:
            root.destroy()
        except tk.TclError:
            pass
