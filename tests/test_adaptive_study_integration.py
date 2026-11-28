"""Phase 19.4C — Home/StudyMaster adaptive integration closeout checks."""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import config
import pytest
from adaptive_study import (
    AdaptiveStudyIdentity,
    PracticeAvailability,
    adaptive_integration_enabled,
    adaptive_unlocked_allowed,
    attach_bridge,
    build_integrated_session,
    capture_identity,
    open_practice_availability,
    open_practice_store,
    production_practice_storage_requirements,
    select_due_new_entries,
)
from adaptive_vocabulary import AdaptivePreviewRefused, apply_independent_write
from attempt_history import utc_now_iso
from daily_study import DailyStudyPlan, plan_for_language
from practice_store import PracticeStoreError
from study_data import open_study_data
from study_session import (
    KIND_LISTENING,
    KIND_READING,
    KIND_VOCABULARY,
    STATUS_COMPLETED,
    STATUS_PENDING,
    build_study_session,
)


FIETS = "11111111-1111-4111-8111-111111111111"
HUIS = "22222222-2222-4222-8222-222222222222"
BOEK = "33333333-3333-4333-8333-333333333333"
WATER = "44444444-4444-4444-8444-444444444444"
INVALID = "not-a-uuid"


def _entries(n=2):
    base = [
        {"id": FIETS, "word": "de fiets", "meaning": "bicycle"},
        {"id": HUIS, "word": "het huis", "meaning": "house"},
        {"id": BOEK, "word": "het boek", "meaning": "book"},
        {"id": WATER, "word": "het water", "meaning": "water"},
    ]
    return base[:n]


def _isolate(monkeypatch, data: Path, *, adaptive: bool = True) -> None:
    data.mkdir(parents=True, exist_ok=True)
    settings = data / "settings.json"
    settings.write_text(
        json.dumps(
            {
                "native": "en",
                "language": "nl",
                "study_languages": ["nl"],
                "activities": {"reading": True, "listening": True},
            }
        ),
        encoding="utf-8",
    )
    lang = data / "languages" / "nl"
    lang.mkdir(parents=True)
    (lang / "vocab.json").write_text(
        json.dumps(_entries(2), ensure_ascii=False), encoding="utf-8"
    )
    (lang / "progress.json").write_text(json.dumps({"words": {}}), encoding="utf-8")
    (lang / "attempts.jsonl").write_text("", encoding="utf-8")
    monkeypatch.setenv("LG_DATA_DIR", str(data))
    if adaptive:
        monkeypatch.setenv("LG_ADAPTIVE_STUDY", "1")
    else:
        monkeypatch.delenv("LG_ADAPTIVE_STUDY", raising=False)
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


def test_integration_requires_opt_in_and_isolated_root(monkeypatch, tmp_path):
    data = tmp_path / "opt"
    _isolate(monkeypatch, data, adaptive=False)
    assert adaptive_integration_enabled() is False
    monkeypatch.setenv("LG_ADAPTIVE_STUDY", "1")
    assert adaptive_integration_enabled() is True
    monkeypatch.setattr(config, "is_frozen", lambda: True)
    assert adaptive_integration_enabled() is False


def test_unlocked_gate_refuses_locked_guard(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path / "lock")
    assert adaptive_unlocked_allowed(_Guard(False)) is True
    assert adaptive_unlocked_allowed(_Guard(True)) is False


def test_attach_bridge_refuses_locked():
    from adaptive_vocabulary import AdaptiveVocabularySession

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


