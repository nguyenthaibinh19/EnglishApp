"""Adaptive vocabulary ladder. Domain tests are not GUI proof."""

from __future__ import annotations

import random

import config
import pytest

from adaptive_vocabulary import (
    GUIDED_TYPING,
    INDEPENDENT_RECALL,
    INTRODUCTION,
    MISSING_LETTERS,
    MULTIPLE_CHOICE,
    AdaptivePreviewRefused,
    AdaptiveSessionBridge,
    AdaptiveVocabularySession,
    apply_independent_write,
    build_exercise,
    guided_guidance,
    guided_pattern,
    reconstruct_mask,
    mask_target,
    speech_for_card,
    starting_level,
)
from attempt_history import LearningAttempt
from daily_study import DailyStudyPlan
from quiz_engine import QuizEngine
from study_session import KIND_READING, build_study_session

FIETS = "11111111-1111-4111-8111-111111111111"
HUIS = "22222222-2222-4222-8222-222222222222"
BOEK = "33333333-3333-4333-8333-333333333333"
WATER = "44444444-4444-4444-8444-444444444444"
POORT = "55555555-5555-4555-8555-555555555555"


def word(vid, text, meaning, example=""):
    entry = {"id": vid, "word": text, "meaning": meaning}
    if example:
        entry["example"] = example
    return entry


def pool():
    return [
        word(FIETS, "de fiets", "bicycle", "Ik ga met de fiets."),
        word(HUIS, "het huis", "house"),
        word(BOEK, "het boek", "book"),
        word(WATER, "het water", "water"),
    ]


def session(entries, **kwargs):
    items = list(entries)
    return AdaptiveVocabularySession(
        items,
        language_code="nl",
        pool=kwargs.pop("pool", pool()),
        rng=kwargs.pop("rng", random.Random(4)),
        **kwargs,
    )


def attempt(vid, *, correct, verdict, hint=False, language="nl"):
    return LearningAttempt(
        timestamp="2026-11-27T12:00:00+00:00",
        language_code=language,
        word="de fiets",
        user_answer="fiets" if correct else "nope",
        expected_answer="de fiets",
        correct=correct,
        verdict=verdict,
        hint_used=hint,
        prompt="bicycle",
        vocab_id=vid,
    )


def drive_success(controller: AdaptiveVocabularySession, limit=12):
    kinds = []
    for _ in range(limit):
        card = controller.current_card()
        if card is None:
            break
        kinds.append((card.vocab_id, card.kind))
        if card.kind == INTRODUCTION:
            controller.continue_card()
            continue
        if card.kind == MULTIPLE_CHOICE:
            result = controller.submit(choice_index=card.correct_index)
        else:
            result = controller.submit(card.reveal_word)
        assert result.write is None or card.kind == INDEPENDENT_RECALL
        controller.continue_card()
        if controller.finished:
            break
    return kinds


def test_new_word_starts_at_introduction_and_mastered_due_word_at_recall():
    assert starting_level(None, None) == INTRODUCTION
    assert starting_level({"seen": 0}, None) == INTRODUCTION
    latest = attempt(FIETS, correct=False, verdict="wrong")
    assert starting_level({"seen": 2, "streak": 0}, latest) == GUIDED_TYPING
    mastered = attempt(FIETS, correct=True, verdict="exact")
    due = {"seen": 3, "streak": 2, "due_at": "2020-01-01T00:00:00+00:00"}
    assert starting_level(due, mastered) == INDEPENDENT_RECALL


def test_new_dutch_word_reaches_independent_recall():
    controller = session([pool()[0]])
    kinds = [kind for _vid, kind in drive_success(controller)]
    assert kinds == [
        INTRODUCTION,
        MULTIPLE_CHOICE,
        MISSING_LETTERS,
        GUIDED_TYPING,
        INDEPENDENT_RECALL,
    ]
    assert controller.finished
    assert controller.counters.words_completed == 1
    assert controller.counters.independent_mastered == 1
    assert controller.counters.recognition_successes == 2
    assert controller.counters.assisted_successes == 2
    assert controller.take_completion() is True
    assert controller.take_completion() is False


