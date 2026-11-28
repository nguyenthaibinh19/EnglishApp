"""Optional sentence practice window. Separate from required vocabulary completion.

Unlocked development only. Does not write LearningAttempt, Progress, SRS,
Mistake Book, PracticeRecord, or sync outbox events.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import customtkinter as ctk

import config
import ui_common
import ui_foundation
import voice_prefs
from adaptive_vocabulary import AdaptivePreviewRefused, SpeechPlan
from grammar_companion import build_companion, component_color
from listening import ListeningAudioError
from listening_windows_tts import NORMAL_RATE, SLOW_RATE
from sentence_content import (
    KIND_FILL_BLANK,
    KIND_GUIDED_WRITING,
    KIND_INDEPENDENT_WRITING,
    KIND_WORD_BANK,
)
from sentence_grading import (
    STATUS_INCORRECT,
    STATUS_PROVISIONAL_ACCEPT,
    STATUS_PROVISIONAL_CORRECT,
    STATUS_REVIEWED_CORRECT,
    STATUS_UNGRADED,
    STATUS_UNAVAILABLE,
    FakeSentenceGradeProvider,
    grade_async,
)
from sentence_practice import SentencePracticeSession
from speech_player import play_async
from study_presentation import StudyCardShell
from ctk_keyboard import bind_activation

ctk.deactivate_automatic_dpi_awareness()
ctk.set_appearance_mode("light")

PREVIEW_WIDTH = 560
PREVIEW_HEIGHT = 720


def speech_for_sentence(exercise, phase: str) -> SpeechPlan:
    """Only speak reviewed revealed sentences after check."""
    if exercise is None:
        return SpeechPlan(False, reason="no exercise")
    if phase != "feedback":
        return SpeechPlan(False, reason="answer stays hidden until check")
    text = exercise.primary_answer()
    if not text:
        return SpeechPlan(False, reason="no reviewed sentence")
    return SpeechPlan(True, text=text)


def _voice_problem(error) -> str:
    message = str(error or "")
    lower = message.lower()
    if "no voice" in lower or "not available" in lower:
        return config.ui(
            "Máy này chưa có giọng cho ngôn ngữ đang học. Bạn vẫn có thể tiếp tục.",
            "No voice for this language on this PC. You can continue.",
        )
    return config.ui(
        "Không phát được âm thanh. Bạn vẫn có thể tiếp tục.",
        "Playback failed. You can continue.",
    )


class SentencePracticeApp:
    def __init__(
        self,
        window: tk.Misc,
        session: SentencePracticeSession,
        *,
        on_completed=None,
        on_leave=None,
        provider=None,
        grade_service=None,
        identity=None,
        account_generation_reader=None,
        locked: bool = False,
    ):
        if locked:
            raise AdaptivePreviewRefused("Locked sessions stay on the legacy study path.")
        self.window = window
        self.session = session
        self.on_completed = on_completed
        self.on_leave = on_leave
        self.provider = provider
        self.grade_service = grade_service
        self.identity = identity
        self.account_generation_reader = account_generation_reader
        self._phase = "answer"
        self._checking = False
        self._completion_calls = 0
        self._leave_calls = 0
        self._card_token = 0
        self._grammar_open = False
        self._last_feedback = None
        self._feedback_exercise = None
        self._bank_selected: list = []
        self._ai_pending = False
        self._active_submission_id = ""
        self._active_instance_id = ""
        self.window.title(
            config.ui(
                "LanguageGuard — Luyện câu",
                "LanguageGuard — Sentence practice",
            )
        )
        self.guard = ui_common.ScreenGuard(
            window,
            enabled=False,
            on_close_attempt=self._leave,
            on_unlocked_close=self._leave,
        )
        if not self.guard.enabled:
            try:
                self.window.geometry(f"{PREVIEW_WIDTH}x{PREVIEW_HEIGHT}")
                self.window.minsize(480, 600)
                self.window.configure(bg=ui_foundation.COLOR_BG)
            except tk.TclError:
                pass
        self._build()
        self.window.bind("<Return>", self._on_return)
        self.window.bind("<KP_Enter>", self._on_return)
        self.window.bind("<Destroy>", self._on_destroy, add="+")
        self._show_current()

    def _build(self) -> None:
        self.container = ttk.Frame(self.window, padding=12)
        self.container.pack(fill=tk.BOTH, expand=True)
        self.shell = StudyCardShell(
            self.container,
            locked=False,
            on_check=self._check,
            on_hint=lambda: None,
            on_continue=self._continue,
            on_done=self._close_complete,
            on_sentence=lambda: None,
            on_hear=lambda: self._hear(NORMAL_RATE),
            on_leave=self._leave,
            on_emergency=self._leave,
        )
        self.shell.set_copy(
            check=config.ui("Kiểm tra", "Check answer"),
            hint="",
            continue_text=config.ui("Tiếp tục", "Continue"),
            leave=config.ui("Để lúc khác", "Leave for now"),
            emergency=config.ui("Thoát khẩn cấp", "Emergency exit"),
        )
        self.shell.hint_button.pack_forget()
        self.shell.sentence_button.pack_forget()
        self.shell.hear_button.configure(text=config.ui("Nghe câu", "Hear the sentence"))
        self.shell.pack(fill=tk.BOTH, expand=True)
        self.grammar_host = ctk.CTkFrame(
            self.shell.host, fg_color=ui_foundation.COLOR_BG, corner_radius=0
        )
        self.why_button = ctk.CTkButton(
            self.shell.host,
            text=config.ui("Vì sao?", "Why?"),
            command=self._toggle_grammar,
            height=28,
            corner_radius=8,
            fg_color="transparent",
            hover_color=ui_foundation.COLOR_SOFT_GREEN,
            text_color="#5C7268",
            font=ctk.CTkFont(family="Segoe UI", size=13),
        )
        bind_activation(self.why_button)
        self.slow_hear_button = ctk.CTkButton(
            self.shell.host,
            text=config.ui("Nghe chậm", "Listen slowly"),
            command=lambda: self._hear(SLOW_RATE),
            height=28,
            corner_radius=8,
            fg_color="transparent",
            hover_color=ui_foundation.COLOR_SOFT_GREEN,
            text_color="#5C7268",
            font=ctk.CTkFont(family="Segoe UI", size=13),
        )
        bind_activation(self.slow_hear_button)

    def _binding_current(self) -> bool:
        identity = self.identity
        if identity is None:
            return True
        generation = None
        reader = self.account_generation_reader
        if callable(reader):
            try:
                generation = int(reader())
            except Exception:
                generation = None
        check = getattr(identity, "still_current", None)
        if callable(check):
            try:
                return bool(check(account_generation=generation))
            except TypeError:
                return bool(check())
        return True

    def _on_return(self, _event=None):
        if self._phase == "feedback":
            self._continue()
        elif self._phase == "complete":
            self._close_complete()
        elif self._phase == "answer" and not self._ai_pending:
            self._check()
        return "break"

    def _update_progress(self) -> None:
        done, total = self.session.progress_pair()
        self.shell.set_progress(done, total, f"{done}/{total}")

    def _show_current(self) -> None:
        if self.session.abandoned:
            self._show_left()
            return
        if self.session.missing_content:
            self._show_missing()
            return
        if self.session.finished and self.session.levels_achieved() >= 4:
            self._show_complete()
            return
        card = self.session.current_card()
        if card is None:
            self._show_missing()
            return
        self._phase = "answer"
        self._card_token += 1
        self._grammar_open = False
        self._last_feedback = None
        self._feedback_exercise = None
        self._bank_selected = []
        self._active_submission_id = ""
        self._active_instance_id = ""
        self._clear_feedback_extras()
        self._mount(card.exercise)
        self.shell.set_stage(_stage_label(card.exercise.kind))
        self._update_progress()
        self.shell.show_answering(show_hint=False, clear_support=True)
        self.shell.hint_button.pack_forget()

    def _mount(self, exercise) -> None:
        if exercise.kind == KIND_WORD_BANK:
            body = WordBankExercise(self.shell.card, exercise, on_change=self._bank_changed)
        elif exercise.kind == KIND_FILL_BLANK:
            body = FillBlankExercise(self.shell.card, exercise)
        elif exercise.kind == KIND_GUIDED_WRITING:
            body = GuidedWritingExercise(self.shell.card, exercise)
        else:
            body = IndependentWritingExercise(self.shell.card, exercise)
        self.shell.swap_exercise(body)

    def _bank_changed(self, selected: list) -> None:
        self._bank_selected = list(selected)

    def _check(self) -> None:
        if self._phase != "answer" or self._checking or self._ai_pending:
            return
        if not self._binding_current():
            self._leave()
            return
        card = self.session.current_card()
        if card is None:
            return
        submission_id = self.session.begin_submission()
        if not submission_id:
            return
        self._checking = True
        self._active_submission_id = submission_id
        self._active_instance_id = card.instance_id
        try:
            exercise = card.exercise
            if exercise.kind == KIND_WORD_BANK:
                result = self.session.submit_local(
                    tokens=self._bank_selected,
                    submission_id=submission_id,
                    instance_id=card.instance_id,
                )
            else:
                answer = self.shell.exercise.answer_text()
                result = self.session.submit_local(
                    answer,
                    submission_id=submission_id,
                    instance_id=card.instance_id,
                )
            if result.status in ("empty", "incomplete"):
                self.shell.show_feedback(
                    result.feedback
                    or config.ui("Hãy nhập câu trả lời.", "Please enter an answer."),
                    "empty",
                )
                self._phase = "answer"
                return
            if result.status == "waiting_ai" and self.grade_service is not None:
                self._ai_pending = True
                self.shell.show_feedback(
                    config.ui("Đang chấm…", "Checking…"),
                    "near",
                )
                answer = self.shell.exercise.answer_text()
                grade_async(
                    self.window,
                    service=self.grade_service,
                    exercise=exercise,
                    learner_answer=answer,
                    still_current=lambda sid=submission_id, iid=card.instance_id: (
                        self._binding_current()
                        and self.session.submission_current(sid, iid)
                    ),
                    submission_id=submission_id,
                    on_done=lambda grade, text=answer, sid=submission_id, iid=card.instance_id: self._on_ai_grade(
                        grade, text, submission_id=sid, instance_id=iid
                    ),
                )
                return
            if result.status == "stale":
                return
            self._show_feedback_result(result)
        finally:
            self._checking = False

    def _on_ai_grade(self, grade, learner_answer: str, *, submission_id: str, instance_id: str) -> None:
        self._ai_pending = False
        if not self._binding_current():
            self.session.clear_submission(submission_id)
            return
        if not self.session.submission_current(submission_id, instance_id):
            return
        result = self.session.apply_external_grade(
            grade,
            learner_answer,
            submission_id=submission_id,
            instance_id=instance_id,
        )
        if result.status == "stale":
            return
        self._show_feedback_result(result)

    def _show_feedback_result(self, result) -> None:
        self._phase = "feedback"
        self._last_feedback = result
        exercise = result.submitted_exercise
        if exercise is None and self.session.results:
            last_id = self.session.results[-1].exercise_id
            for item in self.session.pack.exercises:
                if item.exercise_id == last_id:
                    exercise = item
                    break
        self._feedback_exercise = exercise
        tone = result.tone or "bad"
        feedback = result.feedback
        plan = speech_for_sentence(exercise, "feedback")
        self._update_progress()
        self.shell.show_feedback(
            feedback, tone, offer_sentence=False, offer_hear=plan.allowed
        )
        grade = result.grade
        if exercise and grade and grade.status in (
            STATUS_INCORRECT,
            STATUS_PROVISIONAL_CORRECT,
            STATUS_PROVISIONAL_ACCEPT,
            STATUS_REVIEWED_CORRECT,
        ):
            shown = ""
            if grade.status == STATUS_INCORRECT:
                shown = exercise.primary_answer()
            elif grade.status == STATUS_PROVISIONAL_CORRECT:
                shown = grade.corrected_sentence or exercise.primary_answer()
            elif grade.status == STATUS_PROVISIONAL_ACCEPT:
                shown = ""
            elif grade.status == STATUS_REVIEWED_CORRECT:
                shown = ""
            if shown and tone != "ok":
                self.shell.show_expected(shown, tone)
        self._companion = None
        if exercise is not None and grade is not None:
            if grade.status not in (STATUS_UNAVAILABLE, STATUS_UNGRADED):
                rules = self.session.rules_for(exercise)
                self._companion = build_companion(
                    exercise,
                    rules,
                    corrected_sentence=exercise.primary_answer(),
                    error_hint=grade.error_hint,
                    diagnosis_certain=grade.diagnosis_certain,
                    allow_ai_suggestion=False,
                )
        if plan.allowed:
            self.slow_hear_button.pack(pady=(4, 0))
        else:
            self.slow_hear_button.pack_forget()
        if self._companion is not None:
            self.why_button.pack(pady=(4, 0))
        else:
            self.why_button.pack_forget()

    def _toggle_grammar(self) -> None:
        if self._companion is None or self._phase != "feedback":
            return
        if self._grammar_open:
            self._hide_grammar()
            return
        self._grammar_open = True
        for child in self.grammar_host.winfo_children():
            child.destroy()
        view = self._companion
        box = ctk.CTkFrame(
            self.grammar_host, fg_color=ui_foundation.COLOR_SOFT_GREEN, corner_radius=12
        )
        box.pack(fill=tk.X, padx=8, pady=(4, 8))
        ctk.CTkLabel(
            box,
            text=view.title,
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color=ui_foundation.COLOR_TEXT,
            fg_color=ui_foundation.COLOR_SOFT_GREEN,
            anchor="w",
        ).pack(fill=tk.X, padx=12, pady=(10, 4))
        ctk.CTkLabel(
            box,
            text=view.beginner,
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=ui_foundation.COLOR_TEXT,
            fg_color=ui_foundation.COLOR_SOFT_GREEN,
            wraplength=460,
            justify="left",
            anchor="w",
        ).pack(fill=tk.X, padx=12, pady=(0, 6))
        ctk.CTkLabel(
            box,
            text=view.full,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#5C7268",
            fg_color=ui_foundation.COLOR_SOFT_GREEN,
            wraplength=460,
            justify="left",
            anchor="w",
        ).pack(fill=tk.X, padx=12, pady=(0, 8))
        if view.components:
            row = ctk.CTkFrame(box, fg_color=ui_foundation.COLOR_SOFT_GREEN, corner_radius=0)
            row.pack(fill=tk.X, padx=12, pady=(0, 8))
            for part in view.components:
                chip = ctk.CTkLabel(
                    row,
                    text=part.text,
                    font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                    text_color="#FFFFFF",
                    fg_color=component_color(part.role),
                    corner_radius=8,
                    padx=8,
                    pady=4,
                )
                chip.pack(side=tk.LEFT, padx=(0, 6))
        if view.corrected:
            ctk.CTkLabel(
                box,
                text=config.ui(f"Câu đúng: {view.corrected}", f"Corrected: {view.corrected}"),
                font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                text_color=ui_foundation.COLOR_PRIMARY,
                fg_color=ui_foundation.COLOR_SOFT_GREEN,
                wraplength=460,
                justify="left",
                anchor="w",
            ).pack(fill=tk.X, padx=12, pady=(0, 6))
        for example in view.examples:
            ctk.CTkLabel(
                box,
                text=f"• {example}",
                font=ctk.CTkFont(family="Segoe UI", size=12),
                text_color="#5C7268",
                fg_color=ui_foundation.COLOR_SOFT_GREEN,
                anchor="w",
            ).pack(fill=tk.X, padx=12, pady=(0, 2))
        self.grammar_host.pack(fill=tk.X, before=self.shell.continue_button)
        self.shell.continue_button.configure(state="normal")

    def _hide_grammar(self) -> None:
        self._grammar_open = False
        try:
            self.grammar_host.pack_forget()
        except tk.TclError:
            pass

    def _clear_feedback_extras(self) -> None:
        self._hide_grammar()
        try:
            self.why_button.pack_forget()
            self.slow_hear_button.pack_forget()
        except tk.TclError:
            pass

    def _continue(self) -> None:
        if self._phase != "feedback":
            return
        if not self._binding_current():
            self._leave()
            return
        self._clear_feedback_extras()
        if self.session.finished and self.session.levels_achieved() >= 4:
            self._show_complete()
            return
        self.session.continue_after_feedback()
        self._show_current()

    def _hear(self, rate: int) -> None:
        exercise = self._feedback_exercise
        plan = speech_for_sentence(exercise, "feedback" if self._phase == "feedback" else "answer")
        if not plan.allowed:
            return
        token = self._card_token
        language = self.session.language_code
        spoken = plan.text
        voice_name = voice_prefs.selected_voice_name(language) or None

        def scope() -> bool:
            if token != self._card_token:
                return False
            if not self._binding_current():
                return False
            current = speech_for_sentence(self._feedback_exercise, "feedback")
            return current.allowed and current.text == spoken

        started = play_async(
            self.window,
            text=spoken,
            language_code=language,
            rate=int(rate),
            voice_name=voice_name,
            provider=self.provider,
            scope=scope,
            on_error=lambda error, mark=token: self._voice_status(mark, _voice_problem(error)),
            on_done=lambda mark=token: self._voice_status(mark, ""),
        )
        if not started:
            self._voice_status(
                token,
                config.ui(
                    "Đang phát một đoạn khác. Bạn vẫn có thể tiếp tục.",
                    "Another clip is still playing. You can continue.",
                ),
            )
            return
        self._voice_status(token, config.ui("Đang phát…", "Playing…"))

    def _voice_status(self, token: int, text: str) -> None:
        if token != self._card_token:
            return
        note = getattr(self.shell.exercise, "support", None)
        if note is None:
            return
        try:
            if text:
                note.configure(text=text)
        except tk.TclError:
            pass

    def _show_complete(self) -> None:
        if self.session.abandoned or self.session.missing_content:
            self._show_left() if self.session.abandoned else self._show_missing()
            return
        if self.session.levels_achieved() < 4:
            # Repeating easier levels must not look like success.
            self._phase = "incomplete"
            self._clear_feedback_extras()
            self.shell.set_stage("")
            self._update_progress()
            self.shell.show_complete(
                config.ui("Chưa xong bốn mức.", "The four levels are not finished yet."),
                config.ui(
                    "Phiên câu chưa hoàn thành.",
                    "This sentence round is not complete.",
                ),
                config.ui("Để lúc khác", "Leave for now"),
                celebrate=False,
            )
            self.shell.continue_button.configure(command=self._leave)
            return
        self._phase = "complete"
        self._clear_feedback_extras()
        done, total = self.session.progress_pair()
        self.shell.set_stage("")
        self.shell.set_progress(done, total, f"{done}/{total}")
        self.shell.show_complete(
            config.ui("Xong phần luyện câu.", "Sentence practice is done."),
            config.ui(
                "Phần này không ghi tiến độ từ vựng hay SRS.\n"
                "Bạn có thể quay lại Study.",
                "This round does not write vocabulary progress or SRS.\n"
                "You can return to Study.",
            ),
            config.ui("Về Study", "Back to Study"),
            celebrate=True,
        )

    def _show_missing(self) -> None:
        self._phase = "missing"
        self._clear_feedback_extras()
        self.shell.set_stage("")
        self.shell.set_progress(0, 4, "0/4")
        self.shell.show_complete(
            config.ui("Chưa có bài câu.", "No sentence content is available."),
            config.ui(
                "Phiên này chưa hoàn thành.",
                "This is not a completed session.",
            ),
            config.ui("Để lúc khác", "Leave for now"),
            celebrate=False,
        )
        self.shell.continue_button.configure(command=self._leave)

    def _show_left(self) -> None:
        self._phase = "left"
        self._clear_feedback_extras()
        self.shell.set_stage("")
        self._update_progress()
        self.shell.show_complete(
            config.ui("Đã thoát luyện câu.", "Sentence practice was left."),
            config.ui(
                "Chưa hoàn thành. Tiến độ từ vựng không đổi.",
                "Not completed. Vocabulary progress is unchanged.",
            ),
            config.ui("Về Study", "Back to Study"),
            celebrate=False,
        )
        self.shell.continue_button.configure(command=self._leave)

    def _close_complete(self) -> None:
        if self._phase != "complete" or self._completion_calls:
            return
        if not self._binding_current():
            self._force_leave()
            return
        if not self.session.take_completion():
            self._force_leave()
            return
        self._completion_calls += 1
        self._phase = "closed"
        if callable(self.on_completed):
            self.on_completed()
        try:
            self.window.destroy()
        except tk.TclError:
            pass

    def _force_leave(self) -> None:
        """Leave without recursion through complete."""
        if self._leave_calls:
            return
        self._leave_calls += 1
        self._phase = "closed"
        if not self.session.abandoned:
            self.session.abandon()
        if callable(self.on_leave):
            self.on_leave()
        try:
            self.window.destroy()
        except tk.TclError:
            pass

    def _leave(self) -> None:
        if self._phase == "complete":
            # Binding may be invalid — never recurse into leave via close_complete.
            if not self._binding_current():
                self._force_leave()
                return
            self._close_complete()
            return
        if self._phase in ("closed",):
            return
        self._force_leave()

    def _on_destroy(self, event=None) -> None:
        if event is not None and event.widget is not self.window:
            return


def _stage_label(kind: str) -> str:
    labels = {
        KIND_WORD_BANK: ("Sắp xếp từ", "Word bank"),
        KIND_FILL_BLANK: ("Điền chỗ trống", "Fill the blank"),
        KIND_GUIDED_WRITING: ("Viết có mẫu", "Guided writing"),
        KIND_INDEPENDENT_WRITING: ("Tự viết câu", "Independent writing"),
    }
    pair = labels.get(kind)
    if pair is None:
        return ""
    return config.ui(*pair)


class _BaseSentenceBody:
    def set_enabled(self, enabled: bool) -> None:
        return None

    def show_support(self, text: str) -> None:
        return None

    def focus_answer(self) -> None:
        return None

    def clear_answer(self) -> None:
        return None

    def answer_text(self) -> str:
        return ""

    def choice_index(self):
        return None


class WordBankExercise(_BaseSentenceBody):
    kind = KIND_WORD_BANK

    def __init__(self, parent, exercise, on_change=None):
        self.exercise = exercise
        self.on_change = on_change
        self.selected: list = []
        self.frame = ctk.CTkFrame(parent, fg_color=ui_foundation.COLOR_CARD, corner_radius=0)
        ctk.CTkLabel(
            self.frame,
            text=exercise.prompt,
            font=ctk.CTkFont(family="Segoe UI", size=16),
            text_color="#5C7268",
            fg_color=ui_foundation.COLOR_CARD,
            wraplength=460,
        ).pack(pady=(8, 6))
        self.built = ctk.CTkLabel(
            self.frame,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=ui_foundation.COLOR_TEXT,
            fg_color=ui_foundation.COLOR_CARD,
            wraplength=460,
        )
        self.built.pack(pady=(0, 10))
        self.bank = ctk.CTkFrame(self.frame, fg_color=ui_foundation.COLOR_CARD, corner_radius=0)
        self.bank.pack(fill=tk.X, padx=8)
        self._buttons = []
        for token in exercise.word_bank:
            button = ctk.CTkButton(
                self.bank,
                text=token,
                width=64,
                height=36,
                corner_radius=10,
                fg_color=ui_foundation.COLOR_SOFT_GREEN,
                hover_color="#D7E8DC",
                text_color=ui_foundation.COLOR_TEXT,
                font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
                command=lambda t=token: self._pick(t),
            )
            button.pack(side=tk.LEFT, padx=4, pady=4)
            bind_activation(button)
            self._buttons.append((token, button))
        undo = ctk.CTkButton(
            self.frame,
            text=config.ui("Hoàn tác", "Undo"),
            height=32,
            corner_radius=10,
            fg_color="transparent",
            hover_color=ui_foundation.COLOR_SOFT_GREEN,
            text_color="#5C7268",
            command=self._undo,
        )
        undo.pack(pady=(8, 4))
        bind_activation(undo)
        translation = (
            exercise.translation_vi
            if config.native_code() == "vi"
            else exercise.translation_en
        )
        self.support = ctk.CTkLabel(
            self.frame,
            text=translation,
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color="#5C7268",
            fg_color=ui_foundation.COLOR_CARD,
        )
        self.support.pack(pady=(4, 0))

    def _pick(self, token: str) -> None:
        from collections import Counter

        bank_counts = Counter(t for t, _ in self._buttons)
        used_counts = Counter(self.selected)
        if used_counts.get(token, 0) >= bank_counts.get(token, 0):
            return
        self.selected.append(token)
        self._refresh()

    def _undo(self) -> None:
        if self.selected:
            self.selected.pop()
            self._refresh()

    def _refresh(self) -> None:
        from sentence_grading import join_tokens

        self.built.configure(text=join_tokens(self.selected))
        used_counts = {}
        for item in self.selected:
            used_counts[item] = used_counts.get(item, 0) + 1
        for token, button in self._buttons:
            count_token = sum(1 for t, _ in self._buttons if t == token)
            used = used_counts.get(token, 0)
            button.configure(state="disabled" if used >= count_token else "normal")
        if callable(self.on_change):
            self.on_change(self.selected)

    def answer_text(self) -> str:
        from sentence_grading import join_tokens

        return join_tokens(self.selected)

    def clear_answer(self) -> None:
        self.selected.clear()
        self._refresh()

    def set_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for _token, button in self._buttons:
            button.configure(state=state)


class FillBlankExercise(_BaseSentenceBody):
    kind = KIND_FILL_BLANK

    def __init__(self, parent, exercise):
        self.exercise = exercise
        self._blank = exercise.blank_sentence
        self.frame = ctk.CTkFrame(parent, fg_color=ui_foundation.COLOR_CARD, corner_radius=0)
        ctk.CTkLabel(
            self.frame,
            text=exercise.prompt,
            font=ctk.CTkFont(family="Segoe UI", size=16),
            text_color="#5C7268",
            fg_color=ui_foundation.COLOR_CARD,
            wraplength=460,
        ).pack(pady=(8, 6))
        ctk.CTkLabel(
            self.frame,
            text=exercise.blank_sentence,
            font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"),
            text_color=ui_foundation.COLOR_TEXT,
            fg_color=ui_foundation.COLOR_CARD,
        ).pack(pady=(0, 10))
        self.entry = ctk.CTkEntry(
            self.frame,
            height=48,
            corner_radius=12,
            justify="center",
            font=ctk.CTkFont(family="Segoe UI", size=20),
            fg_color="#FFFFFF",
            border_color=ui_foundation.COLOR_BORDER,
            text_color=ui_foundation.COLOR_TEXT,
        )
        self.entry.pack(fill=tk.X, padx=8, pady=(0, 8))
        translation = (
            exercise.translation_vi
            if config.native_code() == "vi"
            else exercise.translation_en
        )
        self.support = ctk.CTkLabel(
            self.frame,
            text=translation,
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color="#5C7268",
            fg_color=ui_foundation.COLOR_CARD,
        )
        self.support.pack()

    def answer_text(self) -> str:
        typed = self.entry.get().strip()
        if not typed:
            return ""
        if "___" in self._blank and " " not in typed:
            return self._blank.replace("___", typed)
        return typed

    def clear_answer(self) -> None:
        self.entry.delete(0, "end")

    def set_enabled(self, enabled: bool) -> None:
        self.entry.configure(state="normal" if enabled else "disabled")

    def focus_answer(self) -> None:
        try:
            self.entry.focus_set()
        except tk.TclError:
            pass


class GuidedWritingExercise(_BaseSentenceBody):
    kind = KIND_GUIDED_WRITING

    def __init__(self, parent, exercise):
        self.exercise = exercise
        self.frame = ctk.CTkFrame(parent, fg_color=ui_foundation.COLOR_CARD, corner_radius=0)
        ctk.CTkLabel(
            self.frame,
            text=exercise.prompt,
            font=ctk.CTkFont(family="Segoe UI", size=16),
            text_color="#5C7268",
            fg_color=ui_foundation.COLOR_CARD,
            wraplength=460,
        ).pack(pady=(8, 4))
        ctk.CTkLabel(
            self.frame,
            text=exercise.grammar_template,
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color=ui_foundation.COLOR_PRIMARY,
            fg_color=ui_foundation.COLOR_SOFT_GREEN,
            corner_radius=8,
            padx=10,
            pady=6,
        ).pack(pady=(4, 10))
        self.entry = ctk.CTkEntry(
            self.frame,
            height=48,
            corner_radius=12,
            justify="center",
            font=ctk.CTkFont(family="Segoe UI", size=18),
            fg_color="#FFFFFF",
            border_color=ui_foundation.COLOR_BORDER,
            text_color=ui_foundation.COLOR_TEXT,
        )
        self.entry.pack(fill=tk.X, padx=8, pady=(0, 8))
        translation = (
            exercise.translation_vi
            if config.native_code() == "vi"
            else exercise.translation_en
        )
        self.support = ctk.CTkLabel(
            self.frame,
            text=translation,
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color="#5C7268",
            fg_color=ui_foundation.COLOR_CARD,
        )
        self.support.pack()

    def answer_text(self) -> str:
        return self.entry.get().strip()

    def clear_answer(self) -> None:
        self.entry.delete(0, "end")

    def set_enabled(self, enabled: bool) -> None:
        self.entry.configure(state="normal" if enabled else "disabled")

    def focus_answer(self) -> None:
        try:
            self.entry.focus_set()
        except tk.TclError:
            pass


class IndependentWritingExercise(_BaseSentenceBody):
    kind = KIND_INDEPENDENT_WRITING

    def __init__(self, parent, exercise):
        self.exercise = exercise
        self.frame = ctk.CTkFrame(parent, fg_color=ui_foundation.COLOR_CARD, corner_radius=0)
        ctk.CTkLabel(
            self.frame,
            text=exercise.prompt,
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color=ui_foundation.COLOR_TEXT,
            fg_color=ui_foundation.COLOR_CARD,
            wraplength=460,
        ).pack(pady=(12, 10))
        self.entry = ctk.CTkEntry(
            self.frame,
            height=48,
            corner_radius=12,
            justify="center",
            font=ctk.CTkFont(family="Segoe UI", size=18),
            fg_color="#FFFFFF",
            border_color=ui_foundation.COLOR_BORDER,
            text_color=ui_foundation.COLOR_TEXT,
        )
        self.entry.pack(fill=tk.X, padx=8, pady=(0, 8))
        self.support = ctk.CTkLabel(
            self.frame,
            text=config.ui(
                "Viết câu hoàn chỉnh bằng tiếng đang học.",
                "Write a full sentence in the study language.",
            ),
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color="#5C7268",
            fg_color=ui_foundation.COLOR_CARD,
        )
        self.support.pack()

    def answer_text(self) -> str:
        return self.entry.get().strip()

    def clear_answer(self) -> None:
        self.entry.delete(0, "end")

    def set_enabled(self, enabled: bool) -> None:
        self.entry.configure(state="normal" if enabled else "disabled")

    def focus_answer(self) -> None:
        try:
            self.entry.focus_set()
        except tk.TclError:
            pass


def build_demo_grade_service(mode: str = "accept_valid"):
    """Inject a deterministic fake provider through AIService."""
    from ai.service import AIService

    return AIService(provider=FakeSentenceGradeProvider(mode=mode))
