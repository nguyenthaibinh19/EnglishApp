# Lessons

Durable engineering lessons from Phases 1–14. Prefer these over repeating past mistakes.

## Separation of concerns

- Avoid combining **persistence** with **selection** logic (Progress vs Scheduler).
- Domain logic should remain **testable without Tkinter**.
- Derived UI state (Home, Mistake Book, Daily Study labels) must not become another **source of truth**.

## Migrations and identity

- Compatibility wrappers + idempotent migration beat destructive all-at-once rewrites.
- **Stable identity should precede rich metadata** (UUID before enrichment / CEFR / cloud sync).
- When rewriting user files: atomic temp + fsync + replace; never truncate first.
- Second load must not regenerate IDs or duplicate Progress/attempts.

## AI and security

- Introduce an **AI provider abstraction before** local-model / StudyGuard-AI work.
- Production secrets stay on the server; desktop talks HTTP with tokens.

## Product semantics

- Mastery ≠ “accepted answer” (exact + no hint).
- Future SRS reviews must never be labeled **due**.
- Reading failure must not hard-block session completion after required vocab.

## Engineering style

- Prefer a small pure module over a new framework.
- Tests should assert **behavior / invariants**, not private implementation details.
- Do not invent CI/CD, schemas, or features in docs that the repo does not support.
- Chat is disposable context; **repository memory** (`.ai/` + code + tests + Git) is durable.
