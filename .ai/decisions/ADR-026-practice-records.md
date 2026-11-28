# ADR-026 Practice records

Status: **Proposed for review.** Not merged. Not a release. Branch `phase19.4b/practice-records`.

## Context

Phase 19.1 section 10 and E2 require an append-only practice record for recognition and assisted vocabulary. Those exercises cannot be stored as today's progress events. A progress event is `exact`, `near`, or `wrong`, and the server applies the SRS ladder from it. An assisted success must not be sent as one of those events.

Phase 19.4A already shows the exercises. It keeps recognition and assisted results in memory. Independent recall already appends one `LearningAttempt`.

## Decision

A practice event is a separate record. It is not a `LearningAttempt` and it is not an SRS review.

The record format is version 1. Each row has a practice event id, an exercise instance id, a session id, the vocabulary UUID, the study language, the actual kind, the intended kind, the support level, the outcome, an observable error class, a UTC occurrence time, and the policy id `adaptive-vocab-session-v1`. That policy id is not an SRS algorithm id.

Introduction is stored as `acknowledged`. Graded recognition and assisted answers are stored as `exact`, `near`, or `wrong`. A near answer is the only spelling class this phase records. A wrong answer is a vocabulary miss. Conjugation, word order, and grammar are not inferred. The row does not store the learner's typed answer.

The same exercise instance is inserted once. A repeat of that submission returns the stored row. A different outcome for the same instance is rejected. Rows are not updated. Equal timestamps keep append order.

The file is `practice_records.db`. A guest language uses `languages/{code}/practice_records.db`. An account uses `accounts/{user_id}/practice_records.db`. Neither file is `account_study.db`. The caller must pass an explicit data root. Production AppData is refused. Guest rows are not copied into an account file.

Writing a practice row does not call `Progress.record`, does not change SRS fields, does not clear Mistake Book attention, and does not enqueue a Cloud Sync progress event. Independent recall keeps the existing attempt path and does not also write a practice row.

The cross-session start rule is conservative. An exact unaided attempt, or an existing mastered streak, still starts at independent recall. Assisted success does not promote a non-mastered word to independent recall. For a new word, the latest recent success starts one step harder and stops at guided typing. Two recent failures at the tail start one step easier. Records older than 14 days, records that fail validation, and records whose format version is not 1 are ignored. The in-session step-down remains two failures. SRS due dates stay on the existing scheduler.

A future sync revision, if practice records are synced, is additive. Old clients and the current server keep accepting only `exact`, `near`, and `wrong` progress events. An unknown practice record on an older server is ignored. It must not block vocabulary sync.

## Why

The learning engine can remember recognition and assisted practice without pretending that practice was an independent review.

## Consequences

Easier: a later session can start from saved evidence. Harder: two local files now exist beside AttemptHistory, and a future deletion or sync pass has to know about both. This phase does not delete old rows and does not sync them.

## Do not

Do not write practice rows into `account_study.db`. Do not import guest practice into an account. Do not send a practice row as a progress event. Do not treat assisted success as mastery.
