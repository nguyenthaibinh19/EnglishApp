"""Phase 18C.2 — signed-in study_data facade uses AccountLocalStore."""

from __future__ import annotations

import json
from pathlib import Path

import config
from account_local_store import AccountLocalStore
from study_data import open_study_data
from vocab_identity import new_vocab_id


def _isolate_settings(monkeypatch, data: Path) -> None:
    data.mkdir(parents=True, exist_ok=True)
    settings = data / "settings.json"
    settings.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(config, "SETTINGS_FILE", str(settings))
    monkeypatch.setattr(config, "data_dir", lambda: str(data))
    config.reload()


def test_signed_in_vocab_quiz_path_uses_account_store(tmp_path, monkeypatch):
    data = Path(tmp_path) / "data"
    _isolate_settings(monkeypatch, data)

    user_id = 42
    config.save_account("learner_a", "token-a", user_id=user_id)
    assert config.account_user_id() == user_id

    bundle = open_study_data("nl", data_root=str(data))
    assert bundle.signed_in is True
    assert bundle.vocab.add("fiets", "bike") is True
    words = [e["word"] for e in bundle.vocab.all()]
    assert "fiets" in words

    guest_vocab = data / "languages" / "nl" / "vocab.json"
    assert not guest_vocab.exists()

    store = AccountLocalStore(user_id, data_root=str(data))
    listed = store.list_vocabulary("nl")
    assert any(e.get("word") == "fiets" for e in listed)
    store.close()


def test_guest_mode_still_uses_language_files(tmp_path, monkeypatch):
    data = Path(tmp_path) / "data"
    _isolate_settings(monkeypatch, data)
    config.clear_account()
    config.reload()

    bundle = open_study_data("nl", data_root=str(data))
    assert bundle.signed_in is False
    assert bundle.vocab.add("huis", "house") is True
    guest_vocab = Path(config.vocab_path("nl"))
    assert guest_vocab.exists()
    payload = json.loads(guest_vocab.read_text(encoding="utf-8"))
    assert any(e.get("word") == "huis" for e in payload)


def test_legacy_import_requires_consent(tmp_path):
    store = AccountLocalStore(7, data_root=str(tmp_path))
    entries = [{"id": new_vocab_id(), "word": "kat", "meaning": "cat"}]
    try:
        store.import_guest_vocabulary("nl", entries, require_consent=True)
        assert False, "expected consent error"
    except Exception as error:
        assert "consent" in str(error).lower()
    store.grant_legacy_consent("nl", "guest")
    result = store.import_guest_vocabulary("nl", entries, require_consent=True)
    assert result["imported"] == 1
    result2 = store.import_guest_vocabulary("nl", entries, require_consent=True)
    assert result2["imported"] == 0
    assert result2["skipped"] == 1
    store.close()


def test_preferences_contract_roundtrip(tmp_path):
    import sync_store

    path = tmp_path / "study_sync.db"
    conn = sync_store.connect(str(path))
    doc = sync_store.put_user_preferences(
        conn,
        user_id=1,
        values={"study_languages": ["nl"], "reading_level": "A2", "native": "vi"},
        expected_revision=0,
    )
    assert doc["revision"] == 1
    got = sync_store.get_user_preferences(conn, 1)
    assert got["values"]["study_languages"] == ["nl"]
    assert got["contract_version"] == sync_store.PREFERENCES_CONTRACT_VERSION
    try:
        sync_store.put_user_preferences(
            conn, user_id=1, values={"native": "en"}, expected_revision=0
        )
        assert False, "stale revision should conflict"
    except sync_store.SyncConflictError:
        pass
    conn.close()


def test_account_day_buckets_dedupe_attempts(tmp_path):
    store = AccountLocalStore(9, data_root=str(tmp_path))
    vid = new_vocab_id()
    store.upsert_vocabulary(
        language_code="nl",
        vocab_id=vid,
        payload={"id": vid, "word": "dag", "meaning": "day"},
    )
    store.record_learning_attempt(
        language_code="nl",
        vocab_id=vid,
        verdict="exact",
        hint_used=False,
        word_snapshot="dag",
        user_answer="day",
        expected_answer="day",
        prompt="?",
        occurred_at="2026-11-19T12:00:00+00:00",
    )
    store.record_learning_attempt(
        language_code="nl",
        vocab_id=vid,
        verdict="wrong",
        hint_used=False,
        word_snapshot="dag",
        user_answer="night",
        expected_answer="day",
        prompt="?",
        occurred_at="2026-11-19T13:00:00+00:00",
    )
    days = store.account_day_buckets("nl")
    assert "2026-11-19" in days
    assert days["2026-11-19"]["asked"] == [vid]
    store.close()


def test_account_day_buckets_use_occurred_at_not_received_at(tmp_path):
    """Offline Day-1 answer uploaded on Day-3 stays on Day-1 (UTC occurred_at)."""
    store = AccountLocalStore(11, data_root=str(tmp_path))
    vid = new_vocab_id()
    store.upsert_vocabulary(
        language_code="nl",
        vocab_id=vid,
        payload={"id": vid, "word": "zon", "meaning": "sun"},
    )
    event_id = store.record_learning_attempt(
        language_code="nl",
        vocab_id=vid,
        verdict="exact",
        hint_used=False,
        word_snapshot="zon",
        user_answer="sun",
        expected_answer="sun",
        prompt="?",
        occurred_at="2026-11-01T22:30:00+00:00",
    )
    # Simulate download/apply stamping a later received_at without moving the day.
    with store._lock:
        store._conn.execute(
            "UPDATE learning_attempts SET received_at = ? WHERE event_id = ?",
            ("2026-11-03T08:00:00+00:00", event_id),
        )
        store._conn.commit()
    days = store.account_day_buckets("nl")
    assert "2026-11-01" in days
    assert "2026-11-03" not in days
    assert days["2026-11-01"]["asked"] == [vid]
    store.close()


def test_account_day_buckets_utc_midnight_boundary(tmp_path):
    store = AccountLocalStore(12, data_root=str(tmp_path))
    vid = new_vocab_id()
    store.upsert_vocabulary(
        language_code="nl",
        vocab_id=vid,
        payload={"id": vid, "word": "maan", "meaning": "moon"},
    )
    store.record_learning_attempt(
        language_code="nl",
        vocab_id=vid,
        verdict="wrong",
        hint_used=False,
        word_snapshot="maan",
        user_answer="x",
        expected_answer="moon",
        prompt="?",
        occurred_at="2026-11-02T00:15:00+00:00",
    )
    # Just before UTC midnight belongs to the previous UTC day.
    store.record_learning_attempt(
        language_code="nl",
        vocab_id=vid,
        verdict="exact",
        hint_used=False,
        word_snapshot="maan",
        user_answer="moon",
        expected_answer="moon",
        prompt="?",
        occurred_at="2026-11-01T23:45:00+00:00",
    )
    days = store.account_day_buckets("nl")
    assert "2026-11-01" in days
    assert "2026-11-02" in days
    from study_data import AccountProgress

    progress = AccountProgress(store, "nl")
    # Streak anchored on UTC 2026-11-02 with activity that day and previous day.
    assert progress.account_day_streak(today=__import__("datetime").date(2026, 11, 2)) == 2
    store.close()
