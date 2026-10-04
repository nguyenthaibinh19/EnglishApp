# ADR-008 Study Session

Status: Accepted

## Context

Lock-mode activity flow mixed logical “what’s left to do” with Tkinter window/lock enforcement, making optional reading and offline AI failures hard to reason about.

## Decision

`StudySession` owns logical activity state (pending/active/completed/skipped/unavailable). Vocabulary is required when planned count > 0. Reading is optional when enabled. ScreenGuard/Tkinter remains the enforcement layer for lock/fullscreen.

## Why

Logical completion must be testable without GUI. Reading/AI failure must not trap the learner after required work.

## Consequences

Easier: add activities via planner → session → Tk adapter. Harder: must not smuggle lock rules into the domain model.

## Do not

Do not move ScreenGuard/security into StudySession. Do not insert new activities as ad-hoc chains only in `main.py`.
