# Production Login API Compatibility

Status: **Architect Accepted — source merge** (`APP_LOGIN_COMPAT_SOURCE_MERGED`). Source merge only — **no VPS/SSH/deploy** until separate Owner authorization.

## Root cause (evidence)

| Layer | Finding |
|-------|---------|
| Owner symptom | RC login shows `Máy chủ không trả về user_id.` |
| Client (`account_client.login_session`) | Requires integer `user_id` from `/api/login` (added for Account UX / per-account local stores). Never derives id from username. |
| Current `main` server | Since `618f457` (18C.1), `/api/login` returns `token` + `user_id` + `username`, and `/api/session` returns `{user_id, username}`. |
| Pre-`618f457` server | `/api/login` returned only `{"token": token}`; **no** `/api/session`. |
| Likely production posture | Deployed Account Server package **predates** the client contract. **Source on `main` is not evidence of deploy.** |

This hotfix hardens the login contract (always emit `user_id`/`username` on success), adds a client `/api/session` fallback for token-only login bodies, locks regressions, and documents a minimal deploy plan. It does **not** enable Cloud Sync or migrate accounts.

## Source change inventory (this PR)

| Path | Change |
|------|--------|
| `app/account_server.py` | Successful `/api/login` always returns `token`, `user_id`, `username`; fail closed if session user missing. `/api/session` unchanged. |
| `app/account_client.py` | If login omits `user_id`, resolve once via `/api/session` with the issued token (still server-issued; never invent from username). |
| `app/setup_wizard.py` | RC login banner shows `PRODUCTION BACKEND · RC TEST DATA` (not plain `PRODUCTION`). |
| `tests/test_login_api_compatibility.py` | Synthetic local DB compatibility suite; sync remains OFF. |
| This plan | Deploy verification / backup / rollback / smoke — Owner-authorized later. |

**Not in scope:** account DB migration, `STUDY_SYNC_ENABLED`, production EXE replace, public Release, staging activation.

## Deployed-version verification (strictly read-only, when authorized)

Initial VPS version verification must **not** call `POST /api/login`. Login is **not** read-only: a successful login **inserts a session row** into `accounts.db`.

1. On the VPS account service host, record running unit name, working directory / entrypoint, and service dependencies (e.g. `language-guard.service`).
2. Compare SHA-256 of deployed `account_server.py` (and co-located modules such as `account_store.py` if present) to `main` at the merge commit. Diff the exact proposed replacement against the deployed package before any write.
3. Confirm `STUDY_SYNC_ENABLED` is unset / not `1` in the service environment (read-only env inspection).
4. Authenticated login smoke (`POST /api/login` / RC login) is a **separately authorized deployment step** after backup — never part of the initial read-only version check. Do not use live learner passwords in logs.

## Pre-deployment backup and rollback

1. Stop is **not** required for a file copy if the service is restarted cleanly afterward; prefer: backup → copy → restart.
2. Backup at least: deployed `account_server.py`, `account_store.py` (if replaced), and a copy of `accounts.db` (accounts backup mode / existing Owner backup scripts).
3. Record previous file SHA-256s.
4. Rollback: restore backed-up Python files, restart service, re-run login smoke. **Do not** restore `accounts.db` unless a write incident occurred (this change does not mutate the schema).

## Exact deploy file set (proposed)

Minimum:

- `app/account_server.py`

Recommended same package for consistency (no schema change):

- `app/account_client.py` is **desktop-only** — not required on VPS.
- `app/account_store.py` — deploy only if the VPS copy drifts; login/session use existing `user_for_token` / `users.id`.

Restart the account HTTP service after copy. **Do not** set `STUDY_SYNC_ENABLED=1`. **Do not** run sync DB migrations.

## Post-deployment login smoke

1. From an Owner machine, run `langstudyguard-rc.exe` (isolated `%APPDATA%\langstudyguard-rc`).
2. Confirm chrome / login banner: **PRODUCTION BACKEND · RC TEST DATA**.
3. Log in with a known test account — expect success (no `user_id` error).
4. Log out / log in again — same account identity.
5. Wrong password still rejected.
6. Confirm Cloud Sync remains disabled / not “Synced”.
7. Confirm production AppData / installed EXE untouched by RC.

## Confirmation checklist

- [ ] No Account Sync activation
- [ ] No accounts.db schema migration
- [ ] No production desktop EXE replacement from this PR alone
- [ ] Older clients that only read `token` still work (extra JSON fields)
- [ ] 18B.9 remains PAUSED; staging RESERVED; Cloud Sync OFF; sync pilot NO-GO

## Status preserved

- ADR-025 Accepted
- Account UX / RC source merged (PR #23)
- 18C.1 / 18C.2 CLOSED
- 18B.9 PAUSED, NOT CLOSED
- Staging RESERVED
- Production Cloud Sync OFF
