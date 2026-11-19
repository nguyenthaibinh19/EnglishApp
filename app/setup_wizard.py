"""Lần đầu mở bản cài đặt: đăng nhập tài khoản do dev tạo.

API key không nhập ở đây. Key chỉ nằm trên server tài khoản.
"""

import tkinter as tk
from tkinter import ttk

import account_client
import config
import ui_common


def _env_banner(parent) -> None:
    """Compact identity before credentials (ADR-025 F3). No secrets."""
    identity = config.environment_identity()
    if identity.identity_error:
        text = "ENVIRONMENT ERROR"
        color = ui_common.COLOR_BAD
    elif getattr(identity, "rc_smoke", False):
        # RC must not look like a fully activated production install.
        text = "PRODUCTION BACKEND · RC TEST DATA"
        color = ui_common.COLOR_WARN
    elif identity.runtime_environment == "production":
        text = "PRODUCTION"
        color = ui_common.COLOR_OK
    elif identity.runtime_environment == "staging":
        text = "STAGING"
        color = ui_common.COLOR_WARN
    else:
        text = "DEVELOPMENT"
        color = ui_common.COLOR_WARN
    ttk.Label(
        parent,
        text=text,
        foreground=color,
        style="Muted.TLabel",
    ).pack(anchor="w", pady=(0, 8))


def _window_title() -> str:
    return config.environment_identity().display_title("Language Guard")


def _form(parent, on_success, *, commit_session: bool = True, result_holder: dict = None):
    """Vẽ form đăng nhập. `on_success` chạy trên luồng giao diện sau khi có token.

    When ``commit_session`` is False, credentials are returned via ``result_holder``
    as ``{"username", "token", "user_id"}`` without saving or starting sync — used
    for transactional account switch (keep A until B authenticates).
    """
    card = ttk.Frame(parent, padding=28)
    card.pack(fill=tk.BOTH, expand=True)

    ttk.Label(card, text=config.ui("Đăng nhập", "Sign in"), style="Title.TLabel").pack(anchor="w")
    _env_banner(card)
    ttk.Label(
        card,
        text=config.ui(
            "Dùng tài khoản do người phát triển tạo. App tự dùng AI, bạn không cần API key.",
            "Use the account the developer created. The app uses the AI for you. You do not need an API key.",
        ),
        style="Muted.TLabel",
        wraplength=420,
        justify="left",
    ).pack(anchor="w", pady=(10, 16))

    ttk.Label(card, text=config.ui("Tên tài khoản", "Username")).pack(anchor="w")
    user_var = tk.StringVar()
    user_entry = ttk.Entry(card, textvariable=user_var, font=ui_common.FONT_BODY)
    user_entry.pack(fill=tk.X, pady=(4, 8), ipady=4)

    ttk.Label(card, text=config.ui("Mật khẩu", "Password")).pack(anchor="w")
    password_var = tk.StringVar()
    ttk.Entry(card, textvariable=password_var, show="*", font=ui_common.FONT_BODY).pack(
        fill=tk.X, pady=(4, 8), ipady=4
    )

    error_label = ttk.Label(card, text="", foreground=ui_common.COLOR_BAD, wraplength=420, justify="left")
    error_label.pack(anchor="w", pady=(4, 4))

    button = ttk.Button(card, text=config.ui("Đăng nhập", "Sign in"))
    button.pack(anchor="w", pady=(8, 0))

    def submit(_event=None):
        username = user_var.get().strip()
        password = password_var.get()
        if not username or not password:
            error_label.config(text=config.ui("Hãy nhập tên tài khoản và mật khẩu.", "Enter a username and password."))
            return
        button.state(["disabled"])
        error_label.config(text=config.ui("Đang đăng nhập…", "Signing in…"))

        def work():
            return account_client.login_session(username, password)

        def ok(result):
            token, user_id = result
            if commit_session:
                config.save_account(username, token, user_id=user_id)
                try:
                    from account_sync_bootstrap import maybe_start_account_sync

                    # Never auto-import guest vocabulary on login.
                    maybe_start_account_sync()
                except Exception:
                    pass
            elif result_holder is not None:
                result_holder["username"] = username
                result_holder["token"] = token
                result_holder["user_id"] = int(user_id)
            on_success()

        def failed(error):
            button.state(["!disabled"])
            # Never surface tokens; account_client errors are user-facing messages.
            error_label.config(text=str(error))

        ui_common.run_async(parent, work, ok, failed)

    button.config(command=submit)
    parent.bind("<Return>", submit)
    user_entry.focus_set()
    return card


def _place(window, width, height):
    window.update_idletasks()
    width = max(width, window.winfo_reqwidth())
    height = max(height, window.winfo_reqheight())
    x = max(0, (window.winfo_screenwidth() - width) // 2)
    y = max(0, (window.winfo_screenheight() - height) // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")


def run(root: tk.Tk) -> bool:
    """Hiện form đăng nhập. Trả về True nếu đã có phiên làm việc."""
    ui_common.reset_window(root)
    root.title(_window_title())
    root.resizable(False, False)
    ui_common.apply_theme(root)
    root.withdraw()

    done = {"ok": False}

    def success():
        done["ok"] = True
        root.quit()

    _form(root, success)
    _place(root, 480, 420)
    root.deiconify()
    root.protocol("WM_DELETE_WINDOW", root.quit)
    root.mainloop()
    root.unbind("<Return>")
    return done["ok"]


def ask(parent, *, commit_session: bool = True) -> bool:
    """Hỏi đăng nhập lại khi server từ chối phiên cũ. Không đụng cửa sổ bài học."""
    dialog = tk.Toplevel(parent)
    dialog.title(_window_title())
    dialog.resizable(False, False)
    dialog.transient(parent)
    try:
        dialog.attributes("-topmost", True)
    except tk.TclError:
        pass
    ui_common.apply_theme(dialog)

    done = {"ok": False}

    def success():
        done["ok"] = True
        dialog.destroy()

    _form(dialog, success, commit_session=commit_session)
    _place(dialog, 480, 420)
    dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
    dialog.grab_set()
    parent.wait_window(dialog)
    return done["ok"]


def authenticate(parent):
    """Authenticate without committing the session. Returns (username, token, user_id) or None.

    Used for transactional account switch: keep the current account until this succeeds.
    Tokens are never written to logs or dialog text.
    """
    dialog = tk.Toplevel(parent)
    dialog.title(_window_title())
    dialog.resizable(False, False)
    dialog.transient(parent)
    try:
        dialog.attributes("-topmost", True)
    except tk.TclError:
        pass
    ui_common.apply_theme(dialog)

    holder = {}
    done = {"ok": False}

    def success():
        done["ok"] = True
        dialog.destroy()

    _form(dialog, success, commit_session=False, result_holder=holder)
    _place(dialog, 480, 420)
    dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
    dialog.grab_set()
    parent.wait_window(dialog)
    if not done["ok"]:
        return None
    username = str(holder.get("username") or "").strip()
    token = str(holder.get("token") or "").strip()
    try:
        user_id = int(holder.get("user_id") or 0)
    except (TypeError, ValueError):
        user_id = 0
    if not username or not token or user_id < 1:
        return None
    return username, token, user_id
