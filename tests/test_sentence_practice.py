"""Phase 19.5A sentence practice — content, ladder, grading, isolation."""

from __future__ import annotations

import json
import os
from pathlib import Path

import config
import pytest

from grammar_companion import build_companion
from sentence_content import (
    KIND_FILL_BLANK,
    KIND_GUIDED_WRITING,
    KIND_INDEPENDENT_WRITING,
    KIND_WORD_BANK,
    future_ai_feedback_contract_extensions,
    future_sentence_skill_record_contract,
    load_pack,
    validate_pack,
)
from sentence_grading import (
    FakeSentenceGradeProvider,
    answers_match,
    grade_locally,
    grade_with_ai_service,
    normalize_sentence,
)
from sentence_practice import SentencePracticeSession
from sentence_practice_app import build_demo_grade_service


def test_dutch_a1_pack_validates_and_covers_four_levels():
    pack = load_pack("nl", "A1")
    assert validate_pack(pack) == []
    kinds = {item.kind for item in pack.exercises}
    assert kinds == {
        KIND_WORD_BANK,
        KIND_FILL_BLANK,
        KIND_GUIDED_WRITING,
        KIND_INDEPENDENT_WRITING,
    }
    assert all(item.review_status for item in pack.exercises)
    assert pack.review_checklist
    assert "pending" in pack.provenance.lower() or any(
        rule.review_status.endswith("expert_validation") for rule in pack.rules
    )


def test_other_languages_have_contract_but_no_pack():
    with pytest.raises(LookupError):
        load_pack("en", "A1")
    with pytest.raises(LookupError):
        load_pack("vi", "A1")


def test_normalize_handles_punctuation_case_and_spaces():
    assert normalize_sentence("  Ik  drink  water! ") == "ik drink water"
    assert answers_match("Ik drink water", ("Ik drink water.", "Ik drink water"))
    assert answers_match("IK DRINK WATER.", ("Ik drink water.",))


def test_multiple_reviewed_answers_and_wrong_order():
    pack = load_pack("nl", "A1")
    guided = next(item for item in pack.exercises if item.kind == KIND_GUIDED_WRITING)
    assert grade_locally(guided, "Ze leest een boek.").status == "correct"
    assert grade_locally(guided, "Zij leest een boek").status == "correct"
    bank = next(item for item in pack.exercises if item.exercise_id == "nl-a1-wb-drink-water")
    wrong = grade_locally(bank, "water drink Ik.")
    assert wrong.status == "incorrect"
    assert wrong.error_hint == "word_order"


def test_conjugation_fill_blank():
    pack = load_pack("nl", "A1")
    blank = next(item for item in pack.exercises if item.kind == KIND_FILL_BLANK)
    assert grade_locally(blank, "drinkt").status == "correct"
    bad = grade_locally(blank, "drinken")
    assert bad.status == "incorrect"
    assert bad.error_hint == "conjugation"


def test_ladder_advances_and_steps_down():
    session = SentencePracticeSession.from_language("nl", "A1")
    card = session.current_card()
    assert card.exercise.kind == KIND_WORD_BANK
    ok = session.submit_local(tokens=["Ik", "drink", "water", "."])
    assert ok.advanced
    assert session.current_card().exercise.kind == KIND_FILL_BLANK
    # Two failures step down.
    session.submit_local("wrong")
    stepped = session.submit_local("still wrong")
    assert stepped.stepped_down
    assert session.current_card().exercise.kind == KIND_WORD_BANK


def test_complete_four_levels_with_reviewed_answers():
    session = SentencePracticeSession.from_language("nl", "A1")
    answers = {
        KIND_WORD_BANK: ("Ik", "drink", "water", "."),
        KIND_FILL_BLANK: "Hij drinkt water.",
        KIND_GUIDED_WRITING: "Ze leest een boek.",
        KIND_INDEPENDENT_WRITING: "Ik koop een fiets.",
    }
    for _ in range(4):
        card = session.current_card()
        assert card is not None
        kind = card.exercise.kind
        payload = answers[kind]
        if kind == KIND_WORD_BANK:
            result = session.submit_local(tokens=payload)
        else:
            result = session.submit_local(payload)
        assert result.grade.status == "correct"
        session.continue_after_feedback()
    assert session.finished
    assert all(row.outcome == "correct" for row in session.results)


