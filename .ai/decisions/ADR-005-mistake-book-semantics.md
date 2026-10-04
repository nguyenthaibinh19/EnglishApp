# ADR-005 Mistake Book semantics

Status: Accepted

## Context

Learners need a current “needs attention” list. Permanently listing every past error is noisy and wrong after recovery.

## Decision

Needs-attention is **derived** from AttemptHistory: if the **latest** attempt for an item is non-mastered, it needs attention; if latest is mastered, it does not. `attention_count` may still summarize historical non-mastered attempts.

Mastery uses existing semantics (`exact` and not hint-assisted).

## Why

Simple, deterministic, matches learner intuition (“did I get it last time?”). No second persistence store.

## Consequences

Easier: Practice Mistakes and Home attention metrics. Harder: renaming/identity bugs show up as split attention groups if IDs are wrong.

## Do not

Do not turn Mistake Book into a permanent forever-error list. Do not invent a second mastery definition for attention.
