# Active handoff

Rolling coordination checkpoint. See [current_state.md](../current_state.md), [roadmap.md](../roadmap.md), [ACCOUNT-UX-RELEASE-READINESS.md](../plans/ACCOUNT-UX-RELEASE-READINESS.md), and [PRODUCTION-LOGIN-API-COMPATIBILITY.md](../plans/PRODUCTION-LOGIN-API-COMPATIBILITY.md).

## 1. Checkpoint metadata

- Written: 2026-11-19 (Login API compatibility — **Architect Accepted, source merged**).
- **Account UX / RC** — PR #23 **MERGED** (`a08a9e0`).
- **Login compatibility** — PR #24 **MERGED** (`62c567b`); tag `APP_LOGIN_COMPAT_SOURCE_MERGED`.
- **NOT AUTHORIZED:** VPS deployment or production writes. Source merge does not update production.
- **18C.1 / 18C.2 CLOSED**. **18B.9 PAUSED, NOT CLOSED**.
- Staging **RESERVED**. Production Cloud Sync **OFF**. Sync pilot **NO-GO**.

## 2. Last results

- Hardened `/api/login` contract + `/api/session` fallback; RC banner clarified.
- Pre-merge corrections: login is not read-only for VPS verification; `/api/grade` test mocks AI.
- Focused compatibility tests passed.

## 3. Next

1. Future Owner-authorized deploy must separately verify deployed Account Server version, entrypoint, dependencies, exact diff, SQLite backup/rollback, and Cloud Sync OFF.
2. Do not enable `STUDY_SYNC_ENABLED`, rebuild Owner EXE, or resume 18B.9 from this handoff.

## 4. STOP / boundaries

- No VPS/SSH, production DB mutation, production sync flag, Drive/OAuth, public GitHub Release.
- Do not overwrite `D:\EnglishApp\dist\langstudyguard.exe` / `.zip` / `.bak`.
- STOP after merge documentation.
