"""Phase 15C — production AI vocabulary enrichment (no live OpenAI / VPS)."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer

import account_server
import account_store
import ai_teacher
import config
from ai.base import (
    AIError,
    AIProvider,
    GradeRequest,
    GradeResult,
    ReadingRequest,
    VocabularyEnrichmentAIRequest,
    VocabularyEnrichmentAIResult,
    sanitize_enrichment_ai_payload,
)
from ai.service import AIService, set_service
from vocab_identity import entry_id
from vocab_store import VocabStore
from vocabulary_enrichment import (
    AccountServerVocabularyEnrichmentProvider,
    EnrichmentApplySelection,
    EnrichmentDraft,
    EnrichmentError,
    EnrichmentRequest,
    VocabularyEnrichmentService,
    apply_enrichment,
    draft_from_ai_result,
)
from vocabulary_model import GrammaticalForms, VocabularyExample

NOW = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)


class RecordingAIProvider(AIProvider):
    def __init__(self, result: VocabularyEnrichmentAIResult = None, error: Exception = None):
        self.result = result or VocabularyEnrichmentAIResult(
            part_of_speech="verb",
            forms={"past": "vergat", "past_participle": "vergeten"},
            examples=(
                {
                    "text": "Ik vergeet vaak mijn sleutels.",
                    "meaning": "I often forget my keys.",
                },
            ),
        )
        self.error = error
        self.enrich_calls = []

    def grade_answer(self, request: GradeRequest) -> GradeResult:
        raise AssertionError("grade not used")

    def generate_reading(self, request: ReadingRequest) -> dict:
        raise AssertionError("reading not used")

    def enrich_vocabulary(
        self, request: VocabularyEnrichmentAIRequest
    ) -> VocabularyEnrichmentAIResult:
        self.enrich_calls.append(request)
        if self.error is not None:
            raise self.error
        return self.result


def _store(tmp_path, rows=None) -> VocabStore:
    path = tmp_path / "vocab.json"
    path.write_text(json.dumps(rows or []), encoding="utf-8")
    return VocabStore(str(path))


def test_sanitize_pos_forms_examples_and_limits():
    result = sanitize_enrichment_ai_payload(
        {
            "part_of_speech": "VERB",
            "forms": {
                "past": "went",
                "unknown_form": "nope",
                "plural": " " ,
            },
            "examples": [
                {"text": "One.", "meaning": "1"},
                {"text": "Two."},
                {"text": "Three should be dropped."},
            ],
            "pronunciation": {"ipa": "must-not-pass"},
            "cefr": "B1",
        }
    )
    assert result.part_of_speech == "verb"
    assert result.forms == {"past": "went"}
    assert len(result.examples) == 2
    assert "pronunciation" not in result.as_dict()
    assert "cefr" not in result.as_dict()


def test_unsupported_pos_omitted_and_malformed_rejected():
    empty_pos = sanitize_enrichment_ai_payload({"part_of_speech": "preposition"})
    assert empty_pos.part_of_speech == ""
    try:
        sanitize_enrichment_ai_payload(["not", "an", "object"])
        assert False, "expected AIError"
    except AIError:
        pass


def test_aiservice_delegates_enrich_to_provider():
    fake = RecordingAIProvider()
    set_service(AIService(provider=fake))
    try:
        result = ai_teacher.enrich_vocabulary(
            "vergeten",
            "to forget",
            part_of_speech="verb",
            profile={
                "code": "nl",
                "name_en": "Dutch",
                "name_vi": "tiếng Hà Lan",
                "articles": (),
                "elisions": (),
            },
            native_label="English",
        )
        assert result["part_of_speech"] == "verb"
        assert result["forms"]["past"] == "vergat"
        assert fake.enrich_calls[0].word == "vergeten"
        assert fake.enrich_calls[0].study_language.code == "nl"
        assert fake.enrich_calls[0].native_label == "English"
    finally:
        set_service(None)


def test_draft_from_ai_result_omits_ipa_and_sets_source_ai():
    draft = draft_from_ai_result(
        {
            "part_of_speech": "noun",
            "forms": {"plural": "huizen"},
            "examples": [{"text": "Een huis.", "meaning": "A house."}],
            "pronunciation": {"ipa": "/hœys/"},
        }
    )
    assert draft.source == "ai"
    assert draft.part_of_speech == "noun"
    assert draft.forms.plural == "huizen"
    assert draft.pronunciation is None or draft.pronunciation.ipa == ""
    assert draft.examples[0].text == "Een huis."


def test_desktop_provider_maps_request_via_account_client(monkeypatch):
    captured = {}

    def fake_enrich(word, meaning, part_of_speech="", language_code=None, native_language=None):
        captured["payload"] = {
            "word": word,
            "meaning": meaning,
            "part_of_speech": part_of_speech,
            "language": language_code,
            "native": native_language,
        }
        return {
            "part_of_speech": "verb",
            "forms": {"past": "vergat"},
            "examples": [{"text": "Ik vergeet het.", "meaning": "I forget it."}],
        }

    monkeypatch.setattr(config, "uses_account_server", lambda: True)
    monkeypatch.setattr("account_client.enrich_vocabulary", fake_enrich)

    provider = AccountServerVocabularyEnrichmentProvider()
    draft = provider.enrich(
        EnrichmentRequest(
            vocab_id="vid",
            word="vergeten",
            meaning="to forget",
            study_language="nl",
            native_language="en",
            part_of_speech="verb",
        )
    )
    assert captured["payload"]["language"] == "nl"
    assert captured["payload"]["native"] == "en"
    assert captured["payload"]["word"] == "vergeten"
    assert draft.source == "ai"
    assert draft.part_of_speech == "verb"


def test_desktop_provider_dev_direct_openai_path(monkeypatch):
    fake = RecordingAIProvider()
    set_service(AIService(provider=fake))
    monkeypatch.setattr(config, "uses_account_server", lambda: False)
    try:
        provider = AccountServerVocabularyEnrichmentProvider()
        draft = provider.enrich(
            EnrichmentRequest(
                vocab_id="vid",
                word="huis",
                meaning="house",
                study_language="nl",
                native_language="vi",
            )
        )
        assert draft.part_of_speech == "verb"
        assert fake.enrich_calls[0].native_label == "Tiếng Việt"
        assert fake.enrich_calls[0].study_language.code == "nl"
    finally:
        set_service(None)


def test_successful_ai_response_does_not_write_before_apply(tmp_path, monkeypatch):
    store = _store(tmp_path, [{"word": "huis", "meaning": "house"}])
    mtime = (tmp_path / "vocab.json").stat().st_mtime_ns
    monkeypatch.setattr(config, "uses_account_server", lambda: True)
    monkeypatch.setattr(
        "account_client.enrich_vocabulary",
        lambda *a, **k: {"part_of_speech": "noun", "forms": {"plural": "huizen"}},
    )
    draft = AccountServerVocabularyEnrichmentProvider().enrich(
        EnrichmentRequest(
            vocab_id=entry_id(store.get(0)) or "",
            word="huis",
            meaning="house",
            study_language="nl",
            native_language="en",
        )
    )
    assert draft.has_suggestions()
    assert (tmp_path / "vocab.json").stat().st_mtime_ns == mtime
    assert "part_of_speech" not in store.get(0)


def test_network_failure_causes_no_vocab_mutation(tmp_path, monkeypatch):
    store = _store(
        tmp_path,
        [{"word": "huis", "meaning": "house", "part_of_speech": "noun"}],
    )
    original = dict(store.get(0))
    monkeypatch.setattr(config, "uses_account_server", lambda: True)

    def boom(*_a, **_k):
        from account_client import AccountError

        raise AccountError("Couldn't reach the account server.")

    monkeypatch.setattr("account_client.enrich_vocabulary", boom)
    try:
        AccountServerVocabularyEnrichmentProvider().enrich(
            EnrichmentRequest(
                vocab_id=entry_id(store.get(0)) or "",
                word="huis",
                meaning="house",
                study_language="nl",
                native_language="en",
            )
        )
        assert False, "expected EnrichmentError"
    except EnrichmentError:
        pass
    assert store.get(0) == original


def test_cancel_and_unselected_fields_preserve_canonical(tmp_path):
    store = _store(
        tmp_path,
        [
            {
                "word": "go",
                "meaning": "đi",
                "part_of_speech": "verb",
                "forms": {"past": "went"},
                "examples": [{"text": "I go."}],
            }
        ],
    )
    vid = entry_id(store.get(0))
    draft = EnrichmentDraft(
        part_of_speech="noun",
        forms=GrammaticalForms(past="goed", plural="goes"),
        examples=(VocabularyExample(text="We go."),),
        source="ai",
    )
    # Cancel / nothing selected.
    assert apply_enrichment(store.get(0), draft, EnrichmentApplySelection()) == {}
    # Apply only plural.
    VocabularyEnrichmentService(
        AccountServerVocabularyEnrichmentProvider()
    ).apply_to_store(
        store, 0, draft, EnrichmentApplySelection(form_keys=("plural",))
    )
    entry = store.get(0)
    assert entry_id(entry) == vid
    assert entry["part_of_speech"] == "verb"
    assert entry["forms"]["past"] == "went"
    assert entry["forms"]["plural"] == "goes"
    assert entry["examples"] == [{"text": "I go."}]


def test_explicit_apply_persists_selected_enrichment(tmp_path):
    store = _store(tmp_path, [{"word": "huis", "meaning": "house"}])
    vid = entry_id(store.get(0))
    draft = draft_from_ai_result(
        {
            "part_of_speech": "noun",
            "forms": {"plural": "huizen"},
            "examples": [{"text": "Ik woon in een huis.", "meaning": "I live in a house."}],
        }
    )
    VocabularyEnrichmentService(
        AccountServerVocabularyEnrichmentProvider()
    ).apply_to_store(
        store,
        0,
        draft,
        EnrichmentApplySelection(
            apply_part_of_speech=True,
            form_keys=("plural",),
            example_indices=(0,),
        ),
    )
    reloaded = VocabStore(store.filename).get(0)
    assert entry_id(reloaded) == vid
    assert reloaded["part_of_speech"] == "noun"
    assert reloaded["forms"] == {"plural": "huizen"}
    assert reloaded["examples"][0]["text"] == "Ik woon in een huis."


def test_progress_attempts_unchanged_and_languages_isolated(tmp_path, monkeypatch):
    nl = tmp_path / "nl"
    de = tmp_path / "de"
    nl.mkdir()
    de.mkdir()
    vid = "11111111-1111-4111-8111-111111111111"
    (nl / "vocab.json").write_text(
        json.dumps([{"id": vid, "word": "huis", "meaning": "house"}]),
        encoding="utf-8",
    )
    (de / "vocab.json").write_text(
        json.dumps([{"word": "Haus", "meaning": "house"}]),
        encoding="utf-8",
    )
    progress_path = nl / "progress.json"
    attempts_path = nl / "attempts.jsonl"
    progress_path.write_text(
        json.dumps(
            {
                "version": 3,
                "words": {
                    vid: {
                        "seen": 1,
                        "correct": 1,
                        "wrong": 0,
                        "streak": 1,
                        "last_seen": NOW.isoformat(),
                        "interval_days": 1,
                        "due_at": NOW.isoformat(),
                    }
                },
                "legacy_index": {},
            }
        ),
        encoding="utf-8",
    )
    attempts_path.write_text(
        json.dumps({"vocab_id": vid, "word": "huis", "correct": True}) + "\n",
        encoding="utf-8",
    )
    nl_store = VocabStore(str(nl / "vocab.json"))
    de_store = VocabStore(str(de / "vocab.json"))
    progress_before = json.loads(progress_path.read_text(encoding="utf-8"))["words"][vid]
    attempts_before = attempts_path.read_text(encoding="utf-8")

    draft = draft_from_ai_result({"part_of_speech": "noun", "forms": {"plural": "huizen"}})
    VocabularyEnrichmentService(
        AccountServerVocabularyEnrichmentProvider()
    ).apply_to_store(
        nl_store,
        0,
        draft,
        EnrichmentApplySelection(apply_part_of_speech=True, form_keys=("plural",)),
    )
    assert json.loads(progress_path.read_text(encoding="utf-8"))["words"][vid] == progress_before
    assert attempts_path.read_text(encoding="utf-8") == attempts_before
    assert "forms" not in de_store.get(0)
    assert entry_id(nl_store.get(0)) == vid


def test_account_enrich_endpoint_requires_auth_and_delegates(tmp_path, monkeypatch):
    folder_path = tmp_path / "accounts"
    folder_path.mkdir()
    folder = str(folder_path)
    account_store.add_user("learner", "secret1", folder=folder)
    token = account_store.login("learner", "secret1", folder=folder)

    enrich_calls = []

    def fake_enrich(word, meaning, part_of_speech="", profile=None, native_label=None):
        enrich_calls.append(
            {
                "word": word,
                "meaning": meaning,
                "part_of_speech": part_of_speech,
                "profile": profile,
                "native_label": native_label,
            }
        )
        return {
            "part_of_speech": "verb",
            "forms": {"past": "vergat"},
            "examples": [{"text": "Ik vergeet het.", "meaning": "I forget it."}],
        }

    monkeypatch.setattr(ai_teacher, "enrich_vocabulary", fake_enrich)
    original_user_for_token = account_store.user_for_token

    def user_for_token_tmp(token_value, folder_arg=None):
        return original_user_for_token(token_value, folder=folder)

    monkeypatch.setattr(account_store, "user_for_token", user_for_token_tmp)

    server = ThreadingHTTPServer(("127.0.0.1", 0), account_server.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        import urllib.error
        import urllib.request

        def post(path, payload, auth=None):
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}{path}", data=data, method="POST"
            )
            req.add_header("Content-Type", "application/json")
            if auth:
                req.add_header("Authorization", "Bearer " + auth)
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status, json.loads(response.read().decode("utf-8"))

        try:
            post(
                "/api/enrich",
                {
                    "word": "vergeten",
                    "meaning": "to forget",
                    "language": "nl",
                    "native": "en",
                },
            )
            assert False, "expected 401"
        except urllib.error.HTTPError as error:
            assert error.code == 401

        status, body = post(
            "/api/enrich",
            {
                "word": "vergeten",
                "meaning": "to forget",
                "part_of_speech": "verb",
                "language": "nl",
                "native": "en",
            },
            auth=token,
        )
        assert status == 200
        assert body["part_of_speech"] == "verb"
        assert "api_key" not in body
        assert enrich_calls[0]["word"] == "vergeten"
        assert enrich_calls[0]["native_label"] == "English"
        assert enrich_calls[0]["profile"]["code"] == "nl"
    finally:
        server.shutdown()
        server.server_close()


def test_server_enrich_rejects_empty_word():
    try:
        account_server._enrich({"word": "", "meaning": "x", "language": "nl", "native": "en"})
        assert False, "expected ValueError"
    except ValueError:
        pass
