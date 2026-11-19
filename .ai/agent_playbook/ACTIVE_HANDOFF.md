# Active handoff

Rolling coordination checkpoint. See [current_state.md](../current_state.md), [roadmap.md](../roadmap.md), [ADR-025](../decisions/ADR-025-environment-identity-and-isolation.md), and [STAGING_EXE_PRODUCT_OWNER_GUIDE.md](../procedures/STAGING_EXE_PRODUCT_OWNER_GUIDE.md). Do not treat a commit/merge as a live activation.

## 1. Checkpoint metadata

- Written: 2026-11-19 (environment identity / staging EXE readiness).
- **18C.1 CLOSED — Architect Accepted** (PR #20).
- **18C.2 CLOSED — Architect Accepted** (PR #21).
- **ADR-025 Environment Identity and Isolation** — implementation PR open; **STOP for Architect review** (do not merge without review).
- **18B.9 Off-box Recovery — PAUSED, NOT CLOSED**
- Production Cloud Sync remains **OFF**.

## 2. Last results

- Explicit `development` / `staging` / `production` identity via `build_manifest.json` + runtime validation.
- Staging AppData isolation; production token/host refuse; StudyMaster environment banner + details.
- Staging EXE: `dist-staging/langstudyguard-staging.exe` (production `dist/langstudyguard.exe` untouched).

## 3. Next

1. Architect review of ADR-025 / isolation PR — **do not merge until Accepted**.
2. Product Owner staging trial per [STAGING_EXE_PRODUCT_OWNER_GUIDE.md](../procedures/STAGING_EXE_PRODUCT_OWNER_GUIDE.md).
3. Resume 18B.9 only under new Owner authorization.
4. Production Cloud Sync activation remains separately gated.

## 4. STOP / boundaries

- No VPS/SSH, production DB, production `STUDY_SYNC_ENABLED=1`, Google Drive/OAuth, or off-box changes without new Owner approval.
- Do not overwrite `D:\EnglishApp\dist\langstudyguard.exe` / `.zip` / `.bak` with staging artifacts.
- Phase 18B.9 **OPEN but PAUSED**. Drive **NOT CONFIGURED**. Cloud Sync **OFF**.