def test_two_failures_step_down_and_other_words_still_get_a_turn():
    controller = session(
        [pool()[0], pool()[1]],
        level_overrides={FIETS: MULTIPLE_CHOICE, HUIS: MULTIPLE_CHOICE},
    )
    assert controller.current_card().vocab_id == FIETS
    controller.submit(choice_index=0 if controller.current_card().correct_index != 0 else 1)
    controller.continue_card()
    assert controller.current_card().vocab_id == HUIS
    assert controller.level_of(FIETS) == MULTIPLE_CHOICE
    controller.submit(choice_index=controller.current_card().correct_index)
    controller.continue_card()
    assert controller.current_card().vocab_id == FIETS
    controller.submit(choice_index=0 if controller.current_card().correct_index != 0 else 1)
    controller.continue_card()
    assert controller.level_of(FIETS) == INTRODUCTION


def test_repeated_guided_failures_reveal_more_then_step_down():
    controller = session([pool()[0]], level_overrides={FIETS: GUIDED_TYPING})
    assert controller.current_card().mask.startswith("d_")
    assert "de fiets" not in controller.current_card().mask
    controller.submit("nope")
    controller.continue_card()
    assert controller.current_card().kind == GUIDED_TYPING
    assert controller.current_card().mask.startswith("de")
    controller.submit("nope")
    controller.continue_card()
    assert controller.current_card().kind == MISSING_LETTERS


def test_mask_keeps_unicode_space_and_punctuation():
    rng = random.Random(1)
    masked = mask_target("één", rng)
    assert masked is not None
    assert len(masked) == len("één")
    assert "_" in masked
    phrase = mask_target("op de fiets", rng)
    assert " " in phrase
    assert phrase.replace("_", "") != ""
    punct = mask_target("rock-'n'-roll", rng)
    assert "-" in punct and "'" in punct
    assert mask_target("é", rng) is None
    guidance = guided_guidance("één", 1)
    assert "één" not in guidance
    assert guided_pattern("één", 1) != "één"
    assert "_" in guided_pattern("één", 1)
    assert "één" not in guided_pattern("één", 2)


def test_ambiguous_or_thin_pools_fall_back():
    twin = word(POORT, "de poort", "bicycle")
    card = build_exercise(pool()[0], [pool()[0], twin], random.Random(1), "nl", MULTIPLE_CHOICE)
    assert card.kind != MULTIPLE_CHOICE
    assert card.intended_kind == MULTIPLE_CHOICE
    thin = build_exercise(pool()[0], [pool()[0]], random.Random(1), "nl", MULTIPLE_CHOICE)
    assert thin.kind != MULTIPLE_CHOICE


def test_hint_leaves_independent_recall_without_a_write():
    controller = session([pool()[0]], level_overrides={FIETS: INDEPENDENT_RECALL})
    result = controller.request_assistance()
    assert result.status == "help"
    assert result.write is None
    assert controller.current_card().kind == GUIDED_TYPING
    assert controller.counters.independent_answered == 0


def test_independent_recall_records_once_and_near_is_not_mastery():
    controller = session([pool()[0]], level_overrides={FIETS: INDEPENDENT_RECALL})
    # "fietsen" is a near miss only when distance and length qualify; use a short typo on a long form.
    result = controller.submit("de fiets")
    assert result.write is not None
    assert result.write.verdict == "exact"
    assert result.write.mastered is True
    assert result.write.hint_used is False
    again = controller.submit("de fiets")
    assert again.status == "ignored"
    assert again.write is None
    controller.continue_card()

    other = session(
        [word(BOEK, "het boek", "book")],
        level_overrides={BOEK: INDEPENDENT_RECALL},
    )
    near = other.submit("het boeek")
    assert near.write is not None
    assert near.write.verdict == "near"
    assert near.write.mastered is False
    assert "het boek" in near.feedback
    assert config.ui("chưa phải lần tự nhớ chính xác", "not an exact recall") in near.feedback
    wrong = session(
        [word(WATER, "het water", "water")],
        level_overrides={WATER: INDEPENDENT_RECALL},
    )
    missed = wrong.submit("nope")
    assert missed.write.mastered is False
    assert missed.write.verdict == "wrong"
    assert wrong.counters.words_completed == 0


