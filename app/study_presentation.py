"""Study card presentation for the current recall step.

The shell is the shared frame. The legacy quiz still mounts only independent
typing. Adaptive vocabulary mounts the other exercise bodies itself.
"""

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

import ui_foundation
from ctk_keyboard import bind_activation

# Same Tk root and main loop as the rest of the app. No CTk() window.
ctk.deactivate_automatic_dpi_awareness()
ctk.set_appearance_mode("light")

# Future cards. Not constructed and not shown.
FUTURE_EXERCISE_KINDS = (
    "multiple_choice",
    "missing_letters",
    "guided_typing",
    "sentence_arrangement",
    "fill_blank",
    "grammar_explanation",
    "audio_playback",
)
ACTIVE_EXERCISE_KIND = "independent_typing"


class IndependentTyping:
    """One meaning, one typed answer. This is the only exercise this wave shows."""

    kind = ACTIVE_EXERCISE_KIND

    def __init__(self, parent):
        self.frame = ctk.CTkFrame(parent, fg_color=ui_foundation.COLOR_CARD, corner_radius=0)
        self.kicker = ctk.CTkLabel(
            self.frame,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=15),
            text_color="#5C7268",
            fg_color=ui_foundation.COLOR_CARD,
            wraplength=460,
            justify="center",
        )
        self.kicker.pack(pady=(8, 6))
        self.question = ctk.CTkLabel(
            self.frame,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=28, weight="bold"),
            text_color=ui_foundation.COLOR_TEXT,
            fg_color=ui_foundation.COLOR_CARD,
            wraplength=460,
            justify="center",
        )
        self.question.pack(pady=(0, 12))
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
        self.support = ctk.CTkLabel(
            self.frame,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=14),
            text_color="#5C7268",
            fg_color=ui_foundation.COLOR_CARD,
            wraplength=460,
            justify="center",
        )
        self.support.pack(pady=(0, 4))

    def set_prompt(self, kicker: str, question: str) -> None:
        self.kicker.configure(text=kicker)
        self.question.configure(text=question)

    def answer_text(self) -> str:
        return self.entry.get().strip()

    def clear_answer(self) -> None:
        self.entry.delete(0, "end")

    def set_enabled(self, enabled: bool) -> None:
        self.entry.configure(state="normal" if enabled else "disabled")

    def show_support(self, text: str) -> None:
        self.support.configure(text=text)

    def focus_answer(self) -> None:
        try:
            self.entry.focus_set()
        except tk.TclError:
            pass


