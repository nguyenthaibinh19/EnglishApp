"""Phase 15B — enrichment draft, review, apply foundation."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from progress import Progress
from vocab_identity import entry_id, is_vocab_id
from vocab_store import VocabStore
from vocabulary_enrichment import (
    EnrichmentApplySelection,
    EnrichmentDraft,
    EnrichmentRequest,
    FakeEnrichmentProvider,
    VocabularyEnrichmentService,
    apply_enrichment,
    build_review_state,
    normalize_draft,
)
from vocabulary_model import (
    GrammaticalForms,
    PronunciationInfo,
    VocabularyExample,
    entry_examples,
    entry_forms,
    entry_part_of_speech,
    entry_pronunciation,
)

NOW = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)


def _store(tmp_path, rows=None) -> VocabStore:
    path = tmp_path / "vocab.json"
    path.write_text(json.dumps(rows or []), encoding="utf-8")
    return VocabStore(str(path))


def test_empty_and_partial_draft():
    empty = normalize_draft(EnrichmentDraft())
    assert not empty.has_suggestions()
    partial = normalize_draft(
        EnrichmentDraft(part_of_speech="verb", forms=GrammaticalForms(past="ging"))
    )
    assert partial.part_of_speech == "verb"
    assert partial.forms.past == "ging"
    assert partial.pronunciation is None
    assert partial.examples is None


def test_fake_provider_returns_draft_without_network():
    provider = FakeEnrichmentProvider(
        EnrichmentDraft(part_of_speech="noun", source="test")
    )
    service = VocabularyEnrichmentService(provider)
    draft = service.request_draft(
        EnrichmentRequest(
            vocab_id="id-1",
            word="huis",
            meaning="house",
            study_language="nl",
        )
    )
    assert draft.part_of_speech == "noun"
    assert len(provider.calls) == 1
    assert provider.calls[0].word == "huis"


def test_draft_creation_does_not_write_vocab_store(tmp_path):
    store = _store(tmp_path, [{"word": "huis", "meaning": "house"}])
    before = store.filename
    mtime = (tmp_path / "vocab.json").stat().st_mtime_ns
    service = VocabularyEnrichmentService(FakeEnrichmentProvider())
    entry = store.get(0)
    service.request_draft(
        EnrichmentRequest(
            vocab_id=entry_id(entry) or "",
            word=entry["word"],
            meaning=entry["meaning"],
            study_language="nl",
        )
    )
    assert (tmp_path / "vocab.json").stat().st_mtime_ns == mtime
    assert store.filename == before


def test_cancel_no_apply_leaves_entry_unchanged(tmp_path):
    store = _store(
        tmp_path,
        [
            {
                "word": "huis",
                "meaning": "house",
                "part_of_speech": "noun",
                "examples": [{"text": "Ik woon hier."}],
            }
        ],
    )
    original = dict(store.get(0))
    draft = EnrichmentDraft(
        part_of_speech="verb",
        pronunciation=PronunciationInfo(ipa="hœys"),
        source="test",
    )
    # Cancel = never call apply.
    assert store.get(0) == original
    assert apply_enrichment(
        store.get(0),
        draft,
        EnrichmentApplySelection(),  # nothing selected
    ) == {}


def test_apply_pos_preserves_id(tmp_path):
    store = _store(
        tmp_path,
        [{"word": "gaan", "meaning": "to go", "part_of_speech": "noun"}],
    )
    vid = entry_id(store.get(0))
    assert is_vocab_id(vid)
    service = VocabularyEnrichmentService(FakeEnrichmentProvider())
    draft = EnrichmentDraft(part_of_speech="verb", source="test")
    assert service.apply_to_store(
        store,
        0,
        draft,
        EnrichmentApplySelection(apply_part_of_speech=True),
    )
    assert entry_id(store.get(0)) == vid
    assert entry_part_of_speech(store.get(0)) == "verb"


def test_apply_forms_preserves_unspecified_existing_forms(tmp_path):
    store = _store(
        tmp_path,
        [
            {
                "word": "huis",
                "meaning": "house",
                "forms": {"plural": "huizen"},
            }
        ],
    )
    draft = EnrichmentDraft(forms=GrammaticalForms(past="x"), source="test")
    updates = apply_enrichment(
        store.get(0),
        draft,
        EnrichmentApplySelection(form_keys=("past",)),
    )
    assert updates["forms"]["plural"] == "huizen"
    assert updates["forms"]["past"] == "x"
    service = VocabularyEnrichmentService(FakeEnrichmentProvider())
    service.apply_to_store(
        store, 0, draft, EnrichmentApplySelection(form_keys=("past",))
    )
    forms = entry_forms(store.get(0)).as_dict()
    assert forms["plural"] == "huizen"
    assert forms["past"] == "x"


def test_ipa_requires_explicit_selection_and_unselected_survives(tmp_path):
    store = _store(
        tmp_path,
        [
            {
                "word": "huis",
                "meaning": "house",
                "pronunciation": {"ipa": "old"},
            }
        ],
    )
    draft = EnrichmentDraft(
        pronunciation=PronunciationInfo(ipa="new"), source="test"
    )
    # No selection → no IPA update kwargs.
    assert "pronunciation" not in apply_enrichment(
        store.get(0), draft, EnrichmentApplySelection()
    )
    VocabularyEnrichmentService(FakeEnrichmentProvider()).apply_to_store(
        store, 0, draft, EnrichmentApplySelection()
    )
    assert entry_pronunciation(store.get(0)).ipa == "old"

    VocabularyEnrichmentService(FakeEnrichmentProvider()).apply_to_store(
        store,
        0,
        draft,
        EnrichmentApplySelection(apply_pronunciation=True),
    )
    assert entry_pronunciation(store.get(0)).ipa == "new"


def test_accepted_example_appends_preserves_order_dedupes(tmp_path):
    store = _store(
        tmp_path,
        [
            {
                "word": "huis",
                "meaning": "house",
                "examples": [
                    {"text": "First."},
                    {"text": "Second."},
                ],
            }
        ],
    )
    draft = EnrichmentDraft(
        examples=(
            VocabularyExample(text="First."),  # duplicate
            VocabularyExample(text="Third."),
            VocabularyExample(text="Fourth."),
        ),
        source="test",
    )
    updates = apply_enrichment(
        store.get(0),
        draft,
        EnrichmentApplySelection(example_indices=(0, 1, 2)),
    )
    texts = [item["text"] for item in updates["examples"]]
    assert texts == ["First.", "Second.", "Third.", "Fourth."]

    VocabularyEnrichmentService(FakeEnrichmentProvider()).apply_to_store(
        store, 0, draft, EnrichmentApplySelection(example_indices=(1,))
    )
    texts = [e.text for e in entry_examples(store.get(0))]
    assert texts == ["First.", "Second.", "Third."]


def test_selective_apply_does_not_overwrite_unrelated_or_missing_fields(tmp_path):
    store = _store(
        tmp_path,
        [
            {
                "word": "go",
                "meaning": "đi",
                "part_of_speech": "verb",
                "pronunciation": {"ipa": "goʊ"},
                "forms": {"past": "went"},
                "examples": [{"text": "I go."}],
                "note": "keep me",
            }
        ],
    )
    draft = EnrichmentDraft(
        part_of_speech="noun",
        pronunciation=PronunciationInfo(ipa="changed"),
        forms=GrammaticalForms(past="goed", plural="goes"),
        examples=(VocabularyExample(text="We go."),),
        source="test",
    )
    # Apply only plural form.
    VocabularyEnrichmentService(FakeEnrichmentProvider()).apply_to_store(
        store, 0, draft, EnrichmentApplySelection(form_keys=("plural",))
    )
    entry = store.get(0)
    assert entry_part_of_speech(entry) == "verb"
    assert entry_pronunciation(entry).ipa == "goʊ"
    assert entry_forms(entry).as_dict() == {"past": "went", "plural": "goes"}
    assert [e.text for e in entry_examples(entry)] == ["I go."]
    assert entry.get("note") == "keep me"


def test_missing_draft_field_does_not_clear_canonical(tmp_path):
    store = _store(
        tmp_path,
        [
            {
                "word": "huis",
                "meaning": "house",
                "part_of_speech": "noun",
                "pronunciation": {"ipa": "hœys"},
                "forms": {"plural": "huizen"},
            }
        ],
    )
    draft = EnrichmentDraft(examples=(VocabularyExample(text="Nieuw."),), source="test")
    VocabularyEnrichmentService(FakeEnrichmentProvider()).apply_to_store(
        store, 0, draft, EnrichmentApplySelection(example_indices=(0,))
    )
    entry = store.get(0)
    assert entry_part_of_speech(entry) == "noun"
    assert entry_pronunciation(entry).ipa == "hœys"
    assert entry_forms(entry).plural == "huizen"


def test_apply_through_vocab_store_persists(tmp_path):
    store = _store(tmp_path, [{"word": "huis", "meaning": "house"}])
    draft = EnrichmentDraft(
        part_of_speech="noun",
        pronunciation=PronunciationInfo(ipa="hœys"),
        forms=GrammaticalForms(plural="huizen"),
        examples=(VocabularyExample(text="Ik woon in een huis."),),
        source="test",
    )
    VocabularyEnrichmentService(FakeEnrichmentProvider()).apply_to_store(
        store,
        0,
        draft,
        EnrichmentApplySelection(
            apply_part_of_speech=True,
            apply_pronunciation=True,
            form_keys=("plural",),
            example_indices=(0,),
        ),
    )
    reloaded = VocabStore(store.filename).get(0)
    assert reloaded["part_of_speech"] == "noun"
    assert reloaded["pronunciation"] == {"ipa": "hœys"}
    assert reloaded["forms"] == {"plural": "huizen"}
    assert reloaded["examples"] == [{"text": "Ik woon in een huis."}]


def test_progress_srs_attempts_unchanged_on_enrich(tmp_path):
    vocab_path = tmp_path / "nl" / "vocab.json"
    progress_path = tmp_path / "nl" / "progress.json"
    attempts_path = tmp_path / "nl" / "attempts.jsonl"
    vocab_path.parent.mkdir(parents=True)
    vid = "11111111-1111-4111-8111-111111111111"
    vocab_path.write_text(
        json.dumps([{"id": vid, "word": "huis", "meaning": "house"}]),
        encoding="utf-8",
    )
    progress_payload = {
        "version": 3,
        "words": {
            vid: {
                "seen": 2,
                "correct": 1,
                "wrong": 1,
                "streak": 1,
                "last_seen": NOW.isoformat(),
                "interval_days": 3,
                "due_at": NOW.isoformat(),
            }
        },
        "legacy_index": {},
    }
    progress_path.write_text(json.dumps(progress_payload), encoding="utf-8")
    attempts_path.write_text(
        json.dumps(
            {
                "vocab_id": vid,
                "word": "huis",
                "correct": True,
                "timestamp": NOW.isoformat(),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    # Load once so any identity-normalization rewrite settles before measuring.
    store = VocabStore(str(vocab_path))
    progress_before = json.loads(progress_path.read_text(encoding="utf-8"))
    attempts_before = attempts_path.read_text(encoding="utf-8")
    word_before = progress_before["words"][vid]

    draft = EnrichmentDraft(part_of_speech="noun", source="test")
    VocabularyEnrichmentService(FakeEnrichmentProvider()).apply_to_store(
        store,
        0,
        draft,
        EnrichmentApplySelection(apply_part_of_speech=True),
    )
    progress_after = json.loads(progress_path.read_text(encoding="utf-8"))
    assert progress_after["words"][vid] == word_before
    assert attempts_path.read_text(encoding="utf-8") == attempts_before
    assert entry_id(store.get(0)) == vid


def test_rename_still_preserves_uuid_after_enrichment_path(tmp_path):
    store = _store(tmp_path, [{"word": "huis", "meaning": "house"}])
    vid = entry_id(store.get(0))
    draft = EnrichmentDraft(part_of_speech="noun", source="test")
    VocabularyEnrichmentService(FakeEnrichmentProvider()).apply_to_store(
        store,
        0,
        draft,
        EnrichmentApplySelection(apply_part_of_speech=True),
    )
    assert store.update(0, "het huis", "house", part_of_speech="noun")
    assert entry_id(store.get(0)) == vid
    assert store.get(0)["word"] == "het huis"


def test_multi_language_storage_isolated(tmp_path):
    nl = tmp_path / "nl" / "vocab.json"
    de = tmp_path / "de" / "vocab.json"
    nl.parent.mkdir()
    de.parent.mkdir()
    nl.write_text(json.dumps([{"word": "huis", "meaning": "house"}]), encoding="utf-8")
    de.write_text(json.dumps([{"word": "Haus", "meaning": "house"}]), encoding="utf-8")
    nl_store = VocabStore(str(nl))
    de_store = VocabStore(str(de))
    draft = EnrichmentDraft(forms=GrammaticalForms(plural="huizen"), source="test")
    VocabularyEnrichmentService(FakeEnrichmentProvider()).apply_to_store(
        nl_store, 0, draft, EnrichmentApplySelection(form_keys=("plural",))
    )
    assert "forms" in nl_store.get(0)
    assert "forms" not in de_store.get(0)
    assert VocabStore(str(de)).get(0).get("forms") is None


def test_review_state_only_shows_present_suggestions():
    entry = {
        "word": "go",
        "meaning": "đi",
        "part_of_speech": "verb",
        "forms": {"past": "went"},
    }
    draft = EnrichmentDraft(
        forms=GrammaticalForms(past_participle="gone"),
        pronunciation=PronunciationInfo(ipa="goʊ"),
        source="test",
    )
    state = build_review_state(entry, draft)
    assert state.part_of_speech is None
    assert state.pronunciation is not None
    assert state.pronunciation.current == "—"
    assert [item.target for item in state.forms] == ["past_participle"]
    assert state.forms[0].current == "—"
    selection = state.to_selection()
    assert selection.apply_pronunciation is True
    assert selection.form_keys == ("past_participle",)


def test_legacy_single_example_edit_preserves_additional_examples(tmp_path):
    """Regression: editing the single example field must not drop examples[1:]."""
    store = _store(
        tmp_path,
        [
            {
                "word": "huis",
                "meaning": "house",
                "examples": [
                    {"text": "First example.", "meaning": "A"},
                    {"text": "Second example."},
                    {"text": "Third example."},
                ],
            }
        ],
    )
    vid = entry_id(store.get(0))
    assert store.update(
        0,
        "huis",
        "house",
        example="Updated first example.",
    )
    entry = store.get(0)
    assert entry_id(entry) == vid
    assert entry["examples"] == [
        {"text": "Updated first example.", "meaning": "A"},
        {"text": "Second example."},
        {"text": "Third example."},
    ]
    # Clearing first example text keeps the remaining structured examples.
    assert store.update(0, "huis", "house", example="")
    assert [e["text"] for e in store.get(0)["examples"]] == [
        "Second example.",
        "Third example.",
    ]
