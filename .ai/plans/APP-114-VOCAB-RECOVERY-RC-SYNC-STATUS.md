# APP-114 — Controlled Dutch vocab recovery + RC Sync status fix

Status: **Architect Accepted — source merged**  
Verdict token: `APP_114_VOCAB_RC_MERGED_ACCEPTED`  
PR: [#25](https://github.com/nguyenthaibinh19/EnglishApp/pull/25) (approved HEAD `ed50fb1cdc6329b6a082a113d40f78a7594d3b2e`)  
Merge commit / `main`: `5cf50abcea849fe1edc6aa3e827258fd837f3d77`  
Cloud Sync: **OFF** (no VPS / `STUDY_SYNC_ENABLED` change)  
18B.9: **PAUSED, NOT CLOSED** · Staging: **RESERVED**  
Local recovery data: **preserved** (no re-import; RC DB / outbox / Guest JSON / recovery backups untouched)

## Authorization

| Field | Value |
|-------|--------|
| Scope | One-time local import of Owner production Guest Dutch vocabulary (114) into isolated RC account `id 1`; client-only Sync 404 status correction |
| Environment | Production RC only (`%APPDATA%\langstudyguard-rc`) |
| Not authorized | VPS/SSH, production DB edits, Cloud Sync ON, production EXE replace, Guest overwrite, Progress/SRS/attempts migration, auto-import on login, GitHub Release |

## Part A — Source fingerprint (preconditions)

| Check | Result |
|-------|--------|
| Source path | `%APPDATA%\langstudyguard\languages\nl\vocab.json` |
| SHA-256 | `ca387ab1bf13a95dd39dd033b0034dfc498fd4fc0e7450ea260161a75d805946` |
| Size | 17268 bytes |
| Valid entries | 114 |
| UUID issues | None (no missing / invalid / duplicate IDs) |
| Target account | RC `accounts\1` (`manhmanhcute` / server-issued id `1`) |
| Pre-import live vocab | 0 |
| Production Guest JSON | Unchanged after import (`source_sha_unchanged: true`) |

## Part B — Backup and import

Recovery directory (outside production Guest tree):

`%LOCALAPPDATA%\LanguageGuard-Recovery\vocab-114-20261119-232144\`

| Artifact | Path / value |
|----------|----------------|
| Source copy | `source-guest-nl-vocab.json` (SHA matches source) |
| Pre-import SQLite backup | `account_study.db.pre.sqlitebackup` |
| Backup SHA-256 | `9efe5eb7cab7b5f2347a6dda13112809e6cd6493268ada32b421349c8aecb72c` |
| Import API | `AccountLocalStore.grant_legacy_consent()` + `import_guest_vocabulary()` |
| Imported / skipped / failed | **114 / 0 / 0** |
| Live RC `nl` count | **114** |
| ID set match | **true** |
| Lexical mismatches | **0** |
| Outbox after import | **114 pending** (not marked Synced) |
| SQLite `integrity_check` | **ok** |

No Progress / attempts / SRS / other Guest history imported. Production Guest file not modified. Production account stores not touched.

### Rollback (RC SQLite only)

While **all** `langstudyguard-rc` processes are closed:

1. Copy `account_study.db.pre.sqlitebackup` over `%APPDATA%\langstudyguard-rc\accounts\1\account_study.db`.
2. Run `PRAGMA integrity_check` → expect `ok`.
3. Confirm live vocabulary count returns to pre-import (0).

**Never** restore or overwrite the production Guest `vocab.json`.

## Part C — Client Sync status correction

### Root cause

Account sync worker starts after login without verifying server Sync routes. With production `STUDY_SYNC_ENABLED` OFF, Sync endpoints return HTTP **404**. The client left status as **Pending**, which implied an upload/download in progress.

### Fix (client-only)

| Path | Change |
|------|--------|
| `app/account_local_store.py` | `STATUS_UNAVAILABLE`; `set_server_sync_unavailable` / `server_sync_unavailable`; status priority ahead of Pending |
| `app/account_sync_engine.py` | Map Sync endpoint **404** → unavailable; **session-scoped** suspend (notify/local edits do not re-hit HTTP); **new engine clears flag** for one fresh capability probe; clear flag on successful cycle |
| `app/app_environment.py` | UI: `Server Sync unavailable` / `Data saved locally; not uploaded` |
| `app/account_session.py` | Surface the same label/detail in account status |
| `tests/test_sync_unavailable_status.py` | Worker-loop: first 404 → unavailable; no retry storm on notify; new session probes once; success clears flag; outbox survives disabled attempts; offline/auth/409 preserved |

UI shows: **Cloud Sync: Server Sync unavailable — Data saved locally; not uploaded**  
Does **not** show Synced. Login / AI APIs unchanged. A future authorized Sync pilot that starts a new engine/session gets one probe; still-disabled servers return to unavailable without a loop.

### Architect R1 lifecycle correction

Persisted `server_sync_unavailable=1` must not permanently block a later engine. `AccountSyncEngine.__init__` resets the flag so login / account switch / engine restart may attempt Sync once. Within one running worker, 404 suspends automatic and notify-driven Sync HTTP for that session only.

## Part D — RC rebuild

| Item | Value |
|------|--------|
| Build script | `build_production_rc.bat` |
| Output | `dist-rc/langstudyguard-rc.exe` only (never `dist/langstudyguard.exe`) |
| RC EXE SHA-256 | `01fa9a587f5040a025c65081bfe5ee5e7550b42dbd8d6568be86f16cd751fe6e` |
| RC EXE size | 36203600 bytes (R1 rebuild) |
| Data root | `%APPDATA%\langstudyguard-rc` |
| Production `dist/` EXE | **Not present / not modified** in this worktree |
| Production Cloud Sync | Remains **OFF** |
| GitHub Release | **Not published** |

## Boundaries confirmed

- No VPS/SSH · No production data edits · No production EXE replacement  
- No account deletion/reset · No Cloud Sync activation  
- No Progress/attempts/SRS migration · No automatic Guest import on login  
- 18B.9 remains PAUSED · Staging remains RESERVED
