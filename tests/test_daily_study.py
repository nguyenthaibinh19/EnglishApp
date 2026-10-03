"""Daily Study Planner — category counts and planned workload."""

from __future__ import annotations

import copy
import json
from datetime import date, datetime, timedelta, timezone

from attempt_history import AttemptHistory, LearningAttempt
from daily_study import build_daily_study_plan, format_plan_preview_lines, plan_for_language
from mistake_book import MistakeSummary, summarize_mistakes
from progress import Progress
from scheduler import compute_weight
from srs import is_due, is_future, is_new, to_utc_iso
from vocab_store import VocabStore

NOW = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)


def _summary(word: str) -> MistakeSummary:
    return MistakeSummary(
        word=word,
        prompt="",
        attention_count=1,
        last_user_answer="x",
        expected_answer=word,
        last_verdict="wrong",
        last_hint_used=False,
        last_timestamp="2026-10-01T12:00:00+00:00",
        language_code="nl",
    )


def test_empty_vocabulary():
    plan = build_daily_study_plan(
        "nl",
        [],
        {},
        [],
        quiz_target=5,
        reading_enabled=True,
        now=NOW,
    )
    assert plan.vocab_total == 0
    assert plan.planned_vocab_count == 0
    assert plan.due_review_count == 0
    assert plan.new_word_count == 0


def test_all_new_vocabulary():
    vocab = [{"word": "a", "vi": "1"}, {"word": "b", "vi": "2"}]
    plan = build_daily_study_plan(
        "nl", vocab, {}, [], quiz_target=5, reading_enabled=False, now=NOW
    )
    assert plan.new_word_count == 2
    assert plan.due_review_count == 0
    assert plan.future_review_count == 0
    assert plan.planned_vocab_count == 2
    assert plan.reading_enabled is False


def test_one_due_word():
    vocab = [{"word": "huis", "vi": "nhà"}]
    words = {
        "huis": {
            "seen": 2,
            "correct": 1,
            "wrong": 1,
            "streak": 0,
            "due_at": to_utc_iso(NOW),
            "interval_days": 0,
        }
    }
    plan = build_daily_study_plan(
        "nl", vocab, words, [], quiz_target=5, reading_enabled=True, now=NOW
    )
    assert plan.due_review_count == 1
    assert plan.new_word_count == 0
    assert plan.future_review_count == 0


def test_future_not_counted_as_due():
    vocab = [{"word": "trein", "vi": "tàu"}]
    words = {
        "trein": {
            "seen": 3,
            "correct": 3,
            "wrong": 0,
            "streak": 3,
            "due_at": to_utc_iso(NOW + timedelta(days=7)),
            "interval_days": 7,
        }
    }
    plan = build_daily_study_plan(
        "nl", vocab, words, [], quiz_target=5, reading_enabled=True, now=NOW
    )
    assert plan.due_review_count == 0
    assert plan.future_review_count == 1
    assert plan.planned_vocab_count == 1  # target still respected for session


def test_legacy_seen_without_due_at_counts_as_due():
    vocab = [{"word": "alpha", "vi": "a"}]
    words = {
        "alpha": {
            "seen": 4,
            "correct": 4,
            "wrong": 0,
            "streak": 4,
            "last_seen": "2026-09-01T10:00:00",
        }
    }
    plan = build_daily_study_plan(
        "nl", vocab, words, [], quiz_target=5, reading_enabled=True, now=NOW
    )
    assert is_due(words["alpha"], NOW) is True
    assert plan.due_review_count == 1
    assert plan.future_review_count == 0


def test_mixed_due_new_future():
    vocab = [
        {"word": "new1", "vi": "n"},
        {"word": "due1", "vi": "d"},
        {"word": "future1", "vi": "f"},
    ]
    words = {
        "due1": {
            "seen": 1,
            "correct": 0,
            "wrong": 1,
            "streak": 0,
            "due_at": to_utc_iso(NOW - timedelta(days=1)),
            "interval_days": 0,
        },
        "future1": {
            "seen": 2,
            "correct": 2,
            "wrong": 0,
            "streak": 2,
            "due_at": to_utc_iso(NOW + timedelta(days=3)),
            "interval_days": 3,
        },
    }
    plan = build_daily_study_plan(
        "de", vocab, words, [], quiz_target=5, reading_enabled=True, now=NOW
    )
    assert plan.new_word_count == 1
    assert plan.due_review_count == 1
    assert plan.future_review_count == 1
    assert plan.vocab_total == 3


def test_attention_overlap_does_not_double_planned():
    vocab = [{"word": "huis", "vi": "nhà"}, {"word": "fiets", "vi": "xe"}]
    words = {
        "huis": {
            "seen": 2,
            "correct": 0,
            "wrong": 2,
            "streak": 0,
            "due_at": to_utc_iso(NOW),
            "interval_days": 0,
        },
    }
    mistakes = [_summary("huis"), _summary("ghost")]
    plan = build_daily_study_plan(
        "nl", vocab, words, mistakes, quiz_target=5, reading_enabled=True, now=NOW
    )
    assert plan.due_review_count == 1
    assert plan.attention_word_count == 2
    assert plan.planned_vocab_count == 2  # not 1+2


def test_attention_follows_phase6(tmp_path):
    history = AttemptHistory(str(tmp_path / "a.jsonl"), language_code="nl")
    history.record(
        LearningAttempt(
            timestamp="2026-10-01T10:00:00+00:00",
            language_code="nl",
            word="kat",
            user_answer="dog",
            expected_answer="kat",
            correct=False,
            verdict="wrong",
        )
    )
    history.record(
        LearningAttempt(
            timestamp="2026-10-01T11:00:00+00:00",
            language_code="nl",
            word="kat",
            user_answer="kat",
            expected_answer="kat",
            correct=True,
            verdict="exact",
        )
    )
    summaries = summarize_mistakes(history.load_attempts(), "nl")
    plan = build_daily_study_plan(
        "nl",
        [{"word": "kat", "vi": "mèo"}],
        {},
        summaries,
        quiz_target=5,
        reading_enabled=True,
        now=NOW,
    )
    assert plan.attention_word_count == 0


