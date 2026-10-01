"""Mistake Book v1 — màn hình xem từ cần chú ý (đọc từ AttemptHistory)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import config
import ui_common
from mistake_book import (
    STATUS_HINT,
    STATUS_NEAR,
    STATUS_WRONG,
    MistakeSummary,
    attention_status,
    load_mistake_summaries,
    practice_target,
    resolve_practice_entries,
)
from progress import Progress
from vocab_store import VocabStore


def status_label(summary: MistakeSummary) -> str:
    """Localized label from verdict / hint_used — no AI copy."""
    key = attention_status(summary.last_verdict, summary.last_hint_used)
    if key == STATUS_HINT:
        return config.ui("Đã xem gợi ý", "Used a hint")
    if key == STATUS_NEAR:
        return config.ui("Gần đúng", "Almost correct")
    if key == STATUS_WRONG:
        return config.ui("Sai", "Wrong")
    return config.ui("Cần chú ý", "Needs attention")


def format_item_lines(summary: MistakeSummary) -> list[str]:
    """Pure view-model lines for one list row (testable without Tk)."""
    return [
        summary.word,
        summary.prompt,
        config.ui(
            f"Bạn trả lời: {summary.last_user_answer or '—'}",
            f"Your answer: {summary.last_user_answer or '—'}",
        ),
        config.ui(
            f"Đáp án: {summary.expected_answer or '—'}",
            f"Expected: {summary.expected_answer or '—'}",
        ),
        config.ui(
            f"Cần chú ý: {summary.attention_count} lần · {status_label(summary)}",
            f"Needs attention: {summary.attention_count}× · {status_label(summary)}",
        ),
        summary.last_timestamp,
    ]


class MistakeBookApp:
    """Cửa sổ Mistake Book — reload mỗi lần mở / bấm Làm mới."""

    def __init__(self, window: tk.Misc, language_code: str = None):
        self.window = window
        self.language_code = language_code or config.active_code()
        config.set_language(self.language_code)

        self.window.title(
            f"{config.APP_NAME} — " + config.ui("Sổ lỗi", "Mistake Book")
        )
        ui_common.apply_theme(window)
        try:
            self.window.geometry("560x520")
            self.window.minsize(480, 360)
        except tk.TclError:
            pass

        self.practice_window = None
        self._practice_entries: list = []
        self._info_label = None

        self.root = ttk.Frame(window, padding=20)
        self.root.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(self.root)
        header.pack(fill=tk.X)
        ttk.Label(
            header, text=config.ui("Sổ lỗi", "Mistake Book"), style="Title.TLabel"
        ).pack(side=tk.LEFT)
        ttk.Button(
            header,
            text=config.ui("Làm mới", "Refresh"),
            style="Small.TButton",
            command=self.refresh,
        ).pack(side=tk.RIGHT)

        self.meta_label = ttk.Label(self.root, text="", style="Muted.TLabel")
        self.meta_label.pack(anchor="w", pady=(8, 4))

        self.info_label = ttk.Label(self.root, text="", style="Muted.TLabel", wraplength=480)
        self.info_label.pack(anchor="w", pady=(0, 8))

        self.scroll = ui_common.ScrollableFrame(self.root)
        self.scroll.pack(fill=tk.BOTH, expand=True)

        self.empty_label = ttk.Label(
            self.root,
            text="",
            style="Muted.TLabel",
            wraplength=480,
            justify="left",
        )

        footer = ttk.Frame(self.root)
        footer.pack(fill=tk.X, pady=(12, 0))
        self.practice_button = ttk.Button(
            footer,
            text=config.ui("Luyện từ lỗi", "Practice mistakes"),
            command=self._start_practice,
        )
        self.practice_button.pack(side=tk.LEFT)
        ttk.Button(
            footer, text=config.ui("Đóng", "Close"), command=self.window.destroy
        ).pack(side=tk.RIGHT)

        self.refresh()

    def refresh(self):
        for child in self.scroll.body.winfo_children():
            child.destroy()
        self.empty_label.pack_forget()
        self.info_label.config(text="")

        path = config.attempts_path(self.language_code)
        summaries = load_mistake_summaries(path, language_code=self.language_code)
        store = VocabStore(config.vocab_path(self.language_code))
        self._practice_entries = resolve_practice_entries(summaries, store.all())

        lang_name = config.language_name(self.language_code)
        self.meta_label.config(
            text=config.ui(
                f"{lang_name} · {len(summaries)} từ cần chú ý",
                f"{lang_name} · {len(summaries)} words need attention",
            )
        )

        if not summaries:
            self.practice_button.state(["disabled"])
            self.empty_label.config(
                text=config.ui(
                    "Chưa có từ nào cần chú ý.\n"
                    "Hãy tiếp tục học — những từ khó sẽ xuất hiện ở đây.",
                    "No vocabulary needs attention yet.\n"
                    "Keep studying and your difficult words will appear here.",
                )
            )
            self.empty_label.pack(anchor="w", pady=20)
            return

        if not self._practice_entries:
            self.practice_button.state(["disabled"])
            self.info_label.config(
                text=config.ui(
                    "Các từ trong sổ lỗi không còn trong kho từ hiện tại, "
                    "nên chưa luyện được. Hãy thêm lại từ hoặc học tiếp.",
                    "Listed words are no longer in the current vocabulary, "
                    "so practice isn’t available. Re-add them or keep studying.",
                )
            )
        else:
            self.practice_button.state(["!disabled"])
            skipped = len(summaries) - len(self._practice_entries)
            if skipped > 0:
                self.info_label.config(
                    text=config.ui(
                        f"{skipped} từ trong lịch sử không còn trong kho — sẽ bỏ qua khi luyện.",
                        f"{skipped} history word(s) missing from vocabulary — skipped in practice.",
                    )
                )

        for summary in summaries:
            self._add_row(summary)

    def _start_practice(self):
        if self.practice_window is not None and self.practice_window.winfo_exists():
            self.practice_window.lift()
            return

        # Re-resolve in case vocab changed since last refresh.
        path = config.attempts_path(self.language_code)
        summaries = load_mistake_summaries(path, language_code=self.language_code)
        store = VocabStore(config.vocab_path(self.language_code))
        entries = resolve_practice_entries(summaries, store.all())
        self._practice_entries = entries
        if not entries:
            self.practice_button.state(["disabled"])
            self.info_label.config(
                text=config.ui(
                    "Không có từ nào trong kho để luyện lúc này.",
                    "No vocabulary entries are available to practice right now.",
                )
            )
            return

        from quiz_app import VocabQuizApp

        target = practice_target(len(entries))
        progress = Progress(config.progress_path(self.language_code))
        self.practice_window = tk.Toplevel(self.window)
        VocabQuizApp(
            self.practice_window,
            progress=progress,
            quiz_entries=entries,
            target=target,
            language_code=self.language_code,
            required=False,
            locked=False,
            allow_manage=False,
            window_title=config.ui("Luyện từ lỗi", "Practice mistakes"),
            on_closed=self._on_practice_closed,
        )

    def _on_practice_closed(self):
        self.practice_window = None
        try:
            if self.window.winfo_exists():
                self.refresh()
        except tk.TclError:
            pass

    def _add_row(self, summary: MistakeSummary):
        card = ttk.Frame(self.scroll.body, padding=(0, 0, 0, 14))
        card.pack(fill=tk.X, anchor="w")

        ttk.Label(card, text=summary.word, style="H2.TLabel").pack(anchor="w")
        if summary.prompt:
            ttk.Label(card, text=summary.prompt, style="Muted.TLabel").pack(anchor="w")

        ttk.Label(
            card,
            text=config.ui(
                f"Bạn trả lời: {summary.last_user_answer or '—'}",
                f"Your answer: {summary.last_user_answer or '—'}",
            ),
            style="Muted.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            card,
            text=config.ui(
                f"Đáp án: {summary.expected_answer or '—'}",
                f"Expected: {summary.expected_answer or '—'}",
            ),
            style="Muted.TLabel",
        ).pack(anchor="w")

        key = attention_status(summary.last_verdict, summary.last_hint_used)
        if key == STATUS_WRONG:
            status_color = ui_common.COLOR_BAD
        elif key == STATUS_NEAR:
            status_color = ui_common.COLOR_WARN
        else:
            status_color = ui_common.COLOR_ACCENT
        ttk.Label(
            card,
            text=config.ui(
                f"Cần chú ý: {summary.attention_count} lần · {status_label(summary)}",
                f"Needs attention: {summary.attention_count}× · {status_label(summary)}",
            ),
            foreground=status_color,
            font=ui_common.FONT_SMALL,
        ).pack(anchor="w")
        if summary.last_timestamp:
            ttk.Label(
                card, text=summary.last_timestamp, style="Muted.TLabel"
            ).pack(anchor="w")

        ttk.Separator(card, orient="horizontal").pack(fill=tk.X, pady=(10, 0))
