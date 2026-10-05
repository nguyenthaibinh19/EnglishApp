"""Listening activity Tk adapter (Phase 17C content + 17B audio).

Launched from StudyMaster. Owns ScreenGuard when locked.
Content loads asynchronously; audio uses the existing provider seam.
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
    ListeningItem,
    ListeningSession,
)
from listening_source import NoListeningAvailable, build_listening_item
from word_lookup_overlay import (
    open_word_action_overlay,
    prepare_clickable_text,
    word_at_text_index,
)


class ListeningApp:
    """Play → answer → Check → Continue with async AI/bundled content."""

    def __init__(
        self,
        window: tk.Misc,
        *,
        language_code: str = None,
        audio_provider: Optional[ListeningAudioProvider] = None,
        item: Optional[ListeningItem] = None,
        content_loader: Optional[Callable[[], ListeningItem]] = None,
        vocab_store=None,
        on_completed: Optional[Callable[[], None]] = None,
        on_failed: Optional[Callable[[], None]] = None,
        on_skip: Optional[Callable[[], None]] = None,
        on_emergency: Optional[Callable[[], None]] = None,
        required: bool = False,
        locked: bool = False,
    ):
        self.window = window
        self.language_code = language_code or config.active_code()
        self.audio_provider = audio_provider
        self.on_completed = on_completed
        self.on_failed = on_failed
        self.on_skip = on_skip
        self.on_emergency = on_emergency
        self.required = bool(required)
        self.locked = locked
        self._play_busy = False
        self._load_generation = 0
        self._closed = False
        self._word_popup = None
        self.vocab_store = vocab_store
        self.session: Optional[ListeningSession] = None
        self._prebuilt_item = item
        self._content_loader = content_loader

        ui_common.apply_theme(window)
        try:
            window.configure(bg=ui_common.COLOR_BG)
        except tk.TclError:
            pass
        window.title(f"{config.APP_NAME} — {config.ui('Nghe', 'Listening')}")
        if not locked:
            window.geometry("560x460")

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

        self.body = ttk.Frame(self.root)
        self.body.pack(fill=tk.BOTH, expand=True)

        if self._prebuilt_item is not None:
            self._bind_item(self._prebuilt_item)
            return

        self._show_loading()
        self._start_content_load()

    def _alive(self) -> bool:
        if self._closed:
            return False
        try:
            return bool(self.window.winfo_exists())
        except tk.TclError:
            return False

    def _clear_body(self):
        for child in self.body.winfo_children():
            try:
                child.destroy()
            except tk.TclError:
                pass

    def _show_loading(self):
        self._clear_body()
        ttk.Label(
            self.body,
            text=config.ui(
                "Đang chuẩn bị bài nghe…",
                "Preparing listening exercise…",
            ),
            style="Muted.TLabel",
            wraplength=480,
        ).pack(anchor="w", pady=(8, 16))
        if callable(self.on_skip):
            ttk.Button(
                self.body,
                text=config.ui("Bỏ qua", "Skip"),
                style="Small.TButton",
                command=self._skip,
            ).pack(anchor="e")
        ttk.Button(
            self.body,
            text=config.ui("Thoát khẩn cấp", "Emergency exit"),
            style="Small.TButton",
            command=self._emergency_exit,
        ).pack(anchor="e", pady=(8, 0))

    def _default_content_loader(self) -> ListeningItem:
        if self._content_loader is not None:
            return self._content_loader()
        from progress import Progress
        from vocab_store import VocabStore

        store = self.vocab_store or VocabStore(config.vocab_path(self.language_code))
        progress = Progress(config.progress_path(self.language_code))
        summaries = None
        try:
            from mistake_book import load_mistake_summaries

            summaries = load_mistake_summaries(language_code=self.language_code)
        except Exception:
            summaries = None
        return build_listening_item(
            store,
            progress,
            language_code=self.language_code,
            native_code=config.native_code(),
            native_label=config.native_label(),
            level=config.READING_LEVEL,
            mistake_summaries=summaries,
        )

    def _start_content_load(self):
        self._load_generation += 1
        generation = self._load_generation
        language = self.language_code

        def work():
            return self._default_content_loader()

        def on_ok(item: ListeningItem):
            if generation != self._load_generation or not self._alive():
                return
            if language != self.language_code:
                return
            self._bind_item(item)

        def on_error(error: Exception):
            if generation != self._load_generation or not self._alive():
                return
            self.session = ListeningSession.create(
                self.language_code,
                audio_provider=self.audio_provider,
                item=ListeningItem(text="", question="", answer=""),
            )
            self.session.unavailable = True
            self.session.unavailable_reason = "no_content"
            self._build_unavailable(extra=str(error))

        ui_common.run_async(self.window, work, on_ok, on_error)

    def _bind_item(self, item: ListeningItem):
        self.session = ListeningSession.create(
            self.language_code,
            item=item,
            audio_provider=self.audio_provider,
        )
        if self.session.unavailable:
            self._build_unavailable()
            return
        self._build_exercise()

    def _build_unavailable(self, extra: str = ""):
        self._clear_body()
        reason = ""
        if self.session is not None:
            reason = self.session.unavailable_reason_message()
            if not reason:
                if self.session.unavailable_reason == "no_voice":
                    reason = config.ui(
                        f"Chưa cài giọng đọc Windows cho {config.language_name(self.language_code)}.",
                        f"No Windows text-to-speech voice is installed for "
                        f"{config.language_name(self.language_code)}.",
                    )
                elif self.session.unavailable_reason == "no_content":
                    reason = config.ui(
                        "Chưa có bài nghe cho ngôn ngữ này.",
                        "No listening exercise is available for this language.",
                    )
                else:
                    reason = config.ui(
                        "Phần nghe chưa dùng được — chưa có nguồn phát âm thanh.",
                        "Listening is unavailable — no audio provider is configured yet.",
                    )
        if extra and not reason:
            reason = extra
        elif extra:
            reason = f"{reason}\n\n{extra}" if reason else extra
        ttk.Label(
            self.body,
            text=reason,
            style="Muted.TLabel",
            wraplength=480,
        ).pack(anchor="w", pady=(8, 16))
        ttk.Button(
            self.body,
            text=config.ui("Tiếp tục", "Continue"),
            style="Primary.TButton",
            command=self._resolve_unavailable,
        ).pack(anchor="e")
        ttk.Button(
            self.body,
            text=config.ui("Thoát khẩn cấp", "Emergency exit"),
            style="Small.TButton",
            command=self._emergency_exit,
        ).pack(anchor="e", pady=(8, 0))

    def _build_exercise(self):
        self._clear_body()
        assert self.session is not None
        ttk.Label(
            self.body,
            text=config.ui(
                "Nghe đoạn nói, rồi trả lời câu hỏi. Nội dung chỉ hiện sau khi trả lời.",
                "Listen, then answer the question. The transcript appears after you answer.",
            ),
            style="Muted.TLabel",
            wraplength=480,
        ).pack(anchor="w")

        self.play_button = ttk.Button(
            self.body,
            text=config.ui("Phát", "Play"),
            style="Secondary.TButton",
            command=self._play,
        )
        self.play_button.pack(anchor="w", pady=(12, 8))

        ttk.Label(
            self.body,
            text=config.ui("Câu hỏi", "Question"),
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(4, 2))
        self.question_text = prepare_clickable_text(
            self.body,
            self.session.item.question,
            font=ui_common.FONT_BODY,
            on_click=self._on_question_word_click,
            height=3,
            width=58,
        )
        self.question_text.pack(anchor="w", fill=tk.X, pady=(0, 8))

        self.answer_var = tk.StringVar()
        self.answer_entry = ttk.Entry(
            self.body, textvariable=self.answer_var, width=48, font=ui_common.FONT_BODY
        )
        self.answer_entry.pack(anchor="w", fill=tk.X)
        self.answer_entry.focus_set()

        self.status = ttk.Label(self.body, text="", style="Muted.TLabel", wraplength=480)
        self.status.pack(anchor="w", pady=(8, 0))

        # Transcript/meaning containers stay empty until Check (no hidden content).
        self.transcript_frame = ttk.Frame(self.body)
        self.transcript_frame.pack(anchor="w", fill=tk.X, pady=(8, 0))
        self.transcript_label = None
        self.transcript_text = None
        self.meaning_label = None

        actions = ttk.Frame(self.body)
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

    def _on_question_word_click(self, event):
        if self.session is None or self.session.unavailable:
            return
        word, _start, _end = word_at_text_index(event.widget, f"@{event.x},{event.y}")
        if not word:
            return
        question = self.session.item.question
        self._word_popup = open_word_action_overlay(
            self.window,
            word=word,
            x_root=event.x_root,
            y_root=event.y_root,
            language_code=self.language_code,
            native_code=config.native_code(),
            sentence_provider=lambda: question,
            on_save=self._save_word,
            previous=self._word_popup,
        )

    def _on_transcript_word_click(self, event):
        if self.session is None or not self.session.answered:
            return
        word, _start, _end = word_at_text_index(event.widget, f"@{event.x},{event.y}")
        if not word:
            return
        transcript = self.session.item.text
        self._word_popup = open_word_action_overlay(
            self.window,
            word=word,
            x_root=event.x_root,
            y_root=event.y_root,
            language_code=self.language_code,
            native_code=config.native_code(),
            sentence_provider=lambda: transcript,
            on_save=self._save_word,
            previous=self._word_popup,
        )

    def _save_word(self, word: str, meaning: str):
        """Return ``saved`` / ``duplicate`` / ``failed`` for truthful overlay UX."""
        store = self.vocab_store
        if store is None:
            from vocab_store import VocabStore

            store = VocabStore(config.vocab_path(self.language_code))
        text = str(word or "").strip()
        gloss = str(meaning or "").strip()
        if not text or not gloss:
            return "failed"
        if store.index_of(text) is not None:
            return "duplicate"
        if store.add(text, gloss):
            return "saved"
        return "failed"

    def _play(self):
        if self.session is None or self._play_busy or self.session.unavailable:
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
            if not self._alive():
                return
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
            if not self._alive():
                return
            try:
                self.status.config(text=str(error), foreground=ui_common.COLOR_WARN)
            except tk.TclError:
                pass
            self._resolve_unavailable()

        ui_common.run_async(self.window, work, on_ok, on_error)

    def _check(self):
        if self.session is None or self.session.answered or self.session.unavailable:
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

        for child in self.transcript_frame.winfo_children():
            child.destroy()
        ttk.Label(
            self.transcript_frame,
            text=config.ui("Nội dung", "Transcript"),
            style="Muted.TLabel",
        ).pack(anchor="w")
        self.transcript_text = prepare_clickable_text(
            self.transcript_frame,
            self.session.item.text,
            font=ui_common.FONT_BODY,
            on_click=self._on_transcript_word_click,
            height=3,
            width=58,
        )
        self.transcript_text.pack(anchor="w", fill=tk.X, pady=(2, 4))
        if self.session.item.meaning:
            self.meaning_label = ttk.Label(
                self.transcript_frame,
                text=config.ui(
                    f"Nghĩa: {self.session.item.meaning}",
                    f"Meaning: {self.session.item.meaning}",
                ),
                style="Muted.TLabel",
                wraplength=480,
            )
            self.meaning_label.pack(anchor="w")

        self.continue_button.state(["!disabled"])
        self.check_button.state(["disabled"])

    def _finish(self):
        if self.session is None:
            return
        try:
            self.session.finish()
        except ListeningError as error:
            self.status.config(text=str(error), foreground=ui_common.COLOR_WARN)
            return
        if callable(self.on_completed):
            self.on_completed()
        self._closed = True
        self.window.destroy()

    def _skip(self):
        self._closed = True
        self._load_generation += 1
        if callable(self.on_skip):
            self.on_skip()
        try:
            if self.window.winfo_exists():
                self.window.destroy()
        except tk.TclError:
            pass

    def _resolve_unavailable(self):
        if self.session is not None:
            self.session.unavailable = True
        self._closed = True
        self._load_generation += 1
        if callable(self.on_failed):
            self.on_failed()
        try:
            if self.window.winfo_exists():
                self.window.destroy()
        except tk.TclError:
            pass

    def _on_close_attempt(self):
        if self.session is not None and self.session.completed:
            self._closed = True
            self.window.destroy()
            return
        if self.session is not None and self.session.unavailable:
            self._resolve_unavailable()
            return
        if not self.required:
            if callable(self.on_skip):
                self._skip()
                return
            if callable(self.on_failed):
                self.on_failed()
            self._closed = True
            self._load_generation += 1
            self.window.destroy()
            return
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
        self._closed = True
        self._load_generation += 1
        if callable(self.on_emergency):
            self.on_emergency()
        else:
            self.window.destroy()
