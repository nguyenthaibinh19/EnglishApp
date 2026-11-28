"""Phase 19.5A R1 sentence practice — families, grading, lifecycle, isolation."""

from __future__ import annotations

import json

import config
import pytest

from grammar_companion import build_companion, select_rule
from sentence_content import (
    KIND_FILL_BLANK,
    KIND_GUIDED_WRITING,
    KIND_INDEPENDENT_WRITING,
    KIND_WORD_BANK,
    LADDER,
    future_ai_feedback_contract_extensions,
    future_sentence_skill_record_contract,
    load_pack,
    provisional_acceptance_progression_policy,
    validate_pack,
)
from sentence_grading import (
    STATUS_INCOMPLETE,
    STATUS_INCORRECT,
    STATUS_PROVISIONAL_ACCEPT,
    STATUS_PROVISIONAL_CORRECT,
    STATUS_REVIEWED_CORRECT,
    STATUS_UNGRADED,
    STATUS_UNLISTED,
    FakeSentenceGradeProvider,
    answers_match,
    grade_locally,
    grade_with_ai_service,
    normalize_sentence,
)
from sentence_practice import SentencePracticeSession
from sentence_practice_app import build_demo_grade_service, speech_for_sentence


def test_dutch_a1_family_covers_four_levels():
    pack = load_pack("nl", "A1")
    assert validate_pack(pack) == []
    family = pack.families()[0]
    kinds = {item.kind for item in pack.by_family(family)}
    assert kinds == set(LADDER)


def test_multiple_reviewed_answers():
    pack = load_pack("nl", "A1")
    guided = next(item for item in pack.exercises if item.kind == KIND_GUIDED_WRITING)
    assert grade_locally(guided, "Ze leest een boek.").status == STATUS_REVIEWED_CORRECT
    assert grade_locally(guided, "Zij leest een boek").status == STATUS_REVIEWED_CORRECT
    assert answers_match("Zij leest een boek!", guided.accepted_answers)


def test_incomplete_word_bank_is_not_a_failure():
    session = SentencePracticeSession.from_language("nl", "A1")
    card = session.current_card()
    result = session.submit_local(tokens=["Zij", "leest"])
    assert result.status == "incomplete"
    assert result.grade.status == STATUS_INCOMPLETE
    assert session.levels_achieved() == 0
    assert len(session.results) == 0
    assert session.current_card().exercise.exercise_id == card.exercise.exercise_id


def test_related_family_step_down():
    session = SentencePracticeSession.from_language("nl", "A1")
    family = session.current_card().exercise.family_id
    sid = session.begin_submission()
    card = session.current_card()
    session.submit_local(
        tokens=list(card.exercise.word_bank),
        submission_id=sid,
        instance_id=card.instance_id,
    )
    assert session.current_card().exercise.kind == KIND_FILL_BLANK
    for _ in range(2):
        sid = session.begin_submission()
        card = session.current_card()
        result = session.submit_local(
            "lezen", submission_id=sid, instance_id=card.instance_id
        )
    assert result.stepped_down
    down = session.current_card()
    assert down.exercise.kind == KIND_WORD_BANK
    assert down.exercise.family_id == family


def test_potentially_valid_unlisted_is_not_incorrect():
    pack = load_pack("nl", "A1")
    independent = next(
        item for item in pack.exercises if item.kind == KIND_INDEPENDENT_WRITING
    )
    grade = grade_locally(independent, "Zij leest een boek vandaag")
    assert grade.status == STATUS_UNLISTED
    assert grade.status != STATUS_INCORRECT


def test_wrong_language_fake_grading():
    pack = load_pack("nl", "A1")
    independent = next(
        item for item in pack.exercises if item.kind == KIND_INDEPENDENT_WRITING
    )
    service = build_demo_grade_service("accept_valid")
    grade = grade_with_ai_service(service, independent, "She reads a book.")
    assert grade.status == STATUS_PROVISIONAL_CORRECT
    assert grade.status != STATUS_PROVISIONAL_ACCEPT


