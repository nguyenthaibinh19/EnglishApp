# Active handoff

Rolling coordination checkpoint. See [current_state.md](../current_state.md), [roadmap.md](../roadmap.md), [ACCOUNT-UX-RELEASE-READINESS.md](../plans/ACCOUNT-UX-RELEASE-READINESS.md), and [PRODUCTION-LOGIN-API-COMPATIBILITY.md](../plans/PRODUCTION-LOGIN-API-COMPATIBILITY.md).

## 1. Checkpoint metadata

- Written: 2026-11-19 (Production login API compatibility hotfix — **STOP for Architect review**).
- **Account UX / RC** — PR #23 **MERGED** / Architect Accepted (`a08a9e0` / approved source `3d44bb5`).
- **Login compatibility** — source PR open; tag `APP_PRODUCTION_LOGIN_COMPATIBILITY_READY`. **No VPS/SSH/deploy** until separate Owner authorization.
- **18C.1 / 18C.2 CLOSED**. **18B.9 PAUSED, NOT CLOSED**.
- Staging **RESERVED**. Production Cloud Sync **OFF**. Sync pilot **NO-GO**.

## 2. Last results

- Root cause: deployed Account Server login predates client `user_id` contract (`{"token"}` only vs RC `login_session`).
- Hardened `/api/login` + `/api/session` regressions; RC login banner clarified.
- Deployment plan documented — not executed.

## 3. Next

1. Architect review of login compatibility PR — merge when Accepted.
2. Owner-authorized VPS deploy of `account_server.py` only after Accepted + backup checklist.
3. Do not enable `STUDY_SYNC_ENABLED` or start unrelated milestones.

## 4. STOP / boundaries

- No VPS/SSH, production DB mutation, production sync flag, Drive/OAuth, public GitHub Release.
- Do not overwrite `D:\EnglishApp\dist\langstudyguard.exe` / `.zip` / `.bak` from this hotfix.
