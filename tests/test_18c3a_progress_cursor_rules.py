"""Synthetic coverage for ADR-022 progress cursor and snapshot rules.

Temporary databases only. No network and no Owner RC data.
"""

from __future__ import annotations

import pytest

from account_local_store import AccountLocalConflict, AccountLocalStore
from vocab_identity import new_vocab_id


def _event(store, event_id, vocab_id, *, verdict="exact"):
    mastered = 1 if verdict == "exact" else 0
    return {
        "event_id": event_id,
        "device_id": store.device_id(),
        "language_code": "nl",
        "vocab_id": vocab_id,
        "verdict": verdict,
        "mastered": mastered,
        "hint_used": 0,
        "occurred_at": "2026-01-01T00:00:00+00:00",
        "algorithm_id": "ladder-v2",
        "word_snapshot": "huis",
        "user_answer": "house",
        "expected_answer": "house",
        "prompt": "meaning",
    }


def _snapshot(version, seen, streak, event_id, *, due="2026-01-03T00:00:00+00:00"):
    return {
        "seen": seen,
        "correct": seen,
        "wrong": 0,
        "streak": streak,
        "interval_days": 1,
        "due_at": due,
        "state_version": version,
        "algorithm_id": "ladder-v2",
        "last_event_id": event_id,
        "last_server_seq": version,
    }


def _page(change_id, event, snapshot):
    return {"change_id": change_id, "event": event, "progress_after": snapshot}


@pytest.fixture
def store(tmp_path):
    account = AccountLocalStore(4, data_root=str(tmp_path))
    vocab_id = new_vocab_id()
    account.upsert_vocabulary(
        language_code="nl",
        vocab_id=vocab_id,
        payload={"word": "huis", "meaning": "house"},
    )
    yield account, vocab_id
    account.close()


def test_older_snapshot_does_not_regress_confirmed_and_advances_cursor(store):
    account, vocab_id = store
    newer = _event(account, "evt-new", vocab_id)
    older = _event(account, "evt-old", vocab_id, verdict="wrong")
    account.apply_progress_changes_page(
        [_page(1, newer, _snapshot(2, 5, 5, "evt-new"))],
        next_cursor=1,
        has_more=False,
    )
    account.apply_progress_changes_page(
        [_page(2, older, _snapshot(1, 1, 0, "evt-old"))],
        next_cursor=2,
        has_more=False,
    )
    confirmed = account.confirmed_progress("nl", vocab_id)
    assert int(confirmed["seen"]) == 5
    assert int(confirmed["streak"]) == 5
    assert int(confirmed["state_version"]) == 2
    assert account.cursors()["progress_cursor"] == 2
    ids = {row["event_id"] for row in account.list_attempts("nl")}
    assert ids == {"evt-new", "evt-old"}


def test_equal_version_mismatch_does_not_advance_cursor(store):
    account, vocab_id = store
    first = _event(account, "evt-a", vocab_id)
    clash = _event(account, "evt-b", vocab_id, verdict="wrong")
    account.apply_progress_changes_page(
        [_page(1, first, _snapshot(2, 5, 5, "evt-a"))],
        next_cursor=1,
        has_more=False,
    )
    with pytest.raises(AccountLocalConflict):
        account.apply_progress_changes_page(
            [_page(2, clash, _snapshot(2, 9, 9, "evt-b"))],
            next_cursor=2,
            has_more=False,
        )
    assert account.cursors()["progress_cursor"] == 1
    confirmed = account.confirmed_progress("nl", vocab_id)
    assert int(confirmed["seen"]) == 5
    assert int(confirmed["state_version"]) == 2
    assert "evt-b" not in {row["event_id"] for row in account.list_attempts("nl")}


def test_non_increasing_change_id_leaves_cursor(store):
    account, vocab_id = store
    event = _event(account, "evt-a", vocab_id)
    account.apply_progress_changes_page(
        [_page(3, event, _snapshot(1, 1, 1, "evt-a"))],
        next_cursor=3,
        has_more=False,
    )
    with pytest.raises(AccountLocalConflict):
        account.apply_progress_changes_page(
            [_page(3, event, _snapshot(1, 1, 1, "evt-a"))],
            next_cursor=3,
            has_more=False,
        )
    assert account.cursors()["progress_cursor"] == 3


def test_pending_attempt_survives_page_and_stays_in_provisional(store):
    account, vocab_id = store
    local_id = account.record_learning_attempt(
        language_code="nl",
        vocab_id=vocab_id,
        verdict="wrong",
        hint_used=False,
        word_snapshot="huis",
        user_answer="home",
        expected_answer="house",
        prompt="meaning",
    )
    remote = _event(account, "evt-remote", vocab_id)
    account.apply_progress_changes_page(
        [_page(1, remote, _snapshot(1, 1, 1, "evt-remote"))],
        next_cursor=1,
        has_more=False,
    )
    pending = [row["event_id"] for row in account.pending_outbox()]
    assert local_id in pending
    confirmed = account.confirmed_progress("nl", vocab_id)
    provisional = account.provisional_progress("nl", vocab_id)
    assert int(confirmed["seen"]) == 1
    assert int(confirmed["streak"]) == 1
    assert int(provisional["seen"]) == int(confirmed["seen"]) + 1
    assert int(provisional["streak"]) == 0
