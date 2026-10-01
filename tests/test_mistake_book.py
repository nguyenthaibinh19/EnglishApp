"""Mistake Book v1 — domain aggregation rules."""

from __future__ import annotations

from attempt_history import AttemptHistory, LearningAttempt
from mistake_book import (
    STATUS_HINT,
    STATUS_NEAR,
    STATUS_WRONG,
    attention_status,
    load_mistake_summaries,
    summarize_mistakes,
)


def _attempt(
    word: str,
    *,
    correct: bool,
    timestamp: str,
    language_code: str = "nl",
    user_answer: str = "",
    expected: str = "",
    verdict: str = "wrong",
    hint_used: bool = False,
    prompt: str = "",
) -> LearningAttempt:
    return LearningAttempt(
        timestamp=timestamp,
        language_code=language_code,
        word=word,
        user_answer=user_answer or ("ok" if correct else "bad"),
        expected_answer=expected or word,
        correct=correct,
        verdict=verdict,
        hint_used=hint_used,
        prompt=prompt,
    )


def test_empty_attempts_empty_summaries():
    assert summarize_mistakes([]) == []


def test_mastered_only_word_excluded():
    attempts = [
        _attempt("fiets", correct=True, timestamp="2026-10-01T10:00:00+00:00", verdict="exact"),
    ]
    assert summarize_mistakes(attempts) == []


def test_non_mastered_produces_one_summary():
    attempts = [
        _attempt(
            "de fiets",
            correct=False,
            timestamp="2026-10-01T11:00:00+00:00",
            user_answer="fietz",
            expected="de fiets",
            verdict="near",
            prompt="xe đạp",
        ),
    ]
    summaries = summarize_mistakes(attempts)
    assert len(summaries) == 1
    s = summaries[0]
    assert s.word == "de fiets"
    assert s.prompt == "xe đạp"
    assert s.attention_count == 1
    assert s.last_user_answer == "fietz"
    assert s.expected_answer == "de fiets"
    assert s.last_verdict == "near"
    assert s.last_hint_used is False


def test_repeated_non_mastered_aggregates():
    attempts = [
        _attempt("huis", correct=False, timestamp="2026-10-01T09:00:00+00:00", user_answer="a"),
        _attempt("huis", correct=False, timestamp="2026-10-01T10:00:00+00:00", user_answer="b"),
        _attempt("huis", correct=False, timestamp="2026-10-01T11:00:00+00:00", user_answer="c"),
    ]
    summaries = summarize_mistakes(attempts)
    assert len(summaries) == 1
    assert summaries[0].attention_count == 3
    assert summaries[0].last_user_answer == "c"
    assert summaries[0].last_timestamp == "2026-10-01T11:00:00+00:00"


def test_later_mastery_removes_word_from_list():
    """v1 rule: latest attempt mastered → word leaves Mistake Book."""
    attempts = [
        _attempt("trein", correct=False, timestamp="2026-10-01T09:00:00+00:00"),
        _attempt(
            "trein",
            correct=True,
            timestamp="2026-10-01T12:00:00+00:00",
            verdict="exact",
        ),
    ]
    assert summarize_mistakes(attempts) == []


def test_mastery_then_fail_returns_with_prior_attention_count():
    attempts = [
        _attempt("kat", correct=False, timestamp="2026-10-01T08:00:00+00:00"),
        _attempt("kat", correct=True, timestamp="2026-10-01T09:00:00+00:00", verdict="exact"),
        _attempt(
            "kat",
            correct=False,
            timestamp="2026-10-01T10:00:00+00:00",
            user_answer="dog",
            verdict="wrong",
        ),
    ]
    summaries = summarize_mistakes(attempts)
    assert len(summaries) == 1
    assert summaries[0].attention_count == 2  # both non-mastered across history
    assert summaries[0].last_user_answer == "dog"


def test_near_and_hint_preserved():
    near = _attempt(
        "één",
        correct=False,
        timestamp="2026-10-01T10:00:00+00:00",
        verdict="near",
        user_answer="een",
        prompt="một",
    )
    hint = _attempt(
        "lopen",
        correct=False,
        timestamp="2026-10-01T11:00:00+00:00",
        verdict="exact",
        hint_used=True,
        user_answer="lopen",
    )
    summaries = summarize_mistakes([near, hint])
    by_word = {s.word: s for s in summaries}
    assert by_word["één"].last_verdict == "near"
    assert by_word["één"].prompt == "một"
    assert by_word["lopen"].last_hint_used is True
    assert attention_status("near", False) == STATUS_NEAR
    assert attention_status("exact", True) == STATUS_HINT
    assert attention_status("wrong", False) == STATUS_WRONG


def test_multiple_words_separate_and_sort_deterministic():
    attempts = [
        _attempt("alpha", correct=False, timestamp="2026-10-01T10:00:00+00:00"),
        _attempt("alpha", correct=False, timestamp="2026-10-01T11:00:00+00:00"),
        _attempt("beta", correct=False, timestamp="2026-10-01T12:00:00+00:00"),
        _attempt("gamma", correct=False, timestamp="2026-10-01T09:00:00+00:00"),
        _attempt("gamma", correct=False, timestamp="2026-10-01T12:00:00+00:00"),
    ]
    # gamma last@12 count2; beta last@12 count1; alpha last@11 count2
    # sort: timestamp desc, then count desc, then word
    words = [s.word for s in summarize_mistakes(attempts)]
    assert words == ["gamma", "beta", "alpha"]


def test_unicode_intact():
    attempts = [
        _attempt(
            "école",
            correct=False,
            timestamp="2026-10-01T10:00:00+00:00",
            language_code="fr",
            user_answer="ecole",
            expected="l'école",
            prompt="trường học",
            verdict="near",
        ),
    ]
    s = summarize_mistakes(attempts)[0]
    assert s.word == "école"
    assert s.expected_answer == "l'école"
    assert s.prompt == "trường học"


def test_language_isolation(tmp_path):
    nl = AttemptHistory(str(tmp_path / "nl.jsonl"), language_code="nl")
    de = AttemptHistory(str(tmp_path / "de.jsonl"), language_code="de")
    nl.record(
        _attempt("fiets", correct=False, timestamp="2026-10-01T10:00:00+00:00", language_code="nl")
    )
    de.record(
        _attempt("Hund", correct=False, timestamp="2026-10-01T10:00:00+00:00", language_code="de")
    )
    nl_sum = load_mistake_summaries(str(tmp_path / "nl.jsonl"), language_code="nl")
    de_sum = load_mistake_summaries(str(tmp_path / "de.jsonl"), language_code="de")
    assert [s.word for s in nl_sum] == ["fiets"]
    assert [s.word for s in de_sum] == ["Hund"]


def test_missing_file_empty(tmp_path):
    assert load_mistake_summaries(str(tmp_path / "missing.jsonl"), language_code="nl") == []


def test_status_label_and_format_helpers():
    from mistake_book_app import format_item_lines, status_label

    summary = summarize_mistakes(
        [
            _attempt(
                "huis",
                correct=False,
                timestamp="2026-10-01T10:00:00+00:00",
                verdict="near",
                user_answer="huys",
                prompt="nhà",
            )
        ]
    )[0]
    label = status_label(summary)
    assert label  # localized non-empty
    lines = format_item_lines(summary)
    assert lines[0] == "huis"
    assert "huys" in lines[2]