def test_non_independent_exercises_do_not_ask_for_a_write():
    controller = session([pool()[0]])
    writes = []
    while controller.current_card() and controller.current_card().kind != INDEPENDENT_RECALL:
        card = controller.current_card()
        if card.kind == INTRODUCTION:
            result = controller.continue_card()
        elif card.kind == MULTIPLE_CHOICE:
            result = controller.submit(choice_index=card.correct_index)
            controller.continue_card()
        else:
            result = controller.submit(card.reveal_word)
            controller.continue_card()
        if result.write is not None:
            writes.append(result.write)
    assert writes == []
    assert controller.counters.words_completed == 0


def test_apply_write_is_the_only_progress_path_and_runs_once():
    class ProgressSink:
        def __init__(self):
            self.calls = []

        def record(self, word, correct, autosave=True, reviewed_at=None, *, vocab_id=None):
            self.calls.append((word, correct, vocab_id))

    class AttemptSink:
        def __init__(self):
            self.rows = []

        def record(self, attempt):
            self.rows.append(attempt)

    controller = session([pool()[0]], level_overrides={FIETS: INDEPENDENT_RECALL})
    result = controller.submit("nope")
    progress = ProgressSink()
    attempts = AttemptSink()
    apply_independent_write(progress, attempts, result.write, timestamp="2026-11-27T12:00:00+00:00")
    assert progress.calls == [("de fiets", False, FIETS)]
    assert len(attempts.rows) == 1
    assert attempts.rows[0].hint_used is False
    intro = session([pool()[0]])
    assert intro.continue_card().write is None


def test_language_isolation_and_leave_do_not_complete_the_study_session():
    english_attempt = attempt(FIETS, correct=False, verdict="wrong", language="en")
    dutch = session([pool()[0]], attempts=[english_attempt])
    assert dutch.current_card().kind == INTRODUCTION
    english = AdaptiveVocabularySession(
        [word(FIETS, "the bicycle", "fiets")],
        language_code="en",
        pool=[word(FIETS, "the bicycle", "fiets"), word(HUIS, "the house", "huis"), word(BOEK, "the book", "boek")],
        attempts=[english_attempt],
        rng=random.Random(1),
    )
    assert english.current_card().kind == GUIDED_TYPING
    assert dutch.state_key(FIETS) != english.state_key(FIETS)

    plan = DailyStudyPlan(
        language_code="nl",
        vocab_total=1,
        due_review_count=0,
        new_word_count=1,
        future_review_count=0,
        attention_word_count=0,
        planned_vocab_count=1,
        reading_enabled=True,
        listening_enabled=True,
    )
    study = build_study_session(plan)
    bridge = AdaptiveSessionBridge(study, dutch, locked=False)
    bridge.leave()
    assert study.vocabulary_complete() is False
    assert study.status(KIND_READING) == "pending"
    assert bridge.note_finished() is False
    with pytest.raises(AdaptivePreviewRefused):
        AdaptiveSessionBridge(study, dutch, locked=True)


def test_audio_stays_hidden_until_independent_submit():
    controller = session([pool()[0]], level_overrides={FIETS: INDEPENDENT_RECALL})
    card = controller.current_card()
    assert speech_for_card(card, "answer").allowed is False
    intro = session([pool()[0]]).current_card()
    assert speech_for_card(intro, "answer").allowed is True
    assert intro.show_example == "Ik ga met de fiets."
    bare = session([word(HUIS, "het huis", "house")]).current_card()
    assert bare.show_example == ""


