"""Account-scoped learning preferences (Phase 18C.2).

Synced keys: study_languages, reading_level, native, activities.
Machine-local (never synced): data paths, ScreenGuard, TTS, Windows startup.

Remote preference application must never mark the store dirty (no feedback loop).
Unsynced local edits are preserved until a successful push or an explicit conflict.
"""

from __future__ import annotations

import threading
from typing import Any, Dict, Optional

import config

ACCOUNT_PREF_KEYS = ("study_languages", "reading_level", "native", "activities")

_remote_apply = threading.local()


def remote_apply_active() -> bool:
    return bool(getattr(_remote_apply, "active", False))


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


def preferences_dirty(store) -> bool:
    prefs = store.get_preferences()
    return bool(prefs.get("_prefs_dirty"))


def preferences_conflict(store) -> bool:
    prefs = store.get_preferences()
    return bool(prefs.get("_prefs_conflict"))


def _set_meta_flag(store, key: str, value: Any) -> None:
    store.set_preference(key, value)


def persist_account_preferences(store) -> None:
    """Write current account-scoped settings into the account local store as a local edit."""
    values = collect_local_account_preferences()
    for key, value in values.items():
        store.set_preference(key, value)
    _set_meta_flag(store, "_prefs_dirty", True)
    _set_meta_flag(store, "_prefs_conflict", False)


def apply_preferences_to_settings(values: Dict[str, Any], *, from_remote: bool = False) -> None:
    """Apply a preferences document onto local settings (account-scoped keys only)."""
    if not isinstance(values, dict):
        return
    if from_remote:
        _remote_apply.active = True
    try:
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
                config.READING_LEVEL = level
        if "activities" in values and isinstance(values["activities"], dict):
            for activity_id, enabled in values["activities"].items():
                try:
                    config.set_activity_enabled(str(activity_id), bool(enabled))
                except Exception:
                    continue
    finally:
        if from_remote:
            _remote_apply.active = False


def _values_equal(left: Any, right: Any) -> bool:
    return left == right


def _account_pref_subset(source: Dict[str, Any]) -> Dict[str, Any]:
    return {key: source[key] for key in ACCOUNT_PREF_KEYS if key in source}


def sync_preferences_once(store, client) -> None:
    """Pull then conditionally push preferences (revision-safe, no remote dirty loop)."""
    remote = client.get_preferences()
    remote_values = dict(remote.get("values") or {}) if isinstance(remote, dict) else {}
    remote_revision = int(remote.get("revision") or 0) if isinstance(remote, dict) else 0

    local = store.get_preferences()
    dirty = bool(local.get("_prefs_dirty"))
    local_values = _account_pref_subset(local)

    if dirty:
        # Preserve unsynced local edits. Do not overwrite them with remote silently.
        if not local_values:
            local_values = collect_local_account_preferences()
            for key, value in local_values.items():
                store.set_preference(key, value)
        try:
            body = client.put_preferences(
                values=local_values, expected_revision=remote_revision
            )
        except Exception as error:
            from account_sync_client import SyncConflictClientError

            if isinstance(error, SyncConflictClientError):
                # Deterministic conflict: keep local dirty + conflict flag; do not
                # apply remote over local until the user edits again or retries.
                tip = error.body.get("current") if isinstance(error.body, dict) else None
                if isinstance(tip, dict) and "revision" in tip:
                    _set_meta_flag(store, "_prefs_server_revision", int(tip["revision"]))
                else:
                    _set_meta_flag(store, "_prefs_server_revision", remote_revision)
                _set_meta_flag(store, "_prefs_dirty", True)
                _set_meta_flag(store, "_prefs_conflict", True)
                return
            _set_meta_flag(store, "_prefs_dirty", True)
            raise
        new_revision = int(body.get("revision") or remote_revision + 1)
        accepted = _account_pref_subset(body.get("values") or local_values)
        for key, value in accepted.items():
            store.set_preference(key, value)
        _set_meta_flag(store, "_prefs_server_revision", new_revision)
        _set_meta_flag(store, "_prefs_dirty", False)
        _set_meta_flag(store, "_prefs_conflict", False)
        # Mirror accepted tip into settings without marking dirty.
        apply_preferences_to_settings(accepted, from_remote=True)
        return

    # Clean local: adopt remote when present. First empty account may seed once.
    _set_meta_flag(store, "_prefs_server_revision", remote_revision)
    _set_meta_flag(store, "_prefs_conflict", False)
    if remote_values:
        changed = False
        for key in ACCOUNT_PREF_KEYS:
            if key not in remote_values:
                continue
            if key not in local or not _values_equal(local.get(key), remote_values[key]):
                store.set_preference(key, remote_values[key])
                changed = True
        if changed or remote_values:
            apply_preferences_to_settings(remote_values, from_remote=True)
        return

    # Server empty (revision 0) and local clean: seed neutral defaults once.
    # Do not copy machine settings — they may belong to a previously signed-in account.
    if remote_revision == 0 and not local_values:
        import languages

        activities = {activity["id"]: (activity["id"] == "reading") for activity in config.OPTIONAL_ACTIVITIES}
        seed = {
            "study_languages": [languages.default_study_code()],
            "reading_level": "A2",
            "native": "vi",
            "activities": activities,
        }
        for key, value in seed.items():
            store.set_preference(key, value)
        _set_meta_flag(store, "_prefs_dirty", True)
        body = client.put_preferences(values=seed, expected_revision=0)
        new_revision = int(body.get("revision") or 1)
        accepted = _account_pref_subset(body.get("values") or seed)
        for key, value in accepted.items():
            store.set_preference(key, value)
        _set_meta_flag(store, "_prefs_server_revision", new_revision)
        _set_meta_flag(store, "_prefs_dirty", False)
        apply_preferences_to_settings(accepted, from_remote=True)


def mark_preferences_dirty(store: Optional[Any] = None) -> None:
    """Call after the signed-in user changes account-scoped settings."""
    if remote_apply_active():
        return
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
