# ADR-014 Learning Progress Dashboard is derived read-only state

Status: Accepted

## Context

After AttemptHistory, Mistake Book, SRS, and DailyStudyPlanner, learners need a calm Progress screen. Persisting a second analytics summary would drift from Progress / attempts and invite dual sources of truth.

## Decision

The Progress Dashboard recomputes a `LearningProgressSnapshot` from current VocabStore + Progress + AttemptHistory + MistakeBook (via existing DailyStudy / SRS helpers). Metrics are not written to `analytics.json` or similar. UI presentation lives in a Progress view-model; Tkinter does not redefine mastery / due / attention.

## Why

Aggregates and events already answer “state now” and “what happened”. A derived read model keeps analytics honest and offline.

## Consequences

Easier: Home → Progress without algorithm changes. Harder: large attempt histories must be aggregated in one pass (no O(vocab × history) loops).

## Do not

Do not invent “mastered words” without a durable word-level definition. Do not gamify (XP/badges). Do not call network/AI from the Progress screen.
