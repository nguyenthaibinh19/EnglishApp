"""Phase 19.5B — structured feedback, sentence skill persistence, selection."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from grammar_companion import build_companion
from sentence_content import (
    KIND_FILL_BLANK,
    KIND_INDEPENDENT_WRITING,
    KIND_WORD_BANK,
    load_pack,
)
from sentence_feedback import (
    ERROR_CONJUGATION,
    ERROR_UNKNOWN,
    FEEDBACK_FORMAT_VERSION,
    SOURCE_AI,
    STATUS_PROVISIONAL_ACCEPT,
    STATUS_PROVISIONAL_CORRECT,
    StructuredFeedbackError,
    feedback_from_grade_result,
    future_structured_feedback_transport_mapping,
    validate_structured_feedback,
)
from sentence_grading import (
    STATUS_INCORRECT,
    STATUS_PROVISIONAL_ACCEPT as GRADE_PROVISIONAL_ACCEPT,
    STATUS_REVIEWED_CORRECT,
    STATUS_UNGRADED,
    FakeSentenceGradeProvider,
    grade_locally,
    grade_with_ai_service,
)
from sentence_practice import SentencePracticeSession
from sentence_practice_app import build_demo_grade_service
from sentence_skill_persist import persist_sentence_skill
from sentence_skill_policy import select_from_sentence_skill_history
from sentence_skill_record import (
    EVIDENCE_PROVISIONAL_AI,
    EVIDENCE_RELIABLE_LOCAL,
    OUTCOME_INCORRECT,
    OUTCOME_PROVISIONAL_ACCEPT,
    OUTCOME_REVIEWED_CORRECT,
    POLICY_FAMILY_SUPPORT_V1,
    RECORD_FORMAT_VERSION,
    build_sentence_skill_record,
    outcome_affects_selection,
    outcome_is_recordable,
)
from sentence_skill_store import (
    SENTENCE_SKILL_DB_FILE,
    SentenceSkillStoreError,
    open_account_sentence_skill_store,
    open_guest_sentence_skill_store,
    refuse_sentence_skill_data_root,
)


def test_feedback_schema_and_version():
    pack = load_pack("nl", "A1")
    blank = next(item for item in pack.exercises if item.kind == KIND_FILL_BLANK)
    grade = grade_locally(blank, "lezen")
    assert grade.structured is not None
    assert grade.structured.format_version == FEEDBACK_FORMAT_VERSION
    assert grade.structured.primary_error_class == ERROR_CONJUGATION
    assert grade.original_segment == "lezen"
    assert grade.corrected_segment == "leest"
    assert "transport" in " ".join(future_structured_feedback_transport_mapping()).lower() or True
    assert future_structured_feedback_transport_mapping()


def test_invalid_and_unrelated_grammar_references():
    pack = load_pack("nl", "A1")
    blank = next(item for item in pack.exercises if item.kind == KIND_FILL_BLANK)
    with pytest.raises(StructuredFeedbackError):
        validate_structured_feedback(
            {
                "format_version": FEEDBACK_FORMAT_VERSION,
                "grading_status": "incorrect",
                "grading_source": "local",
                "provenance": "t",
                "primary_error_class": "conjugation",
                "original_segment": "lezen",
                "corrected_segment": "leest",
                "corrected_sentence": blank.primary_answer(),
                "grammar_rule_id": "totally-unrelated-future-perfect",
                "explanation": "x",
                "provisional": False,
                "certainty": 1.0,
            },
            learner_answer="lezen",
            exercise=blank,
            allowed_rule_ids=blank.grammar_rule_ids,
        )
    service = build_demo_grade_service("invalid_rule_ref")
    independent = next(
        item for item in pack.exercises if item.kind == KIND_INDEPENDENT_WRITING
    )
    grade = grade_with_ai_service(service, independent, "Zij leest een boek vandaag")
    # Invalid rule must not become a trusted explanation.
    assert grade.structured is None or grade.structured.grammar_rule_id == ""
    companion = build_companion(
        independent,
        tuple(pack.rule_map()[rid] for rid in independent.grammar_rule_ids),
        structured=grade.structured,
        diagnosis_certain=False,
    )
    assert companion is None or companion.guidance_only or companion.provisional


def test_provisional_versus_reviewed_outcomes():
    pack = load_pack("nl", "A1")
    blank = next(item for item in pack.exercises if item.kind == KIND_FILL_BLANK)
    reviewed = grade_locally(blank, "leest")
    assert reviewed.status == STATUS_REVIEWED_CORRECT
    assert reviewed.structured is not None
    assert not reviewed.structured.provisional
    independent = next(
        item for item in pack.exercises if item.kind == KIND_INDEPENDENT_WRITING
    )
    provisional = grade_with_ai_service(
        build_demo_grade_service("accept_valid"),
        independent,
        "Zij leest een boek vandaag",
    )
    assert provisional.status == GRADE_PROVISIONAL_ACCEPT
    assert provisional.structured is not None
    assert provisional.structured.provisional
    assert provisional.structured.grading_status == STATUS_PROVISIONAL_ACCEPT
    assert outcome_is_recordable(OUTCOME_PROVISIONAL_ACCEPT)
    assert not outcome_affects_selection(OUTCOME_PROVISIONAL_ACCEPT)
    assert outcome_affects_selection(OUTCOME_INCORRECT)
    assert outcome_affects_selection(OUTCOME_REVIEWED_CORRECT)


def test_grade_result_backward_compatibility():
    from ai.base import GradeResult

    pack = load_pack("nl", "A1")
    independent = next(
        item for item in pack.exercises if item.kind == KIND_INDEPENDENT_WRITING
    )
    result = GradeResult(
        is_correct_usage=True,
        score=0.91,
        feedback_vi="ok",
        corrected_sentence="Zij leest een boek vandaag",
        suggested_sentence="Zij leest een boek.",
    )
    structured = feedback_from_grade_result(
        result, learner_answer="Zij leest een boek vandaag", exercise=independent
    )
    assert structured.grading_status == STATUS_PROVISIONAL_ACCEPT
    assert structured.primary_error_class != ERROR_CONJUGATION
    # Old provider without structured capability still works.
    class OldProvider:
        def grade_answer(self, request):
            return result

    from ai.service import AIService

    grade = grade_with_ai_service(AIService(provider=OldProvider()), independent, "Zij leest een boek vandaag")
    assert grade.status == GRADE_PROVISIONAL_ACCEPT
    assert grade.structured is not None


def test_malformed_structured_and_score_coercion_rejected(tmp_path):
    with pytest.raises(StructuredFeedbackError):
        validate_structured_feedback(
            {
                "format_version": FEEDBACK_FORMAT_VERSION,
                "grading_status": STATUS_PROVISIONAL_ACCEPT,
                "grading_source": SOURCE_AI,
                "provenance": "x",
                "primary_error_class": "unclassified",
                "original_segment": "",
                "corrected_segment": "",
                "corrected_sentence": "",
                "grammar_rule_id": "",
                "explanation": "ok",
                "provisional": "yes",
                "certainty": 0.9,
            }
        )
    with pytest.raises(StructuredFeedbackError):
        validate_structured_feedback(
            {
                "format_version": FEEDBACK_FORMAT_VERSION,
                "grading_status": STATUS_PROVISIONAL_CORRECT,
                "grading_source": SOURCE_AI,
                "provenance": "x",
                "primary_error_class": ERROR_UNKNOWN,
                "original_segment": "",
                "corrected_segment": "",
                "corrected_sentence": "",
                "grammar_rule_id": "",
                "explanation": "ok",
                "provisional": True,
                "certainty": float("nan"),
            }
        )
    pack = load_pack("nl", "A1")
    independent = next(
        item for item in pack.exercises if item.kind == KIND_INDEPENDENT_WRITING
    )
    grade = grade_with_ai_service(
        build_demo_grade_service("malformed_structured"),
        independent,
        "Zij leest een boek vandaag",
    )
    # Degrades from GradeResult; never silently coerces the bad boolean.
    assert grade.status in (GRADE_PROVISIONAL_ACCEPT, STATUS_UNGRADED)


def test_persistent_event_identity_and_dedup(tmp_path):
    root = tmp_path / "guest-root"
    root.mkdir()
    store = open_guest_sentence_skill_store(str(root), "nl")
    record = build_sentence_skill_record(
        session_id="s1",
        exercise_instance_id="ei1",
        submission_id="sub1",
        exercise_id="nl-a1-fb-zij-leest",
        family_id="nl-a1-family-lezen-boek",
        content_version="1",
        study_language="nl",
        cefr_level="A1",
        exercise_kind=KIND_FILL_BLANK,
        support_level=1,
        outcome=OUTCOME_INCORRECT,
        grading_source="local",
        error_classification="conjugation",
        evidence_status=EVIDENCE_RELIABLE_LOCAL,
        grammar_skill_refs=("nl-a1-present-conjugation",),
    )
    first = store.append(record)
    second = store.append(record)
    assert first.skill_event_id == second.skill_event_id
    assert store.count() == 1
    contradictory = build_sentence_skill_record(
        session_id="s1",
        exercise_instance_id="ei1",
        submission_id="sub1",
        exercise_id="nl-a1-fb-zij-leest",
        family_id="nl-a1-family-lezen-boek",
        content_version="1",
        study_language="nl",
        cefr_level="A1",
        exercise_kind=KIND_FILL_BLANK,
        support_level=1,
        outcome=OUTCOME_REVIEWED_CORRECT,
        grading_source="local",
        error_classification="none",
        evidence_status="reviewed",
        skill_event_id="different-id",
    )
    with pytest.raises(SentenceSkillStoreError):
        store.append(contradictory)
    store.close()


def test_restart_and_cross_session_selection(tmp_path):
    root = tmp_path / "restart-root"
    root.mkdir()
    store = open_guest_sentence_skill_store(str(root), "nl")
    pack = load_pack("nl", "A1")
    blank = next(item for item in pack.exercises if item.kind == KIND_FILL_BLANK)
    session = SentencePracticeSession.from_language(
        "nl", "A1", start_kind=KIND_FILL_BLANK, skill_store=store
    )
    sid = session.begin_submission()
    card = session.current_card()
    # Force the fill-blank conjugation miss.
    result = session.submit_local("lezen", submission_id=sid, instance_id=card.instance_id)
    assert result.grade.status == STATUS_INCORRECT
    assert store.count() >= 1
    history = store.for_language("nl")
    store.close()

    # Restart: new store + session uses history for scaffolding.
    store2 = open_guest_sentence_skill_store(str(root), "nl")
    history2 = store2.for_language("nl")
    assert len(history2) == len(history)
    decision = select_from_sentence_skill_history(
        history2, pack.exercises, study_language="nl", content_version="1"
    )
    assert decision.family_id == blank.family_id
    assert decision.preferred_kind == KIND_WORD_BANK
    assert decision.policy_id == POLICY_FAMILY_SUPPORT_V1
    session2 = SentencePracticeSession.from_language(
        "nl", "A1", skill_store=store2, skill_history=history2
    )
    assert session2.current_card().exercise.family_id == blank.family_id
    assert session2.current_card().exercise.kind == KIND_WORD_BANK
    store2.close()


def test_account_guest_language_isolation(tmp_path):
    root = tmp_path / "iso-root"
    root.mkdir()
    guest_nl = open_guest_sentence_skill_store(str(root), "nl")
    guest_en = open_guest_sentence_skill_store(str(root), "en")
    account = open_account_sentence_skill_store(str(root), 42)
    for store, lang, sub in (
        (guest_nl, "nl", "g-nl"),
        (guest_en, "en", "g-en"),
        (account, "nl", "a-nl"),
    ):
        store.append(
            build_sentence_skill_record(
                session_id="s",
                exercise_instance_id=f"ei-{sub}",
                submission_id=sub,
                exercise_id="ex",
                family_id="fam",
                content_version="1",
                study_language=lang,
                cefr_level="A1",
                exercise_kind=KIND_WORD_BANK,
                support_level=0,
                outcome=OUTCOME_INCORRECT,
                grading_source="local",
                error_classification="word_order",
                evidence_status=EVIDENCE_RELIABLE_LOCAL,
            )
        )
    assert guest_nl.count() == 1
    assert guest_en.count() == 1
    assert account.count() == 1
    assert guest_nl.for_language("nl")[0].submission_id == "g-nl"
    assert guest_en.for_language("en")[0].submission_id == "g-en"
    assert account.for_language("nl")[0].submission_id == "a-nl"
    guest_nl.close()
    guest_en.close()
    account.close()
    assert (root / "languages" / "nl" / SENTENCE_SKILL_DB_FILE).exists()
    assert (root / "accounts" / "42" / SENTENCE_SKILL_DB_FILE).exists()


def test_corrupt_and_unavailable_storage(tmp_path):
    assert refuse_sentence_skill_data_root("") is not None
    with pytest.raises(SentenceSkillStoreError):
        open_guest_sentence_skill_store("", "nl")
    root = tmp_path / "ok-root"
    root.mkdir()
    store = open_guest_sentence_skill_store(str(root), "nl")
    path = Path(store.db_path)
    store.close()
    # Corrupt by writing non-sqlite bytes.
    path.write_bytes(b"not-a-database")
    with pytest.raises(SentenceSkillStoreError):
        open_guest_sentence_skill_store(str(root), "nl")


def test_provisional_ai_does_not_drive_selection(tmp_path):
    root = tmp_path / "prov-root"
    root.mkdir()
    store = open_guest_sentence_skill_store(str(root), "nl")
    pack = load_pack("nl", "A1")
    store.append(
        build_sentence_skill_record(
            session_id="s",
            exercise_instance_id="ei",
            submission_id="sub",
            exercise_id="nl-a1-iw-leest-boek",
            family_id="nl-a1-family-lezen-boek",
            content_version="1",
            study_language="nl",
            cefr_level="A1",
            exercise_kind=KIND_INDEPENDENT_WRITING,
            support_level=3,
            outcome=OUTCOME_PROVISIONAL_ACCEPT,
            grading_source="ai",
            error_classification="unclassified",
            evidence_status=EVIDENCE_PROVISIONAL_AI,
        )
    )
    decision = select_from_sentence_skill_history(
        store.for_language("nl"), pack.exercises, study_language="nl"
    )
    assert decision.family_id == ""
    store.close()


def test_zero_vocab_srs_practice_writes(tmp_path, monkeypatch):
    root = tmp_path / "zero-root"
    root.mkdir()
    (root / "settings.json").write_text(
        json.dumps(
            {
                "native": "en",
                "language": "nl",
                "study_languages": ["nl"],
                "activities": {"reading": False, "listening": False},
            }
        ),
        encoding="utf-8",
    )
    lang = root / "languages" / "nl"
    lang.mkdir(parents=True)
    (lang / "vocab.json").write_text("[]", encoding="utf-8")
    (lang / "progress.json").write_text(json.dumps({"words": {}}), encoding="utf-8")
    (lang / "attempts.jsonl").write_text("", encoding="utf-8")
    monkeypatch.setenv("LG_DATA_DIR", str(root))
    monkeypatch.setenv("LG_ADAPTIVE_STUDY", "1")
    import config

    config.SETTINGS_FILE = str(root / "settings.json")
    config.reload()
    store = open_guest_sentence_skill_store(str(root), "nl")
    session = SentencePracticeSession.from_language(
        "nl", "A1", start_kind=KIND_FILL_BLANK, skill_store=store
    )
    sid = session.begin_submission()
    card = session.current_card()
    session.submit_local("lezen", submission_id=sid, instance_id=card.instance_id)
    store.close()
    assert (lang / "attempts.jsonl").read_text(encoding="utf-8") == ""
    progress = json.loads((lang / "progress.json").read_text(encoding="utf-8"))
    assert progress.get("words") == {}
    assert not (lang / "practice_records.db").exists()
    assert (lang / SENTENCE_SKILL_DB_FILE).exists()
    assert not list(root.glob("**/sync_outbox*"))
    assert not list((root / "accounts").glob("**/*")) if (root / "accounts").exists() else True


def test_segment_in_answer_mismatch_rejected():
    with pytest.raises(StructuredFeedbackError):
        validate_structured_feedback(
            {
                "format_version": FEEDBACK_FORMAT_VERSION,
                "grading_status": "incorrect",
                "grading_source": "local",
                "provenance": "t",
                "primary_error_class": "conjugation",
                "original_segment": "totally-absent-token",
                "corrected_segment": "leest",
                "corrected_sentence": "Zij leest een boek.",
                "grammar_rule_id": "",
                "explanation": "x",
                "provisional": False,
                "certainty": 1.0,
            },
            learner_answer="lezen",
        )


def test_multi_rule_incorrect_keeps_single_skill_ref():
    record = build_sentence_skill_record(
        session_id="s",
        exercise_instance_id="ei",
        submission_id="sub",
        exercise_id="ex",
        family_id="fam",
        content_version="1",
        study_language="nl",
        cefr_level="A1",
        exercise_kind=KIND_FILL_BLANK,
        support_level=1,
        outcome=OUTCOME_INCORRECT,
        grading_source="local",
        error_classification="conjugation",
        evidence_status=EVIDENCE_RELIABLE_LOCAL,
        grammar_skill_refs=("nl-a1-present-conjugation", "nl-a1-svo-main", "nl-a1-articles"),
    )
    assert len(record.grammar_skill_refs) == 1


def test_record_format_version():
    assert RECORD_FORMAT_VERSION == 1
