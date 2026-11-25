"""Home Dashboard v1 — FreeHome learning dashboard.

Uses DailyStudyPlan (Phase 9) and launches StudyMaster/StudySession (Phase 10).
No ScreenGuard. No learning-algorithm logic in the UI.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import config
import ui_common
import ui_foundation
from daily_study import plan_for_language
from home_viewmodel import HomeViewModel, build_home_view_model


class FreeHome:
    """Manual-launch dashboard: plan preview + start study + quick actions."""

    def __init__(self, root: tk.Tk):
        ui_common.reset_window(root)
        self.root = root
        self.bank_window = None
        self.mistake_window = None
        self.progress_window = None
        self._owned_callbacks = True
        self._refresh_after_id = None
        self._plan = None
        self._view: HomeViewModel | None = None

        self.root.title(config.APP_NAME)
        self.root.geometry("560x640")
        self.root.minsize(420, 560)
        self.root.resizable(True, True)
        ui_foundation.paint_root(root)
        ui_common.apply_theme(root)
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)
        self._page = "today"
        self._nav_buttons = {}

        shell = tk.Frame(root, bg=ui_foundation.COLOR_BG)
        shell.pack(fill=tk.BOTH, expand=True, padx=ui_foundation.PAD_PAGE, pady=ui_foundation.PAD_PAGE)

        self.greeting_label = ui_foundation.label(shell, "", font=ui_foundation.FONT_GREETING)
        self.greeting_label.pack(anchor="w")

        lang_row = tk.Frame(shell, bg=ui_foundation.COLOR_BG)
        lang_row.pack(fill=tk.X, pady=(4, ui_foundation.GAP))
        self.language_label = ui_foundation.label(lang_row, "", font=ui_foundation.FONT_CARD_TITLE)
        self.language_label.pack(side=tk.LEFT)
        self.change_lang_button = ui_foundation.quiet_button(
            lang_row,
            config.ui("Đổi", "Change"),
            self._change_language,
        )
        self.change_lang_button.pack(side=tk.RIGHT)

        self.pages = tk.Frame(shell, bg=ui_foundation.COLOR_BG)
        self.pages.pack(fill=tk.BOTH, expand=True)

        self.today_page = tk.Frame(self.pages, bg=ui_foundation.COLOR_BG)
        self.plan_card = ui_foundation.card(self.today_page)
        self.plan_card.pack(fill=tk.X)
        self.plan_headline = ui_foundation.label(
            self.plan_card, "", font=ui_foundation.FONT_CARD_TITLE, bg=ui_foundation.COLOR_CARD
        )
        self.plan_headline.pack(anchor="w")
        self.plan_support = ui_foundation.label(
            self.plan_card, "", font=ui_foundation.FONT_BODY, bg=ui_foundation.COLOR_CARD
        )
        self.plan_support.configure(wraplength=360, justify="left")
        self.plan_support.pack(anchor="w", pady=(8, 16))
        self.start_button = ui_foundation.primary_button(
            self.plan_card,
            config.ui("Bắt đầu học", "Start learning"),
            self._start_study,
        )
        self.start_button.pack(fill=tk.X)

        account_row = tk.Frame(self.today_page, bg=ui_foundation.COLOR_BG)
        account_row.pack(fill=tk.X, pady=(ui_foundation.GAP, 0))
        self.account_chip = ui_foundation.label(account_row, "", font=ui_foundation.FONT_SMALL)
        self.account_chip.pack(anchor="w")
        self.sync_chip = ui_foundation.status_chip(
            self.today_page,
            "Cloud Sync",
            "guest",
            command=self._show_settings,
        )
        self.sync_chip.pack(anchor="w", pady=(8, 0))

        self.you_page = tk.Frame(self.pages, bg=ui_foundation.COLOR_BG)
        ui_foundation.label(
            self.you_page,
            config.ui("Bạn", "You"),
            font=ui_foundation.FONT_CARD_TITLE,
        ).pack(anchor="w", pady=(0, 8))
        ui_foundation.quiet_button(
            self.you_page,
            config.ui("Tiến độ", "Progress"),
            self._open_progress,
        ).pack(anchor="w", pady=4)
        ui_foundation.quiet_button(
            self.you_page,
            config.ui("Sổ lỗi", "Mistake Book"),
            self._open_mistake_book,
        ).pack(anchor="w", pady=4)

        self.settings_page = tk.Frame(self.pages, bg=ui_foundation.COLOR_BG)
        ui_foundation.label(
            self.settings_page,
            config.ui("Cài đặt", "Settings"),
            font=ui_foundation.FONT_CARD_TITLE,
        ).pack(anchor="w")
        self.sync_detail = ui_foundation.label(
            self.settings_page, "", font=ui_foundation.FONT_SMALL
        )
        self.sync_detail.pack(anchor="w", pady=(8, 8))
        reading_var = tk.BooleanVar(value=config.activity_enabled("reading"))
        listening_var = tk.BooleanVar(value=config.activity_enabled("listening"))

        def on_reading_toggle():
            config.set_activity_enabled("reading", bool(reading_var.get()))
            self.refresh()

        def on_listening_toggle():
            config.set_activity_enabled("listening", bool(listening_var.get()))
            self.refresh()

        tk.Checkbutton(
            self.settings_page,
            text=config.ui("Đọc", "Reading"),
            variable=reading_var,
            command=on_reading_toggle,
            bg=ui_foundation.COLOR_BG,
            fg=ui_foundation.COLOR_TEXT,
            activebackground=ui_foundation.COLOR_BG,
            selectcolor=ui_foundation.COLOR_SOFT_GREEN,
            font=ui_foundation.FONT_BODY,
        ).pack(anchor="w")
        tk.Checkbutton(
            self.settings_page,
            text=config.ui("Nghe", "Listening"),
            variable=listening_var,
            command=on_listening_toggle,
            bg=ui_foundation.COLOR_BG,
            fg=ui_foundation.COLOR_TEXT,
            activebackground=ui_foundation.COLOR_BG,
            selectcolor=ui_foundation.COLOR_SOFT_GREEN,
            font=ui_foundation.FONT_BODY,
        ).pack(anchor="w", pady=(4, 8))

        from account_panel import AccountPanel, AccountSyncStatusPoller

        self.account_panel = AccountPanel(
            self.settings_page,
            on_session_changed=self._on_account_session_changed,
            allow_logout=True,
        )
        self.account_panel.on_refreshed = self._apply_sync_status
        self.account_panel.pack(fill=tk.X, pady=(8, 8))
        self._sync_status_poller = AccountSyncStatusPoller(
            self.root, self.account_panel
        )
        ui_foundation.quiet_button(
            self.settings_page,
            config.ui("Mã thoát khẩn cấp", "Emergency code"),
            lambda: self._emergency_code(self.root),
        ).pack(anchor="w", pady=(8, 0))
        self.conflict_button = ui_foundation.quiet_button(
            self.settings_page,
            config.ui("Xem xung đột", "Review conflict"),
            self._open_sync_conflict,
        )

        nav = tk.Frame(shell, bg=ui_foundation.COLOR_BG)
        nav.pack(fill=tk.X, pady=(ui_foundation.GAP, 0))
        for key, label, command in (
            ("today", config.ui("Hôm nay", "Today"), self._show_today),
            ("words", config.ui("Từ", "Words"), self._open_vocabulary),
            ("you", config.ui("Bạn", "You"), self._show_you),
            ("settings", config.ui("Cài đặt", "Settings"), self._show_settings),
        ):
            button = ui_foundation.quiet_button(nav, label, command)
            button.pack(side=tk.LEFT, padx=(0, 6))
            self._nav_buttons[key] = button

        self._show_today()
        self.refresh()
        self._apply_sync_status(*self._current_sync_text())
        self._sync_status_poller.start()
        # Bind cleanup to the FreeHome-owned AccountPanel frame — never accumulate
        # <Destroy> handlers on the long-lived Tk root across FreeHome recreations.
        self._sync_panel_destroy_bind = self.account_panel.frame.bind(
            "<Destroy>",
            self._on_account_panel_destroy_stop_sync_poller,
            add="+",
        )

    def _on_account_panel_destroy_stop_sync_poller(self, event) -> None:
        panel = getattr(self, "account_panel", None)
        if panel is None or event.widget is not panel.frame:
            return
        self._stop_sync_status_polling()

    def _stop_sync_status_polling(self) -> None:
        poller = getattr(self, "_sync_status_poller", None)
        if poller is not None:
            poller.stop()
        bind_id = getattr(self, "_sync_panel_destroy_bind", None)
        self._sync_panel_destroy_bind = None
        frame = getattr(getattr(self, "account_panel", None), "frame", None)
        if bind_id and frame is not None:
            try:
                frame.unbind("<Destroy>", bind_id)
            except tk.TclError:
                pass

    # ---------- plan / view ----------

    def _cancel_owned_refresh(self) -> None:
        job = self._refresh_after_id
        self._refresh_after_id = None
        if job is None:
            return
        try:
            self.root.after_cancel(job)
        except (tk.TclError, ValueError):
            pass

    def _schedule_owned_refresh(self) -> None:
        """Refresh after a child closes, unless this home is already leaving."""
        if not self._owned_callbacks:
            return
        self._cancel_owned_refresh()
        try:
            self._refresh_after_id = self.root.after(80, self._run_owned_refresh)
        except tk.TclError:
            self._refresh_after_id = None

    def _run_owned_refresh(self) -> None:
        self._refresh_after_id = None
        if not self._owned_callbacks:
            return
        self.refresh()

    def _invalidate_owned_callbacks(self) -> None:
        self._owned_callbacks = False
        self._cancel_owned_refresh()

    def refresh(self):
        """Recompute DailyStudyPlan for the active language and redraw."""
        if not self._owned_callbacks:
            return
        label = getattr(self, "greeting_label", None)
        try:
            if label is None or not label.winfo_exists():
                return
        except tk.TclError:
            return
        code = config.active_code()
        try:
            self._plan = plan_for_language(code)
        except Exception:
            self._plan = None
        if self._plan is None:
            self.greeting_label.config(text=config.ui("Học hôm nay", "Today's Study"))
            self.language_label.config(text=config.language_name(code))
            self.plan_headline.config(
                text=config.ui("Chưa tính được kế hoạch.", "Could not build today's plan.")
            )
            self.plan_support.config(text="")
            self.start_button.config(text=config.ui("Bắt đầu học", "Start learning"))
            return

        self._view = build_home_view_model(
            self._plan,
            config.language_name(code),
            study_language_count=len(config.study_codes()),
        )
        self._apply_view(self._view)

    def _apply_view(self, view: HomeViewModel):
        self.greeting_label.config(text=view.greeting)
        self.language_label.config(text=view.language_label)
        if view.can_change_language:
            self.change_lang_button.config(state="normal")
        else:
            self.change_lang_button.config(state="disabled")
        self.plan_headline.config(text=view.plan_headline)
        self.plan_support.config(text=view.plan_support)
        self.start_button.config(text=view.primary_action_label)
        self._refresh_account_chip()

    def _refresh_account_chip(self) -> None:
        import account_session

        if account_session.is_signed_in():
            text = config.ui(
                f"Tài khoản · {account_session.account_display_name()}",
                f"Account · {account_session.account_display_name()}",
            )
        else:
            text = config.ui("Tài khoản · trên máy này", "Account · on this PC")
        self.account_chip.config(text=text)

    def _current_sync_text(self) -> tuple[str, str]:
        import account_session

        try:
            return account_session.describe_cloud_sync()
        except Exception:
            return "Unknown", ""

    def _apply_sync_status(self, label: str, detail: str) -> None:
        kind = ui_foundation.sync_status_kind(label)
        bg, fg = ui_foundation.sync_status_colors(kind)
        try:
            self.sync_chip.config(text=f"Cloud Sync · {label}", bg=bg, fg=fg, activebackground=bg, activeforeground=fg)
            self.sync_detail.config(text=detail or label)
        except tk.TclError:
            return
        if kind == "conflict":
            self.conflict_button.pack(anchor="w", pady=(8, 0))
        else:
            self.conflict_button.pack_forget()

    def _select_nav(self, key: str) -> None:
        self._page = key
        for name, button in self._nav_buttons.items():
            bg = ui_foundation.COLOR_SOFT_GREEN if name == key else ui_foundation.COLOR_BG
            try:
                button.config(bg=bg)
            except tk.TclError:
                pass

    def _show_page(self, page: tk.Frame, key: str) -> None:
        for child in (self.today_page, self.you_page, self.settings_page):
            child.pack_forget()
        page.pack(fill=tk.BOTH, expand=True)
        self._select_nav(key)

    def _show_today(self) -> None:
        self._show_page(self.today_page, "today")

    def _show_you(self) -> None:
        self._show_page(self.you_page, "you")

    def _show_settings(self) -> None:
        self._show_page(self.settings_page, "settings")
        self._apply_sync_status(*self._current_sync_text())

    def _open_sync_conflict(self) -> None:
        from sync_conflict_app import open_sync_conflicts

        open_sync_conflicts(self.root, on_resolved=self.refresh)

    # ---------- actions ----------

    def _close_account_bound_windows(self):
        """Dispose Vocabulary / Progress / Mistake Book before exposing a new session."""
        import account_session

        account_session.close_account_bound_windows(
            self.bank_window, self.mistake_window, self.progress_window
        )
        self.bank_window = None
        self.mistake_window = None
        self.progress_window = None

    def _on_account_session_changed(self):
        """Rebind dashboard after login/logout/switch — no Guest auto-import."""
        self._close_account_bound_windows()
        self.refresh()
        try:
            self.account_panel.refresh()
        except Exception:
            pass
        # Keep the existing poller; do not start a second loop on account switch.

    def _start_study(self):
        self.refresh()  # avoid stale plan before launch
        self._invalidate_owned_callbacks()
        self._stop_sync_status_polling()
        self._close_bank()
        self._close_mistake_book()
        for child in list(self.root.winfo_children()):
            try:
                child.destroy()
            except tk.TclError:
                pass
        self.root.resizable(True, True)
        StudyMasterApp = self._study_master_class()
        StudyMasterApp(self.root, on_finished=self._on_study_finished)

    @staticmethod
    def _study_master_class():
        """Resolve StudyMasterApp whether launched as main or __main__."""
        import sys

        for name in ("main", "__main__"):
            mod = sys.modules.get(name)
            if mod is not None and hasattr(mod, "StudyMasterApp"):
                return mod.StudyMasterApp
        from main import StudyMasterApp

        return StudyMasterApp

    def _on_study_finished(self):
        """Return from StudyMaster to dashboard and refresh plan."""
        FreeHome(self.root)

    def _change_language(self):
        codes = config.study_codes()
        if len(codes) <= 1:
            return
        self._choose_language(codes, mode="active")

    def _open_vocabulary(self):
        codes = config.study_codes()
        if len(codes) == 1:
            self._open_bank(codes[0], focus_add=False)
            return
        self._choose_language(codes, mode="vocabulary")

    def _add_words(self):
        codes = config.study_codes()
        if len(codes) == 1:
            self._open_bank(codes[0], focus_add=True)
            return
        self._choose_language(codes, mode="bank")

    def _open_mistake_book(self):
        codes = config.study_codes()
        if len(codes) == 1:
            self._show_mistake_book(codes[0])
            return
        self._choose_language(codes, mode="mistakes")

    def _open_progress(self):
        codes = config.study_codes()
        if len(codes) == 1:
            self._show_progress(codes[0])
            return
        self._choose_language(codes, mode="progress")

    def _open_settings(self):
        self._show_settings()

    def _emergency_code(self, parent):
        import emergency_enroll

        emergency_enroll.recover(parent, lock_active=False)

    def _choose_language(self, codes, mode: str):
        dialog = tk.Toplevel(self.root)
        dialog.title(config.ui("Chọn ngôn ngữ", "Choose a language"))
        dialog.resizable(False, False)
        dialog.transient(self.root)
        frame = ttk.Frame(dialog, padding=16)
        frame.pack()
        if mode == "mistakes":
            prompt = config.ui(
                "Xem sổ lỗi ngôn ngữ nào?", "Mistake Book for which language?"
            )
        elif mode == "progress":
            prompt = config.ui(
                "Xem tiến độ ngôn ngữ nào?", "Progress for which language?"
            )
        elif mode == "active":
            prompt = config.ui(
                "Đặt ngôn ngữ đang học?", "Set the active study language?"
            )
        elif mode == "vocabulary":
            prompt = config.ui(
                "Xem kho từ ngôn ngữ nào?", "Vocabulary for which language?"
            )
        else:
            prompt = config.ui(
                "Thêm từ cho ngôn ngữ nào?", "Add words for which language?"
            )
        ttk.Label(frame, text=prompt).pack(anchor="w", pady=(0, 8))
        for code in codes:
            if mode == "mistakes":
                action = lambda c=code, dialog=dialog: (
                    dialog.destroy(),
                    self._show_mistake_book(c),
                )
            elif mode == "progress":
                action = lambda c=code, dialog=dialog: (
                    dialog.destroy(),
                    self._show_progress(c),
                )
            elif mode == "active":
                action = lambda c=code, dialog=dialog: (
                    dialog.destroy(),
                    self._set_active_language(c),
                )
            elif mode == "vocabulary":
                action = lambda c=code, dialog=dialog: (
                    dialog.destroy(),
                    self._open_bank(c, focus_add=False),
                )
            else:
                action = lambda c=code, dialog=dialog: (
                    dialog.destroy(),
                    self._open_bank(c, focus_add=True),
                )
            ttk.Button(
                frame, text=config.language_name(code), command=action
            ).pack(fill=tk.X, pady=2)
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog.geometry("+%d+%d" % (self.root.winfo_rootx() + 40, self.root.winfo_rooty() + 40))

    def _set_active_language(self, code: str):
        config.set_language(code)
        self.refresh()

    def _show_mistake_book(self, code):
        from mistake_book_app import MistakeBookApp

        config.set_language(code)
        self.refresh()
        if self.mistake_window is not None and self.mistake_window.winfo_exists():
            self.mistake_window.destroy()
        self.mistake_window = tk.Toplevel(self.root)
        ui_common.own_toplevel(self.mistake_window, self.root)
        MistakeBookApp(self.mistake_window, language_code=code)
        self.mistake_window.bind(
            "<Destroy>", lambda _e: self._schedule_owned_refresh(), add="+"
        )

    def _show_progress(self, code):
        from progress_app import ProgressApp

        config.set_language(code)
        self.refresh()
        if self.progress_window is not None and self.progress_window.winfo_exists():
            self.progress_window.destroy()
        self.progress_window = tk.Toplevel(self.root)
        ui_common.own_toplevel(self.progress_window, self.root)
        ProgressApp(self.progress_window, language_code=code)
        self.progress_window.bind(
            "<Destroy>", lambda _e: self._schedule_owned_refresh(), add="+"
        )

    def _open_bank(self, code, focus_add: bool = False):
        from vocabulary_app import VocabularyLibraryApp

        config.set_language(code)
        self.refresh()
        if self.bank_window is not None and self.bank_window.winfo_exists():
            self.bank_window.lift()
            app = getattr(self, "_library_app", None)
            if focus_add and app is not None:
                try:
                    app.open_add_dialog()
                except tk.TclError:
                    pass
            return
        self.bank_window = tk.Toplevel(self.root)
        ui_common.own_toplevel(self.bank_window, self.root)
        self._library_app = VocabularyLibraryApp(
            self.bank_window,
            language_code=code,
            focus_add=focus_add,
            on_saved=self.refresh,
        )
        self.bank_window.bind(
            "<Destroy>", lambda _e: self._schedule_owned_refresh(), add="+"
        )

    def _close_bank(self):
        if self.bank_window is not None and self.bank_window.winfo_exists():
            self.bank_window.destroy()

    def _close_mistake_book(self):
        if self.mistake_window is not None and self.mistake_window.winfo_exists():
            self.mistake_window.destroy()
