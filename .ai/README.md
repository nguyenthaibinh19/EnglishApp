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

## Recommended reading order

1. Read [`current_state.md`](current_state.md)
2. Read [`invariants.md`](invariants.md)
3. Read [`agent_playbook/README.md`](agent_playbook/README.md) and then [`agent_playbook/AI_AGENT_WORKFLOW.md`](agent_playbook/AI_AGENT_WORKFLOW.md)
4. Read the ADR, architecture page, or procedure for the task
5. Inspect the code and tests named by the brief
6. Read a dated file under [`agent_playbook/handoffs/`](agent_playbook/handoffs/) only when resuming that snapshot

`current_state.md`, `invariants.md`, `architecture.md`, the ADRs, and `roadmap.md` remain authoritative for their subjects. The playbook owns collaboration, diffs, and handoff rules. A dated handoff is a historical snapshot and is not a second current state.

## Recommended agent workflow

The canonical loop is [`agent_playbook/AI_AGENT_WORKFLOW.md`](agent_playbook/AI_AGENT_WORKFLOW.md). In short:

1. Confirm the baseline SHA in the Leader brief
2. Read the memory files in the order above
3. Make the smallest testable change inside the brief
4. Run the required tests and report passed, failed, and skipped counts
5. Put the complete review diff in `diff/` and wait for review before commit
6. Update durable memory only when architecture, schema, invariants, or roadmap changed

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
| [decisions/](decisions/) | Architecture Decision Records (through ADR-022; ADR-022 is Accepted, architecture only, not implemented) |
| [procedures/SYNC_DB_OPERATIONS.md](procedures/SYNC_DB_OPERATIONS.md) | Sync backup/restore and activation checklist (not executed) |
| [plans/PHASE-18B.3-production-readiness.md](plans/PHASE-18B.3-production-readiness.md) | Phase 18B.3 production-readiness plan (Accepted; `97f7b25`) |
| [procedures/](procedures/) | How-to checklists |
| [procedures/HOW_TO_UPDATE_PROJECT_MEMORY.md](procedures/HOW_TO_UPDATE_PROJECT_MEMORY.md) | When/how to update `.ai/` memory |
| [agent_playbook/README.md](agent_playbook/README.md) | Collaboration playbook: workflow, diff standard, and chat handoffs |
| [agent_playbook/AI_AGENT_WORKFLOW.md](agent_playbook/AI_AGENT_WORKFLOW.md) | Canonical User / Leader / Developer / Codex workflow |
| [procedures/AI_AGENT_WORKFLOW.md](procedures/AI_AGENT_WORKFLOW.md) | Pointer to the canonical workflow |
