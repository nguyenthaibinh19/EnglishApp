# Hetzner Account Server — Read-Only Login API Inspection

Status: **COMPLETE — read-only** (`APP_HETZNER_LOGIN_READONLY_INSPECTION_READY`).  
**No production mutation, restart, deploy, login probe, or backup creation was performed.**

| Field | Value |
|-------|--------|
| Authorization | Product Owner APPROVED — VPS read-only inspection only |
| Inspected at (UTC) | 2026-11-19 ~22:50 |
| GitHub `main` baseline | `4f339c9b994dd33318143c8b350790acaf98a589` (PR #24 merged) |
| Host | Existing authorized Hetzner SSH target (IP/credentials not published here) |

## 1. Service and deployment layout

| Item | Finding |
|------|---------|
| Service | `language-guard.service` — **active / running** |
| Unit file | `/etc/systemd/system/language-guard.service` |
| User | `guard` |
| WorkingDirectory | `/opt/language-guard` |
| ExecStart | `/opt/language-guard/venv/bin/python account_server.py serve` |
| Bind | `ACCOUNT_BIND=127.0.0.1`, `ACCOUNT_PORT=8765` (Caddy front-end expected) |
| Process cwd / module | cwd=`/opt/language-guard`; running file=`/opt/language-guard/account_server.py` |
| Python | venv → system **Python 3.14.4** |
| Layout | **Flat copied application tree** under `/opt/language-guard` (not a Git checkout; **no** `.git`) |
| Desktop `app/` package | **Absent** on VPS (server modules live at tree root) |

Systemd unit Environment lines observed (non-secret): `ACCOUNT_BIND`, `ACCOUNT_PORT` only. No `EnvironmentFile=` in the unit. A `.env` file exists (`0600`, `guard:guard`); contents were **not** read or logged.

## 2. Deployed file hashes vs GitHub `main`

| Deployed path | SHA-256 (deployed) | Closest Git blob match | `main` expected SHA-256 |
|---------------|--------------------|------------------------|-------------------------|
| `/opt/language-guard/account_server.py` | `1662fb3b24f014f4b836d10f64f8adaf2761c531c1768b749630a6cea29b78da` | `599e473` (2026-10-28, feature-gated sync API) | `4101e111abee9400217334b468901c5e033c6be1fa79be7ba189c72f749685b9` |
| `/opt/language-guard/account_store.py` | `6afc3235dbea43b49f942cf1f38a97344d02971d362703017e6c9598dc02a534` | `b112009` (2026-09-29) | `187345f6b8d8eae46ae9cdf290dbc33f556e7d29518046ed5891b4e9da73a331` |
| `/opt/language-guard/sync_http.py` | `7b50069d9c42ab0aa3236959d4cbb0f8995ed1748f6582897d9b319bc8344d0f` | `599e473` | `a3970550cc0cfb58124804135ed49ea0004e14b8a8de51c5d027b200bb3a5222` |

**Entrypoint confirmation:** importing from `/opt/language-guard` resolves `account_server` / `account_store` / `sync_http` to the same hashed files above. The running service uses those files.

## 3. `/api/login` and `/api/session` compatibility

Static source inspection of the **running** `account_server.py` (no live `POST`):

| Check | Deployed result |
|-------|-----------------|
| `/api/login` present | Yes |
| Login success body | **`{"token": token}` only** |
| Login returns `user_id` | **No** |
| Login returns `username` | **No** |
| `/api/session` route | **Absent** |
| `account_store.user_for_token()` | **Present** |
| Stable integer `users.id` | **Present** (store selects `users.id`) |

This matches the RC client error `Máy chủ không trả về user_id.`: authentication can still return HTTP 200 with a token, while `login_session()` rejects the body.

Journal meta (method/path/status only; no account names/tokens): recent `POST /api/login` responses were **200**, consistent with token-only success on the old contract.

Git diff `599e473..main` for `app/account_server.py` is **only** the login/`/api/session` contract changes from 18C.1 + PR #24 (≈28 lines). No other account_server behavioral drift relative to the deployed blob.

## 4. Cloud Sync flag

| Check | Result |
|-------|--------|
| Process environ `STUDY_SYNC_ENABLED` | **UNSET** |
| Effective status | **OFF** |
| `sync_http.sync_enabled()` in-process (cwd import) | `False` |
| `study_sync.db` | **ABSENT** |
| `language-guard-sync-backup.timer` | **disabled / inactive** |

**Not ON.** Inspection continued.

## 5. Backup / rollback readiness (read-only)

| Item | Finding |
|------|---------|
| Live DB | `/opt/language-guard/accounts.db` (`0600`, `guard:guard`; mtime reflects normal operation — **not opened**) |
| Backup dir | `/var/backups/language-guard/` (mode `0700`, `guard`) |
| Mechanism | `language-guard-backup.timer` **enabled/active**; `OnCalendar=*-*-* 03:15:00` (+ randomized delay); ExecStart `backup_accounts.py` |
| Recent backups | Daily `accounts-YYYYMMDD-*.db` present (e.g. newest inspected listing: `accounts-20261119-032526.db`) |
| This inspection | **Did not** create, copy, open, or restore any backup |

**Safe future hotfix prerequisites (not executed):**

1. Confirm service still points at `/opt/language-guard/account_server.py`.
2. Copy pre-change SHA-256 of that file; retain/verify latest accounts backup (or take a new backup under separate authorization).
3. Replace **only** `account_server.py` with `main` bytes; restart `language-guard.service` under separate authorization.
4. Rollback: restore previous `account_server.py` bytes + restart. Schema unchanged — no accounts.db restore required for this hotfix unless a write incident occurs.

## 6. Deployment compatibility assessment

### Can the minimum future deploy be `account_server.py` only?

**Yes — assessed as safe for the login contract**, given current VPS package:

| Dependency | Required for this hotfix? | Why |
|------------|---------------------------|-----|
| `account_server.py` | **Yes — replace** | Adds `user_id`/`username` on `/api/login` and `/api/session` |
| `account_store.py` | **No** | Deployed store already has `user_for_token` + integer `users.id` |
| `sync_http.py` | **No** | Unrelated to login contract; sync remains flag-gated OFF |
| `config.py` / AI modules | **No** | Main `account_server` import set unchanged vs deployed era; login path does not need newer config |

**Expected new `account_server.py` SHA-256 (GitHub `main` / local tree at inspection):**  
`4101e111abee9400217334b468901c5e033c6be1fa79be7ba189c72f749685b9`

### Risks / downtime / AI

| Topic | Assessment |
|-------|------------|
| Existing accounts / passwords | Unchanged (no DB migration; store untouched) |
| Older token-only clients | Remain compatible (extra JSON fields) |
| AI Grade / Reading / Listening | Same module imports; login-only diff vs deployed blob |
| Cloud Sync | Remains OFF if `STUDY_SYNC_ENABLED` stays unset |
| Service downtime | Brief restart window only (separately authorized) |
| Wrong-file risk | Deploy must target **flat** `/opt/language-guard/account_server.py`, not an `app/` subfolder |

### Recommended minimal future deployment (NOT AUTHORIZED now)

1. Read-only re-verify hashes immediately before change.  
2. Authorized backup of `account_server.py` (+ optional fresh `accounts.db` backup).  
3. Replace `/opt/language-guard/account_server.py` only with `main` content.  
4. Restart `language-guard.service`.  
5. Authorized post-deploy RC login smoke (creates sessions — outside this inspection).  
6. Confirm sync still OFF.

## 7. Boundaries preserved

- PR #24 source **MERGED** (not deployed by this task)
- ADR-025 Accepted
- 18C.1 / 18C.2 CLOSED
- 18B.9 PAUSED, NOT CLOSED
- Staging RESERVED
- Production Cloud Sync **OFF**
- Production Sync Pilot **NO-GO**

## 8. Mutation confirmation

**None.** No file edits, deploys, service restarts/reloads/stops, DB writes, login/session API probes, backup create/restore, systemd/Caddy/firewall changes, or `STUDY_SYNC_ENABLED` changes.