def test_incomplete_target_refuses_smaller_plan(tmp_path, monkeypatch):
    data = tmp_path / "short"
    _isolate(monkeypatch, data)
    # Ten vocab rows; seven are future reviews; three remain due/new.
    words = []
    progress_words = {}
    now = datetime.now(timezone.utc)
    future = (now + timedelta(days=30)).isoformat()
    for index in range(10):
        vid = f"{index:08x}-1111-4111-8111-111111111111"
        words.append({"id": vid, "word": f"woord{index}", "meaning": f"m{index}"})
        if index >= 3:
            progress_words[vid] = {
                "seen": 3,
                "correct": 3,
                "wrong": 0,
                "streak": 3,
                "interval_days": 30,
                "due_at": future,
                "ease": 2.5,
            }
    lang = data / "languages" / "nl"
    (lang / "vocab.json").write_text(json.dumps(words), encoding="utf-8")
    (lang / "progress.json").write_text(
        json.dumps({"words": progress_words}), encoding="utf-8"
    )
    monkeypatch.setattr(config, "QUIZ_TARGET_CORRECT", 10)
    bundle = open_study_data("nl")
    plan = plan_for_language("nl")
    assert plan.planned_vocab_count == 10
    built = build_integrated_session(
        bundle, planned_count=plan.planned_vocab_count, rng=random.Random(1)
    )
    assert built.ok is False
    assert built.required_count == 10
    assert built.selected_count == 3
    assert built.refusal_reason == "insufficient_eligible_words"
    assert built.session is None


def test_duplicate_and_invalid_ids_do_not_pad_target(tmp_path, monkeypatch):
    data = tmp_path / "dup"
    _isolate(monkeypatch, data)
    rows = [
        {"id": FIETS, "word": "de fiets", "meaning": "bicycle"},
        {"id": FIETS, "word": "de fiets", "meaning": "bicycle copy"},
        {"id": INVALID, "word": "broken", "meaning": "x"},
        {"id": HUIS, "word": "het huis", "meaning": "house"},
    ]
    lang = data / "languages" / "nl"
    (lang / "vocab.json").write_text(json.dumps(rows), encoding="utf-8")
    bundle = open_study_data("nl")
    # Deduped due/new set cannot invent rows to meet a larger required target.
    built = build_integrated_session(
        bundle, planned_count=4, rng=random.Random(2)
    )
    assert built.ok is False
    assert built.selected_count < 4
    assert built.refusal_reason == "insufficient_eligible_words"


def test_guest_build_matches_planned_count(tmp_path, monkeypatch):
    data = tmp_path / "guest"
    _isolate(monkeypatch, data)
    bundle = open_study_data("nl")
    plan = plan_for_language("nl")
    assert plan.planned_vocab_count == 2
    identity = capture_identity("nl")
    store = open_practice_store(identity)
    built = build_integrated_session(
        bundle,
        planned_count=plan.planned_vocab_count,
        practice_store=store,
        rng=random.Random(2),
    )
    assert built.ok is True
    assert built.session.counters.planned == 2
    store.close()


def test_practice_init_failure_is_unavailable_not_saved(tmp_path, monkeypatch):
    data = tmp_path / "failstore"
    _isolate(monkeypatch, data)
    identity = AdaptiveStudyIdentity(
        user_id=0,
        language_code="nl",
        data_root="",
        signed_in=False,
        binding_id="x",
        account_generation=0,
    )
    availability = open_practice_availability(identity)
    assert availability.unavailable is True
    assert availability.store is None

    bundle = open_study_data("nl")
    built = build_integrated_session(
        bundle,
        planned_count=2,
        practice=PracticeAvailability(status="unavailable", detail="boom"),
        rng=random.Random(3),
    )
    assert built.ok is True
    assert built.practice.unavailable is True


def test_assisted_practice_zero_outbox_signed_in(tmp_path, monkeypatch):
    data = tmp_path / "signed"
    _isolate(monkeypatch, data)
    from account_local_store import AccountLocalStore

    user_id = 77
    store = AccountLocalStore(user_id, data_root=str(data))
    for entry in _entries(2):
        store.upsert_vocabulary(
            language_code="nl", vocab_id=entry["id"], payload=dict(entry)
        )
    store.close()
    config.save_account("synth77", "token-77", user_id=user_id)

    bundle = open_study_data("nl", data_root=str(data))
    identity = capture_identity("nl", data_root=str(data))
    practice = open_practice_store(identity)
    built = build_integrated_session(
        bundle, planned_count=1, practice_store=practice, rng=random.Random(7)
    )
    assert built.ok
    controller = built.session
    outbox_before = _outbox_count(data, user_id)
    guard = 10
    while (
        controller.current_card()
        and controller.current_card().kind != "independent_recall"
        and guard
    ):
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


