"""Account-scoped learning preferences (Phase 18C.2).

Synced keys: study_languages, reading_level, native, activities.
Machine-local (never synced): data paths, ScreenGuard, TTS, Windows startup.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import config

ACCOUNT_PREF_KEYS = ("study_languages", "reading_level", "native", "activities")


def collect_local_account_preferences() -> Dict[str, Any]:
    """Snapshot account-scoped settings from the current machine settings file."""
    activities = {}
    for activity in config.OPTIONAL_ACTIVITIES:
        activities[activity["id"]] = bool(config.activity_enabled(activity["id"]))
    return {
        "study_languages": list(config.study_codes()),
        "reading_level": str(config.READING_LEVEL or "A2").strip().upper(),
        "native": config.native_code(),
        "activities": activities,
    }


def persist_account_preferences(store) -> None:
    """Write current account-scoped settings into the account local store."""
    values = collect_local_account_preferences()
    for key, value in values.items():
        store.set_preference(key, value)
    store.set_preference("_prefs_dirty", True)


def apply_preferences_to_settings(values: Dict[str, Any]) -> None:
    """Apply a preferences document onto local settings (account-scoped keys only)."""
    if not isinstance(values, dict):
        return
    if "study_languages" in values and isinstance(values["study_languages"], list):
        config.set_study_codes(values["study_languages"])
    if "native" in values:
        native = str(values["native"] or "").strip().lower()
        if native in {"vi", "en"}:
            payload = config._read_settings()
            payload["native"] = native
            payload.pop("emergency_password", None)
            config._write_settings(payload)
            config.reload()
    if "reading_level" in values:
        level = str(values["reading_level"] or "").strip().upper()
        if level:
            # Runtime only for this process; machine .env remains the install default.
            config.READING_LEVEL = level
    if "activities" in values and isinstance(values["activities"], dict):
        for activity_id, enabled in values["activities"].items():
            try:
                config.set_activity_enabled(str(activity_id), bool(enabled))
            except Exception:
                continue


def sync_preferences_once(store, client) -> None:
    """Pull then push preferences (revision-safe). Applies remote values locally."""
    remote = client.get_preferences()
    remote_values = remote.get("values") if isinstance(remote, dict) else {}
    remote_revision = int(remote.get("revision") or 0) if isinstance(remote, dict) else 0
    local = store.get_preferences()
    dirty = bool(local.pop("_prefs_dirty", False))
    # Always mirror remote into the local preference table.
    for key in ACCOUNT_PREF_KEYS:
        if key in (remote_values or {}):
            store.set_preference(key, remote_values[key])
    store.set_preference("_prefs_server_revision", remote_revision)
    if remote_values:
        apply_preferences_to_settings(remote_values)
    if not dirty:
        return
    local_values = {k: local[k] for k in ACCOUNT_PREF_KEYS if k in local}
    if not local_values:
        local_values = collect_local_account_preferences()
    try:
        body = client.put_preferences(
            values=local_values, expected_revision=remote_revision
        )
    except Exception as error:
        from account_sync_client import SyncConflictClientError

        if isinstance(error, SyncConflictClientError):
            # Re-pull; keep dirty so the next cycle retries with the new tip.
            remote = client.get_preferences()
            remote_values = remote.get("values") if isinstance(remote, dict) else {}
            remote_revision = (
                int(remote.get("revision") or 0) if isinstance(remote, dict) else 0
            )
            for key in ACCOUNT_PREF_KEYS:
                if key in (remote_values or {}):
                    store.set_preference(key, remote_values[key])
            store.set_preference("_prefs_server_revision", remote_revision)
            store.set_preference("_prefs_dirty", True)
            return
        store.set_preference("_prefs_dirty", True)
        raise
    new_revision = int(body.get("revision") or remote_revision + 1)
    for key, value in (body.get("values") or local_values).items():
        if key in ACCOUNT_PREF_KEYS:
            store.set_preference(key, value)
    store.set_preference("_prefs_server_revision", new_revision)
    store.set_preference("_prefs_dirty", False)


def mark_preferences_dirty(store: Optional[Any] = None) -> None:
    """Call after the signed-in user changes account-scoped settings."""
    if store is None:
        from study_data import active_account_store, is_signed_in

        if not is_signed_in():
            return
        store = active_account_store()
    if store is None:
        return
    persist_account_preferences(store)
    try:
        from account_sync_engine import notify_local_change

        notify_local_change()
    except Exception:
        pass
