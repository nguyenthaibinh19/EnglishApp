"""Shared in-window word-action overlay for Reading/Listening (Phase 17C).

Never creates a Toplevel, never toggles fullscreen/state, never pauses ScreenGuard.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

import config
import dictionary
import ui_common


def open_word_action_overlay(
    parent: tk.Misc,
    *,
    word: str,
    x_root: int,
    y_root: int,
    language_code: str,
    native_code: str = None,
    sentence_provider: Optional[Callable[[], str]] = None,
    on_save: Optional[Callable[[str, str], object]] = None,
    on_highlight: Optional[Callable[[], None]] = None,
    previous: Optional[tk.Misc] = None,
) -> tk.Frame:
    """Show an in-window overlay for translate-word / translate-sentence / save.

    ``sentence_provider`` returns the visible sentence/question only — callers
    must not expose hidden transcript content.
    """
    if previous is not None:
        try:
            if previous.winfo_exists():
                previous.destroy()
        except tk.TclError:
            pass

    word = str(word or "").strip()
    source = str(language_code or "").strip().lower()
    native = str(native_code or config.native_code()).strip().lower()

    pop = tk.Frame(
        parent,
        bg=ui_common.COLOR_CARD,
        highlightbackground=ui_common.COLOR_BORDER,
        highlightthickness=1,
        bd=0,
    )
    closed = {"done": False}

    def close(_event=None):
        if closed["done"]:
            return
        closed["done"] = True
        try:
            pop.grab_release()
        except tk.TclError:
            pass
        try:
            if pop.winfo_exists():
                pop.destroy()
        except tk.TclError:
            pass

    pop.bind("<Destroy>", lambda event: close() if event.widget is pop else None)
    pop.bind("<Escape>", close)

    body = ttk.Frame(pop, padding=12)
    body.pack()
    ttk.Label(body, text=word, style="H2.TLabel").pack(anchor="w")
    result_label = ttk.Label(body, text="", wraplength=260, justify="left")
    result_label.pack(anchor="w", pady=(6, 4))

    meaning_var = tk.StringVar()
    ttk.Entry(
        body, textvariable=meaning_var, width=28, font=ui_common.FONT_BODY
    ).pack(anchor="w", pady=(4, 0))

    def translate_word():
        result_label.config(text=config.ui("Đang dịch từ…", "Translating word…"))

        def show(glosses):
            if closed["done"]:
                return
            lines = []
            if isinstance(glosses, list):
                for item in glosses[:8]:
                    if isinstance(item, dict):
                        lines.append(str(item.get("text") or item.get("meaning") or item))
                    else:
                        lines.append(str(item))
            elif glosses:
                lines.append(str(glosses))
            text = "\n".join(line for line in lines if line).strip()
            result_label.config(
                text=text
                or config.ui("Không có nghĩa.", "No gloss found.")
            )
            if text and not meaning_var.get().strip():
                meaning_var.set(lines[0] if lines else "")

        def failed(error):
            if not closed["done"]:
                result_label.config(text=str(error))

        ui_common.run_async(
            pop, lambda: dictionary.lookup(word, source, native), show, failed
        )

    def translate_sentence():
        sentence = ""
        if callable(sentence_provider):
            try:
                sentence = str(sentence_provider() or "").strip()
            except Exception:
                sentence = ""
        if not sentence:
            result_label.config(
                text=config.ui(
                    "Không thấy câu quanh từ này.",
                    "No sentence around this word.",
                )
            )
            return
        result_label.config(text=config.ui("Đang dịch câu…", "Translating sentence…"))

        def show(text):
            if closed["done"]:
                return
            if text:
                result_label.config(text=f"{sentence}\n\n{text}")
            else:
                result_label.config(
                    text=config.ui(
                        f"Không dịch được câu:\n{sentence}",
                        f"Couldn't translate:\n{sentence}",
                    )
                )

        def failed(error):
            if not closed["done"]:
                result_label.config(text=str(error))

        ui_common.run_async(
            pop,
            lambda: dictionary.translate_sentence(sentence, source, native),
            show,
            failed,
        )

    def save_word():
        meaning = meaning_var.get().strip()
        if not meaning:
            result_label.config(
                text=config.ui("Nhập nghĩa trước khi lưu.", "Enter a meaning before saving.")
            )
            return
        if callable(on_save):
            try:
                result = on_save(word, meaning)
            except Exception as error:  # noqa: BLE001
                result_label.config(text=str(error))
                return
            # Contract: True/"saved" | False/"duplicate" | "failed"/other
            if result is True or result == "saved":
                result_label.config(text=config.ui("Đã lưu.", "Saved."))
            elif result is False or result == "duplicate":
                result_label.config(
                    text=config.ui(
                        "Từ này đã có trong danh sách.",
                        "This word is already in your list.",
                    )
                )
            else:
                result_label.config(
                    text=config.ui(
                        "Không lưu được từ này.",
                        "Could not save this word.",
                    )
                )
        else:
            result_label.config(
                text=config.ui("Không lưu được từ này.", "Saving is not available here.")
            )

    row1 = ttk.Frame(body)
    row1.pack(anchor="w", pady=(8, 0))
    ttk.Button(
        row1, text=config.ui("Dịch từ", "Translate word"), command=translate_word
    ).pack(side=tk.LEFT)
    ttk.Button(
        row1,
        text=config.ui("Dịch câu", "Translate sentence"),
        command=translate_sentence,
    ).pack(side=tk.LEFT, padx=(6, 0))
    row2 = ttk.Frame(body)
    row2.pack(anchor="w", pady=(6, 0))
    ttk.Button(
        row2, text=config.ui("Lưu từ", "Save word"), command=save_word
    ).pack(side=tk.LEFT)
    if callable(on_highlight):
        ttk.Button(
            row2,
            text=config.ui("Đánh dấu", "Highlight"),
            command=on_highlight,
        ).pack(side=tk.LEFT, padx=(6, 0))
    ttk.Button(
        row2, text=config.ui("Đóng", "Close"), command=close
    ).pack(side=tk.LEFT, padx=(6, 0))

    _place_overlay(parent, pop, x_root, y_root)
    try:
        pop.lift()
        pop.focus_set()
    except tk.TclError:
        pass
    return pop


def _place_overlay(parent: tk.Misc, pop: tk.Misc, x_root: int, y_root: int) -> None:
    try:
        parent.update_idletasks()
        pop.update_idletasks()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        ww = max(pop.winfo_reqwidth(), 220)
        wh = max(pop.winfo_reqheight(), 120)
        x = max(8, min(int(x_root - px), pw - ww - 8))
        y = max(8, min(int(y_root - py), ph - wh - 8))
        pop.place(x=x, y=y)
    except tk.TclError:
        try:
            pop.place(x=24, y=24)
        except tk.TclError:
            pass


def word_at_text_index(widget: tk.Text, index) -> tuple:
    """Return (word, start, end) for a Text click index, or ("", None, None)."""
    try:
        start = widget.index(f"{index} wordstart")
        end = widget.index(f"{index} wordend")
        word = widget.get(start, end).strip()
        cleaned = "".join(ch for ch in word if ch.isalnum() or ch in "'’-")
        return cleaned, start, end
    except tk.TclError:
        return "", None, None


def prepare_clickable_text(
    parent: tk.Misc,
    content: str,
    *,
    font=None,
    foreground=None,
    on_click: Optional[Callable] = None,
    height: int = 3,
    width: int = 56,
) -> tk.Text:
    """Read-only Text that can host per-word click handlers."""
    style = ttk.Style()
    background = style.lookup("TFrame", "background") or "#f7f4ef"
    widget = tk.Text(
        parent,
        height=height,
        width=width,
        wrap="word",
        font=font or ui_common.FONT_BODY,
        relief="flat",
        borderwidth=0,
        highlightthickness=0,
        background=background,
        foreground=foreground or ui_common.COLOR_TEXT,
        cursor="hand2",
    )
    widget.insert("1.0", content)
    widget.configure(state="disabled")
    if callable(on_click):
        widget.bind("<Button-1>", on_click)
    return widget
