"""Explicit guest → account legacy import (Phase 18C.2 / ADR-022).

Never auto-imports on login. Never rewrites guest JSON/JSONL files.
Requires account-specific consent before copying vocabulary into the account store.
"""

from __future__ import annotations

import json
import os
import tkinter as tk
from tkinter import messagebox, ttk

import config
import ui_common


def preview_guest_vocabulary(language_code: str, data_root: str = None) -> dict:
    """Read-only preview of guest vocab.json for one language."""
    from account_local_store import guest_language_dir

    code = str(language_code or config.active_code()).strip().lower()
    folder = guest_language_dir(code, data_root=data_root)
    vocab_path = os.path.join(folder, "vocab.json")
    attempts_path = os.path.join(folder, "attempts.jsonl")
    entries = []
    if os.path.isfile(vocab_path):
        try:
            raw = json.loads(open(vocab_path, encoding="utf-8").read())
            if isinstance(raw, list):
                entries = [e for e in raw if isinstance(e, dict)]
        except (OSError, json.JSONDecodeError):
            entries = []
    attempt_lines = 0
    if os.path.isfile(attempts_path):
        try:
            with open(attempts_path, encoding="utf-8") as handle:
                attempt_lines = sum(1 for line in handle if line.strip())
        except OSError:
            attempt_lines = 0
    return {
        "language_code": code,
        "vocab_path": vocab_path,
        "attempts_path": attempts_path,
        "entry_count": len(entries),
        "entries": entries,
        "attempt_line_count": attempt_lines,
        "vocab_exists": os.path.isfile(vocab_path),
    }


class LegacyImportApp:
    def __init__(self, window: tk.Misc, language_code: str = None, on_done=None):
        self.window = window
        self.language_code = language_code or config.active_code()
        self.on_done = on_done
        self.consent_var = tk.BooleanVar(value=False)
        self.window.title(
            config.APP_NAME + " — " + config.ui("Nhập dữ liệu khách", "Import guest data")
        )
        ui_common.apply_theme(window)
        self.root = ttk.Frame(window, padding=12)
        self.root.pack(fill=tk.BOTH, expand=True)
        self.preview = preview_guest_vocabulary(self.language_code)
        ttk.Label(
            self.root,
            text=config.ui(
                "Nhập từ vựng guest vào tài khoản đang đăng nhập. "
                "Không tự động khi đăng nhập. File guest không bị ghi đè.",
                "Import guest vocabulary into the signed-in account. "
                "Never automatic on login. Guest files are not rewritten.",
            ),
            wraplength=520,
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(0, 8))
        ttk.Label(
            self.root,
            text=config.ui(
                f"Ngôn ngữ: {self.preview['language_code']} · "
                f"{self.preview['entry_count']} từ · "
                f"{self.preview['attempt_line_count']} dòng lịch sử (xem trước).",
                f"Language: {self.preview['language_code']} · "
                f"{self.preview['entry_count']} words · "
                f"{self.preview['attempt_line_count']} history lines (preview).",
            ),
            wraplength=520,
        ).pack(anchor="w", pady=(0, 8))
        sample = ttk.Label(self.root, text="", style="Muted.TLabel", wraplength=520)
        words = []
        for entry in self.preview["entries"][:8]:
            words.append(str(entry.get("word") or ""))
        sample.config(
            text=config.ui("Mẫu: ", "Sample: ") + (", ".join(w for w in words if w) or "—")
        )
        sample.pack(anchor="w", pady=(0, 8))
        ttk.Checkbutton(
            self.root,
            text=config.ui(
                "Tôi đồng ý nhập từ vựng guest vào tài khoản này (không phải tài khoản khác).",
                "I consent to import guest vocabulary into this account (not another account).",
            ),
            variable=self.consent_var,
        ).pack(anchor="w", pady=(0, 8))
        ttk.Label(
            self.root,
            text=config.ui(
                "Lịch sử trả lời guest chưa được nhập tự động trong 18C.2 "
                "(cần ledger ADR-022 đầy đủ). Chỉ từ vựng được sao chép khi đồng ý.",
                "Guest attempt history is not auto-imported in 18C.2 "
                "(full ADR-022 ledger deferred). Only vocabulary is copied on consent.",
            ),
            wraplength=520,
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(0, 8))
        buttons = ttk.Frame(self.root)
        buttons.pack(anchor="e", fill=tk.X)
        ttk.Button(
            buttons,
            text=config.ui("Hủy", "Cancel"),
            command=self.window.destroy,
        ).pack(side=tk.RIGHT)
        ttk.Button(
            buttons,
            text=config.ui("Nhập từ vựng", "Import vocabulary"),
            command=self._import,
        ).pack(side=tk.RIGHT, padx=(0, 8))

    def _import(self):
        if not self.consent_var.get():
            messagebox.showwarning(
                config.APP_NAME,
                config.ui("Cần đánh dấu đồng ý trước.", "Consent is required first."),
                parent=self.window,
            )
            return
        from study_data import active_account_store, is_signed_in

        if not is_signed_in():
            messagebox.showerror(
                config.APP_NAME,
                config.ui("Cần đăng nhập.", "Sign in required."),
                parent=self.window,
            )
            return
        store = active_account_store()
        if store is None:
            messagebox.showerror(config.APP_NAME, "No account store.", parent=self.window)
            return
        store.grant_legacy_consent(
            self.language_code,
            "guest",
            note="explicit-gui-consent",
        )
        result = store.import_guest_vocabulary(
            self.language_code,
            self.preview["entries"],
            require_consent=True,
        )
        try:
            from account_sync_engine import notify_local_change

            notify_local_change()
        except Exception:
            pass
        messagebox.showinfo(
            config.APP_NAME,
            config.ui(
                f"Đã nhập {result['imported']} từ, bỏ qua {result['skipped']}.",
                f"Imported {result['imported']} words, skipped {result['skipped']}.",
            ),
            parent=self.window,
        )
        if callable(self.on_done):
            self.on_done(result)
        self.window.destroy()


def open_legacy_import(parent: tk.Misc, language_code: str = None, on_done=None):
    window = tk.Toplevel(parent)
    ui_common.own_toplevel(window, parent)
    LegacyImportApp(window, language_code=language_code, on_done=on_done)
    return window
