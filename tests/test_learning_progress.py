"""Phase 16 — Learning Progress read-only query layer."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

from attempt_history import LearningAttempt
from learning_progress import (
    attempt_local_date,
    build_day_activity,
    build_learning_progress,
    load_learning_progress,
    practiced_word_count,
)
from mistake_book import MistakeSummary, summarize_mistakes
from progress import Progress
from srs import to_utc_iso
from vocab_store import VocabStore

NOW = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
TODAY = date(2026, 10, 1)
TZ = timezone.utc


def _attempt(
    word: str,
    *,
    correct: bool,
    timestamp: str,
    vocab_id: str = "",
    hint_used: bool = False,
    verdict: str = "",
    language_code: str = "nl",
) -> LearningAttempt:
    if not verdict:
        verdict = "exact" if correct else "wrong"
    return LearningAttempt(
        timestamp=timestamp,
        language_code=language_code,
        word=word,
        user_answer="x",
        expected_answer=word,
        correct=correct,
        verdict=verdict,
        hint_used=hint_used,
        prompt="p",
        vocab_id=vocab_id,
    )


def _summary(word: str, vocab_id: str = "") -> MistakeSummary:
    return MistakeSummary(
        word=word,
        prompt="p",
        attention_count=1,
        last_user_answer="x",
        expected_answer=word,
        last_verdict="wrong",
        last_hint_used=False,
        last_timestamp=to_utc_iso(NOW),
        language_code="nl",
        vocab_id=vocab_id,
    )


def test_empty_vocabulary():
    snap = build_learning_progress("nl", [], {}, [], [], now=NOW, today_local=TODAY, local_tz=TZ)
    assert snap.vocab_total == 0
    assert snap.practiced_word_count == 0
    assert snap.new_word_count == 0
    assert snap.due_review_count == 0
    assert snap.future_review_count == 0
    assert snap.attention_word_count == 0
    assert snap.total_attempt_count == 0
    assert snap.mastery_attempt_rate is None


def test_unpracticed_and_practiced_counts():
    vocab = [
        {"id": "11111111-1111-4111-8111-111111111111", "word": "nieuw", "meaning": "new"},
        {"id": "22222222-2222-4222-8222-222222222222", "word": "oud", "meaning": "old"},
    ]
    words = {
        "22222222-2222-4222-8222-222222222222": {
            "seen": 2,
            "correct": 1,
            "wrong": 1,
            "streak": 0,
            "due_at": to_utc_iso(NOW),
            "interval_days": 0,
        }
    }
    snap = build_learning_progress(
        "nl", vocab, words, [], [], now=NOW, today_local=TODAY, local_tz=TZ
    )
    assert snap.vocab_total == 2
    assert snap.new_word_count == 1
    assert snap.practiced_word_count == 1
    assert snap.due_review_count == 1
    assert snap.future_review_count == 0
    assert practiced_word_count(vocab, words) == 1


def test_due_future_attention_and_overlap():
    vocab = [
        {"id": "11111111-1111-4111-8111-111111111111", "word": "a", "meaning": "1"},
        {"id": "22222222-2222-4222-8222-222222222222", "word": "b", "meaning": "2"},
        {"id": "33333333-3333-4333-8333-333333333333", "word": "c", "meaning": "3"},
    ]
    words = {
        "22222222-2222-4222-8222-222222222222": {
            "seen": 1,
            "correct": 0,
            "wrong": 1,
            "streak": 0,
            "due_at": to_utc_iso(NOW - timedelta(days=1)),
            "interval_days": 0,
        },
        "33333333-3333-4333-8333-333333333333": {
            "seen": 3,
            "correct": 3,
            "wrong": 0,
            "streak": 3,
            "due_at": to_utc_iso(NOW + timedelta(days=5)),
            "interval_days": 7,
        },
    }
    summaries = [_summary("b", "22222222-2222-4222-8222-222222222222")]
    snap = build_learning_progress(
        "nl", vocab, words, [], summaries, now=NOW, today_local=TODAY, local_tz=TZ
    )
    assert snap.new_word_count == 1
    assert snap.due_review_count == 1
    assert snap.future_review_count == 1
    assert snap.attention_word_count == 1
    assert snap.new_word_count + snap.due_review_count + snap.future_review_count == snap.vocab_total


def test_deleted_vocabulary_excluded_from_current_counts():
    vocab = [{"id": "11111111-1111-4111-8111-111111111111", "word": "keep", "meaning": "k"}]
    words = {
        "11111111-1111-4111-8111-111111111111": {
            "seen": 1,
            "correct": 1,
            "wrong": 0,
            "streak": 1,
            "due_at": to_utc_iso(NOW + timedelta(days=1)),
            "interval_days": 1,
        },
        "99999999-9999-4999-8999-999999999999": {
            "seen": 5,
            "correct": 5,
            "wrong": 0,
            "streak": 5,
            "due_at": to_utc_iso(NOW),
            "interval_days": 30,
        },
    }
    orphan_attempts = [
        _attempt(
            "gone",
            correct=False,
            timestamp=to_utc_iso(NOW),
            vocab_id="99999999-9999-4999-8999-999999999999",
        )
    ]
    summaries = summarize_mistakes(orphan_attempts, language_code="nl")
    snap = build_learning_progress(
        "nl",
        vocab,
        words,
        orphan_attempts,
        summaries,
        now=NOW,
        today_local=TODAY,
        local_tz=TZ,
    )
    assert snap.vocab_total == 1
    assert snap.practiced_word_count == 1
    assert snap.due_review_count == 0
    assert snap.future_review_count == 1
    # Orphan history still counts in attempt analytics / attention.
    assert snap.total_attempt_count == 1
    assert snap.attention_word_count == 1


def test_legacy_attempts_without_vocab_id_count_in_activity():
    attempts = [
        _attempt("huis", correct=True, timestamp=to_utc_iso(NOW), vocab_id=""),
        _attempt(
            "huis",
            correct=False,
            timestamp=to_utc_iso(NOW - timedelta(hours=1)),
            vocab_id="",
            verdict="near",
        ),
    ]
    snap = build_learning_progress(
        "nl",
        [{"word": "huis", "meaning": "house"}],
        {},
        attempts,
        [],
        now=NOW,
        today_local=TODAY,
        local_tz=TZ,
    )
    assert snap.total_attempt_count == 2
    assert snap.mastery_attempt_count == 1
    assert snap.non_mastery_attempt_count == 1


def test_mastery_attempt_semantics_hint_and_near():
    attempts = [
        _attempt("a", correct=True, timestamp=to_utc_iso(NOW), verdict="exact"),
        _attempt(
            "a",
            correct=False,
            timestamp=to_utc_iso(NOW),
            verdict="exact",
            hint_used=True,
        ),
        _attempt("a", correct=False, timestamp=to_utc_iso(NOW), verdict="near"),
    ]
    snap = build_learning_progress(
        "nl", [], {}, attempts, [], now=NOW, today_local=TODAY, local_tz=TZ
    )
    assert snap.mastery_attempt_count == 1
    assert snap.non_mastery_attempt_count == 2
    assert snap.mastery_attempt_rate == 1 / 3


def test_zero_attempt_rate_is_none_not_zero():
    snap = build_learning_progress("nl", [], {}, [], [], now=NOW, today_local=TODAY, local_tz=TZ)
    assert snap.mastery_attempt_rate is None


def test_seven_day_grouping_and_day_boundary():
    # Local day grouping with a fixed UTC+2 offset (no tz database required).
    local = timezone(timedelta(hours=2))
    # 2026-10-01 00:30 +02:00 = 2026-09-30 22:30 UTC → local date 2026-10-01
    morning_local = datetime(2026, 10, 1, 0, 30, tzinfo=local).astimezone(timezone.utc)
    prev = datetime(2026, 9, 30, 12, 0, tzinfo=local).astimezone(timezone.utc)
    attempts = [
        _attempt("a", correct=True, timestamp=to_utc_iso(morning_local)),
        _attempt("b", correct=False, timestamp=to_utc_iso(prev)),
        _attempt("c", correct=True, timestamp=to_utc_iso(prev)),
    ]
    days = build_day_activity(
        attempts,
        days=7,
        today_local=date(2026, 10, 1),
        local_tz=local,
    )
    assert len(days) == 7
    assert days[-1].date == "2026-10-01"
    assert days[-1].attempt_count == 1
    assert days[-1].mastery_attempt_count == 1
    assert days[-2].date == "2026-09-30"
    assert days[-2].attempt_count == 2
    assert days[-2].mastery_attempt_count == 1
    assert attempt_local_date(to_utc_iso(morning_local), local_tz=local) == "2026-10-01"


def test_recent_attempts_newest_first():
    attempts = [
        _attempt("old", correct=True, timestamp="2026-09-01T10:00:00+00:00"),
        _attempt("mid", correct=False, timestamp="2026-09-02T10:00:00+00:00"),
        _attempt("new", correct=True, timestamp="2026-09-03T10:00:00+00:00"),
    ]
    snap = build_learning_progress(
        "nl",
        [],
        {},
        attempts,
        [],
        now=NOW,
        today_local=TODAY,
        local_tz=TZ,
        recent_attempt_limit=2,
    )
    assert [item.word for item in snap.recent_attempts] == ["new", "mid"]


def test_language_isolation(tmp_path):
    nl = tmp_path / "nl"
    de = tmp_path / "de"
    nl.mkdir()
    de.mkdir()
    (nl / "vocab.json").write_text(
        json.dumps([{"word": "huis", "meaning": "house"}]), encoding="utf-8"
    )
    (de / "vocab.json").write_text(
        json.dumps([{"word": "Haus", "meaning": "house"}]), encoding="utf-8"
    )
    Progress(str(nl / "progress.json")).record("huis", True, vocab_id=None)
    # Write Dutch attempts only into nl file via AttemptHistory path used by loader.
    from attempt_history import AttemptHistory

    AttemptHistory(str(nl / "attempts.jsonl"), language_code="nl").record(
        _attempt("huis", correct=True, timestamp=to_utc_iso(NOW))
    )
    nl_snap = load_learning_progress(
        "nl",
        now=NOW,
        today_local=TODAY,
        local_tz=TZ,
        vocab_store=VocabStore(str(nl / "vocab.json")),
        progress=Progress(str(nl / "progress.json")),
        attempts=AttemptHistory(str(nl / "attempts.jsonl"), language_code="nl").load_attempts(),
    )
    de_snap = load_learning_progress(
        "de",
        now=NOW,
        today_local=TODAY,
        local_tz=TZ,
        vocab_store=VocabStore(str(de / "vocab.json")),
        progress=Progress(str(de / "progress.json")),
        attempts=[],
    )
    assert nl_snap.total_attempt_count == 1
    assert nl_snap.practiced_word_count == 1
    assert de_snap.total_attempt_count == 0
    assert de_snap.practiced_word_count == 0
    assert de_snap.new_word_count == 1


def test_no_mutation_of_progress_or_attempts(tmp_path):
    path = tmp_path / "vocab.json"
    progress_path = tmp_path / "progress.json"
    attempts_path = tmp_path / "attempts.jsonl"
    path.write_text(
        json.dumps(
            [
                {
                    "id": "11111111-1111-4111-8111-111111111111",
                    "word": "huis",
                    "meaning": "house",
                }
            ]
        ),
        encoding="utf-8",
    )
    progress_path.write_text(
        json.dumps({"version": 3, "words": {}, "days": {}, "legacy_index": {}}),
        encoding="utf-8",
    )
    attempts_path.write_text("", encoding="utf-8")
    # Settle any identity migration first, then assert the query itself writes nothing.
    store = VocabStore(str(path))
    prog = Progress(str(progress_path))
    before_p = json.loads(progress_path.read_text(encoding="utf-8"))
    before_a = attempts_path.read_text(encoding="utf-8")
    build_learning_progress(
        "nl",
        store.all(),
        prog.data.get("words") or {},
        [],
        [],
        now=NOW,
        today_local=TODAY,
        local_tz=TZ,
    )
    assert json.loads(progress_path.read_text(encoding="utf-8")) == before_p
    assert attempts_path.read_text(encoding="utf-8") == before_a
    # Progress object in memory also unchanged by the query.
    assert prog.data.get("words") == before_p.get("words")


def test_deterministic_output():
    vocab = [{"id": "11111111-1111-4111-8111-111111111111", "word": "x", "meaning": "y"}]
    words = {
        "11111111-1111-4111-8111-111111111111": {
            "seen": 1,
            "correct": 1,
            "wrong": 0,
            "streak": 1,
            "due_at": to_utc_iso(NOW),
            "interval_days": 1,
        }
    }
    attempts = [_attempt("x", correct=True, timestamp=to_utc_iso(NOW), vocab_id="11111111-1111-4111-8111-111111111111")]
    a = build_learning_progress(
        "nl", vocab, words, attempts, [], now=NOW, today_local=TODAY, local_tz=TZ
    )
    b = build_learning_progress(
        "nl", vocab, words, attempts, [], now=NOW, today_local=TODAY, local_tz=TZ
    )
    assert a == b
