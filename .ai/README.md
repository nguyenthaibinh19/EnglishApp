# StudyGuard project memory (`.ai/`)

This directory is **durable engineering memory** for langstudyguard / StudyGuard.

## Purpose

The **repository** is the long-term source of truth for architecture, decisions, and procedures.

Chat / conversation history is **working context only**. It is not durable memory. A future AI coding agent or developer should be able to reconstruct important project state from `.ai/` + code + tests + Git — without needing prior chats.

Project memory:

- explains **why**, **boundaries**, **contracts**, and **constraints**;
- does **not** replace code, tests, or Git history;
- does **not** need to be bundled into the frozen desktop executable.

## Source-of-truth hierarchy

```text
Tests / executable behavior
        +
Current code
        +
ADRs / invariants
        +
Git history
        +
Roadmap / current state
```

If documentation conflicts with tested current behavior, **investigate the conflict** — do not blindly trust either side.

- **Tests** are authoritative for enforceable behavior.
- **ADRs** explain why decisions were made.
- **Code** is authoritative for exact implementation.

## Recommended agent workflow

1. Read [`current_state.md`](current_state.md)
2. Read [`invariants.md`](invariants.md)
3. Read relevant architecture / ADR files
4. Inspect relevant code
5. Inspect tests
6. Make the smallest safe change
7. Run `python -m pytest`
8. Run `python app/smoke_test.py` when relevant
9. Update durable memory **only if** architecture, schema, invariants, or roadmap changed

## What belongs here

- accepted architecture decisions (ADRs)
- schema contracts and identity rules
- invariants and security boundaries
- migration constraints
- roadmap direction
- recurring procedures
- known long-term debt / lessons

## What does **not** belong here

- temporary debugging notes
- raw chat transcripts
- exhaustive lists of edited files for a single session
- test runtime durations
- ephemeral implementation details discoverable from one function
- fixed bugs that no longer matter

## Index

| File | Role |
|------|------|
| [current_state.md](current_state.md) | Start here — product + position snapshot |
| [architecture.md](architecture.md) | Subsystem boundaries |
| [invariants.md](invariants.md) | Rules that must not be broken |
| [roadmap.md](roadmap.md) | Directional plan |
| [lessons.md](lessons.md) | Durable engineering lessons |
| [decisions/](decisions/) | Architecture Decision Records (through ADR-011) |
| [procedures/](procedures/) | How-to checklists |
| [procedures/HOW_TO_UPDATE_PROJECT_MEMORY.md](procedures/HOW_TO_UPDATE_PROJECT_MEMORY.md) | When/how to update `.ai/` memory |