def test_identity_generation_blocks_a_to_b_to_a(tmp_path, monkeypatch):
    data = tmp_path / "stale"
    _isolate(monkeypatch, data)
    config.save_account("a", "t", user_id=11)
    identity = capture_identity("nl", data_root=str(data), account_generation=1)
    assert identity.still_current(account_generation=1) is True
    config.save_account("b", "t2", user_id=22)
    assert identity.still_current(account_generation=2) is False
    config.save_account("a", "t3", user_id=11)
    # Same account id again, but generation advanced — still stale.
    assert identity.still_current(account_generation=3) is False


def test_completion_leaves_reading_and_listening_pending():
    from adaptive_vocabulary import AdaptiveVocabularySession

    plan = DailyStudyPlan(
        language_code="nl",
        vocab_total=1,
        due_review_count=0,
        new_word_count=1,
        future_review_count=0,
        attention_word_count=0,
        planned_vocab_count=1,
        reading_enabled=True,
        listening_enabled=True,
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
    assert study.status(KIND_READING) == STATUS_PENDING
    assert study.status(KIND_LISTENING) == STATUS_PENDING
    nxt = study.next_activity()
    assert nxt is not None and nxt.kind == KIND_READING


def test_home_and_studymaster_lifecycle_on_one_tk(monkeypatch, tmp_path):
    """One Tk root: Home dispatch, lift-on-repeat, stale callback, account clear, next activity."""
    import tkinter as tk

    from home_app import FreeHome
    from main import StudyMasterApp

    data = tmp_path / "ui"
    _isolate(monkeypatch, data)
    captured = {}

    class FakeStudyMaster:
        def __init__(self, root, on_finished=None, prefer_adaptive: bool = False):
            captured["prefer_adaptive"] = prefer_adaptive
            captured["on_finished"] = on_finished

    root = tk.Tk()
    root.withdraw()
    opened = {}
    try:
        home = FreeHome(root)
        assert home.adaptive_button is not None
        home._study_master_class = staticmethod(lambda: FakeStudyMaster)
        home._close_bank = lambda: None
        home._close_mistake_book = lambda: None
        home._invalidate_owned_callbacks = lambda: None
        home._stop_sync_status_polling = lambda: None
        home.refresh = lambda: None
        home._start_adaptive_study()
        assert captured["prefer_adaptive"] is True
        home._start_study()
        assert captured["prefer_adaptive"] is False

        for child in list(root.winfo_children()):
            try:
                child.destroy()
            except tk.TclError:
                pass

        app = StudyMasterApp(root, prefer_adaptive=False)
        child = tk.Toplevel(root)
        app.vocab_window = child
        app._vocab_binding_language = "nl"
        assert app._lift_vocab_window_if_same("nl") is True
        assert child.winfo_exists()
        app._activate("en")
        assert app.vocab_window is None
        app._activate("nl")

        session = app._session_for("nl")
        if session.has_activity(KIND_VOCABULARY):
            session.start(KIND_VOCABULARY)
        gen = app._account_generation
        app._account_generation = gen + 1
        app._deliver_vocab_completed(gen, "nl")
        assert app._session_for("nl").vocabulary_complete() is False

        session = app._session_for("nl")
        if session.has_activity(KIND_VOCABULARY) and session.status(KIND_VOCABULARY) == STATUS_PENDING:
            session.start(KIND_VOCABULARY)
        app.open_reading_section = lambda code=None: opened.setdefault(
            "reading", code or "nl"
        )
        app.open_listening_section = lambda code=None: opened.setdefault(
            "listening", code or "nl"
        )
        app._deliver_vocab_completed(app._account_generation, "nl")
        assert app._session_for("nl").vocabulary_complete() is True
        assert app._session_for("nl").status(KIND_READING) == STATUS_PENDING
        root.update()
        root.after(250, root.quit)
        root.mainloop()
        assert opened.get("reading") == "nl"
        assert "listening" not in opened

        gen2 = app._account_generation
        app._on_account_session_changed()
        assert app._account_generation == gen2 + 1
        assert app._session_for("nl").vocabulary_complete() is False
        assert app._vocab_binding_language is None
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass


def test_production_requirements_documented():
    items = production_practice_storage_requirements()
    assert any("AppData" in item for item in items)
    assert any("opt-in" in item.lower() or "LG_ADAPTIVE" in item for item in items)


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
