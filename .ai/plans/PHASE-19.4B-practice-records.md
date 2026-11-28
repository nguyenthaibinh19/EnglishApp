# Phase 19.4B practice records

Status: Ready for review. Not merged. Branch `phase19.4b/practice-records`. Review commit `0df2ee5b32e7b032d96f5ec171dd5a4f64bc191b`. Baseline `8fa61e304eee4ac5a609eb87dbc50d638c52f9df`. Decision: [ADR-026](../decisions/ADR-026-practice-records.md). Tag `APP_19D4B_PERSISTENT_PRACTICE_READY_FOR_REVIEW`.

This follows Phase 19.1 section 10 and E2. It adds a local practice file to the unlocked adaptive preview. It does not replace the legacy quiz, and it is not part of the installed v1.5.0 download.

## Contract

Format version 1. Policy id `adaptive-vocab-session-v1`. That id is not an SRS algorithm id.

| Field | Meaning |
|---|---|
| Practice event id | UUID for this stored event |
| Exercise instance id | UUID for one shown exercise. Repeating that submission does not insert another row |
| Session id | The adaptive session that showed the exercise |
| Vocabulary id | Stable vocabulary UUID |
| Study language | Language of the exercise |
| Actual kind and intended kind | The card that was shown, and the step the ladder asked for |
| Support level | `recognition` or `assisted` |
| Outcome | `acknowledged`, `exact`, `near`, or `wrong` |
| Error class | Empty on success. `spelling` only for a near answer. `vocabulary` for a wrong answer |
| Occurred at | UTC timestamp |
| Policy id | `adaptive-vocab-session-v1` |
| Format version | `1` |

Introduction acknowledgement is its own outcome. It is not a graded answer. Empty input, an unfinished missing-letter card, a second Check, a hint request, playback, and closing without a submission do not create a row. Independent recall does not create a practice row. It still uses the existing attempt path.

The store orders rows by occurrence time and then by append order. A retry of the same exercise instance returns the first row. A different outcome for that instance is rejected. Invalid rows and version 2 files are refused or ignored. They are not rewritten.

The practice file owns these events. AttemptHistory still owns independent answers. Progress still owns SRS aggregates. Guest files and account files are separate. Nothing copies one into the other.

## Storage

`practice_records.db` is a small SQLite file. Guest path: `languages/{code}/practice_records.db`. Account path: `accounts/{user_id}/practice_records.db`. The schema version is 1. The caller passes an explicit data root. Production AppData is refused. The preview and the tests do not open the installed data directory.

Each submitted recognition or assisted exercise adds one short row. The row has no learner answer. This phase does not delete rows. The start rule ignores rows older than 14 days, but the rows remain. A future account or guest deletion must remove this file with that data root. A future retention pass may drop old rows and must not rewrite the rows it keeps. Sync, if it is added later, is additive and must not turn these rows into progress events.

## What the preview writes

The adaptive window appends the row when the submission is valid, before the learner leaves. If the write fails, the card says the practice result was not saved. The session can still continue. A failed write is not described as saved.

Practice rows do not call `Progress.record`, do not change SRS, do not clear Mistake Book attention, and do not create a Cloud Sync outbox event.

## Cross-session start

The in-session rule is unchanged: two failures at the same step move one step easier.

The next session uses recent practice only as a start hint.

- An exact unaided attempt, or a mastered streak, starts at independent recall. Later assisted success does not change that, and it does not make the word mastered.
- A non-mastered independent attempt still starts at guided typing. Assisted success does not promote it. Two newer practice failures can start one step easier.
- A new word with no attempt starts at introduction. A recent success starts one step harder and stops at guided typing. Two recent failures start one step easier.
- Missing, stale, invalid, and unsupported-version rows are ignored. The old start rule remains.

SRS due dates are not read from this file.

## Restart evidence

`python scripts/adaptive_vocabulary_preview.py --practice-demo` rewrites synthetic Dutch data under `D:\EnglishApp\.local\19d4b-preview\demo`. The evidence file is `practice-evidence.json`.

One new word was acknowledged, answered exactly on multiple choice, and answered exactly on missing letters. The session was left before independent recall. Reopening the same file started at guided typing. Independent recall then used the existing attempt path: one mastered attempt, and no new practice row. No `account_study.db` was created.

A second session had a non-mastered independent attempt, so the start without practice was guided typing. Two wrong guided submissions were saved. Reopening started at missing letters.

The interactive preview uses `D:\EnglishApp\.local\19d4b-preview\interactive` and prints the starting exercise when it opens. The installed Study button is unchanged.

## Tests

`tests/test_practice_records.py`: 5 passed, on real temporary SQLite files. They cover restart, idempotent insert, account and guest separation, language separation, a refused production data root, an unsupported schema version, stale and unsupported rows, and no progress write.

`tests/test_adaptive_vocabulary.py` and `tests/test_adaptive_vocabulary_ui.py`: 28 passed. The window saved an acknowledgement and a recognition answer, ignored an empty missing-letter card, a hint, and playback, left the day unfinished, and showed an unsaved notice when the store raised.

`tests/test_quiz_engine.py` and `tests/test_study_card_ui.py` passed together in their own process: 10 passed. The legacy quiz still records.

## Remaining integration

- The production study button still opens the legacy quiz.
- Locked sessions still cannot open the adaptive window.
- Practice rows are not synced and are not imported from guest to account.
- `account_study.db` is not migrated.
- Old practice rows are not deleted by this phase.
- Sentence practice and Grammar Companion are not in this flow.
- No executable was built. v1.5.0 does not contain this file.
