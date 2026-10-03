"""Home Dashboard v1 — FreeHome learning dashboard.

Uses DailyStudyPlan (Phase 9) and launches StudyMaster/StudySession (Phase 10).
No ScreenGuard. No learning-algorithm logic in the UI.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import config
import ui_common
from daily_study import plan_for_language
from home_viewmodel import HomeViewModel, build_home_view_model


class FreeHome:
    """Manual-launch dashboard: plan preview + start study + quick actions."""

    def __init__(self, root: tk.Tk):
        ui_common.reset_window(root)
        self.root = root
        self.bank_window = None
        self.mistake_window = None
        self._plan = None
        self._view: HomeViewModel | None = None

        self.root.title(config.APP_NAME)
        self.root.geometry("560x620")
        self.root.minsize(480, 520)
        self.root.resizable(True, True)
        try:
            self.root.configure(bg=ui_common.COLOR_BG)
        except tk.TclError:
            pass
        ui_common.apply_theme(root)
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)

        shell = ttk.Frame(root, padding=ui_common.PAD_PAGE)
        shell.pack(fill=tk.BOTH, expand=True)

        # Header
        header = ttk.Frame(shell)
        header.pack(fill=tk.X)
        ttk.Label(header, text=config.APP_NAME, style="Page.TLabel").pack(side=tk.LEFT)
        ttk.Button(
            header,
            text=config.ui("Cài đặt học", "Study settings"),
            style="Small.TButton",
            command=self._open_settings,
        ).pack(side=tk.RIGHT)

        self.greeting_label = ttk.Label(shell, text="", style="Muted.TLabel")
        self.greeting_label.pack(anchor="w", pady=(ui_common.GAP_SECTION, 4))

        lang_row = ttk.Frame(shell)
        lang_row.pack(fill=tk.X, pady=(0, ui_common.GAP_SECTION))
        self.language_label = ttk.Label(lang_row, text="", style="H2.TLabel")
        self.language_label.pack(side=tk.LEFT)
        self.change_lang_button = ttk.Button(
            lang_row,
            text=config.ui("Đổi", "Change"),
            style="Small.TButton",
            command=self._change_language,
        )
        self.change_lang_button.pack(side=tk.RIGHT)

        # Today's Study card
        self.plan_card = ttk.LabelFrame(
            shell,
            text=config.ui("Học hôm nay", "Today's Study"),
            style="Card.TLabelframe",
            padding=ui_common.PAD_CARD,
        )
        self.plan_card.pack(fill=tk.X, pady=(0, ui_common.GAP_SECTION))

        metrics = ttk.Frame(self.plan_card)
        metrics.pack(fill=tk.X, pady=(0, 10))
        self.due_metric = ttk.Label(metrics, text="", style="Metric.TLabel")
        self.due_metric.pack(side=tk.LEFT, padx=(0, 18))
        self.new_metric = ttk.Label(metrics, text="", style="Metric.TLabel")
        self.new_metric.pack(side=tk.LEFT, padx=(0, 18))
        self.attention_metric = ttk.Label(metrics, text="", style="Metric.TLabel")
        self.attention_metric.pack(side=tk.LEFT)

        self.vocab_plan_label = ttk.Label(self.plan_card, text="", style="Muted.TLabel")
        self.vocab_plan_label.pack(anchor="w")
        self.reading_state_label = ttk.Label(self.plan_card, text="", style="Muted.TLabel")
        self.reading_state_label.pack(anchor="w", pady=(2, 12))

        self.empty_hint = ttk.Label(
            self.plan_card, text="", style="Muted.TLabel", wraplength=460
        )
        self.empty_hint.pack(anchor="w")

        self.start_button = ttk.Button(
            self.plan_card,
            text="",
            style="Primary.TButton",
            command=self._start_study,
        )
        self.start_button.pack(fill=tk.X, pady=(8, 0))

        # Quick access
        quick = ttk.LabelFrame(
            shell,
            text=config.ui("Truy cập nhanh", "Quick access"),
            padding=ui_common.PAD_CARD,
        )
        quick.pack(fill=tk.X)
        row1 = ttk.Frame(quick)
        row1.pack(fill=tk.X, pady=2)
        ttk.Button(
            row1,
            text=config.ui("Kho từ", "Vocabulary"),
            style="Secondary.TButton",
            command=self._open_vocabulary,
        ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 6))
        ttk.Button(
            row1,
            text=config.ui("Sổ lỗi", "Mistake Book"),
            style="Secondary.TButton",
            command=self._open_mistake_book,
        ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(6, 0))
        row2 = ttk.Frame(quick)
        row2.pack(fill=tk.X, pady=(8, 2))
        ttk.Button(
            row2,
            text=config.ui("Thêm từ", "Add words"),
            style="Secondary.TButton",
            command=self._add_words,
        ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 6))
        ttk.Button(
            row2,
            text=config.ui("Cài đặt học", "Study settings"),
            style="Secondary.TButton",
            command=self._open_settings,
        ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(6, 0))

        ttk.Label(
            shell,
            text=config.ui(
                "Làm bài sẽ mở phiên học có khóa màn hình khi bật.",
                "Study opens a locked session when lock mode is enabled.",
            ),
            style="Muted.TLabel",
            wraplength=480,
        ).pack(anchor="w", pady=(ui_common.GAP_SECTION, 0))

        self.refresh()

    # ---------- plan / view ----------

    def refresh(self):
        """Recompute DailyStudyPlan for the active language and redraw."""
        code = config.active_code()
        try:
            self._plan = plan_for_language(code)
        except Exception:
            self._plan = None
        if self._plan is None:
            self.greeting_label.config(text=config.ui("Học hôm nay", "Today's Study"))
            self.language_label.config(text=config.language_name(code))
            self.due_metric.config(text="—")
            self.new_metric.config(text="—")
            self.attention_metric.config(text="—")
            self.vocab_plan_label.config(
                text=config.ui("Chưa tính được kế hoạch.", "Could not build today's plan.")
            )
            self.reading_state_label.config(text="")
            self.empty_hint.config(text="")
            self.start_button.config(
                text=config.ui("Bắt đầu học hôm nay", "Start today's study")
            )
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
            self.change_lang_button.state(["!disabled"])
        else:
            self.change_lang_button.state(["disabled"])

        self.due_metric.config(text=view.due_label)
        self.new_metric.config(text=view.new_label)
        self.attention_metric.config(text=view.attention_label)
        self.vocab_plan_label.config(text=view.vocab_plan_label)
        self.reading_state_label.config(text=view.reading_label)
        self.start_button.config(text=view.primary_action_label)

        if view.empty_vocab:
            self.empty_hint.config(
                text=config.ui(
                    "Kho từ đang trống. Hãy thêm từ trước khi học, "
                    "hoặc bắt đầu phiên nếu chỉ muốn phần đọc (khi đang bật).",
                    "Your word list is empty. Add words before studying, "
                    "or start a session if only optional reading is enabled.",
                )
            )
        elif view.due_is_zero:
            self.empty_hint.config(
                text=config.ui(
                    f"Không có từ đến hạn — phiên vẫn hỏi tối đa {view.planned_vocab_count} câu.",
                    f"Nothing due — the session still asks up to {view.planned_vocab_count} answers.",
                )
            )
        else:
            self.empty_hint.config(text="")

    # ---------- actions ----------

    def _start_study(self):
        self.refresh()  # avoid stale plan before launch
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

    def _open_settings(self):
        dialog = tk.Toplevel(self.root)
        dialog.title(config.ui("Cài đặt học", "Study settings"))
        dialog.resizable(False, False)
        dialog.transient(self.root)
        frame = ttk.Frame(dialog, padding=16)
        frame.pack()
        ttk.Label(
            frame,
            text=config.ui("Phần tùy chọn", "Optional parts"),
            style="H2.TLabel",
        ).pack(anchor="w", pady=(0, 8))
        reading_var = tk.BooleanVar(value=config.activity_enabled("reading"))

        def on_toggle():
            config.set_activity_enabled("reading", bool(reading_var.get()))
            self.refresh()

        ttk.Checkbutton(
            frame,
            text=config.ui("Đọc", "Reading"),
            variable=reading_var,
            command=on_toggle,
        ).pack(anchor="w")
        ttk.Label(
            frame,
            text=config.ui(
                "Ngôn ngữ học và khóa màn hình được quản lý trong phiên học.",
                "Study languages and lock mode are managed inside the study session.",
            ),
            style="Muted.TLabel",
            wraplength=360,
        ).pack(anchor="w", pady=(12, 0))
        ttk.Button(
            frame, text=config.ui("Đóng", "Close"), command=dialog.destroy
        ).pack(anchor="e", pady=(14, 0))
        dialog.geometry("+%d+%d" % (self.root.winfo_rootx() + 40, self.root.winfo_rooty() + 40))

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
        MistakeBookApp(self.mistake_window, language_code=code)
        self.mistake_window.bind("<Destroy>", lambda _e: self.root.after(80, self.refresh), add="+")

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
        self._library_app = VocabularyLibraryApp(
            self.bank_window, language_code=code, focus_add=focus_add
        )
        self.bank_window.bind("<Destroy>", lambda _e: self.root.after(80, self.refresh), add="+")

    def _close_bank(self):
        if self.bank_window is not None and self.bank_window.winfo_exists():
            self.bank_window.destroy()

    def _close_mistake_book(self):
        if self.mistake_window is not None and self.mistake_window.winfo_exists():
            self.mistake_window.destroy()
