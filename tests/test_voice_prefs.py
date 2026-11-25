"""Device voice choices stay out of account sync."""

from __future__ import annotations

import config
import voice_prefs
from account_prefs import ACCOUNT_PREF_KEYS, collect_local_account_preferences


def test_voice_choice_is_local_and_not_an_account_preference(tmp_path, monkeypatch):
    monkeypatch.delenv("LG_DATA_DIR", raising=False)
    monkeypatch.setattr(config, "SETTINGS_FILE", str(tmp_path / "settings.json"))
    assert voice_prefs.DEVICE_VOICES_KEY not in ACCOUNT_PREF_KEYS
    voice_prefs.set_selected_voice_name("nl", "Microsoft Frank")
    voice_prefs.set_selected_voice_name("es", "Microsoft Helena")
    assert voice_prefs.selected_voice_name("nl") == "Microsoft Frank"
    assert voice_prefs.selected_voice_name("en") == ""
    snapshot = collect_local_account_preferences()
    assert voice_prefs.DEVICE_VOICES_KEY not in snapshot
    assert "Microsoft Frank" not in str(snapshot)
