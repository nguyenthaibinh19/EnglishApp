"""Practice Mistakes — subset resolution and quiz-only VocabView."""

from __future__ import annotations

import json
import random

from attempt_history import AttemptHistory, LearningAttempt
from mistake_book import (
    MistakeSummary,
    practice_target,
    resolve_practice_entries,
    summarize_mistakes,
)
from progress import Progress
from quiz_engine import QuizEngine
from vocab_store import ReadOnlyVocabView, VocabStore


def _summary(word: str, prompt: str = "") -> MistakeSummary:
    return MistakeSummary(
        word=word,
        prompt=prompt,
        attention_count=1,
        last_user_answer="x",
        expected_answer=word,
        last_verdict="wrong",
        last_hint_used=False,
        last_timestamp="2026-10-01T12:00:00+00:00",
        language_code="nl",
    )


def test_resolve_maps_to_full_vocab_entries():
    vocab = [
        {"word": "de fiets", "vi": "xe đạp", "alt": ["fiets"], "example": "Ik fiets."},
        {"word": "het huis", "vi": "ngôi nhà"},
    ]
    summaries = [_summary("de fiets"), _summary("het huis")]
    entries = resolve_practice_entries(summaries, vocab)
    assert len(entries) == 2
    assert entries[0]["alt"] == ["fiets"]
    assert entries[0]["example"] == "Ik fiets."
    assert entries[1]["word"] == "het huis"


def test_resolve_skips_missing_vocab_words():
    vocab = [{"word": "de fiets", "vi": "xe đạp"}]
    summaries = [_summary("de fiets"), _summary("deleted-word")]
    entries = resolve_practice_entries(summaries, vocab)
    assert [e["word"] for e in entries] == ["de fiets"]


def test_resolve_duplicate_headword_takes_first():
    vocab = [
        {"word": "bank", "vi": "ngân hàng"},
        {"word": "Bank", "vi": "bờ sông"},
    ]
    entries = resolve_practice_entries([_summary("bank")], vocab)
    assert len(entries) == 1
    assert entries[0]["vi"] == "ngân hàng"


def test_practice_target_capped_by_subset_size():
    assert practice_target(2, quiz_target=5) == 2
    assert practice_target(10, quiz_target=5) == 5
    assert practice_target(0, quiz_target=5) == 0
    assert practice_target(3, quiz_target=1) == 1


def test_readonly_view_refuses_mutation(tmp_path):
    real = tmp_path / "vocab.json"
    real.write_text(
        json.dumps([{"word": "a", "vi": "1"}, {"word": "b", "vi": "2"}], ensure_ascii=False),
        encoding="utf-8",
    )
    store = VocabStore(str(real))
    view = ReadOnlyVocabView(store.entries_for_keys(["a"]))
    assert view.count() == 1
    assert view.add("c", "3") is False
    assert view.update(0, "aa", "11") is False
    assert view.delete(0) is False
    view.save()
    # Real file unchanged; view still has original entry.
    reloaded = VocabStore(str(real))
    assert reloaded.count() == 2
    assert view.count() == 1
    assert view.get(0)["word"] == "a"


def test_quiz_engine_on_readonly_subset_records_progress_and_attempt(tmp_path):
    progress_path = tmp_path / "progress.json"
    attempts_path = tmp_path / "attempts.jsonl"
    progress = Progress(str(progress_path))
    history = AttemptHistory(str(attempts_path), language_code="nl")
    view = ReadOnlyVocabView(
        [
            {"word": "de fiets", "vi": "xe đạp", "alt": ["fiets"]},
            {"word": "het huis", "vi": "ngôi nhà"},
        ]
    )
    engine = QuizEngine(
        view,
        progress,
        target=practice_target(view.count(), quiz_target=5),
        attempt_history=history,
        language_code="nl",
        rng=random.Random(1),
    )
    assert engine.target == 2

    engine.pick_next()
    engine.submit("totally wrong")
    assert len(history.load_attempts()) == 1
    assert history.load_attempts()[0].correct is False

    # Force known entry and master it
    engine.current_index = 0
    engine.hint_used = False
    engine.submit("de fiets")
    attempts = history.load_attempts()
    assert len(attempts) == 2
    assert attempts[-1].correct is True
    assert attempts[-1].word == "de fiets"
    stats = progress.word_stats("de fiets")
    assert stats["correct"] >= 1

    # Vocab membership unchanged (read-only)
    assert view.count() == 2
    assert view.add("x", "y") is False


def test_mastered_practice_removes_from_mistake_book(tmp_path):
    attempts_path = tmp_path / "attempts.jsonl"
    history = AttemptHistory(str(attempts_path), language_code="nl")
    history.record(
        LearningAttempt(
            timestamp="2026-10-01T10:00:00+00:00",
            language_code="nl",
            word="de fiets",
            user_answer="bad",
            expected_answer="de fiets",
            correct=False,
            verdict="wrong",
            prompt="xe đạp",
        )
    )
    assert len(summarize_mistakes(history.load_attempts(), "nl")) == 1

    progress = Progress(str(tmp_path / "progress.json"))
    view = ReadOnlyVocabView([{"word": "de fiets", "vi": "xe đạp"}])
    engine = QuizEngine(
        view,
        progress,
        target=1,
        attempt_history=history,
        language_code="nl",
        rng=random.Random(0),
    )
    engine.current_index = 0
    engine.hint_used = False
    engine.submit("de fiets")
    assert summarize_mistakes(history.load_attempts(), "nl") == []


def test_multiple_mistakes_map_to_practice_subset():
    vocab = [
        {"word": "alpha", "vi": "A"},
        {"word": "beta", "vi": "B"},
        {"word": "gamma", "vi": "C"},
    ]
    summaries = [_summary("gamma"), _summary("alpha"), _summary("missing")]
    entries = resolve_practice_entries(summaries, vocab)
    assert [e["word"] for e in entries] == ["gamma", "alpha"]
