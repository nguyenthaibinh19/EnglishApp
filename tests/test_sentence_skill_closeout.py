"""Phase 19.5B closeout corrections — session plan, validation, selection, store."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from grammar_companion import build_companion
from sentence_content import (
    KIND_FILL_BLANK,
    KIND_GUIDED_WRITING,
    KIND_INDEPENDENT_WRITING,
    KIND_WORD_BANK,
    load_pack,
)
from sentence_feedback import (
    ERROR_CONJUGATION,
    FEEDBACK_FORMAT_VERSION,
    SOURCE_AI,
    SOURCE_LOCAL,
    STATUS_INCORRECT,
    STATUS_PROVISIONAL_ACCEPT,
    STATUS_PROVISIONAL_CORRECT,
    STATUS_REVIEWED_CORRECT,
    StructuredFeedbackError,
    segment_in_answer,
    validate_structured_feedback,
)
from sentence_grading import (
    STATUS_PROVISIONAL_ACCEPT as GRADE_ACCEPT,
    STATUS_PROVISIONAL_CORRECT as GRADE_CORRECT,
    FakeSentenceGradeProvider,
    grade_locally,
    grade_with_ai_service,
)
from sentence_practice import SentencePracticeSession
from sentence_practice_app import build_demo_grade_service
from sentence_skill_policy import select_from_sentence_skill_history
from sentence_skill_record import (
    EVIDENCE_RELIABLE_LOCAL,
    EVIDENCE_REVIEWED,
    OUTCOME_INCORRECT,
    OUTCOME_REVIEWED_CORRECT,
    build_sentence_skill_record,
)
from sentence_skill_store import (
    SentenceSkillStoreError,
    open_guest_sentence_skill_store,
)


def _solve_word_bank(session: SentencePracticeSession) -> None:
    card = session.current_card()
    sid = session.begin_submission()
    session.submit_local(
        tokens=list(card.exercise.word_bank),
        submission_id=sid,
        instance_id=card.instance_id,
    )


def _submit(session: SentencePracticeSession, answer: str):
    sid = session.begin_submission()
    card = session.current_card()
    return session.submit_local(answer, submission_id=sid, instance_id=card.instance_id)


def test_completion_from_fill_blank_start():
    session = SentencePracticeSession.from_language(
        "nl", "A1", start_kind=KIND_FILL_BLANK
    )
    assert session.session_plan_levels() == (1, 2, 3)
    assert session.progress_pair() == (0, 3)
    # Skipped word bank is not demonstrated.
    assert 0 not in session._achieved_levels

    result = _submit(session, "leest")
    assert result.grade.status == "reviewed_correct"
    assert session.current_card().exercise.kind == KIND_GUIDED_WRITING
    assert session.progress_pair() == (1, 3)

    _submit(session, "Zij leest een boek.")
    assert session.current_card().exercise.kind == KIND_INDEPENDENT_WRITING

    service = build_demo_grade_service("accept_valid")
    sid = session.begin_submission()
    card = session.current_card()
    grade = grade_with_ai_service(service, card.exercise, "Zij leest een boek vandaag")
    applied = session.apply_external_grade(
        grade, "Zij leest een boek vandaag", submission_id=sid, instance_id=card.instance_id
    )
    assert applied.session_finished
    assert session.finished
    assert session.plan_complete()
    assert session.take_completion()
    assert session.progress_pair() == (3, 3)


def test_guided_start_step_down_then_complete():
    session = SentencePracticeSession.from_language(
        "nl", "A1", start_kind=KIND_GUIDED_WRITING
    )
    assert session.session_plan_levels() == (2, 3)
    # Fail guided twice → step down into fill blank; plan expands.
    for answer in ("een boek Zij leest", "een boek Zij leest"):
        result = _submit(session, answer)
    assert result.stepped_down
    assert 1 in session.session_plan_levels()
    assert session.current_card().exercise.kind == KIND_FILL_BLANK
    # Climb back through plan.
    _submit(session, "leest")
    _submit(session, "Zij leest een boek.")
    sid = session.begin_submission()
    card = session.current_card()
    grade = grade_with_ai_service(
        build_demo_grade_service("accept_valid"),
        card.exercise,
        "Zij leest een boek vandaag",
    )
    applied = session.apply_external_grade(
        grade, "Zij leest een boek vandaag", submission_id=sid, instance_id=card.instance_id
    )
    assert applied.session_finished
    assert session.take_completion()


def test_easier_success_does_not_clear_harder_difficulty(tmp_path):
    pack = load_pack("nl", "A1")
    family = pack.families()[0]
    now = datetime.now(timezone.utc)
    harder_incorrect = build_sentence_skill_record(
        session_id="s1",
        exercise_instance_id="ei-hard",
        submission_id="sub-hard",
        exercise_id="nl-a1-fb-zij-leest",
        family_id=family,
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
        occurred_at=(now - timedelta(hours=2)).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    )
    easier_success = build_sentence_skill_record(
        session_id="s2",
        exercise_instance_id="ei-easy",
        submission_id="sub-easy",
        exercise_id="nl-a1-wb-leest-boek",
        family_id=family,
        content_version="1",
        study_language="nl",
        cefr_level="A1",
        exercise_kind=KIND_WORD_BANK,
        support_level=0,
        outcome=OUTCOME_REVIEWED_CORRECT,
        grading_source="local",
        error_classification="none",
        evidence_status=EVIDENCE_REVIEWED,
        occurred_at=(now - timedelta(hours=1)).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    )
    decision = select_from_sentence_skill_history(
        [harder_incorrect, easier_success],
        pack.exercises,
        study_language="nl",
        content_version="1",
        now=now,
    )
    assert decision.family_id == family
    assert decision.preferred_kind == KIND_WORD_BANK


def test_same_or_harder_success_resolves_difficulty():
    pack = load_pack("nl", "A1")
    family = pack.families()[0]
    now = datetime.now(timezone.utc)
    incorrect = build_sentence_skill_record(
        session_id="s1",
        exercise_instance_id="ei1",
        submission_id="sub1",
        exercise_id="nl-a1-fb-zij-leest",
        family_id=family,
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
        occurred_at=(now - timedelta(hours=2)).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    )
    resolved = build_sentence_skill_record(
        session_id="s2",
        exercise_instance_id="ei2",
        submission_id="sub2",
        exercise_id="nl-a1-fb-zij-leest",
        family_id=family,
        content_version="1",
        study_language="nl",
        cefr_level="A1",
        exercise_kind=KIND_FILL_BLANK,
        support_level=1,
        outcome=OUTCOME_REVIEWED_CORRECT,
        grading_source="local",
        error_classification="none",
        evidence_status=EVIDENCE_REVIEWED,
        grammar_skill_refs=("nl-a1-present-conjugation",),
        occurred_at=(now - timedelta(hours=1)).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    )
    decision = select_from_sentence_skill_history(
        [incorrect, resolved],
        pack.exercises,
        study_language="nl",
        content_version="1",
        now=now,
    )
    assert decision.family_id == ""


def test_strict_feedback_types_and_source_status():
    with pytest.raises(StructuredFeedbackError):
        validate_structured_feedback(
            {
                "format_version": True,
                "grading_status": STATUS_INCORRECT,
                "grading_source": SOURCE_LOCAL,
                "provenance": "x",
                "primary_error_class": ERROR_CONJUGATION,
                "original_segment": "",
                "corrected_segment": "",
                "corrected_sentence": "",
                "grammar_rule_id": "",
                "explanation": "",
                "provisional": False,
                "certainty": 1.0,
            }
        )
    with pytest.raises(StructuredFeedbackError):
        validate_structured_feedback(
            {
                "format_version": FEEDBACK_FORMAT_VERSION,
                "grading_status": STATUS_REVIEWED_CORRECT,
                "grading_source": SOURCE_AI,
                "provenance": "model",
                "primary_error_class": "",
                "original_segment": "",
                "corrected_segment": "",
                "corrected_sentence": "ok",
                "grammar_rule_id": "",
                "explanation": "ok",
                "provisional": True,
                "certainty": 0.9,
            }
        )
    with pytest.raises(StructuredFeedbackError):
        validate_structured_feedback(
            {
                "format_version": FEEDBACK_FORMAT_VERSION,
                "grading_status": STATUS_PROVISIONAL_ACCEPT,
                "grading_source": SOURCE_AI,
                "provenance": "model",
                "primary_error_class": ERROR_CONJUGATION,
                "original_segment": "",
                "corrected_segment": "",
                "corrected_sentence": "ok",
                "grammar_rule_id": "",
                "explanation": "ok",
                "provisional": True,
                "certainty": 0.9,
            }
        )
    assert segment_in_answer("lezen", "lezen")
    assert not segment_in_answer("lezen is long", "lezen")


def test_contradictory_structured_falls_back_to_grade_result():
    pack = load_pack("nl", "A1")
    independent = next(e for e in pack.exercises if e.kind == KIND_INDEPENDENT_WRITING)
    service = build_demo_grade_service("contradictory_structured")
    # Force accept path on GradeResult while structured says correct/reject.
    provider = FakeSentenceGradeProvider(mode="contradictory_structured")
    from ai.service import AIService

    # Mode contradictory returns structured reject; GradeResult from same mode uses accept_valid-like
    # via grade_answer in accept path — set mode that accepts valid extra then contradictory structured.
    provider.mode = "accept_valid"
    # Patch structured to contradictory after grade.
    original = provider.structured_sentence_feedback

    def contradictory(request, *, exercise=None, grade_result=None):
        provider.mode = "contradictory_structured"
        return original(request, exercise=exercise, grade_result=grade_result)

    provider.structured_sentence_feedback = contradictory
    grade = grade_with_ai_service(AIService(provider=provider), independent, "Zij leest een boek vandaag")
    assert grade.status == GRADE_ACCEPT
    assert grade.structured is not None
    assert grade.structured.grading_status == STATUS_PROVISIONAL_ACCEPT


def test_invalid_segment_and_corrected_segment():
    pack = load_pack("nl", "A1")
    blank = next(e for e in pack.exercises if e.kind == KIND_FILL_BLANK)
    with pytest.raises(StructuredFeedbackError):
        validate_structured_feedback(
            {
                "format_version": FEEDBACK_FORMAT_VERSION,
                "grading_status": STATUS_INCORRECT,
                "grading_source": SOURCE_LOCAL,
                "provenance": "local",
                "primary_error_class": ERROR_CONJUGATION,
                "original_segment": "absent",
                "corrected_segment": "leest",
                "corrected_sentence": blank.primary_answer(),
                "grammar_rule_id": "",
                "explanation": "",
                "provisional": False,
                "certainty": 1.0,
            },
            learner_answer="lezen",
            exercise=blank,
        )
    with pytest.raises(StructuredFeedbackError):
        validate_structured_feedback(
            {
                "format_version": FEEDBACK_FORMAT_VERSION,
                "grading_status": STATUS_INCORRECT,
                "grading_source": SOURCE_LOCAL,
                "provenance": "local",
                "primary_error_class": ERROR_CONJUGATION,
                "original_segment": "lezen",
                "corrected_segment": "zzzz",
                "corrected_sentence": blank.primary_answer(),
                "grammar_rule_id": "nl-a1-present-conjugation",
                "explanation": "",
                "provisional": False,
                "certainty": 1.0,
            },
            learner_answer="lezen",
            exercise=blank,
            allowed_rule_ids=blank.grammar_rule_ids,
        )


def test_unclassified_local_failure_has_no_rule_ref():
    pack = load_pack("nl", "A1")
    blank = next(e for e in pack.exercises if e.kind == KIND_FILL_BLANK)
    grade = grade_locally(blank, "xyzzy")
    assert grade.status == "incorrect"
    assert not grade.diagnosis_certain
    assert grade.structured is None or grade.structured.grammar_rule_id == ""
    companion = build_companion(
        blank,
        tuple(pack.rule_map()[rid] for rid in blank.grammar_rule_ids),
        error_hint=grade.error_hint,
        diagnosis_certain=grade.diagnosis_certain,
        structured=grade.structured,
    )
    assert companion is None or companion.guidance_only or not companion.diagnosis_certain


def test_store_closed_and_init_failure(tmp_path):
    root = tmp_path / "store-root"
    root.mkdir()
    store = open_guest_sentence_skill_store(str(root), "nl")
    store.close()
    with pytest.raises(SentenceSkillStoreError):
        store.count()
    with pytest.raises(SentenceSkillStoreError):
        store.for_language("nl")
    bad = tmp_path / "bad-root"
    bad.mkdir()
    db_parent = bad / "languages" / "nl"
    db_parent.mkdir(parents=True)
    db_path = db_parent / "sentence_skill_records.db"
    db_path.write_bytes(b"not-sqlite")
    with pytest.raises(SentenceSkillStoreError):
        open_guest_sentence_skill_store(str(bad), "nl")


def test_integrated_studymaster_sentence_persistence(tmp_path, monkeypatch):
    root = tmp_path / "integrated-root"
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

    from adaptive_study import capture_identity, open_sentence_skill_store
    from sentence_skill_store import load_sentence_skill_history

    identity = capture_identity("nl", account_generation=0)
    store = open_sentence_skill_store(identity)
    history = load_sentence_skill_history(store, "nl")
    session = SentencePracticeSession.from_language(
        "nl", "A1", start_kind=KIND_FILL_BLANK, skill_store=store, skill_history=history
    )
    _submit(session, "lezen")
    assert store.count() >= 1
    store.close()
    assert (lang / "attempts.jsonl").read_text(encoding="utf-8") == ""
    assert json.loads((lang / "progress.json").read_text(encoding="utf-8")).get("words") == {}
    assert not (lang / "practice_records.db").exists()
    assert (lang / "sentence_skill_records.db").exists()
