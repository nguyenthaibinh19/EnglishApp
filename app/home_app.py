"""Home Dashboard v1 — FreeHome learning dashboard.

Uses DailyStudyPlan (Phase 9) and launches StudyMaster/StudySession (Phase 10).
No ScreenGuard. No learning-algorithm logic in the UI.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import customtkinter as ctk
import config
import ui_common
import ui_foundation
from ctk_keyboard import bind_activation

# Home-only. CTk's DPI path expects a CTk root (it calls
# block_update_dimensions_event). This window stays tk.Tk, so automatic
# scaling stays off and the 560×600 client is not sized twice.
ctk.deactivate_automatic_dpi_awareness()
ctk.set_appearance_mode("light")
from daily_study import plan_for_language
from home_viewmodel import HomeViewModel, build_home_view_model


class _ShortcutCard(ctk.CTkFrame):
    """Two-line destination. Title and subtitle use different type sizes."""

    def __init__(self, parent, title: str, subtitle: str, command):
        super().__init__(
            parent,
            fg_color=ui_foundation.COLOR_CARD,
            corner_radius=16,
            border_width=0,
        )
        self._command = command
        self._title = ctk.CTkLabel(
            self,
            text=title,
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color=ui_foundation.COLOR_TEXT,
            fg_color=ui_foundation.COLOR_CARD,
            anchor="w",
        )
        self._title.pack(anchor="w", padx=14, pady=(12, 0))
        self._subtitle = ctk.CTkLabel(
            self,
            text=subtitle,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#5C7268",
            fg_color=ui_foundation.COLOR_CARD,
            anchor="w",
        )
        self._subtitle.pack(anchor="w", padx=14, pady=(0, 12))
        for widget in (self, self._title, self._subtitle):
            widget.bind("<Button-1>", self._on_click, add="+")

        def fire(_event=None):
            self.invoke()
            return "break"

        for widget in (self._title, self._subtitle):
            widget.bind("<Return>", fire, add="+")
            widget.bind("<space>", fire, add="+")
        bind_activation(self)

    def _on_click(self, _event=None):
        if self._command is not None:
            self._command()

    def invoke(self):
        self._on_click()

    def cget(self, attribute_name: str):
        if attribute_name == "text":
            return self._title.cget("text")
        return super().cget(attribute_name)

    def configure(self, **kwargs):
        if "command" in kwargs:
            self._command = kwargs.pop("command")
        if kwargs:
            super().configure(**kwargs)


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

        self.root.title("LanguageGuard")
        self.root.geometry("560x600")
        self.root.minsize(480, 560)
        self.root.resizable(True, True)
        ui_foundation.paint_root(root)
        ui_common.apply_theme(root)
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)
        self._settings_dialog = None
        self._settings_account_panel = None
        self._reading_var = None
        self._listening_var = None
        self._settings_sync_label = None
        self._vocab_conflict_window = None
        self._prefs_conflict_window = None
        self._refreshing_visible_account = False
        self._sync_detail_text = ""
        self._in_plan_refresh = False

        shell = ctk.CTkFrame(root, fg_color=ui_foundation.COLOR_BG, corner_radius=0)
        shell.pack(fill=tk.BOTH, expand=True)

        nav = ctk.CTkFrame(shell, fg_color=ui_foundation.COLOR_BG, corner_radius=0, height=52)
        nav.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=(2, 8))
        self.today_button = self._nav_button(
            nav, "⌂", config.ui("Hôm nay", "Today"), self.refresh, selected=True
        )
        self.words_nav_button = self._nav_button(
            nav, "☰", config.ui("Từ", "Words"), self._open_vocabulary
        )
        self.you_button = self._nav_button(
            nav, "☺", config.ui("Bạn", "You"), self._open_progress
        )
        self.settings_button = self._nav_button(
            nav, "⚙", config.ui("Cài đặt", "Settings"), self._open_settings
        )
        for button in (
            self.today_button,
            self.words_nav_button,
            self.you_button,
            self.settings_button,
        ):
            button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)

        meta = ctk.CTkFrame(shell, fg_color=ui_foundation.COLOR_BG, corner_radius=0)
        meta.pack(side=tk.BOTTOM, fill=tk.X, padx=16, pady=(0, 0))

        content = ctk.CTkFrame(shell, fg_color=ui_foundation.COLOR_BG, corner_radius=0)
        content.pack(fill=tk.BOTH, expand=True, padx=16, pady=(12, 4))

        brand = ctk.CTkFrame(content, fg_color=ui_foundation.COLOR_BG, corner_radius=0)
        brand.pack(fill=tk.X)
        ctk.CTkLabel(
            brand,
            text="LanguageGuard",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color=ui_foundation.COLOR_PRIMARY,
            fg_color=ui_foundation.COLOR_BG,
        ).pack(side=tk.LEFT)
        self.environment_label = ctk.CTkLabel(
            brand,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=ui_foundation.COLOR_TEXT,
            fg_color=ui_foundation.COLOR_WARM,
            corner_radius=8,
            width=110,
            height=24,
        )
        badge = ui_foundation.environment_badge(config.environment_identity())
        if badge:
            self.environment_label.configure(text=badge)
            self.environment_label.pack(side=tk.RIGHT)

        self.greeting_label = ctk.CTkLabel(
            content,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=26, weight="bold"),
            text_color=ui_foundation.COLOR_TEXT,
            fg_color=ui_foundation.COLOR_BG,
            anchor="w",
        )
        self.greeting_label.pack(anchor="w", pady=(8, 0))
        ctk.CTkLabel(
            content,
            text=config.ui("Một phiên ngắn, vừa sức.", "One session, at your pace."),
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color="#5C7268",
            fg_color=ui_foundation.COLOR_BG,
            anchor="w",
        ).pack(anchor="w")

        lang_row = ctk.CTkFrame(content, fg_color=ui_foundation.COLOR_BG, corner_radius=0)
        lang_row.pack(fill=tk.X, pady=(6, 8))
        self.language_label = ctk.CTkLabel(
            lang_row,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color=ui_foundation.COLOR_TEXT,
            fg_color=ui_foundation.COLOR_BG,
            anchor="w",
        )
        self.language_label.pack(side=tk.LEFT)
        self.change_lang_button = ctk.CTkButton(
            lang_row,
            text=config.ui("Đổi", "Change"),
            command=self._change_language,
            width=72,
            height=28,
            corner_radius=8,
            fg_color=ui_foundation.COLOR_SOFT_GREEN,
            hover_color="#CFE3D6",
            text_color=ui_foundation.COLOR_TEXT,
            font=ctk.CTkFont(family="Segoe UI", size=12),
        )
        self.change_lang_button.pack(side=tk.RIGHT)
        bind_activation(self.change_lang_button)

        self.plan_card = ctk.CTkFrame(
            content,
            fg_color=ui_foundation.COLOR_SOFT_GREEN,
            corner_radius=18,
        )
        self.plan_card.pack(fill=tk.X)
        ctk.CTkLabel(
            self.plan_card,
            text=config.ui("Hôm nay", "Today's learning"),
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#5C7268",
            fg_color=ui_foundation.COLOR_SOFT_GREEN,
            anchor="w",
        ).pack(anchor="w", padx=16, pady=(14, 0))
        self.plan_headline = ctk.CTkLabel(
            self.plan_card,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color=ui_foundation.COLOR_TEXT,
            fg_color=ui_foundation.COLOR_SOFT_GREEN,
            anchor="w",
            wraplength=460,
            justify="left",
        )
        self.plan_headline.pack(anchor="w", padx=16, pady=(2, 0))
        self.plan_support = ctk.CTkLabel(
            self.plan_card,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=ui_foundation.COLOR_TEXT,
            fg_color=ui_foundation.COLOR_SOFT_GREEN,
            anchor="w",
            wraplength=460,
            justify="left",
        )
        self.plan_support.pack(anchor="w", padx=16, pady=(4, 8))
        self.start_button = ctk.CTkButton(
            self.plan_card,
            text=config.ui("Bắt đầu học", "Start learning"),
            command=self._start_study,
            height=46,
            corner_radius=14,
            fg_color=ui_foundation.COLOR_PRIMARY,
            hover_color=ui_foundation.COLOR_PRIMARY_ACTIVE,
            text_color=ui_foundation.COLOR_ON_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
        )
        self.start_button.pack(fill=tk.X, padx=16, pady=(0, 16))
        bind_activation(self.start_button)

        shortcuts = ctk.CTkFrame(content, fg_color=ui_foundation.COLOR_BG, corner_radius=0)
        shortcuts.pack(fill=tk.X, pady=(12, 0))
        self.words_button = _ShortcutCard(
            shortcuts,
            config.ui("Từ", "Words"),
            config.ui("Kho từ của bạn", "Your library"),
            self._open_vocabulary,
        )
        self.progress_button = _ShortcutCard(
            shortcuts,
            config.ui("Tiến độ", "Progress"),
            config.ui("Xem quá trình học", "See your progress"),
            self._open_progress,
        )
        self.words_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        self.progress_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0))

        quiet = ctk.CTkFrame(content, fg_color=ui_foundation.COLOR_BG, corner_radius=0)
        quiet.pack(fill=tk.X, pady=(8, 0))
        self.add_word_button = self._quiet_button(
            quiet, config.ui("Thêm từ", "Add word"), self._add_words
        )
        self.add_word_button.pack(side=tk.LEFT, padx=(0, 8))
        self.mistake_button = self._quiet_button(
            quiet, config.ui("Sổ lỗi", "Mistake Book"), self._open_mistake_book
        )
        self.mistake_button.pack(side=tk.LEFT)

        self.account_chip = ctk.CTkLabel(
            meta,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#5C7268",
            fg_color=ui_foundation.COLOR_BG,
            anchor="w",
        )
        self.account_chip.pack(side=tk.LEFT)
        self.sync_chip = ctk.CTkButton(
            meta,
            text="Cloud Sync",
            command=self._open_settings,
            height=28,
            corner_radius=8,
            fg_color="#EFEAE2",
            hover_color="#E6DFD4",
            text_color=ui_foundation.COLOR_TEXT,
            font=ctk.CTkFont(family="Segoe UI", size=12),
        )
        self.sync_chip.pack(side=tk.RIGHT)
        bind_activation(self.sync_chip)

        from account_panel import AccountPanel, AccountSyncStatusPoller

        self.account_panel = AccountPanel(
            self.root,
            on_session_changed=self._on_account_session_changed,
            allow_logout=True,
        )
        self.account_panel.on_refreshed = self._apply_sync_status
        self._sync_status_poller = AccountSyncStatusPoller(
            self.root, self.account_panel
        )
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

    def _nav_button(self, parent, icon: str, text: str, command, *, selected: bool = False):
        bg = ui_foundation.COLOR_SOFT_GREEN if selected else ui_foundation.COLOR_BG
        button = ctk.CTkButton(
            parent,
            text=f"{icon}  {text}",
            command=command,
            width=100,
            height=36,
            corner_radius=10,
            fg_color=bg,
            hover_color=ui_foundation.COLOR_SOFT_GREEN,
            text_color=ui_foundation.COLOR_TEXT,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold" if selected else "normal"),
        )
        bind_activation(button)
        return button

    def _quiet_button(self, parent, text: str, command):
        button = ctk.CTkButton(
            parent,
            text=text,
            command=command,
            width=120,
            height=30,
            corner_radius=8,
            fg_color="transparent",
            hover_color=ui_foundation.COLOR_SOFT_GREEN,
            text_color=ui_foundation.COLOR_TEXT,
            font=ctk.CTkFont(family="Segoe UI", size=13),
        )
        bind_activation(button)
        return button

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
        if not self._owned_callbacks or self._in_plan_refresh:
            return
        self._in_plan_refresh = True
        try:
            self._refresh_plan()
        finally:
            self._in_plan_refresh = False

    def _refresh_plan(self):
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
            self.greeting_label.configure(text=config.ui("Học hôm nay", "Today's Study"))
            self.language_label.configure(text=config.language_name(code))
            self.plan_headline.configure(
                text=config.ui("Chưa tính được kế hoạch.", "Could not build today's plan.")
            )
            self.plan_support.configure(text="")
            self.start_button.configure(text=config.ui("Bắt đầu học", "Start learning"))
            self._redraw_plan_card()
            self._sync_settings_controls()
            return

        self._view = build_home_view_model(
            self._plan,
            config.language_name(code),
            study_language_count=len(config.study_codes()),
        )
        self._apply_view(self._view)

    def _apply_view(self, view: HomeViewModel):
        self.greeting_label.configure(text=view.greeting)
        self.language_label.configure(text=view.language_label)
        if view.can_change_language:
            self.change_lang_button.configure(state="normal")
        else:
            self.change_lang_button.configure(state="disabled")
        self.plan_headline.configure(text=view.plan_headline)
        self.plan_support.configure(text=view.plan_support)
        self.start_button.configure(text=view.primary_action_label)
        self._refresh_account_chip()
        self._redraw_plan_card()
        self._sync_settings_controls()

    def _refresh_account_chip(self) -> None:
        import account_session

        if account_session.is_signed_in():
            text = config.ui(
                f"Tài khoản · {account_session.account_display_name()}",
                f"Account · {account_session.account_display_name()}",
            )
        else:
            text = config.ui("Tài khoản · trên máy này", "Account · on this PC")
        self.account_chip.configure(text=text)

    def _current_sync_text(self) -> tuple[str, str]:
        import account_session

        try:
            return account_session.describe_cloud_sync()
        except Exception:
            return "Unknown", ""

    def _apply_sync_status(self, label: str, detail: str) -> None:
        self._sync_detail_text = detail or label
        kind = ui_foundation.sync_status_kind(label)
        bg, fg = ui_foundation.sync_status_colors(kind)
        try:
            self.sync_chip.configure(
                text=f"Cloud Sync · {label}",
                fg_color=bg,
                hover_color=bg,
                text_color=fg,
            )
        except tk.TclError:
            return
        self._refresh_visible_account_panel()
        self._sync_settings_controls()
        if self._owned_callbacks and not self._in_plan_refresh:
            self.refresh()

    def _refresh_visible_account_panel(self) -> None:
        """Copy the polled account/sync state onto the open Settings panel."""
        if self._refreshing_visible_account:
            return
        panel = getattr(self, "_settings_account_panel", None)
        if panel is None or panel is getattr(self, "account_panel", None):
            return
        frame = getattr(panel, "frame", None)
        try:
            if frame is None or not frame.winfo_exists():
                return
        except tk.TclError:
            return
        self._refreshing_visible_account = True
        try:
            panel.refresh(notify=False)
        except tk.TclError:
            pass
        finally:
            self._refreshing_visible_account = False

    def _redraw_plan_card(self) -> None:
        card = getattr(self, "plan_card", None)
        redraw = getattr(card, "redraw", None)
        if not callable(redraw):
            return
        try:
            redraw()
        except tk.TclError:
            pass

    def _sync_settings_controls(self) -> None:
        dialog = getattr(self, "_settings_dialog", None)
        if dialog is None:
            return
        try:
            if not dialog.winfo_exists():
                return
        except tk.TclError:
            return
        reading = getattr(self, "_reading_var", None)
        listening = getattr(self, "_listening_var", None)
        if reading is not None:
            reading.set(bool(config.activity_enabled("reading")))
        if listening is not None:
            listening.set(bool(config.activity_enabled("listening")))
        label = getattr(self, "_settings_sync_label", None)
        if label is not None:
            try:
                label.config(text=self._sync_detail_text)
            except tk.TclError:
                pass
    def _open_tracked_dialog(self, attr: str, opener):
        existing = getattr(self, attr, None)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.lift()
                    return existing
            except tk.TclError:
                pass
        window = opener()
        setattr(self, attr, window)
        return window

    def _open_vocab_conflicts(self):
        from sync_conflict_app import open_sync_conflicts

        return self._open_tracked_dialog(
            "_vocab_conflict_window",
            lambda: open_sync_conflicts(self.root, on_resolved=self.refresh),
        )

    def _open_prefs_conflicts(self):
        from prefs_conflict_app import open_prefs_conflict

        return self._open_tracked_dialog(
            "_prefs_conflict_window",
            lambda: open_prefs_conflict(self.root, on_resolved=self.refresh),
        )

    # ---------- actions ----------

    def _close_account_bound_windows(self):
        """Dispose Vocabulary / Progress / Mistake Book before exposing a new session."""
        import account_session

        account_session.close_account_bound_windows(
            self.bank_window,
            self.mistake_window,
            self.progress_window,
            self._vocab_conflict_window,
            self._prefs_conflict_window,
        )
        self.bank_window = None
        self.mistake_window = None
        self.progress_window = None
        self._vocab_conflict_window = None
        self._prefs_conflict_window = None

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
        existing = getattr(self, "_settings_dialog", None)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.lift()
                    return
            except tk.TclError:
                pass
        dialog = tk.Toplevel(self.root)
        self._settings_dialog = dialog
        dialog.title(config.ui("Cài đặt học", "Study settings"))
        dialog.transient(self.root)
        dialog.resizable(False, False)
        frame = tk.Frame(dialog, bg=ui_foundation.COLOR_BG, padx=16, pady=16)
        frame.pack(fill=tk.BOTH, expand=True)
        ui_foundation.label(
            frame,
            config.ui("Phần tùy chọn", "Optional parts"),
            font=ui_foundation.FONT_CARD_TITLE,
        ).pack(anchor="w", pady=(0, 8))
        reading_var = tk.BooleanVar(value=config.activity_enabled("reading"))
        listening_var = tk.BooleanVar(value=config.activity_enabled("listening"))
        self._reading_var = reading_var
        self._listening_var = listening_var

        def on_reading_toggle():
            config.set_activity_enabled("reading", bool(reading_var.get()))
            self.refresh()

        def on_listening_toggle():
            config.set_activity_enabled("listening", bool(listening_var.get()))
            self.refresh()

        tk.Checkbutton(
            frame,
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
            frame,
            text=config.ui("Nghe", "Listening"),
            variable=listening_var,
            command=on_listening_toggle,
            bg=ui_foundation.COLOR_BG,
            fg=ui_foundation.COLOR_TEXT,
            activebackground=ui_foundation.COLOR_BG,
            selectcolor=ui_foundation.COLOR_SOFT_GREEN,
            font=ui_foundation.FONT_BODY,
        ).pack(anchor="w", pady=(4, 8))
        self._settings_sync_label = ui_foundation.label(
            frame, self._sync_detail_text, font=ui_foundation.FONT_SMALL
        )
        self._settings_sync_label.pack(anchor="w", pady=(0, 8))
        from account_panel import AccountPanel

        dialog_panel = AccountPanel(
            frame,
            on_session_changed=self._on_account_session_changed,
            allow_logout=True,
        )
        self._settings_account_panel = dialog_panel
        dialog_panel.pack(fill=tk.X, pady=(0, 8))
        ui_foundation.quiet_button(
            frame,
            config.ui("Mã thoát khẩn cấp", "Emergency code"),
            lambda: self._emergency_code(dialog),
        ).pack(anchor="w", pady=(4, 0))
        ui_foundation.quiet_button(
            frame,
            config.ui("Xung đột đồng bộ", "Sync conflicts"),
            self._open_vocab_conflicts,
        ).pack(anchor="w", pady=(8, 0))
        ui_foundation.quiet_button(
            frame,
            config.ui("Xung đột tùy chọn", "Preference conflict"),
            self._open_prefs_conflicts,
        ).pack(anchor="w", pady=(4, 0))
        self._sync_settings_controls()

        def close():
            self._settings_dialog = None
            self._settings_account_panel = None
            self._reading_var = None
            self._listening_var = None
            self._settings_sync_label = None
            dialog.destroy()

        dialog.protocol("WM_DELETE_WINDOW", close)
        ui_foundation.quiet_button(frame, config.ui("Đóng", "Close"), close).pack(
            anchor="e", pady=(12, 0)
        )

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
