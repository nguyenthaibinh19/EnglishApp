# Phase 19.4A adaptive vocabulary

Status: Ready for review. Not merged. Branch `phase19.4a/adaptive-vocabulary`, created from main `445d62c986b83393a2ba1702c7c108c52aa3f096`. Tag `APP_19D4A_ADAPTIVE_VOCABULARY_READY_FOR_REVIEW`.

The installed public release remains v1.5.0. This preview is not that download. StudyMaster still opens the legacy quiz. A locked session cannot open this window.

## What the session does

Policy id: `adaptive-vocab-session-v1`. That id is not an SRS algorithm id. The step-down count is 2 consecutive failures at the same step. That number is a provisional session policy.

| Step | Exercise | Support | Persistent write |
|---|---|---|---|
| Introduction | See the word, meaning, and stored example. Listen and Listen slowly. | Recognition | None |
| Multiple choice | Pick the word for the meaning. | Recognition | None |
| Missing letters | Type the word with some letters shown. | Assisted | None |
| Guided typing | Type the word. The card says the spelling level. | Assisted | None |
| Independent recall | Type the word from the meaning. | Independent | Existing attempt and progress path, once per submission |

A new word starts at introduction. A word whose latest independent attempt was non-mastered starts at guided typing. A previously mastered word, including a due review, starts at independent recall.

A successful step advances one level and the word rotates behind the other planned words. Two failures at the same level step down one level. The first guided failure reveals one more character and stays on guided typing. Introduction has no failure state. Continue is the explicit action.

Asking for a hint on independent recall moves that word to guided typing. It does not create an attempt and it does not set `hint_used`.

## Completion and mastery

The practiced fraction counts a word only after an independent exact or near answer. Recognition and assisted successes have their own counters and do not fill that fraction.

Exact and unaided is mastered. Near is session-correct and is not mastery. Wrong is not session-correct. Both near and wrong still use the existing progress write, so the SRS ladder sees a non-mastered review. The session does not invent a new mastery formula.

An independent near or exact answer finishes that word for this session, so the word is not asked again today. A wrong independent answer stays in the session and can step down. Previously saved attempts stay saved if the learner leaves after Check.

Leaving before the completion screen does not mark today's vocabulary complete. Reading and listening stay pending. The completion callback runs once, from the completion screen.

## Exercise generation

Generation is local. A seeded `random.Random` makes the choices and masks repeatable. No model is called.

Multiple choice uses other vocabulary as distractors, drops duplicate and equivalent forms, and refuses a meaning that another entry also has. Fewer than two safe distractors falls back to another valid exercise. The intended step is unchanged by that fallback.

Missing letters keeps spaces, hyphens, apostrophes, and Unicode letters. A one-letter target is not a missing-letter exercise. Guided typing states the level and never shows the whole word as the hint. Independent recall hides the example and does not offer the answer audio until after Check.

The introduction example is the sentence already stored on the vocabulary record. An empty record shows that no example is stored.

## Data boundary

In-memory state is keyed by session, language, and vocabulary id. An English attempt does not set the Dutch starting level.

Introduction, multiple choice, and assisted practice do not call `Progress.record`, do not append a `LearningAttempt`, do not clear Mistake Book attention, do not enqueue a sync event, and do not change account preferences.

There is no schema migration and no practice-record table. That contract remains Phase 19.1 E2.

## Preview

`scripts/adaptive_vocabulary_preview.py` writes synthetic Dutch words to `D:\EnglishApp\.local\19d4a-preview` and opens the unlocked window. The interactive preview uses the shared speech provider. `--screenshots` uses a provider that reports no voice, so the pictures show the continue path without synthesis.

Screenshots from that run:

- `D:\EnglishApp\.local\19d4a-screenshots\introduction.png`
- `D:\EnglishApp\.local\19d4a-screenshots\multiple-choice.png`
- `D:\EnglishApp\.local\19d4a-screenshots\missing-letters.png`
- `D:\EnglishApp\.local\19d4a-screenshots\guided-typing.png`
- `D:\EnglishApp\.local\19d4a-screenshots\independent-recall.png`
- `D:\EnglishApp\.local\19d4a-screenshots\independent-incorrect.png`

## Tests

Domain tests in `tests/test_adaptive_vocabulary.py`: 13 passed. They are simulated. They are not proof of the window.

The simulated Dutch walk for a new word `de fiets` is introduction, multiple choice, missing letters, guided typing, then independent recall. One exact submission is the only write, and it is mastered.

A second simulated walk puts two words on multiple choice. A wrong answer on the first word yields the turn to the second word. A second wrong answer on the first word steps it down to introduction.

Guided typing shows level 1, then level 2 after one miss, then missing letters after the second miss.

GUI tests in `tests/test_adaptive_vocabulary_ui.py`: 2 passed, in a real CustomTkinter window. Leave saved nothing. A wrong independent answer appended one non-mastered attempt, and Check did not append a second. A provider with no voice left Continue usable.

`tests/test_study_card_ui.py` passed in its own process. The legacy quiz engine tests passed. A second `Tk()` in the same process is still not a combined-suite pass.

## Limits

- The production study button still opens the legacy quiz.
- Locked sessions stay on that quiz.
- Practice records are not stored.
- Sentence practice and Grammar Companion are not in this flow. The legacy quiz still has its own sentence-practice behavior.
- French and Italian voices were not part of this preview.
- No executable was built.