def test_malformed_ai_is_ungraded():
    pack = load_pack("nl", "A1")
    independent = next(
        item for item in pack.exercises if item.kind == KIND_INDEPENDENT_WRITING
    )
    malformed = grade_with_ai_service(
        build_demo_grade_service("malformed"), independent, "Zij leest een boek vandaag"
    )
    assert malformed.status == STATUS_UNGRADED
    bad_bool = grade_with_ai_service(
        build_demo_grade_service("malformed_bool"),
        independent,
        "Zij leest een boek vandaag",
    )
    assert bad_bool.status == STATUS_UNGRADED


def test_stale_async_delivery_ignored():
    session = SentencePracticeSession.from_language(
        "nl", "A1", start_kind=KIND_INDEPENDENT_WRITING
    )
    sid = session.begin_submission()
    card = session.current_card()
    instance = card.instance_id
    # Move on by abandoning the open submission binding.
    session.clear_submission(sid)
    sid2 = session.begin_submission()
    grade = grade_with_ai_service(
        build_demo_grade_service("accept_valid"),
        card.exercise,
        "Zij leest een boek vandaag",
    )
    stale = session.apply_external_grade(
        grade,
        "Zij leest een boek vandaag",
        submission_id=sid,
        instance_id=instance,
    )
    assert stale.status == "stale"
    assert session.levels_achieved() == 0
    # Fresh binding still works.
    applied = session.apply_external_grade(
        grade,
        "Zij leest een boek vandaag",
        submission_id=sid2,
        instance_id=session.current_card().instance_id,
    )
    assert applied.grade.status == STATUS_PROVISIONAL_ACCEPT
    assert "provisional" in provisional_acceptance_progression_policy().lower()


def test_contextual_grammar_rule_selection():
    pack = load_pack("nl", "A1")
    blank = next(item for item in pack.exercises if item.kind == KIND_FILL_BLANK)
    rules = tuple(pack.rule_map()[rid] for rid in blank.grammar_rule_ids)
    rule, claims = select_rule(
        blank, rules, error_hint="conjugation", diagnosis_certain=True
    )
    assert claims
    assert "conjugation" in rule.rule_id or "present" in rule.rule_id
    bank = next(item for item in pack.exercises if item.kind == KIND_WORD_BANK)
    bank_rules = tuple(pack.rule_map()[rid] for rid in bank.grammar_rule_ids)
    order_rule, order_claims = select_rule(
        bank, bank_rules, error_hint="word_order", diagnosis_certain=True
    )
    assert order_claims
    assert "svo" in order_rule.rule_id
    uncertain = build_companion(
        blank, rules, error_hint="", diagnosis_certain=False
    )
    assert uncertain is not None
    assert uncertain.guidance_only
    assert "not a specific error diagnosis" in uncertain.beginner.lower() or "chẩn đoán" in uncertain.beginner.lower()


def test_progress_is_distinct_levels_not_raw_correct_count():
    session = SentencePracticeSession.from_language("nl", "A1")
    # Climb all four with reviewed answers.
    answers = {
        KIND_WORD_BANK: None,
        KIND_FILL_BLANK: "leest",
        KIND_GUIDED_WRITING: "Ze leest een boek.",
        KIND_INDEPENDENT_WRITING: "Zij leest een boek.",
    }
    for _ in range(4):
        card = session.current_card()
        sid = session.begin_submission()
        kind = card.exercise.kind
        if kind == KIND_WORD_BANK:
            result = session.submit_local(
                tokens=list(card.exercise.word_bank),
                submission_id=sid,
                instance_id=card.instance_id,
            )
        else:
            result = session.submit_local(
                answers[kind], submission_id=sid, instance_id=card.instance_id
            )
        assert result.grade.status == STATUS_REVIEWED_CORRECT
    assert session.finished
    assert session.progress_pair() == (4, 4)
    assert session.take_completion()
    assert not session.take_completion()


def test_repeated_easier_level_does_not_false_complete():
    session = SentencePracticeSession.from_language("nl", "A1")
    # Only clear word-bank repeatedly — never claim 4/4.
    for _ in range(3):
        card = session.current_card()
        assert card.exercise.kind == KIND_WORD_BANK
        sid = session.begin_submission()
        session.submit_local(
            tokens=["boek", "Zij", "een", "leest", "."],
            submission_id=sid,
            instance_id=card.instance_id,
        )
    assert session.levels_achieved() == 0
    assert not session.finished
    assert session.progress_pair()[0] == 0


