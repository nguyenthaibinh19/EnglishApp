"""Compact Account section for FreeHome and StudyMaster (no visual redesign)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

import account_session
import app_environment
import config
import ui_common


class AccountPanel:
    """Visible Guest / Signed-in controls with login, logout, and switch."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        on_session_changed: Optional[Callable[[], None]] = None,
        allow_logout: bool = True,
    ):
        self.parent = parent
        self.on_session_changed = on_session_changed
        self.allow_logout = allow_logout
        self.frame = ttk.LabelFrame(
            parent,
            text=config.ui("Tài khoản", "Account"),
            padding=8,
        )
        self.status_label = ttk.Label(
            self.frame, text="", style="Muted.TLabel", wraplength=520, justify="left"
        )
        self.status_label.pack(anchor="w")
        self.detail_label = ttk.Label(
            self.frame, text="", style="Muted.TLabel", wraplength=520, justify="left"
        )
        self.detail_label.pack(anchor="w", pady=(2, 6))
        self.sync_label = ttk.Label(
            self.frame, text="", style="Muted.TLabel", wraplength=520, justify="left"
        )
        self.sync_label.pack(anchor="w", pady=(0, 6))

        buttons = ttk.Frame(self.frame)
        buttons.pack(anchor="w", fill=tk.X)
        self.login_button = ttk.Button(
            buttons,
            text=config.ui("Đăng nhập", "Log in"),
            style="Small.TButton",
            command=self._login,
        )
        self.logout_button = ttk.Button(
            buttons,
            text=config.ui("Đăng xuất", "Log out"),
            style="Small.TButton",
            command=self._logout,
        )
        self.switch_button = ttk.Button(
            buttons,
            text=config.ui("Đổi tài khoản", "Switch account"),
            style="Small.TButton",
            command=self._switch,
        )
        self.refresh()

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)
        return self

    def refresh(self) -> None:
        identity = config.environment_identity()
        host = app_environment.backend_host(str(config.ACCOUNT_SERVER_URL or "")) or "(none)"
        sync_label, sync_detail = account_session.describe_cloud_sync()
        if account_session.is_signed_in():
            self.status_label.config(
                text=config.ui(
                    f"Đã đăng nhập: {account_session.account_display_name()}",
                    f"Signed in: {account_session.account_display_name()}",
                )
            )
            if identity.rc_smoke:
                env_detail = config.ui(
                    f"PRODUCTION BACKEND · RC TEST DATA · máy chủ {host}",
                    f"PRODUCTION BACKEND · RC TEST DATA · backend {host}",
                )
            else:
                env_detail = config.ui(
                    f"Môi trường {identity.runtime_environment} · máy chủ {host}",
                    f"Environment {identity.runtime_environment} · backend {host}",
                )
            self.detail_label.config(text=env_detail)
            self.login_button.pack_forget()
            if self.allow_logout:
                self.logout_button.pack(side=tk.LEFT)
            else:
                self.logout_button.pack_forget()
            self.switch_button.pack(side=tk.LEFT, padx=(8, 0))
        else:
            self.status_label.config(
                text=config.ui("Khách / Chưa đăng nhập", "Guest / Not signed in")
            )
            self.detail_label.config(
                text=config.ui(
                    "Dữ liệu đang lưu local trên máy này. Đồng bộ tài khoản tắt.",
                    "Data stays local on this PC. Account sync is inactive.",
                )
            )
            self.logout_button.pack_forget()
            self.switch_button.pack_forget()
            self.login_button.pack(side=tk.LEFT)
        self.sync_label.config(text=f"Cloud Sync: {sync_label} — {sync_detail}")

    def _notify(self) -> None:
        self.refresh()
        if self.on_session_changed is not None:
            self.on_session_changed()

    def _login(self) -> None:
        account_session.login_dialog(self.parent, on_success=self._notify)

    def _logout(self) -> None:
        if not account_session.is_signed_in():
            self.refresh()
            return
        if not account_session.confirm_leave_account(self.parent):
            return
        account_session.logout_session()
        self._notify()

    def _switch(self) -> None:
        account_session.switch_account(self.parent, on_success=self._notify)
