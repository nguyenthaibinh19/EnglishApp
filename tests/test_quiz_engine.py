"""QuizEngine non-UI behavior with seeded RNG."""

import json
import random

from attempt_history import AttemptHistory
from progress import Progress
from quiz_engine import QuizEngine
from vocab_store import VocabStore


def _engine(tmp_path, target=3, language_code="nl"):
    vocab = tmp_path / "vocab.json"
    progress_path = tmp_path / "progress.json"
    vocab.write_text(
        json.dumps(
            [
                {"en": "de fiets", "vi": "xe đạp"},
                {"en": "het huis", "vi": "ngôi nhà"},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    store = VocabStore(str(vocab))
    store.add("de trein", "tàu hỏa")
    progress = Progress(str(progress_path))
    attempts = AttemptHistory(str(tmp_path / "attempts.jsonl"), language_code=language_code)
    engine = QuizEngine(
        store,
        progress,
        target=target,
        rng=random.Random(7),
        attempt_history=attempts,
        language_code=language_code,
    )
    return store, progress, engine, attempts


def test_legacy_vocab_key_migrates(tmp_path):
    store, _, _, _ = _engine(tmp_path)
    assert store.count() == 3
    assert "word" in store.get(0) and "en" not in store.get(0)


def test_wrong_answer_does_not_increase_score(tmp_path):
    _, _, engine, _ = _engine(tmp_path)
    assert engine.pick_next() is not None
    result = engine.submit("sai bét")
    assert result.verdict == "wrong"
    assert result.correct_count == 0


def test_enough_correct_answers_finish_session(tmp_path):
    _, progress, engine, _ = _engine(tmp_path, target=3)
    for _ in range(8):
        current = engine.pick_next()
        assert current is not None
        engine.submit(current["word"])
        if engine.finished:
            break
    assert engine.finished
    assert len(progress.words_studied_today()) >= 1


def test_duplicate_add_rejected(tmp_path):
    store, _, _, _ = _engine(tmp_path)
    assert store.add("DE TREIN", "tàu") is False


def test_one_submit_one_attempt_matches_progress(tmp_path):
    _, progress, engine, attempts = _engine(tmp_path, language_code="nl")
    entry = engine.pick_next()
    assert entry is not None
    result = engine.submit("sai bét")
    loaded = attempts.load_attempts()
    assert len(loaded) == 1
    assert loaded[0].correct is False
    assert result.verdict == "wrong"
    word_key = loaded[0].word
    stats = progress.word_stats(word_key)
    assert stats["wrong"] == 1
    assert stats["correct"] == 0
    # Same decision as Progress.record: wrong answer → correct=False
    assert loaded[0].correct is False
    assert loaded[0].language_code == "nl"
    assert loaded[0].user_answer == "sai bét"


def test_correct_and_incorrect_attempts_recorded(tmp_path):
    _, progress, engine, attempts = _engine(tmp_path, language_code="de")
    engine.pick_next()
    engine.submit("totally wrong")
    entry = engine.pick_next()
    engine.submit(entry["word"])
    loaded = attempts.load_attempts()
    assert len(loaded) == 2
    assert loaded[0].correct is False
    assert loaded[1].correct is True
    assert loaded[1].verdict == "exact"
    wrong_stats = progress.word_stats(loaded[0].word)
    right_stats = progress.word_stats(loaded[1].word)
    assert wrong_stats["wrong"] >= 1
    assert right_stats["correct"] >= 1
    assert all(a.language_code == "de" for a in loaded)


def test_near_typo_not_mastered_in_attempt_or_progress(tmp_path):
    """Near match counts for session but Progress + attempt use mastered=False."""
    _, progress, engine, attempts = _engine(tmp_path)
    # Force a known entry: de fiets — one-char typo → near
    engine.current_index = 0
    engine.hint_used = False
    result = engine.submit("de fietz")
    assert result.verdict == "near"
    assert result.is_correct is True
    loaded = attempts.load_attempts()
    assert len(loaded) == 1
    assert loaded[0].correct is False
    assert loaded[0].verdict == "near"
    stats = progress.word_stats("de fiets")
    assert stats["wrong"] == 1
    assert stats["correct"] == 0


def test_requeue_does_not_duplicate_without_new_submit(tmp_path):
    """Scheduling a requeue alone must not invent extra attempt rows."""
    _, _, engine, attempts = _engine(tmp_path)
    engine.pick_next()
    engine.submit("wrong answer xyz")
    assert len(attempts.load_attempts()) == 1
    engine.pick_next()
    assert len(attempts.load_attempts()) == 1
