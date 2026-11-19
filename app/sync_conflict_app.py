"""Vocabulary sync conflict resolution UI (Phase 18C.2).

Shows locally preserved and server-accepted versions. The learner must choose
explicitly; nothing is overwritten silently and deletes are never resurrected
without choosing Keep server or Save local as new word.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

import config
import ui_common


def _format_entry(entry) -> str:
    if entry is None:
        return config.ui("(không có / đã xóa)", "(none / deleted)")
    if not isinstance(entry, dict):
        return str(entry)
    word = str(entry.get("word") or "")
    meaning = str(entry.get("meaning") or entry.get("vi") or "")
    return f"{word} — {meaning}".strip(" —")


class SyncConflictApp:
    def __init__(self, window: tk.Misc, on_resolved=None):
        self.window = window
        self.on_resolved = on_resolved
        self.window.title(config.APP_NAME + " — " + config.ui("Xung đột đồng bộ", "Sync conflicts"))
        ui_common.apply_theme(window)
        self.root = ttk.Frame(window, padding=12)
        self.root.pack(fill=tk.BOTH, expand=True)
        ttk.Label(
            self.root,
            text=config.ui(
                "Chọn phiên bản giữ lại. Không có ghi đè tự động. "
                "Từ đã xóa trên máy chủ không được phục hồi cùng UUID.",
                "Choose which version to keep. Nothing is overwritten automatically. "
                "A server-deleted word cannot be resurrected under the same UUID.",
            ),
            style="Muted.TLabel",
            wraplength=520,
        ).pack(anchor="w", pady=(0, 8))
        self.list_frame = ttk.Frame(self.root)
        self.list_frame.pack(fill=tk.BOTH, expand=True)
        self.empty = ttk.Label(self.root, text="", style="Muted.TLabel")
        ttk.Button(
            self.root,
            text=config.ui("Đóng", "Close"),
            command=self.window.destroy,
        ).pack(anchor="e", pady=(8, 0))
        self.refresh()

    def refresh(self):
        for child in self.list_frame.winfo_children():
            child.destroy()
        from study_data import active_account_store, is_signed_in

        if not is_signed_in():
            self.empty.config(
                text=config.ui("Cần đăng nhập để xem xung đột.", "Sign in to view conflicts.")
            )
            self.empty.pack(anchor="w")
            return
        store = active_account_store()
        if store is None:
            self.empty.config(text=config.ui("Không có kho tài khoản.", "No account store."))
            self.empty.pack(anchor="w")
            return
        conflicts = store.list_open_vocab_conflicts()
        if not conflicts:
            self.empty.config(
                text=config.ui("Không có xung đột từ vựng đang mở.", "No open vocabulary conflicts.")
            )
            self.empty.pack(anchor="w")
            return
        self.empty.pack_forget()
        for item in conflicts:
            self._add_row(store, item)

    def _add_row(self, store, item: dict):
        frame = ttk.LabelFrame(
            self.list_frame,
            text=f"{item.get('language_code')} · {str(item.get('vocab_id') or '')[:8]}…",
            padding=8,
        )
        frame.pack(fill=tk.X, pady=4)
        local_label = (
            config.ui("Xóa cục bộ", "Local delete")
            if item.get("local_operation") == "delete"
            else _format_entry(item.get("local_entry"))
        )
        server_label = (
            config.ui("Đã xóa trên máy chủ", "Deleted on server")
            if item.get("server_deleted")
            else _format_entry(item.get("server_entry"))
        )
        ttk.Label(
            frame,
            text=config.ui("Bản cục bộ: ", "Local: ") + local_label,
            wraplength=480,
        ).pack(anchor="w")
        ttk.Label(
            frame,
            text=config.ui("Bản máy chủ: ", "Server: ") + server_label,
            wraplength=480,
        ).pack(anchor="w", pady=(2, 6))
        buttons = ttk.Frame(frame)
        buttons.pack(anchor="w")
        ttk.Button(
            buttons,
            text=config.ui("Giữ máy chủ", "Keep server"),
            command=lambda: self._resolve(store, item, "server"),
        ).pack(side=tk.LEFT, padx=(0, 8))
        if item.get("server_deleted") and item.get("local_operation") == "put":
            ttk.Button(
                buttons,
                text=config.ui("Lưu cục bộ thành từ mới", "Save local as new word"),
                command=lambda: self._resolve(store, item, "local_as_new"),
            ).pack(side=tk.LEFT)
        elif not item.get("server_deleted"):
            ttk.Button(
                buttons,
                text=config.ui("Giữ cục bộ", "Keep local"),
                command=lambda: self._resolve(store, item, "local"),
            ).pack(side=tk.LEFT)

    def _resolve(self, store, item: dict, keep: str):
        try:
            store.resolve_vocab_conflict(
                item["language_code"], item["vocab_id"], keep=keep
            )
        except Exception as error:
            messagebox.showerror(config.APP_NAME, str(error), parent=self.window)
            return
        try:
            from account_sync_engine import notify_local_change

            notify_local_change()
        except Exception:
            pass
        if callable(self.on_resolved):
            self.on_resolved()
        self.refresh()


def open_sync_conflicts(parent: tk.Misc, on_resolved=None):
    window = tk.Toplevel(parent)
    ui_common.own_toplevel(window, parent)
    SyncConflictApp(window, on_resolved=on_resolved)
    return window
