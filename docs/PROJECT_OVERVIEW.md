# LanguageGuard project overview

This page is the engineering companion to the public README. It records what is released, what exists only in development, and which older notes are historical.

Product name: LanguageGuard. Repository: `nguyenthaibinh19/EnglishApp`.

## What is released

Windows desktop **v1.5.0** is the public release: [v1.5.0 — Account Cloud Sync Update](https://github.com/nguyenthaibinh19/EnglishApp/releases/tag/v1.5.0), built from `154bf03c6856667cf1322cfe4e6f31996e05e09f`.

The release checkpoint suite was **978 passed, 24 skipped, 0 failed**. That number is a checkpoint, not a live CI badge. This repository has no GitHub Actions release pipeline.

The installed v1.4.0 client updated to that build through the in-app updater. The executable is unsigned.

`https://langstudyguard.com` is the deployed account and sync API. It is not a deployed marketing website.

Production Cloud Sync is on for a controlled pilot. Google Drive off-box backup is not configured and is not operational. A scheduled on-server sync backup exists, and a manual restore check of a backup was verified during the v1.5.0 backend work.

## What is implemented but not released

Phase 19 desktop UI work, including CustomTkinter home and study presentations, lives on review branches. Those screenshots in the README are development previews. They are not in the v1.5.0 download.

App-side consumer checks for contract **C-APP-AI-001 v0.2.0** are in the public repository. They do not switch the running app to a local model.

## What is planned or separate

| Workstream | Repository | Public status |
|---|---|---|
| Desktop and account API | `EnglishApp` (public) | v1.5.0 released. API deployed. |
| Website | private Astro repository | Product and download portal. Production deployment is not authorized. |
| Local AI | private runtime repository | Contract v0.2.0 accepted. `LocalAIProvider` is not authorized in the desktop app. |

Do not treat a private commit, a design note, or a lab backup as a released feature.

## Data and sync design

Accepted decisions worth reading:

- [ADR-002](../.ai/decisions/ADR-002-canonical-study-languages.md) — seven study languages, separate from the interface language.
- [ADR-003](../.ai/decisions/ADR-003-ai-provider-boundary.md) — AI calls go through a provider boundary. Production keys stay on the server.
- [ADR-004](../.ai/decisions/ADR-004-learning-attempt-history.md), [ADR-005](../.ai/decisions/ADR-005-mistake-book-semantics.md), [ADR-006](../.ai/decisions/ADR-006-srs-v2.md) — attempts, mistakes, and review spacing.
- [ADR-007](../.ai/decisions/ADR-007-daily-study-planner.md) and [ADR-008](../.ai/decisions/ADR-008-study-session.md) — the daily plan and the session.
- [ADR-009](../.ai/decisions/ADR-009-stable-vocabulary-identity.md) — immutable vocabulary UUIDs.
- [ADR-016](../.ai/decisions/ADR-016-listening-local-tts.md) — Windows voices only, and no silent fallback to another language.
- [ADR-018](../.ai/decisions/ADR-018-account-cloud-sync.md) and [ADR-022](../.ai/decisions/ADR-022-event-first-automatic-account-sync.md) — account sync. ADR-018 is the foundation. Later accepted work turned the pilot on. The foundation note's original "not in production" line is historical.
- [ADR-025](../.ai/decisions/ADR-025-environment-identity-and-isolation.md) — development, staging, and production data roots stay apart.

Older paragraphs in `.ai/ecosystem/SYSTEM_ARCHITECTURE.md` and in the long historical section of `.ai/current_state.md` still say Cloud Sync is off. The 2026-11-24 coordination checkpoint is the later statement: production Cloud Sync is on for the pilot, and Google Drive remains not configured.

## Where to read next

- [Project memory index](../.ai/README.md)
- [Architecture](../.ai/architecture.md)
- [Invariants](../.ai/invariants.md)
- [Current state](../.ai/current_state.md)
- [Agent workflow](../.ai/agent_playbook/AI_AGENT_WORKFLOW.md)
- [Repository registry](../.ai/ecosystem/REPO_REGISTRY.md)
- [Contract registry](../.ai/ecosystem/CONTRACT_REGISTRY.md)
- [How to release](../.ai/procedures/HOW_TO_RELEASE.md)