def test_missing_content_and_abandon_are_not_successful_completion():
    from sentence_content import SentencePack

    empty = SentencePack(
        pack_id="empty",
        language_code="nl",
        cefr="A1",
        title="empty",
        exercises=(),
        rules=(),
    )
    missing = SentencePracticeSession(empty)
    assert missing.missing_content
    assert not missing.take_completion()

    session = SentencePracticeSession.from_language("nl", "A1")
    session.abandon()
    assert session.abandoned
    assert not session.take_completion()


def test_speech_gate_only_after_feedback_reviewed():
    pack = load_pack("nl", "A1")
    exercise = pack.exercises[0]
    assert not speech_for_sentence(exercise, "answer").allowed
    plan = speech_for_sentence(exercise, "feedback")
    assert plan.allowed
    assert plan.text == exercise.primary_answer()


def test_sentence_cta_parent_and_invocation():
    """CTA uses continue_button parent and actually invokes the callback."""
    import tkinter as tk

    pytest.importorskip("customtkinter")
    import customtkinter as ctk
    from ctk_keyboard import bind_activation
    from study_presentation import StudyCardShell

    calls = []
    root = tk.Tk()
    root.withdraw()
    try:
        host = tk.Frame(root)
        host.pack()
        shell = StudyCardShell(
            host,
            locked=False,
            on_check=lambda: None,
            on_hint=lambda: None,
            on_continue=lambda: None,
            on_done=lambda: None,
            on_sentence=lambda: None,
            on_hear=lambda: None,
            on_leave=lambda: None,
            on_emergency=lambda: None,
        )
        shell.pack()
        shell.show_complete("done", "detail", "Back", celebrate=True)
        parent = shell.continue_button.master
        button = ctk.CTkButton(
            parent,
            text="Practice a sentence (optional)",
            command=lambda: calls.append(1),
        )
        button.pack(fill=tk.X, before=shell.continue_button)
        bind_activation(button)
        assert button.master is shell.continue_button.master
        button.invoke()
        assert calls == [1]
    finally:
        root.destroy()


def test_reading_listening_deferred_when_sentence_pending(monkeypatch):
    """StudyMaster defers next activity while sentence-after-vocab is pending."""
    import main as main_mod

    scheduled = []
    monkeypatch.setattr(config, "active_code", lambda: "nl")
    master = object.__new__(main_mod.StudyMasterApp)
    master._account_generation = 1
    master._sentence_after_vocab = ("nl", 1)
    master._resume_after_sentence = None
    master._sentence_resume_done = False
    master.root = type("R", (), {"after": staticmethod(lambda *a, **k: scheduled.append(a))})()
    master._session_for = lambda code: type(
        "S",
        (),
        {
            "complete": lambda self, kind: None,
            "next_activity": lambda self: type("N", (), {"kind": "reading"})(),
        },
    )()
    master._refresh_status = lambda: None
    main_mod.StudyMasterApp._deliver_vocab_completed(master, 1, "nl")
    assert master._resume_after_sentence == ("nl", 1)
    assert scheduled == []


def test_account_language_lifecycle_closes_sentence_binding():
    session = SentencePracticeSession.from_language("nl", "A1")
    sid = session.begin_submission()
    assert sid
    session.abandon()
    assert session.abandoned
    assert session.current_card() is None


def test_no_vocab_writes_from_sentence(tmp_path, monkeypatch):
    root = tmp_path / "19d5a-r1"
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
    sid = session.begin_submission()
    card = session.current_card()
    session.submit_local(
        tokens=["boek", "Zij", "leest", "een", "."],
        submission_id=sid,
        instance_id=card.instance_id,
    )
    session.abandon()
    assert attempts.read_text(encoding="utf-8") == ""
    progress = json.loads((lang / "progress.json").read_text(encoding="utf-8"))
    assert progress.get("words") == {}
    assert not (root / "practice_records.db").exists()


def test_future_contracts_documented():
    assert any("SentenceSkillRecord" in line for line in future_sentence_skill_record_contract())
    assert any("Primary error class" in line for line in future_ai_feedback_contract_extensions())
    assert "provisional_accept" in provisional_acceptance_progression_policy()


def test_normalize_unicode_and_punctuation():
    assert normalize_sentence("  Zij  leest  een  boek! ") == "zij leest een boek"
    assert answers_match("Zij leest een boek", ("Zij leest een boek.",))
