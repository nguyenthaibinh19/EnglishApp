"""Compact Account section for FreeHome and StudyMaster (no visual redesign)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

import account_session
import app_environment
import config
import ui_common


class AccountSyncStatusPoller:
    """Tk main-thread poller that refreshes AccountPanel Cloud Sync labels.

    Does not talk to the network and does not restart the Sync worker. Reads the
    current local sync status via ``AccountPanel.refresh()`` after the worker has
    had time to record its first result (e.g. Sync endpoint 404 → unavailable).
    """

    def __init__(
        self,
        root: tk.Misc,
        panel: "AccountPanel",
        *,
        initial_delay_ms: int = 1500,
        interval_ms: int = 5000,
    ):
        self.root = root
        self.panel = panel
        self.initial_delay_ms = max(0, int(initial_delay_ms))
        self.interval_ms = max(250, int(interval_ms))
        self._generation = 0
        self._job: Optional[str] = None

    @property
    def active(self) -> bool:
        return self._job is not None

    def start(self) -> None:
        """Begin (or replace) a single poll loop for this FreeHome session."""
        self._generation += 1
        generation = self._generation
        self._cancel_job()
        try:
            self._job = self.root.after(
                self.initial_delay_ms, lambda: self._tick(generation)
            )
        except tk.TclError:
            self._job = None

    def stop(self) -> None:
        """Invalidate any scheduled ticks (window destroy / leave FreeHome)."""
        self._generation += 1
        self._cancel_job()

    def _cancel_job(self) -> None:
        job = self._job
        self._job = None
        if job is None:
            return
        try:
            self.root.after_cancel(job)
        except (tk.TclError, ValueError):
            pass

    def _tick(self, generation: int) -> None:
        if generation != self._generation:
            return
        try:
            if not bool(self.root.winfo_exists()):
                self._job = None
                return
            frame = getattr(self.panel, "frame", None)
            if frame is None or not bool(frame.winfo_exists()):
                self._job = None
                return
        except tk.TclError:
            self._job = None
            return
        try:
            self.panel.refresh()
        except Exception:
            pass
        try:
            self._job = self.root.after(
                self.interval_ms, lambda: self._tick(generation)
            )
        except tk.TclError:
            self._job = None


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
        self.on_refreshed = None
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

    def refresh(self, *, notify: bool = True) -> None:
        """Redraw account and sync labels.

        ``notify=False`` updates this panel only. The poller uses that for the
        visible Settings panel so its hook cannot call back into the poller.
        """
        identity = config.environment_identity()
        host = app_environment.backend_host(str(config.ACCOUNT_SERVER_URL or "")) or "(none)"
        sync_label, sync_detail = account_session.describe_cloud_sync()
        signed_in = account_session.is_signed_in()
        if signed_in:
            status_text = config.ui(
                f"Đã đăng nhập: {account_session.account_display_name()}",
                f"Signed in: {account_session.account_display_name()}",
            )
            if identity.rc_smoke:
                detail_text = config.ui(
                    f"PRODUCTION BACKEND · RC TEST DATA · máy chủ {host}",
                    f"PRODUCTION BACKEND · RC TEST DATA · backend {host}",
                )
            else:
                detail_text = config.ui(
                    f"Môi trường {identity.runtime_environment} · máy chủ {host}",
                    f"Environment {identity.runtime_environment} · backend {host}",
                )
        else:
            status_text = config.ui("Khách / Chưa đăng nhập", "Guest / Not signed in")
            detail_text = config.ui(
                "Dữ liệu đang lưu local trên máy này. Đồng bộ tài khoản tắt.",
                "Data stays local on this PC. Account sync is inactive.",
            )
        sync_text = f"Cloud Sync: {sync_label} — {sync_detail}"
        signature = (signed_in, status_text, detail_text, sync_text, self.allow_logout)
        if signature != getattr(self, "_display_signature", None):
            self._display_signature = signature
            self.status_label.config(text=status_text)
            self.detail_label.config(text=detail_text)
            self.sync_label.config(text=sync_text)
            self._pack_account_actions(signed_in)
        if notify:
            hook = getattr(self, "on_refreshed", None)
            if callable(hook):
                try:
                    hook(sync_label, sync_detail)
                except Exception:
                    pass

    def _pack_account_actions(self, signed_in: bool) -> None:
        if signed_in:
            self.login_button.pack_forget()
            if self.allow_logout:
                self.logout_button.pack(side=tk.LEFT)
            else:
                self.logout_button.pack_forget()
            self.switch_button.pack(side=tk.LEFT, padx=(8, 0))
            return
        self.logout_button.pack_forget()
        self.switch_button.pack_forget()
        self.login_button.pack(side=tk.LEFT)

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
