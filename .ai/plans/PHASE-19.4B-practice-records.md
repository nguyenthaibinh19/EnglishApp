# Phase 19.4B practice records

Status: Closed 2026-11-28. Architect decision `APP_19D4B_FOUNDATION_ACCEPTED_CLOSEOUT_CORRECTIONS_REQUIRED`. Review checkpoint `440a99ecb316e3a9c69e8c7ef72b591d2ac84b8e`. Closeout corrections `5f27db9b946f909fdadc1e07609850848121e60a`. Merged to main by PR #36 at `91d3c60f59c5d26d321433a9334c6af31e09c1a5`. Decision: [ADR-026](../decisions/ADR-026-practice-records.md). Tag `APP_19D4B_CLOSED_PERSISTENT_PRACTICE`.

This follows Phase 19.1 section 10 and E2. It adds a local practice file to the unlocked adaptive preview. It does not replace the legacy quiz, and it is not part of the installed v1.5.0 download.

## Contract

Format version 1. Policy id `adaptive-vocab-session-v1`. That id is not an SRS algorithm id.

| Field | Meaning |
|---|---|
| Practice event id | UUID for this stored event |
| Exercise instance id | UUID for one shown exercise. Repeating that submission does not insert another row |
| Session id | The adaptive session that showed the exercise |
| Vocabulary id | Stable vocabulary UUID |
| Study language | A supported study language |
| Actual kind and intended kind | The card that was shown, and the step the ladder asked for |
| Support level | `recognition` or `assisted`, and it must match the actual kind |
| Outcome | `acknowledged`, `exact`, `near`, or `wrong` |
| Error class | Empty on success. `near_match` for a near answer. `incorrect_answer` for a wrong answer |
| Occurred at | Timezone-aware UTC timestamp |
| Policy id | `adaptive-vocab-session-v1` |
| Format version | `1` |

Introduction acknowledgement is its own outcome. It is not a graded answer. Empty input, an unfinished missing-letter card, a second Check, a hint request, playback, and closing without a submission do not create a row. Independent recall does not create a practice row. It still uses the existing attempt path.

Ordering uses parsed UTC timestamps. Equal timestamps keep append order. A retry of the same exercise instance returns the first row only when session id, intended kind, support level, outcome, and error class also match. A contradictory replay is rejected. Invalid rows and version 2 files are refused or ignored. They are not rewritten.

The practice file owns these events. AttemptHistory still owns independent answers. Progress still owns SRS aggregates. Guest files and account files are separate. Nothing copies one into the other.

## Storage

`practice_records.db` is a small SQLite file. Guest path: `languages/{code}/practice_records.db`. Account path: `accounts/{user_id}/practice_records.db`. The schema version is 1. The caller passes an explicit, non-empty data root. Production AppData, protected RC data, and recovery directories are refused for every runtime identity. Resolved paths must stay under that root. The preview and the tests do not open the installed data directory.

Each submitted recognition or assisted exercise adds one short row. The row has no learner answer. This phase does not delete rows. The start rule ignores rows older than 14 days, but the rows remain. A future account or guest deletion must remove this file with that data root. A future retention pass may drop old rows and must not rewrite the rows it keeps. Sync, if it is added later, is additive and must not turn these rows into progress events.

## What the preview writes

The adaptive window appends the row when the submission is valid, before the learner leaves. If the write fails, the card says the practice result was not saved. The session can still continue. A failed write is not described as saved.

Practice rows do not call `Progress.record`, do not change SRS, do not clear Mistake Book attention, and do not create a Cloud Sync outbox event.

## Cross-session start

The in-session rule is unchanged: two failures at the same step move one step easier.

The next session uses recent practice only as a start hint.

- An exact unaided attempt, or a mastered streak, starts at independent recall. Later assisted success does not change that, and it does not make the word mastered.
- A non-mastered independent attempt still starts at guided typing. Assisted success does not promote it. Practice older than, or equal to, that attempt cannot override it. Two newer practice failures can start one step easier.
- A new word with no attempt starts at introduction. A recent success starts one step harder and stops at guided typing. Two recent failures start one step easier.
- Missing, stale, invalid, and unsupported-version rows are ignored. The old start rule remains.

SRS due dates are not read from this file.

## Restart evidence

`python scripts/adaptive_vocabulary_preview.py --practice-demo` rewrites synthetic Dutch data under `D:\EnglishApp\.local\19d4b-preview\demo`. The evidence file is `practice-evidence.json`.

One new word was acknowledged, answered exactly on multiple choice, and answered exactly on missing letters. The session was left before independent recall. Reopening the same file started at guided typing. Independent recall then used the existing attempt path: one mastered attempt, and no new practice row. No `account_study.db` was created.

A second session had a non-mastered independent attempt, so the start without practice was guided typing. Two wrong guided submissions were saved. Reopening started at missing letters.

The interactive preview uses `D:\EnglishApp\.local\19d4b-preview\interactive` and prints the starting exercise when it opens. The installed Study button is unchanged.

## Tests

`tests/test_practice_records.py`: 8 passed, on real temporary SQLite files. They cover restart, idempotent insert, contradictory session and intended-kind replays, account and guest separation, language separation, refused production, RC, and recovery roots, an unsupported schema version, skipped invalid stored rows, older practice that cannot override a newer independent attempt, stale and unsupported rows, and no progress write.

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

## Next product priority

Phase 19.4C Adaptive Study Integration is the next product priority. It waits for a separate Architect brief.
