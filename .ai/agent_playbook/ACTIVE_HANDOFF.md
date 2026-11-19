# Active handoff

Rolling coordination checkpoint. See [current_state.md](../current_state.md), [roadmap.md](../roadmap.md), [ACCOUNT-UX-RELEASE-READINESS.md](../plans/ACCOUNT-UX-RELEASE-READINESS.md), and [ADR-025](../decisions/ADR-025-environment-identity-and-isolation.md).

## 1. Checkpoint metadata

- Written: 2026-11-19 (Account UX + production RC readiness).
- **ADR-025 Accepted** (PR #22 merge `2da93c3`).
- **Account UX / Release Candidate** — implementation PR open; **STOP for Architect review** (do not merge/release/deploy until Accepted).
- **18C.1 / 18C.2 CLOSED**. **18B.9 PAUSED, NOT CLOSED**.
- Staging **RESERVED**. Production Cloud Sync **OFF**.

## 2. Last results

- FreeHome + StudyMaster Account panel: Log in / Log out / Switch account.
- Two-device automated scenarios A (isolation) and B (same-account sync) in tests.
- Production RC build script → `dist-rc/` (does not overwrite `dist/`).
- Sync pilot: **NO-GO** — no per-account allowlist; flag remains off.

## 3. Next

1. Architect review of Account UX / RC PR — no merge until Accepted.
2. Owner may smoke-test RC on a clean PC when ready.
3. Do not enable `STUDY_SYNC_ENABLED` or start a new milestone from this handoff.
4. Resume 18B.9 only under new Owner authorization.

## 4. STOP / boundaries

- No VPS/SSH, production DB mutation, production sync flag, Drive/OAuth, public GitHub Release.
- Do not overwrite `D:\EnglishApp\dist\langstudyguard.exe` / `.zip` / `.bak`.
