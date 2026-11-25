"""Device-local voice choice. Never part of account preferences or sync."""

from __future__ import annotations

import config
import languages

DEVICE_VOICES_KEY = "device_voices"


def _table() -> dict:
    raw = config._read_settings().get(DEVICE_VOICES_KEY)
    if not isinstance(raw, dict):
        return {}
    return {
        str(key).strip().lower(): str(value).strip()
        for key, value in raw.items()
        if str(key).strip() and str(value).strip()
    }


def selected_voice_name(language_code: str) -> str:
    code = str(language_code or "").strip().lower()
    if not languages.is_supported_language(code):
        return ""
    return _table().get(code, "")


def set_selected_voice_name(language_code: str, voice_name: str) -> None:
    """Remember a voice for this PC and study language. Does not mark prefs dirty."""
    code = str(language_code or "").strip().lower()
    if not languages.is_supported_language(code):
        return
    payload = config._read_settings()
    table = _table()
    name = str(voice_name or "").strip()
    if name:
        table[code] = name
    else:
        table.pop(code, None)
    payload[DEVICE_VOICES_KEY] = table
    payload.pop("emergency_password", None)
    config._write_settings(payload)
