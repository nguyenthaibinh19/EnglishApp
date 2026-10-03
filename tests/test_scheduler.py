"""Scheduler weight formula and non-mutating pick."""

import copy
import json
import random
from datetime import date

import scheduler
from progress import Progress
from vocab_store import VocabStore

TODAY = date(2026, 10, 1)


def test_unseen_weight_higher_than_strong():
    unseen = {"seen": 0, "correct": 0, "wrong": 0, "streak": 0, "last_seen": None}
    strong = {
        "seen": 10,
        "correct": 10,
        "wrong": 0,
        "streak": 5,
        "last_seen": "2026-10-01T12:00:00",
    }
    assert scheduler.compute_weight(unseen, TODAY) > scheduler.compute_weight(strong, TODAY)


def test_weak_weight_higher_than_strong():
    weak = {
        "seen": 10,
        "correct": 2,
        "wrong": 8,
        "streak": 0,
        "last_seen": "2026-10-01T12:00:00",
    }
    strong = {
        "seen": 10,
        "correct": 10,
        "wrong": 0,
        "streak": 5,
        "last_seen": "2026-10-01T12:00:00",
    }
    assert scheduler.compute_weight(weak, TODAY) > scheduler.compute_weight(strong, TODAY)


def test_high_streak_reduces_weight():
    high = {"seen": 5, "correct": 5, "wrong": 0, "streak": 5, "last_seen": None}
    low = {"seen": 5, "correct": 5, "wrong": 0, "streak": 0, "last_seen": None}
    assert scheduler.compute_weight(high, TODAY) < scheduler.compute_weight(low, TODAY)


def test_stale_word_regains_weight():
    strong = {
        "seen": 10,
        "correct": 10,
        "wrong": 0,
        "streak": 5,
        "last_seen": "2026-10-01T12:00:00",
    }
    stale = {
        "seen": 10,
        "correct": 10,
        "wrong": 0,
        "streak": 5,
        "last_seen": "2026-09-01T12:00:00",
    }
    assert scheduler.compute_weight(stale, TODAY) > scheduler.compute_weight(strong, TODAY)


def test_pick_next_does_not_mutate_progress(tmp_path):
    vocab = tmp_path / "vocab.json"
    progress_path = tmp_path / "progress.json"
    vocab.write_text(
        json.dumps(
            [
                {"word": "alpha", "vi": "a"},
                {"word": "beta", "vi": "b"},
                {"word": "gamma", "vi": "c"},
            ]
        ),
        encoding="utf-8",
    )
    progress_path.write_text(
        json.dumps(
            {
                "version": 2,
                "words": {
                    "alpha": {
                        "seen": 4,
                        "correct": 4,
                        "wrong": 0,
                        "streak": 4,
                        "last_seen": "2026-10-01T10:00:00",
                    }
                },
                "days": {},
            }
        ),
        encoding="utf-8",
    )
    store = VocabStore(str(vocab))  # identity migration may rewrite progress once
    before = progress_path.read_text(encoding="utf-8")
    progress = Progress(str(progress_path))
    snapshot = copy.deepcopy(progress.data)
    chooser = scheduler.VocabScheduler(progress, rng=random.Random(1))
    picked = chooser.pick_next(store, answered=0)
    assert picked is not None and "word" in picked
    assert progress.data == snapshot
    assert progress_path.read_text(encoding="utf-8") == before


def test_progress_weight_matches_scheduler(tmp_path):
    progress_path = tmp_path / "progress.json"
    progress_path.write_text(
        json.dumps(
            {
                "version": 2,
                "words": {
                    "alpha": {
                        "seen": 4,
                        "correct": 4,
                        "wrong": 0,
                        "streak": 4,
                        "last_seen": "2026-10-01T10:00:00",
                    }
                },
                "days": {},
            }
        ),
        encoding="utf-8",
    )
    progress = Progress(str(progress_path))
    assert abs(
        progress.weight("alpha") - scheduler.compute_weight(progress.word_stats("alpha"))
    ) < 1e-9
