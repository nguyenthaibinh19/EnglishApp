"""ADR-022 guest AttemptHistory ledger. Temporary databases and files only."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import timedelta

import pytest

from account_local_store import (
    LEGACY_DISP_IMPORTED,
    LEGACY_DISP_OVERLAP,
    LEGACY_DISP_SKIPPED,
    LEGACY_DISP_SKIPPED_OVERLAP,
    LEGACY_DISP_UNREADABLE,
    STATUS_CONFLICT,
    AccountLocalError,
    AccountLocalStore,
)
from attempt_history import AttemptHistory, LearningAttempt
from legacy_attempt_import import (
    LegacySourceIdentityError,
    import_attempt_bytes,
    import_guest_attempts,
    read_windows_attempt_source,
    read_windows_file_identity,
)
from srs import parse_utc, to_utc_iso
from vocab_identity import new_vocab_id


def _store(tmp_path, user_id=1):
    return AccountLocalStore(user_id, data_root=str(tmp_path))


def _line(vocab_id, **overrides) -> bytes:
    body = {
        "timestamp": "2020-01-01T00:00:00+00:00",
        "language_code": "nl",
        "word": "huis",
        "user_answer": "house",
        "expected_answer": "house",
        "correct": True,
        "verdict": "exact",
        "hint_used": False,
        "prompt": "meaning",
        "vocab_id": vocab_id,
    }
    body.update(overrides)
    return (json.dumps(body, ensure_ascii=False) + "\n").encode("utf-8")


def _import(store, data, identity="vol:a", resolutions=None):
    store.grant_attempt_import_consent("nl", identity)
    return import_attempt_bytes(
        store,
        language_code="nl",
        canonical_path="attempts.jsonl",
        file_identity=identity,
        data=data,
        resolutions=resolutions,
    )


def test_consent_is_required_and_accounts_are_isolated(tmp_path):
    vocab_id = new_vocab_id()
    data = _line(vocab_id)
    account_a = _store(tmp_path, 1)
    account_b = _store(tmp_path, 2)
    blocked = import_attempt_bytes(
        account_a,
        language_code="nl",
        canonical_path="attempts.jsonl",
        file_identity="vol:a",
        data=data,
    )
    assert blocked["status"] == "consent_required"
    assert account_a.legacy_attempt_ledger() == []
    account_a.grant_legacy_consent("nl", "guest", note="vocab-only")
    still_blocked = import_attempt_bytes(
        account_a,
        language_code="nl",
        canonical_path="attempts.jsonl",
        file_identity="vol:a",
        data=data,
    )
    assert still_blocked["status"] == "consent_required"
    imported = _import(account_a, data)
    assert imported["imported"] == 1
    other = import_attempt_bytes(
        account_b,
        language_code="nl",
        canonical_path="attempts.jsonl",
        file_identity="vol:a",
        data=data,
    )
    assert other["status"] == "consent_required"
    assert account_b.list_attempts("nl") == []
    assert len(account_a.list_attempts("nl")) == 1
    account_a.close()
    account_b.close()


def test_source_file_bytes_stay_unchanged(tmp_path):
    vocab_id = new_vocab_id()
    path = tmp_path / "attempts.jsonl"
    payload = _line(vocab_id)
    path.write_bytes(payload)
    before = path.read_bytes()
    store = _store(tmp_path)
    store.grant_attempt_import_consent("nl", "vol:file")
    result = import_guest_attempts(
        store,
        language_code="nl",
        path=str(path),
        identity_reader=lambda _path: "vol:file",
    )
    assert result["imported"] == 1
    assert path.read_bytes() == before
    store.close()


def test_identical_lines_at_different_offsets_are_distinct(tmp_path):
    vocab_id = new_vocab_id()
    data = _line(vocab_id) + _line(vocab_id)
    store = _store(tmp_path)
    result = _import(store, data)
    assert result["imported"] == 2
    rows = store.legacy_attempt_ledger("vol:a")
    assert [row["offset"] for row in rows] == [0, len(_line(vocab_id))]
    assert rows[0]["line_sha256"] == rows[1]["line_sha256"]
    assert rows[0]["event_id"] != rows[1]["event_id"]
    assert len(store.pending_outbox()) == 2
    store.close()


def test_second_import_reuses_event_ids(tmp_path):
    vocab_id = new_vocab_id()
    data = _line(vocab_id)
    store = _store(tmp_path)
    _import(store, data)
    first_ids = [row["event_id"] for row in store.legacy_attempt_ledger()]
    again = _import(store, data)
    assert again["imported"] == 0
    assert [row["event_id"] for row in store.legacy_attempt_ledger()] == first_ids
    assert len(store.pending_outbox()) == 1
    store.close()


def test_failure_before_commit_leaves_no_partial_row(tmp_path):
    vocab_id = new_vocab_id()
    store = _store(tmp_path)
    local_id = store.record_learning_attempt(
        language_code="nl",
        vocab_id=vocab_id,
        verdict="wrong",
        hint_used=False,
        word_snapshot="huis",
        user_answer="home",
        expected_answer="house",
        prompt="meaning",
    )
    before = [row["event_id"] for row in store.pending_outbox()]
    store.grant_attempt_import_consent("nl", "vol:a")
    store._legacy_import_fail_before_commit = True
    with pytest.raises(AccountLocalError):
        import_attempt_bytes(
            store,
            language_code="nl",
            canonical_path="attempts.jsonl",
            file_identity="vol:a",
            data=_line(vocab_id),
        )
    assert store.legacy_attempt_ledger() == []
    assert store.legacy_attempt_high_water("nl", "vol:a") == 0
    assert [row["event_id"] for row in store.pending_outbox()] == before
    assert local_id in before
    confirmed = store.confirmed_progress("nl", vocab_id)
    assert confirmed is None
    store.close()


def test_partial_final_line_is_not_ledgered(tmp_path):
    vocab_id = new_vocab_id()
    complete = _line(vocab_id)
    data = complete + b'{"timestamp":"2020-01-02T00:00:00+00:00"'
    store = _store(tmp_path)
    result = _import(store, data)
    assert result["imported"] == 1
    rows = store.legacy_attempt_ledger()
    assert len(rows) == 1
    assert rows[0]["offset"] == 0
    assert store.legacy_attempt_high_water("nl", "vol:a") == len(complete)
    store.close()


def test_invalid_json_and_missing_vocab_id_are_not_uploaded(tmp_path):
    vocab_id = new_vocab_id()
    spelled = new_vocab_id()
    store = _store(tmp_path)
    store.upsert_vocabulary(
        language_code="nl",
        vocab_id=spelled,
        payload={"word": "huis", "meaning": "house"},
    )
    missing = _line("", word="huis")
    invalid_id = _line("not-a-uuid")
    bad_json = b"not-json\n"
    inconsistent = _line(vocab_id, correct=False, verdict="exact")
    data = bad_json + missing + invalid_id + inconsistent + _line(vocab_id)
    result = _import(store, data)
    assert result["imported"] == 1
    rows = store.legacy_attempt_ledger()
    assert [row["disposition"] for row in rows] == [
        LEGACY_DISP_UNREADABLE,
        LEGACY_DISP_SKIPPED,
        LEGACY_DISP_SKIPPED,
        LEGACY_DISP_UNREADABLE,
        LEGACY_DISP_IMPORTED,
    ]
    attempts = store.list_attempts("nl")
    assert len(attempts) == 1
    assert attempts[0]["vocab_id"] == vocab_id
    assert attempts[0]["occurred_at"] == "2020-01-01T00:00:00+00:00"
    assert attempts[0]["source"] == "legacy_import"
    progress = [row for row in store.pending_outbox() if row["kind"] == "progress"]
    assert len(progress) == 1
    store.close()


def test_replacement_requires_fresh_consent_and_keeps_old_events(tmp_path):
    vocab_id = new_vocab_id()
    data = _line(vocab_id)
    store = _store(tmp_path)
    _import(store, data, identity="vol:old")
    original = store.list_attempts("nl")[0]["event_id"]
    replaced = import_attempt_bytes(
        store,
        language_code="nl",
        canonical_path="attempts.jsonl",
        file_identity="vol:new",
        data=data,
    )
    assert replaced["status"] == "replacement_consent_required"
    assert store.status().status == STATUS_CONFLICT
    assert [row["event_id"] for row in store.list_attempts("nl")] == [original]
    store.grant_attempt_import_consent("nl", "vol:new")
    waiting = import_attempt_bytes(
        store,
        language_code="nl",
        canonical_path="attempts.jsonl",
        file_identity="vol:new",
        data=data,
    )
    assert waiting["status"] == "overlap"
    assert waiting["imported"] == 0
    assert len(store.pending_outbox()) == 1
    assert store.legacy_attempt_ledger("vol:new")[0]["disposition"] == LEGACY_DISP_OVERLAP
    store.close()


def test_truncation_and_changed_line_keep_accepted_events(tmp_path):
    vocab_id = new_vocab_id()
    first = _line(vocab_id)
    second = _line(
        vocab_id,
        timestamp="2020-01-02T00:00:00+00:00",
        user_answer="home",
        correct=False,
        verdict="wrong",
    )
    store = _store(tmp_path)
    _import(store, first + second)
    ids = {row["event_id"] for row in store.list_attempts("nl")}
    shortened = import_attempt_bytes(
        store,
        language_code="nl",
        canonical_path="attempts.jsonl",
        file_identity="vol:a",
        data=first,
    )
    assert shortened["reason"] == "truncation"
    assert {row["event_id"] for row in store.list_attempts("nl")} == ids
    restored = _import(store, first + second)
    assert restored["imported"] == 0
    changed = first.replace(b"house", b"homes") + second
    conflict = import_attempt_bytes(
        store,
        language_code="nl",
        canonical_path="attempts.jsonl",
        file_identity="vol:a",
        data=changed,
    )
    assert conflict["reason"] == "source_conflict"
    assert {row["event_id"] for row in store.list_attempts("nl")} == ids
    assert store.legacy_attempt_ledger()[0]["disposition"] == "source_conflict"
    assert len(store.pending_outbox()) == 2
    store.close()


def test_overlap_skip_and_distinct_are_explicit(tmp_path):
    vocab_id = new_vocab_id()
    original = _line(vocab_id)
    unique = _line(new_vocab_id(), timestamp="2020-02-01T00:00:00+00:00", word="boom")
    skip_store = _store(tmp_path, 3)
    _import(skip_store, original, identity="vol:old")
    skip_store.grant_attempt_import_consent("nl", "vol:new")
    held = import_attempt_bytes(
        skip_store,
        language_code="nl",
        canonical_path="attempts.jsonl",
        file_identity="vol:new",
        data=original + unique,
    )
    assert held["status"] == "overlap"
    assert held["imported"] == 0
    assert len(skip_store.legacy_attempt_ledger("vol:new")) == 1
    assert len(skip_store.pending_outbox()) == 1
    skipped = import_attempt_bytes(
        skip_store,
        language_code="nl",
        canonical_path="attempts.jsonl",
        file_identity="vol:new",
        data=original + unique,
        resolutions={0: "skip"},
    )
    assert skipped["imported"] == 1
    overlap_row = skip_store.legacy_attempt_ledger("vol:new")[0]
    assert overlap_row["disposition"] == LEGACY_DISP_SKIPPED_OVERLAP
    assert overlap_row["event_id"] is None
    assert len(skip_store.pending_outbox()) == 2
    skip_store.close()

    distinct_store = _store(tmp_path, 4)
    _import(distinct_store, original, identity="vol:old")
    original_id = distinct_store.list_attempts("nl")[0]["event_id"]
    distinct_store.grant_attempt_import_consent("nl", "vol:new")
    imported = import_attempt_bytes(
        distinct_store,
        language_code="nl",
        canonical_path="attempts.jsonl",
        file_identity="vol:new",
        data=original,
        resolutions={0: "distinct"},
    )
    assert imported["imported"] == 1
    ids = {row["event_id"] for row in distinct_store.list_attempts("nl")}
    assert original_id in ids
    assert len(ids) == 2
    assert len(distinct_store.pending_outbox()) == 2
    distinct_store.close()


def test_imported_event_and_outbox_commit_together(tmp_path):
    vocab_id = new_vocab_id()
    store = _store(tmp_path)
    _import(store, _line(vocab_id))
    ledger = store.legacy_attempt_ledger()
    attempts = store.list_attempts("nl")
    pending = store.pending_outbox()
    assert ledger[0]["event_id"] == attempts[0]["event_id"] == pending[0]["event_id"]
    assert store.confirmed_progress("nl", vocab_id) is None
    store.close()


def test_guest_writer_and_signed_in_answer_stay_independent(tmp_path):
    guest_path = tmp_path / "guest-attempts.jsonl"
    history = AttemptHistory(str(guest_path), language_code="nl")
    history.record(
        LearningAttempt(
            timestamp="2020-01-01T00:00:00+00:00",
            language_code="nl",
            word="huis",
            user_answer="house",
            expected_answer="house",
            correct=True,
            verdict="exact",
            hint_used=False,
            prompt="meaning",
            vocab_id=new_vocab_id(),
        )
    )
    store = _store(tmp_path)
    local_id = store.record_learning_attempt(
        language_code="nl",
        vocab_id=new_vocab_id(),
        verdict="exact",
        hint_used=False,
        word_snapshot="boom",
        user_answer="tree",
        expected_answer="tree",
        prompt="meaning",
    )
    assert store.legacy_attempt_ledger() == []
    assert store.list_attempts("nl")[0]["source"] == "local"
    assert store.list_attempts("nl")[0]["event_id"] == local_id
    assert b"boom" not in guest_path.read_bytes()
    store.close()


def _seed_confirmed(store, vocab_id, *, due="2026-06-01T00:00:00+00:00"):
    event = {
        "event_id": "evt-seed",
        "device_id": store.device_id(),
        "language_code": "nl",
        "vocab_id": vocab_id,
        "verdict": "exact",
        "mastered": 1,
        "hint_used": 0,
        "occurred_at": "2026-05-01T00:00:00+00:00",
        "algorithm_id": "ladder-v2",
        "word_snapshot": "huis",
        "user_answer": "house",
        "expected_answer": "house",
        "prompt": "meaning",
    }
    snapshot = {
        "seen": 4,
        "correct": 4,
        "wrong": 0,
        "streak": 2,
        "interval_days": 3,
        "due_at": due,
        "state_version": 3,
        "algorithm_id": "ladder-v2",
        "last_event_id": "evt-seed",
        "last_server_seq": 3,
    }
    store.apply_progress_changes_page(
        [{"change_id": 1, "event": event, "progress_after": snapshot}],
        next_cursor=1,
        has_more=False,
    )


def _due_after(created_at: str, days: int) -> str:
    return to_utc_iso(parse_utc(created_at) + timedelta(days=days))


def test_historical_and_future_imports_keep_evidence_and_confirmed(tmp_path):
    past_id = new_vocab_id()
    future_id = new_vocab_id()
    past_at = "2024-01-15T08:00:00+00:00"
    future_at = "2099-01-15T08:00:00+00:00"
    store = _store(tmp_path)
    _seed_confirmed(store, past_id)
    confirmed_before = store.confirmed_progress("nl", past_id)
    result = _import(
        store,
        _line(past_id, timestamp=past_at, user_answer="home", correct=False, verdict="wrong")
        + _line(future_id, timestamp=future_at),
    )
    assert result["imported"] == 2
    again = _import(
        store,
        _line(past_id, timestamp=past_at, user_answer="home", correct=False, verdict="wrong")
        + _line(future_id, timestamp=future_at),
    )
    assert again["imported"] == 0
    by_stamp = {row["occurred_at"]: row for row in store.list_attempts("nl")}
    assert by_stamp[past_at]["vocab_id"] == past_id
    assert by_stamp[past_at]["source"] == "legacy_import"
    assert by_stamp[future_at]["vocab_id"] == future_id
    assert len(store.list_attempts("nl")) == 3
    progress = [row for row in store.pending_outbox() if row["kind"] == "progress"]
    assert len(progress) == 2
    by_vocab = {row["vocab_id"]: row for row in progress}
    past_due = store.provisional_progress("nl", past_id)["due_at"]
    future_due = store.provisional_progress("nl", future_id)["due_at"]
    assert past_due == by_vocab[past_id]["created_at"]
    assert future_due == _due_after(by_vocab[future_id]["created_at"], 1)
    assert past_due != past_at
    assert "2099" not in future_due
    assert store.confirmed_progress("nl", past_id) == confirmed_before
    assert store.confirmed_progress("nl", future_id) is None
    assert past_id in store.account_day_buckets("nl")["2024-01-15"]["asked"]
    mistakes = {row["vocab_id"] for row in store.mistake_book_entries("nl")}
    assert past_id in mistakes
    store.close()


def test_import_follows_outbox_order_ahead_of_historical_time(tmp_path):
    vocab_id = new_vocab_id()
    store = _store(tmp_path)
    _seed_confirmed(store, vocab_id, due="2026-07-01T00:00:00+00:00")
    local_id = store.record_learning_attempt(
        language_code="nl",
        vocab_id=vocab_id,
        verdict="wrong",
        hint_used=False,
        word_snapshot="huis",
        user_answer="home",
        expected_answer="house",
        prompt="meaning",
        occurred_at="2026-11-22T10:00:00+00:00",
    )
    imported = _import(store, _line(vocab_id, timestamp="2020-01-01T00:00:00+00:00"))
    assert imported["imported"] == 1
    provisional = store.provisional_progress("nl", vocab_id)
    progress = [row for row in store.pending_outbox() if row["kind"] == "progress"]
    import_row = next(row for row in progress if row["event_id"] != local_id)
    assert int(provisional["seen"]) == 6
    assert int(provisional["streak"]) == 1
    assert provisional["due_at"] == _due_after(import_row["created_at"], 1)
    confirmed = store.confirmed_progress("nl", vocab_id)
    assert int(confirmed["seen"]) == 4
    assert confirmed["due_at"] == "2026-07-01T00:00:00+00:00"
    assert {row["event_id"] for row in progress} == {local_id, import_row["event_id"]}
    stored = next(row for row in store.list_attempts("nl") if row["event_id"] == import_row["event_id"])
    assert stored["occurred_at"] == "2020-01-01T00:00:00+00:00"
    store.close()


def test_local_attempt_still_schedules_from_its_own_occurred_at(tmp_path):
    vocab_id = new_vocab_id()
    store = _store(tmp_path)
    store.record_learning_attempt(
        language_code="nl",
        vocab_id=vocab_id,
        verdict="exact",
        hint_used=False,
        word_snapshot="huis",
        user_answer="house",
        expected_answer="house",
        prompt="meaning",
        occurred_at="2024-06-01T00:00:00+00:00",
    )
    provisional = store.provisional_progress("nl", vocab_id)
    assert provisional["due_at"] == "2024-06-02T00:00:00+00:00"
    assert store.confirmed_progress("nl", vocab_id) is None
    store.close()


def test_server_ack_reconciles_from_received_at_without_duplicating(tmp_path):
    vocab_id = new_vocab_id()
    historical = "2020-03-01T00:00:00+00:00"
    received_at = "2026-11-22T12:00:00+00:00"
    server_due = "2026-11-23T12:00:00+00:00"
    store = _store(tmp_path)
    _import(store, _line(vocab_id, timestamp=historical))
    event_id = store.legacy_attempt_ledger()[0]["event_id"]
    event = next(row for row in store.list_attempts("nl") if row["event_id"] == event_id)
    store.acknowledge_progress_upload(
        event_id,
        {
            "event": {
                "event_id": event_id,
                "device_id": event["device_id"],
                "language_code": "nl",
                "vocab_id": vocab_id,
                "verdict": "exact",
                "mastered": 1,
                "hint_used": 0,
                "occurred_at": historical,
                "received_at": received_at,
                "server_seq": 8,
                "algorithm_id": "ladder-v2",
                "word_snapshot": event["word_snapshot"],
                "user_answer": event["user_answer"],
                "expected_answer": event["expected_answer"],
                "prompt": event["prompt"],
            },
            "progress_after": {
                "seen": 1,
                "correct": 1,
                "wrong": 0,
                "streak": 1,
                "interval_days": 1,
                "due_at": server_due,
                "state_version": 1,
                "algorithm_id": "ladder-v2",
                "last_event_id": event_id,
                "last_server_seq": 8,
            },
        },
    )
    stored = next(row for row in store.list_attempts("nl") if row["event_id"] == event_id)
    assert stored["occurred_at"] == historical
    assert stored["received_at"] == received_at
    confirmed = store.confirmed_progress("nl", vocab_id)
    assert confirmed["due_at"] == server_due
    assert int(confirmed["seen"]) == 1
    assert store.pending_outbox() == []
    retry = _import(store, _line(vocab_id, timestamp=historical))
    assert retry["imported"] == 0
    assert len(store.list_attempts("nl")) == 1
    assert store.confirmed_progress("nl", vocab_id)["due_at"] == server_due
    assert store.legacy_attempt_ledger()[0]["event_id"] == event_id
    store.close()


def _conflict_rows(store):
    with store._lock:
        rows = store._conn.execute(
            "SELECT kind, detail, resolved FROM sync_conflicts ORDER BY id"
        ).fetchall()
    return [(row["kind"], row["detail"], int(row["resolved"])) for row in rows]


def test_verified_import_resolves_only_its_identity_conflict(tmp_path):
    path = tmp_path / "attempts.jsonl"
    path.write_bytes(_line(new_vocab_id()))
    store = _store(tmp_path)

    def _fail(_path):
        raise LegacySourceIdentityError("Windows file identity is unavailable.")

    failed = import_guest_attempts(
        store,
        language_code="nl",
        path=str(path),
        identity_reader=_fail,
    )
    assert failed["status"] == "identity_unavailable"
    assert ("legacy_attempt", "identity_unavailable nl", 0) in _conflict_rows(store)
    store.note_legacy_attempt_conflict("identity_unavailable en")
    store.note_legacy_attempt_conflict("overlap en")
    unread = import_guest_attempts(
        store,
        language_code="nl",
        path=str(path),
        identity_reader=lambda _path: "vol:recovered",
    )
    assert unread["status"] == "consent_required"
    assert ("legacy_attempt", "identity_unavailable nl", 0) in _conflict_rows(store)
    store.grant_attempt_import_consent("nl", "vol:recovered")
    recovered = import_guest_attempts(
        store,
        language_code="nl",
        path=str(path),
        identity_reader=lambda _path: "vol:recovered",
    )
    assert recovered["status"] == "ok"
    assert recovered["imported"] == 1
    rows = _conflict_rows(store)
    assert ("legacy_attempt", "identity_unavailable nl", 1) in rows
    assert ("legacy_attempt", "identity_unavailable en", 0) in rows
    assert ("legacy_attempt", "overlap en", 0) in rows
    store.close()


def test_invalid_replacement_line_is_not_imported_as_distinct(tmp_path):
    vocab_id = new_vocab_id()
    missing = _line("", word="huis")
    broken = b"not-json\n"
    valid = _line(vocab_id, timestamp="2021-06-01T00:00:00+00:00", word="boom")
    store = _store(tmp_path)
    first = _import(store, missing + broken, identity="vol:old")
    assert first["imported"] == 0
    assert [row for row in store.pending_outbox() if row["kind"] == "progress"] == []
    store.grant_attempt_import_consent("nl", "vol:new")
    replaced = import_attempt_bytes(
        store,
        language_code="nl",
        canonical_path="attempts.jsonl",
        file_identity="vol:new",
        data=missing + broken + valid,
        resolutions={0: "distinct", len(missing): "distinct"},
    )
    assert replaced["status"] == "ok"
    assert replaced["imported"] == 1
    progress = [row for row in store.pending_outbox() if row["kind"] == "progress"]
    assert len(progress) == 1
    new_rows = store.legacy_attempt_ledger("vol:new")
    assert [row["disposition"] for row in new_rows] == [
        LEGACY_DISP_SKIPPED,
        LEGACY_DISP_UNREADABLE,
        LEGACY_DISP_IMPORTED,
    ]
    assert new_rows[0]["event_id"] is None
    assert new_rows[1]["event_id"] is None
    assert new_rows[2]["event_id"] == progress[0]["event_id"]
    old_rows = store.legacy_attempt_ledger("vol:old")
    assert [row["event_id"] for row in old_rows] == [None, None]
    store.close()


def test_windows_file_identity_is_stable_across_append(tmp_path):
    if os.name != "nt":
        pytest.skip("Windows file identity")
    first = tmp_path / "attempts.jsonl"
    second = tmp_path / "other.jsonl"
    first.write_bytes(b'{"ok":true}\n')
    second.write_bytes(b'{"ok":true}\n')
    identity, data = read_windows_attempt_source(str(first))
    assert identity == read_windows_file_identity(str(first))
    assert identity.startswith("win:")
    assert data == first.read_bytes()
    other, _other_data = read_windows_attempt_source(str(second))
    assert other.startswith("win:")
    assert other != identity
    with first.open("ab") as handle:
        handle.write(b'{"ok":false}\n')
    appended, appended_data = read_windows_attempt_source(str(first))
    assert appended == identity
    assert appended_data == first.read_bytes()


def test_server_incompatible_lines_never_enter_the_outbox(tmp_path):
    vocab_id = new_vocab_id()
    valid = _line(vocab_id, timestamp="2021-05-01T00:00:00+00:00", word="boom")
    rejected = [
        _line(vocab_id, timestamp="not-a-timestamp"),
        _line(vocab_id, user_answer="x" * 501),
        _line(vocab_id, expected_answer=""),
        _line(vocab_id, hint_used="false"),
    ]
    store = _store(tmp_path)
    result = _import(store, b"".join(rejected) + valid)
    assert result["imported"] == 1
    rows = store.legacy_attempt_ledger()
    assert [row["disposition"] for row in rows[:4]] == [LEGACY_DISP_UNREADABLE] * 4
    assert all(row["event_id"] is None for row in rows[:4])
    progress = [row for row in store.pending_outbox() if row["kind"] == "progress"]
    assert len(progress) == 1
    assert len(store.list_attempts("nl")) == 1
    assert store.list_attempts("nl")[0]["occurred_at"] == "2021-05-01T00:00:00+00:00"
    store.close()


def test_windows_ancestor_junction_file_fails_closed(tmp_path):
    if os.name != "nt":
        pytest.skip("Windows file identity")
    target = tmp_path / "real"
    link = tmp_path / "junction"
    target.mkdir()
    (target / "attempts.jsonl").write_bytes(b'{"ok":true}\n')
    subprocess.check_call(["cmd", "/c", "mklink", "/J", str(link), str(target)])
    aliased = link / "attempts.jsonl"
    assert aliased.is_file()
    with pytest.raises(LegacySourceIdentityError):
        read_windows_attempt_source(str(aliased))


def test_windows_file_symlink_fails_closed(tmp_path):
    if os.name != "nt":
        pytest.skip("Windows file identity")
    target = tmp_path / "real.jsonl"
    link = tmp_path / "attempts.jsonl"
    target.write_bytes(b'{"ok":true}\n')
    try:
        os.symlink(target, link)
    except OSError:
        pytest.skip("file symlink creation not permitted")
    with pytest.raises(LegacySourceIdentityError):
        read_windows_attempt_source(str(link))
