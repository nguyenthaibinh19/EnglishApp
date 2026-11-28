# ADR-026 Practice records

Status: **Accepted.** Merged by PR #36 at `91d3c60f59c5d26d321433a9334c6af31e09c1a5`. Closeout corrections `5f27db9b946f909fdadc1e07609850848121e60a`. Review checkpoint `440a99ecb316e3a9c69e8c7ef72b591d2ac84b8e`. Not a release. Not in the installed v1.5.0 download.

## Context

Phase 19.1 section 10 and E2 require an append-only practice record for recognition and assisted vocabulary. Those exercises cannot be stored as today's progress events. A progress event is `exact`, `near`, or `wrong`, and the server applies the SRS ladder from it. An assisted success must not be sent as one of those events.

Phase 19.4A already shows the exercises. Independent recall already appends one `LearningAttempt`.

## Decision

A practice event is a separate record. It is not a `LearningAttempt` and it is not an SRS review.

The record format is version 1. Each row has a practice event id, an exercise instance id, a session id, the vocabulary UUID, a supported study language, the actual kind, the intended kind, the support level, the outcome, an observable error class, a UTC occurrence time, and the policy id `adaptive-vocab-session-v1`. That policy id is not an SRS algorithm id.

Introduction is stored as `acknowledged`. Graded recognition and assisted answers are stored as `exact`, `near`, or `wrong`. Support level must match the actual kind: introduction and multiple choice are recognition; missing letters and guided typing are assisted. A near answer is recorded as `near_match`. A wrong answer is recorded as `incorrect_answer`. Spelling, conjugation, word order, vocabulary sense, and grammar are not inferred from a generic wrong answer. The row does not store the learner's typed answer.

The same exercise instance is inserted once. A repeat of that submission returns the stored row only when session id, intended kind, support level, outcome, and error class also match. A contradictory replay is rejected. Rows are not updated. Ordering uses parsed UTC timestamps. Equal timestamps keep append order.

The file is `practice_records.db`. A guest language uses `languages/{code}/practice_records.db`. An account uses `accounts/{user_id}/practice_records.db`. Neither file is `account_study.db`. The caller must pass an explicit, non-empty data root. Production AppData, protected RC data, and recovery directories are refused for every runtime identity. Resolved paths, including symbolic links and junctions where the platform reports them, must stay under that root. Guest rows are not copied into an account file. Invalid stored rows are skipped on read. They do not crash adaptive startup and they are not rewritten.

Writing a practice row does not call `Progress.record`, does not change SRS fields, does not clear Mistake Book attention, and does not enqueue a Cloud Sync progress event. Independent recall keeps the existing attempt path and does not also write a practice row. If storage fails, the learner is told the practice result was not saved.

The cross-session start rule is conservative. An exact unaided attempt, or an existing mastered streak, still starts at independent recall. Assisted success does not promote a non-mastered word to independent recall. Practice that is older than, or equal to, the latest independent attempt cannot override that attempt. For a new word, the latest recent success starts one step harder and stops at guided typing. Two recent failures at the tail start one step easier. Records older than 14 days, records that fail validation, and records whose format version is not 1 are ignored. The in-session step-down remains two failures. SRS due dates stay on the existing scheduler.

A future sync revision, if practice records are synced, is additive. Old clients and the current server keep accepting only `exact`, `near`, and `wrong` progress events. An unknown practice record on an older server is ignored. It must not block vocabulary sync.

## Why

The learning engine can remember recognition and assisted practice without pretending that practice was an independent review.

## Consequences

Easier: a later session can start from saved evidence. Harder: two local files now exist beside AttemptHistory, and a future deletion or sync pass has to know about both. This phase does not delete old rows and does not sync them. StudyMaster still opens the legacy quiz.

## Do not

Do not write practice rows into `account_study.db`. Do not import guest practice into an account. Do not send a practice row as a progress event. Do not treat assisted success as mastery. Do not diagnose linguistic error classes beyond `near_match` and `incorrect_answer`.
