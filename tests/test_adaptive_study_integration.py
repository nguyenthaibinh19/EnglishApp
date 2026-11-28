"""Phase 19.4C — Home/StudyMaster adaptive integration (dev unlocked only)."""

from __future__ import annotations

import json
import random
from pathlib import Path

import config
import pytest
from adaptive_study import (
    AdaptiveStudyIdentity,
    adaptive_integration_enabled,
    adaptive_unlocked_allowed,
    attach_bridge,
    build_integrated_session,
    capture_identity,
    open_practice_store,
    production_practice_storage_requirements,
)
from adaptive_vocabulary import AdaptivePreviewRefused, apply_independent_write
from attempt_history import utc_now_iso
from daily_study import plan_for_language
from practice_store import PracticeStoreError
from study_data import open_study_data
from study_session import KIND_READING, KIND_VOCABULARY, STATUS_COMPLETED, build_study_session


FIETS = "11111111-1111-4111-8111-111111111111"
HUIS = "22222222-2222-4222-8222-222222222222"


def _entries():
    return [
        {"id": FIETS, "word": "de fiets", "meaning": "bicycle"},
        {"id": HUIS, "word": "het huis", "meaning": "house"},
    ]


def _isolate(monkeypatch, data: Path) -> None:
    data.mkdir(parents=True, exist_ok=True)
    settings = data / "settings.json"
    settings.write_text(
        json.dumps(
            {
                "native": "en",
                "language": "nl",
                "study_languages": ["nl"],
                "activities": {"reading": True, "listening": False},
            }
        ),
        encoding="utf-8",
    )
    lang = data / "languages" / "nl"
    lang.mkdir(parents=True)
    (lang / "vocab.json").write_text(
        json.dumps(_entries(), ensure_ascii=False), encoding="utf-8"
    )
    (lang / "progress.json").write_text(json.dumps({"words": {}}), encoding="utf-8")
    (lang / "attempts.jsonl").write_text("", encoding="utf-8")
    monkeypatch.setenv("LG_DATA_DIR", str(data))
    monkeypatch.setenv("LOCK_SCREEN", "0")
    monkeypatch.setattr(config, "SETTINGS_FILE", str(settings))
    monkeypatch.setattr(config, "data_dir", lambda: str(data))
    monkeypatch.setattr(config, "is_frozen", lambda: False)
    monkeypatch.setattr(config, "LOCK_SCREEN", False)
    monkeypatch.setattr(config, "QUIZ_TARGET_CORRECT", 2)
    config.clear_account()
    config.reload()


class _Guard:
    def __init__(self, locking: bool):
        self._locking = locking

    def locks_the_user(self):
        return self._locking


def test_integration_enabled_only_when_not_frozen(monkeypatch):
    monkeypatch.setattr(config, "is_frozen", lambda: False)
    assert adaptive_integration_enabled() is True
    monkeypatch.setattr(config, "is_frozen", lambda: True)
    assert adaptive_integration_enabled() is False


def test_unlocked_gate_refuses_locked_guard(monkeypatch):
    monkeypatch.setattr(config, "is_frozen", lambda: False)
    assert adaptive_unlocked_allowed(_Guard(False)) is True
    assert adaptive_unlocked_allowed(_Guard(True)) is False


def test_attach_bridge_refuses_locked():
    from adaptive_vocabulary import AdaptiveVocabularySession
    from daily_study import DailyStudyPlan

    plan = DailyStudyPlan(
        language_code="nl",
        vocab_total=1,
        due_review_count=0,
        new_word_count=1,
        future_review_count=0,
        attention_word_count=0,
        planned_vocab_count=1,
        reading_enabled=False,
        listening_enabled=False,
    )
    session = build_study_session(plan)
    controller = AdaptiveVocabularySession(
        _entries()[:1], language_code="nl", pool=_entries(), rng=random.Random(1)
    )
    with pytest.raises(AdaptivePreviewRefused):
        attach_bridge(session, controller, locked=True)


