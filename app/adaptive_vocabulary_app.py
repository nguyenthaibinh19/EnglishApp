"""Unlocked adaptive vocabulary window. The legacy quiz is unchanged.

Locked ScreenGuard sessions stay on VocabQuizApp. Development StudyMaster may
open this window when ScreenGuard is not locking the learner.
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
    MissingLettersExercise,
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
        practice_store=None,
        practice_persistence: str = "ok",
        identity=None,
        locked: bool = False,
        account_generation_reader=None,
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
        self.practice_store = practice_store
        # ok | unavailable | disabled — unavailable must never look like a successful save.
        self.practice_persistence = str(practice_persistence or "ok").strip().lower()
        self.identity = identity
        self.account_generation_reader = account_generation_reader
        self.practice_saved = 0
        self.practice_unsaved = 0
        self._unsaved_notice = ""
        self._phase = "answer"
        self._checking = False
        self._completion_calls = 0
        self._applied_writes = 0
        self._authoritative_write_failed = False
        self._card_token = 0
        self.window.title(
            config.ui(
                "LanguageGuard — Học thích ứng",
                "LanguageGuard — Adaptive study",
            )
        )
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
        self.window.bind("<Destroy>", self._on_destroy, add="+")
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
        self.shell.set_stage(_stage_label(card.kind))
        self.shell.show_answering(show_hint=show_hint, clear_support=False)
        self._update_progress()
        inputs = getattr(self.shell.exercise, "inputs", None) or []
        if inputs:
            for entry in inputs:
                inner = getattr(entry, "_entry", entry)
                inner.bind("<Return>", self._on_return, add="+")
                inner.bind("<KP_Enter>", self._on_return, add="+")
        elif hasattr(self.shell.exercise, "entry"):
            inner = getattr(self.shell.exercise.entry, "_entry", self.shell.exercise.entry)
            inner.bind("<Return>", self._on_return, add="+")

    def _mount(self, card) -> None:
        if card.kind == "introduction":
            exercise = IntroductionExercise(self.shell.card, card, self._hear)
        elif card.kind == "multiple_choice":
            exercise = MultipleChoiceExercise(self.shell.card, card)
        elif card.kind == "missing_letters":
            exercise = MissingLettersExercise(self.shell.card, card)
        else:
            exercise = TypingExercise(self.shell.card, card, card.kind)
        self.shell.swap_exercise(exercise)

    def _update_progress(self) -> None:
        done = self.session.counters.words_completed
        total = max(self.session.counters.planned, 1)
        mastered = self.session.counters.independent_mastered
        label = f"{done}/{total}"
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
        if not self._binding_current():
            self._reject_stale_action()
            return
        if card.kind == "introduction":
            result = self.session.continue_card()
            self._persist_practice(result.practice)
            self._show_current()
            self._show_unsaved_notice()
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
        if not self._binding_current():
            self._reject_stale_action()
            return
        saved = self._persist_practice(result.practice)
        wrote = self._apply_write(result)
        if result.write is not None and not wrote:
            # Independent success without an authoritative write must not complete.
            self._authoritative_write_failed = True
            self._phase = "feedback"
            self.shell.show_feedback(
                config.ui(
                    "Không ghi được câu trả lời tự nhớ. Phiên này chưa hoàn thành.",
                    "The independent answer could not be saved. This session is not complete.",
                ),
                "bad",
                offer_sentence=False,
                offer_hear=False,
            )
            return
        self._phase = "feedback"
        self._update_progress()
        tone = result.tone or "bad"
        feedback = result.feedback
        if result.practice is not None and not saved:
            feedback = f"{feedback}\n\n{self._practice_failure_text()}"
        self.shell.show_feedback(
            feedback,
            tone,
            offer_sentence=False,
            offer_hear=speech_for_card(card, "feedback").allowed,
        )
        if card.kind == "multiple_choice":
            mark = getattr(exercise, "mark_result", None)
            if callable(mark):
                mark(card.correct_index, exercise.choice_index())
        elif tone != "empty" and card.reveal_word:
            self.shell.show_expected(card.reveal_word, tone)

    def _help(self) -> None:
        if self._phase != "answer":
            return
        if not self._binding_current():
            self._reject_stale_action()
            return
        result = self.session.request_assistance()
        if result.status == "help":
            self._show_current()

    def _continue(self) -> None:
        if self._phase != "feedback":
            return
        if not self._binding_current():
            self._reject_stale_action()
            return
        if self._authoritative_write_failed:
            self._leave()
            return
        result = self.session.continue_card()
        if result.session_finished or self.session.finished:
            self._show_complete()
            return
        self._show_current()

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

    def _reject_stale_action(self) -> None:
        self._unsaved_notice = config.ui(
            "Phiên học này đã hết hiệu lực. Không ghi thêm câu trả lời.",
            "This study window is no longer current. No further answers were saved.",
        )
        self._show_unsaved_notice()
        self._leave()

    def _practice_failure_text(self) -> str:
        if self.practice_persistence == "unavailable":
            return config.ui(
                "Không dùng được lịch sử luyện Adaptive. Câu trả lời tự nhớ vẫn được ghi.",
                "Adaptive practice history is unavailable. Independent answers are still recorded.",
            )
        return _unsaved_practice()

    def _persist_practice(self, record) -> bool:
        """Save one practice event. False means the learner must be told it was not saved."""
        if record is None:
            return True
        if self.practice_persistence == "disabled" and self.practice_store is None:
            # Intentionally off — not a failed save.
            return True
        if self.practice_persistence == "unavailable" or self.practice_store is None:
            self.practice_unsaved += 1
            self._unsaved_notice = self._practice_failure_text()
            return False
        if not self._binding_current():
            self.practice_unsaved += 1
            self._unsaved_notice = _unsaved_practice()
            return False
        from practice_store import PracticeStoreError

        try:
            self.practice_store.append(record)
        except PracticeStoreError:
            self.practice_unsaved += 1
            self._unsaved_notice = _unsaved_practice()
            return False
        self.practice_saved += 1
        self._unsaved_notice = ""
        return True

    def _show_unsaved_notice(self) -> None:
        notice = getattr(self, "_unsaved_notice", "")
        if not notice:
            return
        note = getattr(self.shell.exercise, "voice_note", None)
        if note is None:
            return
        try:
            note.configure(text=notice)
            note.pack(pady=(2, 0))
        except tk.TclError:
            pass
        self._unsaved_notice = ""

    def _apply_write(self, result) -> bool:
        """Apply one independent write. False means no authoritative learning evidence."""
        if result.write is None:
            return True
        if self.progress is None or self.attempts is None:
            return False
        if not self._binding_current():
            return False
        apply_independent_write(
            self.progress,
            self.attempts,
            result.write,
            timestamp=utc_now_iso(),
        )
        self._applied_writes += 1
        return True

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
        note = getattr(self.shell.exercise, "voice_note", None)
        if note is None:
            return
        try:
            note.configure(text=text)
            if text:
                note.pack(pady=(2, 0))
            else:
                note.pack_forget()
        except tk.TclError:
            pass

    def _show_empty(self) -> None:
        """An empty plan is not a finished study session."""
        self._phase = "empty"
        self.shell.set_stage("")
        self.shell.set_progress(0, 0, "0/0")
        self.shell.show_complete(
            config.ui("Chưa có từ trong phiên này.", "This session has no planned words."),
            config.ui("Phiên này chưa hoàn thành.", "This is not a completed session."),
            config.ui("Để lúc khác", "Leave for now"),
            celebrate=False,
        )
        self.shell.continue_button.configure(command=self._leave)

    def _show_complete(self) -> None:
        self._phase = "complete"
        self._update_progress()
        self.shell.set_stage("")
        counters = self.session.counters
        detail = config.ui(
            f"{counters.words_completed} từ đã luyện trong phiên này.\n"
            f"{counters.independent_mastered} từ trả lời đúng khi tự nhớ.",
            f"{counters.words_completed} words practiced this session.\n"
            f"{counters.independent_mastered} answered exactly on your own.",
        )
        waiting = _still_waiting(self.bridge)
        if waiting:
            detail = f"{detail}\n\n{waiting}"
        self.shell.show_complete(
            config.ui("Xong phần từ vựng.", "This vocabulary round is done."),
            detail,
            config.ui("Về hôm nay", "Back"),
            celebrate=True,
        )

    def _close_practice_store(self) -> None:
        store = self.practice_store
        self.practice_store = None
        if store is None:
            return
        closer = getattr(store, "close", None)
        if callable(closer):
            try:
                closer()
            except Exception:
                pass

    def _on_destroy(self, event=None) -> None:
        if event is not None and event.widget is not self.window:
            return
        self._close_practice_store()

    def _close_complete(self) -> None:
        if self._phase != "complete" or self._completion_calls:
            return
        if self._authoritative_write_failed or not self._binding_current():
            self._leave()
            return
        self._completion_calls += 1
        self._phase = "closed"
        notified = False
        if self.bridge is not None and self._binding_current():
            notified = self.bridge.note_finished()
        if notified and callable(self.on_completed):
            self.on_completed()
        self._close_practice_store()
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
        self._close_practice_store()
        try:
            self.window.destroy()
        except tk.TclError:
            pass


def _stage_label(kind: str) -> str:
    labels = {
        "introduction": ("Làm quen", "Introduction"),
        "multiple_choice": ("Chọn từ", "Choose"),
        "missing_letters": ("Điền chữ", "Fill the letters"),
        "guided_typing": ("Gõ từ", "Type the word"),
        "independent_recall": ("Tự nhớ", "Recall"),
    }
    pair = labels.get(kind)
    if pair is None:
        return ""
    return config.ui(*pair)


def _voice_unavailable(error: Exception) -> bool:
    """True when this language has no local voice. Other playback errors stay separate."""
    text = str(error or "").casefold()
    markers = (
        "no voice",
        "no windows text-to-speech voice",
        "text-to-speech voice is installed",
        "chưa có giọng",
        "chưa cài giọng",
    )
    return any(marker in text for marker in markers)


def _unsaved_practice() -> str:
    return config.ui(
        "Kết quả luyện này chưa được lưu.",
        "This practice result was not saved.",
    )


def _voice_problem(error: Exception) -> str:
    """Learner-facing voice note. Shown only after a playback attempt."""
    if _voice_unavailable(error):
        return config.ui(
            "Chưa có giọng cho ngôn ngữ này trên máy này. Bạn vẫn có thể tiếp tục.",
            "No voice for this language on this PC. You can continue.",
        )
    return config.ui(
        "Không phát được âm thanh. Bạn vẫn có thể tiếp tục.",
        "Playback did not finish. You can continue.",
    )


def _still_waiting(bridge) -> str:
    """Optional activities stay pending. Completing vocabulary is not the whole day."""
    if bridge is None:
        return ""
    study = getattr(bridge, "study_session", None)
    if study is None:
        return ""
    reading = study.status("reading") == "pending"
    listening = study.status("listening") == "pending"
    if reading and listening:
        return config.ui("Đọc và nghe vẫn còn.", "Reading and listening are still waiting.")
    if reading:
        return config.ui("Phần đọc vẫn còn.", "Reading is still waiting.")
    if listening:
        return config.ui("Phần nghe vẫn còn.", "Listening is still waiting.")
    return ""


def example_sentence_is_stored(entry: dict) -> str:
    """Introduction may show only the example already on the vocabulary record."""
    return entry_example(entry)
