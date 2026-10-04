"""Phase 14 — canonical VocabularyEntry model + lexical migration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from progress import Progress
from text_utils import match_answer
from vocab_identity import is_vocab_id
from vocab_store import VocabStore
from vocabulary_library import build_vocabulary_items, filter_vocabulary_items
from vocabulary_model import (
    VocabularyEntry,
    entry_meaning,
    entry_to_storage_dict,
    needs_schema_migration,
    normalize_alternatives,
    normalize_entry_dict,
    normalize_part_of_speech,
    normalize_vocab_list,
    vocabulary_entry_from_dict,
    wire_meaning_as_vi,
)


def test_canonical_entry_creation_and_uuid():
    entry = vocabulary_entry_from_dict({"word": "huis", "meaning": "house"})
    assert entry is not None
    assert is_vocab_id(entry.id)
    assert entry.word == "huis"
    assert entry.meaning == "house"
    stored = entry_to_storage_dict(entry)
    assert "vi" not in stored
    assert stored["meaning"] == "house"


def test_legacy_vi_loads_and_canonical_wins():
    legacy = normalize_entry_dict({"word": "huis", "vi": "nhà"}, assign_id=False)
    assert legacy["meaning"] == "nhà"
    assert "vi" not in legacy

    both = normalize_entry_dict(
        {"word": "huis", "meaning": "house", "vi": "nhà"}, assign_id=False
    )
    assert both["meaning"] == "house"


def test_legacy_nl_en_still_load():
    nl = normalize_entry_dict({"nl": "de fiets", "vi": "xe đạp"}, assign_id=False)
    en = normalize_entry_dict({"en": "the house", "vi": "ngôi nhà"}, assign_id=False)
    assert nl["word"] == "de fiets" and nl["meaning"] == "xe đạp"
    assert en["word"] == "the house"


def test_alternatives_normalize_deterministically():
    assert normalize_alternatives(["fiets", " fiets ", "FIETS", ""]) == ["fiets"]
    assert normalize_alternatives("rijwiel") == ["rijwiel"]
    assert normalize_alternatives(None) == []
    row = normalize_entry_dict(
        {"word": "de fiets", "vi": "xe", "alt": "fiets"}, assign_id=False
    )
    assert row["alternatives"] == ["fiets"]
    assert "alt" not in row


def test_example_note_round_trip(tmp_path):
    path = tmp_path / "vocab.json"
    path.write_text("[]", encoding="utf-8")
    store = VocabStore(str(path))
    assert store.add(
        "huis",
        "house",
        example="Het huis is groot.",
        note="common noun",
    )
    entry = store.get(0)
    assert entry["examples"] == [{"text": "Het huis is groot."}]
    assert "example" not in entry
    assert entry["note"] == "common noun"
    assert "vi" not in entry
    reloaded = VocabStore(str(path)).get(0)
    assert reloaded["examples"] == entry["examples"]
    assert reloaded["id"] == entry["id"]


def test_type_migration_known_and_unknown():
    assert normalize_part_of_speech("ww") == "verb"
    assert normalize_part_of_speech("NOUN") == "noun"
    assert normalize_part_of_speech("mystery-tag") == "mystery-tag"
    row = normalize_entry_dict(
        {"word": "lopen", "vi": "đi", "type": "ww"}, assign_id=False
    )
    assert row["part_of_speech"] == "verb"
    assert "type" not in row
    unknown = normalize_entry_dict(
        {"word": "x", "meaning": "y", "type": "custom-pos"}, assign_id=False
    )
    assert unknown["part_of_speech"] == "custom-pos"


def test_migration_idempotent_and_preserves_id(tmp_path):
    path = tmp_path / "vocab.json"
    path.write_text(
        json.dumps([{"word": "huis", "vi": "house", "alt": ["home"]}]),
        encoding="utf-8",
    )
    store1 = VocabStore(str(path))
    vid = store1.get(0)["id"]
    assert store1.get(0)["meaning"] == "house"
    assert store1.get(0)["alternatives"] == ["home"]
    raw1 = path.read_text(encoding="utf-8")
    store2 = VocabStore(str(path))
    assert store2.get(0)["id"] == vid
    assert path.read_text(encoding="utf-8") == raw1
    assert "vi" not in json.loads(raw1)[0]


def test_failed_migration_leaves_source_intact(tmp_path, monkeypatch):
    path = tmp_path / "vocab.json"
    original = json.dumps([{"word": "huis", "vi": "house"}])
    path.write_text(original, encoding="utf-8")

    def boom(*_a, **_k):
        raise OSError("disk full")

    monkeypatch.setattr("os.replace", boom)
    store = VocabStore(str(path))
    # In-memory may be canonical for the session, but source file untouched.
    assert path.read_text(encoding="utf-8") == original
    assert entry_meaning(store.get(0)) == "house"


def test_rename_preserves_id_and_learning_state(tmp_path):
    folder = tmp_path / "nl"
    folder.mkdir()
    vocab = folder / "vocab.json"
    progress = folder / "progress.json"
    vocab.write_text(json.dumps([{"word": "huis", "vi": "house"}]), encoding="utf-8")
    store = VocabStore(str(vocab))
    vid = store.get(0)["id"]
    prog = Progress(str(progress))
    prog.record("huis", correct=True, vocab_id=vid)
    due = prog.data["words"][vid]["due_at"]
    assert store.update(0, "het huis", "the house")
    assert store.get(0)["id"] == vid
    assert store.get(0)["meaning"] == "the house"
    assert "vi" not in store.get(0)
    prog2 = Progress(str(progress))
    assert prog2.data["words"][vid]["due_at"] == due


def test_quiz_matching_same_before_after_canonicalization():
    legacy = {"nl": "de fiets", "vi": "xe đạp", "alt": ["rijwiel"]}
    canonical = normalize_entry_dict(legacy, assign_id=False)
    assert match_answer("de fiets", legacy)[0] == match_answer("de fiets", canonical)[0]
    assert match_answer("fiets", legacy)[0] == match_answer("fiets", canonical)[0]
    assert match_answer("rijwiel", legacy)[0] == match_answer("rijwiel", canonical)[0]


def test_library_search_on_canonical_meaning():
    vocab = [
        {"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "word": "huis", "meaning": "house"},
        {"id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", "word": "fiets", "meaning": "bicycle"},
    ]
    items = build_vocabulary_items(vocab, {}, [])
    found = filter_vocabulary_items(items, query="house", vocab_entries=vocab)
    assert [i.word for i in found] == ["huis"]


def test_add_writes_canonical_schema(tmp_path):
    path = tmp_path / "vocab.json"
    path.write_text("[]", encoding="utf-8")
    store = VocabStore(str(path))
    store.add("trein", "train", alternatives=["de trein"])
    raw = json.loads(path.read_text(encoding="utf-8"))[0]
    assert raw["meaning"] == "train"
    assert raw["alternatives"] == ["de trein"]
    assert "vi" not in raw
    assert "alt" not in raw
    assert is_vocab_id(raw["id"])


def test_wire_meaning_as_vi_keeps_http_shape():
    wire = wire_meaning_as_vi([{"word": "huis", "meaning": "house"}])
    assert wire == [{"word": "huis", "vi": "house"}]


def test_needs_schema_migration_flags():
    assert needs_schema_migration({"word": "a", "vi": "b"})
    assert needs_schema_migration({"word": "a", "meaning": "b", "alt": []})
    assert not needs_schema_migration({"word": "a", "meaning": "b"})


def test_normalize_vocab_list_changed_flag():
    entries, changed = normalize_vocab_list(
        [{"word": "a", "vi": "1"}], assign_ids=False
    )
    assert changed
    assert entries[0]["meaning"] == "1"
    entries2, changed2 = normalize_vocab_list(entries, assign_ids=False)
    assert not changed2
