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

## Local speech

- Windows has two speech catalogs. A voice listed in System.Speech is not the same fact as a voice listed in Windows.Media.SpeechSynthesis.
- A locale map is not playback. Audible playback on one PC does not mean every study language has a voice.
- Learner text, voice id, and rate stay in environment data. The script stays fixed. Do not persist generated audio.
- A second `Tk()` in the same process is not a combined-suite pass.

## Third-party agent tools

- A proposed skill or local memory server is not project memory until a human accepts it. `.ai/` on GitHub remains the approved record.
- Inspect scripts, hooks, dependencies, licenses, and outbound data before any execution. Pin the reviewed commit. Do not download and execute an installer as the review.

## Windows installation

- `shutil.copy2` keeps the source timestamp, so an older executable can replace a newer install without looking newer.
- An installed launch must not recreate Startup. An external copy must not overwrite an existing install.
- Creating a `--lock` shortcut is not a test of that locked session or of Emergency Exit.

## Engineering style

- Prefer a small pure module over a new framework.
- Tests should assert **behavior / invariants**, not private implementation details.
- Do not invent CI/CD, schemas, or features in docs that the repo does not support.
- Chat is disposable context; **repository memory** (`.ai/` + code + tests + Git) is durable.