def test_languages_isolated():
    nl = build_daily_study_plan(
        "nl",
        [{"word": "fiets", "vi": "xe"}],
        {},
        [_summary("fiets")],
        quiz_target=5,
        reading_enabled=True,
        now=NOW,
    )
    de = build_daily_study_plan(
        "de",
        [{"word": "Hund", "vi": "chó"}],
        {
            "hund": {
                "seen": 1,
                "correct": 1,
                "wrong": 0,
                "streak": 1,
                "due_at": to_utc_iso(NOW + timedelta(days=1)),
                "interval_days": 1,
            }
        },
        [],
        quiz_target=5,
        reading_enabled=False,
        now=NOW,
    )
    assert nl.language_code == "nl" and nl.new_word_count == 1
    assert de.language_code == "de" and de.future_review_count == 1
    assert de.reading_enabled is False


def test_plan_construction_performs_no_writes(tmp_path):
    vocab = tmp_path / "vocab.json"
    progress_path = tmp_path / "progress.json"
    attempts = tmp_path / "attempts.jsonl"
    # Pre-assign stable id so VocabStore load does not need an identity rewrite.
    vocab.write_text(
        json.dumps(
            [{"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "word": "a", "vi": "1"}]
        ),
        encoding="utf-8",
    )
    progress_path.write_text(
        json.dumps(
            {
                "version": 3,
                "identity": "vocab_id",
                "words": {},
                "days": {},
                "legacy_index": {"a": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"},
            }
        ),
        encoding="utf-8",
    )
    before_v = vocab.read_text(encoding="utf-8")
    before_p = progress_path.read_text(encoding="utf-8")
    assert not attempts.exists()
    store = VocabStore(str(vocab))
    progress = Progress(str(progress_path))
    snapshot = copy.deepcopy(progress.data)
    plan = plan_for_language(
        "nl",
        now=NOW,
        quiz_target=5,
        reading_enabled=True,
        vocab_store=store,
        progress=progress,
        attempts_filename=str(attempts),
    )
    assert plan.new_word_count == 1
    assert progress.data == snapshot
    assert vocab.read_text(encoding="utf-8") == before_v
    assert progress_path.read_text(encoding="utf-8") == before_p
    assert not attempts.exists()


def test_target_respected_and_capped_by_vocab_size():
    many = [{"word": f"w{i}", "vi": str(i)} for i in range(40)]
    plan = build_daily_study_plan(
        "nl", many, {}, [], quiz_target=5, reading_enabled=True, now=NOW
    )
    assert plan.due_review_count == 0
    assert plan.new_word_count == 40
    assert plan.planned_vocab_count == 5

    few = [{"word": "only", "vi": "1"}]
    plan2 = build_daily_study_plan(
        "nl", few, {}, [], quiz_target=5, reading_enabled=True, now=NOW
    )
    assert plan2.planned_vocab_count == 1


def test_no_due_reported_even_when_session_has_fallback():
    vocab = [{"word": "a", "vi": "1"}, {"word": "b", "vi": "2"}]
    words = {
        "a": {
            "seen": 1,
            "correct": 1,
            "wrong": 0,
            "streak": 1,
            "due_at": to_utc_iso(NOW + timedelta(days=5)),
            "interval_days": 1,
        },
        "b": {
            "seen": 1,
            "correct": 1,
            "wrong": 0,
            "streak": 1,
            "due_at": to_utc_iso(NOW + timedelta(days=5)),
            "interval_days": 1,
        },
    }
    plan = build_daily_study_plan(
        "nl", vocab, words, [], quiz_target=5, reading_enabled=True, now=NOW
    )
    assert plan.due_review_count == 0
    assert plan.future_review_count == 2
    assert plan.planned_vocab_count == 2
    lines = format_plan_preview_lines(plan, "Dutch")
    assert any("Nothing due" in line or "Chưa có từ đến hạn" in line for line in lines)


def test_reading_enabled_flag():
    plan_on = build_daily_study_plan(
        "nl", [], {}, [], quiz_target=5, reading_enabled=True, now=NOW
    )
    plan_off = build_daily_study_plan(
        "nl", [], {}, [], quiz_target=5, reading_enabled=False, now=NOW
    )
    assert plan_on.reading_enabled is True
    assert plan_off.reading_enabled is False


def test_naive_and_aware_last_seen_weights():
    today = date(2026, 10, 1)
    naive = {
        "seen": 5,
        "correct": 5,
        "wrong": 0,
        "streak": 2,
        "last_seen": "2026-09-20T10:00:00",
    }
    aware = {
        "seen": 5,
        "correct": 5,
        "wrong": 0,
        "streak": 2,
        "last_seen": "2026-09-20T10:00:00+00:00",
    }
    w_naive = compute_weight(naive, today)
    w_aware = compute_weight(aware, today)
    assert w_naive == w_aware
    assert w_naive > 0.15


def test_is_new_is_future_helpers():
    assert is_new(None) is True
    assert is_new({"seen": 0}) is True
    future_stats = {
        "seen": 1,
        "due_at": to_utc_iso(NOW + timedelta(days=2)),
        "interval_days": 1,
    }
    assert is_future(future_stats, NOW) is True
    assert is_due(future_stats, NOW) is False
