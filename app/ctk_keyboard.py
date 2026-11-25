"""Keyboard behavior for CustomTkinter controls inside the existing Tk root.

CustomTkinter puts focus on an inner label. Return and Space must be bound
there, and a disabled control must not run its command.
"""

from __future__ import annotations

import tkinter as tk

import ui_foundation


def control_is_enabled(widget) -> bool:
    try:
        state = widget.cget("state")
    except Exception:
        return True
    return str(state) != "disabled"


def bind_activation(widget) -> None:
    """Enter and Space run the control. A disabled control stays inactive."""

    def fire(_event=None):
        if not control_is_enabled(widget):
            return "break"
        invoke = getattr(widget, "invoke", None)
        if callable(invoke):
            invoke()
        return "break"

    def focus_in(_event=None):
        try:
            widget.configure(border_width=2, border_color=ui_foundation.COLOR_PRIMARY)
        except Exception:
            pass

    def focus_out(_event=None):
        try:
            widget.configure(border_width=0)
        except Exception:
            pass

    widget.bind("<Return>", fire, add="+")
    widget.bind("<space>", fire, add="+")
    widget.bind("<FocusIn>", focus_in, add="+")
    widget.bind("<FocusOut>", focus_out, add="+")
    # CustomTkinter focuses the inner label. Tab only lands there when that
    # label takes focus. The canvas stays out of the order so one control is
    # one stop.
    label = getattr(widget, "_text_label", None)
    if label is not None:
        try:
            label.configure(takefocus=1)
        except tk.TclError:
            pass