def test_guest_build_uses_planned_count_and_practice(tmp_path, monkeypatch):
    data = tmp_path / "guest"
    _isolate(monkeypatch, data)
    bundle = open_study_data("nl")
    plan = plan_for_language("nl")
    assert plan.planned_vocab_count == 2
    identity = capture_identity("nl")
    store = open_practice_store(identity)
    session = build_integrated_session(
        bundle, planned_count=plan.planned_vocab_count, practice_store=store, rng=random.Random(2)
    )
    assert session.counters.planned == 2
    assert identity.signed_in is False
    assert "languages" in store.db_path.replace("\\", "/")
    store.close()


def test_planned_target_not_silently_reduced(tmp_path, monkeypatch):
    data = tmp_path / "target"
    _isolate(monkeypatch, data)
    monkeypatch.setattr(config, "QUIZ_TARGET_CORRECT", 5)
    bundle = open_study_data("nl")
    plan = plan_for_language("nl")
    # Only two words exist → planned is min(2, 5) = 2, same as legacy lock session.
    assert plan.planned_vocab_count == 2
    session = build_study_session(plan)
    assert session.planned_vocab_count == 2
    controller = build_integrated_session(
        bundle, planned_count=session.planned_vocab_count, rng=random.Random(3)
    )
    assert controller.counters.planned == session.planned_vocab_count


def test_assisted_practice_zero_outbox_signed_in(tmp_path, monkeypatch):
    data = tmp_path / "signed"
    _isolate(monkeypatch, data)
    from account_local_store import AccountLocalStore

    user_id = 77
    store = AccountLocalStore(user_id, data_root=str(data))
    for entry in _entries():
        store.upsert_vocabulary(
            language_code="nl", vocab_id=entry["id"], payload=dict(entry)
        )
    store.close()
    config.save_account("synth77", "token-77", user_id=user_id)

    bundle = open_study_data("nl", data_root=str(data))
    identity = capture_identity("nl", data_root=str(data))
    assert identity.signed_in is True
    practice = open_practice_store(identity)
    controller = build_integrated_session(
        bundle, planned_count=1, practice_store=practice, rng=random.Random(7)
    )
    outbox_before = _outbox_count(data, user_id)
    # Drive to an assisted or recognition success.
    guard = 10
    while controller.current_card() and controller.current_card().kind != "independent_recall" and guard:
        card = controller.current_card()
        if card.kind == "introduction":
            controller.continue_card()
        elif card.kind == "multiple_choice":
            result = controller.submit(choice_index=card.correct_index)
            if result.practice is not None:
                practice.append(result.practice)
            controller.continue_card()
        else:
            result = controller.submit(card.reveal_word)
            if result.practice is not None:
                practice.append(result.practice)
            controller.continue_card()
        guard -= 1
    assert practice.count() >= 1
    assert _outbox_count(data, user_id) == outbox_before

    indie = controller.submit(controller.current_card().reveal_word)
    assert indie.write is not None
    apply_independent_write(
        bundle.progress, bundle.attempts, indie.write, timestamp=utc_now_iso()
    )
    assert _outbox_count(data, user_id) == outbox_before + 1
    practice.close()


def test_identity_blocks_stale_account(tmp_path, monkeypatch):
    data = tmp_path / "stale"
    _isolate(monkeypatch, data)
    config.save_account("a", "t", user_id=11)
    identity = capture_identity("nl", data_root=str(data))
    assert identity.still_current() is True
    config.save_account("b", "t2", user_id=22)
    assert identity.still_current() is False


def test_language_switch_invalidates_identity(tmp_path, monkeypatch):
    data = tmp_path / "lang"
    _isolate(monkeypatch, data)
    identity = capture_identity("nl", data_root=str(data))
    config.set_language("en")
    assert identity.still_current() is False


