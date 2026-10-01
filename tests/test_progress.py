"""Progress persistence round-trip and counters."""

import json

from progress import Progress


def test_new_progress_defaults(empty_progress_file):
    progress = Progress(str(empty_progress_file))
    assert progress.data["version"] == 2
    assert progress.data["words"] == {}
    assert progress.data["days"] == {}


def test_record_correct_and_incorrect(empty_progress_file):
    progress = Progress(str(empty_progress_file))
    progress.record("de fiets", correct=False, autosave=True)
    stats = progress.word_stats("de fiets")
    assert stats["seen"] == 1
    assert stats["wrong"] == 1
    assert stats["streak"] == 0

    progress.record("de fiets", correct=True, autosave=True)
    stats = progress.word_stats("de fiets")
    assert stats["seen"] == 2
    assert stats["correct"] == 1
    assert stats["streak"] == 1
    assert "de fiets" in progress.words_studied_today()


def test_streak_resets_on_wrong(empty_progress_file):
    progress = Progress(str(empty_progress_file))
    progress.record("huis", correct=True, autosave=False)
    progress.record("huis", correct=True, autosave=False)
    assert progress.word_stats("huis")["streak"] == 2
    progress.record("huis", correct=False, autosave=True)
    assert progress.word_stats("huis")["streak"] == 0


def test_save_load_round_trip(empty_progress_file):
    progress = Progress(str(empty_progress_file))
    progress.record("trein", correct=True, autosave=True)
    reloaded = Progress(str(empty_progress_file))
    assert "trein" in reloaded.data["words"]
    assert reloaded.data["words"]["trein"]["correct"] == 1


def test_legacy_progress_json_loads(tmp_path):
    path = tmp_path / "progress.json"
    path.write_text(
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
    progress = Progress(str(path))
    assert progress.data.get("version") == 2
    assert "alpha" in progress.data["words"]
