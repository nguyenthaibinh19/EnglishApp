# ADR-004 Learning attempt history

Status: Accepted

## Context

Progress alone could not power Mistake Book, analytics, or future AI datasets without reconstructing events from aggregates.

## Decision

Keep aggregate Progress separate from append-oriented `AttemptHistory` (JSONL). Each finalized vocabulary answer becomes a LearningAttempt event.

## Why

Aggregates answer “what is the state now?”; events answer “what happened?”. Both are needed.

## Consequences

Easier: Mistake Book and future personalization. Harder: two stores must stay semantically aligned on mastery (`correct`).

## Do not

Do not treat Progress counters as a complete event log. Do not rewrite JSONL casually without atomic safety and identity rules.
