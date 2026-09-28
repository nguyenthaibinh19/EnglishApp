"""Lần đầu mở bản cài đặt: đăng nhập tài khoản do dev tạo.

API key không nhập ở đây. Key chỉ nằm trên server tài khoản.
"""

import tkinter as tk
from tkinter import ttk

import account_client
import config
import ui_common


def run(root: tk.Tk) -> bool:
    """Hiện form đăng nhập. Trả về True nếu đã có phiên làm việc."""
    root.title(config.APP_NAME)
    root.geometry("480x340")
    root.minsize(440, 300)
    ui_common.apply_theme(root)

    done = {"ok": False}
    card = ttk.Frame(root, padding=28)
    card.pack(fill=tk.BOTH, expand=True)

    ttk.Label(card, text=config.ui("Đăng nhập", "Sign in"), style="Title.TLabel").pack(anchor="w")
    ttk.Label(
        card,
        text=config.ui(
            "Dùng tài khoản do người phát triển tạo. App tự dùng AI, bạn không cần API key.",
            "Use the account the developer created. The app uses the AI for you. You do not need an API key.",
        ),
        style="Muted.TLabel",
        wraplength=400,
        justify="left",
    ).pack(anchor="w", pady=(10, 16))

    ttk.Label(card, text=config.ui("Tên tài khoản", "Username")).pack(anchor="w")
    user_var = tk.StringVar()
    user_entry = ttk.Entry(card, textvariable=user_var, font=ui_common.FONT_BODY)
    user_entry.pack(fill=tk.X, pady=(4, 8), ipady=4)

    ttk.Label(card, text=config.ui("Mật khẩu", "Password")).pack(anchor="w")
    password_var = tk.StringVar()
    password_entry = ttk.Entry(card, textvariable=password_var, show="*", font=ui_common.FONT_BODY)
    password_entry.pack(fill=tk.X, pady=(4, 8), ipady=4)

    error_label = ttk.Label(card, text="", foreground=ui_common.COLOR_BAD, wraplength=400, justify="left")
    error_label.pack(anchor="w", pady=(4, 4))

    def submit(_event=None):
        username = user_var.get().strip()
        password = password_var.get()
        if not username or not password:
            error_label.config(text=config.ui("Hãy nhập tên tài khoản và mật khẩu.", "Enter a username and password."))
            return
        try:
            token = account_client.login(username, password)
            config.save_account(username, token)
        except account_client.AccountError as error:
            error_label.config(text=str(error))
            return
        except OSError as error:
            error_label.config(text=str(error))
            return
        done["ok"] = True
        root.quit()

    ttk.Button(card, text=config.ui("Đăng nhập", "Sign in"), command=submit).pack(anchor="w", pady=(8, 0))
    user_entry.focus_set()
    root.bind("<Return>", submit)
    root.protocol("WM_DELETE_WINDOW", root.quit)
    root.mainloop()
    root.unbind("<Return>")
    return done["ok"]