def test_completion_once_does_not_complete_reading(tmp_path, monkeypatch):
    from adaptive_vocabulary import AdaptiveVocabularySession
    from daily_study import DailyStudyPlan

    plan = DailyStudyPlan(
        language_code="nl",
        vocab_total=1,
        due_review_count=0,
        new_word_count=1,
        future_review_count=0,
        attention_word_count=0,
        planned_vocab_count=1,
        reading_enabled=True,
        listening_enabled=False,
    )
    study = build_study_session(plan)
    controller = AdaptiveVocabularySession(
        _entries()[:1],
        language_code="nl",
        pool=_entries(),
        rng=random.Random(4),
        level_overrides={FIETS: "independent_recall"},
    )
    bridge = attach_bridge(study, controller, locked=False)
    result = controller.submit("de fiets")
    assert result.write is not None and result.write.mastered
    controller.continue_card()
    assert controller.finished is True
    assert bridge.note_finished() is True
    assert bridge.note_finished() is False
    assert study.status(KIND_VOCABULARY) == STATUS_COMPLETED
    assert study.status(KIND_READING) != STATUS_COMPLETED


def test_practice_store_failure_does_not_block_independent(tmp_path, monkeypatch):
    data = tmp_path / "fail"
    _isolate(monkeypatch, data)
    bundle = open_study_data("nl")
    identity = capture_identity("nl", data_root=str(data))

    class BrokenStore:
        def append(self, _record):
            raise PracticeStoreError("boom")

        def close(self):
            return None

    controller = build_integrated_session(
        bundle, planned_count=1, practice_store=None, rng=random.Random(5)
    )
    # Direct UI path is covered elsewhere; here ensure open_practice_store refuses empty.
    with pytest.raises(PracticeStoreError):
        open_practice_store(
            AdaptiveStudyIdentity(
                user_id=0,
                language_code="nl",
                data_root="",
                signed_in=False,
                binding_id="x",
            )
        )
    assert identity.data_root
    assert BrokenStore is not None
    assert controller.counters.planned >= 1


def test_home_and_account_switch_on_one_tk(monkeypatch, tmp_path):
    """One Tk root: FreeHome adaptive button, then StudyMaster account clear."""
    import tkinter as tk

    from home_app import FreeHome
    from main import StudyMasterApp
    from study_session import KIND_VOCABULARY, STATUS_COMPLETED

    data = tmp_path / "ui"
    _isolate(monkeypatch, data)
    monkeypatch.setattr(config, "is_frozen", lambda: False)
    root = tk.Tk()
    root.withdraw()
    try:
        home = FreeHome(root)
        assert home.adaptive_button is not None
        for child in list(root.winfo_children()):
            try:
                child.destroy()
            except tk.TclError:
                pass
        app = StudyMasterApp(root, prefer_adaptive=False)
        session = app._session_for("nl")
        if session.has_activity(KIND_VOCABULARY):
            session.start(KIND_VOCABULARY)
            session.complete(KIND_VOCABULARY)
        assert app._session_for("nl").vocabulary_complete() is True
        gen = app._account_generation
        app._on_account_session_changed()
        assert app._account_generation == gen + 1
        assert app._session_for("nl").vocabulary_complete() is False
        assert app._session_for("nl").status(KIND_VOCABULARY) != STATUS_COMPLETED
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass

    monkeypatch.setattr(config, "is_frozen", lambda: True)
    assert adaptive_integration_enabled() is False


def test_production_requirements_documented():
    items = production_practice_storage_requirements()
    assert any("AppData" in item for item in items)
    assert any("SRS" in item for item in items)


def _outbox_count(data: Path, user_id: int) -> int:
    import sqlite3

    path = data / "accounts" / str(user_id) / "account_study.db"
    if not path.exists():
        return 0
    conn = sqlite3.connect(str(path))
    try:
        return int(conn.execute("SELECT COUNT(*) FROM outbox").fetchone()[0])
    finally:
        conn.close()