class StudyCardShell:
    """Progress, one card, one primary action, and a quiet way out."""

    def __init__(
        self,
        parent,
        *,
        locked: bool,
        on_check,
        on_hint,
        on_continue,
        on_done,
        on_sentence,
        on_hear,
        on_leave,
        on_emergency,
    ):
        self._on_continue = on_continue
        self._on_done = on_done
        self._on_hear = on_hear
        self.host = ctk.CTkFrame(parent, fg_color=ui_foundation.COLOR_BG, corner_radius=0)
        header = ctk.CTkFrame(self.host, fg_color=ui_foundation.COLOR_BG, corner_radius=0)
        header.pack(fill=tk.X, padx=8, pady=(4, 8))
        self.counter = ctk.CTkLabel(
            header,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color=ui_foundation.COLOR_TEXT,
            fg_color=ui_foundation.COLOR_BG,
        )
        self.counter.pack(side=tk.LEFT)
        self.leave_button = ctk.CTkButton(
            header,
            text="Leave for now",
            command=on_leave,
            width=108,
            height=32,
            corner_radius=10,
            fg_color="transparent",
            hover_color=ui_foundation.COLOR_SOFT_GREEN,
            text_color="#5C7268",
            font=ctk.CTkFont(family="Segoe UI", size=13),
        )
        self.emergency_button = ctk.CTkButton(
            header,
            text="Emergency exit",
            command=on_emergency,
            width=140,
            height=32,
            corner_radius=10,
            fg_color=ui_foundation.COLOR_WARM,
            hover_color="#E8C98A",
            text_color=ui_foundation.COLOR_TEXT,
            font=ctk.CTkFont(family="Segoe UI", size=13),
        )
        if locked:
            self.emergency_button.pack(side=tk.RIGHT)
        else:
            self.leave_button.pack(side=tk.RIGHT)
        bind_activation(self.leave_button)
        bind_activation(self.emergency_button)

        self.progress = ctk.CTkProgressBar(
            self.host,
            height=8,
            corner_radius=6,
            progress_color=ui_foundation.COLOR_PRIMARY,
            fg_color=ui_foundation.COLOR_BORDER,
        )
        self.progress.pack(fill=tk.X, padx=8, pady=(0, 12))
        self.progress.set(0)

        self.card = ctk.CTkFrame(
            self.host,
            fg_color=ui_foundation.COLOR_CARD,
            corner_radius=18,
            border_width=0,
        )
        self.card.pack(fill=tk.X, padx=4, pady=(0, 8))

        self.exercise = IndependentTyping(self.card)
        self.exercise.frame.pack(fill=tk.X, padx=18, pady=(22, 8))

        self.feedback = ctk.CTkLabel(
            self.card,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=16),
            text_color=ui_foundation.COLOR_TEXT,
            fg_color=ui_foundation.COLOR_CARD,
            wraplength=460,
            justify="center",
        )
        self.feedback.pack(fill=tk.X, padx=18, pady=(4, 8))

        actions = ctk.CTkFrame(self.card, fg_color=ui_foundation.COLOR_CARD, corner_radius=0)
        actions.pack(fill=tk.X, padx=18, pady=(0, 18))
        self.hint_button = ctk.CTkButton(
            actions,
            text="Hint",
            command=on_hint,
            height=32,
            corner_radius=10,
            fg_color="transparent",
            hover_color=ui_foundation.COLOR_SOFT_GREEN,
            text_color=ui_foundation.COLOR_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=14),
        )
        self.hint_button.pack(pady=(0, 8))
        self.check_button = ctk.CTkButton(
            actions,
            text="Check answer",
            command=on_check,
            height=46,
            corner_radius=14,
            fg_color=ui_foundation.COLOR_PRIMARY,
            hover_color=ui_foundation.COLOR_PRIMARY_ACTIVE,
            text_color=ui_foundation.COLOR_ON_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
        )
        self.check_button.pack(fill=tk.X)
        self.continue_button = ctk.CTkButton(
            actions,
            text="Continue",
            command=on_continue,
            height=46,
            corner_radius=14,
            fg_color=ui_foundation.COLOR_PRIMARY,
            hover_color=ui_foundation.COLOR_PRIMARY_ACTIVE,
            text_color=ui_foundation.COLOR_ON_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
        )
        self.sentence_button = ctk.CTkButton(
            actions,
            text="Write a sentence",
            command=on_sentence,
            height=32,
            corner_radius=10,
            fg_color="transparent",
            hover_color=ui_foundation.COLOR_SOFT_GREEN,
            text_color="#5C7268",
            font=ctk.CTkFont(family="Segoe UI", size=14),
        )
        self.hear_button = ctk.CTkButton(
            actions,
            text="Hear the word",
            command=on_hear,
            height=32,
            corner_radius=10,
            fg_color="transparent",
            hover_color=ui_foundation.COLOR_SOFT_GREEN,
            text_color="#5C7268",
            font=ctk.CTkFont(family="Segoe UI", size=14),
        )
        bind_activation(self.hint_button)
        bind_activation(self.check_button)
        bind_activation(self.continue_button)
        bind_activation(self.sentence_button)
        bind_activation(self.hear_button)

    def pack(self, **kwargs) -> None:
        self.host.pack(**kwargs)

    def set_progress(self, completed: int, total: int, label: str | None = None) -> None:
        total = max(int(total), 1)
        completed = max(0, min(int(completed), total))
        self.counter.configure(text=label if label else f"{completed}/{total}")
        if completed <= 0:
            self.progress.configure(progress_color=ui_foundation.COLOR_BORDER)
            self.progress.set(0)
        else:
            self.progress.configure(progress_color=ui_foundation.COLOR_PRIMARY)
            self.progress.set(completed / total)

    def set_copy(self, *, check: str, hint: str, continue_text: str, leave: str, emergency: str) -> None:
        self.check_button.configure(text=check)
        self.hint_button.configure(text=hint)
        self.continue_button.configure(text=continue_text)
        self.leave_button.configure(text=leave)
        self.emergency_button.configure(text=emergency)

    def swap_exercise(self, exercise) -> None:
        """Replace the card body. The legacy quiz keeps IndependentTyping."""
        self.exercise.frame.destroy()
        self.exercise = exercise
        self.exercise.frame.pack(fill=tk.X, padx=18, pady=(22, 8), before=self.feedback)

    def show_answering(self, *, show_hint: bool = True, clear_support: bool = True) -> None:
        self.exercise.frame.pack(fill=tk.X, padx=18, pady=(22, 8), before=self.feedback)
        self.exercise.set_enabled(True)
        self.exercise.clear_answer()
        self.hint_button.configure(state="normal")
        if show_hint:
            self.hint_button.pack(pady=(0, 8))
        else:
            self.hint_button.pack_forget()
        self.continue_button.pack_forget()
        self.sentence_button.pack_forget()
        self.hear_button.pack_forget()
        self.check_button.configure(state="normal")
        self.check_button.pack(fill=tk.X)
        self.feedback.configure(text="", text_color=ui_foundation.COLOR_TEXT)
        if clear_support:
            self.exercise.show_support("")
        self.exercise.focus_answer()

    def show_feedback(self, text: str, tone: str, *, offer_sentence: bool = False, offer_hear: bool = False) -> None:
        colors = {
            "ok": ui_foundation.COLOR_PRIMARY,
            "near": "#8A5A12",
            "bad": ui_foundation.COLOR_ERROR_TEXT,
            "empty": "#8A5A12",
        }
        self.feedback.configure(text=text, text_color=colors.get(tone, ui_foundation.COLOR_TEXT))
        if tone == "empty":
            self.exercise.focus_answer()
            return
        self.exercise.set_enabled(False)
        self.hint_button.configure(state="disabled")
        self.hint_button.pack_forget()
        self.check_button.pack_forget()
        self.continue_button.configure(command=self._on_continue, state="normal")
        self.continue_button.pack(fill=tk.X)
        if offer_sentence:
            self.sentence_button.pack(pady=(8, 0))
        else:
            self.sentence_button.pack_forget()
        if offer_hear:
            self.hear_button.pack(pady=(8, 0))
        else:
            self.hear_button.pack_forget()
        try:
            self.continue_button.focus_set()
        except tk.TclError:
            pass

    def show_complete(self, title: str, detail: str, button_text: str) -> None:
        self.exercise.frame.pack_forget()
        self.hint_button.pack_forget()
        self.check_button.pack_forget()
        self.sentence_button.pack_forget()
        self.hear_button.pack_forget()
        self.feedback.configure(
            text=f"{title}\n\n{detail}",
            text_color=ui_foundation.COLOR_TEXT,
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
        )
        self.continue_button.configure(text=button_text, state="normal", command=self._on_done)
        self.continue_button.pack(fill=tk.X, pady=(12, 0))
        try:
            self.continue_button.focus_set()
        except tk.TclError:
            pass