def test_prolonged_failure_keeps_every_word_and_does_not_finish():
    one = session([pool()[0]], level_overrides={FIETS: INDEPENDENT_RECALL})
    one._states[FIETS].presentations = 48
    for _ in range(5):
        assert one.current_card() is not None
        assert one.current_card().vocab_id == FIETS
        one.submit("nope")
        one.continue_card()
    assert one._states[FIETS].presentations == 53
    assert one.counters.words_completed == 0
    assert one.counters.independent_mastered == 0
    assert one.finished is False
    assert list(one._order) == [FIETS]

    both = session(
        [pool()[0], pool()[1]],
        level_overrides={FIETS: INDEPENDENT_RECALL, HUIS: INDEPENDENT_RECALL},
    )
    for state in both._states.values():
        state.presentations = 48
    seen = []
    for _ in range(6):
        card = both.current_card()
        assert card is not None
        seen.append(card.vocab_id)
        both.submit("nope")
        both.continue_card()
    assert seen == [FIETS, HUIS, FIETS, HUIS, FIETS, HUIS]
    assert both._states[FIETS].presentations > 48
    assert both._states[HUIS].presentations > 48
    assert both.counters.words_completed == 0
    assert both.counters.independent_mastered == 0
    assert both.finished is False
    assert set(both._order) == {FIETS, HUIS}


def test_empty_or_invalid_plan_is_not_a_completed_session():
    empty = AdaptiveVocabularySession([], language_code="nl", rng=random.Random(1))
    assert empty.current_card() is None
    assert empty.finished is False
    assert empty.take_completion() is False
    invalid = AdaptiveVocabularySession(
        [{"word": "de fiets", "meaning": "bicycle"}],
        language_code="nl",
        rng=random.Random(1),
    )
    assert invalid.current_card() is None
    assert invalid.finished is False
    plan = DailyStudyPlan(
        language_code="nl",
        vocab_total=0,
        due_review_count=0,
        new_word_count=0,
        future_review_count=0,
        attention_word_count=0,
        planned_vocab_count=1,
        reading_enabled=True,
        listening_enabled=True,
    )
    study = build_study_session(plan)
    bridge = AdaptiveSessionBridge(study, empty, locked=False)
    assert bridge.note_finished() is False
    assert study.vocabulary_complete() is False
    assert study.status(KIND_READING) == "pending"


def test_missing_letter_fields_rebuild_the_word_without_a_write():
    assert reconstruct_mask("d_ fi_ts", ["e", "e"]) == "de fiets"
    assert reconstruct_mask("w_ll-'n'-r_ll", ["e", "o"]) == "well-'n'-roll"
    assert reconstruct_mask("é_n", ["é"]) == "één"
    assert reconstruct_mask("d_", [""]) == "d"
    controller = session([pool()[0]], level_overrides={FIETS: MISSING_LETTERS})
    card = controller.current_card()
    assert card.kind == MISSING_LETTERS
    assert card.support_level == "assisted"
    fills = [card.reveal_word[index] for index, char in enumerate(card.mask) if char == "_"]
    answer = reconstruct_mask(card.mask, fills)
    result = controller.submit(answer)
    assert result.write is None
    assert result.success is True
    assert controller.counters.assisted_successes == 1
    assert controller.counters.independent_answered == 0


def test_legacy_quiz_still_records_an_independent_answer(tmp_path):
    from attempt_history import AttemptHistory
    from progress import Progress
    from vocab_store import VocabStore

    path = tmp_path / "vocab.json"
    path.write_text("[]", encoding="utf-8")
    store = VocabStore(str(path))
    store.add("de fiets", "bicycle")
    progress = Progress(str(tmp_path / "progress.json"))
    attempts = AttemptHistory(str(tmp_path / "attempts.jsonl"), language_code="nl")
    engine = QuizEngine(store, progress, target=1, attempt_history=attempts, language_code="nl")
    engine.pick_next()
    engine.submit("de fiets")
    assert len(attempts.load_attempts()) == 1
    assert attempts.load_attempts()[0].correct is True
