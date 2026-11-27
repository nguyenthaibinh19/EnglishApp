# Phase 19.4A adaptive vocabulary

Status: UX polish ready for review. Not merged. Branch `phase19.4a/adaptive-vocabulary`. UX polish `98d7bc09f44cdecaa838caa4721d504107555721`. UX parent `0f0925616f1baac1109a4839966056732473f266`. Functional correction `c5f17c5020d72d931b8b2f7022ecd1a57db2e96a`. Foundation parent `5087b33f1b56d5ec47e47f4b1db19b0ed930ee7d`. The branch was created from main `445d62c986b83393a2ba1702c7c108c52aa3f096`. Tag `APP_19D4A_UX_POLISHED_READY_FOR_REVIEW`.

Functional R1 is accepted. This pass changes the learner-facing cards. The ladder and the SRS write boundary stay as accepted.

The installed public release remains v1.5.0. This preview is not that download. StudyMaster still opens the legacy quiz. A locked session cannot open this window.

## What the session does

Policy id: `adaptive-vocab-session-v1`. That id is not an SRS algorithm id. The step-down count is 2 consecutive failures at the same step. That number is a provisional session policy.

| Step | Exercise | Support | Persistent write |
|---|---|---|---|
| Introduction | See the word, meaning, and stored example. Listen and Listen slowly. | Recognition | None |
| Multiple choice | Pick the word for the meaning. | Recognition | None |
| Missing letters | Fill only the hidden letters. Visible characters, spaces and marks stay fixed. | Assisted | None |
| Guided typing | Type the whole word. The card shows the revealed prefix and placeholders for the rest. | Assisted | None |
| Independent recall | Type the word from the meaning. | Independent | Existing attempt and progress path, once per submission |

A new word starts at introduction. A word whose latest independent attempt was non-mastered starts at guided typing. A previously mastered word, including a due review, starts at independent recall.

A successful step advances one level and the word rotates behind the other planned words. Two failures at the same level step down one level. The first guided failure reveals one more character and stays on guided typing. Introduction has no failure state. Continue is the explicit action.

The presentation cap is 48. It only prefers another planned word that is still under the cap. The pass rotates at most one full cycle, then builds the card. When every remaining word is at or past 48, the word already at the front stays there. The cap does not complete, discard, or master a word, and it does not reset the counter. One word past the cap keeps being shown. An empty plan, or a plan whose entries have no vocabulary id, has no card and is not a finished session. The window then offers Leave, and the completion callback does not run.

Asking for a hint on independent recall moves that word to guided typing. It does not create an attempt and it does not set `hint_used`.

## Completion and mastery

The practiced fraction counts a word only after an independent exact or near answer. Recognition and assisted successes have their own counters and do not fill that fraction.

Exact and unaided is mastered. Near is session-correct and is not mastery. Wrong is not session-correct. Both near and wrong still use the existing progress write, so the SRS ladder sees a non-mastered review. The session does not invent a new mastery formula.

An independent near or exact answer finishes that word for this session, so the word is not asked again today. A wrong independent answer stays in the session and can step down. Previously saved attempts stay saved if the learner leaves after Check.

Leaving before the completion screen does not mark today's vocabulary complete. Reading and listening stay pending. The completion card says so, and it does not call the day finished. The header counter is completed planned words over the plan size. It is not a percentage of the five steps. The completion callback runs once, from the completion screen.

## Exercise generation

Generation is local. A seeded `random.Random` makes the choices and masks repeatable. No model is called.

Multiple choice uses other vocabulary as distractors, drops duplicate and equivalent forms, and refuses a meaning that another entry also has. Fewer than two safe distractors falls back to another valid exercise. The intended step is unchanged by that fallback.

Missing letters keeps spaces, hyphens, apostrophes, and Unicode letters. The learner types only the blanks. The window rebuilds the word for the existing grader. A one-letter target is not a missing-letter exercise. Guided typing shows a prefix and placeholders, never the whole word, and does not print the internal level. Independent recall hides the example and does not speak the answer until after Check. A correct choice turns soft green. A different choice turns warm amber. Typed feedback shows the expected word in the same colors. Independent exact feedback says the learner recalled it on their own. Assisted success does not. Interface copy uses `config.ui` (Vietnamese, then English). A missing voice is mentioned only after a playback attempt.

