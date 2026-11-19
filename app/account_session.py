"""Account login / logout / switch lifecycle (Product Owner Account UX).

Stops and starts the sync engine, never deletes local account SQLite, never
auto-imports Guest data, and never silently falls back to Guest after errors.

Switching is transactional: account A stays active until B authenticates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Tuple

import config

AuthResult = Tuple[str, str, int]  # username, token, user_id


@dataclass(frozen=True)
class PendingSyncSummary:
    pending_vocab: int = 0
    pending_progress: int = 0
    prefs_dirty: bool = False
    conflict: bool = False
    offline: bool = False

    @property
    def has_pending(self) -> bool:
        return bool(
            self.pending_vocab
            or self.pending_progress
            or self.prefs_dirty
            or self.conflict
            or self.offline
        )

    def user_message(self) -> str:
        parts = []
        if self.pending_vocab:
            parts.append(
                config.ui(
                    f"{self.pending_vocab} thay đổi từ vựng chưa đồng bộ",
                    f"{self.pending_vocab} vocabulary change(s) not synced",
                )
            )
        if self.pending_progress:
            parts.append(
                config.ui(
                    f"{self.pending_progress} tiến độ chưa đồng bộ",
                    f"{self.pending_progress} progress item(s) not synced",
                )
            )
        if self.prefs_dirty:
            parts.append(
                config.ui("tùy chọn chưa đồng bộ", "preferences not synced")
            )
        if self.conflict:
            parts.append(
                config.ui("còn xung đột cần xử lý", "open conflicts need attention")
            )
        if self.offline:
            parts.append(
                config.ui("đang offline với máy chủ", "currently offline from the server")
            )
        if not parts:
            return ""
        return config.ui(
            "Còn dữ liệu chưa đồng bộ: " + "; ".join(parts) + ". "
            "Đăng xuất không xóa dữ liệu tài khoản trên máy này.",
            "Unsynced account data remains: " + "; ".join(parts) + ". "
            "Logging out does not delete this account's local data on this PC.",
        )


def is_signed_in() -> bool:
    from study_data import is_signed_in as _signed

    return _signed()


def account_display_name() -> str:
    if not is_signed_in():
        return config.ui("Khách", "Guest")
    settings = config._read_settings()
    username = str(settings.get("account_username") or "").strip()
    user_id = config.account_user_id()
    if username and user_id:
        return f"{username} (id {user_id})"
    if username:
        return username
    if user_id:
        return f"id {user_id}"
    return config.ui("Đã đăng nhập", "Signed in")


def pending_sync_summary() -> PendingSyncSummary:
    if not is_signed_in():
        return PendingSyncSummary()
    try:
        from account_sync_engine import active_engine
        from account_local_store import AccountLocalStore

        engine = active_engine()
        owned = False
        if engine is not None and engine.store.user_id == config.account_user_id():
            store = engine.store
        else:
            store = AccountLocalStore(config.account_user_id())
            owned = True
        try:
            snap = store.status()
            prefs_dirty = snap.status == "pending" and not (
                snap.pending_vocab or snap.pending_progress
            )
            return PendingSyncSummary(
                pending_vocab=snap.pending_vocab,
                pending_progress=snap.pending_progress,
                prefs_dirty=prefs_dirty,
                conflict=snap.conflict,
                offline=snap.offline,
            )
        finally:
            if owned:
                store.close()
    except Exception:
        return PendingSyncSummary()


def describe_cloud_sync() -> tuple[str, str]:
    """User-readable Cloud Sync label + explanation. Never guess Synced."""
    import app_environment

    if not is_signed_in():
        return app_environment.cloud_sync_ui_state(
            signed_in=False, engine_running=False
        )
    identity = config.environment_identity()
    if not identity.network_writes_allowed:
        return (
            "Unavailable",
            config.ui(
                "Cấu hình môi trường không cho phép ghi mạng.",
                "Environment identity blocks network writes.",
            ),
        )
    try:
        from account_sync_engine import active_engine

        engine = active_engine()
        if engine is None:
            return (
                "Signed in / Server Sync disabled",
                config.ui(
                    "Đã đăng nhập nhưng đồng bộ tài khoản trên máy chủ chưa bật "
                    "hoặc worker chưa chạy. Dữ liệu vẫn lưu local theo tài khoản.",
                    "Signed in, but server account sync is off or the worker is "
                    "not running. Learning data still stays in this account's local store.",
                ),
            )
        snap = engine.status()
        caught_up = bool(snap.vocab_caught_up and snap.progress_caught_up) and not (
            snap.pending_vocab or snap.pending_progress or snap.conflict or snap.offline
        )
        label, detail = app_environment.cloud_sync_ui_state(
            signed_in=True,
            engine_running=True,
            engine_status=snap.status,
            engine_detail=snap.detail,
            caught_up=caught_up,
        )
        if label == "Conflict":
            return (
                "Conflict / Action required",
                detail
                or config.ui(
                    "Có xung đột — mở Sync conflicts để chọn Keep local/server.",
                    "Conflicts need a choice — open Sync conflicts.",
                ),
            )
        if label == "Server Sync unavailable":
            return (
                "Server Sync unavailable",
                detail
                or config.ui(
                    "Đã lưu local; máy chủ chưa bật đồng bộ — chưa tải lên.",
                    "Data saved locally; not uploaded",
                ),
            )
        if label == "Pending":
            return (
                "Pending",
                detail
                or config.ui(
                    "Đang chờ tải lên/xuống. Chưa coi là đã sao lưu xong.",
                    "Upload/download in progress. Not a confirmed backup yet.",
                ),
            )
        if label == "Synced":
            return (
                "Synced",
                config.ui(
                    "Máy chủ đã nhận và client đã bắt kịp.",
                    "Server accepted changes and this client caught up.",
                ),
            )
        return label, detail
    except Exception:
        return (
            "Unknown",
            config.ui(
                "Không đọc được trạng thái đồng bộ.",
                "Could not read sync status.",
            ),
        )


def stop_sync_engine() -> None:
    try:
        from account_sync_engine import stop_active

        stop_active()
    except Exception:
        pass


def start_sync_engine() -> None:
    try:
        from account_sync_bootstrap import maybe_start_account_sync

        maybe_start_account_sync()
    except Exception:
        pass


def logout_session() -> None:
    """Clear the session token only. Local account SQLite is kept on disk."""
    stop_sync_engine()
    config.clear_account()


def confirm_leave_account(parent) -> bool:
    """Warn about pending unsynced changes before logout/switch. Returns True to proceed."""
    from tkinter import messagebox

    summary = pending_sync_summary()
    if not summary.has_pending:
        return messagebox.askyesno(
            config.ui("Đăng xuất", "Log out"),
            config.ui(
                "Đăng xuất khỏi tài khoản này?\n"
                "Dữ liệu học của tài khoản vẫn giữ trên máy này.",
                "Log out of this account?\n"
                "This account's learning data stays on this PC.",
            ),
            parent=parent,
        )
    return messagebox.askyesno(
        config.ui("Còn dữ liệu chưa đồng bộ", "Unsynced changes"),
        summary.user_message()
        + "\n\n"
        + config.ui("Vẫn đăng xuất / đổi tài khoản?", "Still log out / switch account?"),
        parent=parent,
    )


def commit_session(username: str, token: str, user_id: int) -> None:
    """Persist B's session and start B's sync worker. Does not log tokens."""
    stop_sync_engine()
    config.save_account(username, token, user_id=user_id)
    start_sync_engine()


def login_dialog(parent, *, on_success: Optional[Callable[[], None]] = None) -> bool:
    """Open in-app login without restarting. Returns True if a session was established."""
    import setup_wizard

    ok = setup_wizard.ask(parent, commit_session=True)
    if ok:
        start_sync_engine()
        if on_success is not None:
            on_success()
    return ok


def switch_account(parent, *, on_success: Optional[Callable[[], None]] = None) -> bool:
    """Authenticate B before leaving A. Cancel/failure keeps A signed in.

    Sequence on success:
    1) confirm pending changes
    2) authenticate B (A session still active)
    3) stop A's sync worker (A SQLite remains on disk)
    4) commit B's session + start B's worker
    5) rebind views via on_success
    """
    import setup_wizard

    if is_signed_in():
        if not confirm_leave_account(parent):
            return False
        credentials = setup_wizard.authenticate(parent)
        if credentials is None:
            # Cancelled or auth failed — A remains active; sync still running.
            return False
        username, token, user_id = credentials
        commit_session(username, token, user_id)
        if on_success is not None:
            on_success()
        return True
    # Guest → login (same as login_dialog)
    return login_dialog(parent, on_success=on_success)


def close_account_bound_windows(*windows) -> None:
    """Destroy account-backed Toplevels so they cannot write the previous store."""
    for window in windows:
        if window is None:
            continue
        try:
            if window.winfo_exists():
                window.destroy()
        except Exception:
            pass
