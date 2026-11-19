"""Account-scoped learning preferences (Phase 18C.2).

Synced keys: study_languages, reading_level, native, activities.
Machine-local (never synced): data paths, ScreenGuard, TTS, Windows startup.

Optimistic concurrency:
  - Each local edit locks ``_prefs_base_revision`` to the last accepted server tip.
  - Sync compares the live remote tip to that base. Divergent remote content becomes
    a persistent conflict; local unsynced values are preserved.
  - Sync never auto-PUTs against a newly fetched tip just to bypass the conflict.
  - Explicit ``resolve_preferences_conflict(keep=local|server)`` is required.
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
    return bool(store.get_preferences().get("_prefs_dirty"))


def preferences_conflict(store) -> bool:
    return bool(store.get_preferences().get("_prefs_conflict"))


def _set_meta_flag(store, key: str, value: Any) -> None:
    store.set_preference(key, value)


def _values_equal(left: Any, right: Any) -> bool:
    return left == right


def _account_pref_subset(source: Dict[str, Any]) -> Dict[str, Any]:
    return {key: source[key] for key in ACCOUNT_PREF_KEYS if key in source}


def _base_revision(prefs: Dict[str, Any]) -> int:
    try:
        if "_prefs_base_revision" in prefs:
            return int(prefs.get("_prefs_base_revision") or 0)
        return int(prefs.get("_prefs_server_revision") or 0)
    except (TypeError, ValueError):
        return 0


def persist_account_preferences(store) -> None:
    """Write current account-scoped settings as a local edit.

    Locks ``_prefs_base_revision`` on the first dirty transition. Does not clear an
    existing preference conflict (user may refine the local side while conflicted).
    """
    prefs = store.get_preferences()
    values = collect_local_account_preferences()
    for key, value in values.items():
        store.set_preference(key, value)
    if not prefs.get("_prefs_dirty"):
        _set_meta_flag(
            store, "_prefs_base_revision", int(prefs.get("_prefs_server_revision") or 0)
        )
    _set_meta_flag(store, "_prefs_dirty", True)


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


def _record_conflict(store, *, remote_revision: int, remote_values: Dict[str, Any]) -> None:
    _set_meta_flag(store, "_prefs_conflict", True)
    _set_meta_flag(store, "_prefs_dirty", True)
    _set_meta_flag(store, "_prefs_conflict_remote_revision", int(remote_revision))
    _set_meta_flag(store, "_prefs_conflict_remote_values", dict(remote_values or {}))
    # Do not advance ``_prefs_server_revision`` / base — that would invite a silent PUT.


def _clear_conflict_meta(store) -> None:
    _set_meta_flag(store, "_prefs_conflict", False)
    _set_meta_flag(store, "_prefs_conflict_remote_revision", 0)
    _set_meta_flag(store, "_prefs_conflict_remote_values", {})


def sync_preferences_once(store, client) -> None:
    """Pull / push preferences with true optimistic concurrency on the edit base."""
    remote = client.get_preferences()
    remote_values = dict(remote.get("values") or {}) if isinstance(remote, dict) else {}
    remote_revision = int(remote.get("revision") or 0) if isinstance(remote, dict) else 0

    local = store.get_preferences()
    dirty = bool(local.get("_prefs_dirty"))
    conflicted = bool(local.get("_prefs_conflict"))
    local_values = _account_pref_subset(local)

    # Unresolved conflict: never auto-PUT or overwrite local. Wait for explicit resolve.
    if conflicted:
        _set_meta_flag(store, "_prefs_conflict_remote_revision", remote_revision)
        _set_meta_flag(store, "_prefs_conflict_remote_values", remote_values)
        return

    if dirty:
        if not local_values:
            local_values = collect_local_account_preferences()
            for key, value in local_values.items():
                store.set_preference(key, value)
        base = _base_revision(local)
        if remote_revision != base:
            # Remote tip moved since this device's edit base → persistent conflict.
            _record_conflict(
                store, remote_revision=remote_revision, remote_values=remote_values
            )
            return
        # Tip still equals the edit base — safe optimistic PUT.
        try:
            body = client.put_preferences(
                values=local_values, expected_revision=base
            )
        except Exception as error:
            from account_sync_client import SyncConflictClientError

            if isinstance(error, SyncConflictClientError):
                tip = error.body.get("current") if isinstance(error.body, dict) else None
                tip_rev = remote_revision
                tip_vals = remote_values
                if isinstance(tip, dict):
                    if "revision" in tip:
                        tip_rev = int(tip["revision"])
                    if isinstance(tip.get("values"), dict):
                        tip_vals = tip["values"]
                _record_conflict(
                    store, remote_revision=tip_rev, remote_values=tip_vals
                )
                return
            _set_meta_flag(store, "_prefs_dirty", True)
            raise
        new_revision = int(body.get("revision") or base + 1)
        accepted = _account_pref_subset(body.get("values") or local_values)
        for key, value in accepted.items():
            store.set_preference(key, value)
        _set_meta_flag(store, "_prefs_server_revision", new_revision)
        _set_meta_flag(store, "_prefs_base_revision", new_revision)
        _set_meta_flag(store, "_prefs_dirty", False)
        _clear_conflict_meta(store)
        apply_preferences_to_settings(accepted, from_remote=True)
        return

    # Clean local: adopt remote when present. Never invent a dirty flag here.
    _set_meta_flag(store, "_prefs_server_revision", remote_revision)
    _set_meta_flag(store, "_prefs_base_revision", remote_revision)
    _clear_conflict_meta(store)
    if remote_values:
        for key in ACCOUNT_PREF_KEYS:
            if key not in remote_values:
                continue
            if key not in local or not _values_equal(local.get(key), remote_values[key]):
                store.set_preference(key, remote_values[key])
        apply_preferences_to_settings(remote_values, from_remote=True)
        return

    # Server empty (revision 0) and local clean: seed neutral defaults once.
    # Do not copy machine settings — they may belong to a previously signed-in account.
    if remote_revision == 0 and not local_values:
        import languages

        activities = {
            activity["id"]: (activity["id"] == "reading")
            for activity in config.OPTIONAL_ACTIVITIES
        }
        seed = {
            "study_languages": [languages.default_study_code()],
            "reading_level": "A2",
            "native": "vi",
            "activities": activities,
        }
        for key, value in seed.items():
            store.set_preference(key, value)
        _set_meta_flag(store, "_prefs_base_revision", 0)
        _set_meta_flag(store, "_prefs_dirty", True)
        body = client.put_preferences(values=seed, expected_revision=0)
        new_revision = int(body.get("revision") or 1)
        accepted = _account_pref_subset(body.get("values") or seed)
        for key, value in accepted.items():
            store.set_preference(key, value)
        _set_meta_flag(store, "_prefs_server_revision", new_revision)
        _set_meta_flag(store, "_prefs_base_revision", new_revision)
        _set_meta_flag(store, "_prefs_dirty", False)
        _clear_conflict_meta(store)
        apply_preferences_to_settings(accepted, from_remote=True)


def resolve_preferences_conflict(store, client, *, keep: str) -> None:
    """Explicit Keep local / Keep server for a preference conflict."""
    keep = str(keep or "").strip().lower()
    if keep not in {"local", "server"}:
        raise ValueError("keep must be 'local' or 'server'.")
    local = store.get_preferences()
    if not local.get("_prefs_conflict") and not local.get("_prefs_dirty"):
        return

    if keep == "server":
        remote = client.get_preferences()
        remote_values = dict(remote.get("values") or {})
        remote_revision = int(remote.get("revision") or 0)
        for key in ACCOUNT_PREF_KEYS:
            if key in remote_values:
                store.set_preference(key, remote_values[key])
        _set_meta_flag(store, "_prefs_server_revision", remote_revision)
        _set_meta_flag(store, "_prefs_base_revision", remote_revision)
        _set_meta_flag(store, "_prefs_dirty", False)
        _clear_conflict_meta(store)
        apply_preferences_to_settings(remote_values, from_remote=True)
        return

    # keep == local: user explicitly authorizes overwriting the current remote tip.
    local_values = _account_pref_subset(local)
    if not local_values:
        local_values = collect_local_account_preferences()
    remote = client.get_preferences()
    remote_revision = int(remote.get("revision") or 0)
    try:
        body = client.put_preferences(
            values=local_values, expected_revision=remote_revision
        )
    except Exception as error:
        from account_sync_client import SyncConflictClientError

        if isinstance(error, SyncConflictClientError):
            tip = error.body.get("current") if isinstance(error.body, dict) else None
            tip_rev = remote_revision
            tip_vals = dict(remote.get("values") or {})
            if isinstance(tip, dict):
                if "revision" in tip:
                    tip_rev = int(tip["revision"])
                if isinstance(tip.get("values"), dict):
                    tip_vals = tip["values"]
            _record_conflict(store, remote_revision=tip_rev, remote_values=tip_vals)
            return
        raise
    new_revision = int(body.get("revision") or remote_revision + 1)
    accepted = _account_pref_subset(body.get("values") or local_values)
    for key, value in accepted.items():
        store.set_preference(key, value)
    _set_meta_flag(store, "_prefs_server_revision", new_revision)
    _set_meta_flag(store, "_prefs_base_revision", new_revision)
    _set_meta_flag(store, "_prefs_dirty", False)
    _clear_conflict_meta(store)
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