def _label(parent, text, size, weight=None):
    return ctk.CTkLabel(
        parent,
        text=text,
        font=ctk.CTkFont(family="Segoe UI", size=size, weight=weight) if weight else ctk.CTkFont(family="Segoe UI", size=size),
        text_color=ui_foundation.COLOR_TEXT,
        fg_color=ui_foundation.COLOR_CARD,
        wraplength=460,
        justify="center",
    )


class IntroductionExercise:
    """Word, meaning, and the stored example. Hearing is optional."""

    kind = "introduction"

    def __init__(self, parent, card, on_hear):
        self.frame = ctk.CTkFrame(parent, fg_color=ui_foundation.COLOR_CARD, corner_radius=0)
        _label(self.frame, card.kicker, 15).pack(pady=(8, 6))
        _label(self.frame, card.show_word, 32, "bold").pack(pady=(0, 8))
        _label(self.frame, card.show_meaning, 20).pack(pady=(0, 8))
        example = card.show_example or "No example is stored for this word."
        _label(self.frame, example, 15).pack(pady=(0, 8))
        row = ctk.CTkFrame(self.frame, fg_color=ui_foundation.COLOR_CARD, corner_radius=0)
        row.pack(pady=(4, 4))
        self.normal_button = ctk.CTkButton(
            row, text="Listen", width=120, height=34, corner_radius=10,
            fg_color=ui_foundation.COLOR_SOFT_GREEN, hover_color="#D3E6DA",
            text_color=ui_foundation.COLOR_PRIMARY,
            command=lambda: on_hear(0),
        )
        self.slow_button = ctk.CTkButton(
            row, text="Listen slowly", width=140, height=34, corner_radius=10,
            fg_color=ui_foundation.COLOR_SOFT_GREEN, hover_color="#D3E6DA",
            text_color=ui_foundation.COLOR_PRIMARY,
            command=lambda: on_hear(-4),
        )
        self.normal_button.pack(side=tk.LEFT, padx=6)
        self.slow_button.pack(side=tk.LEFT, padx=6)
        bind_activation(self.normal_button)
        bind_activation(self.slow_button)
        self.voice_note = _label(self.frame, card.guidance, 14)
        self.voice_note.pack(pady=(6, 0))

    def answer_text(self) -> str:
        return ""

    def choice_index(self):
        return None

    def clear_answer(self) -> None:
        return None

    def set_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self.normal_button.configure(state=state)
        self.slow_button.configure(state=state)

    def show_support(self, text: str) -> None:
        if text:
            self.voice_note.configure(text=text)

    def focus_answer(self) -> None:
        return None


