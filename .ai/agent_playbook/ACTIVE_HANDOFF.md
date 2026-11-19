# Active handoff

Rolling coordination checkpoint. See [current_state.md](../current_state.md), [roadmap.md](../roadmap.md), [ADR-025](../decisions/ADR-025-environment-identity-and-isolation.md), and [STAGING_EXE_PRODUCT_OWNER_GUIDE.md](../procedures/STAGING_EXE_PRODUCT_OWNER_GUIDE.md). Do not treat a commit/merge as a live activation.

## 1. Checkpoint metadata

- Written: 2026-11-19 (ADR-025 Architect R1 safety fixes).
- **18C.1 CLOSED — Architect Accepted** (PR #20).
- **18C.2 CLOSED — Architect Accepted** (PR #21).
- **ADR-025 / PR #22** — R1 targeted safety fixes applied; **STOP for Architect merge review**.
- **18B.9 Off-box Recovery — PAUSED, NOT CLOSED**
- Production Cloud Sync remains **OFF**.
- **Staging reserved for future use** — EXE may exist; no staging backend or user trial now. Local testing → development/localhost.

## 2. Last results

- F1: `LG_DATA_DIR` cannot point non-production builds at production AppData/install (overlap-aware).
- F2: Account/sync clients refuse credentialed HTTP redirects (synthetic localhost→production Location covered).
- F3: Login/setup windows show STAGING / DEVELOPMENT / PRODUCTION / ENVIRONMENT ERROR before credentials.

## 3. Next

1. Architect merge review of PR #22 — **do not merge until Accepted**.
2. Do not activate staging trial or staging backend without new Owner authorization.
3. Resume 18B.9 only under new Owner authorization.
4. Production Cloud Sync activation remains separately gated.

## 4. STOP / boundaries

- No VPS/SSH, production DB, production `STUDY_SYNC_ENABLED=1`, Google Drive/OAuth, or off-box changes without new Owner approval.
- Do not overwrite `D:\EnglishApp\dist\langstudyguard.exe` / `.zip` / `.bak` with staging artifacts.
- Phase 18B.9 **OPEN but PAUSED**. Drive **NOT CONFIGURED**. Cloud Sync **OFF**.
