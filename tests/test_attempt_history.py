"""AttemptHistory store — local JSONL learning attempts."""

from __future__ import annotations

import json

from attempt_history import (
    AttemptHistory,
    LearningAttempt,
    load_attempts,
    recent_attempts,
)
from progress import Progress


def _make_attempt(
    language_code: str,
    word: str,
    user_answer: str,
    expected: str,
    correct: bool,
    **kwargs,
) -> LearningAttempt:
    return LearningAttempt(
        timestamp="2026-10-01T18:32:12+00:00",
        language_code=language_code,
        word=word,
        user_answer=user_answer,
        expected_answer=expected,
        correct=correct,
        **kwargs,
    )


def test_missing_history_is_empty(tmp_path):
    path = tmp_path / "attempts.jsonl"
    history = AttemptHistory(str(path), language_code="nl")
    assert history.load_attempts() == []
    assert not path.exists()


def test_first_record_creates_file(tmp_path):
    path = tmp_path / "attempts.jsonl"
    history = AttemptHistory(str(path), language_code="nl")
    history.record(_make_attempt("nl", "de fiets", "fiets", "de fiets", True))
    assert path.is_file()
    loaded = history.load_attempts()
    assert len(loaded) == 1
    assert loaded[0].word == "de fiets"
    assert loaded[0].correct is True


def test_multiple_attempts_append_in_order(tmp_path):
    path = tmp_path / "attempts.jsonl"
    history = AttemptHistory(str(path), language_code="de")
    history.record(_make_attempt("de", "Haus", "haus", "Haus", True))
    history.record(_make_attempt("de", "Hund", "katze", "Hund", False, verdict="wrong"))
    history.record(_make_attempt("de", "Haus", "Haus", "Haus", True))
    words = [a.word for a in load_attempts(str(path))]
    assert words == ["Haus", "Hund", "Haus"]


def test_correct_incorrect_round_trip(tmp_path):
    path = tmp_path / "attempts.jsonl"
    history = AttemptHistory(str(path), language_code="fr")
    history.record(
        _make_attempt(
            "fr",
            "la maison",
            "maison",
            "la maison",
            True,
            verdict="exact",
            prompt="ngôi nhà",
        )
    )
    history.record(
        _make_attempt(
            "fr",
            "la maison",
            "voiture",
            "la maison",
            False,
            verdict="wrong",
            prompt="ngôi nhà",
        )
    )
    a, b = history.load_attempts()
    assert a.correct is True and a.verdict == "exact"
    assert b.correct is False and b.verdict == "wrong"
    assert a.prompt == "ngôi nhà"


def test_unicode_survives(tmp_path):
    path = tmp_path / "attempts.jsonl"
    history = AttemptHistory(str(path), language_code="nl")
    history.record(
        _make_attempt("nl", "één", "een", "één", False, verdict="near", prompt="một")
    )
    loaded = history.load_attempts()[0]
    assert loaded.word == "één"
    assert loaded.expected_answer == "één"
    assert loaded.prompt == "một"


def test_languages_remain_isolated(tmp_path):
    nl_path = tmp_path / "nl" / "attempts.jsonl"
    de_path = tmp_path / "de" / "attempts.jsonl"
    nl = AttemptHistory(str(nl_path), language_code="nl")
    de = AttemptHistory(str(de_path), language_code="de")
    nl.record(_make_attempt("nl", "fiets", "fiets", "fiets", True))
    de.record(_make_attempt("de", "Fahrrad", "Fahrrad", "Fahrrad", True))
    assert [a.word for a in nl.load_attempts()] == ["fiets"]
    assert [a.word for a in de.load_attempts()] == ["Fahrrad"]


def test_malformed_lines_skipped(tmp_path):
    path = tmp_path / "attempts.jsonl"
    good = _make_attempt("en", "cat", "cat", "cat", True)
    path.write_text(
        "\n".join(
            [
                "{not json",
                json.dumps(
                    {
                        "timestamp": good.timestamp,
                        "language_code": "en",
                        "word": "cat",
                        "user_answer": "cat",
                        "expected_answer": "cat",
                        "correct": True,
                    },
                    ensure_ascii=False,
                ),
                "",
                '{"word": "only"}',  # missing fields still parse via defaults
                "truncated",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    loaded = load_attempts(str(path))
    # First good record + the partial dict (defaults) — truncated/invalid JSON skipped.
    assert any(a.word == "cat" and a.correct is True for a in loaded)
    assert all(isinstance(a, LearningAttempt) for a in loaded)


def test_recording_history_does_not_modify_progress(tmp_path):
    progress_path = tmp_path / "progress.json"
    progress = Progress(str(progress_path))
    before = json.dumps(progress.data, sort_keys=True)
    history = AttemptHistory(str(tmp_path / "attempts.jsonl"), language_code="nl")
    history.record(_make_attempt("nl", "fiets", "fiets", "fiets", True))
    reloaded = Progress(str(progress_path))
    assert json.dumps(reloaded.data, sort_keys=True) == before
    assert reloaded.data["words"] == {}


def test_recent_attempts_limit(tmp_path):
    path = tmp_path / "attempts.jsonl"
    history = AttemptHistory(str(path), language_code="es")
    for i in range(5):
        history.record(_make_attempt("es", f"w{i}", f"a{i}", f"w{i}", i % 2 == 0))
    recent = recent_attempts(str(path), limit=2)
    assert [a.word for a in recent] == ["w3", "w4"]