The introduction example is the sentence already stored on the vocabulary record. An empty record shows that no example is stored.

## Data boundary

In-memory state is keyed by session, language, and vocabulary id. An English attempt does not set the Dutch starting level.

Introduction, multiple choice, and assisted practice do not call `Progress.record`, do not append a `LearningAttempt`, do not clear Mistake Book attention, do not enqueue a sync event, and do not change account preferences.

There is no schema migration and no practice-record table. That contract remains Phase 19.1 E2.

## Preview

`scripts/adaptive_vocabulary_preview.py` writes synthetic Dutch words to `D:\EnglishApp\.local\19d4a-preview` and opens the unlocked window. The interactive preview uses the shared speech provider and the saved device voice. Listen and Listen slowly use rates 0 and -4. Voice discovery stays off the Tk thread. A missing voice and a busy clip update the note for the current card only. `--screenshots` uses a provider that reports no voice and does not synthesize.

The unlocked screen guard first applies 1280×820. The preview then sets the compact study window to 560×640, with a minimum of 480×560. The legacy quiz stays 560×520. Lock is not turned on. The card fills the window and the primary button stays at the bottom. The card does not scroll. Four choices and the letter fields fit. This capture's window and bitmap were both 560×640.

Screenshots from that run:

- `D:\EnglishApp\.local\19d4a-screenshots\introduction.png`
- `D:\EnglishApp\.local\19d4a-screenshots\multiple-choice.png`
- `D:\EnglishApp\.local\19d4a-screenshots\missing-letters.png`
- `D:\EnglishApp\.local\19d4a-screenshots\guided-typing.png`
- `D:\EnglishApp\.local\19d4a-screenshots\independent-recall.png`
- `D:\EnglishApp\.local\19d4a-screenshots\independent-incorrect.png`
- `D:\EnglishApp\.local\19d4a-screenshots\choice-correct.png`
- `D:\EnglishApp\.local\19d4a-screenshots\correct-feedback.png`
- `D:\EnglishApp\.local\19d4a-screenshots\completion.png`

## Tests

Domain tests in `tests/test_adaptive_vocabulary.py`: 16 passed, including mask reconstruction, prolonged failure past 48 presentations, and an empty or id-less plan that does not report completion. They are simulated. They are not proof of the window.

The simulated Dutch walk for a new word `de fiets` is introduction, multiple choice, missing letters, guided typing, then independent recall. One exact submission is the only write, and it is mastered.

A second simulated walk puts two words on multiple choice. A wrong answer on the first word yields the turn to the second word. A second wrong answer on the first word steps it down to introduction.

Guided typing shows a one-character prefix, then a longer prefix after one miss, then missing letters after the second miss. The card does not print the policy level.

GUI tests in `tests/test_adaptive_vocabulary_ui.py`: 5 passed, on one Tk root, in a real CustomTkinter window. Leave saved nothing, and reading and listening stayed pending. A missing voice and a busy clip updated the current card only. A wrong independent answer appended one non-mastered attempt, and a second Check did not append another. An empty plan showed Leave and did not call the completion callback. One window walked introduction, multiple choice, missing letters, guided typing, and independent recall. Digit keys selected the choice. Missing letters accepted only the blanks, including backspace, and Enter submitted the rebuilt word. A correct choice turned soft green. The completion header showed 1/1. A re-entrant Check graded recognition once. Recognition and assisted steps wrote nothing. The completion button ran the callback once. A second completion call did not run it again.

`tests/test_quiz_engine.py` and `tests/test_study_card_ui.py` passed together in their own process: 10 passed. The legacy quiz still records. A second `Tk()` in the same process is still not a combined-suite pass.

## Limits

- The production study button still opens the legacy quiz.
- Locked sessions stay on that quiz.
- Practice records are not stored.
- Sentence practice and Grammar Companion are not in this flow. The legacy quiz still has its own sentence-practice behavior.
- French and Italian voices were not part of this preview.
- No executable was built.
