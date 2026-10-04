"""Progress Dashboard v1 — read-only learning analytics UI.

Uses LearningProgressSnapshot + ProgressViewModel. No learning-algorithm logic.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import config
import ui_common
from learning_progress import load_learning_progress
from progress_viewmodel import ProgressViewModel, build_progress_view_model


class ProgressApp:
    """Learner-facing Progress screen for one study language."""

    def __init__(self, window: tk.Misc, language_code: str = None):
        self.window = window
        self.language_code = language_code or config.active_code()
        config.set_language(self.language_code)
        self._view: ProgressViewModel | None = None

        ui_common.apply_theme(window)
        try:
            window.configure(bg=ui_common.COLOR_BG)
        except tk.TclError:
            pass
        window.title(
            f"{config.APP_NAME} — {config.ui('Tiến độ', 'Progress')}"
        )
        window.geometry("560x640")
        window.minsize(480, 520)

        self.shell = ttk.Frame(window, padding=ui_common.PAD_PAGE)
        self.shell.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(self.shell)
        header.pack(fill=tk.X)
        ttk.Label(
            header, text=config.ui("Tiến độ", "Progress"), style="Page.TLabel"
        ).pack(side=tk.LEFT)
        ttk.Button(
            header,
            text=config.ui("Làm mới", "Refresh"),
            style="Small.TButton",
            command=self.refresh,
        ).pack(side=tk.RIGHT)

        lang_row = ttk.Frame(self.shell)
        lang_row.pack(fill=tk.X, pady=(ui_common.GAP_SECTION, ui_common.GAP_SECTION))
        self.language_label = ttk.Label(lang_row, text="", style="H2.TLabel")
        self.language_label.pack(side=tk.LEFT)
        self.change_lang_button = ttk.Button(
            lang_row,
            text=config.ui("Đổi", "Change"),
            style="Small.TButton",
            command=self._change_language,
        )
        self.change_lang_button.pack(side=tk.RIGHT)

        self.scroll = ui_common.ScrollableFrame(self.shell)
        self.scroll.pack(fill=tk.BOTH, expand=True)
        self.body = self.scroll.body

        footer = ttk.Frame(self.shell)
        footer.pack(fill=tk.X, pady=(ui_common.GAP_SECTION, 0))
        ttk.Button(
            footer,
            text=config.ui("Đóng", "Close"),
            command=self.window.destroy,
        ).pack(side=tk.RIGHT)

        self.refresh()

    def refresh(self):
        snapshot = load_learning_progress(self.language_code)
        self._view = build_progress_view_model(
            snapshot,
            config.language_name(self.language_code),
            study_language_count=len(config.study_codes()),
        )
        self._render(self._view)

    def _clear_body(self):
        for child in self.body.winfo_children():
            child.destroy()

    def _render(self, view: ProgressViewModel):
        self._clear_body()
        self.language_label.config(text=view.language_label)
        if view.can_change_language:
            self.change_lang_button.state(["!disabled"])
        else:
            self.change_lang_button.state(["disabled"])

        overview = ttk.LabelFrame(
            self.body,
            text=config.ui("Tổng quan", "Overview"),
            style="Card.TLabelframe",
            padding=ui_common.PAD_CARD,
        )
        overview.pack(fill=tk.X, pady=(0, ui_common.GAP_SECTION))
        for text in (
            view.total_label,
            view.practiced_label,
            view.new_label,
            view.due_label,
            view.future_label,
            view.attention_label,
        ):
            ttk.Label(overview, text=text, style="Muted.TLabel").pack(anchor="w")
        if view.overview_hint:
            ttk.Label(
                overview,
                text=view.overview_hint,
                style="Muted.TLabel",
                wraplength=460,
            ).pack(anchor="w", pady=(8, 0))

        activity = ttk.LabelFrame(
            self.body,
            text=config.ui("Hoạt động học", "Learning activity"),
            style="Card.TLabelframe",
            padding=ui_common.PAD_CARD,
        )
        activity.pack(fill=tk.X, pady=(0, ui_common.GAP_SECTION))
        ttk.Label(activity, text=view.attempts_label, style="Muted.TLabel").pack(
            anchor="w"
        )
        ttk.Label(
            activity, text=view.mastery_answers_label, style="Muted.TLabel"
        ).pack(anchor="w")
        ttk.Label(activity, text=view.mastery_rate_label, style="Muted.TLabel").pack(
            anchor="w"
        )
        if view.activity_hint:
            ttk.Label(
                activity,
                text=view.activity_hint,
                style="Muted.TLabel",
                wraplength=460,
            ).pack(anchor="w", pady=(8, 0))

        recent = ttk.LabelFrame(
            self.body,
            text=view.recent_days_title,
            style="Card.TLabelframe",
            padding=ui_common.PAD_CARD,
        )
        recent.pack(fill=tk.X, pady=(0, ui_common.GAP_SECTION))
        if view.no_attempts:
            ttk.Label(
                recent,
                text=config.ui(
                    "Chưa có hoạt động trong 7 ngày gần đây.",
                    "No activity in the last 7 days.",
                ),
                style="Muted.TLabel",
            ).pack(anchor="w")
        else:
            for row in view.recent_days:
                block = ttk.Frame(recent)
                block.pack(fill=tk.X, pady=2)
                ttk.Label(block, text=row.date_label, width=12).pack(side=tk.LEFT)
                bar_width = max(4, int(120 * row.bar_ratio)) if row.attempt_count else 4
                canvas = tk.Canvas(
                    block,
                    width=124,
                    height=10,
                    highlightthickness=0,
                    bg=ui_common.COLOR_BG,
                )
                canvas.pack(side=tk.LEFT, padx=(6, 8))
                fill = ui_common.COLOR_OK if row.attempt_count else ui_common.COLOR_MUTED
                canvas.create_rectangle(0, 1, bar_width, 9, fill=fill, width=0)
                ttk.Label(block, text=row.summary_label, style="Muted.TLabel").pack(
                    side=tk.LEFT
                )

        answers = ttk.LabelFrame(
            self.body,
            text=view.recent_attempts_title,
            style="Card.TLabelframe",
            padding=ui_common.PAD_CARD,
        )
        answers.pack(fill=tk.X)
        if not view.recent_attempts:
            ttk.Label(
                answers,
                text=config.ui("Chưa có câu trả lời gần đây.", "No recent answers."),
                style="Muted.TLabel",
            ).pack(anchor="w")
        else:
            for item in view.recent_attempts:
                block = ttk.Frame(answers, padding=(0, 0, 0, 8))
                block.pack(fill=tk.X, anchor="w")
                ttk.Label(block, text=item.word).pack(anchor="w")
                ttk.Label(
                    block,
                    text=f"{item.when_label} · {item.result_label}",
                    style="Muted.TLabel",
                ).pack(anchor="w")

    def _change_language(self):
        codes = config.study_codes()
        if len(codes) <= 1:
            return
        dialog = tk.Toplevel(self.window)
        dialog.title(config.ui("Chọn ngôn ngữ", "Choose language"))
        dialog.resizable(False, False)
        dialog.transient(self.window)
        frame = ttk.Frame(dialog, padding=16)
        frame.pack()
        ttk.Label(
            frame,
            text=config.ui(
                "Xem tiến độ ngôn ngữ nào?",
                "Progress for which language?",
            ),
        ).pack(anchor="w", pady=(0, 8))
        for code in codes:
            ttk.Button(
                frame,
                text=config.language_name(code),
                style="Secondary.TButton",
                command=lambda c=code: self._select_language(c, dialog),
            ).pack(fill=tk.X, pady=2)

    def _select_language(self, code: str, dialog: tk.Toplevel):
        dialog.destroy()
        self.language_code = code
        config.set_language(code)
        self.refresh()
