# Phase 18D.1 — Desktop release candidate

Status: **isolated smoke completed. The ready tag was not returned** because the protected learner database and the production sync database changed during the smoke window.  
Date: 2026-11-24  
Proposed release: v1.5.0 — Account Cloud Sync Update  
Packaged source: `29292749da54b0035833321a80e2776007b6ee8e`  
Accepted pilot baseline: `54f452da36211e419ef51a105009c1428b2525a9`

No GitHub Release, tag, or publication. The installed production EXE was not replaced.

## Candidate

| File | SHA-256 |
|------|---------|
| `D:\EnglishApp\.local\builds\18d1-v1.5.0-rc\langstudyguard-rc.exe` | `284f96460279e5812cac74fcefe2c2f407ea98d73502e255a02cf5ce28ffd3f5` |
| `D:\EnglishApp\.local\builds\18d1-v1.5.0-rc\langstudyguard-rc.zip` | `348cbe7feb92c1831f9a5cdf6809f5abfcfc795d4fcbbc16f19e402a45b4f226` |

The embedded manifest is channel `production`, version `1.5.0`, commit `29292749da54b0035833321a80e2776007b6ee8e`. The ZIP entry is `langstudyguard-rc.exe`. PyInstaller 6.22.3, Python 3.13.13. Dependency notes are in `dependencies.json` beside the EXE. The repository `dist\` and `dist-rc\` trees were not used.

The bundled account URL is `https://langstudyguard.com`. The bundled emergency password is the synthetic placeholder `18d1-rc-placeholder-not-for-publication`. It is not the owner password and is not suitable for a public release. The existing bundling path still reads `EMERGENCY_PASSWORD` from a developer `.env`. That mechanism needs a separate release security decision before publication. No API key, account token, OAuth token, SSH credential, real database, or developer `.env` is in the archive.

## Frozen smoke

Launched with `LG_DATA_DIR=D:\EnglishApp\.local\data\18d1-v1.5.0-rc` and `LG_RC_SMOKE=1`. The visible window title is `Language Guard — PRODUCTION BACKEND · RC TEST DATA`. The first screen is the account login form. Starter vocabulary was created only under that data directory.

| Check | Result |
|-------|--------|
| Starts without Python source | Pass |
| Production HTTPS identity, RC data banner | Pass |
| No production auto-update prompt | Pass. No updater dialog. RC smoke does not call the updater. No production updater process was running |
| Installed EXE and Startup shortcut unchanged | Pass, rechecked after logout. EXE `36,050,859` bytes, `2026-11-08T16:18:07Z`, SHA-256 `bbcd5e9a8bb22c72acdf863c94b68f6dbb7cc76717b737c6b93b0e50b28d58c3`. Shortcut `1,273` bytes, `2026-11-08T17:16:53Z` |
| Candidate EXE and ZIP unchanged | Pass. The hashes in the table above match the files after the smoke |
| Signed-in identity | Pass. Home showed `syncpilot_18c4p`, user id 3 |
| Effective data root | Pass for this process. Settings and `accounts\3\account_study.db` are under `.local\data\18d1-v1.5.0-rc`. This process started at `2026-11-24T13:09:26Z` |
| Home Dashboard and Dutch | Pass. Header `Language Guard — PRODUCTION BACKEND`, language `Tiếng Hà Lan`, vocabulary count `2 mục` while signed in |
| Vocabulary download | Pass in the isolated account database. `syncprobe` / `lab-marker-a` revision 4, and the existing `groot` / `big` revision 1. The vocabulary list window was not opened |
| Two attempts and SRS | Pass. Sequences 1 and 2, both exact. Both SRS rows are seen 1, correct 1, wrong 0, streak 1, interval 1 day, state version 1. Outbox 0, conflicts 0, caught up |
| Cloud Sync reaches Synced | Pass. Home label `Cloud Sync: Synced — Máy chủ đã nhận và client đã bắt kịp.` |
| Close and reopen | Pass. The same EXE was closed with `WM_CLOSE` and opened again with the same isolated environment. No rebuild |
| Persistence | Pass. After reopen, the same account, the same device-id SHA-256 prefix `4a6b88fefe82e9c1`, the same two vocabulary rows, the same two attempts, and the same SRS rows |
| Tk callback error | No error dialog on the signed-in home, the reopen, or the logout screen. The windowed EXE has no console log |
| Logout keeps the local database | Pass. The confirmation dialog title was `Đăng xuất`. After the affirmative answer, settings have no token, username, or user id. The home shows `Khách / Chưa đăng nhập` and `Đăng nhập`. `accounts\3\account_study.db` remains, `118,784` bytes, with the same two vocabulary rows, two attempts, and two SRS rows. Logged-out Home then shows the local Dutch library, not the account store |
| Real RC account database untouched | **Fail.** See below |
| Recovery files untouched | Pass. `LanguageGuard-Recovery\vocab-114-20261119-232144` is still `2026-11-19T23:21:44Z` |

