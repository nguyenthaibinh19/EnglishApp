"""Tiện ích dùng chung cho các cửa sổ: khóa màn hình và gọi AI ở luồng nền."""

import hmac
import threading
import tkinter as tk
from contextlib import contextmanager
from tkinter import messagebox, ttk

import config

# ============================================================
# Bảng màu & phông chữ dùng chung
# ============================================================

FONT_TITLE = ("Segoe UI", 22, "bold")
FONT_H2 = ("Segoe UI", 14, "bold")
FONT_BODY = ("Segoe UI", 12)
FONT_SMALL = ("Segoe UI", 10)
FONT_QUESTION = ("Segoe UI", 26, "bold")
FONT_ANSWER = ("Segoe UI", 20)

COLOR_OK = "#1a7f37"
COLOR_BAD = "#c62828"
COLOR_WARN = "#b26a00"
COLOR_MUTED = "#5f6368"
COLOR_ACCENT = "#1e4f9c"


def apply_theme(root: tk.Misc):
    """Đồng bộ phông chữ cho toàn bộ widget ttk."""
    style = ttk.Style(root)
    if "vista" in style.theme_names():
        style.theme_use("vista")
    style.configure("TLabel", font=FONT_BODY)
    style.configure("TButton", font=FONT_BODY, padding=6)
    style.configure("Small.TButton", font=FONT_SMALL, padding=4)
    style.configure("TLabelframe.Label", font=FONT_H2)
    style.configure("TRadiobutton", font=FONT_BODY)
    style.configure("Title.TLabel", font=FONT_TITLE)
    style.configure("H2.TLabel", font=FONT_H2)
    style.configure("Muted.TLabel", font=FONT_SMALL, foreground=COLOR_MUTED)
    return style


# ============================================================
# Khóa màn hình
# ============================================================


class ScreenGuard:
    """Giữ cửa sổ ở chế độ toàn màn hình, luôn trên cùng và không cho tắt.

    Có thể tạm ngưng khi cần mở hộp thoại hay combobox:

        with guard.suspended():
            messagebox.askyesno(...)

    Đặt LOCK_SCREEN=0 trong .env để tắt hẳn khi đang dev.
    """

    def __init__(self, window: tk.Misc, enabled: bool = None, on_close_attempt=None):
        self.window = window
        self.enabled = config.LOCK_SCREEN if enabled is None else enabled
        self.on_close_attempt = on_close_attempt
        self._suspend_depth = 0

        window.protocol("WM_DELETE_WINDOW", self._handle_close_request)
        window.bind("<Alt-F4>", lambda _e: "break")

        if self.enabled:
            window.attributes("-fullscreen", True)
            window.attributes("-topmost", True)
            window.bind("<FocusOut>", self._on_focus_out)
        else:
            window.geometry("1280x820")

    # ---------- Chặn đóng cửa sổ ----------

    def _handle_close_request(self):
        if self.on_close_attempt:
            self.on_close_attempt()

    # ---------- Giữ focus ----------

    def _on_focus_out(self, _event=None):
        self.window.after(120, self._maybe_refocus)

    def _maybe_refocus(self):
        if not self.enabled or self._suspend_depth:
            return
        try:
            # focus_displayof() trả về None khi tiêu điểm đã rời khỏi ứng dụng;
            # nếu focus chỉ nhảy sang widget con thì không cần kéo lại.
            if self.window.focus_displayof() is not None:
                return
        except (tk.TclError, KeyError):
            return
        self.force_focus()

    def force_focus(self):
        try:
            self.window.attributes("-topmost", True)
            self.window.lift()
            self.window.focus_force()
        except tk.TclError:
            pass

    # ---------- Tạm ngưng ----------

    def suspend(self):
        self._suspend_depth += 1
        if self._suspend_depth == 1 and self.enabled:
            try:
                self.window.attributes("-topmost", False)
            except tk.TclError:
                pass

    def resume(self, refocus: bool = True):
        self._suspend_depth = max(self._suspend_depth - 1, 0)
        if self._suspend_depth == 0 and self.enabled:
            if refocus:
                self.window.after(150, self.force_focus)
            else:
                try:
                    self.window.attributes("-topmost", True)
                except tk.TclError:
                    pass

    @contextmanager
    def suspended(self):
        self.suspend()
        try:
            yield
        finally:
            self.resume()

    def bind_free_focus(self, widget: tk.Widget):
        """Cho phép widget (combobox, menu...) mở popup mà không bị kéo focus."""
        widget.bind("<Button-1>", lambda _e: self.suspend(), add="+")
        widget.bind("<<ComboboxSelected>>", lambda _e: self.resume(), add="+")
        widget.bind("<FocusOut>", lambda _e: self.resume(refocus=False), add="+")

    # ---------- Hộp thoại an toàn ----------

    def ask_yes_no(self, title: str, message: str) -> bool:
        with self.suspended():
            try:
                return bool(messagebox.askyesno(title, message, parent=self.window))
            except tk.TclError:
                return True

    def show_info(self, title: str, message: str):
        with self.suspended():
            try:
                messagebox.showinfo(title, message, parent=self.window)
            except tk.TclError:
                pass

    def show_error(self, title: str, message: str):
        with self.suspended():
            try:
                messagebox.showerror(title, message, parent=self.window)
            except tk.TclError:
                pass

    def confirm_emergency_exit(self) -> bool:
        with self.suspended():
            return confirm_developer_exit(self.window)


