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
                "Đồng ý từ vựng không nhập lịch sử trả lời. Lịch sử cần một lần "
                "đồng ý riêng cho đúng tài khoản và đúng file nguồn.",
                "Vocabulary consent does not import attempt history. History needs "
                "its own consent for this account and this source file.",
            ),
            wraplength=520,
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(0, 8))
        self.attempt_consent_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            self.root,
            text=config.ui(
                "Tôi đồng ý nhập lịch sử trả lời guest vào tài khoản đang đăng nhập.",
                "I consent to import guest attempt history into the current account.",
            ),
            variable=self.attempt_consent_var,
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
            text=config.ui("Nhập lịch sử", "Import attempt history"),
            command=self._import_attempts,
        ).pack(side=tk.RIGHT, padx=(0, 8))
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

    def _import_attempts(self):
        if not self.attempt_consent_var.get():
            messagebox.showwarning(
                config.APP_NAME,
                config.ui(
                    "Cần đồng ý riêng cho lịch sử trả lời.",
                    "Attempt history needs its own consent.",
                ),
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
        path = self.preview["attempts_path"]
        if not os.path.isfile(path):
            messagebox.showinfo(
                config.APP_NAME,
                config.ui("Không có file lịch sử guest.", "No guest attempt file."),
                parent=self.window,
            )
            return
        from legacy_attempt_import import (
            LegacySourceIdentityError,
            import_guest_attempts,
            read_windows_file_identity,
        )

        try:
            identity = read_windows_file_identity(path)
        except LegacySourceIdentityError:
            store.note_legacy_attempt_conflict(
                f"identity_unavailable {self.language_code}"
            )
            messagebox.showwarning(
                config.APP_NAME,
                config.ui(
                    "Không xác định được file nguồn. Lịch sử chưa được nhập.",
                    "The source file identity could not be verified. Nothing was imported.",
                ),
                parent=self.window,
            )
            return
        store.grant_attempt_import_consent(
            self.language_code,
            identity,
            note="explicit-attempt-consent",
        )
        result = import_guest_attempts(
            store,
            language_code=self.language_code,
            path=path,
        )
        if result["status"] == "overlap":
            choice = _prompt_overlap_choice(self.window)
            if choice is None:
                messagebox.showwarning(
                    config.APP_NAME,
                    config.ui(
                        "Cần chọn cách xử lý dòng trùng. Chưa nhập thêm.",
                        "Choose how to handle overlapping lines. Nothing further was imported.",
                    ),
                    parent=self.window,
                )
                return
            resolutions = {offset: choice for offset in result["overlap_offsets"]}
            result = import_guest_attempts(
                store,
                language_code=self.language_code,
                path=path,
                resolutions=resolutions,
            )
        if result["status"] in {"conflict", "identity_unavailable", "replacement_consent_required"}:
            messagebox.showwarning(
                config.APP_NAME,
                config.ui(
                    "Nhập lịch sử bị chặn. Dữ liệu đã nhận không bị xóa.",
                    "Attempt import is blocked. Accepted history was not deleted.",
                ),
                parent=self.window,
            )
            return
        messagebox.showinfo(
            config.APP_NAME,
            config.ui(
                f"Đã nhập {result['imported']} lần trả lời vào tài khoản này.",
                f"Imported {result['imported']} attempts into this account.",
            ),
            parent=self.window,
        )


def _prompt_overlap_choice(parent: tk.Misc):
    """Return skip, distinct, or None. Skip is the default action."""
    dialog = tk.Toplevel(parent)
    dialog.title(config.APP_NAME)
    dialog.transient(parent)
    dialog.grab_set()
    choice = {"value": None}
    frame = ttk.Frame(dialog, padding=12)
    frame.pack(fill=tk.BOTH, expand=True)
    ttk.Label(
        frame,
        text=config.ui(
            "Một số dòng đã có trong tài khoản. Bỏ qua là mặc định. "
            "Nhập thành lần trả lời riêng chỉ khi bạn chọn rõ.",
            "Some lines were already imported. Skip is the default. "
            "Import them as distinct attempts only if you choose that explicitly.",
        ),
        wraplength=420,
    ).pack(anchor="w", pady=(0, 8))

    def _choose(value):
        choice["value"] = value
        dialog.destroy()

    buttons = ttk.Frame(frame)
    buttons.pack(anchor="e")
    ttk.Button(
        buttons,
        text=config.ui("Bỏ qua", "Skip"),
        command=lambda: _choose("skip"),
    ).pack(side=tk.RIGHT)
    ttk.Button(
        buttons,
        text=config.ui("Nhập riêng", "Import as distinct"),
        command=lambda: _choose("distinct"),
    ).pack(side=tk.RIGHT, padx=(0, 8))
    dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
    parent.wait_window(dialog)
    return choice["value"]


def open_legacy_import(parent: tk.Misc, language_code: str = None, on_done=None):
    window = tk.Toplevel(parent)
    ui_common.own_toplevel(window, parent)
    LegacyImportApp(window, language_code=language_code, on_done=on_done)
    return window
