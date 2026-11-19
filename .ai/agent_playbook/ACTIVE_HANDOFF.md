# Active handoff

Rolling coordination checkpoint. See [current_state.md](../current_state.md), [roadmap.md](../roadmap.md), [ACCOUNT-UX-RELEASE-READINESS.md](../plans/ACCOUNT-UX-RELEASE-READINESS.md), and [ADR-025](../decisions/ADR-025-environment-identity-and-isolation.md).

## 1. Checkpoint metadata

- Written: 2026-11-19 (Account UX / RC — **Architect Accepted, source merged**).
- **ADR-025 Accepted** (PR #22 merge `2da93c3`).
- **Account UX / Release Candidate** — PR #23 **MERGED** (`a08a9e0`); approved source `3d44bb5`; tag `APP_ACCOUNT_UX_RC_MERGED_ACCEPTED`.
- **18C.1 / 18C.2 CLOSED**. **18B.9 PAUSED, NOT CLOSED**.
- Staging **RESERVED**. Production Cloud Sync **OFF**. Production sync pilot **NO-GO**.

## 2. Last results

- Architect Accepted: transactional switch, account-bound window cleanup, isolated RC smoke (`%APPDATA%\langstudyguard-rc`).
- Source merge only — no public Release, no production EXE replacement, no VPS/SSH, no Cloud Sync activation.
- Isolated RC EXE remains available for Product Owner testing only.

## 3. Next

1. Product Owner may smoke-test RC per [RC_SMOKE_PRODUCT_OWNER.md](../procedures/RC_SMOKE_PRODUCT_OWNER.md).
2. Do not enable `STUDY_SYNC_ENABLED` or start a new milestone from this handoff.
3. Resume 18B.9 only under new Owner authorization.

## 4. STOP / boundaries

- No VPS/SSH, production DB mutation, production sync flag, Drive/OAuth, public GitHub Release.
- Do not overwrite `D:\EnglishApp\dist\langstudyguard.exe` / `.zip` / `.bak`.
- STOP after merge documentation — no new milestone.
