"""Vocabulary Library v2 + Word Detail v1 — learner-facing browse/edit UI."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

import config
import ui_common
from progress import Progress
from text_utils import entry_word, normalize
from vocabulary_model import entry_alternatives, entry_example, entry_meaning
from vocabulary_library import (
    FILTER_ALL,
    FILTER_ATTENTION,
    FILTER_DUE,
    FILTER_NEW,
    VocabularyDetail,
    VocabularyListItem,
    attention_status_label,
    attempt_status_label,
    build_vocabulary_detail,
    due_status_label,
    filter_vocabulary_items,
    format_list_subtitle,
    load_vocabulary_library,
    mastery_rate_label,
)
from vocab_store import VocabStore


class VocabularyLibraryApp:
    """Browse/search vocabulary, open Word Detail, add/edit/delete via VocabStore."""

    def __init__(self, window: tk.Misc, language_code: str = None, focus_add: bool = False):
        self.window = window
        self.language_code = language_code or config.active_code()
        config.set_language(self.language_code)
        self.focus_add = focus_add

        self.items: list[VocabularyListItem] = []
        self.visible: list[VocabularyListItem] = []
        self.store: VocabStore | None = None
        self.progress: Progress | None = None
        self.attempts = []
        self.summaries = []
        self.detail_window = None

        self.window.title(
            f"{config.APP_NAME} — "
            + config.ui("Kho từ", "Vocabulary")
            + f" · {config.language_name(self.language_code)}"
        )
        ui_common.apply_theme(window)
        try:
            self.window.geometry("640x560")
            self.window.minsize(520, 420)
            self.window.configure(bg=ui_common.COLOR_BG)
        except tk.TclError:
            pass

        root = ttk.Frame(window, padding=ui_common.PAD_PAGE)
        root.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(root)
        header.pack(fill=tk.X)
        ttk.Label(
            header,
            text=config.ui(
                f"Kho từ — {config.language_name(self.language_code)}",
                f"Vocabulary — {config.language_name(self.language_code)}",
            ),
            style="Page.TLabel",
        ).pack(side=tk.LEFT)
        ttk.Button(
            header,
            text=config.ui("Thêm từ", "Add word"),
            style="Primary.TButton",
            command=self._add_word_dialog,
        ).pack(side=tk.RIGHT)

        self.count_label = ttk.Label(root, text="", style="Muted.TLabel")
        self.count_label.pack(anchor="w", pady=(8, 8))

        tools = ttk.Frame(root)
        tools.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(tools, text=config.ui("Tìm:", "Search:")).pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._apply_filters())
        search = ttk.Entry(tools, textvariable=self.search_var, font=ui_common.FONT_BODY)
        search.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        self.filter_var = tk.StringVar()
        filter_box = ttk.Combobox(
            tools,
            textvariable=self.filter_var,
            state="readonly",
            width=18,
        )
        filter_box.pack(side=tk.LEFT)
        self._localize_filter_box(filter_box)
        filter_box.bind("<<ComboboxSelected>>", lambda _e: self._apply_filters())

        list_frame = ttk.Frame(root)
        list_frame.pack(fill=tk.BOTH, expand=True)
        self.listbox = tk.Listbox(list_frame, font=ui_common.FONT_BODY, activestyle="none")
        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scroll.set)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.bind("<Double-Button-1>", self._open_selected_detail)
        self.listbox.bind("<Return>", self._open_selected_detail)

        self.empty_label = ttk.Label(
            root, text="", style="Muted.TLabel", wraplength=560, justify="left"
        )

        footer = ttk.Frame(root)
        footer.pack(fill=tk.X, pady=(12, 0))
        ttk.Button(
            footer,
            text=config.ui("Mở chi tiết", "Open detail"),
            style="Secondary.TButton",
            command=self._open_selected_detail,
        ).pack(side=tk.LEFT)
        ttk.Button(
            footer, text=config.ui("Đóng", "Close"), command=self.window.destroy
        ).pack(side=tk.RIGHT)

        self.reload()
        if focus_add:
            self.window.after(120, self._add_word_dialog)

    def _localize_filter_box(self, box: ttk.Combobox):
        labels = {
            FILTER_ALL: config.ui("Tất cả", "All"),
            FILTER_DUE: config.ui("Đến hạn", "Due"),
            FILTER_NEW: config.ui("Mới", "New"),
            FILTER_ATTENTION: config.ui("Cần chú ý", "Needs attention"),
        }
        self._filter_labels = labels
        self._filter_keys = {v: k for k, v in labels.items()}
        box.configure(values=list(labels.values()))
        self.filter_var.set(labels[FILTER_ALL])

    def _current_filter_key(self) -> str:
        label = self.filter_var.get()
        return self._filter_keys.get(label, FILTER_ALL)

    def reload(self):
        items, store, progress, attempts, summaries = load_vocabulary_library(
            self.language_code
        )
        self.items = items
        self.store = store
        self.progress = progress
        self.attempts = attempts
        self.summaries = summaries
        self._apply_filters()

    def _apply_filters(self):
        if self.store is None:
            return
        self.visible = filter_vocabulary_items(
            self.items,
            query=self.search_var.get(),
            filter_key=self._current_filter_key(),
            vocab_entries=self.store.all(),
        )
        self.listbox.delete(0, tk.END)
        for item in self.visible:
            subtitle = format_list_subtitle(item)
            self.listbox.insert(
                tk.END, f"{item.word}  —  {item.prompt}    ({subtitle})"
            )
        total = len(self.items)
        shown = len(self.visible)
        self.count_label.config(
            text=config.ui(
                f"{total} từ · đang hiện {shown}",
                f"{total} words · showing {shown}",
            )
        )
        if total == 0:
            self.empty_label.config(
                text=config.ui(
                    "Kho từ đang trống. Hãy thêm từ đầu tiên.",
                    "This vocabulary list is empty. Add your first word.",
                )
            )
            self.empty_label.pack(anchor="w", pady=(8, 0))
        elif shown == 0:
            self.empty_label.config(
                text=config.ui(
                    "Không có từ khớp bộ lọc / tìm kiếm.",
                    "No words match this search or filter.",
                )
            )
            self.empty_label.pack(anchor="w", pady=(8, 0))
        else:
            self.empty_label.pack_forget()

    def _selected_item(self) -> VocabularyListItem | None:
        selection = self.listbox.curselection()
        if not selection:
            return None
        return self.visible[selection[0]]

    def _open_selected_detail(self, _event=None):
        item = self._selected_item()
        if item is None:
            return
        self._open_detail(item.store_index)

    def _open_detail(self, store_index: int):
        if self.store is None or self.progress is None:
            return
        entry = self.store.get(store_index)
        if not entry:
            return
        detail = build_vocabulary_detail(
            entry,
            store_index,
            language_code=self.language_code,
            progress_words=self.progress.data.get("words") or {},
            attempts=self.attempts,
            mistake_summaries=self.summaries,
        )
        if self.detail_window is not None and self.detail_window.winfo_exists():
            self.detail_window.destroy()
        self.detail_window = tk.Toplevel(self.window)
        WordDetailApp(
            self.detail_window,
            detail=detail,
            store=self.store,
            language_code=self.language_code,
            on_changed=self._on_detail_changed,
        )

    def _on_detail_changed(self):
        self.reload()

    def _add_word_dialog(self):
        self._edit_dialog(mode="add")

    def open_add_dialog(self):
        """Public hook for Home “Add words” when the library is already open."""
        self._add_word_dialog()

    def _edit_dialog(self, mode: str, store_index: int = None, entry: dict = None):
        dialog = tk.Toplevel(self.window)
        dialog.title(
            config.ui("Thêm từ", "Add word")
            if mode == "add"
            else config.ui("Sửa từ", "Edit word")
        )
        dialog.resizable(False, False)
        dialog.transient(self.window)
        frame = ttk.Frame(dialog, padding=16)
        frame.pack()

        vars_map = {
            "word": tk.StringVar(value=entry_word(entry) if entry else ""),
            "meaning": tk.StringVar(value=entry_meaning(entry) if entry else ""),
            "alt": tk.StringVar(value=" | ".join(entry_alternatives(entry) if entry else [])),
            "example": tk.StringVar(value=entry_example(entry) if entry else ""),
        }
        labels = [
            ("word", config.ui("Từ:", "Word:")),
            ("meaning", config.ui("Nghĩa:", "Meaning:")),
            ("alt", config.ui("Cách viết khác (|):", "Other spellings (|):")),
            ("example", config.ui("Câu ví dụ:", "Example:")),
        ]
        entries = {}
        for row, (key, label) in enumerate(labels):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=4)
            ent = ttk.Entry(
                frame, textvariable=vars_map[key], width=36, font=ui_common.FONT_BODY
            )
            ent.grid(row=row, column=1, sticky="ew", pady=4, padx=(8, 0))
            entries[key] = ent

        status = ttk.Label(frame, text="", style="Muted.TLabel")
        status.grid(row=len(labels), column=0, columnspan=2, sticky="w", pady=(4, 0))

        def save():
            word = vars_map["word"].get().strip()
            meaning = vars_map["meaning"].get().strip()
            alt = [a.strip() for a in vars_map["alt"].get().split("|") if a.strip()]
            example = vars_map["example"].get().strip()
            extra = {"alternatives": alt, "example": example}
            if not word or not meaning:
                status.config(
                    text=config.ui(
                        "Cần có từ và nghĩa.", "Word and meaning are required."
                    )
                )
                return
            if mode == "add":
                if not self.store.add(word, meaning, **extra):
                    status.config(
                        text=config.ui(
                            "Từ đã tồn tại (sau chuẩn hóa) hoặc không lưu được.",
                            "Word already exists (after normalization) or could not be saved.",
                        )
                    )
                    return
            else:
                if not self.store.update(store_index, word, meaning, **extra):
                    status.config(
                        text=config.ui("Không lưu được.", "Could not save.")
                    )
                    return
            dialog.destroy()
            self.reload()

        buttons = ttk.Frame(frame)
        buttons.grid(row=len(labels) + 1, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(
            buttons,
            text=config.ui("Lưu", "Save"),
            style="Primary.TButton",
            command=save,
        ).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(
            buttons, text=config.ui("Hủy", "Cancel"), command=dialog.destroy
        ).pack(side=tk.LEFT)
        entries["word"].focus_set()
        dialog.bind("<Return>", lambda _e: save())


class WordDetailApp:
    """Word Detail panel with learning state, attempts, edit/delete/practice."""

    def __init__(
        self,
        window: tk.Misc,
        *,
        detail: VocabularyDetail,
        store: VocabStore,
        language_code: str,
        on_changed=None,
    ):
        self.window = window
        self.detail = detail
        self.store = store
        self.language_code = language_code
        self.on_changed = on_changed
        self.practice_window = None

        self.window.title(f"{config.APP_NAME} — {detail.word}")
        ui_common.apply_theme(window)
        try:
            self.window.geometry("520x560")
            self.window.minsize(420, 400)
            self.window.configure(bg=ui_common.COLOR_BG)
        except tk.TclError:
            pass

        self._build_body()

    def _build_body(self):
        for child in list(self.window.winfo_children()):
            try:
                child.destroy()
            except tk.TclError:
                pass

        detail = self.detail
        root = ttk.Frame(self.window, padding=ui_common.PAD_PAGE)
        root.pack(fill=tk.BOTH, expand=True)

        ttk.Label(root, text=detail.word, style="Page.TLabel").pack(anchor="w")
        ttk.Label(root, text=detail.prompt, style="H2.TLabel").pack(anchor="w", pady=(4, 8))
        if getattr(detail, "part_of_speech", ""):
            ttk.Label(
                root,
                text=config.ui(
                    f"Loại từ: {detail.part_of_speech}",
                    f"Part of speech: {detail.part_of_speech}",
                ),
                style="Muted.TLabel",
            ).pack(anchor="w")
        if detail.alt:
            ttk.Label(
                root,
                text=config.ui(
                    "Khác: " + " | ".join(detail.alt),
                    "Also: " + " | ".join(detail.alt),
                ),
                style="Muted.TLabel",
            ).pack(anchor="w")
        if getattr(detail, "pronunciation_ipa", ""):
            ttk.Label(
                root,
                text=config.ui(
                    f"Phát âm: /{detail.pronunciation_ipa}/",
                    f"Pronunciation: /{detail.pronunciation_ipa}/",
                ),
                style="Muted.TLabel",
            ).pack(anchor="w", pady=(4, 0))
        form_items = getattr(detail, "forms", ()) or ()
        if form_items:
            form_labels = {
                "plural": config.ui("Số nhiều", "Plural"),
                "past": config.ui("Quá khứ", "Past"),
                "past_participle": config.ui("Quá khứ phân từ", "Past participle"),
                "comparative": config.ui("So sánh hơn", "Comparative"),
                "superlative": config.ui("So sánh nhất", "Superlative"),
            }
            lines = [
                f"{form_labels.get(name, name)}: {value}"
                for name, value in form_items
                if value
            ]
            if lines:
                ttk.Label(
                    root,
                    text=config.ui("Dạng từ", "Forms") + " — " + " · ".join(lines),
                    style="Muted.TLabel",
                    wraplength=460,
                ).pack(anchor="w", pady=(4, 0))
        detail_examples = getattr(detail, "examples", ()) or ()
        if detail_examples:
            for item in detail_examples:
                line = item.text
                if getattr(item, "meaning", ""):
                    line = f"{item.text} — {item.meaning}"
                ttk.Label(
                    root, text=line, style="Muted.TLabel", wraplength=460
                ).pack(anchor="w", pady=(4, 0))
        elif detail.example:
            ttk.Label(
                root, text=detail.example, style="Muted.TLabel", wraplength=460
            ).pack(anchor="w", pady=(4, 0))

        card = ttk.LabelFrame(
            root,
            text=config.ui("Tiến độ học", "Learning progress"),
            style="Card.TLabelframe",
            padding=ui_common.PAD_CARD,
        )
        card.pack(fill=tk.X, pady=(ui_common.GAP_SECTION, 8))
        for line in self._progress_lines(detail):
            ttk.Label(card, text=line, style="Muted.TLabel").pack(anchor="w")

        attempts_card = ttk.LabelFrame(
            root,
            text=config.ui("Lần trả lời gần đây", "Recent attempts"),
            style="Card.TLabelframe",
            padding=ui_common.PAD_CARD,
        )
        attempts_card.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        if not detail.recent_attempts:
            ttk.Label(
                attempts_card,
                text=config.ui("Chưa có lần trả lời nào.", "No attempts yet."),
                style="Muted.TLabel",
            ).pack(anchor="w")
        else:
            scroll = ui_common.ScrollableFrame(attempts_card)
            scroll.pack(fill=tk.BOTH, expand=True)
            for attempt in detail.recent_attempts:
                block = ttk.Frame(scroll.body, padding=(0, 0, 0, 10))
                block.pack(fill=tk.X, anchor="w")
                ttk.Label(
                    block,
                    text=f"{attempt.timestamp} · {attempt_status_label(attempt)}",
                    style="Muted.TLabel",
                ).pack(anchor="w")
                ttk.Label(
                    block,
                    text=config.ui(
                        f"Bạn: {attempt.user_answer or '—'}",
                        f"You: {attempt.user_answer or '—'}",
                    ),
                ).pack(anchor="w")
                ttk.Label(
                    block,
                    text=config.ui(
                        f"Đáp án: {attempt.expected_answer or '—'}",
                        f"Expected: {attempt.expected_answer or '—'}",
                    ),
                    style="Muted.TLabel",
                ).pack(anchor="w")

        actions = ttk.Frame(root)
        actions.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(
            actions,
            text=config.ui("Luyện từ này", "Practice"),
            style="Primary.TButton",
            command=self._practice,
        ).pack(side=tk.LEFT)
        ttk.Button(
            actions,
            text=config.ui("Sửa", "Edit"),
            style="Secondary.TButton",
            command=self._edit,
        ).pack(side=tk.LEFT, padx=6)
        ttk.Button(
            actions,
            text=config.ui("Xóa", "Delete"),
            style="Secondary.TButton",
            command=self._delete,
        ).pack(side=tk.LEFT)
        ttk.Button(
            actions, text=config.ui("Đóng", "Close"), command=self.window.destroy
        ).pack(side=tk.RIGHT)

    def _progress_lines(self, detail: VocabularyDetail) -> list[str]:
        lines = [
            due_status_label(detail),
            attention_status_label(detail.needs_attention, detail.attention_count),
            config.ui(
                f"Đã gặp: {detail.seen} · Thuộc: {detail.mastered_count} · "
                f"Chưa thuộc: {detail.non_mastered_count} · Chuỗi: {detail.streak}",
                f"Seen: {detail.seen} · Mastered: {detail.mastered_count} · "
                f"Not mastered: {detail.non_mastered_count} · Streak: {detail.streak}",
            ),
            mastery_rate_label(detail.mastery_rate, detail.seen),
        ]
        if detail.interval_days is not None:
            lines.append(
                config.ui(
                    f"Khoảng cách SRS: {detail.interval_days} ngày",
                    f"SRS interval: {detail.interval_days} days",
                )
            )
        return lines

    def _practice(self):
        from quiz_app import VocabQuizApp

        entry = self.store.get(self.detail.store_index)
        if not entry:
            return
        if self.practice_window is not None and self.practice_window.winfo_exists():
            self.practice_window.lift()
            return
        progress = Progress(config.progress_path(self.language_code))
        self.practice_window = tk.Toplevel(self.window)
        VocabQuizApp(
            self.practice_window,
            progress=progress,
            quiz_entries=[entry],
            target=1,
            language_code=self.language_code,
            required=False,
            locked=False,
            allow_manage=False,
            window_title=config.ui("Luyện một từ", "Practice one word"),
            on_closed=self._on_practice_closed,
        )

    def _on_practice_closed(self):
        self.practice_window = None
        if callable(self.on_changed):
            self.on_changed()
        self._refresh_from_disk()

    def _refresh_from_disk(self):
        store = VocabStore(config.vocab_path(self.language_code))
        progress = Progress(config.progress_path(self.language_code))
        from attempt_history import AttemptHistory
        from mistake_book import summarize_mistakes

        attempts = AttemptHistory(
            config.attempts_path(self.language_code), language_code=self.language_code
        ).load_attempts()
        summaries = summarize_mistakes(attempts, language_code=self.language_code)
        from vocab_identity import entry_id

        target_id = str(getattr(self.detail, "vocab_id", "") or "")
        key = normalize(self.detail.word)
        matched_index = None
        matched_entry = None
        if target_id:
            for index, entry in enumerate(store.all()):
                if entry_id(entry) == target_id:
                    matched_index = index
                    matched_entry = entry
                    break
        if matched_entry is None:
            candidate = store.get(self.detail.store_index)
            if candidate is not None and normalize(entry_word(candidate)) == key:
                matched_index = self.detail.store_index
                matched_entry = candidate
            else:
                for index, entry in enumerate(store.all()):
                    if normalize(entry_word(entry)) == key:
                        matched_index = index
                        matched_entry = entry
                        break
        if matched_entry is None:
            self.window.destroy()
            return
        self.store = store
        self.detail = build_vocabulary_detail(
            matched_entry,
            matched_index,
            language_code=self.language_code,
            progress_words=progress.data.get("words") or {},
            attempts=attempts,
            mistake_summaries=summaries,
        )
        self._build_body()

    def _edit(self):
        entry = self.store.get(self.detail.store_index)
        if not entry:
            return
        dialog = tk.Toplevel(self.window)
        dialog.title(config.ui("Sửa từ", "Edit word"))
        dialog.resizable(False, False)
        dialog.transient(self.window)
        frame = ttk.Frame(dialog, padding=16)
        frame.pack()
        vars_map = {
            "word": tk.StringVar(value=self.detail.word),
            "meaning": tk.StringVar(value=self.detail.prompt),
            "alt": tk.StringVar(value=" | ".join(self.detail.alt)),
            "example": tk.StringVar(value=self.detail.example),
        }
        for row, (key, label) in enumerate(
            [
                ("word", config.ui("Từ:", "Word:")),
                ("meaning", config.ui("Nghĩa:", "Meaning:")),
                ("alt", config.ui("Cách viết khác (|):", "Other spellings (|):")),
                ("example", config.ui("Câu ví dụ:", "Example:")),
            ]
        ):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=4)
            ttk.Entry(frame, textvariable=vars_map[key], width=36).grid(
                row=row, column=1, sticky="ew", padx=(8, 0), pady=4
            )

        def save():
            word = vars_map["word"].get().strip()
            meaning = vars_map["meaning"].get().strip()
            alt = [a.strip() for a in vars_map["alt"].get().split("|") if a.strip()]
            example = vars_map["example"].get().strip()
            if not word or not meaning:
                return
            if self.store.update(
                self.detail.store_index,
                word,
                meaning,
                alternatives=alt,
                example=example,
            ):
                dialog.destroy()
                if callable(self.on_changed):
                    self.on_changed()
                self._refresh_from_disk()

        buttons = ttk.Frame(frame)
        buttons.grid(row=4, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(
            buttons,
            text=config.ui("Lưu", "Save"),
            style="Primary.TButton",
            command=save,
        ).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(
            buttons, text=config.ui("Hủy", "Cancel"), command=dialog.destroy
        ).pack(side=tk.LEFT)

    def _delete(self):
        entry = self.store.get(self.detail.store_index)
        if not entry:
            return
        if not messagebox.askyesno(
            config.ui("Xóa từ", "Delete word"),
            config.ui(
                f"Xóa “{self.detail.word} — {self.detail.prompt}”?\n"
                "Lịch sử học / attempts vẫn giữ lại.",
                f"Delete “{self.detail.word} — {self.detail.prompt}”?\n"
                "Learning history / attempts are kept.",
            ),
            parent=self.window,
        ):
            return
        self.store.delete(self.detail.store_index)
        if callable(self.on_changed):
            self.on_changed()
        self.window.destroy()
