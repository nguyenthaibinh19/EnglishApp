"""Phase 13 — stable vocabulary identity + migration."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from attempt_history import AttemptHistory, LearningAttempt
from mistake_book import resolve_practice_entries, summarize_mistakes
from progress import Progress
from quiz_engine import QuizEngine
from vocab_identity import (
    IDENTITY_MARKER,
    PROGRESS_IDENTITY_VERSION,
    ensure_language_identity,
    is_vocab_id,
    migrate_attempts_lines,
    migrate_progress_words,
    new_vocab_id,
)
from vocab_store import VocabStore
from vocabulary_library import build_vocabulary_detail

NOW = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)


def _write_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _lang_dir(tmp_path: Path) -> Path:
    d = tmp_path / "nl"
    d.mkdir()
    return d


def test_new_vocab_item_receives_id(tmp_path):
    path = tmp_path / "vocab.json"
    _write_json(path, [])
    store = VocabStore(str(path))
    assert store.add("huis", "house")
    entry = store.get(0)
    assert is_vocab_id(entry["id"])
    reloaded = VocabStore(str(path))
    assert reloaded.get(0)["id"] == entry["id"]


def test_edit_preserves_id(tmp_path):
    path = tmp_path / "vocab.json"
    _write_json(path, [{"word": "huis", "vi": "house"}])
    store = VocabStore(str(path))
    vid = store.get(0)["id"]
    assert store.update(0, "het huis", "the house")
    assert store.get(0)["id"] == vid
    assert store.get(0)["word"] == "het huis"
    again = VocabStore(str(path))
    assert again.get(0)["id"] == vid


def test_delete_does_not_mutate_unrelated_ids(tmp_path):
    path = tmp_path / "vocab.json"
    _write_json(
        path,
        [
            {"word": "a", "vi": "1"},
            {"word": "b", "vi": "2"},
            {"word": "c", "vi": "3"},
        ],
    )
    store = VocabStore(str(path))
    ids = [e["id"] for e in store.all()]
    store.delete(1)
    left = [e["id"] for e in store.all()]
    assert left == [ids[0], ids[2]]


def test_legacy_vocab_migrates_idempotent(tmp_path):
    folder = _lang_dir(tmp_path)
    vocab = folder / "vocab.json"
    progress = folder / "progress.json"
    attempts = folder / "attempts.jsonl"
    _write_json(
        vocab,
        [{"word": "huis", "vi": "house"}, {"nl": "fiets", "vi": "bike"}],
    )
    _write_json(
        progress,
        {
            "version": 2,
            "words": {
                "huis": {
                    "seen": 5,
                    "correct": 4,
                    "wrong": 1,
                    "streak": 2,
                    "last_seen": "2026-09-01T00:00:00+00:00",
                    "due_at": "2026-09-02T00:00:00+00:00",
                    "interval_days": 1,
                }
            },
            "days": {},
        },
    )
    attempts.write_text(
        json.dumps(
            {
                "timestamp": "2026-09-01T00:00:00+00:00",
                "language_code": "nl",
                "word": "huis",
                "user_answer": "huis",
                "expected_answer": "huis",
                "correct": True,
                "verdict": "exact",
                "hint_used": False,
                "prompt": "house",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    store1 = VocabStore(str(vocab))
    id_huis = store1.get(0)["id"]
    id_fiets = store1.get(1)["id"]
    assert is_vocab_id(id_huis) and is_vocab_id(id_fiets)
    assert store1.get(1)["word"] == "fiets"

    prog1 = Progress(str(progress))
    assert prog1.data["version"] >= PROGRESS_IDENTITY_VERSION
    assert prog1.data["identity"] == IDENTITY_MARKER
    assert id_huis in prog1.data["words"]
    assert "huis" not in prog1.data["words"]
    stats = prog1.data["words"][id_huis]
    assert stats["seen"] == 5
    assert stats["streak"] == 2
    assert stats["interval_days"] == 1
    assert stats["due_at"] == "2026-09-02T00:00:00+00:00"

    hist = AttemptHistory(str(attempts), language_code="nl").load_attempts()
    assert hist[0].vocab_id == id_huis

    # Second load keeps same IDs / no duplication
    store2 = VocabStore(str(vocab))
    assert store2.get(0)["id"] == id_huis
    assert store2.get(1)["id"] == id_fiets
    prog2 = Progress(str(progress))
    assert list(prog2.data["words"].keys()) == [id_huis]
    hist2 = AttemptHistory(str(attempts), language_code="nl").load_attempts()
    assert len(hist2) == 1 and hist2[0].vocab_id == id_huis


def test_new_progress_uses_stable_id(tmp_path):
    folder = _lang_dir(tmp_path)
    vocab = folder / "vocab.json"
    progress = folder / "progress.json"
    _write_json(vocab, [{"word": "trein", "vi": "train"}])
    store = VocabStore(str(vocab))
    vid = store.get(0)["id"]
    prog = Progress(str(progress))
    prog.record("trein", correct=True, vocab_id=vid, reviewed_at=NOW)
    assert vid in prog.data["words"]
    assert prog.data["words"][vid]["correct"] == 1
    assert prog.word_stats("trein")["correct"] == 1  # legacy_index compat


def test_legacy_progress_readable_during_compat(tmp_path):
    path = tmp_path / "progress.json"
    _write_json(
        path,
        {
            "version": 2,
            "words": {"alpha": {"seen": 2, "correct": 2, "wrong": 0, "streak": 2}},
            "days": {},
        },
    )
    prog = Progress(str(path))
    assert prog.word_stats("alpha")["seen"] == 2


def test_new_attempt_stores_vocab_id(tmp_path):
    folder = _lang_dir(tmp_path)
    vocab = folder / "vocab.json"
    progress = folder / "progress.json"
    attempts = folder / "attempts.jsonl"
    _write_json(vocab, [{"word": "kat", "vi": "cat"}])
    store = VocabStore(str(vocab))
    vid = store.get(0)["id"]
    prog = Progress(str(progress))
    engine = QuizEngine(
        store,
        prog,
        target=1,
        language_code="nl",
        attempt_history=AttemptHistory(str(attempts), language_code="nl"),
        apply_due_filter=False,
        rng=__import__("random").Random(0),
    )
    engine.pick_next()
    engine.submit("kat")
    items = AttemptHistory(str(attempts)).load_attempts()
    assert items[-1].vocab_id == vid
    assert vid in prog.data["words"]


def test_unresolved_legacy_attempt_preserved(tmp_path):
    folder = _lang_dir(tmp_path)
    vocab = folder / "vocab.json"
    attempts = folder / "attempts.jsonl"
    _write_json(vocab, [{"word": "huis", "vi": "house"}])
    line = {
        "timestamp": "t",
        "language_code": "nl",
        "word": "ghost",
        "user_answer": "x",
        "expected_answer": "ghost",
        "correct": False,
        "verdict": "wrong",
        "hint_used": False,
        "prompt": "p",
    }
    attempts.write_text(json.dumps(line) + "\n", encoding="utf-8")
    VocabStore(str(vocab))  # migrate
    raw = attempts.read_text(encoding="utf-8").strip()
    data = json.loads(raw)
    assert "vocab_id" not in data or not data.get("vocab_id")
    assert data["word"] == "ghost"


def test_attempt_migration_preserves_order(tmp_path):
    entries = [
        {"id": "11111111-1111-1111-1111-111111111111", "word": "a", "vi": "1"},
        {"id": "22222222-2222-2222-2222-222222222222", "word": "b", "vi": "2"},
    ]
    lines = [
        json.dumps(
            {
                "timestamp": f"t{i}",
                "language_code": "nl",
                "word": w,
                "user_answer": "x",
                "expected_answer": w,
                "correct": False,
                "verdict": "wrong",
                "hint_used": False,
                "prompt": "p",
            }
        )
        + "\n"
        for i, w in enumerate(["a", "b", "a"])
    ]
    out, changed = migrate_attempts_lines(lines, entries)
    assert changed
    words = [json.loads(x)["word"] for x in out]
    assert words == ["a", "b", "a"]
    assert json.loads(out[0])["vocab_id"].startswith("1111")
    assert json.loads(out[1])["vocab_id"].startswith("2222")


def test_ambiguous_duplicate_maps_progress_to_first_only():
    id_a = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    id_b = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    vocab = [
        {"id": id_a, "word": "bank", "vi": "sofa"},
        {"id": id_b, "word": "Bank", "vi": "finance"},
    ]
    progress = {
        "version": 2,
        "words": {"bank": {"seen": 3, "correct": 1, "wrong": 2, "streak": 0}},
        "days": {},
    }
    migrated, changed = migrate_progress_words(progress, vocab)
    assert changed
    assert id_a in migrated["words"]
    assert id_b not in migrated["words"]
    assert migrated["words"][id_a]["seen"] == 3
    assert "bank" not in migrated["words"]


def test_mistake_book_groups_by_id():
    vid = "cccccccc-cccc-cccc-cccc-cccccccccccc"
    attempts = [
        LearningAttempt(
            timestamp="t1",
            language_code="nl",
            word="huis",
            user_answer="x",
            expected_answer="huis",
            correct=False,
            verdict="wrong",
            vocab_id=vid,
        ),
        LearningAttempt(
            timestamp="t2",
            language_code="nl",
            word="het huis",
            user_answer="y",
            expected_answer="het huis",
            correct=False,
            verdict="wrong",
            vocab_id=vid,
        ),
    ]
    summaries = summarize_mistakes(attempts, language_code="nl")
    assert len(summaries) == 1
    assert summaries[0].vocab_id == vid
    assert summaries[0].attention_count == 2


def test_practice_resolves_by_id():
    id_a = "dddddddd-dddd-dddd-dddd-dddddddddddd"
    id_b = "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"
    vocab = [
        {"id": id_a, "word": "bank", "vi": "sofa"},
        {"id": id_b, "word": "bank", "vi": "finance"},  # would be blocked by add(), but legacy
    ]
    from mistake_book import MistakeSummary

    summary = MistakeSummary(
        word="bank",
        prompt="finance",
        attention_count=1,
        last_user_answer="x",
        expected_answer="bank",
        last_verdict="wrong",
        last_hint_used=False,
        last_timestamp="t",
        language_code="nl",
        vocab_id=id_b,
    )
    resolved = resolve_practice_entries([summary], vocab)
    assert len(resolved) == 1
    assert resolved[0]["id"] == id_b
    assert resolved[0]["vi"] == "finance"


def test_rename_preserves_progress_attempts_mistakes_detail(tmp_path):
    folder = _lang_dir(tmp_path)
    vocab = folder / "vocab.json"
    progress = folder / "progress.json"
    attempts = folder / "attempts.jsonl"
    _write_json(vocab, [{"word": "huis", "vi": "house"}])
    store = VocabStore(str(vocab))
    vid = store.get(0)["id"]
    prog = Progress(str(progress))
    prog.record("huis", correct=False, vocab_id=vid, reviewed_at=NOW)
    due_at = prog.data["words"][vid]["due_at"]
    hist = AttemptHistory(str(attempts), language_code="nl")
    hist.record(
        LearningAttempt(
            timestamp="2026-10-01T10:00:00+00:00",
            language_code="nl",
            word="huis",
            user_answer="x",
            expected_answer="huis",
            correct=False,
            verdict="wrong",
            prompt="house",
            vocab_id=vid,
        )
    )

    assert store.update(0, "het huis", "the house")
    assert store.get(0)["id"] == vid

    prog2 = Progress(str(progress))
    assert prog2.data["words"][vid]["seen"] == 1
    assert prog2.data["words"][vid]["due_at"] == due_at

    attempts_list = AttemptHistory(str(attempts)).load_attempts()
    summaries = summarize_mistakes(attempts_list, language_code="nl")
    assert summaries[0].vocab_id == vid
    assert summaries[0].attention_count == 1

    detail = build_vocabulary_detail(
        store.get(0),
        0,
        language_code="nl",
        progress_words=prog2.data["words"],
        attempts=attempts_list,
        mistake_summaries=summaries,
        now=NOW,
    )
    assert detail.vocab_id == vid
    assert detail.seen == 1
    assert detail.needs_attention
    assert len(detail.recent_attempts) == 1
    assert detail.word == "het huis"


def test_languages_isolated(tmp_path):
    nl = tmp_path / "nl"
    de = tmp_path / "de"
    nl.mkdir()
    de.mkdir()
    _write_json(nl / "vocab.json", [{"word": "huis", "vi": "house"}])
    _write_json(de / "vocab.json", [{"word": "haus", "vi": "house"}])
    _write_json(
        nl / "progress.json",
        {"version": 2, "words": {"huis": {"seen": 9, "correct": 9, "wrong": 0, "streak": 9}}, "days": {}},
    )
    _write_json(
        de / "progress.json",
        {"version": 2, "words": {"haus": {"seen": 1, "correct": 0, "wrong": 1, "streak": 0}}, "days": {}},
    )
    nl_store = VocabStore(str(nl / "vocab.json"))
    de_store = VocabStore(str(de / "vocab.json"))
    nl_prog = Progress(str(nl / "progress.json"))
    de_prog = Progress(str(de / "progress.json"))
    nl_id = nl_store.get(0)["id"]
    de_id = de_store.get(0)["id"]
    assert nl_id != de_id
    assert nl_prog.data["words"][nl_id]["seen"] == 9
    assert de_prog.data["words"][de_id]["seen"] == 1


def test_failed_migration_does_not_truncate_attempts(tmp_path, monkeypatch):
    folder = _lang_dir(tmp_path)
    vocab = folder / "vocab.json"
    attempts = folder / "attempts.jsonl"
    _write_json(vocab, [{"word": "huis", "vi": "house"}])
    original = (
        json.dumps(
            {
                "timestamp": "t",
                "language_code": "nl",
                "word": "huis",
                "user_answer": "x",
                "expected_answer": "huis",
                "correct": False,
                "verdict": "wrong",
                "hint_used": False,
                "prompt": "h",
            }
        )
        + "\n"
    )
    attempts.write_text(original, encoding="utf-8")

    import vocab_identity

    def boom(*_a, **_k):
        raise OSError("disk full")

    monkeypatch.setattr(vocab_identity, "atomic_write_text", boom)
    # Assign ids on vocab may succeed; attempts rewrite fails.
    with pytest.raises(OSError):
        ensure_language_identity(
            str(vocab),
            progress_path=str(folder / "progress.json"),
            attempts_path=str(attempts),
        )
    assert attempts.read_text(encoding="utf-8") == original


def test_duplicate_add_still_blocked(tmp_path):
    path = tmp_path / "vocab.json"
    _write_json(path, [])
    store = VocabStore(str(path))
    assert store.add("de trein", "train")
    assert store.add("DE TREIN", "train") is False
