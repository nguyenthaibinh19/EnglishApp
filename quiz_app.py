"""Màn hình luyện từ vựng tiếng Hà Lan.

Ba khung dùng chung một cửa sổ: làm bài, đặt câu ví dụ (AI chấm) và quản lý từ vựng.
"""

import tkinter as tk
from tkinter import ttk

import ai_teacher
import config
import ui_common
from progress import Progress
from quiz_engine import QuizEngine
from text_utils import strip_tags
from vocab_store import VocabStore


class VocabQuizApp:
    def __init__(
        self,
        window: tk.Misc,
        store: VocabStore = None,
        progress: Progress = None,
        on_completed=None,
        on_request_switch=None,
        on_emergency=None,
    ):
        self.window = window
        self.window.title(f"{config.APP_NAME} — Woordenschat")

        self.store = store or VocabStore()
        self.progress = progress or Progress()
        self.engine = QuizEngine(self.store, self.progress)

        self.on_completed = on_completed
        self.on_request_switch = on_request_switch
        self.on_emergency = on_emergency

        self.completed = False
        self.practice_mode = None      # None | "free" | "forced"
        self._pending_action = None    # hành động đang chờ trước khi sang câu mới
        self._pending_after_id = None

        ui_common.apply_theme(window)
        self.guard = ui_common.ScreenGuard(window, on_close_attempt=self._on_close_attempt)

        if self.store.count() == 0:
            self.guard.show_error(
                "Chưa có từ vựng",
                "vocab.json đang trống.\n\n"
                'Hãy thêm từ theo mẫu: {"nl": "de fiets", "vi": "xe đạp"}',
            )
            self.window.destroy()
            return

        self._build_ui()
        self._next_question()

    # ============================================================
    # Dựng giao diện
    # ============================================================

    def _build_ui(self):
        self.container = ttk.Frame(self.window, padding=20)
        self.container.pack(fill=tk.BOTH, expand=True)

        self.quiz_view = self._build_quiz_view()
        self.practice_view = None
        self.manager_view = None
        self._show(self.quiz_view)

        # Ô nhập bị khóa lúc đang hiện đáp án, nên Enter phải bắt ở cấp cửa sổ.
        self.window.bind("<Return>", self._on_window_return)

    def _show(self, view: ttk.Frame):
        for other in (self.quiz_view, self.practice_view, self.manager_view):
            if other is not None and other is not view:
                other.pack_forget()
        view.pack(fill=tk.BOTH, expand=True)

    # ---------- Khung làm bài ----------

    def _build_quiz_view(self) -> ttk.Frame:
        view = ttk.Frame(self.container)

        header = ttk.Frame(view)
        header.pack(fill=tk.X)
        ttk.Label(header, text="Luyện từ vựng tiếng Hà Lan", style="Title.TLabel").pack(side=tk.LEFT)
        self.stats_label = ttk.Label(header, text="", style="Muted.TLabel")
        self.stats_label.pack(side=tk.RIGHT)

        self.progress_bar = ttk.Progressbar(
            view, maximum=self.engine.target, value=0, length=400
        )
        self.progress_bar.pack(fill=tk.X, pady=(12, 4))

        self.progress_label = ttk.Label(view, text="", style="Muted.TLabel")
        self.progress_label.pack(anchor="w")

        body = ttk.Frame(view)
        body.pack(fill=tk.BOTH, expand=True)

        ttk.Label(body, text="Từ tiếng Hà Lan nào có nghĩa là:", style="H2.TLabel").pack(pady=(40, 8))

        self.question_label = ttk.Label(
            body, text="", font=ui_common.FONT_QUESTION, wraplength=900, justify="center"
        )
        self.question_label.pack(pady=6)

        self.hint_label = ttk.Label(body, text="", style="Muted.TLabel")
        self.hint_label.pack(pady=4)

        self.answer_var = tk.StringVar()
        self.answer_entry = ttk.Entry(
            body, textvariable=self.answer_var, font=ui_common.FONT_ANSWER,
            width=32, justify="center",
        )
        self.answer_entry.pack(pady=14, ipady=6)
        self.answer_entry.bind("<Return>", self._on_enter)

        self.feedback_label = ttk.Label(
            body, text="", font=ui_common.FONT_BODY, wraplength=900, justify="center"
        )
        self.feedback_label.pack(pady=10)

        buttons = ttk.Frame(view)
        buttons.pack(fill=tk.X, pady=(10, 0))

        self.submit_button = ttk.Button(buttons, text="Trả lời", command=self._submit)
        self.submit_button.pack(side=tk.LEFT)

        self.hint_button = ttk.Button(buttons, text="Gợi ý", command=self._show_hint, style="Small.TButton")
        self.hint_button.pack(side=tk.LEFT, padx=6)

        ttk.Button(
            buttons, text="Đặt câu ví dụ", style="Small.TButton",
            command=lambda: self._open_practice("free"),
        ).pack(side=tk.LEFT, padx=6)

        ttk.Button(
            buttons, text="Quản lý từ vựng", style="Small.TButton",
            command=self._open_manager,
        ).pack(side=tk.LEFT, padx=6)

        if self.on_request_switch is not None:
            ttk.Button(
                buttons, text="Sang phần đọc", style="Small.TButton",
                command=self.on_request_switch,
            ).pack(side=tk.LEFT, padx=6)

        ttk.Button(
            buttons, text="Thoát khẩn cấp", style="Small.TButton",
            command=self._emergency_exit,
        ).pack(side=tk.RIGHT)

        return view

    # ============================================================
    # Vòng hỏi đáp
    # ============================================================

    def _next_question(self):
        self._cancel_pending()
        entry = self.engine.pick_next()
        if entry is None:
            self.question_label.config(text="Kho từ vựng đang trống.")
            return

        self.question_label.config(text=f"“{entry['vi']}”")
        self.hint_label.config(text=entry.get("example", ""))
        self.feedback_label.config(text="", foreground="black")
        self.answer_var.set("")
        self.answer_entry.state(["!disabled"])
        self.submit_button.state(["!disabled"])
        self.hint_button.state(["!disabled"])
        self.answer_entry.focus_set()
        self._update_progress()

    def _update_progress(self):
        stats = self.engine.session_stats()
        self.progress_bar.config(value=stats["correct"])
        self.progress_label.config(
            text=f"Đúng {stats['correct']}/{stats['target']} • "
                 f"chuỗi đúng liên tiếp: {stats['streak']} • "
                 f"độ chính xác: {stats['accuracy'] * 100:.0f}%"
        )
        today = self.progress.summary()
        self.stats_label.config(
            text=f"Hôm nay đã ôn {today['asked_today']} từ • đã thuộc {today['known_words']} từ"
        )

    def _on_enter(self, _event=None):
        # Đang chờ xem đáp án thì Enter nghĩa là "đi tiếp luôn".
        if self._pending_action is not None:
            self._run_pending_now()
        else:
            self._submit()
        return "break"

    def _on_window_return(self, _event=None):
        """Enter khi ô nhập đang bị khóa: bỏ qua thời gian chờ, sang câu mới."""
        if not self.quiz_view.winfo_ismapped() or self._pending_action is None:
            return None
        self._run_pending_now()
        return "break"

    def _show_hint(self):
        hint = self.engine.use_hint()
        if hint:
            self.hint_label.config(text=f"Gợi ý: {hint}")
            self.answer_entry.focus_set()

    def _submit(self):
        if self._pending_action is not None:
            return
        answer = self.answer_var.get().strip()
        if not answer:
            self.feedback_label.config(text="Bạn chưa nhập gì cả.", foreground=ui_common.COLOR_WARN)
            return

        result = self.engine.submit(answer)
        self._update_progress()

        if result.verdict == "exact":
            self.feedback_label.config(
                text=f"Chính xác! {result.correct_display}", foreground=ui_common.COLOR_OK
            )
            if result.finished:
                self._finish()
                return
            self._schedule(self._next_question, 600)

        elif result.verdict == "near":
            self.feedback_label.config(
                text=f"Gần đúng — chú ý chính tả.\nViết đúng là: {result.correct_display}",
                foreground=ui_common.COLOR_WARN,
            )
            if result.finished:
                self._finish()
                return
            self._schedule(self._next_question, 1600)

        else:
            entry = result.entry
            self.feedback_label.config(
                text=f"Chưa đúng. Bạn trả lời: {answer}\n"
                     f"Đáp án: {result.correct_display}  —  {entry.get('vi', '')}",
                foreground=ui_common.COLOR_BAD,
            )
            self._lock_input()
            if config.FORCE_SENTENCE_ON_WRONG and ai_teacher.is_configured():
                self._schedule(lambda: self._open_practice("forced"), 3000)
            else:
                self._schedule(self._next_question, 2500)

    def _lock_input(self):
        self.answer_entry.state(["disabled"])
        self.submit_button.state(["disabled"])
        self.hint_button.state(["disabled"])

    def _schedule(self, action, delay_ms: int):
        self._cancel_pending()
        self._pending_action = action
        self._pending_after_id = self.window.after(delay_ms, self._run_pending_now)

    def _run_pending_now(self):
        action = self._pending_action
        self._cancel_pending()
        if action is not None:
            action()

    def _cancel_pending(self):
        if self._pending_after_id is not None:
            try:
                self.window.after_cancel(self._pending_after_id)
            except (ValueError, tk.TclError):
                pass
        self._pending_after_id = None
        self._pending_action = None

    def _finish(self):
        self.completed = True
        stats = self.engine.session_stats()
        message = (
            f"Hoàn thành phần từ vựng!\n\n"
            f"Số câu đã trả lời: {stats['answered']}\n"
            f"Độ chính xác: {stats['accuracy'] * 100:.0f}%\n"
            f"Chuỗi đúng dài nhất: {stats['best_streak']}"
        )
        if stats["wrong_words"]:
            message += "\n\nCần ôn thêm: " + ", ".join(stats["wrong_words"][:8])

        self.guard.show_info("Goed gedaan!", message)
        if callable(self.on_completed):
            self.on_completed()
        self.window.destroy()

    # ============================================================
    # Khung đặt câu ví dụ (AI chấm)
    # ============================================================

    def _open_practice(self, mode: str):
        entry = self.engine.current_entry
        if entry is None:
            return

        self.practice_mode = mode
        if self.practice_view is None:
            self.practice_view = self._build_practice_view()

        word = strip_tags(entry["nl"])
        self.practice_word_label.config(text=word)
        self.practice_meaning_label.config(text=entry.get("vi", ""))
        self.practice_input.delete("1.0", "end")
        ui_common.set_text(self.practice_result, "")
        self.practice_status.config(text="", foreground=ui_common.COLOR_MUTED)
        self.grade_button.state(["!disabled"])
        self.back_button.config(
            text="Bỏ qua, học câu khác" if mode == "forced" else "Quay lại làm bài"
        )

        self._show(self.practice_view)
        self.practice_input.focus_set()

    def _build_practice_view(self) -> ttk.Frame:
        view = ttk.Frame(self.container)

        ttk.Label(view, text="Đặt câu với từ này", style="Title.TLabel").pack(anchor="w")

        self.practice_word_label = ttk.Label(view, text="", font=ui_common.FONT_QUESTION)
        self.practice_word_label.pack(pady=(16, 2))
        self.practice_meaning_label = ttk.Label(view, text="", style="Muted.TLabel")
        self.practice_meaning_label.pack()

        ttk.Label(
            view,
            text="Viết một câu tiếng Hà Lan dùng từ trên. AI sẽ sửa ngữ pháp và giải thích bằng tiếng Việt.",
            style="H2.TLabel",
        ).pack(pady=(20, 6))

        self.practice_input = tk.Text(view, height=4, font=ui_common.FONT_BODY, wrap="word")
        self.practice_input.pack(fill=tk.X, padx=60)
        self.practice_input.bind("<Control-Return>", lambda _e: self._grade_sentence())

        self.practice_status = ttk.Label(view, text="", style="Muted.TLabel")
        self.practice_status.pack(pady=6)

        result_frame = ttk.Frame(view)
        result_frame.pack(fill=tk.BOTH, expand=True, padx=60, pady=(0, 10))
        self.practice_result = ui_common.make_text(
            result_frame, height=10, font=ui_common.FONT_BODY, state="disabled"
        )

        buttons = ttk.Frame(view)
        buttons.pack(fill=tk.X)
        self.grade_button = ttk.Button(buttons, text="Chấm câu (Ctrl+Enter)", command=self._grade_sentence)
        self.grade_button.pack(side=tk.LEFT)
        self.back_button = ttk.Button(buttons, text="Quay lại làm bài", command=self._leave_practice)
        self.back_button.pack(side=tk.LEFT, padx=8)

        return view

    def _grade_sentence(self):
        sentence = self.practice_input.get("1.0", "end").strip()
        if not sentence:
            self.practice_status.config(text="Bạn chưa viết câu nào.", foreground=ui_common.COLOR_WARN)
            return

        entry = self.engine.current_entry or {}
        word = strip_tags(entry.get("nl", ""))
        meaning = entry.get("vi", "")

        self.grade_button.state(["disabled"])
        self.practice_status.config(text="Đang gửi cho AI chấm…", foreground=ui_common.COLOR_MUTED)

        ui_common.run_async(
            self.window,
            lambda: ai_teacher.check_sentence(word, sentence, meaning),
            self._on_sentence_graded,
            self._on_sentence_error,
        )

    def _on_sentence_graded(self, result: dict):
        self.grade_button.state(["!disabled"])
        ok = result["is_correct_usage"]
        self.practice_status.config(
            text=f"{'Đúng rồi!' if ok else 'Cần sửa thêm.'} Điểm: {result['score']:.2f}",
            foreground=ui_common.COLOR_OK if ok else ui_common.COLOR_WARN,
        )

        lines = [result["feedback_vi"]]
        if result["corrected_sentence"]:
            lines.append(f"\nCâu đã sửa:\n{result['corrected_sentence']}")
        if result["suggested_sentence"]:
            lines.append(f"\nCâu mẫu khác:\n{result['suggested_sentence']}")
        ui_common.set_text(self.practice_result, "\n".join(lines).strip())

        if ok and self.practice_mode == "forced":
            self.practice_status.config(
                text="Đúng rồi! Quay lại bài trong giây lát…", foreground=ui_common.COLOR_OK
            )
            self.window.after(2000, self._leave_practice)

    def _on_sentence_error(self, error: Exception):
        self.grade_button.state(["!disabled"])
        self.practice_status.config(text="Không chấm được câu.", foreground=ui_common.COLOR_BAD)
        ui_common.set_text(
            self.practice_result,
            f"{error}\n\nBạn vẫn có thể bấm “Bỏ qua” để học tiếp.",
        )

    def _leave_practice(self):
        self.practice_mode = None
        self._show(self.quiz_view)
        self._next_question()

    # ============================================================
    # Khung quản lý từ vựng
    # ============================================================

    def _open_manager(self):
        if self.manager_view is None:
            self.manager_view = self._build_manager_view()
        self._refresh_word_list()
        self._show(self.manager_view)
        self.search_entry.focus_set()

    def _build_manager_view(self) -> ttk.Frame:
        view = ttk.Frame(self.container)

        header = ttk.Frame(view)
        header.pack(fill=tk.X)
        ttk.Label(header, text="Quản lý từ vựng", style="Title.TLabel").pack(side=tk.LEFT)
        self.manager_count_label = ttk.Label(header, text="", style="Muted.TLabel")
        self.manager_count_label.pack(side=tk.RIGHT)

        body = ttk.Frame(view)
        body.pack(fill=tk.BOTH, expand=True, pady=12)

        # ----- Danh sách bên trái -----
        left = ttk.Frame(body)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        search_row = ttk.Frame(left)
        search_row.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(search_row, text="Tìm:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._refresh_word_list())
        self.search_entry = ttk.Entry(search_row, textvariable=self.search_var, font=ui_common.FONT_BODY)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        self.search_entry.bind("<Return>", self._on_manager_search_enter)
        self.search_entry.bind("<KP_Enter>", self._on_manager_search_enter)

        list_frame = ttk.Frame(left)
        list_frame.pack(fill=tk.BOTH, expand=True)
        self.word_listbox = tk.Listbox(list_frame, font=ui_common.FONT_BODY, activestyle="none")
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.word_listbox.yview)
        self.word_listbox.config(yscrollcommand=scrollbar.set)
        self.word_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.word_listbox.bind("<<ListboxSelect>>", self._on_word_selected)
        self.word_listbox.bind("<Return>", self._on_manager_enter)
        self.word_listbox.bind("<KP_Enter>", self._on_manager_enter)

        # ----- Biểu mẫu bên phải -----
        right = ttk.Frame(body, padding=(20, 0, 0, 0))
        right.pack(side=tk.RIGHT, fill=tk.Y)

        self.form_vars = {}
        self.form_entries = {}
        fields = [
            ("nl", "Tiếng Hà Lan:", "vd: de fiets"),
            ("vi", "Nghĩa tiếng Việt:", "vd: xe đạp"),
            ("alt", "Cách viết khác:", "ngăn nhau bằng dấu |"),
            ("example", "Câu ví dụ:", "không bắt buộc"),
        ]
        for row, (key, label, hint) in enumerate(fields):
            ttk.Label(right, text=label).grid(row=row * 2, column=0, sticky="w", pady=(8, 0))
            var = tk.StringVar()
            self.form_vars[key] = var
            entry = ttk.Entry(right, textvariable=var, font=ui_common.FONT_BODY, width=34)
            entry.grid(row=row * 2 + 1, column=0, sticky="ew")
            entry.bind("<Return>", self._on_manager_enter)
            entry.bind("<KP_Enter>", self._on_manager_enter)
            self.form_entries[key] = entry
            ttk.Label(right, text=hint, style="Muted.TLabel").grid(row=row * 2 + 1, column=1, padx=6)

        button_row = ttk.Frame(right)
        button_row.grid(row=len(fields) * 2, column=0, columnspan=2, sticky="ew", pady=16)
        ttk.Button(button_row, text="Thêm mới", command=self._add_word).pack(side=tk.LEFT)
        ttk.Button(button_row, text="Cập nhật", command=self._update_word).pack(side=tk.LEFT, padx=6)
        delete_btn = ttk.Button(button_row, text="Xóa", command=self._delete_word)
        delete_btn.pack(side=tk.LEFT)
        # Enter khi nút Xóa đang focus vẫn là lưu, không phải xóa.
        delete_btn.bind("<Return>", self._on_manager_enter)
        delete_btn.bind("<KP_Enter>", self._on_manager_enter)

        ttk.Label(
            right,
            text="Enter để thêm từ mới, hoặc cập nhật từ đang chọn.\n"
                 "Xóa từ phải bấm nút Xóa.\n"
                 "Mẹo: viết danh từ kèm mạo từ (de/het).",
            style="Muted.TLabel",
            justify="left",
        ).grid(row=len(fields) * 2 + 1, column=0, columnspan=2, sticky="w")

        ttk.Button(view, text="Quay lại làm bài", command=self._close_manager).pack(anchor="w")
        return view

    def _on_manager_search_enter(self, _event=None):
        """Enter ở ô tìm: chọn kết quả đầu, rồi nhảy sang form để sửa."""
        if self._filtered_indices:
            self.word_listbox.selection_clear(0, tk.END)
            self.word_listbox.selection_set(0)
            self.word_listbox.activate(0)
            self.word_listbox.see(0)
            self._on_word_selected()
            self.form_entries["nl"].focus_set()
        return "break"

    def _on_manager_enter(self, _event=None):
        """Enter = lưu: đang chọn một từ thì cập nhật, chưa chọn thì thêm mới."""
        if self._selected_store_index() is not None:
            self._update_word()
        else:
            self._add_word()
        return "break"

    def _refresh_word_list(self, select_index=None):
        keyword = self.search_var.get().strip().lower()
        self.word_listbox.delete(0, tk.END)
        self._filtered_indices = []

        for index, entry in enumerate(self.store.all()):
            label = f"{strip_tags(entry['nl'])} — {entry['vi']}"
            if keyword and keyword not in label.lower():
                continue
            self._filtered_indices.append(index)
            self.word_listbox.insert(tk.END, label)

        self.manager_count_label.config(
            text=f"Hiển thị {len(self._filtered_indices)}/{self.store.count()} từ"
        )

        self.word_listbox.selection_clear(0, tk.END)
        if select_index is not None and select_index in self._filtered_indices:
            pos = self._filtered_indices.index(select_index)
            self.word_listbox.selection_set(pos)
            self.word_listbox.activate(pos)
            self.word_listbox.see(pos)

    def _selected_store_index(self):
        selection = self.word_listbox.curselection()
        if not selection:
            return None
        return self._filtered_indices[selection[0]]

    def _on_word_selected(self, _event=None):
        index = self._selected_store_index()
        if index is None:
            return
        entry = self.store.get(index) or {}
        alt = entry.get("alt") or []
        self.form_vars["nl"].set(entry.get("nl", ""))
        self.form_vars["vi"].set(entry.get("vi", ""))
        self.form_vars["alt"].set(" | ".join(alt) if isinstance(alt, list) else str(alt))
        self.form_vars["example"].set(entry.get("example", ""))

    def _form_values(self):
        alt_raw = self.form_vars["alt"].get().strip()
        return (
            self.form_vars["nl"].get().strip(),
            self.form_vars["vi"].get().strip(),
            {
                "alt": [a.strip() for a in alt_raw.split("|") if a.strip()],
                "example": self.form_vars["example"].get().strip(),
            },
        )

    def _add_word(self):
        nl, vi, extra = self._form_values()
        if not nl or not vi:
            self.guard.show_error("Thiếu dữ liệu", "Cần nhập cả từ tiếng Hà Lan và nghĩa tiếng Việt.")
            return
        if not self.store.add(nl, vi, **extra):
            self.guard.show_error("Trùng từ", f"“{nl}” đã có trong danh sách.")
            return
        self._clear_form()
        self._refresh_word_list()
        self.form_entries["nl"].focus_set()

    def _update_word(self):
        index = self._selected_store_index()
        if index is None:
            self.guard.show_error("Chưa chọn từ", "Hãy chọn một từ trong danh sách bên trái.")
            return
        nl, vi, extra = self._form_values()
        if not self.store.update(index, nl, vi, **extra):
            self.guard.show_error("Thiếu dữ liệu", "Cần nhập cả từ tiếng Hà Lan và nghĩa tiếng Việt.")
            return
        self._refresh_word_list(select_index=index)
        self.form_entries["nl"].focus_set()

    def _delete_word(self):
        index = self._selected_store_index()
        if index is None:
            self.guard.show_error("Chưa chọn từ", "Hãy chọn một từ trong danh sách bên trái.")
            return
        if self.store.count() <= 1:
            self.guard.show_error("Không thể xóa", "Phải giữ lại ít nhất 1 từ để còn làm bài.")
            return
        entry = self.store.get(index)
        if self.guard.ask_yes_no("Xóa từ", f"Xóa “{entry['nl']} — {entry['vi']}”?"):
            self.store.delete(index)
            self._clear_form()
            self._refresh_word_list()
            self.form_entries["nl"].focus_set()

    def _clear_form(self):
        for var in self.form_vars.values():
            var.set("")

    def _close_manager(self):
        self._show(self.quiz_view)
        if self.store.count() == 0:
            self.guard.show_error("Chưa có từ vựng", "Hãy thêm ít nhất một từ trước khi làm bài.")
            return
        self._next_question()

    # ============================================================
    # Thoát
    # ============================================================

    def _on_close_attempt(self):
        self.guard.show_info(
            "Chưa xong",
            f"Cần trả lời đúng {self.engine.target} câu mới đóng được cửa sổ này.\n"
            f"Hiện tại: {self.engine.correct_count}/{self.engine.target}.\n\n"
            "Nếu app bị lỗi, hãy dùng nút “Thoát khẩn cấp”.",
        )

    def _emergency_exit(self):
        if not self.guard.confirm_emergency_exit():
            return
        if callable(self.on_emergency):
            self.on_emergency()
        else:
            self.window.destroy()
