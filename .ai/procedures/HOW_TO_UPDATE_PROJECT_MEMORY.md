# How to update project memory

Update `.ai/` **only for durable facts** — not for temporary debugging or session chatter.

## When to update what

| Change | Update |
|--------|--------|
| Architecture / subsystem boundaries | [`architecture.md`](../architecture.md) and a new or existing ADR where appropriate |
| Invariant / must-not-break rule | [`invariants.md`](../invariants.md) **and** corresponding tests |
| Schema / persistence contracts | [`current_state.md`](../current_state.md) + relevant ADR and/or procedure (e.g. vocab schema) |
| Completed or current roadmap phase | [`current_state.md`](../current_state.md) + [`roadmap.md`](../roadmap.md) |

## What does not belong in `.ai/`

- Temporary debugging notes
- Session-only implementation details
- Raw chat transcripts
- Exhaustive “files touched today” lists
- Details easily discovered from a single function in code

## ADR history

Do **not** rewrite old ADR history when a decision changes.

Instead:

1. Mark the old ADR status as **`Superseded by ADR-XXX`**
2. Create a **new Accepted** ADR (`ADR-XXX`) that records the replacement decision

## Authority

- Project memory must **not** duplicate easily discoverable implementation details.
- **Code and tests remain authoritative** for exact behavior.
- If memory conflicts with tested behavior, investigate — do not blindly trust either side.

## Related

- [`.ai/README.md`](../README.md) — purpose and agent workflow
- [`HOW_TO_RUN_TESTS.md`](HOW_TO_RUN_TESTS.md)
