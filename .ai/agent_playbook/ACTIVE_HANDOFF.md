# Active handoff

Rolling coordination checkpoint. See [current_state.md](../current_state.md), [roadmap.md](../roadmap.md), [ACCOUNT-UX-RELEASE-READINESS.md](../plans/ACCOUNT-UX-RELEASE-READINESS.md), and [ADR-025](../decisions/ADR-025-environment-identity-and-isolation.md).

## 1. Checkpoint metadata

- Written: 2026-11-19 (Account UX RC **final** — F3 complete data isolation).
- **ADR-025 Accepted** (PR #22 merge `2da93c3`).
- **Account UX / Release Candidate** — PR #23; tag `APP_ACCOUNT_UX_RC_FINAL_READY`; **STOP for Architect final merge decision**.
- **18C.1 / 18C.2 CLOSED**. **18B.9 PAUSED, NOT CLOSED**.
- Staging **RESERVED**. Production Cloud Sync **OFF**. Production sync pilot **NO-GO**.

## 2. Last results

- F1 / F2 accepted at source-review level (unchanged this pass).
- F3 final: RC AppData `%APPDATA%\langstudyguard-rc`; no production token/settings adoption; updater blocked; production EXE semantics unchanged.
- Focused RC isolation + Account UX + install regressions green.
- Production `dist\langstudyguard.exe` not modified by RC rebuild.

## 3. Next

1. Architect final merge decision on PR #23 — no merge until Accepted.
2. Owner may smoke-test RC per [RC_SMOKE_PRODUCT_OWNER.md](../procedures/RC_SMOKE_PRODUCT_OWNER.md).
3. Do not enable `STUDY_SYNC_ENABLED` or start a new milestone from this handoff.

## 4. STOP / boundaries

- No VPS/SSH, production DB mutation, production sync flag, Drive/OAuth, public GitHub Release.
- Do not overwrite `D:\EnglishApp\dist\langstudyguard.exe` / `.zip` / `.bak`.