def test_grammar_companion_requires_validated_rule():
    pack = load_pack("nl", "A1")
    exercise = pack.exercises[0]
    rules = tuple(pack.rule_map()[rid] for rid in exercise.grammar_rule_ids)
    view = build_companion(exercise, rules, corrected_sentence=exercise.primary_answer())
    assert view is not None
    assert view.rule_id
    assert view.components
    assert build_companion(exercise, (), corrected_sentence="x") is None


def test_fake_ai_provisional_outside_reviewed_set():
    pack = load_pack("nl", "A1")
    independent = next(
        item for item in pack.exercises if item.kind == KIND_INDEPENDENT_WRITING
    )
    service = build_demo_grade_service("accept_valid")
    local = grade_locally(independent, "Ik koop een fiets vandaag")
    assert local.status == "incorrect"
    grade = grade_with_ai_service(service, independent, "Ik koop een fiets vandaag")
    assert grade.status == "provisional"
    assert grade.score >= 0.7
    session = SentencePracticeSession.from_language("nl", "A1", start_kind=KIND_INDEPENDENT_WRITING)
    applied = session.apply_external_grade(grade, "Ik koop een fiets vandaag")
    assert applied.grade.status == "correct"
    assert applied.session_finished
    # AI result must not mutate pack accepted answers.
    assert "Ik koop een fiets vandaag" not in independent.accepted_answers


def test_ai_unavailable_and_malformed_are_not_definitive_wrong():
    pack = load_pack("nl", "A1")
    independent = next(
        item for item in pack.exercises if item.kind == KIND_INDEPENDENT_WRITING
    )
    unavailable = grade_with_ai_service(
        build_demo_grade_service("unavailable"), independent, "anything"
    )
    assert unavailable.status == "unavailable"
    session = SentencePracticeSession.from_language("nl", "A1", start_kind=KIND_INDEPENDENT_WRITING)
    feedback = session.apply_external_grade(unavailable, "anything")
    assert feedback.tone == "near"
    assert not feedback.stepped_down
    assert session.current_card() is not None

    malformed = grade_with_ai_service(
        build_demo_grade_service("malformed"), independent, "anything"
    )
    assert malformed.status == "provisional"
    soft = session.apply_external_grade(malformed, "anything")
    assert soft.tone == "near"


def test_abandon_preserves_no_vocab_writes(tmp_path, monkeypatch):
    root = tmp_path / "19d5a"
    root.mkdir()
    monkeypatch.setenv("LG_DATA_DIR", str(root))
    monkeypatch.setenv("LG_ADAPTIVE_STUDY", "1")
    monkeypatch.setenv("LOCK_SCREEN", "0")
    settings = {
        "native": "en",
        "language": "nl",
        "study_languages": ["nl"],
        "activities": {"reading": False, "listening": False},
        "ui_language": "en",
    }
    (root / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
    lang = root / "languages" / "nl"
    lang.mkdir(parents=True)
    (lang / "vocab.json").write_text("[]", encoding="utf-8")
    (lang / "progress.json").write_text(json.dumps({"words": {}}), encoding="utf-8")
    attempts = lang / "attempts.jsonl"
    attempts.write_text("", encoding="utf-8")
    config.SETTINGS_FILE = str(root / "settings.json")
    config.reload()

    session = SentencePracticeSession.from_language("nl", "A1")
    session.submit_local(tokens=["water", "Ik", "drink"])
    session.abandon()
    assert session.abandoned
    assert attempts.read_text(encoding="utf-8") == ""
    progress = json.loads((lang / "progress.json").read_text(encoding="utf-8"))
    assert progress.get("words") == {}
    practice_db = root / "practice_records.db"
    assert not practice_db.exists()


def test_future_contracts_documented():
    assert any("SentenceSkillRecord" in line for line in future_sentence_skill_record_contract())
    assert any("Primary error class" in line for line in future_ai_feedback_contract_extensions())


def test_fake_provider_records_calls_without_network():
    provider = FakeSentenceGradeProvider(mode="accept_valid")
    from ai.base import GradeRequest

    result = provider.grade_answer(
        GradeRequest(
            target_word="kopen",
            user_sentence="Ik koop een fiets vandaag",
            meaning="I buy a bicycle.",
            study_language="Dutch",
            native_label="English",
            level="A1",
        )
    )
    assert result.is_correct_usage
    assert len(provider.calls) == 1
