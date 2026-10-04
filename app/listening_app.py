"""Listening activity Tk adapter (Phase 17A hardening).

Launched from StudyMaster like Reading. Owns ScreenGuard when locked.
Does not create an independent Tk root.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

import config
import ui_common
from listening import (
    ListeningAudioError,
    ListeningAudioProvider,
    ListeningError,
    ListeningSession,
    sample_listening_items,
)


class ListeningApp:
    """Minimal Play → answer → Check → Continue flow."""

    def __init__(
        self,
        window: tk.Misc,
        *,
        language_code: str = None,
        audio_provider: Optional[ListeningAudioProvider] = None,
        on_completed: Optional[Callable[[], None]] = None,
        on_failed: Optional[Callable[[], None]] = None,
        on_skip: Optional[Callable[[], None]] = None,
        on_emergency: Optional[Callable[[], None]] = None,
        required: bool = False,
        locked: bool = False,
    ):
        self.window = window
        self.language_code = language_code or config.active_code()
        self.on_completed = on_completed
        self.on_failed = on_failed
        self.on_skip = on_skip
        self.on_emergency = on_emergency
        # Listening is optional in StudySession; never treat unresolved as required.
        self.required = bool(required)
        self.locked = locked
        self._play_busy = False

        self.session = ListeningSession.create(
            self.language_code,
            audio_provider=audio_provider,
            items=sample_listening_items(self.language_code),
        )

        ui_common.apply_theme(window)
        try:
            window.configure(bg=ui_common.COLOR_BG)
        except tk.TclError:
            pass
        window.title(
            f"{config.APP_NAME} — {config.ui('Nghe', 'Listening')}"
        )
        if not locked:
            window.geometry("560x420")

        self.guard = ui_common.ScreenGuard(
            window,
            enabled=config.LOCK_SCREEN if locked else False,
            on_close_attempt=self._on_close_attempt,
        )

        self.root = ttk.Frame(window, padding=ui_common.PAD_PAGE)
        self.root.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            self.root, text=config.ui("Nghe", "Listening"), style="Page.TLabel"
        ).pack(anchor="w")
        ttk.Label(
            self.root,
            text=config.language_name(self.language_code),
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(0, 12))

        if self.session.unavailable:
            self._build_unavailable()
            return
        self._build_exercise()

    def _build_unavailable(self):
        ttk.Label(
            self.root,
            text=config.ui(
                "Phần nghe chưa dùng được — chưa có nguồn phát âm thanh.",
                "Listening is unavailable — no audio provider is configured yet.",
            ),
            style="Muted.TLabel",
            wraplength=480,
        ).pack(anchor="w", pady=(8, 16))
        ttk.Button(
            self.root,
            text=config.ui("Tiếp tục", "Continue"),
            style="Primary.TButton",
            command=self._resolve_unavailable,
        ).pack(anchor="e")
        ttk.Button(
            self.root,
            text=config.ui("Thoát khẩn cấp", "Emergency exit"),
            style="Small.TButton",
            command=self._emergency_exit,
        ).pack(anchor="e", pady=(8, 0))

    def _build_exercise(self):
        ttk.Label(
            self.root,
            text=config.ui(
                "Nghe đoạn nói, rồi trả lời câu hỏi. Nội dung chỉ hiện sau khi trả lời.",
                "Listen, then answer the question. The transcript appears after you answer.",
            ),
            style="Muted.TLabel",
            wraplength=480,
        ).pack(anchor="w")

        self.play_button = ttk.Button(
            self.root,
            text=config.ui("Phát", "Play"),
            style="Secondary.TButton",
            command=self._play,
        )
        self.play_button.pack(anchor="w", pady=(12, 8))

        ttk.Label(
            self.root,
            text=self.session.item.question,
            wraplength=480,
        ).pack(anchor="w", pady=(4, 8))

        self.answer_var = tk.StringVar()
        self.answer_entry = ttk.Entry(
            self.root, textvariable=self.answer_var, width=48, font=ui_common.FONT_BODY
        )
        self.answer_entry.pack(anchor="w", fill=tk.X)
        self.answer_entry.focus_set()

        self.status = ttk.Label(self.root, text="", style="Muted.TLabel", wraplength=480)
        self.status.pack(anchor="w", pady=(8, 0))

        self.transcript = ttk.Label(
            self.root, text="", style="Muted.TLabel", wraplength=480
        )
        self.transcript.pack(anchor="w", pady=(8, 0))

        actions = ttk.Frame(self.root)
        actions.pack(fill=tk.X, pady=(16, 0))
        self.check_button = ttk.Button(
            actions,
            text=config.ui("Kiểm tra", "Check"),
            style="Primary.TButton",
            command=self._check,
        )
        self.check_button.pack(side=tk.LEFT)
        self.continue_button = ttk.Button(
            actions,
            text=config.ui("Xong", "Finish"),
            style="Secondary.TButton",
            command=self._finish,
            state="disabled",
        )
        self.continue_button.pack(side=tk.LEFT, padx=(8, 0))
        if callable(self.on_skip):
            ttk.Button(
                actions,
                text=config.ui("Bỏ qua", "Skip"),
                style="Small.TButton",
                command=self._skip,
            ).pack(side=tk.RIGHT)
        ttk.Button(
            actions,
            text=config.ui("Thoát khẩn cấp", "Emergency exit"),
            style="Small.TButton",
            command=self._emergency_exit,
        ).pack(side=tk.RIGHT, padx=(0, 8) if callable(self.on_skip) else (0, 0))

        self.window.bind("<Return>", lambda _e: self._check())

    def _play(self):
        """Play via run_async so future TTS/network work cannot freeze Tk."""
        if self._play_busy or self.session.unavailable:
            return
        if self.session._playing:
            return
        self._play_busy = True
        self.play_button.state(["disabled"])
        self.status.config(
            text=config.ui("Đang phát…", "Playing…"),
            foreground=ui_common.COLOR_MUTED,
        )

        def work():
            self.session.play()
            return True

        def on_ok(_result):
            self._play_busy = False
            try:
                if not self.session.unavailable:
                    self.play_button.state(["!disabled"])
                self.status.config(
                    text=config.ui("Đã phát.", "Played."),
                    foreground=ui_common.COLOR_MUTED,
                )
            except tk.TclError:
                pass

        def on_error(error: Exception):
            self._play_busy = False
            try:
                self.status.config(text=str(error), foreground=ui_common.COLOR_WARN)
            except tk.TclError:
                pass
            self._resolve_unavailable()

        ui_common.run_async(self.window, work, on_ok, on_error)

    def _check(self):
        if self.session.answered or self.session.unavailable:
            return
        try:
            result = self.session.submit(self.answer_var.get())
        except ListeningError as error:
            self.status.config(text=str(error), foreground=ui_common.COLOR_WARN)
            return
        if result.correct:
            self.status.config(
                text=config.ui("Đúng.", "Correct."),
                foreground=ui_common.COLOR_OK,
            )
        else:
            self.status.config(
                text=config.ui(
                    f"Chưa đúng. Gợi ý đáp án: {result.expected}",
                    f"Not yet. Expected something like: {result.expected}",
                ),
                foreground=ui_common.COLOR_WARN,
            )
        reveal = self.session.item.text
        if self.session.item.meaning:
            reveal = f"{reveal}\n({self.session.item.meaning})"
        self.transcript.config(
            text=config.ui(f"Nội dung: {reveal}", f"Transcript: {reveal}")
        )
        self.continue_button.state(["!disabled"])
        self.check_button.state(["disabled"])

    def _finish(self):
        try:
            self.session.finish()
        except ListeningError as error:
            self.status.config(text=str(error), foreground=ui_common.COLOR_WARN)
            return
        if callable(self.on_completed):
            self.on_completed()
        self.window.destroy()

    def _skip(self):
        if callable(self.on_skip):
            self.on_skip()
        self.window.destroy()

    def _resolve_unavailable(self):
        self.session.unavailable = True
        if callable(self.on_failed):
            self.on_failed()
        try:
            if self.window.winfo_exists():
                self.window.destroy()
        except tk.TclError:
            pass

    def _on_close_attempt(self):
        """Optional Listening: unresolved close → skip/unavailable. Emergency is separate."""
        if self.session.completed:
            self.window.destroy()
            return
        if self.session.unavailable:
            self._resolve_unavailable()
            return
        # Optional activity: never trap the learner on window close.
        if not self.required:
            if callable(self.on_skip):
                self._skip()
                return
            if callable(self.on_failed):
                self.on_failed()
            self.window.destroy()
            return
        # Required path (should not apply to Listening) — show not-finished.
        self.guard.show_info(
            config.ui("Chưa xong", "Not finished"),
            config.ui(
                "Hãy hoàn thành phần nghe trước khi đóng cửa sổ.\n\n"
                "Nếu app bị lỗi, hãy dùng nút “Thoát khẩn cấp”.",
                "Finish Listening before closing.\n\n"
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
