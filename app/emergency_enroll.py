"""Enrollment and recovery dialogs for the local emergency credential.

The secret is shown once in the dialog. It is not written to logs, settings,
or the window title.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

import config
import emergency_credential
import install


def offer(parent: tk.Misc) -> bool:
    """Ask the user to enroll when no usable credential exists.

    Returns True when screen lock is allowed afterwards. Cancel leaves the
    application unlocked.
    """
    if emergency_credential.lock_allowed():
        return True
    state = emergency_credential.status()
    if state == "unreadable":
        return _offer_unreadable(parent)
    if state == "unacknowledged":
        return _confirm_pending(parent)
    return _enroll_new(parent)


def recover(parent: tk.Misc, *, lock_active: bool) -> None:
    """Reveal or replace the credential. Refused while screen lock is active."""
    if lock_active:
        _error(
            parent,
            config.ui(
                "Chỉ khôi phục mã thoát khẩn cấp khi khóa màn hình đang tắt.",
                "Emergency-code recovery is available only while screen lock is off.",
            ),
        )
        return
    state = emergency_credential.status()
    if state == "acknowledged":
        _recover_enrolled(parent)
        return
    if state == "unreadable":
        _offer_unreadable(parent)
        return
    offer(parent)


def _recover_enrolled(parent: tk.Misc) -> None:
    choice = messagebox.askyesnocancel(
        config.APP_NAME,
        config.ui(
            "Có: xem lại mã hiện tại.\nKhông: tạo mã mới.\nHủy: giữ nguyên.",
            "Yes: show the current code.\nNo: create a new code.\nCancel: keep it unchanged.",
        ),
        parent=parent,
    )
    if choice is None:
        return
    if choice:
        try:
            secret = emergency_credential.reveal_outside_lock(lock_active=False)
        except emergency_credential.EmergencyCredentialError as error:
            _error(parent, str(error))
            return
        messagebox.showinfo(
            config.APP_NAME,
            config.ui("Mã thoát khẩn cấp hiện tại:\n\n", "Current emergency code:\n\n") + secret,
            parent=parent,
        )
        return
    _replace_with_choice(parent)


def _offer_unreadable(parent: tk.Misc) -> bool:
    replace = messagebox.askyesno(
        config.APP_NAME,
        config.ui(
            "Mã thoát khẩn cấp đang lưu không đọc được. Khóa màn hình sẽ tắt.\n\n"
            "Tạo mã mới trên máy này?",
            "The saved emergency code cannot be read. Screen lock stays off.\n\n"
            "Create a new code on this computer?",
        ),
        parent=parent,
    )
    if not replace:
        return False
    return _replace_with_choice(parent)


def _confirm_pending(parent: tk.Misc) -> bool:
    try:
        secret = emergency_credential.begin_or_resume()
    except emergency_credential.EmergencyCredentialError as error:
        _error(parent, str(error))
        return False
    return _acknowledge_shown(parent, secret)


def _enroll_new(parent: tk.Misc) -> bool:
    source = _choose_source(parent)
    if source == "random":
        try:
            secret = emergency_credential.begin_or_resume()
        except emergency_credential.EmergencyCredentialError as error:
            _error(parent, str(error))
            return False
        return _acknowledge_shown(parent, secret)
    if source == "own":
        chosen = _collect_own_code(parent)
        if not chosen:
            return False
        try:
            emergency_credential.begin_or_resume(chosen=chosen)
        except emergency_credential.EmergencyCredentialError as error:
            emergency_credential.cancel_enrollment()
            _error(parent, str(error))
            return False
        if not emergency_credential.acknowledge_current(chosen):
            emergency_credential.cancel_enrollment()
            _error(
                parent,
                config.ui(
                    "Mã chưa được lưu. Khóa màn hình vẫn tắt.",
                    "The code was not saved. Screen lock stays off.",
                ),
            )
            return False
        _register_startup(parent)
        return emergency_credential.lock_allowed()
    return False


def _acknowledge_shown(parent: tk.Misc, secret: str) -> bool:
    accepted = _confirm_dialog(
        parent,
        secret,
        intro=config.ui(
            "Hãy lưu mã thoát khẩn cấp này. Khóa màn hình chỉ bật sau khi bạn nhập lại mã.",
            "Save this emergency code. Screen lock turns on only after you type it back.",
        ),
    )
    if not accepted:
        emergency_credential.cancel_enrollment()
        return False
    if not emergency_credential.acknowledge_current(accepted):
        _error(
            parent,
            config.ui(
                "Mã vừa nhập không khớp. Khóa màn hình vẫn tắt.",
                "That code did not match. Screen lock stays off.",
            ),
        )
        return False
    _register_startup(parent)
    return emergency_credential.lock_allowed()


def _replace_with_choice(parent: tk.Misc) -> bool:
    """Replace a credential only after the new code is confirmed."""
    source = _choose_source(parent)
    if source == "random":
        try:
            secret = emergency_credential.start_reenrollment(
                lock_active=False, replace_existing=True
            )
        except emergency_credential.EmergencyCredentialError as error:
            _error(parent, str(error))
            return False
        accepted = _confirm_dialog(
            parent,
            secret,
            intro=config.ui(
                "Mã cũ vẫn còn hiệu lực cho đến khi bạn xác nhận mã mới.",
                "The current code stays in place until you confirm this new one.",
            ),
        )
        if not accepted:
            emergency_credential.cancel_reenrollment()
            return False
        if not emergency_credential.commit_reenrollment(accepted):
            _error(
                parent,
                config.ui(
                    "Mã mới chưa được lưu. Mã cũ vẫn còn hiệu lực.",
                    "The new code was not saved. The current code is unchanged.",
                ),
            )
            return False
        _register_startup(parent)
        return emergency_credential.lock_allowed()
    if source == "own":
        chosen = _collect_own_code(parent)
        if not chosen:
            return False
        try:
            emergency_credential.start_reenrollment(
                lock_active=False, replace_existing=True, chosen=chosen
            )
        except emergency_credential.EmergencyCredentialError as error:
            emergency_credential.cancel_reenrollment()
            _error(parent, str(error))
            return False
        if not emergency_credential.commit_reenrollment(chosen):
            emergency_credential.cancel_reenrollment()
            _error(
                parent,
                config.ui(
                    "Mã mới chưa được lưu. Mã cũ vẫn còn hiệu lực.",
                    "The new code was not saved. The current code is unchanged.",
                ),
            )
            return False
        _register_startup(parent)
        return emergency_credential.lock_allowed()
    return False


def _choose_source(parent: tk.Misc) -> str:
    """Return own, random, or an empty string when cancelled."""
    dialog = tk.Toplevel(parent)
    dialog.title(config.ui("Mã thoát khẩn cấp", "Emergency code"))
    dialog.resizable(False, False)
    dialog.transient(parent)
    result = {"value": ""}
    frame = ttk.Frame(dialog, padding=16)
    frame.pack(fill=tk.BOTH, expand=True)
    ttk.Label(
        frame,
        text=config.ui(
            "Chọn cách đặt mã thoát khẩn cấp. Hủy sẽ giữ nguyên trạng thái hiện tại.",
            "Choose how to set the emergency code. Cancel leaves the current state unchanged.",
        ),
        wraplength=420,
        justify="left",
    ).pack(anchor="w", pady=(0, 12))

    def pick(value: str):
        result["value"] = value
        dialog.destroy()

    ttk.Button(
        frame,
        text=config.ui("Tự đặt mã", "Set my own emergency code"),
        command=lambda: pick("own"),
    ).pack(fill=tk.X)
    ttk.Button(
        frame,
        text=config.ui("Tạo mã ngẫu nhiên an toàn", "Generate a secure random emergency code"),
        command=lambda: pick("random"),
    ).pack(fill=tk.X, pady=(8, 0))
    ttk.Button(
        frame,
        text=config.ui("Hủy", "Cancel"),
        command=lambda: pick(""),
    ).pack(anchor="e", pady=(12, 0))
    dialog.protocol("WM_DELETE_WINDOW", lambda: pick(""))
    dialog.grab_set()
    parent.wait_window(dialog)
    return result["value"]


def _collect_own_code(parent: tk.Misc) -> str:
    """Return a confirmed chosen code, or an empty string when cancelled."""
    dialog = tk.Toplevel(parent)
    dialog.title(config.ui("Tự đặt mã", "Set my own emergency code"))
    dialog.resizable(False, False)
    dialog.transient(parent)
    result = {"value": ""}
    frame = ttk.Frame(dialog, padding=16)
    frame.pack(fill=tk.BOTH, expand=True)
    ttk.Label(
        frame,
        text=config.ui(
            "Nhập mã rồi nhập lại để xác nhận. Mã trống hoặc quá dễ sẽ bị từ chối.",
            "Type the code, then type it again to confirm. Empty or very easy codes are rejected.",
        ),
        wraplength=420,
        justify="left",
    ).pack(anchor="w")
    first = tk.StringVar()
    second = tk.StringVar()
    ttk.Label(frame, text=config.ui("Mã mới", "New code")).pack(anchor="w", pady=(12, 0))
    ttk.Entry(frame, textvariable=first, show="*", width=42).pack(anchor="w", fill=tk.X)
    ttk.Label(frame, text=config.ui("Nhập lại mã", "Confirm the code")).pack(anchor="w", pady=(8, 0))
    entry = ttk.Entry(frame, textvariable=second, show="*", width=42)
    entry.pack(anchor="w", fill=tk.X)
    problem = ttk.Label(frame, text="", wraplength=420)
    problem.pack(anchor="w", pady=(8, 0))

    def accept():
        left = first.get().strip()
        right = second.get().strip()
        if left != right:
            problem.configure(
                text=config.ui("Hai mã không khớp.", "The two codes do not match.")
            )
            return
        try:
            result["value"] = emergency_credential.normalize_chosen_code(left)
        except emergency_credential.WeakEmergencyCode as error:
            result["value"] = ""
            problem.configure(text=str(error))
            return
        dialog.destroy()

    def cancel():
        result["value"] = ""
        dialog.destroy()

    buttons = ttk.Frame(frame)
    buttons.pack(anchor="e", pady=(12, 0))
    ttk.Button(buttons, text=config.ui("Xác nhận", "Confirm"), command=accept).pack(side=tk.LEFT)
    ttk.Button(buttons, text=config.ui("Hủy", "Cancel"), command=cancel).pack(side=tk.LEFT, padx=(8, 0))
    dialog.protocol("WM_DELETE_WINDOW", cancel)
    entry.focus_set()
    dialog.grab_set()
    parent.wait_window(dialog)
    return result["value"]


def _confirm_dialog(parent: tk.Misc, secret: str, *, intro: str) -> str:
    """Return the typed confirmation, or an empty string when cancelled."""
    dialog = tk.Toplevel(parent)
    dialog.title(config.ui("Mã thoát khẩn cấp", "Emergency code"))
    dialog.resizable(False, False)
    dialog.transient(parent)
    result = {"value": ""}
    frame = ttk.Frame(dialog, padding=16)
    frame.pack(fill=tk.BOTH, expand=True)
    ttk.Label(frame, text=intro, wraplength=420, justify="left").pack(anchor="w")
    shown = ttk.Entry(frame, width=42)
    shown.insert(0, secret)
    shown.configure(state="readonly")
    shown.pack(anchor="w", pady=(12, 8), fill=tk.X)
    ttk.Label(
        frame,
        text=config.ui("Nhập lại mã để xác nhận.", "Type the code again to confirm."),
    ).pack(anchor="w")
    typed = tk.StringVar()
    entry = ttk.Entry(frame, textvariable=typed, show="*", width=42)
    entry.pack(anchor="w", pady=(4, 12), fill=tk.X)

    def accept():
        result["value"] = typed.get()
        dialog.destroy()

    def cancel():
        result["value"] = ""
        dialog.destroy()

    buttons = ttk.Frame(frame)
    buttons.pack(anchor="e")
    ttk.Button(buttons, text=config.ui("Xác nhận", "Confirm"), command=accept).pack(side=tk.LEFT)
    ttk.Button(buttons, text=config.ui("Hủy", "Cancel"), command=cancel).pack(side=tk.LEFT, padx=(8, 0))
    dialog.protocol("WM_DELETE_WINDOW", cancel)
    entry.focus_set()
    dialog.grab_set()
    parent.wait_window(dialog)
    return result["value"].strip()


def _register_startup(parent: tk.Misc) -> None:
    try:
        install.register_startup_after_enrollment()
    except OSError as error:
        _error(parent, str(error))


def _error(parent: tk.Misc, text: str) -> None:
    try:
        messagebox.showerror(config.APP_NAME, text, parent=parent)
    except tk.TclError:
        pass
