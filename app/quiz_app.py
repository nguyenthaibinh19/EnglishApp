"""Màn hình luyện từ vựng cho ngôn ngữ đang học.

Ba khung dùng chung một cửa sổ: làm bài, đặt câu ví dụ (AI chấm) và quản lý từ vựng.
"""

import tkinter as tk
from tkinter import ttk

import account_client
import ai_teacher
import config
import dictionary
import ui_common
import ui_foundation
from progress import Progress
from quiz_engine import QuizEngine
from study_presentation import StudyCardShell
from text_utils import entry_word, fold_accents, normalize, strip_tags, without_article
from vocab_store import ReadOnlyVocabView, VocabStore
from vocabulary_model import entry_meaning


class VocabQuizApp:
    def __init__(
        self,
        window: tk.Misc,
        store: VocabStore = None,
        progress: Progress = None,
        on_completed=None,
        on_request_switch=None,
        on_emergency=None,
        required=True,
        manage_only=False,
        locked=True,
        allow_manage: bool = True,
        quiz_entries=None,
        target: int = None,
        language_code: str = None,
        on_closed=None,
        window_title: str = None,
    ):
        self.window = window
        self.manage_only = manage_only
        self.allow_manage = bool(allow_manage) and not manage_only and quiz_entries is None
        self.language_code = language_code
        self.on_closed = on_closed
        self._closed_notified = False

        from study_data import open_study_data

        code = language_code or config.active_code()
        bundle = open_study_data(code)
        if quiz_entries is not None:
            self.store = ReadOnlyVocabView(quiz_entries)
            self.allow_manage = False
        else:
            self.store = store or bundle.vocab

        default_title = (
            config.ui("Kho từ", "Word list")
            if manage_only
            else config.ui("Từ vựng", "Vocabulary")
        )
        self.window.title(
            f"{config.APP_NAME} — " + (window_title if window_title else default_title)
        )

        self.progress = progress or bundle.progress
        # Practice Mistakes (quiz_entries) must ignore long-term due dates.
        apply_due_filter = quiz_entries is None
        self.engine = QuizEngine(
            self.store,
            self.progress,
            target=target,
            language_code=code,
            apply_due_filter=apply_due_filter,
            attempt_history=bundle.attempts,
        )

        self.on_completed = on_completed
        # Quiz-only subset must not jump to reading or open Manage.
        self.on_request_switch = None if quiz_entries is not None else on_request_switch
        self.on_emergency = on_emergency
        self.required = False if manage_only or quiz_entries is not None else required

        self.completed = False
        self.practice_mode = None      # None | "free" | "forced"
        self._pending_action = None    # hành động đang chờ trước khi sang câu mới
        self._pending_after_id = None
        self._phase = "answer"
        self._submitting = False
        self._continuing = False
        self._result_finished = False
        self._last_verdict = ""

        ui_common.apply_theme(window)
        self.guard = ui_common.ScreenGuard(
            window,
            enabled=config.LOCK_SCREEN if locked else False,
            on_close_attempt=self._on_close_attempt,
            on_unlocked_close=self._leave_unlocked,
        )
        if not self.guard.enabled:
            try:
                window.geometry("560x520")
                window.minsize(480, 480)
                window.configure(bg=ui_foundation.COLOR_BG)
            except tk.TclError:
                pass

        if self.store.count() == 0 and not self.manage_only:
            self.guard.show_error(
                config.ui("Chưa có từ vựng", "No vocabulary yet"),
                config.ui(
                    "Danh sách từ của ngôn ngữ này đang trống.\n\n"
                    "Hãy thêm từ bằng nút Kho từ trên menu, "
                    f"ví dụ: {config.current_language()['sample']}.",
                    "This language's word list is empty.\n\n"
                    "Add words with the Word list button on the menu, "
                    f"for example: {config.current_language()['sample']}.",
                ),
            )
            self.window.destroy()
            return

        self.window.bind("<Destroy>", self._on_window_destroy, add="+")

        self._build_ui()
        if self.manage_only:
            self._open_manager()
        else:
            self._next_question()

    # ============================================================
    # Dựng giao diện
    # ============================================================

    def _build_ui(self):
        self.container = ttk.Frame(self.window, padding=12)
        self.container.pack(fill=tk.BOTH, expand=True)

        if self.manage_only:
            self.quiz_view = None
            self.practice_view = None
            self.manager_view = None
            return

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
        language = config.language_name(self.language_code or config.active_code())
        self.shell = StudyCardShell(
            view,
            locked=bool(self.guard.enabled),
            on_check=self._submit,
            on_hint=self._show_hint,
            on_continue=self._continue,
            on_done=self._close_complete,
            on_sentence=self._practice_voluntary,
            on_hear=self._hear_answer,
            on_leave=self._leave_unlocked,
            on_emergency=self._emergency_exit,
        )
        self.shell.set_copy(
            check=config.ui("Kiểm tra", "Check answer"),
            hint=config.ui("Gợi ý", "Hint"),
            continue_text=config.ui("Tiếp tục", "Continue"),
            leave=config.ui("Để lúc khác", "Leave for now"),
            emergency=config.ui("Thoát khẩn cấp", "Emergency exit"),
        )
        self.shell.sentence_button.configure(
            text=config.ui("Đặt câu ví dụ", "Write a sentence"),
        )
        self.shell.hear_button.configure(
            text=config.ui("Nghe từ", "Hear the word"),
        )
        self._question_kicker = config.ui(
            f"Từ {language} nào có nghĩa là",
            f"Which {language} word means",
        )
        self.shell.pack(fill=tk.BOTH, expand=True)
        self.answer_entry = self.shell.exercise.entry
        answer_inner = getattr(self.answer_entry, "_entry", self.answer_entry)
        answer_inner.bind("<Return>", self._on_window_return, add="+")
        answer_inner.bind("<KP_Enter>", self._on_window_return, add="+")
        self.check_button = self.shell.check_button
        self.hint_button = self.shell.hint_button
        self.continue_button = self.shell.continue_button
        self.leave_button = self.shell.leave_button
        self.emergency_button = self.shell.emergency_button
        self.feedback_label = self.shell.feedback
        return view

    # ============================================================
    # Vòng hỏi đáp
    # ============================================================

    def _next_question(self):
        self._cancel_pending()
        self._result_finished = False
        self._last_verdict = ""
        self._card_token = getattr(self, "_card_token", 0) + 1
        self._revealed_word = ""
        entry = self.engine.pick_next()
        if entry is None:
            self.shell.exercise.set_prompt("", config.ui("Kho từ vựng đang trống.", "The word list is empty."))
            return
        self._phase = "answer"
        self.shell.exercise.set_prompt(self._question_kicker, self._learner_meaning(entry))
        self.shell.show_answering()
        self._update_progress()

    def _update_progress(self):
        stats = self.engine.session_stats()
        correct = int(stats["correct"])
        target = int(stats["target"])
        # Session score, not a question index and not a mastery count.
        # Near misses and hinted exact answers increase this score.
        # Only an exact answer without a hint is mastery, and that stays in the attempt record.
        label = config.ui(f"Đúng {correct}/{target}", f"{correct}/{target} correct")
        self.shell.set_progress(correct, target, label)

    def _on_window_return(self, _event=None):
        """Enter submits, then continues once. It does not record the same answer twice."""
        if self.quiz_view is None or not self.quiz_view.winfo_ismapped():
            return None
        if self._phase == "feedback":
            self._continue()
        elif self._phase == "complete":
            self._close_complete()
        elif self._phase == "answer":
            self._submit()
        return "break"

    def _show_hint(self):
        if self._phase != "answer":
            return
        hint = self.engine.use_hint()
        if hint:
            self.shell.exercise.show_support(config.ui(f"Gợi ý: {hint}", f"Hint: {hint}"))
            self.shell.exercise.focus_answer()

    def _submit(self):
        if self._phase != "answer" or self._submitting:
            return
        answer = self.shell.exercise.answer_text()
        if not answer:
            self.shell.show_feedback(
                config.ui("Hãy nhập câu trả lời trước.", "Type an answer first."),
                "empty",
            )
            return

        self._submitting = True
        self._phase = "feedback"
        try:
            result = self.engine.submit(answer)
        except Exception:
            self._phase = "answer"
            raise
        finally:
            self._submitting = False
        self._result_finished = bool(result.finished)
        self._last_verdict = result.verdict
        self._revealed_word = strip_tags(result.correct_display or "")
        self._update_progress()
        self.shell.show_feedback(
            self._feedback_text(result),
            self._feedback_tone(result.verdict),
            offer_sentence=not result.finished,
            offer_hear=bool(self._revealed_word),
        )

    def _feedback_tone(self, verdict: str) -> str:
        if verdict == "exact":
            return "ok"
        if verdict == "near":
            return "near"
        return "bad"

    def _feedback_text(self, result) -> str:
        if result.verdict == "exact":
            return config.ui(
                f"Đúng rồi. {result.correct_display}",
                f"That's it. {result.correct_display}",
            )
        if result.verdict == "near":
            return config.ui(
                f"Rất gần. Viết đúng là {result.correct_display}",
                f"Very close. {result.correct_display}",
            )
        meaning = self._learner_meaning(result.entry or {})
        return config.ui(
            f"Từ đúng là {result.correct_display}. {meaning}",
            f"The word is {result.correct_display}. {meaning}",
        )

    def _continue(self):
        if self._phase != "feedback" or self._continuing:
            return
        self._continuing = True
        try:
            if self._result_finished:
                self._show_complete()
            elif self._wants_forced_sentence():
                self._phase = "practice"
                self._open_practice("forced")
            else:
                self._next_question()
        finally:
            self._continuing = False

    def _wants_forced_sentence(self) -> bool:
        """Wrong answers only. Exact and near misses keep the existing next-step path."""
        if self._last_verdict in ("exact", "near", ""):
            return False
        return bool(config.FORCE_SENTENCE_ON_WRONG and ai_teacher.is_configured())

    def _practice_voluntary(self):
        """Open the existing sentence screen without sitting beside Check."""
        if self._phase != "feedback" or self._continuing or self._result_finished:
            return
        if self.engine.current_entry is None:
            return
        self._phase = "practice"
        self._open_practice("free")

    def _hear_answer(self):
        """Speak the word only after it is already on the feedback card."""
        if self._phase != "feedback":
            return
        word = str(getattr(self, "_revealed_word", "") or "").strip()
        if not word:
            return
        from speech_player import play_async
        import voice_prefs
        from listening_windows_tts import NORMAL_RATE

        language = self.language_code or config.active_code()
        token = getattr(self, "_card_token", 0)

        def scope() -> bool:
            return (
                self._phase == "feedback"
                and getattr(self, "_card_token", None) == token
                and str(getattr(self, "_revealed_word", "") or "").strip() == word
                and (self.language_code or config.active_code()) == language
            )

        started = play_async(
            self.window,
            text=word,
            language_code=language,
            rate=NORMAL_RATE,
            voice_name=voice_prefs.selected_voice_name(language) or None,
            scope=scope,
            on_error=lambda error: self._hear_status(str(error)),
        )
        if not started:
            self._hear_status(config.ui("Đang phát một đoạn khác.", "Another clip is still playing."))

    def _hear_status(self, text: str):
        if self._phase != "feedback":
            return
        try:
            self.shell.exercise.show_support(text)
        except tk.TclError:
            pass

    def _cancel_pending(self):
        if self._pending_after_id is not None:
            try:
                self.window.after_cancel(self._pending_after_id)
            except (ValueError, tk.TclError):
                pass
        self._pending_after_id = None
        self._pending_action = None

    def _show_complete(self):
        self._phase = "complete"
        self.completed = True
        stats = self.engine.session_stats()
        more = self.on_request_switch is not None
        title = config.ui("Xong phần từ vựng.", "Vocabulary done.") if more else config.ui("Hôm nay xong rồi.", "Done for today.")
        detail = config.ui(
            f"{stats['answered']} câu · {stats['accuracy'] * 100:.0f}%",
            f"{stats['answered']} practiced · {stats['accuracy'] * 100:.0f}%",
        )
        button = config.ui("Tiếp tục", "Continue") if more else config.ui("Về hôm nay", "Back to today")
        self._update_progress()
        self.shell.show_complete(title, detail, button)

    def _close_complete(self):
        if self._phase != "complete" or self._continuing:
            return
        self._continuing = True
        self._phase = "closed"
        try:
            if callable(self.on_completed):
                self.on_completed()
        finally:
            try:
                self.window.destroy()
            except tk.TclError:
                pass

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

        word = strip_tags(entry_word(entry))
        self.practice_word_label.config(text=word)
        self.practice_meaning_label.config(text=self._learner_meaning(entry))
        self.practice_input.delete("1.0", "end")
        ui_common.set_text(self.practice_result, "")
        self.practice_status.config(text="", foreground=ui_common.COLOR_MUTED)
        self.grade_button.state(["!disabled"])
        self.back_button.config(
            text=config.ui("Bỏ qua, học câu khác", "Skip, next word")
            if mode == "forced"
            else config.ui("Quay lại làm bài", "Back to the quiz")
        )

        self._show(self.practice_view)
        self.practice_input.focus_set()

    def _build_practice_view(self) -> ttk.Frame:
        view = ttk.Frame(self.container)

        ttk.Label(
            view, text=config.ui("Đặt câu với từ này", "Write a sentence with this word"),
            style="Title.TLabel",
        ).pack(anchor="w")

        self.practice_word_label = ttk.Label(view, text="", font=ui_common.FONT_QUESTION)
        self.practice_word_label.pack(pady=(16, 2))
        self.practice_meaning_label = ttk.Label(view, text="", style="Muted.TLabel")
        self.practice_meaning_label.pack()

        ttk.Label(
            view,
            text=config.ui(
                f"Viết một câu {config.current_language()['name_vi']} dùng từ trên. "
                f"AI sẽ sửa ngữ pháp và giải thích bằng {config.native_label()}.",
                f"Write a {config.language_name(config.active_code())} sentence using the word above. "
                f"The AI will correct the grammar and explain in {config.native_label()}.",
            ),
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
        self.grade_button = ttk.Button(
            buttons, text=config.ui("Chấm câu (Ctrl+Enter)", "Grade sentence (Ctrl+Enter)"),
            command=self._grade_sentence,
        )
        self.grade_button.pack(side=tk.LEFT)
        self.back_button = ttk.Button(
            buttons, text=config.ui("Quay lại làm bài", "Back to the quiz"), command=self._leave_practice
        )
        self.back_button.pack(side=tk.LEFT, padx=8)

        return view

    def _grade_sentence(self):
        sentence = self.practice_input.get("1.0", "end").strip()
        if not sentence:
            self.practice_status.config(
                text=config.ui("Bạn chưa viết câu nào.", "Write a sentence first."),
                foreground=ui_common.COLOR_WARN,
            )
            return

        entry = self.engine.current_entry or {}
        word = strip_tags(entry_word(entry))
        meaning = self._learner_meaning(entry)

        self.grade_button.state(["disabled"])
        self.practice_status.config(
            text=config.ui("Đang gửi cho AI chấm…", "Sending to the AI…"),
            foreground=ui_common.COLOR_MUTED,
        )

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
            text=config.ui(
                f"{'Đúng rồi!' if ok else 'Cần sửa thêm.'} Điểm: {result['score']:.2f}",
                f"{'Correct!' if ok else 'Needs a fix.'} Score: {result['score']:.2f}",
            ),
            foreground=ui_common.COLOR_OK if ok else ui_common.COLOR_WARN,
        )

        lines = [result["feedback_vi"]]
        if result["corrected_sentence"]:
            lines.append(config.ui(
                f"\nCâu đã sửa:\n{result['corrected_sentence']}",
                f"\nCorrected:\n{result['corrected_sentence']}",
            ))
        if result["suggested_sentence"]:
            lines.append(config.ui(
                f"\nCâu mẫu khác:\n{result['suggested_sentence']}",
                f"\nAnother example:\n{result['suggested_sentence']}",
            ))
        ui_common.set_text(self.practice_result, "\n".join(lines).strip())

        if ok and self.practice_mode == "forced":
            self.practice_status.config(
                text=config.ui(
                    "Đúng rồi! Quay lại bài trong giây lát…",
                    "Correct! Back to the quiz in a moment…",
                ),
                foreground=ui_common.COLOR_OK,
            )
            self.window.after(2000, self._leave_practice)

    def _on_sentence_error(self, error: Exception):
        self.grade_button.state(["!disabled"])
        if isinstance(error, account_client.SessionExpired):
            self.guard.pause_enforcement()
            try:
                import setup_wizard
                signed_in = setup_wizard.ask(self.window)
            finally:
                self.guard.resume_enforcement(refocus=False)
            if signed_in:
                self._grade_sentence()
                return
        self.practice_status.config(
            text=config.ui("Không chấm được câu.", "Couldn't grade the sentence."),
            foreground=ui_common.COLOR_BAD,
        )
        ui_common.set_text(
            self.practice_result,
            config.ui(
                f"{error}\n\nBạn vẫn có thể bấm “Bỏ qua” để học tiếp.",
                f"{error}\n\nYou can still press Skip and continue.",
            ),
        )

    def _leave_practice(self):
        self.practice_mode = None
        self._show(self.quiz_view)
        self._next_question()

    # ============================================================
    # Khung quản lý từ vựng
    # ============================================================

    def _open_manager(self):
        if not self.allow_manage and not self.manage_only:
            return
        if self.manager_view is None:
            self.manager_view = self._build_manager_view()
        self._refresh_word_list()
        self._show(self.manager_view)
        self.search_entry.focus_set()

    def _build_manager_view(self) -> ttk.Frame:
        view = ttk.Frame(self.container)

        header = ttk.Frame(view)
        header.pack(fill=tk.X)
        ttk.Label(
            header, text=config.ui("Quản lý từ vựng", "Manage vocabulary"), style="Title.TLabel"
        ).pack(side=tk.LEFT)
        self.manager_count_label = ttk.Label(header, text="", style="Muted.TLabel")
        self.manager_count_label.pack(side=tk.RIGHT)

        body = ttk.Frame(view)
        body.pack(fill=tk.BOTH, expand=True, pady=12)

        # ----- Danh sách bên trái -----
        left = ttk.Frame(body)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        search_row = ttk.Frame(left)
        search_row.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(search_row, text=config.ui("Tìm:", "Search:")).pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._refresh_word_list())
        self.search_entry = ttk.Entry(search_row, textvariable=self.search_var, font=ui_common.FONT_BODY)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        self.search_entry.bind("<Return>", self._on_manager_search_enter)
        self.search_entry.bind("<KP_Enter>", self._on_manager_search_enter)

        list_frame = ttk.Frame(left)
        list_frame.pack(fill=tk.BOTH, expand=True)
        # Keep Listbox selection when Entry fields take the PRIMARY selection
        # (e.g. Ctrl+A in Meaning); otherwise Update/Enter think nothing is selected.
        self.word_listbox = tk.Listbox(
            list_frame,
            font=ui_common.FONT_BODY,
            activestyle="none",
            exportselection=False,
        )
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
        lang = config.current_language()
        fields = [
            ("word", f"{config.language_name(config.active_code())}:", config.ui(f"vd: {lang['sample']}", f"e.g. {lang['sample']}")),
            ("vi", config.ui(f"Nghĩa ({config.native_label()}):", f"Meaning ({config.native_label()}):"), config.ui("vd: xe đạp", "e.g. bicycle")),
            ("alt", config.ui("Cách viết khác:", "Other spellings:"), config.ui("ngăn nhau bằng dấu |", "separate with |")),
            ("example", config.ui("Câu ví dụ:", "Example sentence:"), config.ui("không bắt buộc", "optional")),
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
        ttk.Button(button_row, text=config.ui("Thêm mới", "Add"), command=self._add_word).pack(side=tk.LEFT)
        ttk.Button(button_row, text=config.ui("Cập nhật", "Update"), command=self._update_word).pack(side=tk.LEFT, padx=6)
        delete_btn = ttk.Button(button_row, text=config.ui("Xóa", "Delete"), command=self._delete_word)
        delete_btn.pack(side=tk.LEFT)
        # Enter khi nút Xóa đang focus vẫn là lưu, không phải xóa.
        delete_btn.bind("<Return>", self._on_manager_enter)
        delete_btn.bind("<KP_Enter>", self._on_manager_enter)

        ttk.Label(
            right,
            text=config.ui(
                "Enter để thêm từ mới, hoặc cập nhật từ đang chọn.\n"
                "Xóa từ phải bấm nút Xóa.\n"
                "Mẹo: viết danh từ kèm mạo từ nếu ngôn ngữ đó có.",
                "Press Enter to add a new word, or to update the selected one.\n"
                "Deleting requires the Delete button.\n"
                "Tip: include the article when the language uses one.",
            ),
            style="Muted.TLabel",
            justify="left",
        ).grid(row=len(fields) * 2 + 1, column=0, columnspan=2, sticky="w")

        ttk.Button(
            view,
            text=config.ui("Đóng", "Close") if self.manage_only else config.ui("Quay lại làm bài", "Back to the quiz"),
            command=self._close_manager,
        ).pack(anchor="w")
        return view

    def _on_manager_search_enter(self, _event=None):
        """Enter ở ô tìm: chọn kết quả đầu, rồi nhảy sang form để sửa."""
        if self._filtered_indices:
            self.word_listbox.selection_clear(0, tk.END)
            self.word_listbox.selection_set(0)
            self.word_listbox.activate(0)
            self.word_listbox.see(0)
            self._on_word_selected()
            self.form_entries["word"].focus_set()
        return "break"

    def _on_manager_enter(self, _event=None):
        """Enter = lưu: đang chọn một từ thì cập nhật, chưa chọn thì thêm mới."""
        if self._selected_store_index() is not None:
            self._update_word()
        else:
            self._add_word()
        return "break"

    def _refresh_word_list(self, select_index=None):
        keyword = fold_accents(normalize(self.search_var.get()))
        self.word_listbox.delete(0, tk.END)
        self._filtered_indices = []

        for index, entry in enumerate(self.store.all()):
            label = f"{strip_tags(entry_word(entry))} — {entry_meaning(entry)}"
            if keyword and not self._entry_matches(entry, keyword):
                continue
            self._filtered_indices.append(index)
            self.word_listbox.insert(tk.END, label)

        self.manager_count_label.config(
            text=config.ui(
                f"Hiển thị {len(self._filtered_indices)}/{self.store.count()} từ",
                f"Showing {len(self._filtered_indices)}/{self.store.count()}",
            )
        )

        self.word_listbox.selection_clear(0, tk.END)
        if select_index is not None and select_index in self._filtered_indices:
            pos = self._filtered_indices.index(select_index)
            self.word_listbox.selection_set(pos)
            self.word_listbox.activate(pos)
            self.word_listbox.see(pos)

    def _learner_meaning(self, entry) -> str:
        """Nghĩa hiện ra khi làm bài. Tiếng Anh thì lấy từ điển, không dùng chú thích tiếng Việt đã lưu."""
        stored = entry_meaning(entry)
        if config.native_code() != "en":
            return stored
        gloss = dictionary.learner_gloss(entry_word(entry))
        return gloss or stored

    def _entry_matches(self, entry, keyword: str) -> bool:
        from vocabulary_model import entry_alternatives

        fields = (
            entry_word(entry),
            without_article(
                normalize(entry_word(entry)),
                language_code=getattr(self, "language_code", None),
                entry=entry,
            ),
            entry_meaning(entry),
            " ".join(entry_alternatives(entry)),
        )
        return any(keyword in fold_accents(normalize(str(field))) for field in fields)

    def _selected_store_index(self):
        selection = self.word_listbox.curselection()
        if not selection:
            return None
        return self._filtered_indices[selection[0]]

    def _on_word_selected(self, _event=None):
        index = self._selected_store_index()
        if index is None:
            return
        from vocabulary_model import entry_alternatives, entry_example

        entry = self.store.get(index) or {}
        alt = entry_alternatives(entry)
        self.form_vars["word"].set(entry_word(entry))
        self.form_vars["vi"].set(entry_meaning(entry))
        self.form_vars["alt"].set(" | ".join(alt))
        self.form_vars["example"].set(entry_example(entry))

    def _form_values(self):
        alt_raw = self.form_vars["alt"].get().strip()
        return (
            self.form_vars["word"].get().strip(),
            self.form_vars["vi"].get().strip(),
            {
                "alternatives": [a.strip() for a in alt_raw.split("|") if a.strip()],
                "example": self.form_vars["example"].get().strip(),
            },
        )

    def _add_word(self):
        word, vi, extra = self._form_values()
        if not word or not vi:
            self.guard.show_error(
                config.ui("Thiếu dữ liệu", "Missing fields"),
                config.ui("Cần nhập cả từ và nghĩa.", "Enter both the word and its meaning."),
            )
            return
        if not self.store.add(word, vi, **extra):
            self.guard.show_error(
                config.ui("Trùng từ", "Already saved"),
                config.ui(f"“{word}” đã có trong danh sách.", f"“{word}” is already in the list."),
            )
            return
        self._clear_form()
        self._refresh_word_list()
        self.form_entries["word"].focus_set()

    def _update_word(self):
        index = self._selected_store_index()
        if index is None:
            self.guard.show_error(
                config.ui("Chưa chọn từ", "No word selected"),
                config.ui("Hãy chọn một từ trong danh sách bên trái.", "Select a word in the list on the left."),
            )
            return
        word, vi, extra = self._form_values()
        if not self.store.update(index, word, vi, **extra):
            self.guard.show_error(
                config.ui("Thiếu dữ liệu", "Missing fields"),
                config.ui("Cần nhập cả từ và nghĩa.", "Enter both the word and its meaning."),
            )
            return
        self._refresh_word_list(select_index=index)
        self.form_entries["word"].focus_set()

    def _delete_word(self):
        index = self._selected_store_index()
        if index is None:
            self.guard.show_error(
                config.ui("Chưa chọn từ", "No word selected"),
                config.ui("Hãy chọn một từ trong danh sách bên trái.", "Select a word in the list on the left."),
            )
            return
        if self.store.count() <= 1 and not self.manage_only:
            self.guard.show_error(
                config.ui("Không thể xóa", "Can't delete"),
                config.ui("Phải giữ lại ít nhất 1 từ để còn làm bài.", "Keep at least one word so the quiz can run."),
            )
            return
        entry = self.store.get(index)
        if self.guard.ask_yes_no(
            config.ui("Xóa từ", "Delete word"),
            config.ui(
                f"Xóa “{entry_word(entry)} — {entry_meaning(entry)}”?",
                f"Delete “{entry_word(entry)} — {entry_meaning(entry)}”?",
            ),
        ):
            self.store.delete(index)
            self._clear_form()
            self._refresh_word_list()
            self.form_entries["word"].focus_set()

    def _clear_form(self):
        for var in self.form_vars.values():
            var.set("")

    def _close_manager(self):
        if self.manage_only:
            self.window.destroy()
            return
        self._show(self.quiz_view)
        if self.store.count() == 0:
            self.guard.show_error(
                config.ui("Chưa có từ vựng", "No vocabulary yet"),
                config.ui("Hãy thêm ít nhất một từ trước khi làm bài.", "Add at least one word before starting."),
            )
            return
        self._next_question()

    # ============================================================
    # Thoát
    # ============================================================

    def _on_window_destroy(self, event=None):
        if event is not None and event.widget is not self.window:
            return
        if self._closed_notified:
            return
        self._closed_notified = True
        if callable(self.on_closed):
            try:
                self.on_closed()
            except Exception:
                pass

    def _leave_unlocked(self):
        if getattr(self, "_phase", "") == "complete":
            self._close_complete()
            return
        try:
            self.window.destroy()
        except tk.TclError:
            pass

    def _on_close_attempt(self):
        if getattr(self, "_phase", "") == "complete" or self.completed:
            if getattr(self, "_phase", "") != "complete":
                self._phase = "complete"
            self._close_complete()
            return
        if self.guard.allows_unlocked_leave():
            self._leave_unlocked()
            return
        if not self.required:
            try:
                self.window.destroy()
            except tk.TclError:
                pass
            return
        self.guard.show_info(
            config.ui("Chưa xong", "Not finished"),
            config.ui(
                f"Cần trả lời đúng {self.engine.target} câu mới đóng được cửa sổ này.\n"
                f"Hiện tại: {self.engine.correct_count}/{self.engine.target}.\n\n"
                "Nếu app bị lỗi, hãy dùng nút “Thoát khẩn cấp”.",
                f"Answer {self.engine.target} correctly before this window can close.\n"
                f"Now: {self.engine.correct_count}/{self.engine.target}.\n\n"
                "If the app is stuck, use Emergency exit.",
            ),
        )

    def _emergency_exit(self):
        if not self.guard.confirm_emergency_exit():
            return
        if callable(self.on_emergency):
            self.on_emergency()
        else:
            self.window.destroy()
