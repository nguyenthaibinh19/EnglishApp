"""Màn hình lần đầu của bản .exe: chỉ hỏi API key.

Mật khẩu thoát khẩn cấp do dev đặt trong .env và được đóng vào file .exe.
"""

import tkinter as tk
from tkinter import ttk

import config
import ui_common


def run(root: tk.Tk) -> bool:
    """Hiện form cài đặt phủ kín màn hình. Trả về True nếu đã lưu API key."""
    root.title(config.APP_NAME)
    ui_common.apply_theme(root)
    guard = ui_common.ScreenGuard(root, on_close_attempt=lambda: None)

    done = {"ok": False}
    backdrop = ttk.Frame(root)
    backdrop.pack(fill=tk.BOTH, expand=True)

    card = ttk.Frame(backdrop, padding=36)
    card.place(relx=0.5, rely=0.5, anchor="center")

    ttk.Label(card, text="Cài đặt Dutch Guard", style="Title.TLabel").pack(anchor="w")
    ttk.Label(
        card,
        text="Nhập OpenAI API key để AI chấm câu và viết bài đọc.\nKey lấy tại platform.openai.com/api-keys.",
        style="Muted.TLabel",
        wraplength=460,
        justify="left",
    ).pack(anchor="w", pady=(10, 18))

    ttk.Label(card, text="OpenAI API key").pack(anchor="w")
    key_var = tk.StringVar(value=config.OPENAI_API_KEY)
    key_entry = ttk.Entry(card, textvariable=key_var, show="*", font=ui_common.FONT_BODY, width=48)
    key_entry.pack(fill=tk.X, pady=(6, 6), ipady=6)

    show_key = tk.BooleanVar(value=False)

    def toggle_key():
        key_entry.config(show="" if show_key.get() else "*")

    ttk.Checkbutton(card, text="Hiện key", variable=show_key, command=toggle_key).pack(anchor="w")

    error_label = ttk.Label(card, text="", foreground=ui_common.COLOR_BAD, wraplength=460, justify="left")
    error_label.pack(anchor="w", pady=(12, 4))

    def submit(_event=None):
        key = key_var.get().strip()
        if not config.looks_like_api_key(key):
            error_label.config(text="API key chưa đúng. Key thật bắt đầu bằng sk- và dài hơn 20 ký tự.")
            return
        try:
            config.save_settings(key)
        except OSError as error:
            error_label.config(text=f"Không lưu được cài đặt: {error}")
            return
        done["ok"] = True
        root.quit()

    def emergency():
        if guard.confirm_emergency_exit():
            done["ok"] = False
            root.quit()

    ttk.Button(card, text="Lưu và bắt đầu", command=submit).pack(anchor="w", pady=(8, 0))

    ttk.Button(
        backdrop,
        text="Thoát khẩn cấp",
        style="Small.TButton",
        command=emergency,
    ).place(relx=1.0, rely=1.0, x=-24, y=-24, anchor="se")

    key_entry.focus_set()
    root.bind("<Return>", submit)
    root.mainloop()
    backdrop.destroy()
    root.unbind("<Return>")
    root.unbind("<FocusOut>")
    root.unbind("<Alt-F4>")
    return done["ok"]
