# ADR-007 Daily Study Planner

Status: Accepted

## Context

Home and lock sessions needed a clear “what should I study today?” answer without each UI recalculating SRS/Mistake rules differently.

## Decision

`DailyStudyPlanner` derives NEW / DUE / FUTURE / NEEDS ATTENTION from VocabStore + Progress + Mistake summaries. Plans are not persisted. Planned vocab workload remains `min(vocab_total, QUIZ_TARGET_CORRECT)`. Scheduler still picks concrete items in-session.

## Why

One domain place for workload semantics. Prevents Home from becoming a second SRS engine.

## Consequences

Easier: consistent dashboard copy. Harder: planner must stay aligned with SRS/Mistake definitions.

## Do not

Do not present future-word quiz fallback as “due”. Do not persist DailyStudyPlan as authoritative state.