The candidate was not rebuilt. No new quiz answer was submitted. The session token was not copied.

## Protected learner database

`%APPDATA%\langstudyguard-rc\accounts\1\account_study.db` is no longer the untouched snapshot. It is now `221,184` bytes, last write `2026-11-24T13:04:32Z`. Integrity is ok. It contains 115 vocabulary rows (114 learner rows plus the existing `groot` row), 6 local attempts from `2026-11-22`, 92 acknowledged `vocab_put` rows, 23 still-pending `vocab_put` rows, and 6 pending progress rows. The acknowledgements were written from `2026-11-24T13:04:21Z` through `13:04:32Z`.

That write is earlier than this isolated process, which started at `2026-11-24T13:09:26Z`. The isolated directory has no file written at `13:04`. The real RC `settings.json` is still the `2026-11-22` account id 1 session. Recovery files were not opened.

Production `study_sync.db` was also rewritten at `2026-11-24T13:04:40Z` and is now `151,552` bytes. `sync_http.py` is still `aa88f693764912f589a5945d7b3f154b587363311130b01295127cb600ddd5d1`. `language-guard.service` is active and its start time is still `2026-11-23T16:43:33Z`. `language-guard-sync-backup.timer` is still disabled and inactive. This check did not restart the service, enable the timer, or edit server files. The sync database change itself is a server-record change and was not reversed.

## Backend

Production `sync_http.py` was read only. Its SHA-256 is still `aa88f693764912f589a5945d7b3f154b587363311130b01295127cb600ddd5d1`. The service is active. `language-guard-sync-backup.timer` is disabled and inactive. The repository file is `3de5c413064240ff8036df9c314006201c302be32003cbeb76db502b2612ca6d` and was not deployed.

The new desktop client uses the same seven sync routes. An authenticated request is read by the current server, so the accepted signed-in sync does not require the new body-drain. That drain is required for clean Windows handling of an early 401 or sync-disabled 404. Those answers currently return before the body is read and can surface as WinError 10053. The client timeout is 15 seconds. The undeployed server change reads at most 32,768 bytes before those early answers and still refuses a larger body without reading it.

If a later approval deploys it: copy only the LF `sync_http.py`, restart `language-guard.service`, and keep the sync flag on. Roll back by restoring the `aa88f693` file. No schema change. This task did not deploy it.

Before real-account migration or wider distribution, enable the already installed sync backup timer only under a separate approval, and keep one verified backup. The timer stays disabled now. Phase 18B.9 stays paused.

## Release notes for v1.5.0

Account Cloud Sync is included for a signed-in learner: vocabulary, learning progress, and explicit conflict handling. The desktop build is 1.5.0.

The public update asset must be named `langstudyguard.zip` and must contain `langstudyguard.exe`. The updater selects that ZIP name first and extracts that EXE name. `langstudyguard-rc.zip` is the private candidate. Publishing it as the update asset would not satisfy the updater.

Upgrade replaces `%LOCALAPPDATA%\langstudyguard\langstudyguard.exe` only after a separate acceptance. Rollback restores the previous EXE, whose current hash is `bbcd5e9a8bb22c72acdf863c94b68f6dbb7cc76717b737c6b93b0e50b28d58c3`. First install copies into that folder and creates `langstudyguard.lnk` with `--lock` only when both are absent. This candidate is named `langstudyguard-rc.exe`, so it runs in place and does not install or change Startup.

The executable is unsigned. Windows SmartScreen can warn. No public release was created.

## Public-release gates

These remain explicit gates. None is cleared by this smoke.

- The synthetic emergency password `18d1-rc-placeholder-not-for-publication` is unsuitable for publication.
- The bundled emergency-password architecture still needs review. `bundle_secrets.py` reads `EMERGENCY_PASSWORD` from a developer `.env`.
- The repository `sync_http.py` correction remains undeployed. Source SHA-256 `3de5c413064240ff8036df9c314006201c302be32003cbeb76db502b2612ca6d`. Production remains `aa88f693764912f589a5945d7b3f154b587363311130b01295127cb600ddd5d1`.
- The recurring Sync backup timer remains disabled.
- The final public ZIP must be named `langstudyguard.zip` and must contain `langstudyguard.exe`. This private ZIP contains `langstudyguard-rc.exe`.

`APP_18D1_DESKTOP_RELEASE_CANDIDATE_READY_FOR_REVIEW` was not returned. The isolated signed-in smoke passed, and the protected account id 1 database did not stay untouched.
