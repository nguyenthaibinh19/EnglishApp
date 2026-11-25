"""Shared presentation tokens for the Phase 19.2A desktop shell.

Tkinter stays the toolkit. These helpers paint Today. They do not score
answers, write SRS, or complete a study session.
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

# Initial palette. Text on the filled primary color is white.
# Text on the soft fills stays the dark green so contrast holds.
COLOR_PRIMARY = "#34765B"
COLOR_PRIMARY_ACTIVE = "#2C654E"
COLOR_SOFT_GREEN = "#DFEEE4"
COLOR_BG = "#FAF8F3"
COLOR_WARM = "#F6DEAC"
COLOR_SOFT_BLUE = "#DCE9F6"
COLOR_TEXT = "#29433A"
COLOR_CARD = "#FFFFFF"
COLOR_BORDER = "#E6DFD4"
COLOR_ON_PRIMARY = "#FFFFFF"
COLOR_ERROR_BG = "#F8E4E0"
COLOR_ERROR_TEXT = "#7A2E24"

FONT_BRAND = ("Segoe UI", 16, "bold")
FONT_GREETING = ("Segoe UI", 22, "bold")
FONT_CARD_TITLE = ("Segoe UI", 18, "bold")
FONT_BODY = ("Segoe UI", 12)
FONT_SMALL = ("Segoe UI", 10)
FONT_BUTTON = ("Segoe UI", 13, "bold")
FONT_NAV = ("Segoe UI", 10)

PAD_PAGE = 28
PAD_CARD = 20
GAP = 16


def sync_status_kind(label: str) -> str:
    """Map an existing Cloud Sync label to a compact visual state.

    The label itself stays the source of truth. This only picks a color.
    """
    text = str(label or "").strip().lower()
    if "conflict" in text:
        return "conflict"
    if "offline" in text:
        return "offline"
    if "pending" in text:
        return "pending"
    if "synced" in text or "caught up" in text:
        return "synced"
    if "guest" in text or "disabled" in text or "local" in text:
        return "guest"
    return "error"


def sync_status_colors(kind: str) -> tuple[str, str]:
    if kind == "synced":
        return COLOR_SOFT_GREEN, COLOR_TEXT
    if kind == "pending":
        return COLOR_WARM, COLOR_TEXT
    if kind == "offline":
        return COLOR_SOFT_BLUE, COLOR_TEXT
    if kind == "conflict":
        return COLOR_WARM, COLOR_ERROR_TEXT
    if kind == "guest":
        return "#EFEAE2", COLOR_TEXT
    return COLOR_ERROR_BG, COLOR_ERROR_TEXT


def paint_root(root: tk.Misc) -> None:
    try:
        root.configure(bg=COLOR_BG)
    except tk.TclError:
        pass


def label(parent: tk.Misc, text: str, *, font=None, fg: str = COLOR_TEXT, bg: str = COLOR_BG) -> tk.Label:
    return tk.Label(
        parent,
        text=text,
        font=font or FONT_BODY,
        fg=fg,
        bg=bg,
        justify="left",
        anchor="w",
    )


def card(parent: tk.Misc) -> tk.Frame:
    """Warm card. Windows Tk does not clip children to a rounded mask, so the
    corner is a soft border and padding rather than a drawn radius.
    """
    return tk.Frame(
        parent,
        bg=COLOR_CARD,
        highlightbackground=COLOR_BORDER,
        highlightthickness=1,
        padx=PAD_CARD,
        pady=PAD_CARD,
        bd=0,
    )


def primary_button(parent: tk.Misc, text: str, command: Callable[[], None]) -> tk.Button:
    return tk.Button(
        parent,
        text=text,
        command=command,
        font=FONT_BUTTON,
        bg=COLOR_PRIMARY,
        fg=COLOR_ON_PRIMARY,
        activebackground=COLOR_PRIMARY_ACTIVE,
        activeforeground=COLOR_ON_PRIMARY,
        relief="flat",
        bd=0,
        padx=16,
        pady=10,
        cursor="hand2",
        highlightthickness=0,
    )


def quiet_button(parent: tk.Misc, text: str, command: Callable[[], None], *, selected: bool = False) -> tk.Button:
    bg = COLOR_SOFT_GREEN if selected else COLOR_BG
    return tk.Button(
        parent,
        text=text,
        command=command,
        font=FONT_BODY,
        bg=bg,
        fg=COLOR_TEXT,
        activebackground=COLOR_SOFT_GREEN,
        activeforeground=COLOR_TEXT,
        disabledforeground="#8A9A93",
        relief="flat",
        bd=0,
        padx=10,
        pady=6,
        cursor="hand2",
        highlightthickness=0,
    )


def status_chip(parent: tk.Misc, text: str, kind: str, command: Optional[Callable[[], None]] = None) -> tk.Button:
    bg, fg = sync_status_colors(kind)
    return tk.Button(
        parent,
        text=text,
        command=command,
        font=FONT_SMALL,
        bg=bg,
        fg=fg,
        activebackground=bg,
        activeforeground=fg,
        relief="flat",
        bd=0,
        padx=10,
        pady=4,
        cursor="hand2" if command else "",
        highlightthickness=0,
    )


def environment_badge(identity) -> str:
    """Compact non-production marker. Production stays blank."""
    if bool(getattr(identity, "rc_smoke", False)):
        return "RC TEST"
    env = str(getattr(identity, "runtime_environment", "production") or "production")
    if env == "production":
        return ""
    if env == "staging":
        return "STAGING"
    if env == "development":
        return "DEVELOPMENT"
    return env.replace("_", " ").upper()


def environment_chip(parent: tk.Misc, text: str) -> tk.Label:
    return tk.Label(
        parent,
        text=text,
        font=("Segoe UI", 9, "bold"),
        bg=COLOR_WARM,
        fg=COLOR_TEXT,
        padx=8,
        pady=3,
    )


def _round_rect(canvas: tk.Canvas, x1: int, y1: int, x2: int, y2: int, radius: int, **kwargs):
    radius = max(0, min(radius, (x2 - x1) // 2, (y2 - y1) // 2))
    points = [
        x1 + radius, y1,
        x2 - radius, y1,
        x2, y1,
        x2, y1 + radius,
        x2, y2 - radius,
        x2, y2,
        x2 - radius, y2,
        x1 + radius, y2,
        x1, y2,
        x1, y2 - radius,
        x1, y1 + radius,
        x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, splinesteps=16, **kwargs)


def rounded_panel(parent: tk.Misc, *, fill: str, radius: int = 18) -> tk.Frame:
    """Canvas plate with content inset past the corner radius.

    Windows Tk does not clip a child widget to a rounded mask. The inner frame
    stays square and is inset so the painted corners remain visible.
    """
    try:
        outer_bg = parent.cget("bg")
    except tk.TclError:
        outer_bg = COLOR_BG
    holder = tk.Frame(parent, bg=outer_bg)
    canvas = tk.Canvas(holder, bg=outer_bg, highlightthickness=0, bd=0, height=1)
    canvas.pack(fill=tk.BOTH, expand=True)
    body = tk.Frame(canvas, bg=fill)
    window_id = canvas.create_window(radius, radius, window=body, anchor="nw")
    state = {"drawing": False}

    def redraw(_event=None):
        if state["drawing"]:
            return
        state["drawing"] = True
        try:
            width = max(body.winfo_reqwidth() + radius * 2, 40)
            height = max(body.winfo_reqheight() + radius * 2, 40)
            canvas.configure(width=width, height=height)
            canvas.delete("plate")
            _round_rect(
                canvas, 1, 1, width - 2, height - 2, radius, fill=fill, outline=fill, tags="plate"
            )
            canvas.coords(window_id, radius, radius)
            canvas.tag_raise(window_id)
        finally:
            state["drawing"] = False

    body.bind("<Configure>", redraw, add="+")
    holder.body = body
    holder.redraw = redraw
    return holder


def feedback_banner(parent: tk.Misc, text: str, kind: str = "info") -> tk.Label:
    """Inline feedback. ``kind`` is ok, warn, or error. No score is implied."""
    if kind == "ok":
        bg, fg = COLOR_SOFT_GREEN, COLOR_TEXT
    elif kind == "warn":
        bg, fg = COLOR_WARM, COLOR_TEXT
    elif kind == "error":
        bg, fg = COLOR_ERROR_BG, COLOR_ERROR_TEXT
    else:
        bg, fg = COLOR_SOFT_BLUE, COLOR_TEXT
    return tk.Label(
        parent,
        text=text,
        font=FONT_SMALL,
        bg=bg,
        fg=fg,
        padx=10,
        pady=6,
        justify="left",
        anchor="w",
    )
