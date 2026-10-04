# ADR-006 SRS v2

Status: Accepted

## Context

Weight-only scheduling lacked explicit next-review dates. Learners and Daily Study needed clear due/future semantics.

## Decision

Persist per-word `interval_days` and `due_at`. Fixed ladder: streak 1→1d, 2→3d, 3→7d, 4→14d, ≥5→30d. Non-mastered review sets interval 0 and due-at = review time. Legacy missing `due_at` counts as due. Within-session requeue remains separate from long-term due.

## Why

Explicit schedules are understandable and testable. Ladder is deliberately simple and replaceable later (e.g. FSRS) without UI rewrite.

## Consequences

Easier: Daily Study due/future split. Harder: must not mix FSRS fields into current schema prematurely.

## Do not

Do not label future reviews as due. Do not prematurely merge FSRS state into Progress. Do not conflate session requeue with SRS due dates.
