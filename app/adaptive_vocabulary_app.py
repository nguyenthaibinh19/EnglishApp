"""Unlocked adaptive vocabulary window. The legacy quiz is unchanged.

This window is the development preview. StudyMaster keeps VocabQuizApp, and a
locked session is refused here.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import config
import ui_common
import ui_foundation
import voice_prefs
from adaptive_vocabulary import (
    AdaptivePreviewRefused,
    AdaptiveSessionBridge,
    AdaptiveVocabularySession,
    apply_independent_write,
    speech_for_card,
)
from attempt_history import utc_now_iso
from listening_windows_tts import NORMAL_RATE, SLOW_RATE
from speech_player import play_async
from study_presentation import (
    IntroductionExercise,
    MultipleChoiceExercise,
    StudyCardShell,
    TypingExercise,
)
from vocabulary_model import entry_example

# Compact study card. Four choices plus the whole-word line need more than the
# legacy 560×520 quiz, so this preview is 560×640. Minimum is 480×560.
PREVIEW_WIDTH = 560
PREVIEW_HEIGHT = 640


class AdaptiveVocabularyApp:
    def __init__(
        self,
        window: tk.Misc,
        session: AdaptiveVocabularySession,
        *,
        bridge: AdaptiveSessionBridge = None,
        progress=None,
        attempts=None,
        on_completed=None,
        on_leave=None,
        provider=None,
        locked: bool = False,
    ):
        if locked:
            raise AdaptivePreviewRefused("Locked sessions stay on the legacy quiz.")
        self.window = window
        self.session = session
        self.bridge = bridge
        self.progress = progress
        self.attempts = attempts
        self.on_completed = on_completed
        self.on_leave = on_leave
        self.provider = provider
        self._phase = "answer"
        self._checking = False
        self._completion_calls = 0
        self._applied_writes = 0
        self._card_token = 0
        self.window.title("LanguageGuard — Adaptive vocabulary preview")
        self.guard = ui_common.ScreenGuard(
            window,
            enabled=False,
            on_close_attempt=self._leave,
            on_unlocked_close=self._leave,
        )
        # ScreenGuard's unlocked path sets 1280×820. The study card then uses
        # the compact size. Lock stays off.
        if not self.guard.enabled:
            try:
                self.window.geometry(f"{PREVIEW_WIDTH}x{PREVIEW_HEIGHT}")
                self.window.minsize(480, 560)
                self.window.configure(bg=ui_foundation.COLOR_BG)
            except tk.TclError:
                pass
        self._build()
        self.window.bind("<Return>", self._on_return)
        self.window.bind("<KP_Enter>", self._on_return)
        for digit, index in (("1", 0), ("2", 1), ("3", 2), ("4", 3)):
            self.window.bind(digit, lambda _event, i=index: self._select_choice(i))
        self._show_current()

    def _build(self) -> None:
        self.container = ttk.Frame(self.window, padding=12)
        self.container.pack(fill=tk.BOTH, expand=True)
        self.shell = StudyCardShell(
            self.container,
            locked=False,
            on_check=self._check,
            on_hint=self._help,
            on_continue=self._continue,
            on_done=self._close_complete,
            on_sentence=lambda: None,
            on_hear=lambda: self._hear(NORMAL_RATE),
            on_leave=self._leave,
            on_emergency=self._leave,
        )
        self.shell.set_copy(
            check=config.ui("Kiểm tra", "Check answer"),
            hint=config.ui("Cần gợi ý", "Need a hint"),
            continue_text=config.ui("Tiếp tục", "Continue"),
            leave=config.ui("Để lúc khác", "Leave for now"),
            emergency=config.ui("Thoát khẩn cấp", "Emergency exit"),
        )
        self.shell.hear_button.configure(text=config.ui("Nghe từ", "Hear the word"))
        self.shell.pack(fill=tk.BOTH, expand=True)

    def _on_return(self, _event=None):
        if self._phase == "feedback":
            self._continue()
        elif self._phase == "complete":
            self._close_complete()
        elif self._phase == "answer":
            self._check()
        return "break"

    def _select_choice(self, index: int):
        exercise = self.shell.exercise
        select = getattr(exercise, "_select", None)
        if self._phase == "answer" and callable(select) and index < len(getattr(exercise, "buttons", ())):
            select(index)
        return "break"

    def _show_current(self) -> None:
        if self.session.finished:
            self._show_complete()
            return
        card = self.session.current_card()
        if card is None:
            self._show_empty()
            return
        self._phase = "answer"
        self._card_token += 1
        self._mount(card)
        show_hint = card.kind == "independent_recall"
        self.shell.check_button.configure(
            text=config.ui("Tiếp tục", "Continue")
            if card.kind == "introduction"
            else config.ui("Kiểm tra", "Check answer")
        )
        self.shell.show_answering(show_hint=show_hint, clear_support=False)
        self._update_progress()
        if hasattr(self.shell.exercise, "entry"):
            inner = getattr(self.shell.exercise.entry, "_entry", self.shell.exercise.entry)
            inner.bind("<Return>", self._on_return, add="+")

    def _mount(self, card) -> None:
        if card.kind == "introduction":
            exercise = IntroductionExercise(self.shell.card, card, self._hear)
        elif card.kind == "multiple_choice":
            exercise = MultipleChoiceExercise(self.shell.card, card)
        else:
            exercise = TypingExercise(self.shell.card, card, card.kind)
        self.shell.swap_exercise(exercise)

    def _update_progress(self) -> None:
        done = self.session.counters.words_completed
        total = max(self.session.counters.planned, 1)
        mastered = self.session.counters.independent_mastered
        label = config.ui(f"Đã luyện {done}/{total}", f"{done}/{total} practiced")
        self.shell.set_progress(done, total, label)
        # The fraction is independent session progress, not SRS mastery.
        _ = mastered

    def _check(self) -> None:
        if self._phase != "answer" or self._checking:
            return
        card = self.session.current_card()
        if card is None:
            return
        self._checking = True
        try:
            self._check_card(card)
        finally:
            self._checking = False

    def _check_card(self, card) -> None:
        if card.kind == "introduction":
            self.session.continue_card()
            self._show_current()
            return
        exercise = self.shell.exercise
        result = self.session.submit(
            exercise.answer_text(),
            choice_index=exercise.choice_index(),
        )
        if result.status == "empty":
            self.shell.show_feedback(result.feedback, "empty")
            self._phase = "answer"
            return
        if result.status != "feedback":
            return
        self._apply_write(result)
        self._phase = "feedback"
        self._update_progress()
        self.shell.show_feedback(
            result.feedback,
            result.tone or "bad",
            offer_sentence=False,
            offer_hear=speech_for_card(card, "feedback").allowed,
        )

    def _help(self) -> None:
        if self._phase != "answer":
            return
        result = self.session.request_assistance()
        if result.status == "help":
            self._show_current()

    def _continue(self) -> None:
        if self._phase != "feedback":
            return
        result = self.session.continue_card()
        if result.session_finished or self.session.finished:
            self._show_complete()
            return
        self._show_current()

    def _apply_write(self, result) -> None:
        if result.write is None or self.progress is None or self.attempts is None:
            return
        apply_independent_write(
            self.progress,
            self.attempts,
            result.write,
            timestamp=utc_now_iso(),
        )
        self._applied_writes += 1

    def _hear(self, rate: int) -> None:
        card = self.session.current_card()
        phase = "feedback" if self._phase == "feedback" else "answer"
        plan = speech_for_card(card, phase)
        if card is None or not plan.allowed:
            return
        token = self._card_token
        language = card.language_code
        spoken = plan.text
        spoken_rate = int(rate)
        voice_name = voice_prefs.selected_voice_name(language) or None

        def scope() -> bool:
            if token != self._card_token:
                return False
            try:
                alive = bool(self.window.winfo_exists())
            except tk.TclError:
                return False
            if not alive:
                return False
            current_phase = "feedback" if self._phase == "feedback" else "answer"
            current = speech_for_card(self.session.current_card(), current_phase)
            return current.allowed and current.text == spoken

        started = play_async(
            self.window,
            text=spoken,
            language_code=language,
            rate=spoken_rate,
            voice_name=voice_name,
            provider=self.provider,
            scope=scope,
            on_error=lambda error, mark=token: self._voice_status(mark, str(error)),
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
        note = getattr(self.shell.exercise, "voice_note", None)
        if note is None:
            return
        try:
            note.configure(text=text)
        except tk.TclError:
            pass

    def _show_empty(self) -> None:
        """An empty plan is not a finished study session."""
        self._phase = "empty"
        self.shell.show_complete(
            config.ui("Chưa có từ trong phiên này.", "This session has no planned words."),
            config.ui("Phiên này chưa hoàn thành.", "This is not a completed session."),
            config.ui("Để lúc khác", "Leave for now"),
        )
        self.shell.continue_button.configure(command=self._leave)

    def _show_complete(self) -> None:
        self._phase = "complete"
        counters = self.session.counters
        detail = config.ui(
            f"{counters.independent_session_correct} câu nhớ độc lập trong phiên. "
            f"{counters.independent_mastered} câu đã thuộc. "
            "Câu gần đúng không phải đã thuộc. Bài nhận diện và bài có hỗ trợ không tính vào số này.",
            f"{counters.independent_session_correct} independent session answers. "
            f"{counters.independent_mastered} mastered. "
            "A near answer is not mastery. Assisted practice stays out of this count.",
        )
        self.shell.show_complete(
            config.ui("Xong phần từ vựng.", "Vocabulary done."),
            detail,
            config.ui("Về hôm nay", "Back"),
        )

    def _close_complete(self) -> None:
        if self._phase != "complete" or self._completion_calls:
            return
        self._completion_calls += 1
        self._phase = "closed"
        notified = False
        if self.bridge is not None:
            notified = self.bridge.note_finished()
        if notified and callable(self.on_completed):
            self.on_completed()
        try:
            self.window.destroy()
        except tk.TclError:
            pass

    def _leave(self) -> None:
        if self._phase == "complete":
            self._close_complete()
            return
        if self.bridge is not None:
            self.bridge.leave()
        if callable(self.on_leave):
            self.on_leave()
        try:
            self.window.destroy()
        except tk.TclError:
            pass


def example_sentence_is_stored(entry: dict) -> str:
    """Introduction may show only the example already on the vocabulary record."""
    return entry_example(entry)
