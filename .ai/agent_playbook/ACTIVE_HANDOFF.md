# Active handoff

Rolling coordination checkpoint. See [current_state.md](../current_state.md), [roadmap.md](../roadmap.md), and [ADR-025](../decisions/ADR-025-environment-identity-and-isolation.md). Do not treat a commit/merge as a live activation.

## 1. Checkpoint metadata

- Written: 2026-11-19 (ADR-025 / PR #22 merged).
- **ADR-025 Environment Identity and Isolation — Accepted** (PR #22 merge `2da93c3`).
- **18C.1 CLOSED — Architect Accepted** (PR #20).
- **18C.2 CLOSED — Architect Accepted** (PR #21).
- **18B.9 Off-box Recovery — PAUSED, NOT CLOSED**
- Production Cloud Sync remains **OFF**.
- **Staging reserved for future use** — EXE may exist; no staging backend or user trial. Local testing → development/localhost.

## 2. Last results

- PR #22 merged to `main` at `2da93c3` (approved head `71e142b`).
- F1–F3 isolation safeguards in source: data-root validation, redirect refusal, pre-login identity.
- Staging EXE reference (local, not a production install): `dist-staging/langstudyguard-staging.exe`.

## 3. Next

1. Do **not** auto-start a new milestone.
2. Development / localhost testing available; do not activate staging backend/trial.
3. Resume 18B.9 only under new Owner authorization.
4. Production Cloud Sync activation remains separately gated.

## 4. STOP / boundaries

- No VPS/SSH, production DB, production `STUDY_SYNC_ENABLED=1`, Google Drive/OAuth, or off-box changes without new Owner approval.
- Do not overwrite `D:\EnglishApp\dist\langstudyguard.exe` / `.zip` / `.bak`.
- Phase 18B.9 **OPEN but PAUSED**. Drive **NOT CONFIGURED**. Cloud Sync **OFF**.