def prompt_password(parent: tk.Misc, title: str, prompt: str):
    """Hộp thoại mật khẩu. Trả về chuỗi đã nhập, hoặc None nếu hủy."""
    result = {"value": None}
    dialog = tk.Toplevel(parent)
    dialog.title(title)
    dialog.transient(parent)
    dialog.resizable(False, False)
    try:
        dialog.attributes("-topmost", True)
    except tk.TclError:
        pass

    ttk.Label(dialog, text=prompt, wraplength=380, justify="left").pack(
        padx=16, pady=(16, 8)
    )
    var = tk.StringVar()
    entry = ttk.Entry(dialog, textvariable=var, show="*", width=34, font=FONT_BODY)
    entry.pack(padx=16, pady=4)
    entry.focus_set()

    def submit(_event=None):
        result["value"] = var.get()
        dialog.destroy()

    def cancel(_event=None):
        result["value"] = None
        dialog.destroy()

    buttons = ttk.Frame(dialog)
    buttons.pack(pady=12)
    ttk.Button(buttons, text="OK", command=submit).pack(side=tk.LEFT, padx=6)
    ttk.Button(buttons, text="Hủy", command=cancel).pack(side=tk.LEFT, padx=6)

    dialog.bind("<Return>", submit)
    dialog.bind("<KP_Enter>", submit)
    dialog.bind("<Escape>", cancel)
    dialog.protocol("WM_DELETE_WINDOW", cancel)

    dialog.update_idletasks()
    try:
        px = parent.winfo_rootx() + max((parent.winfo_width() - dialog.winfo_width()) // 2, 0)
        py = parent.winfo_rooty() + max((parent.winfo_height() - dialog.winfo_height()) // 3, 0)
        dialog.geometry(f"+{px}+{py}")
    except tk.TclError:
        pass

    dialog.grab_set()
    dialog.wait_window()
    return result["value"]


def confirm_developer_exit(parent: tk.Misc) -> bool:
    """Chỉ thoát khi nhập đúng EMERGENCY_PASSWORD trong .env."""
    expected = config.EMERGENCY_PASSWORD
    if not expected:
        try:
            messagebox.showerror(
                "Chưa cấu hình",
                "Chưa đặt EMERGENCY_PASSWORD trong file .env nên không thoát khẩn cấp được.",
                parent=parent,
            )
        except tk.TclError:
            pass
        return False

    entered = prompt_password(
        parent,
        "Thoát khẩn cấp",
        "Nhập mật khẩu developer để đóng ứng dụng.\n"
        "Buổi học hôm nay sẽ không được tính là hoàn thành.",
    )
    if entered is None:
        return False
    left = entered.encode("utf-8")
    right = expected.encode("utf-8")
    if len(left) != len(right) or not hmac.compare_digest(left, right):
        try:
            messagebox.showerror(
                "Sai mật khẩu",
                "Không đúng mật khẩu developer.",
                parent=parent,
            )
        except tk.TclError:
            pass
        return False
    return True


# ============================================================
# Gọi hàm chậm (AI) mà không làm đơ giao diện
# ============================================================


def run_async(widget: tk.Misc, work, on_success, on_error=None):
    """Chạy `work()` ở luồng nền rồi gọi callback trên luồng giao diện.

    Callback bị bỏ qua nếu cửa sổ đã bị đóng trong lúc chờ.
    """

    def deliver(callback, value):
        def invoke():
            try:
                if widget.winfo_exists():
                    callback(value)
            except tk.TclError:
                pass

        try:
            widget.after(0, invoke)
        except (tk.TclError, RuntimeError):
            pass

    def runner():
        try:
            result = work()
        except Exception as error:  # noqa: BLE001 - lỗi được đẩy về UI để hiển thị
            if on_error is not None:
                deliver(on_error, error)
            return
        deliver(on_success, result)

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    return thread


# ============================================================
# Widget tiện dụng
# ============================================================


class ScrollableFrame(ttk.Frame):
    """Khung cuộn dọc, dùng cho danh sách câu hỏi dài."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)

        self.canvas = tk.Canvas(self, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.body = ttk.Frame(self.canvas)
        self._window = self.canvas.create_window((0, 0), window=self.body, anchor="nw")

        self.body.bind("<Configure>", self._on_body_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind("<Enter>", lambda _e: self._bind_wheel())
        self.canvas.bind("<Leave>", lambda _e: self._unbind_wheel())

    def _on_body_configure(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure(self._window, width=event.width)

    def _bind_wheel(self):
        self.canvas.bind_all("<MouseWheel>", self._on_wheel)

    def _unbind_wheel(self):
        self.canvas.unbind_all("<MouseWheel>")

    def _on_wheel(self, event):
        self.canvas.yview_scroll(int(-event.delta / 120), "units")


def make_text(parent, **kwargs) -> tk.Text:
    """tk.Text kèm thanh cuộn, trả về chính widget Text."""
    frame = ttk.Frame(parent)
    frame.pack(fill=tk.BOTH, expand=True)

    text = tk.Text(frame, wrap="word", relief=tk.FLAT, **kwargs)
    scrollbar = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
    text.configure(yscrollcommand=scrollbar.set)

    text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    return text


def set_text(widget: tk.Text, content: str):
    """Ghi nội dung vào một Text đang ở trạng thái disabled."""
    widget.config(state="normal")
    widget.delete("1.0", "end")
    if content:
        widget.insert("1.0", content)
    widget.config(state="disabled")
