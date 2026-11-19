"""Start/stop the in-app account sync worker from the Windows UI shell."""

from __future__ import annotations

from typing import Callable, Optional

import config
from account_local_store import SyncStatusSnapshot
from account_sync_engine import start_for_session, stop_active


def maybe_start_account_sync(
    *,
    on_status: Optional[Callable[[SyncStatusSnapshot], None]] = None,
    data_root: Optional[str] = None,
    poll_seconds: float = 60.0,
):
    """Start background sync when a signed-in session and server URL exist.

    No-op for guest. Never uploads machine-global guest files.
    Fail closed when environment identity forbids network writes.
    """
    import app_environment

    token = config.account_token()
    if not token:
        stop_active()
        return None
    base_url = str(getattr(config, "ACCOUNT_SERVER_URL", "") or "").strip()
    if not base_url:
        return None
    identity = app_environment.get_identity()
    if not identity.network_writes_allowed:
        stop_active()
        return None
    if app_environment.validate_backend_for_identity(identity, base_url):
        stop_active()
        return None
    user_id = config.account_user_id()
    if user_id < 1:
        try:
            import account_client

            info = account_client.session_user()
            user_id = int(info.get("user_id") or 0)
            if user_id > 0:
                username = str(
                    info.get("username")
                    or config._read_settings().get("account_username")
                    or ""
                )
                config.save_account(username, token, user_id=user_id)
        except Exception:
            return None
    if user_id < 1:
        return None
    return start_for_session(
        user_id=user_id,
        token=token,
        base_url=base_url,
        data_root=data_root,
        on_status=on_status,
        poll_seconds=poll_seconds,
    )
