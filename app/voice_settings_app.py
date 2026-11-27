"""Voice settings. Discovery and preview stay off the Tk thread."""

from __future__ import annotations

import tkinter as tk
from typing import Optional

import customtkinter as ctk

import config
import languages
import ui_common
import ui_foundation
import voice_prefs
from ctk_keyboard import bind_activation
from listening_speech import preference_matches, resolve_saved_voice
from listening_windows_tts import (
    NORMAL_RATE,
    PREVIEW_TEXT,
    SLOW_RATE,
    WindowsVoiceInfo,
    voices_for_language,
)
from speech_player import invalidate_playback, play_async, playback_busy, refresh_voices

ctk.deactivate_automatic_dpi_awareness()
ctk.set_appearance_mode("light")


# Windows Settings language names for the cultures this app can speak.
# The second name is an extra pack of the same language, never a different language.
_SPEECH_PACKS = {
    "nl": ("Dutch (Netherlands)", ""),
    "en": ("English (United States)", "English (United Kingdom)"),
    "fr": ("French (France)", "French (Canada)"),
    "de": ("German (Germany)", ""),
    "es": ("Spanish (Spain)", "Spanish (Mexico)"),
    "it": ("Italian (Italy)", ""),
    "pt": ("Portuguese (Portugal)", "Portuguese (Brazil)"),
}


def install_guidance(language_code: str) -> str:
    """Tell the learner how to install speech for the language they selected."""
    code = str(language_code or "").strip().lower()
    primary, extra = _SPEECH_PACKS.get(code, ("", ""))
    name = config.language_name(code) if code else code
    pack = primary or name
    extra_vi = f" {extra} cũng được." if extra else ""
    extra_en = f" {extra} works as well." if extra else ""
    return config.ui(
        f"Máy này chưa có giọng System.Speech cho {name}.\n\n"
        "Cách cài, không đổi ngôn ngữ hiển thị của Windows:\n"
        "1. Mở Settings - Time & language - Language & region.\n"
        f"2. Add a language. Chọn {pack}.{extra_vi}\n"
        "3. Nếu có ô Text-to-speech, hãy chọn nó. Không đặt ngôn ngữ đó làm ngôn ngữ hiển thị.\n"
        "4. Mở dấu ... của ngôn ngữ - Language options - Speech - Download.\n"
        "5. Quay lại đây và bấm Làm mới giọng.\n\n"
        "Gói ngôn ngữ hiển thị không phải lúc nào cũng kèm giọng đọc. "
        "Giọng Natural của Windows 11 có thể không xuất hiện trong System.Speech. "
        "LanguageGuard chỉ dùng giọng mà System.Speech chọn được, và không dùng giọng của ngôn ngữ khác.",
        f"This PC has no System.Speech voice for {name}.\n\n"
        "Install one without changing the Windows display language:\n"
        "1. Open Settings - Time & language - Language & region.\n"
        f"2. Choose Add a language. Add {pack}.{extra_en}\n"
        "3. Include Text-to-speech if Windows offers that checkbox. Do not make it the display language.\n"
        "4. Open the language ... menu - Language options - Speech - Download.\n"
        "5. Come back here and choose Refresh voices.\n\n"
        "A display-language pack does not always include a speaking voice. "
        "Windows 11 natural voices may not appear in System.Speech. "
        "LanguageGuard only uses a voice System.Speech can select, and it never borrows another language.",
    )


