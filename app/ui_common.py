"""Tiện ích dùng chung cho các cửa sổ: khóa màn hình và gọi AI ở luồng nền."""

import hmac
import threading
import time
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


def reset_window(window: tk.Misc):
    """Gỡ giao diện cũ trước khi vẽ màn hình mới trên cùng một cửa sổ.

    Nếu không gỡ, form đăng nhập còn nằm dưới màn hình sau và bị kéo fullscreen,
    trông như khung hình bị xé. Lần mở lại không dựng lại các form đó nên hết lỗi.
    """
    try:
        window.attributes("-fullscreen", False)
        window.attributes("-topmost", False)
    except tk.TclError:
        pass
    for child in list(window.winfo_children()):
        try:
            child.destroy()
        except tk.TclError:
            pass
    for sequence in ("<Return>", "<KP_Enter>", "<FocusOut>", "<Alt-F4>", "<Escape>"):
        try:
            window.unbind(sequence)
        except tk.TclError:
            pass
    try:
        window.protocol("WM_DELETE_WINDOW", window.destroy)
        window.resizable(True, True)
    except tk.TclError:
        pass


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

    Lưu ý Windows: gọi focus_force() khi người dùng đang bấm chuột sẽ nuốt
    click (nút không phản hồi, kể cả thoát khẩn cấp). Vì vậy guard chỉ lift/
    topmost khi thật sự mất focus, và bỏ qua trong lúc đang bấm chuột.
    """

    # Trì hoãn kéo lại cửa sổ: đủ lâu để click kịp hoàn tất, đủ ngắn để
    # app khác không nằm trên quá lâu.
    _REFOCUS_DELAY_MS = 450
    # Sau mỗi lần bấm chuột, không được kéo focus trong khoảng này.
    _CLICK_GRACE_MS = 700
    # Lúc máy vừa đăng nhập, Windows và app khác tranh focus rất nhiều.
    _STARTUP_QUIET_MS = 2500

    def __init__(self, window: tk.Misc, enabled: bool = None, on_close_attempt=None):
        self.window = window
        self.enabled = config.LOCK_SCREEN if enabled is None else enabled
        self.on_close_attempt = on_close_attempt
        self._suspend_depth = 0
        self._combos = []
        self._refocus_after_ids = set()
        self._pointer_down = False
        self._quiet_until = 0.0
        self._was_fullscreen = False
        self._fullscreen_released = False

        # Cho updater / hộp thoại bên ngoài tạm ngưng guard của cửa sổ này.
        try:
            window._screen_guard = self
        except (tk.TclError, AttributeError):
            pass

        window.protocol("WM_DELETE_WINDOW", self._handle_close_request)

        if self.enabled:
            window.attributes("-fullscreen", True)
            window.attributes("-topmost", True)
            window.bind("<Alt-F4>", lambda _e: "break")
            window.bind("<FocusOut>", self._on_focus_out)
            # Theo dõi chuột trên toàn app để không gọi focus_force giữa lúc click.
            window.bind_all("<ButtonPress-1>", self._on_pointer_down, add="+")
            window.bind_all("<ButtonRelease-1>", self._on_pointer_up, add="+")
            self._mark_quiet(self._STARTUP_QUIET_MS)
        else:
            window.geometry("1280x820")

    # ---------- Chặn đóng cửa sổ ----------

    def _handle_close_request(self):
        if self.on_close_attempt:
            self.on_close_attempt()

    # ---------- Giữ focus ----------

    def _mark_quiet(self, ms: int):
        self._quiet_until = max(self._quiet_until, time.monotonic() + ms / 1000.0)

    def _in_quiet_period(self) -> bool:
        return time.monotonic() < self._quiet_until

    def _on_pointer_down(self, _event=None):
        self._pointer_down = True
        self._mark_quiet(self._CLICK_GRACE_MS)
        self._cancel_refocus()

    def _on_pointer_up(self, _event=None):
        self._pointer_down = False
        self._mark_quiet(self._CLICK_GRACE_MS)

    def _on_focus_out(self, _event=None):
        if not self.enabled or self._suspend_depth:
            return
        # Hủy lịch cũ rồi hẹn lại — tránh xếp chồng hàng chục lần force_focus.
        self._cancel_refocus()
        self._schedule_refocus(self._REFOCUS_DELAY_MS)

    def _schedule_refocus(self, delay_ms: int):
        try:
            after_id = self.window.after(delay_ms, self._maybe_refocus)
        except tk.TclError:
            return
        self._refocus_after_ids.add(after_id)

    def _maybe_refocus(self):
        self._refocus_after_ids.clear()
        if not self.enabled or self._suspend_depth:
            return
        if self._pointer_down or self._in_quiet_period():
            # Người dùng đang tương tác — thử lại sau, đừng cướp click.
            self._schedule_refocus(self._CLICK_GRACE_MS)
            return
        try:
            # Popup của combobox / hộp thoại đang grab thì không kéo focus.
            if self.window.grab_current() is not None or self._popdown_visible():
                return
            # focus_displayof() trả về None khi tiêu điểm đã rời khỏi ứng dụng;
            # nếu focus chỉ nhảy sang widget con thì không cần kéo lại.
            if self.window.focus_displayof() is not None:
                return
        except (tk.TclError, KeyError):
            return
        self.force_focus()

    def _popdown_visible(self) -> bool:
        for widget in list(self._combos):
            try:
                if widget.winfo_exists() and self._popdown_mapped(widget):
                    return True
            except tk.TclError:
                continue
        return False

    def _popdown_path(self, widget: tk.Widget):
        try:
            return widget.tk.call("ttk::combobox::PopdownWindow", widget)
        except tk.TclError:
            return ""

    def _popdown_mapped(self, widget: tk.Widget) -> bool:
        path = self._popdown_path(widget)
        if not path:
            return False
        try:
            return bool(int(widget.tk.call("winfo", "ismapped", path)))
        except tk.TclError:
            return False

    def _raise_popdown(self, widget: tk.Widget):
        path = self._popdown_path(widget)
        if not path:
            return
        try:
            widget.tk.call("wm", "attributes", path, "-topmost", True)
            widget.tk.call("raise", path)
        except tk.TclError:
            pass

    def force_focus(self):
        if not self.enabled or self._suspend_depth:
            return
        if self._pointer_down or self._in_quiet_period():
            return
        try:
            # Hộp thoại đang mở thì không được kéo cửa sổ lên đè lên nó.
            if self.window.grab_current() is not None or self._popdown_visible():
                return
            self.window.attributes("-topmost", True)
            self.window.lift()
            # Không gọi focus_force() — trên Windows nó hủy click đang diễn ra,
            # khiến mọi nút (kể cả thoát khẩn cấp) gần như không bấm được.
            # topmost + lift đủ để giữ app phía trên; widget nhận focus khi
            # người dùng bấm bình thường.
            if self.window.focus_displayof() is None:
                try:
                    self.window.focus_set()
                except tk.TclError:
                    pass
        except tk.TclError:
            pass

    def _cancel_refocus(self):
        pending = list(self._refocus_after_ids)
        self._refocus_after_ids.clear()
        for after_id in pending:
            try:
                self.window.after_cancel(after_id)
            except (tk.TclError, ValueError):
                pass

    # ---------- Tạm ngưng ----------

    def suspend(self, leave_fullscreen: bool = True):
        self._cancel_refocus()
        self._suspend_depth += 1
        if self._suspend_depth == 1 and self.enabled:
            try:
                self.window.attributes("-topmost", False)
                # Combobox chỉ cần tắt topmost. Hộp thoại mật khẩu / cập nhật
                # phải thoát fullscreen, không thì dialog bị che và không bấm được.
                if leave_fullscreen:
                    self._was_fullscreen = bool(self.window.attributes("-fullscreen"))
                    if self._was_fullscreen:
                        self.window.attributes("-fullscreen", False)
                        self.window.state("zoomed")
                        self._fullscreen_released = True
            except tk.TclError:
                pass

    def resume(self, refocus: bool = True):
        self._suspend_depth = max(self._suspend_depth - 1, 0)
        if self._suspend_depth == 0 and self.enabled:
            try:
                if self._fullscreen_released:
                    self.window.attributes("-fullscreen", True)
                    self._fullscreen_released = False
                self.window.attributes("-topmost", True)
            except tk.TclError:
                pass
            # Cho người dùng một khoảng yên sau hộp thoại, tránh tranh focus.
            self._mark_quiet(self._CLICK_GRACE_MS)
            if refocus:
                self._cancel_refocus()
                self._schedule_refocus(self._REFOCUS_DELAY_MS)

    @contextmanager
    def suspended(self, leave_fullscreen: bool = True):
        self.suspend(leave_fullscreen=leave_fullscreen)
        try:
            yield
        finally:
            self.resume()

    def track_combobox(self, widget: tk.Widget):
        """Giữ dropdown mở được khi cửa sổ đang topmost.

        Danh sách của combobox là một cửa sổ khác. Kéo focus hoặc bật lại
        topmost ngay lúc nó mở sẽ làm danh sách đóng hoặc nằm dưới app.
        """
        if widget not in self._combos:
            self._combos.append(widget)
        if not self.enabled:
            return
        widget.bind("<Button-1>", lambda _e, w=widget: self._suspend_for_popdown(w), add="+")
        widget.bind("<<ComboboxSelected>>", lambda _e: self._resume_if_suspended(), add="+")

    def bind_free_focus(self, widget: tk.Widget):
        self.track_combobox(widget)

    def _suspend_for_popdown(self, widget: tk.Widget):
        if self._suspend_depth == 0:
            self.suspend(leave_fullscreen=False)
        self._watch_popdown(widget, 0, False)

    def _watch_popdown(self, widget: tk.Widget, tries: int, seen: bool):
        try:
            alive = widget.winfo_exists()
        except tk.TclError:
            alive = False
        if not alive:
            self._resume_if_suspended()
            return
        if self._popdown_mapped(widget):
            self._raise_popdown(widget)
            widget.after(50, lambda: self._watch_popdown(widget, tries, True))
            return
        if not seen and tries < 12:
            widget.after(40, lambda: self._watch_popdown(widget, tries + 1, False))
            return
        self._resume_if_suspended()

    def _resume_if_suspended(self):
        if self._suspend_depth:
            self.resume(refocus=False)

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
                config.ui("Chưa cấu hình", "Not configured"),
                config.ui(
                    "Chưa đặt EMERGENCY_PASSWORD trong file .env nên không thoát khẩn cấp được.",
                    "EMERGENCY_PASSWORD is not set, so emergency exit cannot run.",
                ),
                parent=parent,
            )
        except tk.TclError:
            pass
        return False

    entered = prompt_password(
        parent,
        config.ui("Thoát khẩn cấp", "Emergency exit"),
        config.ui(
            "Nhập mật khẩu developer để đóng ứng dụng.\n"
            "Lần mở máy này sẽ không được tính là hoàn thành.",
            "Enter the developer password to close the app.\n"
            "This launch will not count as complete.",
        ),
    )
    if entered is None:
        return False
    left = entered.encode("utf-8")
    right = expected.encode("utf-8")
    if len(left) != len(right) or not hmac.compare_digest(left, right):
        try:
            messagebox.showerror(
                config.ui("Sai mật khẩu", "Wrong password"),
                config.ui("Không đúng mật khẩu developer.", "That is not the developer password."),
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