class MultipleChoiceExercise:
    kind = "multiple_choice"

    def __init__(self, parent, card):
        self.frame = ctk.CTkFrame(parent, fg_color=ui_foundation.COLOR_CARD, corner_radius=0)
        self._selected = None
        self._labels = list(card.choices)
        _label(self.frame, card.kicker, 15).pack(pady=(8, 6))
        _label(self.frame, card.prompt, 26, "bold").pack(pady=(0, 12))
        self.buttons = []
        for index, label in enumerate(self._labels):
            button = ctk.CTkButton(
                self.frame,
                text=f"{index + 1}.  {label}",
                height=42,
                corner_radius=12,
                fg_color="#FFFFFF",
                hover_color=ui_foundation.COLOR_SOFT_GREEN,
                text_color=ui_foundation.COLOR_TEXT,
                border_width=1,
                border_color=ui_foundation.COLOR_BORDER,
                anchor="w",
                command=lambda i=index: self._select(i),
            )
            button.pack(fill=tk.X, padx=8, pady=4)
            bind_activation(button)
            self.buttons.append(button)
        self.support = _label(self.frame, card.guidance, 14)
        self.support.pack(pady=(8, 0))

    def _select(self, index: int) -> None:
        self._selected = index
        for position, button in enumerate(self.buttons):
            if position == index:
                button.configure(
                    fg_color=ui_foundation.COLOR_PRIMARY,
                    text_color=ui_foundation.COLOR_ON_PRIMARY,
                )
            else:
                button.configure(fg_color="#FFFFFF", text_color=ui_foundation.COLOR_TEXT)

    def answer_text(self) -> str:
        if self._selected is None:
            return ""
        return self._labels[self._selected]

    def choice_index(self):
        return self._selected

    def clear_answer(self) -> None:
        self._selected = None
        for button in self.buttons:
            button.configure(fg_color="#FFFFFF", text_color=ui_foundation.COLOR_TEXT)

    def set_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for button in self.buttons:
            button.configure(state=state)

    def show_support(self, text: str) -> None:
        self.support.configure(text=text)

    def focus_answer(self) -> None:
        if self.buttons:
            try:
                self.buttons[0].focus_set()
            except tk.TclError:
                pass


class TypingExercise:
    """Shared typed body for missing letters, guided typing, and recall."""

    def __init__(self, parent, card, kind: str):
        self.kind = kind
        self.frame = ctk.CTkFrame(parent, fg_color=ui_foundation.COLOR_CARD, corner_radius=0)
        self.kicker = _label(self.frame, card.kicker, 15)
        self.kicker.pack(pady=(8, 6))
        self.question = _label(self.frame, card.prompt, 26, "bold")
        self.question.pack(pady=(0, 8))
        self.mask = _label(self.frame, card.mask, 22)
        if card.mask:
            self.mask.pack(pady=(0, 8))
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
        self.support = _label(self.frame, card.guidance, 14)
        self.support.pack(pady=(0, 4))

    def answer_text(self) -> str:
        return self.entry.get().strip()

    def choice_index(self):
        return None

    def clear_answer(self) -> None:
        self.entry.delete(0, "end")

    def set_enabled(self, enabled: bool) -> None:
        self.entry.configure(state="normal" if enabled else "disabled")

    def show_support(self, text: str) -> None:
        self.support.configure(text=text)

    def focus_answer(self) -> None:
        try:
            self.entry.focus_set()
        except tk.TclError:
            pass