class VoiceSettingsApp:
    def __init__(self, window: tk.Misc):
        self.window = window
        self._closed = False
        self._generation = 0
        self._preview_token = 0
        self._catalog: tuple[WindowsVoiceInfo, ...] | None = None
        self._voices: tuple[WindowsVoiceInfo, ...] = ()
        self._loading = False
        codes = [item.code for item in languages.iter_languages()]
        self._codes = codes
        active = config.active_code()
        self._language = active if active in codes else codes[0]
        window.title(config.ui("Giọng đọc", "Voices"))
        try:
            window.geometry("560x640")
            window.minsize(480, 520)
            window.configure(bg=ui_foundation.COLOR_BG)
        except tk.TclError:
            pass
        window.protocol("WM_DELETE_WINDOW", self.close)

        shell = ctk.CTkFrame(window, fg_color=ui_foundation.COLOR_BG, corner_radius=0)
        shell.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)
        ctk.CTkLabel(
            shell,
            text=config.ui("Giọng trên máy này", "Voices on this PC"),
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=ui_foundation.COLOR_TEXT,
            fg_color=ui_foundation.COLOR_BG,
        ).pack(anchor="w")
        ctk.CTkLabel(
            shell,
            text=config.ui(
                "Lựa chọn được lưu trên máy này, theo từng ngôn ngữ. Nó không được đồng bộ.",
                "The choice stays on this PC, per language. It is not synced.",
            ),
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color="#5C7268",
            fg_color=ui_foundation.COLOR_BG,
            wraplength=500,
            justify="left",
        ).pack(anchor="w", pady=(4, 12))

        ctk.CTkLabel(
            shell,
            text=config.ui("Ngôn ngữ học", "Study language"),
            text_color=ui_foundation.COLOR_TEXT,
            fg_color=ui_foundation.COLOR_BG,
        ).pack(anchor="w")
        self.language_menu = ctk.CTkOptionMenu(
            shell,
            values=[config.language_name(code) for code in codes],
            command=self._on_language,
            fg_color=ui_foundation.COLOR_CARD,
            button_color=ui_foundation.COLOR_PRIMARY,
            button_hover_color=ui_foundation.COLOR_PRIMARY_ACTIVE,
            text_color=ui_foundation.COLOR_TEXT,
        )
        self.language_menu.set(config.language_name(self._language))
        self.language_menu.pack(fill=tk.X, pady=(4, 10))

        ctk.CTkLabel(
            shell,
            text=config.ui("Giọng", "Voice"),
            text_color=ui_foundation.COLOR_TEXT,
            fg_color=ui_foundation.COLOR_BG,
        ).pack(anchor="w")
        self.voice_menu = ctk.CTkOptionMenu(
            shell,
            values=[config.ui("Đang tìm giọng…", "Looking for voices…")],
            command=self._on_voice,
            fg_color=ui_foundation.COLOR_CARD,
            button_color=ui_foundation.COLOR_PRIMARY,
            button_hover_color=ui_foundation.COLOR_PRIMARY_ACTIVE,
            text_color=ui_foundation.COLOR_TEXT,
        )
        self.voice_menu.pack(fill=tk.X, pady=(4, 8))
        self.detail = ctk.CTkLabel(
            shell,
            text="",
            text_color="#5C7268",
            fg_color=ui_foundation.COLOR_BG,
            wraplength=500,
            justify="left",
        )
        self.detail.pack(anchor="w", pady=(0, 8))
        self.guidance = ctk.CTkTextbox(
            shell,
            height=180,
            fg_color=ui_foundation.COLOR_CARD,
            text_color=ui_foundation.COLOR_TEXT,
            wrap="word",
        )
        self.guidance.pack(fill=tk.X, pady=(0, 8))
        self.guidance.insert("1.0", "")
        self.guidance.configure(state="disabled")

        row = ctk.CTkFrame(shell, fg_color=ui_foundation.COLOR_BG, corner_radius=0)
        row.pack(fill=tk.X, pady=(4, 0))
        self.normal_button = self._button(row, config.ui("Nghe thường", "Preview normal"), lambda: self._preview(NORMAL_RATE))
        self.slow_button = self._button(row, config.ui("Nghe chậm", "Preview slow"), lambda: self._preview(SLOW_RATE))
        self.refresh_button = self._button(row, config.ui("Làm mới giọng", "Refresh voices"), self._refresh)
        self.normal_button.pack(side=tk.LEFT, padx=(0, 8))
        self.slow_button.pack(side=tk.LEFT, padx=(0, 8))
        self.refresh_button.pack(side=tk.LEFT)
        self.status = ctk.CTkLabel(
            shell,
            text="",
            text_color=ui_foundation.COLOR_TEXT,
            fg_color=ui_foundation.COLOR_BG,
            wraplength=500,
            justify="left",
        )
        self.status.pack(anchor="w", pady=(12, 0))
        self._refresh()

    def _button(self, parent, text, command):
        button = ctk.CTkButton(
            parent,
            text=text,
            command=command,
            height=36,
            fg_color=ui_foundation.COLOR_PRIMARY,
            hover_color=ui_foundation.COLOR_PRIMARY_ACTIVE,
            text_color=ui_foundation.COLOR_ON_PRIMARY,
        )
        bind_activation(button)
        return button

    def close(self):
        self._closed = True
        self._generation += 1
        invalidate_playback()
        try:
            self.window.destroy()
        except tk.TclError:
            pass

    def _on_language(self, label: str):
        for code in self._codes:
            if config.language_name(code) == label:
                self._language = code
                break
        self._preview_token += 1
        self.status.configure(text="")
        if self._catalog is None:
            self._refresh()
            return
        self._render_catalog()
        if playback_busy():
            self._set_preview_enabled(False)
            self._arm_playback_watch()

    def _on_voice(self, label: str):
        voice = self._voice_by_label(label)
        if voice is None:
            return
        voice_prefs.set_selected_voice_name(self._language, voice.token())
        self._preview_token += 1
        self._show_voice(voice)
        if playback_busy():
            self._set_preview_enabled(False)
            self._arm_playback_watch()

    def _voice_by_label(self, label: str) -> Optional[WindowsVoiceInfo]:
        for voice in self._voices:
            if self._voice_label(voice) == label:
                return voice
        return None

    def _voice_label(self, voice: WindowsVoiceInfo) -> str:
        gender = f" · {voice.gender}" if voice.gender else ""
        kind = "Windows voice" if voice.provider == "winrt" else "System.Speech"
        return f"{voice.name} · {voice.culture}{gender} · {kind}"

    def _refresh(self):
        if self._loading:
            return
        self._loading = True
        self._generation += 1
        self._preview_token += 1
        generation = self._generation
        self.status.configure(text=config.ui("Đang tìm giọng trên máy…", "Looking up voices on this PC…"))
        self._set_enabled(False)

        def work():
            return refresh_voices()

        def deliver(voices):
            self._loading = False
            if self._closed or generation != self._generation:
                return
            self._catalog = tuple(voices)
            self._render_catalog()

        def failed(error):
            self._loading = False
            if self._closed or generation != self._generation:
                return
            # Leave the catalog unknown so the next refresh discovers again.
            # Do not call voices_for() here: that would run PowerShell on the Tk thread.
            self._catalog = None
            self._voices = ()
            self._show_missing()
            self.status.configure(text=str(error))

        ui_common.run_async(self.window, work, deliver, failed)

    def _render_catalog(self):
        self._voices = tuple(voices_for_language(self._language, self._catalog or ()))
        self._set_enabled(True)
        if not self._voices:
            self._show_missing()
            self.status.configure(text="")
            return
        labels = [self._voice_label(voice) for voice in self._voices]
        self.voice_menu.configure(values=labels)
        saved = voice_prefs.selected_voice_name(self._language)
        chosen = resolve_saved_voice(self._language, self._voices, saved)
        if chosen is None:
            self._show_missing()
            self.status.configure(text="")
            return
        if saved and not preference_matches(chosen, saved):
            voice_prefs.set_selected_voice_name(self._language, chosen.token())
        self.voice_menu.set(self._voice_label(chosen))
        self._show_voice(chosen)
        self._set_guidance("")
        self._set_preview_enabled(not playback_busy())
        if playback_busy():
            self._arm_playback_watch()
        self.status.configure(text="")

    def _show_missing(self):
        missing = config.ui("Chưa có giọng", "No voice installed")
        self.voice_menu.configure(values=[missing])
        self.voice_menu.set(missing)
        self.voice_menu.configure(state="disabled")
        self.detail.configure(
            text=config.ui(
                "Chưa có giọng Windows cho ngôn ngữ này.",
                "No Windows voice is available for this language.",
            )
        )
        self._set_guidance(install_guidance(self._language))
        self._set_preview_enabled(False)
        self.language_menu.configure(state="normal")
        self.refresh_button.configure(state="normal")

    def _show_voice(self, voice: WindowsVoiceInfo):
        gender = voice.gender or config.ui("không ghi", "not reported")
        kind = "Windows voice" if voice.provider == "winrt" else "System.Speech"
        self.detail.configure(
            text=config.ui(
                f"Ngôn ngữ giọng: {voice.culture}. Giới tính: {gender}. Nguồn: {kind}.",
                f"Voice locale: {voice.culture}. Gender: {gender}. Source: {kind}.",
            )
        )

    def _set_guidance(self, text: str):
        self.guidance.configure(state="normal")
        self.guidance.delete("1.0", "end")
        if text:
            self.guidance.insert("1.0", text)
        self.guidance.configure(state="disabled")

    def _set_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        for button in (self.refresh_button, self.language_menu, self.voice_menu):
            button.configure(state=state)
        if not enabled:
            self._set_preview_enabled(False)

    def _set_preview_enabled(self, enabled: bool):
        state = "normal" if enabled and self._voices and not self._loading else "disabled"
        self.normal_button.configure(state=state)
        self.slow_button.configure(state=state)

    def _preview(self, rate: int):
        if self._closed or self._loading or not self._voices:
            return
        voice = self._voice_by_label(self.voice_menu.get())
        if voice is None:
            return
        sample = PREVIEW_TEXT.get(self._language)
        if not sample:
            return
        language = self._language
        self._preview_token += 1
        token = self._preview_token
        voice_name = voice.token()

        def scope() -> bool:
            return (
                not self._closed
                and token == self._preview_token
                and language == self._language
                and not self._loading
            )

        started = play_async(
            self.window,
            text=sample,
            language_code=language,
            rate=rate,
            voice_name=voice_name,
            scope=scope,
            on_done=lambda: self._preview_done(token, language, ""),
            on_error=lambda error, code=language: self._preview_done(token, code, str(error)),
            on_settled=self._preview_settled,
        )
        if not started:
            self.status.configure(text=config.ui("Đang phát một đoạn khác.", "Another clip is still playing."))
            self._set_preview_enabled(False)
            self._arm_playback_watch()
            return
        self.status.configure(text=config.ui("Đang phát…", "Playing…"))
        self._set_preview_enabled(False)

    def _preview_done(self, token: int, language: str, error: str):
        if self._closed or token != self._preview_token or language != self._language or self._loading:
            return
        self.status.configure(text=error)

    def _arm_playback_watch(self):
        """Re-enable preview after another window releases the shared slot."""
        self._watch_token = getattr(self, "_watch_token", 0) + 1
        token = self._watch_token

        def tick():
            if self._closed or token != getattr(self, "_watch_token", None):
                return
            if self._loading:
                return
            if playback_busy():
                try:
                    self.window.after(200, tick)
                except tk.TclError:
                    pass
                return
            busy = config.ui("Đang phát một đoạn khác.", "Another clip is still playing.")
            try:
                if self.status.cget("text") == busy:
                    self.status.configure(text="")
            except tk.TclError:
                return
            self._set_preview_enabled(True)

        try:
            self.window.after(200, tick)
        except tk.TclError:
            pass

    def _preview_settled(self):
        if self._closed or self._loading:
            return
        if playback_busy():
            self._set_preview_enabled(False)
            return
        playing = config.ui("Đang phát…", "Playing…")
        if self.status.cget("text") == playing:
            self.status.configure(text="")
        self._set_preview_enabled(True)


def open_voice_settings(parent: tk.Misc) -> tk.Toplevel:
    window = tk.Toplevel(parent)
    window.transient(parent)
    VoiceSettingsApp(window)
    return window
