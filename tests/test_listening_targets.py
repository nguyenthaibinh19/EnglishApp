"""Phase 17C — Listening target selection."""

from __future__ import annotations

import json
from pathlib import Path

from listening_source import select_listening_targets
from mistake_book import MistakeSummary
from progress import Progress
from vocab_store import VocabStore


def _store(tmp_path: Path, rows) -> VocabStore:
    path = tmp_path / "vocab.json"
    path.write_text(json.dumps(rows), encoding="utf-8")
    return VocabStore(str(path))


def _progress(tmp_path: Path, data: dict) -> Progress:
    path = tmp_path / "progress.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return Progress(str(path))


def test_today_studied_then_mistakes_then_weak_then_fill(tmp_path: Path):
    store = _store(
        tmp_path,
        [
            {"id": "11111111-1111-1111-1111-111111111111", "word": "trein", "meaning": "train"},
            {"id": "22222222-2222-2222-2222-222222222222", "word": "station", "meaning": "station"},
            {"id": "33333333-3333-3333-3333-333333333333", "word": "kaart", "meaning": "ticket"},
            {"id": "44444444-4444-4444-4444-444444444444", "word": "huis", "meaning": "house"},
        ],
    )
    progress = _progress(
        tmp_path,
        {
            "version": 3,
            "identity": "studyguard-progress",
            "words": {
                "33333333-3333-3333-3333-333333333333": {
                    "seen": 10,
                    "correct": 1,
                    "wrong": 9,
                    "streak": 0,
                },
                "44444444-4444-4444-4444-444444444444": {
                    "seen": 2,
                    "correct": 2,
                    "wrong": 0,
                    "streak": 1,
                },
            },
            "days": {},
        },
    )
    from progress import today_key

    progress.data["days"][today_key()] = {
        "asked": ["11111111-1111-1111-1111-111111111111"],
        "correct": [],
        "wrong": [],
        "reading_done": False,
    }
    progress.save()

    mistakes = [
        MistakeSummary(
            word="station",
            prompt="",
            attention_count=2,
            last_user_answer="",
            expected_answer="",
            last_verdict="wrong",
            last_hint_used=False,
            last_timestamp="2026-01-01T00:00:00",
            language_code="nl",
            vocab_id="22222222-2222-2222-2222-222222222222",
        ),
        MistakeSummary(
            word="gone",
            prompt="",
            attention_count=1,
            last_user_answer="",
            expected_answer="",
            last_verdict="wrong",
            last_hint_used=False,
            last_timestamp="2026-01-01T00:00:00",
            language_code="nl",
            vocab_id="99999999-9999-9999-9999-999999999999",
        ),
    ]
    chosen = select_listening_targets(
        store, progress, language_code="nl", mistake_summaries=mistakes, count=2
    )
    assert len(chosen) == 2
    assert chosen[0]["id"] == "11111111-1111-1111-1111-111111111111"
    assert chosen[1]["id"] == "22222222-2222-2222-2222-222222222222"


def test_no_duplicates_and_max_two(tmp_path: Path):
    store = _store(
        tmp_path,
        [
            {"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "word": "one", "meaning": "1"},
            {"id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", "word": "two", "meaning": "2"},
            {"id": "cccccccc-cccc-cccc-cccc-cccccccccccc", "word": "three", "meaning": "3"},
        ],
    )
    progress = _progress(
        tmp_path,
        {"version": 3, "identity": "studyguard-progress", "words": {}, "days": {}},
    )
    chosen = select_listening_targets(store, progress, language_code="en", count=2)
    assert len(chosen) == 2
    ids = [row["id"] for row in chosen]
    assert len(set(ids)) == 2


def test_legacy_word_key_compatibility(tmp_path: Path):
    store = _store(
        tmp_path,
        [
            {"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "word": "fiets", "meaning": "bike"},
            {"id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", "word": "auto", "meaning": "car"},
        ],
    )
    progress = _progress(
        tmp_path,
        {
            "version": 3,
            "identity": "studyguard-progress",
            "words": {},
            "days": {},
        },
    )
    from progress import today_key

    progress.data["days"][today_key()] = {
        "asked": ["fiets"],
        "correct": [],
        "wrong": [],
        "reading_done": False,
    }
    progress.save()
    chosen = select_listening_targets(store, progress, language_code="nl", count=1)
    assert chosen[0]["word"] == "fiets"
