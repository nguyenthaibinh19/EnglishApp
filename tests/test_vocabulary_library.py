"""Phase 12 — Vocabulary Library query/view-model tests (no Tk)."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta, timezone

import config
from attempt_history import LearningAttempt
from mistake_book import MistakeSummary, summarize_mistakes
from vocab_store import VocabStore
from vocabulary_library import (
    FILTER_ATTENTION,
    FILTER_DUE,
    FILTER_NEW,
    RECENT_ATTEMPT_LIMIT,
    attention_status_label,
    attempt_status_label,
    build_vocabulary_detail,
    build_vocabulary_items,
    due_status_label,
    filter_vocabulary_items,
    format_list_subtitle,
    load_vocabulary_library,
    mastery_rate_label,
    recent_attempts_for_word,
)

NOW = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)


def _attempt(
    word: str,
    *,
    ts: str,
    correct: bool = False,
    verdict: str = "wrong",
    hint_used: bool = False,
    language_code: str = "nl",
    user_answer: str = "x",
    expected: str = "word",
) -> LearningAttempt:
    return LearningAttempt(
        timestamp=ts,
        language_code=language_code,
        word=word,
        user_answer=user_answer,
        expected_answer=expected,
        correct=correct,
        verdict=verdict,
        hint_used=hint_used,
        prompt="p",
    )


def test_empty_vocabulary():
    items = build_vocabulary_items([], {}, [], now=NOW)
    assert items == []


def test_list_item_generation_and_order():
    vocab = [
        {"word": "zebra", "vi": "ngựa vằn"},
        {"word": "de fiets", "vi": "xe đạp"},
        {"word": "Het Huis", "vi": "ngôi nhà"},
    ]
    progress = {
        "de fiets": {
            "seen": 3,
            "correct": 2,
            "wrong": 1,
            "streak": 2,
            "due_at": "2026-09-01T00:00:00+00:00",
            "interval_days": 1,
        }
    }
    items = build_vocabulary_items(vocab, progress, [], now=NOW)
    assert [i.word for i in items] == ["de fiets", "Het Huis", "zebra"]
    assert items[0].store_index == 1
    assert items[0].seen == 3
    assert items[0].streak == 2
    assert items[0].is_due is True
    assert items[1].is_new is True
    assert items[1].is_due is False


def test_search_by_word_and_translation_and_unicode():
    vocab = [
        {"word": "café", "vi": "quán cà phê", "alt": ["cafe"]},
        {"word": "de trein", "vi": "tàu hỏa"},
    ]
    items = build_vocabulary_items(vocab, {}, [], now=NOW)
    by_word = filter_vocabulary_items(items, query="trein", vocab_entries=vocab)
    assert [i.word for i in by_word] == ["de trein"]
    by_vi = filter_vocabulary_items(items, query="cà phê", vocab_entries=vocab)
    assert [i.word for i in by_vi] == ["café"]
    # Accent-folded headword search
    by_fold = filter_vocabulary_items(items, query="cafe", vocab_entries=vocab)
    assert [i.word for i in by_fold] == ["café"]
    by_alt = filter_vocabulary_items(items, query="cafe", vocab_entries=vocab)
    assert len(by_alt) == 1


def test_new_due_future_and_attention_states():
    future = (NOW + timedelta(days=7)).isoformat()
    past = (NOW - timedelta(days=1)).isoformat()
    vocab = [
        {"word": "nieuw", "vi": "mới"},
        {"word": "due", "vi": "đến hạn"},
        {"word": "later", "vi": "sau"},
        {"word": "weak", "vi": "yếu"},
    ]
    progress = {
        "due": {
            "seen": 2,
            "correct": 1,
            "wrong": 1,
            "streak": 0,
            "due_at": past,
            "interval_days": 1,
        },
        "later": {
            "seen": 4,
            "correct": 4,
            "wrong": 0,
            "streak": 4,
            "due_at": future,
            "interval_days": 7,
        },
        "weak": {
            "seen": 3,
            "correct": 1,
            "wrong": 2,
            "streak": 0,
            "due_at": future,
            "interval_days": 1,
        },
    }
    summaries = [
        MistakeSummary(
            word="weak",
            prompt="yếu",
            attention_count=2,
            last_user_answer="x",
            expected_answer="weak",
            last_verdict="wrong",
            last_hint_used=False,
            last_timestamp=past,
            language_code="nl",
        )
    ]
    items = build_vocabulary_items(vocab, progress, summaries, now=NOW)
    by_key = {i.normalized_key: i for i in items}
    assert by_key["nieuw"].is_new and not by_key["nieuw"].is_due
    assert by_key["due"].is_due and not by_key["due"].is_new
    assert not by_key["later"].is_due and not by_key["later"].is_new
    assert by_key["weak"].needs_attention and by_key["weak"].attention_count == 2

    due_only = filter_vocabulary_items(items, filter_key=FILTER_DUE)
    assert {i.word for i in due_only} == {"due"}
    new_only = filter_vocabulary_items(items, filter_key=FILTER_NEW)
    assert {i.word for i in new_only} == {"nieuw"}
    attn = filter_vocabulary_items(items, filter_key=FILTER_ATTENTION)
    assert {i.word for i in attn} == {"weak"}


def test_due_and_attention_overlap():
    past = (NOW - timedelta(hours=1)).isoformat()
    vocab = [{"word": "huis", "vi": "nhà"}]
    progress = {
        "huis": {
            "seen": 5,
            "correct": 2,
            "wrong": 3,
            "streak": 0,
            "due_at": past,
            "interval_days": 1,
        }
    }
    summaries = [
        MistakeSummary(
            word="huis",
            prompt="nhà",
            attention_count=3,
            last_user_answer="x",
            expected_answer="huis",
            last_verdict="wrong",
            last_hint_used=False,
            last_timestamp=past,
            language_code="nl",
        )
    ]
    items = build_vocabulary_items(vocab, progress, summaries, now=NOW)
    assert items[0].is_due and items[0].needs_attention


def test_progress_fields_map_in_detail():
    entry = {"word": "fiets", "vi": "xe đạp", "alt": ["rijwiel"], "example": "Ik fiets."}
    progress = {
        "fiets": {
            "seen": 10,
            "correct": 7,
            "wrong": 3,
            "streak": 2,
            "due_at": "2026-10-10T00:00:00+00:00",
            "interval_days": 7,
        }
    }
    detail = build_vocabulary_detail(
        entry,
        0,
        language_code="nl",
        progress_words=progress,
        attempts=[],
        mistake_summaries=[],
        now=NOW,
    )
    assert detail.seen == 10
    assert detail.mastered_count == 7
    assert detail.non_mastered_count == 3
    assert detail.streak == 2
    assert detail.mastery_rate == 0.7
    assert detail.interval_days == 7
    assert detail.is_due is False
    assert detail.alt == ("rijwiel",)
    assert detail.example == "Ik fiets."
    assert detail.examples[0].text == "Ik fiets."


def test_recent_attempts_newest_first_and_limit():
    attempts = [
        _attempt("huis", ts=f"2026-09-{i:02d}T10:00:00+00:00", user_answer=str(i))
        for i in range(1, 12)
    ]
    recent = recent_attempts_for_word(attempts, "huis", limit=5)
    assert len(recent) == 5
    assert [a.user_answer for a in recent] == ["11", "10", "9", "8", "7"]

    detail = build_vocabulary_detail(
        {"word": "huis", "vi": "nhà"},
        0,
        language_code="nl",
        progress_words={},
        attempts=attempts,
        mistake_summaries=[],
        now=NOW,
        recent_limit=RECENT_ATTEMPT_LIMIT,
    )
    assert len(detail.recent_attempts) == RECENT_ATTEMPT_LIMIT
    assert detail.recent_attempts[0].user_answer == "11"


def test_languages_isolated_via_loader(tmp_path, monkeypatch):
    nl_dir = tmp_path / "nl"
    en_dir = tmp_path / "en"
    nl_dir.mkdir()
    en_dir.mkdir()
    (nl_dir / "vocab.json").write_text(
        json.dumps([{"word": "fiets", "vi": "xe đạp"}]), encoding="utf-8"
    )
    (en_dir / "vocab.json").write_text(
        json.dumps([{"word": "bike", "vi": "xe đạp"}]), encoding="utf-8"
    )
    (nl_dir / "progress.json").write_text("{}", encoding="utf-8")
    (en_dir / "progress.json").write_text("{}", encoding="utf-8")
    (nl_dir / "attempts.jsonl").write_text("", encoding="utf-8")
    (en_dir / "attempts.jsonl").write_text("", encoding="utf-8")

    monkeypatch.setattr(config, "vocab_path", lambda code=None: str((tmp_path / (code or "nl")) / "vocab.json"))
    monkeypatch.setattr(
        config, "progress_path", lambda code=None: str((tmp_path / (code or "nl")) / "progress.json")
    )
    monkeypatch.setattr(
        config, "attempts_path", lambda code=None: str((tmp_path / (code or "nl")) / "attempts.jsonl")
    )

    nl_items, *_ = load_vocabulary_library("nl", now=NOW)
    en_items, *_ = load_vocabulary_library("en", now=NOW)
    assert [i.word for i in nl_items] == ["fiets"]
    assert [i.word for i in en_items] == ["bike"]


def test_build_does_not_mutate_inputs():
    vocab = [{"word": "a", "vi": "b"}]
    progress = {"a": {"seen": 1, "correct": 1, "wrong": 0, "streak": 1}}
    summaries = []
    vocab_before = copy.deepcopy(vocab)
    progress_before = copy.deepcopy(progress)
    build_vocabulary_items(vocab, progress, summaries, now=NOW)
    filter_vocabulary_items(
        build_vocabulary_items(vocab, progress, summaries, now=NOW),
        query="a",
        vocab_entries=vocab,
    )
    assert vocab == vocab_before
    assert progress == progress_before


def test_deleted_history_only_words_absent_from_library():
    vocab = [{"word": "alive", "vi": "sống"}]
    progress = {
        "alive": {"seen": 1, "correct": 1, "wrong": 0, "streak": 1},
        "ghost": {
            "seen": 4,
            "correct": 0,
            "wrong": 4,
            "streak": 0,
            "due_at": "2026-09-01T00:00:00+00:00",
        },
    }
    attempts = [_attempt("ghost", ts="2026-09-01T00:00:00+00:00")]
    summaries = summarize_mistakes(attempts, language_code="nl")
    items = build_vocabulary_items(vocab, progress, summaries, now=NOW)
    assert [i.word for i in items] == ["alive"]
    assert all(i.word != "ghost" for i in items)


def test_presentation_helpers(monkeypatch):
    monkeypatch.setattr(config, "native_code", lambda: "en")

    class _D:
        is_new = False
        is_due = True
        due_at = None

    assert "Due" in due_status_label(_D())

    class _New:
        is_new = True
        is_due = False
        due_at = None

    assert "Not studied" in due_status_label(_New())

    class _Future:
        is_new = False
        is_due = False
        due_at = "2026-10-14T00:00:00+00:00"

    assert "Next review: 2026-10-14" in due_status_label(_Future())

    assert "Needs attention" in attention_status_label(True, 3)
    assert "No attention" in attention_status_label(False, 0)
    assert "No mastery" in mastery_rate_label(None, 0)
    assert "Mastered" in mastery_rate_label(0.5, 2)

    mastered = _attempt("w", ts="t", correct=True, verdict="exact")
    hinted = _attempt("w", ts="t", correct=False, verdict="exact", hint_used=True)
    near = _attempt("w", ts="t", correct=False, verdict="near")
    wrong = _attempt("w", ts="t", correct=False, verdict="wrong")
    assert attempt_status_label(mastered) == "Mastered"
    assert "hint" in attempt_status_label(hinted).lower()
    assert "Almost" in attempt_status_label(near)
    assert attempt_status_label(wrong) == "Wrong"

    item = build_vocabulary_items(
        [{"word": "x", "vi": "y"}],
        {},
        [
            MistakeSummary(
                word="x",
                prompt="y",
                attention_count=1,
                last_user_answer="a",
                expected_answer="x",
                last_verdict="wrong",
                last_hint_used=False,
                last_timestamp="t",
                language_code="nl",
            )
        ],
        now=NOW,
    )[0]
    subtitle = format_list_subtitle(item)
    assert "new" in subtitle
    assert "needs attention" in subtitle


def test_store_index_preserved_for_safe_edit(tmp_path):
    path = tmp_path / "vocab.json"
    path.write_text(
        json.dumps(
            [
                {"word": "beta", "vi": "b"},
                {"word": "alpha", "vi": "a"},
            ]
        ),
        encoding="utf-8",
    )
    store = VocabStore(str(path))
    items = build_vocabulary_items(store.all(), {}, [], now=NOW)
    # Alphabetical: alpha then beta, but store_index must point at real rows.
    assert items[0].word == "alpha" and items[0].store_index == 1
    assert items[1].word == "beta" and items[1].store_index == 0
    assert store.update(items[0].store_index, "alpha", "a2")
    assert store.get(1)["meaning"] == "a2"
