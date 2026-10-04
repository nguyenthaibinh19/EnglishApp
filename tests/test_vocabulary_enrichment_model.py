"""Phase 15A — vocabulary enrichment storage/domain model."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from progress import Progress
from text_utils import match_answer
from vocab_identity import is_vocab_id
from vocab_store import VocabStore
from vocabulary_library import build_vocabulary_detail, build_vocabulary_items, filter_vocabulary_items
from vocabulary_model import (
    GrammaticalForms,
    PronunciationInfo,
    VocabularyEntry,
    VocabularyExample,
    entry_example,
    entry_examples,
    entry_to_storage_dict,
    needs_schema_migration,
    normalize_entry_dict,
    vocabulary_entry_from_dict,
)

NOW = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)


def test_entry_without_enrichment_remains_valid():
    entry = vocabulary_entry_from_dict({"word": "huis", "meaning": "house"})
    assert entry is not None
    assert entry.examples == ()
    assert entry.pronunciation.ipa == ""
    assert entry.forms.to_storage_dict() is None
    stored = entry_to_storage_dict(entry)
    assert "examples" not in stored
    assert "pronunciation" not in stored
    assert "forms" not in stored


def test_structured_examples_round_trip_and_order(tmp_path):
    path = tmp_path / "vocab.json"
    path.write_text("[]", encoding="utf-8")
    store = VocabStore(str(path))
    assert store.add(
        "huis",
        "house",
        examples=[
            {"text": "Ik woon in een huis.", "meaning": "I live in a house."},
            {"text": "Het huis is groot."},
        ],
    )
    entry = store.get(0)
    assert entry["examples"][0]["text"] == "Ik woon in een huis."
    assert entry["examples"][0]["meaning"] == "I live in a house."
    assert entry["examples"][1] == {"text": "Het huis is groot."}
    assert "example" not in entry
    reloaded = VocabStore(str(path)).get(0)
    assert reloaded["examples"] == entry["examples"]


def test_example_meaning_optional():
    examples = entry_examples(
        {"word": "x", "meaning": "y", "examples": [{"text": "Hello."}]}
    )
    assert examples == [VocabularyExample(text="Hello.")]


def test_legacy_example_migrates_and_canonical_wins(tmp_path):
    path = tmp_path / "vocab.json"
    path.write_text(
        json.dumps([{"word": "huis", "meaning": "house", "example": "Oud voorbeeld."}]),
        encoding="utf-8",
    )
    store = VocabStore(str(path))
    assert store.get(0)["examples"] == [{"text": "Oud voorbeeld."}]
    assert "example" not in store.get(0)
    raw = json.loads(path.read_text(encoding="utf-8"))[0]
    assert "example" not in raw

    both = normalize_entry_dict(
        {
            "word": "huis",
            "meaning": "house",
            "example": "legacy",
            "examples": [{"text": "canonical", "meaning": "c"}],
        },
        assign_id=False,
    )
    assert both["examples"] == [{"text": "canonical", "meaning": "c"}]


def test_example_migration_idempotent(tmp_path):
    path = tmp_path / "vocab.json"
    path.write_text(
        json.dumps([{"word": "huis", "meaning": "house", "example": "Een huis."}]),
        encoding="utf-8",
    )
    first = VocabStore(str(path))
    text1 = path.read_text(encoding="utf-8")
    vid = first.get(0)["id"]
    second = VocabStore(str(path))
    assert second.get(0)["id"] == vid
    assert path.read_text(encoding="utf-8") == text1


def test_ipa_round_trip_and_empty_pronunciation_omitted(tmp_path):
    path = tmp_path / "vocab.json"
    path.write_text("[]", encoding="utf-8")
    store = VocabStore(str(path))
    store.add("huis", "house", pronunciation={"ipa": "ɦœys"})
    assert store.get(0)["pronunciation"] == {"ipa": "ɦœys"}
    store.add("fiets", "bike", pronunciation={"ipa": ""})
    fiets = [e for e in store.all() if e["word"] == "fiets"][0]
    assert "pronunciation" not in fiets


def test_forms_round_trip_only_populated(tmp_path):
    path = tmp_path / "vocab.json"
    path.write_text("[]", encoding="utf-8")
    store = VocabStore(str(path))
    store.add(
        "go",
        "đi",
        forms={
            "past": "went",
            "past_participle": "gone",
            "plural": "",
            "comparative": None,
        },
    )
    entry = store.get(0)
    assert entry["forms"] == {"past": "went", "past_participle": "gone"}
    assert "plural" not in entry["forms"]


def test_phase14_vocab_loads_and_uuid_survives_enrichment_migration(tmp_path):
    path = tmp_path / "vocab.json"
    fixed_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    path.write_text(
        json.dumps(
            [
                {
                    "id": fixed_id,
                    "word": "huis",
                    "meaning": "house",
                    "alternatives": ["home"],
                    "example": "Het huis.",
                    "note": "n",
                    "part_of_speech": "noun",
                }
            ]
        ),
        encoding="utf-8",
    )
    store = VocabStore(str(path))
    entry = store.get(0)
    assert entry["id"] == fixed_id
    assert entry["meaning"] == "house"
    assert entry["alternatives"] == ["home"]
    assert entry["examples"] == [{"text": "Het huis."}]
    assert entry["part_of_speech"] == "noun"


def test_rename_preserves_uuid_and_learning_history(tmp_path):
    folder = tmp_path / "nl"
    folder.mkdir()
    vocab = folder / "vocab.json"
    progress = folder / "progress.json"
    vocab.write_text(
        json.dumps([{"word": "huis", "meaning": "house", "example": "Een huis."}]),
        encoding="utf-8",
    )
    store = VocabStore(str(vocab))
    vid = store.get(0)["id"]
    prog = Progress(str(progress))
    prog.record("huis", correct=True, vocab_id=vid, reviewed_at=NOW)
    due = prog.data["words"][vid]["due_at"]
    assert store.update(0, "het huis", "the house")
    assert store.get(0)["id"] == vid
    assert store.get(0)["examples"] == [{"text": "Een huis."}]
    assert Progress(str(progress)).data["words"][vid]["due_at"] == due


def test_quiz_matching_unchanged_with_enrichment():
    legacy = {"word": "de fiets", "meaning": "xe đạp", "alternatives": ["rijwiel"]}
    enriched = normalize_entry_dict(
        {
            **legacy,
            "examples": [{"text": "Ik fiets."}],
            "pronunciation": {"ipa": "fits"},
            "forms": {"plural": "fietsen"},
        },
        assign_id=False,
    )
    assert match_answer("fiets", legacy)[0] == match_answer("fiets", enriched)[0]
    assert match_answer("rijwiel", enriched)[0] == "exact"


def test_library_detail_and_search_consume_examples():
    entry = {
        "id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        "word": "huis",
        "meaning": "house",
        "examples": [{"text": "Ik woon in een klein huis.", "meaning": "I live..."}],
        "pronunciation": {"ipa": "ɦœys"},
        "forms": {"plural": "huizen"},
    }
    detail = build_vocabulary_detail(
        entry,
        0,
        language_code="nl",
        progress_words={},
        attempts=[],
        mistake_summaries=[],
        now=NOW,
    )
    assert detail.example == "Ik woon in een klein huis."
    assert detail.examples[0].meaning == "I live..."
    assert detail.pronunciation_ipa == "ɦœys"
    assert detail.forms == (("plural", "huizen"),)

    items = build_vocabulary_items([entry], {}, [], now=NOW)
    found = filter_vocabulary_items(items, query="klein huis", vocab_entries=[entry])
    assert [i.word for i in found] == ["huis"]


def test_failed_migration_leaves_source_intact(tmp_path, monkeypatch):
    path = tmp_path / "vocab.json"
    original = json.dumps([{"word": "huis", "meaning": "house", "example": "X"}])
    path.write_text(original, encoding="utf-8")

    def boom(*_a, **_k):
        raise OSError("disk full")

    monkeypatch.setattr("os.replace", boom)
    store = VocabStore(str(path))
    assert path.read_text(encoding="utf-8") == original
    assert entry_example(store.get(0)) == "X"


def test_needs_schema_migration_flags_legacy_example():
    assert needs_schema_migration({"word": "a", "meaning": "b", "example": "c"})
    assert not needs_schema_migration(
        {"word": "a", "meaning": "b", "examples": [{"text": "c"}]}
    )


def test_vocabulary_entry_dataclass_shape():
    entry = VocabularyEntry(
        id="cccccccc-cccc-cccc-cccc-cccccccccccc",
        word="go",
        meaning="đi",
        examples=(VocabularyExample(text="I go.", meaning="Tôi đi."),),
        pronunciation=PronunciationInfo(ipa="ɡoʊ"),
        forms=GrammaticalForms(past="went", past_participle="gone"),
    )
    stored = entry_to_storage_dict(entry)
    assert stored["examples"][0]["meaning"] == "Tôi đi."
    assert stored["pronunciation"]["ipa"] == "ɡoʊ"
    assert stored["forms"] == {"past": "went", "past_participle": "gone"}
    assert is_vocab_id(stored["id"])
