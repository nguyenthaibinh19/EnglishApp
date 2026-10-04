# ADR-001 Scheduler separation

Status: Accepted

## Context

Vocabulary selection and scoring weights lived mixed with Progress persistence, making scheduling policy hard to change without touching storage and UI.

## Decision

Progress stores learning state. `VocabScheduler` / scheduler modules select and weight candidates (and handle in-session requeue). QuizEngine orchestrates answers against Progress + AttemptHistory.

## Why

Long-term review policy (SRS, later FSRS) should evolve without rewriting Tkinter or Progress I/O. Pure scheduling is unit-testable.

## Consequences

Easier: swap or tune selection/due policy. Harder: callers must not reintroduce weight formulas inside Progress or UI.

## Do not

Do not put candidate selection or due-priority math back into Progress or Tk widgets.
