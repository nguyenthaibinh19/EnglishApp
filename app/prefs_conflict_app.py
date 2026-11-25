"""Explicit Keep local / Keep server UI for account preference conflicts."""

from __future__ import annotations

import json
import tkinter as tk
from tkinter import messagebox, ttk

import config
import ui_common


class PrefsConflictApp:
    def __init__(self, window: tk.Misc, on_resolved=None):
        self.window = window
        self.on_resolved = on_resolved
        self.window.title(
            config.APP_NAME + " — " + config.ui("Xung đột tùy chọn", "Preference conflict")
        )
        ui_common.apply_theme(window)
        root = ttk.Frame(window, padding=12)
        root.pack(fill=tk.BOTH, expand=True)
        ttk.Label(
            root,
            text=config.ui(
                "Thiết bị khác đã đổi tùy chọn học. Chọn giữ bản cục bộ hoặc bản máy chủ. "
                "Không ghi đè tự động.",
                "Another device changed learning preferences. Choose Keep local or Keep server. "
                "Nothing is overwritten automatically.",
            ),
            wraplength=480,
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(0, 8))
        self.local_label = ttk.Label(root, text="", wraplength=480)
        self.local_label.pack(anchor="w")
        self.remote_label = ttk.Label(root, text="", wraplength=480)
        self.remote_label.pack(anchor="w", pady=(4, 12))
        self._shown_account_key = None
        buttons = ttk.Frame(root)
        buttons.pack(anchor="e")
        ttk.Button(
            buttons,
            text=config.ui("Giữ máy chủ", "Keep server"),
            command=lambda: self._resolve("server"),
        ).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(
            buttons,
            text=config.ui("Giữ cục bộ", "Keep local"),
            command=lambda: self._resolve("local"),
        ).pack(side=tk.LEFT)
        self.refresh()

    def refresh(self):
        from study_data import active_account_store, is_signed_in

        self._shown_account_key = _account_key()
        if not is_signed_in():
            self.local_label.config(text=config.ui("Cần đăng nhập.", "Sign in required."))
            return
        store = active_account_store()
        if store is None:
            return
        prefs = store.get_preferences()
        local = {
            k: prefs.get(k)
            for k in ("study_languages", "reading_level", "native", "activities")
            if k in prefs
        }
        remote = prefs.get("_prefs_conflict_remote_values") or {}
        self.local_label.config(
            text=config.ui("Cục bộ: ", "Local: ")
            + json.dumps(local, ensure_ascii=False)
        )
        self.remote_label.config(
            text=config.ui("Máy chủ: ", "Server: ")
            + json.dumps(remote, ensure_ascii=False)
        )

    def _resolve(self, keep: str):
        from account_prefs import resolve_preferences_conflict
        from account_sync_engine import active_engine, notify_local_change
        from study_data import active_account_store

        if _account_key() != self._shown_account_key:
            self.refresh()
            return
        store = active_account_store()
        engine = active_engine()
        if store is None or engine is None:
            messagebox.showerror(config.APP_NAME, "No active sync session.", parent=self.window)
            return
        try:
            resolve_preferences_conflict(store, engine.client, keep=keep)
            notify_local_change()
        except Exception as error:
            messagebox.showerror(config.APP_NAME, str(error), parent=self.window)
            return
        if callable(self.on_resolved):
            self.on_resolved()
        self.window.destroy()


def _account_key():
    from study_data import is_signed_in

    if not is_signed_in():
        return None
    return config.account_user_id()


def open_prefs_conflict(parent: tk.Misc, on_resolved=None):
    window = tk.Toplevel(parent)
    ui_common.own_toplevel(window, parent)
    PrefsConflictApp(window, on_resolved=on_resolved)
    return window
